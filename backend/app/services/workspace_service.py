"""Espaces de travail : creation, lecture, verification d'existence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import RessourceIntrouvable
from app.models import Workspace
from app.schemas.workspace import WorkspaceLecture


class WorkspaceService:
    """Seule source de verite sur les espaces de travail."""

    async def creer(self, session: AsyncSession, nom: str) -> WorkspaceLecture:
        workspace = Workspace(name=nom.strip())
        session.add(workspace)
        await session.commit()
        return self.en_lecture(workspace)

    async def lister(self, session: AsyncSession) -> list[WorkspaceLecture]:
        resultat = await session.execute(select(Workspace).order_by(Workspace.created_at.desc()))
        return [self.en_lecture(workspace) for workspace in resultat.scalars()]

    async def recuperer(self, session: AsyncSession, workspace_id: str) -> Workspace:
        """Retourne l'espace ou leve une erreur affichable telle quelle."""
        workspace = await session.get(Workspace, workspace_id)
        if workspace is None:
            raise RessourceIntrouvable(
                "Cet espace de travail n'existe pas ou a été supprimé. "
                "Reviens à l'accueil pour en choisir un autre."
            )
        return workspace

    def en_lecture(self, workspace: Workspace) -> WorkspaceLecture:
        return WorkspaceLecture(id=workspace.id, nom=workspace.name, cree_le=workspace.created_at)
