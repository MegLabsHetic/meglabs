"""Point d'entree FastAPI. Les routers metier sont montes ici, jamais de logique."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import files, workspaces
from app.core.config import get_settings
from app.core.database import create_schema
from app.core.errors import ErreurUtilisateur

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


@app.exception_handler(ErreurUtilisateur)
async def erreur_utilisateur(_: Request, erreur: ErreurUtilisateur) -> JSONResponse:
    """Les erreurs imputables a la demande sortent telles quelles, en francais."""
    return JSONResponse(status_code=erreur.code_http, content={"detail": erreur.message})


app.include_router(workspaces.router)
app.include_router(files.router)


@app.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    """Sonde de disponibilite : utilisee par Docker et la CI."""
    return {"status": "ok"}
