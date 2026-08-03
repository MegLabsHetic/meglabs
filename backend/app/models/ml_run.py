"""Entrainement d'un modele et ses resultats."""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class MLRun(Entity):
    __tablename__ = "ml_runs"

    file_id: Mapped[str] = mapped_column(
        ForeignKey("data_files.id", ondelete="CASCADE"), index=True
    )
    analysis_type: Mapped[str] = mapped_column(String(50))
    algorithm: Mapped[str] = mapped_column(String(50))
    # Les hyperparametres sont conserves avec les variables : sans eux, le notebook
    # exporte ne reproduirait pas le modele.
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
