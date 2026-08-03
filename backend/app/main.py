"""Point d'entree FastAPI. Les routers metier sont montes ici, jamais de logique."""

from fastapi import FastAPI

app = FastAPI(
    title="MegLabs",
    description="Analyse de donnees pilotee en francais naturel.",
    version="0.1.0",
)


@app.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    """Sonde de disponibilite : utilisee par Docker et la CI."""
    return {"status": "ok"}
