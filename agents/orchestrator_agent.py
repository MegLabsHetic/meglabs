import pandas as pd

from agents.base_agent import BaseAgent
from config import AGENT_TEMPERATURES

ORCHESTRATOR_SYSTEM_PROMPT = """Tu es l'orchestrateur principal d'une plateforme d'analyse de données IA.
Tu comprends le français et l'anglais. Tu réponds toujours en français.

Ton rôle est de :
1. Comprendre les demandes de l'utilisateur en langage naturel
2. Router vers le bon agent spécialisé
3. Fournir des réponses claires et utiles

Quand l'utilisateur fait une demande, tu dois classifier son intention parmi :
- "profile" : L'utilisateur veut comprendre/explorer ses données
- "clean" : L'utilisateur veut nettoyer ou transformer ses données
- "analyze" : L'utilisateur veut des analyses, corrélations, segmentation, axes d'analyse
- "visualize" : L'utilisateur veut des graphiques, dashboards, cartes
- "question" : L'utilisateur pose une question générale sur ses données
- "help" : L'utilisateur demande de l'aide sur l'utilisation

Retourne TOUJOURS ta réponse en JSON :
```json
{
  "intent": "profile|clean|analyze|visualize|question|help",
  "response": "Ta réponse à l'utilisateur en français",
  "details": "Détails supplémentaires ou paramètres si nécessaire"
}
```"""


class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Orchestrator",
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES["orchestrator"],
        )

    def process_message(
        self, user_message: str, df: pd.DataFrame = None, profile: dict = None
    ) -> dict:
        """Process a user message and route to the appropriate agent."""
        context = ""
        if profile:
            context = self._build_context(profile)

        result = self.ask_json(user_message, context=context)
        intent = result.get("intent", "question")
        response_text = result.get("response", "")

        return {
            "intent": intent,
            "response": response_text,
            "details": result.get("details", ""),
            "raw": result,
            "user_message": user_message,
        }

    def handle_intent(
        self, intent: str, df: pd.DataFrame, profile: dict, agents: dict,
        user_message: str = ""
    ) -> dict:
        """Execute the action corresponding to the detected intent.

        Args:
            intent: The detected intent string.
            df: The current DataFrame.
            profile: The current data profile.
            agents: Dict of shared agent instances (profiler, cleaner, analyzer, visualizer).
            user_message: The original user message (for question intent).
        """
        if intent == "profile":
            insights = agents["profiler"].get_ai_insights(profile)
            return {"type": "text", "content": insights}

        elif intent == "clean":
            cleaned_df, log, suggestions = agents["cleaner"].auto_clean(df, profile)
            return {
                "type": "cleaning",
                "cleaned_df": cleaned_df,
                "log": log,
                "suggestions": suggestions,
            }

        elif intent == "analyze":
            axes = agents["analyzer"].suggest_axes(profile)
            return {"type": "analysis", "axes": axes}

        elif intent == "visualize":
            chart_specs = agents["visualizer"].auto_dashboard(df, profile)
            charts = agents["visualizer"].create_all_charts(df, chart_specs, profile)
            return {"type": "dashboard", "charts": charts, "specs": chart_specs}

        elif intent == "help":
            return {
                "type": "text",
                "content": (
                    "**Comment utiliser DataAnalyst AI :**\n\n"
                    "1. **Uploadez** un fichier CSV ou Excel\n"
                    "2. **Explorez** vos données dans l'onglet Profiling\n"
                    "3. **Discutez** avec moi dans le chat, par exemple :\n"
                    '   - "Montre-moi les données"\n'
                    '   - "Nettoie les données"\n'
                    '   - "Propose des axes d\'analyse"\n'
                    '   - "Crée un dashboard"\n'
                    '   - "Fais une segmentation"\n'
                    '   - "Montre la carte"\n'
                    "4. **Visualisez** les résultats dans les onglets dédiés"
                ),
            }

        else:
            # Generic question - use the profiler to answer data-related questions
            question = user_message or intent
            context = ""
            if profile:
                context = agents["profiler"]._format_profile_for_ai(profile)
            answer = agents["profiler"].ask(
                f"L'utilisateur pose cette question sur ses données : {question}\n"
                "Réponds de manière précise et utile en te basant sur le profil des données.",
                context=context,
            )
            return {"type": "text", "content": answer}

    def _build_context(self, profile: dict) -> str:
        lines = [
            f"Dataset chargé: {profile['shape']['rows']} lignes x {profile['shape']['columns']} colonnes",
            f"Colonnes: {list(profile['columns'].keys())}",
            f"Types: temporelles={profile['date_columns']}, numériques={profile['numeric_columns']}, catégorielles={profile['categorical_columns']}",
            f"Données géo: {'Oui' if profile['geo_info']['has_geo'] else 'Non'}",
            f"Valeurs manquantes: {sum(v['count'] for v in profile['missing_values'].values())} au total",
        ]
        return "\n".join(lines)
