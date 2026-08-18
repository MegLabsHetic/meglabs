"""Agent de reporting : redige l'analyse a partir des chiffres deja calcules.

Le modele ne calcule rien et n'invente aucun nombre : on lui donne les
resultats reels de chaque indicateur du tableau de bord, il en tire une
lecture et des recommandations. Tout chiffre cite dans le texte doit donc
provenir des donnees fournies.
"""

from agents.base_agent import BaseAgent
from agents.langue import directive
from config import AGENT_TEMPERATURES

REPORT_SYSTEM_PROMPT = """Tu es analyste de donnees et tu rediges un rapport destine a
une direction. On te fournit les resultats DEJA CALCULES des indicateurs suivis.

Retourne UNIQUEMENT ce JSON, sans texte autour :
{
  "titre": "titre du rapport, court et parlant",
  "synthese": "3 a 5 phrases : ce qu'il faut retenir si on ne lit que ca",
  "etat_des_lieux": [
    {"titre": "sous-titre court", "texte": "2 a 4 phrases citant les chiffres fournis"}
  ],
  "points_attention": [
    {"titre": "ce qui cloche", "texte": "le constat, chiffre a l'appui"}
  ],
  "recommandations": [
    {"action": "action concrete a mener", "pourquoi": "le chiffre qui la justifie"}
  ]
}

Regles STRICTES :
- N'invente AUCUN chiffre. Tu ne peux citer que des valeurs presentes dans les
  resultats fournis. Si une information manque, ne la mentionne pas.
- Ne deduis pas une tendance d'un seul point : une evolution ne se commente que
  si la serie fournie comporte plusieurs periodes.
- Pas de superlatif creux ni de jargon. Un dirigeant doit comprendre en une lecture.
- 2 a 4 blocs d'etat des lieux, 0 a 3 points d'attention, 2 a 4 recommandations.
- Une recommandation est une ACTION (« relancer », « verifier », « renforcer »),
  pas un constat deguise.
- S'il n'y a pas de point d'attention reel, renvoie une liste vide plutot que
  d'en fabriquer un.
- Reponds UNIQUEMENT en JSON valide."""


def format_resultats(indicateurs: list) -> str:
    """Met les resultats calcules en forme pour le contexte du modele."""
    lines = ["=== RESULTATS CALCULES SUR LES DONNEES REELLES ==="]
    for ind in indicateurs:
        lines.append(f"\n## {ind.get('titre', 'Indicateur')}")
        if ind.get("sql"):
            lines.append(f"   calcul : {ind['sql']}")
        lignes = ind.get("lignes") or []
        if not lignes:
            lines.append("   (aucune donnee)")
            continue
        # Une tuile tient sur une ligne ; une serie est plafonnee pour ne pas
        # noyer le contexte sous des centaines de lignes.
        for row in lignes[:25]:
            valeurs = " | ".join(f"{k} = {v}" for k, v in row.items())
            lines.append(f"   - {valeurs}")
        if len(lignes) > 25:
            lines.append(f"   … et {len(lignes) - 25} lignes supplementaires")
    return "\n".join(lines)


class ReportAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Reporter",
            system_prompt=REPORT_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES.get("reporter", 0.2),
        )

    def rediger(
        self,
        indicateurs: list,
        contexte: str = "",
        langue: str = "fr",
        demande: str = "",
    ) -> dict:
        self.reset()
        bloc = directive(langue) + "\n\n" + format_resultats(indicateurs)
        if contexte:
            bloc += f"\n\n=== CONTEXTE ===\n{contexte}"
        message = demande.strip() or "Rediges le rapport d'analyse de ces donnees."
        return self.ask_json(message, context=bloc)
