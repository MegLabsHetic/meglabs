"""Fichier charge par l'utilisateur, et le resultat de son profilage."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class DataFile(Entity):
    __tablename__ = "data_files"

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    # Nom d'origine, conserve pour l'affichage uniquement : le fichier est stocke
    # sous un nom aleatoire (`path`) pour rendre la traversee de chemin impossible.
    name: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(10))
    size_bytes: Mapped[int]
    path: Mapped[str] = mapped_column(String(500))

    profile: Mapped[dict | None] = mapped_column(JSON, default=None)
    quality_score: Mapped[float | None] = mapped_column(default=None)
    pii_status: Mapped[str] = mapped_column(String(20), default="unknown")
