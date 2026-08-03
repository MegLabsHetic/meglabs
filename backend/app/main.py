"""Point d'entree FastAPI. Les routers metier sont montes ici, jamais de logique."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import create_schema

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Prepare le schema au demarrage, avant d'accepter la premiere requete."""
    await create_schema()
    yield


app = FastAPI(
    title="MegLabs",
    description="Analyse de donnees pilotee en francais naturel.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    """Sonde de disponibilite : utilisee par Docker et la CI."""
    return {"status": "ok"}
