"""Transformation de nettoyage, concue pour etre rejouee.

L'etat courant d'un fichier n'est jamais stocke : il est recalcule en rejouant les
actions actives sur le fichier original, qui reste immuable. Chaque action doit donc
porter assez de parametres pour produire exactement le meme resultat a chaque rejeu —
y compris les valeurs calculees au moment de son application, comme une moyenne
d'imputation.
"""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class CleaningAction(Entity):
    __tablename__ = "cleaning_actions"

    file_id: Mapped[str] = mapped_column(
        ForeignKey("data_files.id", ondelete="CASCADE"), index=True
    )
    # `order` est un mot reserve SQL : le rang est nomme `order_index`.
    order_index: Mapped[int]
    action_type: Mapped[str] = mapped_column(String(50))
    column_name: Mapped[str | None] = mapped_column(String(255), default=None)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    rows_affected: Mapped[int] = mapped_column(default=0)
    enabled: Mapped[bool] = mapped_column(default=True)
