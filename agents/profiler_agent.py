import numpy as np
import pandas as pd

from agents.base_agent import BaseAgent
from config import AGENT_TEMPERATURES
from utils.geo_utils import detect_geo_columns

PROFILER_SYSTEM_PROMPT = """Tu es un agent spécialisé dans le profiling et l'analyse exploratoire de données.
Tu reçois un résumé structuré d'un dataset et tu dois fournir une analyse claire et actionnable.

Tes responsabilités :
1. Résumer la structure du dataset (colonnes, types, taille)
2. Identifier les problèmes de qualité (valeurs manquantes, doublons, outliers)
3. Détecter les types sémantiques (dates, coordonnées, catégories, texte libre, IDs)
4. Proposer 3 à 5 axes d'analyse pertinents basés sur les données
5. Identifier les relations potentielles entre colonnes

Réponds toujours en français. Sois concis et structuré."""


class ProfilerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Profiler",
            system_prompt=PROFILER_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES["profiler"],
        )

    def profile_dataframe(self, df: pd.DataFrame) -> dict:
        """Generate a complete profile of the DataFrame."""
        profile = {
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": {},
            "missing_values": {},
            "duplicates": int(df.duplicated().sum()),
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            "geo_info": detect_geo_columns(df),
            "date_columns": [],
            "numeric_columns": [],
            "categorical_columns": [],
        }

        for col in df.columns:
            col_info = {
                "dtype": str(df[col].dtype),
                "nunique": int(df[col].nunique()),
                "missing": int(df[col].isna().sum()),
                "missing_pct": round(df[col].isna().mean() * 100, 1),
            }

            # Detect dates
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                col_info["type"] = "datetime"
                col_info["min"] = str(df[col].min())
                col_info["max"] = str(df[col].max())
                profile["date_columns"].append(col)
            elif isinstance(df[col].dtype, pd.CategoricalDtype):
                # Colonnes deja converties en dtype category (ex: apres nettoyage)
                col_info["type"] = "categorical"
                col_info["top_values"] = df[col].value_counts().head(5).to_dict()
                profile["categorical_columns"].append(col)
            elif df[col].dtype == "object":
                # Try to parse as date
                try:
                    parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
                    if parsed.notna().mean() > 0.8:
                        col_info["type"] = "datetime (parseable)"
                        col_info["min"] = str(parsed.min())
                        col_info["max"] = str(parsed.max())
                        profile["date_columns"].append(col)
                    else:
                        raise ValueError
                except (ValueError, TypeError):
                    col_info["type"] = (
                        "categorical" if df[col].nunique() < len(df) * 0.5 else "text"
                    )
                    col_info["top_values"] = df[col].value_counts().head(5).to_dict()
                    if col_info["type"] == "categorical":
                        profile["categorical_columns"].append(col)
            elif pd.api.types.is_bool_dtype(df[col]):
                col_info["type"] = "boolean"
                col_info["value_counts"] = df[col].value_counts().to_dict()
                profile["categorical_columns"].append(col)
            elif pd.api.types.is_numeric_dtype(df[col]):
                col_info["type"] = "numeric"
                desc = df[col].describe()
                col_info["mean"] = round(float(desc.get("mean", 0)), 2)
                col_info["std"] = round(float(desc.get("std", 0)), 2)
                col_info["min"] = float(desc.get("min", 0))
                col_info["max"] = float(desc.get("max", 0))
                col_info["median"] = round(float(desc.get("50%", 0)), 2)
                # Outlier detection (IQR)
                q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
                iqr = q3 - q1
                outliers = (
                    (df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)
                ).sum()
                col_info["outliers"] = int(outliers)
                profile["numeric_columns"].append(col)

            profile["columns"][col] = col_info

            if col_info["missing"] > 0:
                profile["missing_values"][col] = {
                    "count": col_info["missing"],
                    "pct": col_info["missing_pct"],
                }

        return profile

    def get_ai_insights(self, profile: dict) -> str:
        """Ask Claude to analyze the profile and provide insights."""
        context = self._format_profile_for_ai(profile)
        return self.ask(
            "Analyse ce profil de données. Donne-moi :\n"
            "1. Un résumé de la qualité des données\n"
            "2. Les problèmes identifiés\n"
            "3. 5 axes d'analyse pertinents avec des questions concrètes\n"
            "4. Les recommandations de nettoyage",
            context=context,
        )

    def suggest_axes(self, profile: dict) -> str:
        """Ask Claude to suggest analysis axes."""
        context = self._format_profile_for_ai(profile)
        return self.ask(
            "Propose 5 axes d'analyse détaillés pour ce dataset. "
            "Pour chaque axe, indique :\n"
            "- Le titre de l'axe\n"
            "- Les colonnes impliquées\n"
            "- Les questions auxquelles on peut répondre\n"
            "- Le type de visualisation recommandé",
            context=context,
        )

    def _format_profile_for_ai(self, profile: dict) -> str:
        """Format profile dict into a readable string for Claude."""
        lines = [
            f"Dataset: {profile['shape']['rows']} lignes x {profile['shape']['columns']} colonnes",
            f"Mémoire: {profile['memory_mb']} MB",
            f"Doublons: {profile['duplicates']}",
            "",
            "=== COLONNES ===",
        ]
        for col, info in profile["columns"].items():
            line = f"- {col} ({info.get('type', info['dtype'])}): {info['nunique']} valeurs uniques, {info['missing']} manquantes ({info['missing_pct']}%)"
            if "mean" in info:
                line += f", moy={info['mean']}, std={info['std']}"
            if "top_values" in info:
                top = list(info["top_values"].items())[:3]
                line += f", top={top}"
            if "outliers" in info and info["outliers"] > 0:
                line += f", outliers={info['outliers']}"
            lines.append(line)

        if profile["geo_info"]["has_geo"]:
            lines.append("")
            lines.append("=== DONNÉES GÉOGRAPHIQUES ===")
            geo = profile["geo_info"]
            if geo["latitude"]:
                lines.append(f"Latitude: {geo['latitude']}")
            if geo["longitude"]:
                lines.append(f"Longitude: {geo['longitude']}")
            if geo["geojson"]:
                lines.append(f"GeoJSON: {geo['geojson']}")
            if geo["location_name"]:
                lines.append(f"Noms de lieux: {geo['location_name']}")

        if profile["date_columns"]:
            lines.append(f"\nColonnes temporelles: {profile['date_columns']}")
        if profile["numeric_columns"]:
            lines.append(f"Colonnes numériques: {profile['numeric_columns']}")
        if profile["categorical_columns"]:
            lines.append(f"Colonnes catégorielles: {profile['categorical_columns']}")

        return "\n".join(lines)
