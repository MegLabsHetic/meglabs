"""Correspondance entre une valeur personnelle et son jeton de substitution.

Cette table n'est exposee par aucune route, sous aucune forme. C'est elle qui rend
la pseudonymisation reversible localement, donc elle constitue la donnee la plus
sensible du systeme.
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class PiiMapping(Entity):
    __tablename__ = "pii_mappings"

    file_id: Mapped[str] = mapped_column(
        ForeignKey("data_files.id", ondelete="CASCADE"), index=True
    )
    column_name: Mapped[str] = mapped_column(String(255))
    # La valeur d'origine n'est jamais stockee en clair.
    original_hash: Mapped[str] = mapped_column(String(64), index=True)
    token: Mapped[str] = mapped_column(String(100))
