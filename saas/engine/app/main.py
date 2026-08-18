"""Service de calcul data/IA (sans etat) pour la plateforme DataAnalyst AI.

Encapsule les agents Python verifies (profiler, cleaning, analysis, documentation,
KPI) derriere une API HTTP appelee par le backend Rust. Ne stocke rien : recoit
des donnees + parametres, renvoie du JSON.
"""

import os
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.analysis_agent import AnalysisAgent
from agents.chat_agent import ChatAnalystAgent
from agents.cleaning_agent import CleaningAgent
from agents.dashboard_agent import DashboardAgent, KpiProposerAgent
from agents.documentation_agent import DocumentationAgent
from agents.kpi_agent import KPIAgent
from agents.profiler_agent import ProfilerAgent
from agents.report_agent import ReportAgent
from agents.schema_agent import SchemaAgent
from agents.sql_agent import SQLAgent

from . import apparence, nettoyage, progres, reporting, structuration, warehouse
from .dataframes import (
    _clean_for_json,
    apply_filters,
    column_values,
    dataframe_from_payload,
    feuilles_du_classeur,
    format_fichier,
    octets_du_payload,
    preview_records,
)

app = FastAPI(title="DataAnalyst AI — Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("ENGINE_ALLOW_ORIGINS", "*").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agents deterministes (reutilisables, sans cle API)
_profiler = ProfilerAgent()
_cleaner = CleaningAgent()
_analyzer = AnalysisAgent()
_documentor = DocumentationAgent()
_kpi = KPIAgent()
_chat = ChatAnalystAgent()
_sql = SQLAgent()
_dashboard = DashboardAgent()
_proposer = KpiProposerAgent()
_schema = SchemaAgent()
_reporter = ReportAgent()

# Les agents lisent ANTHROPIC_API_KEY dans l'environnement du processus.
# On serialise les appels IA pour poser la cle du bon utilisateur sans course.
# NOTE robustesse : a paralleliser via un pool de process par tenant a l'echelle.
_ai_lock = threading.Lock()


def _run_with_key(api_key: str, fn):
    if not api_key:
        raise HTTPException(status_code=400, detail="Cle API Anthropic requise pour cette operation")
    with _ai_lock:
        previous = os.environ.get("ANTHROPIC_API_KEY", "")
        os.environ["ANTHROPIC_API_KEY"] = api_key
        try:
            resultat = fn()
        finally:
            os.environ["ANTHROPIC_API_KEY"] = previous

    # Un agent en echec renvoie {"error": ...} plutot que de lever. Sans ce
    # controle, l'appelant lisait un plan vide et l'interface affichait une
    # bulle vide : l'utilisateur ne voyait ni resultat, ni raison.
    if isinstance(resultat, dict) and resultat.get("error"):
        raise HTTPException(status_code=502, detail=_motif_ia(str(resultat["error"])))
    return resultat


def _motif_ia(brut: str) -> str:
    """Traduit l'erreur du fournisseur en phrase utile.

    Le message d'origine est un JSON d'API en anglais ; tel quel il n'apprend
    rien a quelqu'un qui voulait juste changer une couleur.
    """
    texte = brut.lower()
    if "usage limit" in texte or "credit balance" in texte or "quota" in texte:
        return (
            "Le budget de l'API Anthropic est épuisé pour cette période. "
            "Tout ce qui ne passe pas par un modèle reste disponible : import, "
            "nettoyage, découpage, requêtes SQL et tableau de bord existant."
        )
    if "rate limit" in texte or "429" in texte:
        return "Trop de demandes d'un coup : réessayez dans quelques secondes."
    if "authentication" in texte or "invalid x-api-key" in texte or "401" in texte:
        return "La clé API Anthropic est refusée : vérifiez ANTHROPIC_API_KEY."
    if "connexion" in texte or "connection" in texte:
        return "Le fournisseur du modèle est injoignable."
    return "Le modèle n'a pas pu répondre. Le détail technique est dans les journaux."


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────
class DataPayload(BaseModel):
    csv_text: str | None = None
    # Fichier binaire (classeur Excel) encode en base64 : un .xlsx ne survit
    # pas a un transport en texte.
    file_base64: str | None = None
    # Feuille voulue dans un classeur ; a defaut, la premiere non vide.
    sheet: str | None = None
    records: list | None = None
    filename: str | None = None


class ProfileOp(DataPayload):
    pass


class CleanPlanOp(DataPayload):
    api_key: str = ""


class AxesOp(BaseModel):
    profile: dict
    api_key: str = ""


class DictionaryOp(DataPayload):
    api_key: str = ""


class KpiSuggestOp(BaseModel):
    profile: dict
    dictionary: dict | None = None
    api_key: str = ""


class KpiComputeOp(DataPayload):
    spec: dict
    filters: dict | None = None


class ValuesOp(DataPayload):
    column: str


class ChatOp(DataPayload):
    message: str
    history: list = []
    profile: dict | None = None
    api_key: str = ""


class CleanApplyOp(DataPayload):
    actions: list = []


class CorrelationsOp(DataPayload):
    pass


class SegmentOp(DataPayload):
    columns: list = []
    n_clusters: int = 3


class TimeOp(DataPayload):
    date_col: str


class WarehouseOp(DataPayload):
    dictionary: dict | None = None
    api_key: str = ""


class ExportOp(BaseModel):
    dictionary: dict
    model: dict | None = None
    dataset_name: str = "dataset"


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "engine"}


