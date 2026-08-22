"""Le Redacteur : transformer un tableau en phrase francaise.

C'est le seul agent dont la sortie est lue telle quelle par l'utilisateur, donc le seul
a diffuser mot a mot. Il ne calcule rien : tout ce qu'il cite vient du resultat qu'on
lui remet, et ce resultat est deja borne.
"""

from collections.abc import AsyncIterator

from app.agents.base import BaseAgent
from app.core.config import Task
from app.core.duckdb_engine import ResultatSql
from app.prompts import charger

# Ce qui part au modele pour qu'il redige. Vingt lignes suffisent a decrire une
# repartition ; au-dela on paierait du contexte pour une phrase identique.
LIGNES_TRANSMISES = 20


class Redacteur(BaseAgent):
    """Interprete un resultat en francais, au fil de l'eau."""

    nom = "redacteur"
    libelle = "Rédacteur"

    async def interpreter(self, question: str, resultat: ResultatSql) -> AsyncIterator[str]:
        """Diffuse la reponse. L'etape reste ouverte tant que le flux coule."""
        async with self.etape("rédige la réponse"):
            flux = self.raconter(
                Task.INTERPRETATION,
                charger("writer_interpret"),
                self._contexte(question, resultat),
            )
            async for morceau in flux:
                yield morceau

    def _contexte(self, question: str, resultat: ResultatSql) -> str:
        morceaux = [f"## Question\n\n{question}", f"## Résultat\n\n{self._en_tableau(resultat)}"]
        if resultat.tronque:
            morceaux.append(
                "## Limite\n\nLe résultat est tronqué : il en existe davantage que ce "
                "qui est montré ici."
            )
        return "\n\n".join(morceaux)

    @staticmethod
    def _en_tableau(resultat: ResultatSql) -> str:
        """Un tableau texte plutot que du JSON : moins de jetons pour la meme lecture."""
        if not resultat.lignes:
            return "Aucune ligne. La requête n'a rien renvoyé."

        entete = " | ".join(resultat.colonnes)
        lignes = [
            " | ".join("" if valeur is None else str(valeur) for valeur in ligne)
            for ligne in resultat.lignes[:LIGNES_TRANSMISES]
        ]
        tableau = "\n".join([entete, "-" * len(entete), *lignes])

        reste = resultat.nb_lignes - LIGNES_TRANSMISES
        if reste > 0:
            tableau += f"\n… et {reste} autres lignes non montrées ici."
        return tableau
