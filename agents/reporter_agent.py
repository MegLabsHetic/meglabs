"""Reporter Agent - Generates natural language summaries and insights for reports."""

from agents.base_agent import BaseAgent
from config import AGENT_TEMPERATURES

REPORTER_SYSTEM_PROMPT = """Tu es un agent specialise dans la generation de rapports d'analyse de donnees.
Tu recois un profil de dataset, des resultats d'analyse, et tu dois produire un rapport clair et professionnel.

Tes responsabilites :
1. Rediger un resume executif clair et concis
2. Mettre en avant les insights cles
3. Formuler des recommandations actionnables
4. Structurer le contenu de facon professionnelle

Reponds toujours en francais, de maniere structuree avec des titres, bullet points et mise en forme Markdown."""


class ReporterAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Reporter",
            system_prompt=REPORTER_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES.get("reporter", 0.2),
        )

    def generate_executive_summary(self, profile: dict, analyses: dict = None) -> str:
        """Generate an executive summary of the data analysis."""
        context = self._build_context(profile, analyses)
        return self.ask(
            "Genere un resume executif professionnel pour ce dataset. Inclus :\n"
            "1. Vue d'ensemble des donnees\n"
            "2. Qualite des donnees (score sur 10)\n"
            "3. Insights principaux (3-5 points)\n"
            "4. Recommandations (3-5 points)\n"
            "5. Prochaines etapes suggerees\n\n"
            "Format le resultat en Markdown propre.",
            context=context,
        )

    def generate_section_insight(self, section: str, data: dict, profile: dict) -> str:
        """Generate insights for a specific analysis section."""
        context = f"Section: {section}\nDonnees: {data}\n\nProfil: {self._build_context(profile)}"
        return self.ask(
            f"Genere une analyse detaillee pour la section '{section}'. "
            "Sois precis et donne des insights actionnables.",
            context=context,
        )

    def _build_context(self, profile: dict, analyses: dict = None) -> str:
        lines = [
            f"Dataset: {profile['shape']['rows']} lignes x {profile['shape']['columns']} colonnes",
            f"Memoire: {profile['memory_mb']} MB",
            f"Doublons: {profile['duplicates']}",
        ]
        for col, info in profile["columns"].items():
            line = f"- {col}: {info.get('type', info['dtype'])}, {info['nunique']} uniques, {info['missing']} manquantes"
            if "mean" in info:
                line += f", moy={info['mean']}"
            lines.append(line)

        if profile["geo_info"]["has_geo"]:
            lines.append("Donnees geographiques: OUI")
        if profile["date_columns"]:
            lines.append(f"Colonnes temporelles: {profile['date_columns']}")

        if analyses:
            lines.append("\n=== RESULTATS D'ANALYSE ===")
            if "axes" in analyses:
                lines.append(f"Axes d'analyse: {len(analyses['axes'])} axes proposes")
                for axe in analyses.get("axes", []):
                    lines.append(f"  - {axe.get('titre', 'N/A')}")
            if "segmentation" in analyses:
                seg = analyses["segmentation"]
                lines.append(f"Segmentation: {seg.get('info', {}).get('n_clusters', '?')} clusters")

        return "\n".join(lines)
