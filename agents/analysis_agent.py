import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from agents.base_agent import BaseAgent
from config import AGENT_TEMPERATURES

ANALYSIS_SYSTEM_PROMPT = """Tu es un agent spécialisé dans l'analyse de données et la data science.
Tu reçois des profils de données et tu dois proposer des analyses pertinentes.

Tes capacités :
1. Proposer des axes d'analyse stratégiques
2. Identifier des patterns et tendances
3. Recommander des segmentations
4. Analyser des corrélations
5. Interpréter des résultats statistiques

Réponds toujours en français, de manière structurée et actionnable.
Quand on te demande des axes d'analyse, retourne du JSON :
```json
{
  "axes": [
    {
      "titre": "...",
      "description": "...",
      "colonnes": ["col1", "col2"],
      "questions": ["Question 1?", "Question 2?"],
      "visualisations": ["bar_chart", "line_chart", "map", "pie_chart", "heatmap", "scatter", "box_plot"]
    }
  ]
}
```"""


class AnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Analysis",
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES["analysis"],
        )

    def suggest_axes(self, profile: dict) -> dict:
        """Get analysis axes suggestions from Claude."""
        context = self._format_profile(profile)
        return self.ask_json(
            "Propose 5 axes d'analyse pertinents pour ce dataset. "
            "Retourne le résultat en JSON.",
            context=context,
        )

    def compute_correlations(
        self, df: pd.DataFrame, numeric_cols: list
    ) -> pd.DataFrame:
        """Compute correlation matrix for numeric columns."""
        if len(numeric_cols) < 2:
            return pd.DataFrame()
        return df[numeric_cols].corr().round(3)

    def compute_segmentation(
        self, df: pd.DataFrame, columns: list, n_clusters: int = 3
    ) -> tuple[pd.DataFrame, dict]:
        """Perform K-Means segmentation on selected columns."""
        work_df = df[columns].dropna().copy()
        if len(work_df) < n_clusters:
            return df, {"error": "Pas assez de données pour la segmentation"}

        scaler = StandardScaler()
        scaled = scaler.fit_transform(work_df)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(scaled)

        result_df = work_df.copy()
        result_df["segment"] = labels

        # Compute segment profiles
        segment_info = {}
        for seg in range(n_clusters):
            mask = result_df["segment"] == seg
            segment_info[f"Segment {seg}"] = {
                "count": int(mask.sum()),
                "pct": round(mask.mean() * 100, 1),
                "means": result_df[mask][columns].mean().round(2).to_dict(),
            }

        return result_df, {
            "n_clusters": n_clusters,
            "inertia": round(float(kmeans.inertia_), 2),
            "segments": segment_info,
        }

    def compute_time_analysis(
        self, df: pd.DataFrame, date_col: str, value_col: str = None
    ) -> dict:
        """Analyze time-based patterns."""
        temp = df.copy()
        temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
        temp = temp.dropna(subset=[date_col])

        result = {
            "date_range": {
                "min": str(temp[date_col].min()),
                "max": str(temp[date_col].max()),
            },
            "count_by_year": temp[date_col]
            .dt.year.value_counts()
            .sort_index()
            .to_dict(),
            "count_by_month": temp[date_col]
            .dt.month.value_counts()
            .sort_index()
            .to_dict(),
            "count_by_dayofweek": temp[date_col]
            .dt.dayofweek.value_counts()
            .sort_index()
            .to_dict(),
        }

        if (
            value_col
            and value_col in temp.columns
            and pd.api.types.is_numeric_dtype(temp[value_col])
        ):
            result["mean_by_year"] = (
                temp.groupby(temp[date_col].dt.year)[value_col]
                .mean()
                .round(2)
                .to_dict()
            )

        return result

    def interpret_results(
        self, analysis_type: str, results: dict, profile: dict
    ) -> str:
        """Ask Claude to interpret analysis results."""
        context = f"Type d'analyse: {analysis_type}\n\nRésultats:\n{results}\n\nProfil du dataset:\n{self._format_profile(profile)}"
        return self.ask(
            "Interprète ces résultats d'analyse. Donne des insights actionnables "
            "et des recommandations. Sois précis et concis.",
            context=context,
        )

    def _format_profile(self, profile: dict) -> str:
        lines = [
            f"Dataset: {profile['shape']['rows']} lignes x {profile['shape']['columns']} colonnes",
        ]
        for col, info in profile["columns"].items():
            line = f"- {col}: type={info.get('type', info['dtype'])}, uniques={info['nunique']}"
            if "mean" in info:
                line += f", moy={info['mean']}"
            lines.append(line)
        if profile["date_columns"]:
            lines.append(f"Colonnes temporelles: {profile['date_columns']}")
        if profile["numeric_columns"]:
            lines.append(f"Colonnes numériques: {profile['numeric_columns']}")
        if profile["categorical_columns"]:
            lines.append(f"Colonnes catégorielles: {profile['categorical_columns']}")
        return "\n".join(lines)
