"""Routes des espaces de travail. Couche fine : toute la logique vit dans les services."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.workspace import WorkspaceCreation, WorkspaceLecture
from app.services.notebook_service import NotebookService
from app.services.report_service import ReportService
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api/workspaces", tags=["espaces de travail"])
service = WorkspaceService()
rapports = ReportService()
carnets = NotebookService()


@router.post("", response_model=WorkspaceLecture, status_code=201)
async def creer(
    creation: WorkspaceCreation, session: AsyncSession = Depends(get_session)
) -> WorkspaceLecture:
    return await service.creer(session, creation.nom)


@router.get("", response_model=list[WorkspaceLecture])
async def lister(session: AsyncSession = Depends(get_session)) -> list[WorkspaceLecture]:
    return await service.lister(session)


@router.get("/{workspace_id}", response_model=WorkspaceLecture)
async def recuperer(
    workspace_id: str, session: AsyncSession = Depends(get_session)
) -> WorkspaceLecture:
    return service.en_lecture(await service.recuperer(session, workspace_id))


@router.get("/{workspace_id}/rapport")
async def rapport(workspace_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Le rapport de l'espace : sources, corrections, questions, score de confiance.

    Rien n'est demandé à un modèle : tout ce qui figure ici est déjà enregistré.
    La synthèse rédigée est un appel séparé, pour que le rapport reste consultable
    même quand le fournisseur est indisponible.
    """
    await service.recuperer(session, workspace_id)
    return await rapports.construire(session, workspace_id)


@router.get("/{workspace_id}/rapport/notebook")
async def notebook(workspace_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    """La session en notebook Python exécutable.

    C'est la contrepartie du pilier transparence : les outils sans code enferment
    leurs utilisateurs, on préfère leur rendre le code. Ce qui sort d'ici tourne
    sans la plateforme — y compris pour vérifier qu'elle n'a pas menti.
    """
    espace = await service.recuperer(session, workspace_id)
    donnees = await rapports.construire(session, workspace_id)
    carnet = carnets.exporter(donnees, donnees["corrections"])

    nom = (
        "".join(c if c.isalnum() or c in "-_" else "-" for c in espace.name).strip("-") or "analyse"
    )
    return Response(
        content=carnets.en_json(carnet),
        media_type="application/x-ipynb+json",
        headers={"Content-Disposition": f'attachment; filename="{nom}.ipynb"'},
    )
