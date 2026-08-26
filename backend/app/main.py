"""Point d'entree FastAPI. Les routers metier sont montes ici, jamais de logique."""

import time
import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, files, partages, workspaces
from app.core.config import get_settings
from app.core.database import create_schema
from app.core.errors import ErreurUtilisateur
from app.core.journal import configurer, id_requete, obtenir

configurer()
settings = get_settings()
journal = obtenir(__name__)


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


@app.middleware("http")
async def tracer(requete: Request, suivant: Callable) -> Response:
    """Donne un identifiant a chaque requete et journalise ce qu'elle a fait.

    L'identifiant est renvoye dans l'en-tete : quand quelqu'un signale une erreur,
    il suffit de le lire dans les outils du navigateur pour retrouver la ligne
    exacte cote serveur, sans chercher par horodatage.
    """
    jeton = id_requete.set(uuid.uuid4().hex[:12])
    debut = time.perf_counter()
    try:
        reponse = await suivant(requete)
    except Exception:
        # Journalise avant de laisser remonter : sinon la trace se perd dans le
        # gestionnaire par defaut et il ne reste qu'un 500 sans explication.
        journal.exception(
            "requete interrompue",
            extra={
                "methode": requete.method,
                "chemin": requete.url.path,
                "duree_ms": int((time.perf_counter() - debut) * 1000),
            },
        )
        id_requete.reset(jeton)
        raise

    duree = int((time.perf_counter() - debut) * 1000)
    journal.info(
        "requete",
        extra={
            "methode": requete.method,
            "chemin": requete.url.path,
            "statut": reponse.status_code,
            "duree_ms": duree,
        },
    )
    reponse.headers["X-Request-ID"] = id_requete.get() or ""
    id_requete.reset(jeton)
    return reponse


@app.exception_handler(ErreurUtilisateur)
async def erreur_utilisateur(_: Request, erreur: ErreurUtilisateur) -> JSONResponse:
    """Les erreurs imputables a la demande sortent telles quelles, en francais."""
    journal.info(
        "refus",
        extra={"message_utilisateur": erreur.message, "statut": erreur.code_http},
    )
    return JSONResponse(status_code=erreur.code_http, content={"detail": erreur.message})


app.include_router(workspaces.router)
app.include_router(files.router)
app.include_router(chat.router)
app.include_router(partages.router)


@app.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    """Sonde de disponibilite : utilisee par Docker et la CI."""
    return {"status": "ok"}
