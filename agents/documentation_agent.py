import pandas as pd

from agents.base_agent import BaseAgent
from config import AGENT_TEMPERATURES

DOCUMENTATION_SYSTEM_PROMPT = """Tu es un agent spécialisé en documentation de données et modélisation d'entrepôt (data warehouse).
Tu reçois le profil d'un dataset et un échantillon de lignes, et tu produis une documentation métier claire.

Quand on te demande un DICTIONNAIRE DE DONNÉES, retourne UNIQUEMENT ce JSON :
```json
{
  "resume_dataset": "Description en 2-3 phrases de ce que contient ce dataset et de son usage métier probable",
  "dictionnaire": [
    {
      "colonne": "nom_exact_de_la_colonne",
      "description": "Description métier claire et contextuelle de la colonne",
      "type_semantique": "identifiant|mesure|dimension|date|geo|texte|booleen",
      "role_entrepot": "cle_primaire|cle_etrangere|mesure|attribut_dimension|date|autre",
      "exemple": "une valeur d'exemple",
      "remarques_qualite": "problèmes de qualité observés ou 'RAS'"
    }
  ]
}
```

Quand on te demande un MODÈLE D'ENTREPÔT, retourne UNIQUEMENT ce JSON :
```json
{
  "type_schema": "etoile|flocon|table_unique",
  "justification": "Pourquoi ce type de schéma est adapté",
  "table_de_faits": {
    "nom": "fact_...",
    "description": "...",
    "mesures": ["col1", "col2"],
    "cles_etrangeres": ["col_ref_dim1"]
  },
  "dimensions": [
    {
      "nom": "dim_...",
      "description": "...",
      "cle": "colonne clé",
      "colonnes": ["col1", "col2"]
    }
  ],
  "relations": ["fact_x.col -> dim_y.cle : description de la relation"],
  "recommandations": ["Recommandation concrète de modélisation"]
}
```

Règles :
- Utilise UNIQUEMENT les noms de colonnes réellement présents dans le dataset.
- Réponds en français.
- Réponds UNIQUEMENT en JSON valide, sans texte avant ou après."""


class DocumentationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Documentation",
            system_prompt=DOCUMENTATION_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES["documentation"],
        )

    def generate_dictionary(self, df: pd.DataFrame, profile: dict) -> dict:
        """Generate a business data dictionary for the dataset."""
        context = self._build_context(df, profile)
        return self.ask_json(
            "Génère le DICTIONNAIRE DE DONNÉES complet de ce dataset. "
            "Une entrée par colonne, descriptions métier contextuelles.",
            context=context,
        )

    def propose_warehouse_model(
        self, df: pd.DataFrame, profile: dict, dictionary: dict = None
    ) -> dict:
        """Propose a warehouse model (fact/dimension split) for the dataset."""
        context = self._build_context(df, profile)
        if dictionary and "dictionnaire" in dictionary:
            roles = [
                f"- {e.get('colonne')}: {e.get('type_semantique')} / {e.get('role_entrepot')}"
                for e in dictionary["dictionnaire"]
            ]
            context += "\n\n=== DICTIONNAIRE DÉJÀ ÉTABLI ===\n" + "\n".join(roles)
        return self.ask_json(
            "Propose le MODÈLE D'ENTREPÔT pour ce dataset : table de faits, "
            "dimensions, clés de liaison et recommandations.",
            context=context,
        )

    # ──────────────────────────────────────────
    # Exports (deterministes, sans IA)
    # ──────────────────────────────────────────

    def export_markdown(
        self, dictionary: dict, model: dict = None, dataset_name: str = "dataset"
    ) -> str:
        """Build a downloadable Markdown documentation file."""
        lines = [f"# Documentation des données — {dataset_name}", ""]

        if dictionary:
            if dictionary.get("resume_dataset"):
                lines += ["## Résumé", "", dictionary["resume_dataset"], ""]
            entries = dictionary.get("dictionnaire", [])
            if entries:
                lines += [
                    "## Dictionnaire de données",
                    "",
                    "| Colonne | Description | Type | Rôle entrepôt | Exemple | Qualité |",
                    "|---|---|---|---|---|---|",
                ]
                for e in entries:
                    lines.append(
                        "| `{}` | {} | {} | {} | {} | {} |".format(
                            e.get("colonne", ""),
                            e.get("description", ""),
                            e.get("type_semantique", ""),
                            e.get("role_entrepot", ""),
                            e.get("exemple", ""),
                            e.get("remarques_qualite", ""),
                        )
                    )
                lines.append("")

        if model:
            lines += ["## Modèle d'entrepôt", ""]
            lines.append(
                f"**Type de schéma** : {model.get('type_schema', 'N/A')} — "
                f"{model.get('justification', '')}"
            )
            lines.append("")
            fact = model.get("table_de_faits") or {}
            if fact:
                lines += [
                    f"### Table de faits : `{fact.get('nom', 'fact')}`",
                    "",
                    fact.get("description", ""),
                    "",
                    f"- **Mesures** : {', '.join(fact.get('mesures', []))}",
                    f"- **Clés étrangères** : {', '.join(fact.get('cles_etrangeres', []))}",
                    "",
                ]
            for dim in model.get("dimensions", []):
                lines += [
                    f"### Dimension : `{dim.get('nom', 'dim')}`",
                    "",
                    dim.get("description", ""),
                    "",
                    f"- **Clé** : `{dim.get('cle', '')}`",
                    f"- **Colonnes** : {', '.join(dim.get('colonnes', []))}",
                    "",
                ]
            relations = model.get("relations", [])
            if relations:
                lines += ["### Relations", ""]
                lines += [f"- {r}" for r in relations]
                lines.append("")
            recos = model.get("recommandations", [])
            if recos:
                lines += ["### Recommandations", ""]
                lines += [f"- {r}" for r in recos]
                lines.append("")

        return "\n".join(lines)

    def export_dbt_yaml(
        self, dictionary: dict, dataset_name: str = "dataset"
    ) -> str:
        """Build a dbt-compatible schema.yml from the data dictionary.

        Directement utilisable dans un projet dbt (models/schema.yml).
        """
        safe_name = (
            dataset_name.rsplit(".", 1)[0]
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )
        lines = [
            "version: 2",
            "",
            "models:",
            f"  - name: {safe_name}",
        ]
        resume = (dictionary or {}).get("resume_dataset", "")
        if resume:
            lines.append(f'    description: "{self._yaml_escape(resume)}"')
        lines.append("    columns:")
        for e in (dictionary or {}).get("dictionnaire", []):
            col = e.get("colonne", "")
            desc = self._yaml_escape(e.get("description", ""))
            lines.append(f"      - name: {col}")
            if desc:
                lines.append(f'        description: "{desc}"')
            tests = []
            if e.get("role_entrepot") == "cle_primaire":
                tests = ["unique", "not_null"]
            elif str(e.get("remarques_qualite", "")).strip().upper() == "RAS":
                tests = ["not_null"]
            if tests:
                lines.append("        tests:")
                lines += [f"          - {t}" for t in tests]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _yaml_escape(text: str) -> str:
        return str(text).replace('"', "'").replace("\n", " ")

    def _build_context(self, df: pd.DataFrame, profile: dict) -> str:
        lines = [
            f"Dataset: {profile['shape']['rows']} lignes x {profile['shape']['columns']} colonnes",
            "",
            "=== COLONNES ===",
        ]
        for col, info in profile["columns"].items():
            line = (
                f"- {col}: type={info.get('type', info['dtype'])}, "
                f"uniques={info['nunique']}, manquantes={info['missing_pct']}%"
            )
            if "top_values" in info:
                line += f", top={list(info['top_values'].items())[:3]}"
            if "mean" in info:
                line += f", moy={info['mean']}, min={info['min']}, max={info['max']}"
            lines.append(line)

        lines += ["", "=== ÉCHANTILLON (5 premières lignes) ==="]
        try:
            lines.append(df.head(5).to_csv(index=False)[:3000])
        except Exception:
            lines.append(str(df.head(5)))
        return "\n".join(lines)
