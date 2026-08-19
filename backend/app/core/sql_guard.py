"""Garde-fou SQL : le dernier mot sur ce qui a le droit de toucher les donnees.

Le SQL execute est ecrit par un modele de langage. On ne lui fait pas confiance : on
relit ce qu'il a produit avant de l'executer. Le controle porte sur l'arbre syntaxique
et non sur le texte, parce qu'un filtre par mots-cles se contourne avec un commentaire
ou une majuscule.

Trois interdits, dans cet ordre : ecrire, lire un fichier, lire une table qui
n'appartient pas a l'espace de travail. Chaque refus dit ce qu'il refuse ET ce qu'on
peut faire a la place : quelqu'un qui demande une suppression a un besoin reel
derriere, l'ignorer ne le sert pas.
"""

from collections.abc import Iterable

import sqlglot
from sqlglot import exp

from app.core.errors import ErreurUtilisateur

DIALECTE = "duckdb"

# Tout ce qui modifie l'etat. `Command` couvre ce que sqlglot n'analyse pas
# finement : une instruction qu'on ne comprend pas est une instruction qu'on refuse.
ECRITURES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Merge,
    exp.Copy,
    exp.Grant,
    exp.Attach,
    exp.Detach,
    exp.Pragma,
    exp.Set,
    exp.Use,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Analyze,
    exp.Export,
    exp.Command,
)

# Les fonctions DuckDB qui atteignent le systeme de fichiers ou une base distante.
# Le moteur les bloque deja (voir duckdb_engine), mais un refus lisible vaut mieux
# qu'une erreur technique remontee a l'utilisateur.
FONCTIONS_FICHIER = frozenset(
    {
        "READ_CSV",
        "READ_CSV_AUTO",
        "READ_PARQUET",
        "PARQUET_SCAN",
        "READ_JSON",
        "READ_JSON_AUTO",
        "READ_JSON_OBJECTS",
        "READ_NDJSON",
        "READ_TEXT",
        "READ_BLOB",
        "SNIFF_CSV",
        "GLOB",
        "ICEBERG_SCAN",
        "DELTA_SCAN",
        "POSTGRES_SCAN",
        "MYSQL_SCAN",
        "SQLITE_SCAN",
        "INSTALL",
        "LOAD",
    }
)


class SqlRefuse(ErreurUtilisateur):
    """Refus motive. La raison et l'alternative restent separees pour l'interface."""

    def __init__(self, raison: str, alternative: str) -> None:
        super().__init__(f"{raison} {alternative}")
        self.raison = raison
        self.alternative = alternative


def _refus_lecture_seule() -> SqlRefuse:
    """Le refus central, celui que la demonstration de securite met en scene.

    Deux chemins y menent — une instruction d'ecriture a la racine, ou dissimulee
    dans une sous-requete — et l'utilisateur doit lire la meme chose dans les deux
    cas : ce qui est refuse, et ou aller pour obtenir ce qu'il voulait.
    """
    return SqlRefuse(
        "Je ne peux exécuter que des lectures (SELECT), "
        "jamais modifier ni supprimer vos données.",
        "Pour corriger un fichier, passez par l'étape Exploration : "
        "chaque nettoyage y est tracé et réversible.",
    )


class GardeFouSql:
    """Relit une requete et la rend executable, ou la refuse en francais."""

    def verifier(self, sql: str, tables_autorisees: Iterable[str]) -> str:
        """Renvoie la requete prete a executer, ou leve `SqlRefuse`.

        La requete renvoyee est regeneree depuis l'arbre analyse : ce qui s'execute
        est alors exactement ce qui a ete controle, sans qu'un commentaire ou une
        mise en forme puisse s'intercaler entre les deux.
        """
        arbre = self._analyser(sql)
        self._refuser_ecritures(arbre)
        self._refuser_fonctions_fichier(arbre)
        self._refuser_tables_inconnues(arbre, tables_autorisees)
        return arbre.sql(dialect=DIALECTE)

    # --- Etapes du controle -------------------------------------------------

    def _analyser(self, sql: str) -> exp.Expression:
        """Une requete, une seule, et qui s'analyse."""
        if not sql.strip():
            raise SqlRefuse(
                "Aucune requête n'a été produite.",
                "Reformulez votre question en nommant la donnée qui vous intéresse.",
            )
        try:
            instructions = sqlglot.parse(sql, read=DIALECTE)
        except sqlglot.ParseError as erreur:
            raise SqlRefuse(
                "Cette requête n'est pas du SQL valide.",
                "Reformulez votre question, je la traduirai à nouveau.",
            ) from erreur

        instructions = [instruction for instruction in instructions if instruction is not None]
        if len(instructions) != 1:
            raise SqlRefuse(
                "Je n'exécute qu'une seule requête à la fois.",
                "Posez vos questions l'une après l'autre.",
            )

        arbre = instructions[0]
        if not isinstance(arbre, exp.Query):
            raise _refus_lecture_seule()
        return arbre

    def _refuser_ecritures(self, arbre: exp.Expression) -> None:
        """Une ecriture peut se cacher dans une sous-requete : on fouille l'arbre."""
        for noeud in arbre.walk():
            if isinstance(noeud, ECRITURES):
                raise _refus_lecture_seule()

    def _refuser_fonctions_fichier(self, arbre: exp.Expression) -> None:
        for noeud in arbre.find_all(exp.Func):
            if self._nom_fonction(noeud) in FONCTIONS_FICHIER:
                raise SqlRefuse(
                    "Je ne lis que les fichiers de cet espace de travail.",
                    "Déposez le fichier voulu dans l'espace, il deviendra interrogeable.",
                )

    def _refuser_tables_inconnues(
        self, arbre: exp.Expression, tables_autorisees: Iterable[str]
    ) -> None:
        # Les CTE definissent leurs propres noms : les compter comme des tables
        # inconnues refuserait des requetes parfaitement legitimes.
        connues = {nom.lower() for nom in tables_autorisees}
        connues |= {cte.alias.lower() for cte in arbre.find_all(exp.CTE)}

        for table in arbre.find_all(exp.Table):
            nom = table.name.lower()
            if nom and nom in connues:
                continue
            raise SqlRefuse(
                f"« {table.name or 'source inconnue'} » ne fait pas partie de cet espace.",
                "Les fichiers interrogeables sont : " + ", ".join(sorted(connues)) + ".",
            )

    @staticmethod
    def _nom_fonction(noeud: exp.Func) -> str:
        """Le nom SQL de la fonction. Une fonction inconnue le porte dans `this`."""
        if isinstance(noeud, exp.Anonymous):
            return str(noeud.this).upper()
        return noeud.sql_name().upper()