@app.post("/v1/files/inspect")
def files_inspect(op: DataPayload):
    """Reconnait le format d'un fichier et, pour un classeur, liste ses feuilles.

    Appele AVANT l'ingestion : c'est ce qui permet de demander a l'utilisateur
    quelle feuille importer plutot que d'en choisir une a sa place.
    """
    donnees = octets_du_payload(op.model_dump())
    if donnees is None:
        raise HTTPException(status_code=400, detail="Aucun fichier recu")

    format_ = format_fichier(donnees)
    if format_ == "csv":
        return {"format": "csv", "feuilles": []}

    try:
        feuilles = feuilles_du_classeur(donnees)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Classeur illisible : {str(e).splitlines()[0]}"
        ) from e
    return _clean_for_json({"format": format_, "feuilles": feuilles})


@app.post("/v1/files/diagnose")
def files_diagnose(op: DataPayload):
    """Diagnostic de qualite d'un fichier avant chargement.

    Entierement deterministe : les doublons, colonnes vides et nombres
    stockes en texte se constatent. Aucun appel a un modele, donc aucune
    latence ni cout — et ca fonctionne meme sans cle API.
    """
    df = dataframe_from_payload(op.model_dump())
    diag = nettoyage.diagnostiquer(df)

    # L'impact chiffre de chaque action est calcule sur les vraies donnees :
    # l'utilisateur voit ce qu'il perd avant d'accepter.
    for action in diag["actions"]:
        if action["type"] == "parse_number":
            converties = nettoyage.parse_nombre(df[action["column"]])
            perdues = int(converties.isna().sum() - df[action["column"]].isna().sum())
            action["impact"] = (
                f"{len(df)} valeur(s) converties"
                + (f", {perdues} non convertible(s)" if perdues > 0 else "")
            )
        else:
            action["impact"] = _cleaner.estimate_impact(df, action)

    # Decoupage en tables liees : detection de dependances fonctionnelles,
    # deterministe elle aussi.
    #
    # Calcule sur les donnees NETTOYEES, pas sur le fichier brut : des espaces
    # parasites suffisent a masquer une dependance reelle (« Paris » et
    # « Paris  » passeraient pour deux villes du meme client), et le decoupage
    # proposerait alors moins de tables qu'il ne le devrait.
    recommandees = [a for a in diag["actions"] if a.get("recommande")]
    propre = df
    if recommandees:
        propre, _, restantes = nettoyage.appliquer_supplementaires(df, recommandees)
        if restantes:
            propre, _ = _cleaner.apply_actions(propre, restantes)
    diag["decoupages"] = structuration.proposer_decoupage(propre)
    diag["apercu"] = preview_records(df, 8)
    return _clean_for_json(diag)


@app.post("/v1/profile")
def profile(op: ProfileOp):
    df = dataframe_from_payload(op.model_dump())
    prof = _profiler.profile_dataframe(df)
    return {
        "profile": _clean_for_json(prof),
        "preview": preview_records(df),
    }


@app.post("/v1/clean/plan")
def clean_plan(op: CleanPlanOp):
    df = dataframe_from_payload(op.model_dump())
    prof = _profiler.profile_dataframe(df)
    suggestions = _run_with_key(op.api_key, lambda: _cleaner.suggest_cleaning(prof))
    actions = suggestions.get("actions", []) if isinstance(suggestions, dict) else []
    for a in actions:
        a["impact"] = _cleaner.estimate_impact(df, a)
    return {"profile": _clean_for_json(prof), "plan": _clean_for_json(suggestions)}


