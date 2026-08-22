"""Contrats de la conversation : ce que le modele a le droit de repondre.

Toute sortie de modele passe par un de ces schemas. Un champ absent, un type qui ne
correspond pas, une intention inventee : la validation echoue et le client relance une
fois avec l'erreur. C'est ce qui permet de traiter la reponse d'un modele comme une
donnee et non comme du texte a interpreter.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Intention(str, Enum):
    """Ce que la personne cherche a faire. Une seule valeur possible par question."""

    QUESTION_DONNEES = "question_donnees"
    EXPLORATION = "exploration"
    VISUALISATION = "visualisation"
    NETTOYAGE = "nettoyage"
    PREDICTION = "prediction"
    RAPPORT = "rapport"
    SALUTATION = "salutation"
    HORS_SUJET = "hors_sujet"

    @property
    def demande_du_sql(self) -> bool:
        return self in {Intention.QUESTION_DONNEES, Intention.VISUALISATION}


class Comprehension(BaseModel):
    """Le resultat de l'appel fusionne : classer, traduire et decider en une fois.

    Trois appels separes coutaient trois fois le contexte pour la meme question. Les
    fusionner ramene le chemin nominal d'une question a deux appels : celui-ci, puis
    la redaction de la reponse.
    """

    intention: Intention
    sql: str | None = Field(
        default=None,
        description="Requête DuckDB en lecture seule, ou null si l'intention n'en demande pas.",
    )
    besoin_visualisation: bool = Field(
        default=False,
        description="Vrai si un graphique éclaire la réponse.",
    )
    clarification: str | None = Field(
        default=None,
        description="Question à poser si la demande est trop ambiguë pour être traduite.",
    )


class ReparationSql(BaseModel):
    """La seconde tentative de l'Analyste, apres un echec du moteur."""

    sql: str = Field(description="Requête corrigée, en lecture seule.")
    explication: str = Field(
        description="Ce qui n'allait pas, en une phrase et en français, pour l'affichage.",
    )
