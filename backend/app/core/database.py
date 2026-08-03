"""Acces base : moteur asynchrone, session injectable, creation du schema."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

_settings = get_settings()

engine = create_async_engine(_settings.database_url, future=True)
SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependance FastAPI : une session par requete, fermee quoi qu'il arrive."""
    async with SessionFactory() as session:
        yield session


async def create_schema() -> None:
    """Cree les tables manquantes.

    Suffisant pour un POC. Des qu'un schema devra evoluer sans perdre de donnees,
    remplacer par des migrations versionnees.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