@app.post("/v1/clean/apply")
def clean_apply(op: CleanApplyOp):
    df = dataframe_from_payload(op.model_dump())
    cleaned, log = _cleaner.apply_actions(df, op.actions or [])
    return _clean_for_json({
        "rows_before": len(df),
        "rows_after": len(cleaned),
        "cols_after": len(cleaned.columns),
        "log": log,
        "preview": preview_records(cleaned),
        "cleaned_csv": cleaned.to_csv(index=False),
    })


@app.post("/v1/analyze/axes")
def analyze_axes(op: AxesOp):
    axes = _run_with_key(op.api_key, lambda: _analyzer.suggest_axes(op.profile))
    return {"axes": _clean_for_json(axes)}


@app.post("/v1/doc/dictionary")
def doc_dictionary(op: DictionaryOp):
    df = dataframe_from_payload(op.model_dump())
    prof = _profiler.profile_dataframe(df)
    dictionary = _run_with_key(op.api_key, lambda: _documentor.generate_dictionary(df, prof))
    return {"dictionary": _clean_for_json(dictionary)}


# ── Etape 3 : Exploration (EDA) ──────────────────
@app.post("/v1/analyze/correlations")
def analyze_correlations(op: CorrelationsOp):
    import pandas as pd

    df = dataframe_from_payload(op.model_dump())
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if len(num_cols) < 2:
        return {"columns": [], "matrix": [], "pairs": []}
    corr = df[num_cols].corr().round(3)
    # Paires les plus fortes (triangle superieur)
    pairs = []
    for i in range(len(num_cols)):
        for j in range(i + 1, len(num_cols)):
            pairs.append({
                "a": num_cols[i], "b": num_cols[j],
                "r": float(corr.iloc[i, j]),
            })
    pairs.sort(key=lambda p: abs(p["r"]) if p["r"] == p["r"] else 0, reverse=True)
    return _clean_for_json({
        "columns": num_cols,
        "matrix": corr.values.tolist(),
        "pairs": pairs[:8],
    })


@app.post("/v1/analyze/segment")
def analyze_segment(op: SegmentOp):
    df = dataframe_from_payload(op.model_dump())
    cols = op.columns or []
    if len(cols) < 2:
        return {"error": "Sélectionnez au moins 2 colonnes numériques"}
    seg_df, info = _analyzer.compute_segmentation(df, cols, op.n_clusters)
    if "error" in info:
        return {"error": info["error"]}
    points = seg_df[[cols[0], cols[1], "segment"]].rename(
        columns={cols[0]: "x", cols[1]: "y"}
    )
    return _clean_for_json({
        "info": info,
        "x_label": cols[0],
        "y_label": cols[1],
        "points": points.to_dict(orient="records"),
    })


@app.post("/v1/analyze/time")
def analyze_time(op: TimeOp):
    df = dataframe_from_payload(op.model_dump())
    res = _analyzer.compute_time_analysis(df, op.date_col)
    return _clean_for_json(res)


# ── Etape 4 : Documentation (entrepot + exports) ──
@app.post("/v1/doc/warehouse")
def doc_warehouse(op: WarehouseOp):
    df = dataframe_from_payload(op.model_dump())
    prof = _profiler.profile_dataframe(df)
    model = _run_with_key(
        op.api_key, lambda: _documentor.propose_warehouse_model(df, prof, op.dictionary)
    )
    return {"model": _clean_for_json(model)}


@app.post("/v1/doc/export")
def doc_export(op: ExportOp):
    md = _documentor.export_markdown(op.dictionary, op.model, op.dataset_name)
    dbt = _documentor.export_dbt_yaml(op.dictionary, op.dataset_name)
    return {"markdown": md, "dbt_yaml": dbt}


# ── Etape 5 : KPIs ───────────────────────────────
@app.post("/v1/kpi/suggest")
def kpi_suggest(op: KpiSuggestOp):
    result = _run_with_key(
        op.api_key, lambda: _kpi.suggest_kpis(op.profile, op.dictionary)
    )
    return {"kpis": _clean_for_json(result)}


