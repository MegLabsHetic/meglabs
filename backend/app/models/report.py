"""Rapport genere, et son eventuel lien de partage public."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class Report(Entity):
    __tablename__ = "reports"

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence_score: Mapped[float | None] = mapped_column(default=None)
    # Nul tant que le rapport n'est pas partage ; le remettre a nul revoque le lien.
    share_token: Mapped[str | None] = mapped_column(
        String(64), default=None, unique=True, index=True
    )
