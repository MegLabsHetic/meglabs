"""Contrats d'entree et de sortie des espaces de travail."""

from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreation(BaseModel):
    nom: str = Field(min_length=1, max_length=200)


class WorkspaceLecture(BaseModel):
    # Les modeles nomment leurs colonnes en anglais, les contrats d'API en francais :
    # la conversion est explicite dans le service plutot que par alias implicite.
    id: str
    nom: str
    cree_le: datetime
