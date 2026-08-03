"""Socle declaratif partage par toutes les tables.

Aucun type ni fonction propre a SQLite : la migration vers PostgreSQL ne doit couter
qu'un changement de `DATABASE_URL`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    """Identifiant opaque. Un entier auto-incremente divulguerait des volumes."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base declarative commune."""


class Entity(Base):
    """Identifiant et date de creation, partages par toutes les entites."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
