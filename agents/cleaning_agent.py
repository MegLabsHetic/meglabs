import numpy as np
import pandas as pd

from agents.base_agent import BaseAgent
from config import AGENT_TEMPERATURES

CLEANING_SYSTEM_PROMPT = """Tu es un agent spécialisé dans le nettoyage et la transformation de données.
Tu reçois un profil de dataset et des instructions de l'utilisateur.

Tu dois retourner tes recommandations en JSON avec cette structure exacte :
```json
{
  "actions": [
    {
      "type": "drop_duplicates|fill_missing|drop_column|convert_type|remove_outliers|rename_column|normalize_text",
      "column": "nom_colonne (ou null si global)",
      "params": {},
      "description": "Description de l'action",
      "raison": "Pourquoi cette action est recommandée pour ce dataset"
    }
  ],
  "summary": "Résumé des transformations"
}
```

Types d'actions disponibles :
- drop_duplicates : Supprimer les doublons
- fill_missing : Remplir les valeurs manquantes (params: strategy = mean|median|mode|drop|value, value=...)
- drop_column : Supprimer une colonne inutile
- convert_type : Convertir le type (params: target_type = datetime|numeric|category|string)
- remove_outliers : Supprimer les outliers par IQR (params: factor = 1.5)
- rename_column : Renommer une colonne (params: new_name = ...)
- normalize_text : Normaliser une colonne texte (params: mode = strip|lower|upper|title)

Ton plan sera présenté à l'utilisateur qui validera chaque action avant application.
Sois précis et justifie chaque action. Réponds UNIQUEMENT en JSON valide. Pas de texte avant ou après."""


class CleaningAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Cleaning",
            system_prompt=CLEANING_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES["cleaning"],
        )

    def suggest_cleaning(self, profile: dict) -> dict:
        """Ask Claude to suggest cleaning actions based on the profile."""
        context = self._format_profile(profile)
        return self.ask_json(
            "Analyse ce profil et propose toutes les actions de nettoyage nécessaires. "
            "Priorise : doublons, valeurs manquantes, conversions de types, outliers.",
            context=context,
        )

    def apply_actions(
        self, df: pd.DataFrame, actions: list
    ) -> tuple[pd.DataFrame, list]:
        """Apply a list of cleaning actions and return (cleaned_df, log)."""
        cleaned = df.copy()
        log = []

        for action in actions:
            try:
                action_type = action["type"]
                col = action.get("column")
                params = action.get("params", {})
                desc = action.get("description", action_type)

                before_shape = cleaned.shape

                if action_type == "drop_duplicates":
                    cleaned = cleaned.drop_duplicates()
                    dropped = before_shape[0] - cleaned.shape[0]
                    log.append(f"[OK] {desc} ({dropped} lignes supprimées)")

                elif action_type == "fill_missing" and col and col in cleaned.columns:
                    strategy = params.get("strategy", "drop")
                    if strategy == "mean" and pd.api.types.is_numeric_dtype(
                        cleaned[col]
                    ):
                        cleaned[col] = cleaned[col].fillna(cleaned[col].mean())
                    elif strategy == "median" and pd.api.types.is_numeric_dtype(
                        cleaned[col]
                    ):
                        cleaned[col] = cleaned[col].fillna(cleaned[col].median())
                    elif strategy == "mode":
                        cleaned[col] = cleaned[col].fillna(
                            cleaned[col].mode().iloc[0]
                            if not cleaned[col].mode().empty
                            else "N/A"
                        )
                    elif strategy == "drop":
                        cleaned = cleaned.dropna(subset=[col])
                    elif strategy == "value":
                        cleaned[col] = cleaned[col].fillna(params.get("value", "N/A"))
                    log.append(f"[OK] {desc}")

                elif action_type == "drop_column" and col and col in cleaned.columns:
                    cleaned = cleaned.drop(columns=[col])
                    log.append(f"[OK] {desc}")

                elif action_type == "convert_type" and col and col in cleaned.columns:
                    target = params.get("target_type", "string")
                    if target == "datetime":
                        cleaned[col] = pd.to_datetime(cleaned[col], errors="coerce")
                    elif target == "numeric":
                        cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
                    elif target == "category":
                        cleaned[col] = cleaned[col].astype("category")
                    elif target == "string":
                        cleaned[col] = cleaned[col].astype(str)
                    log.append(f"[OK] {desc}")

                elif (
                    action_type == "remove_outliers" and col and col in cleaned.columns
                ):
                    if pd.api.types.is_numeric_dtype(cleaned[col]):
                        factor = params.get("factor", 1.5)
                        q1 = cleaned[col].quantile(0.25)
                        q3 = cleaned[col].quantile(0.75)
                        iqr = q3 - q1
                        mask = (cleaned[col] >= q1 - factor * iqr) & (
                            cleaned[col] <= q3 + factor * iqr
                        )
                        removed = (~mask).sum()
                        cleaned = cleaned[mask]
                        log.append(f"[OK] {desc} ({removed} outliers supprimés)")

                elif action_type == "normalize_text" and col and col in cleaned.columns:
                    mode = params.get("mode", "strip")
                    mask = cleaned[col].notna()
                    values = cleaned.loc[mask, col].astype(str)
                    if mode == "strip":
                        cleaned.loc[mask, col] = values.str.strip()
                    elif mode == "lower":
                        cleaned.loc[mask, col] = values.str.strip().str.lower()
                    elif mode == "upper":
                        cleaned.loc[mask, col] = values.str.strip().str.upper()
                    elif mode == "title":
                        cleaned.loc[mask, col] = values.str.strip().str.title()
                    log.append(f"[OK] {desc}")

                elif action_type == "rename_column" and col and col in cleaned.columns:
                    new_name = params.get("new_name", col)
                    cleaned = cleaned.rename(columns={col: new_name})
                    log.append(f"[OK] {desc}")

                else:
                    log.append(f"[SKIP] {desc} - Action non applicable")

            except Exception as e:
                log.append(f"[ERREUR] {action.get('description', 'Unknown')}: {str(e)}")

        return cleaned, log

    def estimate_impact(self, df: pd.DataFrame, action: dict) -> str:
        """Estimate how many rows/values an action would affect (deterministic)."""
        try:
            action_type = action.get("type")
            col = action.get("column")
            params = action.get("params", {}) or {}

            if action_type == "drop_duplicates":
                n = int(df.duplicated().sum())
                return f"{n} ligne(s) dupliquée(s) supprimée(s)"

            if action_type == "fill_missing" and col in df.columns:
                n = int(df[col].isna().sum())
                strategy = params.get("strategy", "?")
                if strategy == "drop":
                    return f"{n} ligne(s) supprimée(s)"
                return f"{n} valeur(s) remplie(s) ({strategy})"

            if action_type == "drop_column":
                return "1 colonne supprimée"

            if action_type == "convert_type" and col in df.columns:
                target = params.get("target_type", "?")
                if target == "numeric":
                    lost = int(pd.to_numeric(df[col], errors="coerce").isna().sum()
                               - df[col].isna().sum())
                    return f"{len(df)} valeur(s) converties, {max(0, lost)} non convertible(s)"
                if target == "datetime":
                    parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
                    lost = int(parsed.isna().sum() - df[col].isna().sum())
                    return f"{len(df)} valeur(s) converties, {max(0, lost)} non convertible(s)"
                return f"{len(df)} valeur(s) converties"

            if action_type == "remove_outliers" and col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    factor = params.get("factor", 1.5)
                    q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
                    iqr = q3 - q1
                    n = int(((df[col] < q1 - factor * iqr)
                             | (df[col] > q3 + factor * iqr)).sum())
                    return f"{n} ligne(s) outlier(s) supprimée(s)"

            if action_type == "normalize_text" and col in df.columns:
                n = int(df[col].notna().sum())
                return f"{n} valeur(s) normalisée(s)"

            if action_type == "rename_column":
                return "renommage (aucune ligne modifiée)"

        except Exception:
            pass
        return "impact non estimé"

    def auto_clean(
        self, df: pd.DataFrame, profile: dict
    ) -> tuple[pd.DataFrame, list, dict]:
        """Full auto-clean: get suggestions from Claude, then apply them."""
        suggestions = self.suggest_cleaning(profile)
        actions = suggestions.get("actions", [])
        if not actions:
            return df, ["Aucune action de nettoyage nécessaire."], suggestions
        cleaned, log = self.apply_actions(df, actions)
        return cleaned, log, suggestions

    def _format_profile(self, profile: dict) -> str:
        lines = [
            f"Dataset: {profile['shape']['rows']} lignes x {profile['shape']['columns']} colonnes",
            f"Doublons: {profile['duplicates']}",
        ]
        for col, info in profile["columns"].items():
            line = f"- {col}: type={info.get('type', info['dtype'])}, manquantes={info['missing']} ({info['missing_pct']}%), uniques={info['nunique']}"
            if "outliers" in info:
                line += f", outliers={info['outliers']}"
            lines.append(line)
        return "\n".join(lines)
