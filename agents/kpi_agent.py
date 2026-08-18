import pandas as pd

from agents.base_agent import BaseAgent
from config import AGENT_TEMPERATURES

KPI_SYSTEM_PROMPT = """Tu es un agent spécialisé en Business Intelligence et en définition de KPIs.
Tu reçois le profil d'un dataset et tu proposes des KPIs pertinents ET CALCULABLES sur ce dataset.

Chaque KPI doit avoir une spécification de calcul structurée que la plateforme
exécutera avec pandas. Retourne UNIQUEMENT ce JSON :
```json
{
  "kpis": [
    {
      "id": "kpi_1",
      "nom": "Nom court du KPI",
      "description": "Ce que mesure ce KPI",
      "interet": "Pourquoi ce KPI est utile pour ce dataset",
      "formule": "Description lisible de la formule (ex: Somme de montant / Nombre de commandes)",
      "format": "nombre|pourcentage|monetaire",
      "graphique": "tile|line|area|bar|bar_h|donut",
      "spec": {
        "operation": "sum|mean|median|min|max|count|nunique|ratio|part",
        "colonne": "nom_colonne ou null si count",
        "valeur_cible": "valeur exacte de la colonne (uniquement si operation=part)",
        "operation_denominateur": "sum|mean|count|nunique (uniquement si operation=ratio)",
        "colonne_denominateur": "nom_colonne (uniquement si operation=ratio)",
        "group_by": "colonne catégorielle pour une répartition, ou null",
        "date_col": "colonne date pour une évolution temporelle, ou null",
        "granularite": "jour|semaine|mois|annee"
      }
    }
  ]
}
```

Règles STRICTES sur les opérations :
- Utilise UNIQUEMENT des colonnes réellement présentes dans le profil fourni.
- operation sum/mean/median/min/max exigent une colonne NUMÉRIQUE. Ne les
  applique JAMAIS à une colonne catégorielle ou texte.
- "part" sert aux TAUX sur une colonne catégorielle : part des lignes dont
  colonne == valeur_cible (ex: taux de commandes livrées -> operation="part",
  colonne="status", valeur_cible="Livré", format="pourcentage"). valeur_cible
  doit être une valeur réellement présente (voir les "top" du profil).
- "ratio" sert aux rapports entre deux MESURES numériques (ex: panier moyen =
  somme du CA / nombre de commandes). N'utilise jamais ratio sur du texte.

Règles STRICTES sur le graphique :
- "tile"  : un chiffre seul (ni group_by ni date_col). C'est le cas par défaut.
- "line"  : évolution, uniquement si date_col est renseignée.
- "area"  : évolution aussi, quand le volume cumulé compte plus que le détail.
- "bar"   : répartition, uniquement si group_by est renseigné.
- "bar_h" : même chose, à préférer si les libellés de catégorie sont longs
            ou s'il y a plus de 8 catégories.
- "donut" : part-à-tout UNIQUEMENT (operation sum ou count), 6 catégories max.
            Jamais pour une moyenne, une médiane ou un ratio : ces valeurs ne
            s'additionnent pas en un tout.

Règles STRICTES sur la sélection :
- Propose 6 à 8 KPIs VARIÉS : au moins un volume, une moyenne, un taux, une
  répartition et une évolution — l'utilisateur choisira ensuite lesquels garder.
- Varie aussi les formes : ne propose pas 6 "tile" d'affilée.
- Réponds en français, UNIQUEMENT en JSON valide."""

VALID_OPS = {
    "sum", "mean", "median", "min", "max", "count", "nunique", "ratio", "part",
}
# Operations qui exigent une colonne numerique exploitable
NUMERIC_OPS = {"sum", "mean", "median", "min", "max"}
FREQ_MAP = {"jour": "D", "semaine": "W", "mois": "MS", "annee": "YS"}


class KPIAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="KPI",
            system_prompt=KPI_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES["kpi"],
        )

    def suggest_kpis(self, profile: dict, dictionary: dict = None) -> dict:
        """Ask Claude for computable KPI suggestions."""
        context = self._format_profile(profile)
        if dictionary and "dictionnaire" in dictionary:
            desc = [
                f"- {e.get('colonne')}: {e.get('description')}"
                for e in dictionary["dictionnaire"]
            ]
            context += "\n\n=== DESCRIPTIONS MÉTIER ===\n" + "\n".join(desc)
        return self.ask_json(
            "Propose des KPIs pertinents et calculables pour ce dataset, en JSON.",
            context=context,
        )

    # ──────────────────────────────────────────
    # Calculs deterministes (pandas, sans IA)
    # ──────────────────────────────────────────

    def compute_kpi(self, df: pd.DataFrame, spec: dict) -> dict:
        """Execute a KPI spec deterministically with pandas.

        Returns {"valeur", "serie", "groupes", "erreur"}.
        """
        result = {"valeur": None, "serie": None, "groupes": None, "erreur": None}
        try:
            self._validate_spec(df, spec)
            result["valeur"] = self._scalar(df, spec)

            date_col = spec.get("date_col")
            if date_col and date_col in df.columns:
                temp = df.copy()
                temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
                temp = temp.dropna(subset=[date_col])
                if len(temp) > 0:
                    freq = FREQ_MAP.get(spec.get("granularite", "mois"), "MS")
                    serie = (
                        temp.groupby(pd.Grouper(key=date_col, freq=freq))
                        .apply(lambda g: self._scalar(g, spec))
                        .dropna()
                    )
                    if len(serie) > 0:
                        result["serie"] = serie.reset_index().rename(
                            columns={0: "valeur", serie.name or 0: "valeur"}
                        )
                        result["serie"].columns = [date_col, "valeur"]

            group_by = spec.get("group_by")
            if group_by and group_by in df.columns:
                groupes = (
                    df.groupby(group_by, dropna=True)
                    .apply(lambda g: self._scalar(g, spec))
                    .dropna()
                    .sort_values(ascending=False)
                    .head(12)
                )
                if len(groupes) > 0:
                    result["groupes"] = groupes.reset_index()
                    result["groupes"].columns = [group_by, "valeur"]

        except Exception as e:
            result["erreur"] = str(e)
        return result

    def _validate_spec(self, df: pd.DataFrame, spec: dict):
        op = spec.get("operation", "count")
        if op not in VALID_OPS:
            raise ValueError(f"Opération inconnue : {op}")
        col = spec.get("colonne")
        # count : pas de colonne requise ; ratio : numerateur count si colonne absente
        if op not in ("count", "ratio") and (not col or col not in df.columns):
            raise ValueError(f"Colonne introuvable : {col}")
        if op == "ratio":
            if col and col not in df.columns:
                raise ValueError(f"Colonne introuvable : {col}")
            den = spec.get("colonne_denominateur")
            den_op = spec.get("operation_denominateur", "count")
            if den_op != "count" and (not den or den not in df.columns):
                raise ValueError(f"Colonne dénominateur introuvable : {den}")
        if op == "part":
            if spec.get("valeur_cible") is None:
                raise ValueError(
                    "Opération 'part' : 'valeur_cible' manquante "
                    f"(quelle valeur de '{col}' faut-il compter ?)"
                )

        # Une operation numerique sur une colonne qui ne l'est pas donnait un
        # faux zero silencieux (to_numeric -> NaN, .sum() -> 0.0). On refuse
        # explicitement : mieux vaut un message qu'un chiffre inventé.
        # Le ratio compte aussi : son numerateur est une somme par defaut.
        checked = []
        if op in NUMERIC_OPS:
            checked.append((col, op))
        elif op == "ratio":
            num_op = spec.get("operation_numerateur") or ("sum" if col else "count")
            if num_op in NUMERIC_OPS:
                checked.append((col, num_op))
            den_op = spec.get("operation_denominateur", "count")
            if den_op in NUMERIC_OPS:
                checked.append((spec.get("colonne_denominateur"), den_op))

        for name, name_op in checked:
            if name and name in df.columns:
                if pd.to_numeric(df[name], errors="coerce").notna().sum() == 0:
                    raise ValueError(
                        f"'{name}' n'est pas une colonne numérique : l'opération "
                        f"'{name_op}' ne s'y applique pas. Pour un taux sur une "
                        "colonne catégorielle, utilisez l'opération 'part'."
                    )

    def _scalar(self, frame: pd.DataFrame, spec: dict):
        """Compute the KPI value on a dataframe (or sub-group)."""
        if len(frame) == 0:
            return None
        op = spec.get("operation", "count")
        if op == "part":
            # Part des lignes dont colonne == valeur_cible (taux sur categoriel).
            col = spec.get("colonne")
            target = spec.get("valeur_cible")
            if not col or col not in frame.columns:
                raise ValueError(f"Colonne introuvable : {col}")
            if target is None:
                raise ValueError("Opération 'part' : 'valeur_cible' manquante")
            matches = (frame[col].astype(str) == str(target)).sum()
            return float(matches) / float(len(frame))
        if op == "ratio":
            num = self._simple(frame, spec.get("operation_numerateur")
                               or ("sum" if spec.get("colonne") else "count"),
                               spec.get("colonne"))
            den = self._simple(frame, spec.get("operation_denominateur", "count"),
                               spec.get("colonne_denominateur"))
            if den in (None, 0) or pd.isna(den):
                return None
            return num / den if num is not None else None
        return self._simple(frame, op, spec.get("colonne"))

    @staticmethod
    def _simple(frame: pd.DataFrame, op: str, col):
        if op == "count":
            return float(len(frame))
        if not col or col not in frame.columns:
            raise ValueError(f"Colonne introuvable : {col}")
        s = frame[col]
        if op == "nunique":
            return float(s.nunique())
        s = pd.to_numeric(s, errors="coerce")
        # Aucune valeur exploitable : renvoyer None (le groupe sera ecarte)
        # plutot que le 0.0 que .sum() produit sur une serie entierement NaN.
        if s.notna().sum() == 0:
            return None
        value = getattr(s, op)()
        return None if pd.isna(value) else float(value)

    @staticmethod
    def format_value(value, fmt: str = "nombre") -> str:
        """Human-readable French formatting of a KPI value."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "—"
        if fmt == "pourcentage":
            pct = value * 100 if abs(value) <= 1.5 else value
            return f"{pct:.1f} %".replace(".", ",")
        if abs(value) >= 1000:
            s = f"{value:,.0f}".replace(",", " ")
        elif abs(value) >= 10:
            s = f"{value:,.1f}".rstrip("0").rstrip(".")
        else:
            s = f"{value:,.2f}".rstrip("0").rstrip(".")
        if fmt == "monetaire":
            s += " €"
        return s

    def _format_profile(self, profile: dict) -> str:
        lines = [
            f"Dataset: {profile['shape']['rows']} lignes x {profile['shape']['columns']} colonnes",
            "",
            "=== COLONNES ===",
        ]
        for col, info in profile["columns"].items():
            line = f"- {col}: type={info.get('type', info['dtype'])}, uniques={info['nunique']}"
            if "mean" in info:
                line += f", moy={info['mean']}, min={info['min']}, max={info['max']}"
            if "top_values" in info:
                line += f", top={list(info['top_values'].items())[:3]}"
            lines.append(line)
        if profile["date_columns"]:
            lines.append(f"\nColonnes temporelles: {profile['date_columns']}")
        if profile["numeric_columns"]:
            lines.append(f"Colonnes numériques: {profile['numeric_columns']}")
        if profile["categorical_columns"]:
            lines.append(f"Colonnes catégorielles: {profile['categorical_columns']}")
        return "\n".join(lines)