@app.post("/v1/chat")
def chat(op: ChatOp):
    df = dataframe_from_payload(op.model_dump())
    profile = op.profile or _profiler.profile_dataframe(df)
    result = _run_with_key(
        op.api_key, lambda: _chat.answer(profile, op.message, op.history)
    )
    if not isinstance(result, dict):
        result = {"reponse": str(result), "visualisation": None, "suggestions": []}

    viz = result.get("visualisation")
    computed = None
    if isinstance(viz, dict) and viz.get("operation"):
        spec = {
            "operation": viz.get("operation"),
            "colonne": viz.get("colonne"),
            "operation_denominateur": viz.get("operation_denominateur", "count"),
            "colonne_denominateur": viz.get("colonne_denominateur"),
            "group_by": viz.get("group_by"),
            "date_col": viz.get("date_col"),
            "granularite": viz.get("granularite", "mois"),
        }
        r = _kpi.compute_kpi(df, spec)
        computed = {
            "titre": viz.get("titre", ""),
            "format": viz.get("format", "nombre"),
            "valeur": r.get("valeur"),
            "erreur": r.get("erreur"),
            "serie": r["serie"].to_dict(orient="records") if r.get("serie") is not None else None,
            "groupes": r["groupes"].to_dict(orient="records") if r.get("groupes") is not None else None,
            "spec": spec,
        }
    return _clean_for_json({
        "reponse": result.get("reponse", ""),
        "visualisation": computed,
        "suggestions": result.get("suggestions", []),
    })


@app.post("/v1/analyze/values")
def analyze_values(op: ValuesOp):
    df = dataframe_from_payload(op.model_dump())
    return {"values": column_values(df, op.column)}


# ══════════════════════════════════════════════
# Entrepot analytique (DuckDB) : ETL, SQL, rafraichissement
# ══════════════════════════════════════════════
class WarehouseRef(BaseModel):
    project_id: str


class IngestOp(DataPayload):
    project_id: str
    table: str = "donnees"
    mode: str = "replace"
    # Actions de nettoyage validees par l'utilisateur, appliquees avant le chargement
    clean_actions: list = []
    renames: dict | None = None
    # Tables a extraire du tableau plat (dependances fonctionnelles validees
    # par l'utilisateur). Vide = on charge une table unique.
    decoupage: list = []
    # Renvoyer le CSV normalise coute de la bande passante : inutile quand
    # l'appelant ne le conserve pas.
    return_csv: bool = False
    # Identifiant de suivi : permet a l'interface de savoir ou en est la
    # pipeline pendant qu'elle tourne. Vide = aucun suivi.
    trace: str = ""


class SqlOp(BaseModel):
    project_id: str
    sql: str
    limit: int = 5000


class WarehouseChatOp(BaseModel):
    project_id: str
    message: str
    history: list = []
    dictionary: dict | None = None
    api_key: str = ""


class DashboardEditOp(BaseModel):
    project_id: str
    message: str
    widgets: list = []
    history: list = []
    api_key: str = ""


class ProposeOp(BaseModel):
    project_id: str
    dictionary: dict | None = None
    langue: str = "fr"
    api_key: str = ""


class SchemaCheckOp(DataPayload):
    project_id: str
    table: str = "donnees"
    langue: str = "fr"
    api_key: str = ""
    # Pipeline retenue a l'import : elle est rejouee sur le nouveau fichier
    # avant comparaison, pour comparer ce qui sera reellement charge.
    clean_actions: list = []
    decoupage: list = []


def _warehouse_guard(fn):
    """Traduit une erreur d'entrepot en 400 lisible plutot qu'en 500."""
    try:
        return fn()
    except warehouse.WarehouseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _appliquer_pipeline(df, clean_actions: list, decoupage: list):
    """Rejoue la pipeline validee a l'import : memes corrections, meme decoupage.

    Renvoie la table de faits telle qu'elle sera chargee — les colonnes
    parties en dimension n'y figurent plus. Sert au controle de structure
    d'un rafraichissement, qui doit comparer l'etat final, pas le fichier brut.
    """
    if clean_actions:
        df, _, restantes = nettoyage.appliquer_supplementaires(df, clean_actions)
        if restantes:
            df, _ = _cleaner.apply_actions(df, restantes)
    if decoupage:
        df, _ = structuration.decouper(df, decoupage)
    return df


def _milliers(n: int) -> str:
    """12480 -> « 12 480 » : un nombre de lignes se lit mieux espace."""
    return f"{int(n):,}".replace(",", " ")


