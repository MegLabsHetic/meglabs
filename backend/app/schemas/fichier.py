"""Contrats de sortie des fichiers de donnees.

Les noms de champs sont en francais, comme le profil qu'ils transportent : c'est un
contrat lu directement par l'interface, qui n'affiche aucun terme technique.
"""

from datetime import datetime

from pydantic import BaseModel


class DetectionLecture(BaseModel):
    colonne: str
    type_pii: str
    confiance: float
    exemple_masque: str


class FichierLecture(BaseModel):
    id: str
    nom: str
    format: str
    taille_octets: int
    statut_pii: str
    score_qualite: float | None
    cree_le: datetime


class DepotReponse(BaseModel):
    """Reponse au depot d'un fichier : tout ce que l'interface doit afficher."""

    fichier: FichierLecture
    profil: dict
    donnees_personnelles: list[DetectionLecture]


class PseudonymisationReponse(BaseModel):
    fichier: FichierLecture
    colonnes_pseudonymisees: list[str]
    valeurs_remplacees: int
    profil: dict
