"""Source de donnees externe : une base branchee a un espace de travail.

Les identifiants de connexion sont chiffres. Ils ouvrent un acces qui ne nous
appartient pas : une base tierce compromise par notre faute est plus grave
qu'une de nos propres tables.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class DataSource(Entity):
    __tablename__ = "data_sources"

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    # Le type de connecteur. Une chaine plutot qu'une enumeration : ajouter une
    # source ne doit pas demander une migration de schema.
    source_type: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))

    # Chiffre par `SourceService`. Jamais renvoye tel quel par l'API.
    config: Mapped[str] = mapped_column(Text)

    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    tables_synchronisees: Mapped[int] = mapped_column(default=0)