@app.post("/v1/warehouse/ingest")
def warehouse_ingest(op: IngestOp):
    """Pipeline ETL : extraction du fichier -> nettoyage -> chargement typé.

    Chaque etape s'annonce dans `progres` pendant qu'elle s'execute : le plan
    est publie d'emblee pour que l'interface montre ce qui va se passer, et
    non une liste qui se decouvre au fur et a mesure.
    """
    plan = [("lecture", "Lecture du fichier")]
    if op.clean_actions:
        plan.append(("nettoyage", "Application des corrections"))
    if op.decoupage:
        plan.append(("decoupage", "Extraction des tables liées"))
    plan.append(("chargement", "Chargement dans l'entrepôt"))
    plan.append(("profil", "Analyse des colonnes"))
    progres.planifier(op.trace, plan)

    try:
        progres.commencer(op.trace, "lecture")
        df = dataframe_from_payload(op.model_dump())
        progres.achever(
            op.trace, "lecture",
            f"{_milliers(len(df))} lignes · {len(df.columns)} colonnes",
        )

        log = []
        if op.clean_actions:
            progres.commencer(op.trace, "nettoyage")
            # Les types ajoutes par le diagnostic sont traites d'abord, le reste
            # part vers l'agent de nettoyage historique.
            df, log, restantes = nettoyage.appliquer_supplementaires(df, op.clean_actions)
            if restantes:
                df, suite = _cleaner.apply_actions(df, restantes)
                log += suite
            progres.achever(
                op.trace, "nettoyage",
                f"{len(log)} correction{'s' if len(log) > 1 else ''} appliquée"
                f"{'s' if len(log) > 1 else ''} · {_milliers(len(df))} lignes restantes",
            )

        if op.mode == "append":
            df = _warehouse_guard(
                lambda: warehouse.align_to_table(op.project_id, op.table, df, op.renames or {})
            )
        elif op.renames:
            df = df.rename(columns=op.renames)

        # Decoupage : la table principale garde son nom, chaque dimension prend
        # le sien. Les liens sont redetectes a l'affichage du schema.
        dimensions = []
        if op.decoupage:
            progres.commencer(op.trace, "decoupage")
            df, dimensions = structuration.decouper(df, op.decoupage)
            log.append(f"[OK] tableau decoupe en {len(dimensions) + 1} tables liees")
            progres.achever(
                op.trace, "decoupage",
                ", ".join(d["nom"] for d in dimensions) or "aucune table extraite",
            )

        progres.commencer(op.trace, "chargement")
        res = _warehouse_guard(lambda: warehouse.ingest(op.project_id, op.table, df, op.mode))

        tables_creees = []
        for dim in dimensions:
            nom = warehouse.sql_identifier(dim["nom"], "dimension")
            try:
                r = warehouse.ingest(op.project_id, nom, dim["dataframe"], "replace")
            except warehouse.WarehouseError as e:
                log.append(f"[ERREUR] table « {nom} » non creee : {e}")
                continue
            tables_creees.append({
                "table": r["table"], "rows": r["rows"],
                "columns": r["columns"], "column_map": r["column_map"],
                "cle": dim["cle"],
            })
        progres.achever(
            op.trace, "chargement",
            f"{1 + len(tables_creees)} table{'s' if tables_creees else ''} · "
            f"{_milliers(res.get('rows', 0))} lignes",
        )

        progres.commencer(op.trace, "profil")
        profile = _profiler.profile_dataframe(df)
        sortie = {**res, "clean_log": log, "profile": profile, "tables_liees": tables_creees}

        # Le CSV normalise remonte a l'api pour etre conserve : un classeur Excel
        # n'a pas a etre re-decode a chaque relecture, et tout ce qui suit
        # (rafraichissement, exports) continue de travailler sur du texte.
        if op.return_csv:
            sortie["csv_text"] = df.to_csv(index=False)
        progres.achever(op.trace, "profil", f"{len(df.columns)} colonnes typées")
        progres.terminer(op.trace)
        return _clean_for_json(sortie)
    except Exception as e:
        # Le suivi doit dire ou ca s'est arrete, sinon l'interface montre une
        # etape qui tourne indefiniment alors que le job est deja en erreur.
        progres.echouer(op.trace, str(getattr(e, "detail", None) or e))
        raise


@app.get("/v1/progress/{trace}")
def lire_progres(trace: str):
    """Etat vivant d'un traitement en cours, relaye par l'api au navigateur."""
    return progres.lire(trace)


@app.post("/v1/warehouse/schema")
def warehouse_schema(op: WarehouseRef):
    schema = _warehouse_guard(lambda: warehouse.schema(op.project_id))
    # Les relations ne sont cherchees qu'a partir de deux tables : sur une
    # source unique, c'est du calcul pour rien.
    if len(schema.get("tables", [])) > 1:
        schema["relations"] = _warehouse_guard(lambda: warehouse.relations(op.project_id))
    else:
        schema["relations"] = []
    return _clean_for_json(schema)


@app.post("/v1/warehouse/sql")
def warehouse_sql(op: SqlOp):
    return _clean_for_json(
        _warehouse_guard(lambda: warehouse.run_sql(op.project_id, op.sql, op.limit))
    )


@app.post("/v1/warehouse/drop")
def warehouse_drop(op: WarehouseRef):
    return _warehouse_guard(lambda: warehouse.drop(op.project_id))


