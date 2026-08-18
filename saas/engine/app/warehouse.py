"""Entrepot analytique : un fichier DuckDB par projet.

Remplace le transport du CSV a chaque calcul. Le CSV n'est ingere qu'une fois
(pipeline ETL) ; ensuite tout se calcule en SQL directement dans l'entrepot.

Le service reste sans etat *metier* : Postgres (cote Rust) garde la
metadonnee qui fait foi (projets, sources, historique d'ingestion) ; ici on
ne stocke que les donnees analytiques, adressees par identifiant de projet.
"""

import os
import re
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd

WAREHOUSE_DIR = Path(os.environ.get("WAREHOUSE_DIR", "/warehouse"))

# Un identifiant de projet vient de l'API mais sert a construire un chemin :
# on n'accepte que la forme UUID, jamais une chaine libre.
_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
_IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

# Instructions autorisees dans l'entrepot : lecture seule.
_READ_ONLY_START = ("select", "with")


class WarehouseError(Exception):
    """Erreur fonctionnelle renvoyee telle quelle a l'utilisateur."""


def db_path(project_id: str) -> Path:
    if not _UUID_RE.match(str(project_id or "")):
        raise WarehouseError("identifiant de projet invalide")
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    return WAREHOUSE_DIR / f"{project_id}.duckdb"


