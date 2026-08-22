"""L'Analyste : le seul agent qui touche les donnees.

Il fait trois choses, dans cet ordre : decrire les fichiers au modele, relire ce que
le modele a ecrit, et l'executer. Si le moteur refuse la requete, il la corrige une
fois — et il le montre, parce qu'une correction invisible ne prouve rien.

Une seule reprise, volontairement. Un modele qui echoue deux fois sur la meme question
ne trouvera pas a la troisieme : il tournera, et chaque tour se paie.
"""

import pandas as pd

from app.agents.base import BaseAgent
from app.core.config import Task
from app.core.duckdb_engine import ErreurSql, MoteurDuckdb, ResultatSql
from app.core.errors import ErreurUtilisateur
from app.core.events import evenement_reparation, evenement_sql
from app.core.sql_guard import GardeFouSql, SqlRefuse
from app.prompts import charger
from app.schemas.chat import ReparationSql

# Ce qui part au modele pour qu'il ecrive sa requete : des noms, des types, trois
# valeurs. Jamais une ligne complete — la representation est deja bornee en amont par
# `profiling_service.llm_context`, on ne fait ici que la mettre en forme.
EXEMPLES_PAR_COLONNE = 3
LONGUEUR_EXEMPLE = 80


class Analyste(BaseAgent):
    """Traduit un schema, valide une requete, l'execute, la repare une fois."""

    nom = "analyste"
    libelle = "Agent Analyste"

    def __init__(
        self,
        *args,
        garde: GardeFouSql | None = None,
        moteur: MoteurDuckdb | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._garde = garde or GardeFouSql()
        self._moteur = moteur or MoteurDuckdb()

    # --- Ce que le modele voit des donnees ----------------------------------

    def decrire(self, schemas: dict[str, dict]) -> str:
        """Le schema des fichiers, en texte, tel qu'il entre dans le prompt.

        `schemas` associe un nom de table au contexte compresse produit par le
        profilage. Rien d'autre ne doit y entrer.
        """
        return "\n\n".join(
            self._decrire_table(table, contexte) for table, contexte in schemas.items()
        )

    def _decrire_table(self, table: str, contexte: dict) -> str:
        entete = f"### Table `{table}` — {contexte['nb_lignes']} lignes"
        colonnes = [self._decrire_colonne(colonne) for colonne in contexte["colonnes"]]
        return entete + "\n" + "\n".join(colonnes)

    def _decrire_colonne(self, colonne: dict) -> str:
        ligne = f"- `{colonne['nom']}` ({colonne['type']})"
        exemples = [self._borner(valeur) for valeur in colonne["exemples"][:EXEMPLES_PAR_COLONNE]]
        if exemples:
            ligne += " — exemples : " + ", ".join(exemples)
        if colonne["part_manquantes"]:
            ligne += f" — {colonne['part_manquantes']} % de valeurs absentes"
        return ligne

    @staticmethod
    def _borner(valeur: object) -> str:
        """Une valeur d'exemple est une donnee, jamais une instruction : on la borne.

        Les guillemets encadrent la valeur pour qu'une phrase glissee dans une cellule
        se lise comme un contenu et non comme une consigne adressee au modele.
        """
        texte = str(valeur).replace("\n", " ").replace("`", "'")
        if len(texte) > LONGUEUR_EXEMPLE:
            texte = texte[: LONGUEUR_EXEMPLE - 1] + "…"
        return f'"{texte}"'

    # --- Execution ----------------------------------------------------------

    async def executer(
        self,
        sql: str,
        tables: dict[str, pd.DataFrame],
        schema: str,
    ) -> tuple[ResultatSql, str]:
        """Valide puis execute. Renvoie le resultat et la requete reellement passee."""
        async with self.etape("vérifie et exécute la requête"):
            requete = self._garde.verifier(sql, tables.keys())
            try:
                resultat = await self._moteur.executer(requete, tables)
            except ErreurSql as echec:
                requete, resultat = await self._reparer(requete, echec, tables, schema)

            await self._publier_sql(requete, resultat)
            return resultat, requete

    async def _reparer(
        self,
        requete_echouee: str,
        echec: ErreurSql,
        tables: dict[str, pd.DataFrame],
        schema: str,
    ) -> tuple[str, ResultatSql]:
        """La seconde chance. Un second echec devient une erreur affichable."""
        await self.progresser("la requête a échoué, je la corrige")
        correction = await self.demander(
            Task.SQL_GENERATION,
            charger("analyst_repair"),
            self._contexte_reparation(requete_echouee, echec.message, schema),
            ReparationSql,
        )

        try:
            requete = self._garde.verifier(correction.sql, tables.keys())
            resultat = await self._moteur.executer(requete, tables)
        except (ErreurSql, SqlRefuse) as second_echec:
            raise ErreurUtilisateur(
                "Je n'arrive pas à traduire cette question en une requête qui aboutit. "
                "Reformulez-la en nommant précisément la colonne ou la période visée."
            ) from second_echec

        await self._flux_reparation(requete_echouee, echec.message, requete, correction.explication)
        return requete, resultat

    @staticmethod
    def _contexte_reparation(requete: str, erreur: str, schema: str) -> str:
        return (
            f"## Schéma réel\n\n{schema}\n\n"
            f"## Requête qui a échoué\n\n```sql\n{requete}\n```\n\n"
            f"## Message du moteur\n\n{erreur}"
        )

    # --- Ce que l'ecran montre ----------------------------------------------

    async def _publier_sql(self, requete: str, resultat: ResultatSql) -> None:
        if self._flux is None:
            return
        await self._flux.publier(
            evenement_sql(requete, resultat.duree_ms, resultat.nb_lignes, resultat.tronque)
        )

    async def _flux_reparation(
        self, sql_echoue: str, erreur: str, sql_corrige: str, explication: str
    ) -> None:
        if self._flux is None:
            return
        await self._flux.publier(
            evenement_reparation(sql_echoue, erreur, sql_corrige, explication)
        )