def _run_sql_with_repair(
    project_id: str, sql: str, message: str, schema: dict, api_key: str
) -> dict:
    """Execute le SQL de l'agent ; en cas de refus par DuckDB, une seule
    tentative de correction — au-dela on rend la main plutot que de boucler.

    L'execution SQL reste hors du verrou IA : seule la reparation le prend.
    """
    try:
        result = warehouse.run_sql(project_id, sql)
        return {"sql": sql, "result": result, "erreur": None}
    except warehouse.WarehouseError as first:
        fix = _run_with_key(api_key, lambda: _sql.repair(schema, sql, str(first), message))
        repaired = (fix or {}).get("sql")
        if not repaired:
            return {"sql": sql, "result": None, "erreur": str(first)}
        try:
            return {
                "sql": repaired,
                "result": warehouse.run_sql(project_id, repaired),
                "erreur": None,
                "repare": True,
            }
        except warehouse.WarehouseError as second:
            return {"sql": repaired, "result": None, "erreur": str(second)}


@app.post("/v1/warehouse/chat")
def warehouse_chat(op: WarehouseChatOp):
    """Assistant conversationnel adosse a l'entrepot : question -> SQL -> resultat."""
    schema = _warehouse_guard(lambda: warehouse.schema(op.project_id))
    if not schema.get("tables"):
        raise HTTPException(status_code=400, detail="Aucune donnee dans cet entrepot")

    answer = _run_with_key(
        op.api_key,
        lambda: _sql.answer(schema, op.message, op.history, op.dictionary),
    )
    if not isinstance(answer, dict):
        answer = {"reponse": str(answer), "sql": None, "suggestions": []}

    out = {
        "reponse": answer.get("reponse", ""),
        "suggestions": answer.get("suggestions", []),
        "action": answer.get("action") or None,
        "visualisation": None,
    }
    sql = answer.get("sql")
    if sql:
        run = _run_sql_with_repair(op.project_id, sql, op.message, schema, op.api_key)
        out["visualisation"] = {
            "titre": answer.get("titre", ""),
            "viz": answer.get("viz", "table"),
            "format": answer.get("format", "nombre"),
            "sql": run["sql"],
            "erreur": run["erreur"],
            "colonnes": (run["result"] or {}).get("columns"),
            "lignes": (run["result"] or {}).get("rows"),
        }
    return _clean_for_json(out)


@app.post("/v1/warehouse/kpi/propose")
def warehouse_kpi_propose(op: ProposeOp):
    """Premier tableau de bord propose a partir du schema de l'entrepot.

    Chaque indicateur propose est execute avant d'etre renvoye : l'utilisateur
    ne se voit proposer que des indicateurs qui calculent vraiment.
    """
    schema = _warehouse_guard(lambda: warehouse.schema(op.project_id))
    if not schema.get("tables"):
        raise HTTPException(status_code=400, detail="Aucune donnee dans cet entrepot")

    proposal = _run_with_key(
        op.api_key, lambda: _proposer.propose(schema, op.dictionary, op.langue)
    )
    kpis = (proposal or {}).get("kpis", []) if isinstance(proposal, dict) else []

    valid = []
    for kpi in kpis:
        sql = kpi.get("sql")
        if not sql:
            continue
        try:
            preview = warehouse.run_sql(op.project_id, sql, limit=200)
        except warehouse.WarehouseError as e:
            kpi["erreur"] = str(e)
            continue
        valid.append({**kpi, "apercu": preview})
    return _clean_for_json({"kpis": valid, "rejetes": len(kpis) - len(valid)})


def _widget_vise(operation: dict, widgets: list) -> dict:
    cible = str(operation.get("widget_id") or "")
    for w in widgets or []:
        if str(w.get("id")) == cible:
            return w
    return {}


def _forme(operation: dict, widgets: list) -> str:
    """Forme visee par une operation : celle qu'elle impose, sinon l'actuelle."""
    if operation.get("viz"):
        return str(operation["viz"])
    return str(_widget_vise(operation, widgets).get("viz") or "")


def _libelle(operation: dict, widgets: list) -> str:
    """Nom a montrer dans un refus : « Indicateur » ne dit pas lequel."""
    return (
        operation.get("titre")
        or _widget_vise(operation, widgets).get("title")
        or "Indicateur"
    )


