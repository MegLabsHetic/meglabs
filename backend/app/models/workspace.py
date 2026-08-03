"""Espace de travail : le conteneur d'une session d'analyse."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class Workspace(Entity):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(200))
