"""Routes des espaces de travail. Couche fine : toute la logique vit dans les services."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.workspace import WorkspaceCreation, WorkspaceLecture
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api/workspaces", tags=["espaces de travail"])
service = WorkspaceService()


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