@app.post("/v1/warehouse/dashboard/edit")
def warehouse_dashboard_edit(op: DashboardEditOp):
    """Edition du tableau de bord en langage naturel.

    Une operation dont le SQL echoue est ecartee : on prefere expliquer a
    l'utilisateur qu'afficher un widget casse.
    """
    schema = _warehouse_guard(lambda: warehouse.schema(op.project_id))
    if not schema.get("tables"):
        raise HTTPException(status_code=400, detail="Aucune donnee dans cet entrepot")

    plan = _run_with_key(
        op.api_key, lambda: _dashboard.edit(schema, op.widgets, op.message, op.history)
    )
    if not isinstance(plan, dict):
        plan = {"reponse": str(plan), "operations": []}

    applied, rejected = [], []
    for operation in plan.get("operations", []) or []:
        action = operation.get("action")
        if action == "remove":
            if operation.get("widget_id"):
                applied.append(operation)
            continue

        # L'apparence proposee est filtree avant tout : elle finit dans
        # l'attribut d'un element de page, elle ne peut donc pas etre recopiee
        # telle quelle depuis une sortie de modele.
        apparence_ecartee = False
        if "style" in operation:
            style, refus = apparence.valider(operation.get("style"))
            # Un anneau tire sa lisibilite de ses couleurs : les peindre toutes
            # pareil effacerait la repartition qu'il montre.
            if style.get("couleur") and _forme(operation, op.widgets) == "anneau":
                style.pop("couleur")
                refus.append(
                    "la couleur d'un anneau n'est pas modifiable : ce sont ses teintes "
                    "qui distinguent les parts"
                )
            operation["style"] = style
            apparence_ecartee = bool(refus)
            for r in refus:
                rejected.append({"titre": _libelle(operation, op.widgets), "erreur": r})

        sql = operation.get("sql")
        if not sql:
            # Habiller un indicateur ne demande pas de recalculer : « mets-le
            # en orange » n'a aucune raison de reecrire la requete.
            if action == "update" and operation.get("widget_id") and (
                operation.get("style") or operation.get("viz") or operation.get("titre")
            ):
                applied.append(operation)
                continue
            # Demande purement visuelle deja ecartee : elle porte son
            # explication. Y ajouter « requete SQL absente » brouillerait le
            # message avec une raison qui n'est pas la vraie.
            if apparence_ecartee:
                continue
            rejected.append({**operation, "erreur": "requete SQL absente"})
            continue
        try:
            operation["apercu"] = warehouse.run_sql(op.project_id, sql, limit=200)
            applied.append(operation)
        except warehouse.WarehouseError as e:
            rejected.append({**operation, "erreur": str(e)})

    return _clean_for_json({
        "reponse": plan.get("reponse", ""),
        "operations": applied,
        "rejetees": rejected,
    })


class ReportOp(BaseModel):
    project_id: str
    projet: str = ""
    widgets: list = []
    demande: str = ""
    langue: str = "fr"
    api_key: str = ""


@app.post("/v1/warehouse/report")
def warehouse_report(op: ReportOp):
    """Rapport PDF : etat des lieux, points d'attention, recommandations.

    Les indicateurs du tableau de bord sont d'abord EXECUTES ; l'agent ne
    redige qu'a partir de ces resultats reels. Il ne calcule rien, donc il
    ne peut pas inventer de chiffre.
    """
    schema = _warehouse_guard(lambda: warehouse.schema(op.project_id))
    if not schema.get("tables"):
        raise HTTPException(status_code=400, detail="Aucune donnee dans cet entrepot")

    # Sans tableau de bord, on en propose un a la volee : demander un rapport
    # ne doit pas obliger a construire des indicateurs au prealable.
    widgets = op.widgets
    if not widgets:
        proposition = _run_with_key(
            op.api_key, lambda: _proposer.propose(schema, None, op.langue)
        )
        widgets = [
            {"title": k.get("titre"), "sql": k.get("sql"),
             "viz": k.get("viz"), "format": k.get("format")}
            for k in (proposition or {}).get("kpis", [])
            if k.get("sql")
        ]
    if not widgets:
        raise HTTPException(status_code=400, detail="Aucun indicateur exploitable")

    indicateurs = []
    for w in widgets:
        try:
            res = warehouse.run_sql(op.project_id, w["sql"], limit=500)
        except warehouse.WarehouseError:
            continue  # un indicateur casse ne doit pas faire echouer le rapport
        lignes = res["rows"]
        ind = {
            "titre": w.get("title") or w.get("titre") or "",
            "sql": w.get("sql"),
            "viz": w.get("viz") or "table",
            "format": w.get("format") or "nombre",
            "colonnes": res["columns"],
            "lignes": lignes,
            # L'apparence suit l'indicateur jusque dans le rapport : un pic
            # entoure a l'ecran et absent du PDF ferait douter des deux.
            "style": w.get("style") or {},
            "valeur": (
                list(lignes[0].values())[0]
                if len(lignes) == 1 and len(res["columns"]) == 1
                else None
            ),
        }
        indicateurs.append(ind)

    if not indicateurs:
        raise HTTPException(status_code=400, detail="Aucun indicateur n'a pu etre calcule")

    redaction = _run_with_key(
        op.api_key,
        lambda: _reporter.rediger(indicateurs, "", op.langue, op.demande),
    )
    if not isinstance(redaction, dict) or redaction.get("error"):
        raise HTTPException(status_code=502, detail="La redaction du rapport a echoue")

    # Le rendu des graphiques est hors verrou IA : c'est du calcul local.
    for ind in indicateurs:
        try:
            ind["image"] = reporting.rendre_graphique(ind)
        except Exception:
            ind["image"] = None

    lignes_total = sum(t.get("rows", 0) for t in schema.get("tables", []))
    pdf = reporting.construire_pdf(
        redaction, indicateurs, {"projet": op.projet, "lignes": lignes_total}, op.langue
    )

    import base64

    return {
        "titre": redaction.get("titre", "Rapport"),
        "synthese": redaction.get("synthese", ""),
        "indicateurs": len(indicateurs),
        "pdf_base64": base64.b64encode(pdf).decode("ascii"),
    }


