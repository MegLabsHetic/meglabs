"""Lecture publique d'un rapport partagé.

Ce routeur est le seul qui ne demande aucun espace de travail : c'est le point
d'entrée d'un lien transmis à quelqu'un d'extérieur. Il ne rend que le contenu
figé au moment du partage, et rien qui permette de remonter à l'espace.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.report_service import ReportService

router = APIRouter(prefix="/api/partages", tags=["partages"])
rapports = ReportService()


@router.get("/{jeton}")
async def lire(jeton: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Le rapport derrière un lien.

    Un lien révoqué et un lien qui n'a jamais existé rendent la même erreur :
    distinguer les deux dirait à un curieux qu'il a trouvé quelque chose.
    """
    return await rapports.lire_partage(session, jeton)