def connect(project_id: str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = db_path(project_id)
    if read_only and not path.exists():
        raise WarehouseError("aucune donnee dans cet entrepot")
    return duckdb.connect(str(path), read_only=read_only)


# ──────────────────────────────────────────────
# Normalisation des identifiants SQL
# ──────────────────────────────────────────────
# Translitteration arabe -> latin. Sans elle, « المبيعات » ne laisse aucun
# caractere ASCII et la colonne deviendrait « col_3 » : ni l'utilisateur ni
# l'agent SQL ne pourraient la reconnaitre.
_TRANSLIT_AR = {
    "ا": "a", "أ": "a", "إ": "i", "آ": "a", "ب": "b", "ت": "t", "ث": "th",
    "ج": "j", "ح": "h", "خ": "kh", "د": "d", "ذ": "dh", "ر": "r", "ز": "z",
    "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "a",
    "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n",
    "ه": "h", "و": "w", "ي": "y", "ى": "a", "ة": "a", "ء": "", "ئ": "y",
    "ؤ": "w", "ـ": "",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
}


def transliterate(text: str) -> str:
    """Rend en caracteres latins ce qui n'en a pas, quand on sait le faire."""
    return "".join(_TRANSLIT_AR.get(c, c) for c in text)


def sql_identifier(label: str, fallback: str = "col") -> str:
    """« Chiffre d'affaires (€) » -> « chiffre_d_affaires ».
    « المبيعات » -> « almbyaat ».

    Les noms de colonnes issus d'un CSV sont rarement ecrivables en SQL.
    On produit un identifiant sur ; le libelle d'origine est toujours
    conserve a cote (voir `normalize_columns`) et c'est lui qui est montre
    a l'utilisateur comme a l'agent.
    """
    txt = unicodedata.normalize("NFKD", str(label))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.lower().strip()

    ascii_only = re.sub(r"[^a-z0-9]+", "_", txt).strip("_")
    if not ascii_only:
        # Rien d'exploitable en latin : on tente la translitteration avant
        # d'abandonner sur un identifiant anonyme.
        ascii_only = re.sub(r"[^a-z0-9]+", "_", transliterate(txt)).strip("_")

    if not ascii_only or ascii_only[0].isdigit():
        ascii_only = f"{fallback}_{ascii_only}" if ascii_only else fallback
    return ascii_only[:60]


def normalize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Renomme les colonnes en identifiants SQL, en garantissant l'unicite.

    Renvoie (dataframe renomme, {identifiant_sql: libelle d'origine}).
    """
    mapping: dict[str, str] = {}
    used: set[str] = set()
    renames: dict[str, str] = {}
    for i, col in enumerate(df.columns):
        ident = sql_identifier(col, f"col_{i + 1}")
        base, n = ident, 2
        while ident in used:
            ident = f"{base}_{n}"
            n += 1
        used.add(ident)
        renames[col] = ident
        mapping[ident] = str(col)
    return df.rename(columns=renames), mapping


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Typage a l'ingestion : une colonne texte qui contient des dates ou des
    nombres est convertie, sinon les agregations SQL seraient impossibles."""
    out = df.copy()
    for col in out.columns:
        if not pd.api.types.is_object_dtype(out[col]):
            continue
        serie = out[col].dropna()
        if serie.empty:
            continue

        num = pd.to_numeric(out[col], errors="coerce")
        if num.notna().sum() >= 0.95 * len(serie):
            out[col] = num
            continue

        # format="mixed" evite l'avertissement d'inference ligne a ligne ;
        # errors="coerce" laisse passer les colonnes qui ne sont pas des dates.
        try:
            dates = pd.to_datetime(out[col], errors="coerce", format="mixed")
        except Exception:
            continue
        if dates.notna().sum() >= 0.95 * len(serie):
            out[col] = dates
    return out


# ──────────────────────────────────────────────
# Ingestion
# ──────────────────────────────────────────────
# Table de metadonnees interne : elle rend l'entrepot auto-descriptif.
# Sans elle, une colonne « المبيعات » devenue `almbyaat` perdrait son sens
# pour l'agent comme pour l'utilisateur.
_META_TABLE = "_datavox_columns"


def _save_column_map(con: duckdb.DuckDBPyConnection, table: str, column_map: dict) -> None:
    con.execute(
        f'CREATE TABLE IF NOT EXISTS "{_META_TABLE}" '
        "(table_name VARCHAR, column_name VARCHAR, label VARCHAR)"
    )
    con.execute(f'DELETE FROM "{_META_TABLE}" WHERE table_name = ?', [table])
    for ident, label in column_map.items():
        con.execute(
            f'INSERT INTO "{_META_TABLE}" VALUES (?, ?, ?)', [table, ident, label]
        )


def _load_labels(con: duckdb.DuckDBPyConnection, table: str) -> dict:
    if _META_TABLE not in _table_names(con):
        return {}
    rows = con.execute(
        f'SELECT column_name, label FROM "{_META_TABLE}" WHERE table_name = ?', [table]
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def ingest(project_id: str, table: str, df: pd.DataFrame, mode: str = "replace") -> dict:
    """Charge un DataFrame dans l'entrepot du projet.

    mode = "replace" (remplace la table) ou "append" (ajoute les lignes).
    """
    if not _IDENT_RE.match(table or ""):
        raise WarehouseError(f"nom de table invalide : {table}")

    df, column_map = normalize_columns(df)
    df = _coerce_types(df)

    con = connect(project_id)
    try:
        con.register("_incoming", df)
        if mode == "append" and table in _table_names(con):
            # On aligne les colonnes sur la table cible : une source rafraichie
            # peut arriver avec les colonnes dans un ordre different.
            existing = [c[0] for c in con.execute(f'DESCRIBE "{table}"').fetchall()]
            cols = ", ".join(f'"{c}"' for c in existing)
            missing = [c for c in existing if c not in df.columns]
            if missing:
                raise WarehouseError(
                    "colonnes absentes du fichier : " + ", ".join(missing)
                )
            con.execute(f'INSERT INTO "{table}" ({cols}) SELECT {cols} FROM _incoming')
        else:
            con.execute(f'CREATE OR REPLACE TABLE "{table}" AS SELECT * FROM _incoming')
        con.unregister("_incoming")
        # En mode ajout, les libelles connus font foi : le fichier entrant a
        # pu etre aligne (renommages), ses libelles ne sont plus les bons.
        if mode == "append":
            column_map = {**column_map, **_load_labels(con, table)}
        _save_column_map(con, table, column_map)
        rows = con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
        schema = _describe(con, table)
    finally:
        con.close()

    return {
        "table": table,
        "rows": int(rows),
        "columns": schema,
        "column_map": column_map,
    }


# ──────────────────────────────────────────────
# Lecture du schema
# ──────────────────────────────────────────────
def _table_names(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [r[0] for r in con.execute("SHOW TABLES").fetchall()]


def _describe(con: duckdb.DuckDBPyConnection, table: str) -> list[dict]:
    rows = con.execute(f'DESCRIBE "{table}"').fetchall()
    return [{"name": r[0], "type": r[1]} for r in rows]


def schema(project_id: str, samples: int = 3) -> dict:
    """Schema complet de l'entrepot : tables, colonnes, types, exemples.

    C'est le contexte donne a l'agent SQL — d'ou les valeurs d'exemple,
    qui evitent qu'il invente des modalites (« Livré » vs « livre »).
    """
    path = db_path(project_id)
    if not path.exists():
        return {"tables": []}

    con = connect(project_id, read_only=True)
    try:
        tables = []
        for name in _table_names(con):
            if name == _META_TABLE:
                continue
            cols = _describe(con, name)
            labels = _load_labels(con, name)
            for col in cols:
                label = labels.get(col["name"])
                # Le libelle n'est repris que s'il apporte quelque chose :
                # « pays » -> « pays » n'a pas besoin d'etre repete.
                if label and label != col["name"]:
                    col["label"] = label
            rows = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            if samples > 0:
                for col in cols:
                    try:
                        vals = con.execute(
                            f'SELECT DISTINCT "{col["name"]}" FROM "{name}" '
                            f'WHERE "{col["name"]}" IS NOT NULL LIMIT {int(samples)}'
                        ).fetchall()
                        col["samples"] = [str(v[0]) for v in vals]
                    except duckdb.Error:
                        col["samples"] = []
            tables.append({"name": name, "rows": int(rows), "columns": cols})
        return {"tables": tables}
    finally:
        con.close()


# ──────────────────────────────────────────────
# Relations entre tables
# ──────────────────────────────────────────────
_ENTIER = ("BIGINT", "INTEGER", "HUGEINT", "SMALLINT", "TINYINT", "UBIGINT", "UINTEGER")


def _familles_compatibles(t1: str, t2: str) -> bool:
    """Deux colonnes ne peuvent se referencer que si leurs types s'accordent."""
    if t1 == t2:
        return True
    return t1 in _ENTIER and t2 in _ENTIER


def _noms_apparies(col_a: str, table_b: str, col_b: str) -> bool:
    """Heuristique de nommage, appliquee AVANT toute requete couteuse.

    Comparer les valeurs de toutes les paires de colonnes de toutes les paires
    de tables exploserait en nombre de requetes. On ne teste donc que les
    paires dont les noms rendent la relation plausible :
      client_id -> clients.id, id_client -> client.id, pays -> pays.pays
    """
    a, b = col_a.lower(), col_b.lower()
    base_b = table_b.lower().rstrip("s")
    if a == b:
        return True
    if a in (f"{base_b}_{b}", f"{b}_{base_b}", f"id_{base_b}", f"{base_b}_id"):
        return True
    # « client_id » face a « id » dans la table « clients »
    return a.startswith(base_b) and a.endswith(b) and len(a) > len(b)


def relations(project_id: str, seuil: float = 0.8) -> list:
    """Deduit les liens entre tables : correspondance de noms PUIS verification
    sur les valeurs reelles. Une relation annoncee est une relation constatee.
    """
    path = db_path(project_id)
    if not path.exists():
        return []

    con = connect(project_id, read_only=True)
    try:
        noms = [t for t in _table_names(con) if t != _META_TABLE]
        if len(noms) < 2:
            return []

        colonnes = {t: _describe(con, t) for t in noms}
        trouvees, vues = [], set()

        for source in noms:
            for cible in noms:
                if source == cible:
                    continue
                for ca in colonnes[source]:
                    for cb in colonnes[cible]:
                        if not _familles_compatibles(ca["type"], cb["type"]):
                            continue
                        if not _noms_apparies(ca["name"], cible, cb["name"]):
                            continue

                        cle = (source, ca["name"], cible, cb["name"])
                        if cle in vues:
                            continue
                        vues.add(cle)

                        try:
                            # La cible doit se comporter comme une cle, et les
                            # valeurs de la source doivent s'y retrouver.
                            uniq, total = con.execute(
                                f'SELECT count(DISTINCT "{cb["name"]}"), count(*) FROM "{cible}"'
                            ).fetchone()
                            if not total or uniq / total < 0.95:
                                continue

                            couverts, distincts = con.execute(
                                f'SELECT count(*) FILTER (WHERE v IN (SELECT "{cb["name"]}" FROM "{cible}")), '
                                f'count(*) FROM (SELECT DISTINCT "{ca["name"]}" AS v FROM "{source}" '
                                f'WHERE "{ca["name"]}" IS NOT NULL)'
                            ).fetchone()
                        except duckdb.Error:
                            continue

                        if not distincts or distincts < 2:
                            continue
                        couverture = couverts / distincts
                        if couverture >= seuil:
                            trouvees.append({
                                "source": source,
                                "colonne_source": ca["name"],
                                "cible": cible,
                                "colonne_cible": cb["name"],
                                "couverture": round(couverture, 2),
                            })
        return trouvees
    finally:
        con.close()


# ──────────────────────────────────────────────
# Execution SQL
# ──────────────────────────────────────────────
def _guard(sql: str) -> str:
    """Verifie qu'on execute bien une seule requete de lecture.

    La connexion est de toute facon ouverte en lecture seule (defense en
    profondeur) ; ce controle sert a rendre l'erreur comprehensible.
    """
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        raise WarehouseError("requete SQL vide")
    if ";" in text:
        raise WarehouseError("une seule requete a la fois")
    if not text.lower().lstrip("(").startswith(_READ_ONLY_START):
        raise WarehouseError("seules les requetes SELECT sont autorisees")
    return text


def run_sql(project_id: str, sql: str, limit: int = 5000) -> dict:
    """Execute une requete de lecture et renvoie les lignes en JSON."""
    text = _guard(sql)
    con = connect(project_id, read_only=True)
    try:
        df = con.execute(f"SELECT * FROM ({text}) AS _q LIMIT {int(limit)}").fetchdf()
    except duckdb.Error as e:
        raise WarehouseError(str(e).split("\n")[0]) from e
    finally:
        con.close()

    # Les dates doivent partir en texte : JSON ne connait pas Timestamp.
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    return {
        "columns": [str(c) for c in df.columns],
        "rows": df.to_dict(orient="records"),
        "row_count": len(df),
        "truncated": len(df) >= limit,
    }


def drop(project_id: str) -> dict:
    """Supprime l'entrepot d'un projet (appele a la suppression du projet)."""
    path = db_path(project_id)
    existed = path.exists()
    if existed:
        path.unlink()
    for suffix in (".wal", ".tmp"):
        side = Path(str(path) + suffix)
        if side.exists():
            side.unlink()
    return {"dropped": existed}


# ──────────────────────────────────────────────
# Comparaison de structure (rafraichissement d'une source)
# ──────────────────────────────────────────────
def compare_schema(project_id: str, table: str, df: pd.DataFrame) -> dict:
    """Compare la structure d'un fichier entrant a la table existante.

    Renvoie un verdict :
      - identical    : memes colonnes, memes types -> ingestion directe
      - compatible   : ecarts rattrapables (ordre, colonnes en trop,
                       colonne manquante nullable, renommage probable)
      - incompatible : recouvrement insuffisant -> on previent l'utilisateur
    """
    path = db_path(project_id)
    if not path.exists():
        return {"verdict": "new", "table": table, "issues": [], "renames": {}}

    con = connect(project_id, read_only=True)
    try:
        if table not in _table_names(con):
            return {"verdict": "new", "table": table, "issues": [], "renames": {}}
        target = _describe(con, table)
    finally:
        con.close()

    incoming_df, _ = normalize_columns(df)
    incoming = list(incoming_df.columns)
    expected = [c["name"] for c in target]

    missing = [c for c in expected if c not in incoming]
    extra = [c for c in incoming if c not in expected]

    # Renommage probable : une colonne manquante et une colonne en trop dont
    # les valeurs sont du meme genre. On propose, l'utilisateur tranche.
    renames: dict[str, str] = {}
    if missing and extra:
        for miss in list(missing):
            candidates = [
                e for e in extra
                if e.startswith(miss[:4]) or miss.startswith(e[:4]) or e in miss or miss in e
            ]
            if len(candidates) == 1:
                renames[candidates[0]] = miss
                missing.remove(miss)
                extra.remove(candidates[0])

    common = [c for c in expected if c in incoming or c in renames.values()]
    coverage = len(common) / len(expected) if expected else 0

    issues = []
    if renames:
        issues += [f"colonne « {src} » renommee en « {dst} »" for src, dst in renames.items()]
    if missing:
        issues.append("colonnes absentes du fichier : " + ", ".join(missing))
    if extra:
        issues.append("colonnes en trop, ignorees : " + ", ".join(extra))

    if not missing and not extra and not renames and incoming == expected:
        verdict = "identical"
    elif coverage >= 0.6 and not missing:
        verdict = "compatible"
    elif coverage >= 0.6:
        verdict = "partial"
    else:
        verdict = "incompatible"

    return {
        "verdict": verdict,
        "table": table,
        "expected": expected,
        "incoming": incoming,
        "missing": missing,
        "extra": extra,
        "renames": renames,
        "coverage": round(coverage, 2),
        "issues": issues,
    }


def align_to_table(project_id: str, table: str, df: pd.DataFrame, renames: dict) -> pd.DataFrame:
    """Applique les corrections validees puis aligne sur la table cible."""
    out, _ = normalize_columns(df)
    if renames:
        out = out.rename(columns={k: v for k, v in renames.items() if k in out.columns})

    con = connect(project_id, read_only=True)
    try:
        expected = [c["name"] for c in _describe(con, table)]
    finally:
        con.close()

    for col in expected:
        if col not in out.columns:
            out[col] = None
    return _coerce_types(out[expected])