@app.post("/v1/warehouse/schema/check")
def warehouse_schema_check(op: SchemaCheckOp):
    """Controle de structure avant un rafraichissement de donnees.

    La comparaison nom a nom est mecanique (sans IA). L'agent n'est sollicite
    que lorsqu'elle ne suffit pas a trancher, et sa proposition reste soumise
    a l'utilisateur.

    On compare ce qui sera REELLEMENT charge : la pipeline de l'import est
    d'abord rejouee. Sans cela, un tableau decoupe en tables liees verrait
    ses colonnes de dimension signalees comme « en trop » a chaque mise a
    jour, alors qu'elles partent simplement dans leur propre table.
    """
    df = _appliquer_pipeline(dataframe_from_payload(op.model_dump()),
                             op.clean_actions, op.decoupage)
    diff = _warehouse_guard(lambda: warehouse.compare_schema(op.project_id, op.table, df))

    if diff["verdict"] in ("identical", "new", "compatible"):
        return _clean_for_json(diff)

    # Ecart non tranche : on demande son avis a l'agent.
    normalized, _ = warehouse.normalize_columns(df)
    samples = {
        c: normalized[c].dropna().astype(str).head(3).tolist() for c in normalized.columns
    }
    con_schema = _warehouse_guard(lambda: warehouse.schema(op.project_id, samples=0))
    target = next(
        (t for t in con_schema.get("tables", []) if t["name"] == op.table), {"columns": []}
    )

    verdict = _run_with_key(
        op.api_key,
        lambda: _schema.match(
            op.table, target["columns"], list(normalized.columns), samples, op.langue
        ),
    )
    if isinstance(verdict, dict) and verdict.get("verdict") in ("compatible", "incompatible"):
        renames = verdict.get("renames") or {}
        extra = verdict.get("ignorees", diff.get("extra", []))
        missing = verdict.get("manquantes", diff.get("missing", []))
        # Les constats mecaniques sont remplaces, pas completes : une colonne
        # que l'agent a rattachee ne doit plus etre signalee comme manquante.
        issues = [f"colonne « {src} » renommee en « {dst} »" for src, dst in renames.items()]
        if missing:
            issues.append("colonnes absentes du fichier : " + ", ".join(missing))
        if extra:
            issues.append("colonnes en trop, ignorees : " + ", ".join(extra))
        diff = {
            **diff,
            "verdict": verdict["verdict"],
            "renames": renames,
            "explication": verdict.get("explication", ""),
            "extra": extra,
            "missing": missing,
            "issues": issues,
            "analyse_ia": True,
        }
    return _clean_for_json(diff)


@app.post("/v1/kpi/compute")
def kpi_compute(op: KpiComputeOp):
    df = dataframe_from_payload(op.model_dump())
    df = apply_filters(df, op.filters)
    res = _kpi.compute_kpi(df, op.spec)
    out = {
        "valeur": res.get("valeur"),
        "erreur": res.get("erreur"),
        "serie": None,
        "groupes": None,
    }
    if res.get("serie") is not None:
        out["serie"] = _clean_for_json(res["serie"].to_dict(orient="records"))
    if res.get("groupes") is not None:
        out["groupes"] = _clean_for_json(res["groupes"].to_dict(orient="records"))
    return _clean_for_json(out)
