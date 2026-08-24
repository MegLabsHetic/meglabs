"""Execution des lectures SQL, sur les seules donnees de l'espace de travail.

DuckDB tourne dans le processus : aucune base a heberger, aucune donnee qui sort du
serveur. C'est l'argument de frugalite autant que celui de souverainete.

Trois garanties, chacune independante des deux autres :
 - une connexion neuve par requete, en memoire — rien ne subsiste d'une question a la
   suivante, et deux espaces de travail ne peuvent pas se voir ;
 - l'acces au systeme de fichiers est coupe dans la configuration du moteur, en plus
   d'etre refuse par `sql_guard` ;
 - une requete trop longue est interrompue, plutot que de retenir une connexion et un
   fil d'execution jusqu'a epuisement.
"""

import asyncio
import time
from dataclasses import dataclass, field

import duckdb
import pandas as pd

from app.core.config import get_settings
from app.core.errors import ErreurUtilisateur

# Coupe l'acces aux fichiers et au reseau au niveau du moteur. `sql_guard` refuse deja
# les fonctions concernees ; ceci vaut pour tout ce que la liste aurait manque.
CONFIGURATION = {"enable_external_access": "false"}


class ErreurSql(Exception):
    """Echec d'execution cote moteur, rattrape par l'auto-reparation de l'Analyste.

    Ce n'est volontairement pas une `ErreurUtilisateur` : le message de DuckDB est
    technique et anglais. Il est fait pour etre relu par le modele, pas affiche.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class ResultatSql:
    """Ce qu'une requete a rendu, borne a ce qui est affichable."""

    colonnes: list[str]
    lignes: list[list] = field(default_factory=list)
    tronque: bool = False
    duree_ms: int = 0

    @property
    def nb_lignes(self) -> int:
        return len(self.lignes)

    def en_dicts(self) -> list[dict]:
        return [dict(zip(self.colonnes, ligne, strict=True)) for ligne in self.lignes]


class MoteurDuckdb:
    """Execute une requete de lecture deja validee par le garde-fou."""

    def __init__(self, limite_lignes: int | None = None, timeout_s: int | None = None) -> None:
        parametres = get_settings()
        self._limite = limite_lignes or parametres.max_sql_result_rows
        self._timeout = timeout_s or parametres.duckdb_timeout_seconds

    async def executer(self, sql: str, tables: dict[str, pd.DataFrame]) -> ResultatSql:
        """Lance la requete sans bloquer la boucle, et l'interrompt si elle s'eternise.

        DuckDB est synchrone : sans le fil separe, une requete lourde figerait toutes
        les autres conversations en cours.
        """
        connexion = duckdb.connect(":memory:", config=CONFIGURATION)
        for nom, table in tables.items():
            connexion.register(nom, table)

        debut = time.perf_counter()
        try:
            resultat = await self._executer_avec_delai(connexion, sql)
        except duckdb.Error as erreur:
            raise ErreurSql(str(erreur)) from erreur
        finally:
            connexion.close()

        resultat.duree_ms = int((time.perf_counter() - debut) * 1000)
        return resultat

    async def _executer_avec_delai(
        self, connexion: duckdb.DuckDBPyConnection, sql: str
    ) -> ResultatSql:
        """Interrompt le moteur au-dela du delai, puis attend que le fil se denoue.

        Interrompre ne suffit pas : le fil met un instant a remonter l'exception, et
        fermer la connexion pendant ce temps ferait tomber le processus. On attend
        donc qu'il se termine avant de rendre la main.
        """
        tache = asyncio.create_task(asyncio.to_thread(self._interroger, connexion, sql))
        try:
            return await asyncio.wait_for(asyncio.shield(tache), timeout=self._timeout)
        except TimeoutError as erreur:
            connexion.interrupt()
            await asyncio.gather(tache, return_exceptions=True)
            raise ErreurUtilisateur(
                f"Cette question a dépassé {self._timeout} secondes de calcul. "
                "Restreignez-la à une période ou à un service, puis réessayez."
            ) from erreur

    def _interroger(self, connexion: duckdb.DuckDBPyConnection, sql: str) -> ResultatSql:
        """Une ligne de plus que la limite : de quoi savoir s'il en restait."""
        curseur = connexion.execute(sql)
        lignes = curseur.fetchmany(self._limite + 1)
        colonnes = [description[0] for description in curseur.description or []]
        return ResultatSql(
            colonnes=colonnes,
            lignes=[list(ligne) for ligne in lignes[: self._limite]],
            tronque=len(lignes) > self._limite,
        )


def nom_de_table(nom_fichier: str, pris: set[str]) -> str:
    """Transforme un nom de fichier en identifiant SQL utilisable et unique.

    Le nom compte : c'est celui que le modele lira dans le schema et ecrira dans ses
    requetes, et celui que l'utilisateur verra dans le SQL affiche.
    """
    base = nom_fichier.rsplit(".", 1)[0].lower()
    propre = "".join(caractere if caractere.isalnum() else "_" for caractere in base)
    propre = propre.strip("_") or "fichier"
    if propre[0].isdigit():
        propre = f"t_{propre}"

    candidat = propre
    suffixe = 2
    while candidat in pris:
        candidat = f"{propre}_{suffixe}"
        suffixe += 1
    return candidat
