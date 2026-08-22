"""L'orchestrateur : comprendre la question, en un seul appel.

Classer l'intention, traduire en SQL et decider s'il faut un graphique sont trois
decisions prises sur le meme contexte — le schema des fichiers et l'historique. Les
poser en trois appels, c'est payer trois fois ce contexte pour la meme question. Elles
sont donc fusionnees ici, et le chemin nominal d'une question tient en deux appels :
celui-ci, puis la redaction de la reponse.

Consequence assumee : ce module produit du SQL alors que l'Analyste porte le titre de
Text-to-SQL. Le partage tient : l'orchestrateur decide, l'Analyste est seul a toucher
la base — il valide, execute et se repare.
"""

from dataclasses import dataclass

from app.agents.base import BaseAgent
from app.core.config import Task
from app.prompts import charger
from app.schemas.chat import Comprehension

# Au-dela, l'historique coute plus qu'il ne rapporte : les references a resoudre
# (« et pour 2024 ? ») portent presque toujours sur le dernier echange.
ECHANGES_MEMORISES = 3

# L'historique est resume avant d'etre renvoye : une reponse entiere reinjectee a
# chaque tour ferait grossir le contexte sans rien ajouter a la comprehension.
LONGUEUR_RESUME = 200


@dataclass(frozen=True)
class Echange:
    """Un tour de conversation, tel qu'il est rappele au modele."""

    question: str
    reponse: str
    sql: str | None = None

    def resume(self) -> str:
        reponse = self.reponse.strip().replace("\n", " ")
        if len(reponse) > LONGUEUR_RESUME:
            reponse = reponse[: LONGUEUR_RESUME - 1].rstrip() + "…"
        lignes = [f"Question : {self.question}", f"Réponse : {reponse}"]
        if self.sql:
            lignes.append(f"SQL exécuté : {self.sql}")
        return "\n".join(lignes)


class Orchestrateur(BaseAgent):
    """Classe l'intention, traduit la question et decide du graphique."""

    nom = "orchestrateur"
    libelle = "Orchestrateur"

    async def comprendre(
        self,
        question: str,
        schema: str,
        memoire: list[Echange] | None = None,
    ) -> Comprehension:
        """L'appel fusionne. Une question entre, une decision complete sort."""
        async with self.etape("analyse la question"):
            return await self.demander(
                Task.SQL_GENERATION,
                charger("orchestrator_classify"),
                self._contexte(question, schema, memoire or []),
                Comprehension,
            )

    def _contexte(self, question: str, schema: str, memoire: list[Echange]) -> str:
        """Le variable, apres le stable : l'entete du prompt reste ainsi cachable."""
        morceaux = [f"## Schéma des fichiers disponibles\n\n{schema}"]
        if memoire:
            morceaux.append("## Échanges précédents\n\n" + self._rappeler(memoire))
        morceaux.append(f"## Question\n\n{question}")
        return "\n\n".join(morceaux)

    @staticmethod
    def _rappeler(memoire: list[Echange]) -> str:
        """Les derniers echanges, du plus ancien au plus recent, resumes."""
        derniers = memoire[-ECHANGES_MEMORISES:]
        return "\n\n".join(echange.resume() for echange in derniers)
