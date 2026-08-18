"""Agent d'analyse conversationnel : répond en langage naturel et propose,
si utile, une visualisation calculable (même format de spec que les KPIs)."""

from agents.base_agent import BaseAgent
from config import AGENT_TEMPERATURES

CHAT_SYSTEM_PROMPT = """Tu es un analyste de données conversationnel pour une plateforme de BI.
Tu t'adresses à un utilisateur NON technique : sois clair, concret, accessible.
Réponds toujours dans la langue de la question (français, anglais ou arabe).

On te fournit le profil d'un dataset et une question. Tu réponds, et si un chiffre clé,
une répartition ou une évolution aide à répondre, tu fournis une spécification de
visualisation CALCULABLE (elle sera exécutée sur les vraies données, ne calcule pas toi-même).

Retourne UNIQUEMENT ce JSON, sans texte autour :
{
  "reponse": "ta réponse en français, 2 à 4 phrases, ton accessible",
  "visualisation": null | {
    "titre": "titre court du graphique/indicateur",
    "operation": "count|sum|mean|median|min|max|nunique|ratio|part",
    "colonne": "nom_colonne ou null",
    "valeur_cible": "valeur exacte de la colonne (uniquement si operation=part)",
    "operation_denominateur": "count (uniquement si operation=ratio)",
    "colonne_denominateur": "nom_colonne (uniquement si operation=ratio)",
    "group_by": "colonne catégorielle pour une répartition, ou null",
    "date_col": "colonne date pour une évolution, ou null",
    "granularite": "mois",
    "format": "nombre|pourcentage|monetaire"
  },
  "suggestions": ["question de suivi 1", "question de suivi 2", "question de suivi 3"]
}

Règles STRICTES :
- Utilise UNIQUEMENT des colonnes réellement présentes dans le profil fourni.
- Propose une "visualisation" seulement si la question porte sur un chiffre, une
  répartition (group_by) ou une évolution dans le temps (date_col). Sinon mets null.
- operation sum/mean/median/min/max exigent une colonne NUMÉRIQUE. Ne les
  applique JAMAIS à une colonne catégorielle ou texte.
- Pour un TAUX sur une colonne catégorielle (ex: « quel est le taux de commandes
  livrées ? »), utilise operation="part" avec colonne="status",
  valeur_cible="Livré" et format="pourcentage". N'utilise jamais "ratio" sur du
  texte : le résultat serait faux.
- "group_by" -> graphique en barres ; "date_col" -> courbe ; ni l'un ni l'autre -> chiffre unique.
- 3 suggestions maximum, courtes, réellement répondables avec ce dataset.
- Réponds UNIQUEMENT en JSON valide."""


class ChatAnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ChatAnalyst",
            system_prompt=CHAT_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES.get("orchestrator", 0.3),
        )

    def answer(self, profile: dict, message: str, history: list = None) -> dict:
        # Stateless : on repart de zéro et on injecte l'historique dans le contexte
        self.reset()
        context = self._format(profile, history)
        return self.ask_json(message, context=context)

    def _format(self, profile: dict, history: list = None) -> str:
        lines = [
            f"Dataset : {profile['shape']['rows']} lignes x {profile['shape']['columns']} colonnes",
            "",
            "=== COLONNES ===",
        ]
        for col, info in profile["columns"].items():
            line = f"- {col} ({info.get('type', info['dtype'])}) : {info['nunique']} valeurs uniques"
            if "mean" in info:
                line += f", moy={info['mean']}, min={info['min']}, max={info['max']}"
            if "top_values" in info:
                line += f", top={list(info['top_values'].items())[:3]}"
            lines.append(line)
        lines.append(f"\nColonnes numériques : {profile.get('numeric_columns')}")
        lines.append(f"Colonnes catégorielles : {profile.get('categorical_columns')}")
        lines.append(f"Colonnes temporelles : {profile.get('date_columns')}")

        if history:
            lines.append("\n=== CONVERSATION PRÉCÉDENTE ===")
            for m in history[-6:]:
                role = "Utilisateur" if m.get("role") == "user" else "Assistant"
                lines.append(f"{role} : {str(m.get('content', ''))[:300]}")
        return "\n".join(lines)
