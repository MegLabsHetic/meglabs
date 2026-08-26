"""Routes des sources externes. Couche fine : la logique vit dans les services.

C'est la deuxième porte d'entrée des données. Jusqu'ici la seule façon de faire
entrer une table était de déposer un fichier à la main.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.debit import LIMITE_DEPOT, limiteur
from app.services.file_service import FileService
from app.services.source_service import SourceService
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api", tags=["sources"])
sources = SourceService()
fichiers = FileService()
espaces = WorkspaceService()


class Connexion(BaseModel):
    """Ce qu'il faut pour joindre une base. Le mot de passe n'en ressort jamais."""

    nom: str = Field(default="", max_length=255)
    hote: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    base: str = Field(min_length=1, max_length=255)
    utilisateur: str = Field(min_length=1, max_length=255)
    mot_de_passe: str = Field(default="", max_length=512)
    schema_cible: str = Field(default="public", max_length=63)

    def en_config(self) -> dict:
        return {
            "hote": self.hote,
            "port": self.port,
            "base": self.base,
            "utilisateur": self.utilisateur,
            "mot_de_passe": self.mot_de_passe,
            "schema": self.schema_cible,
        }


class ChoixTables(BaseModel):
    tables: list[str] = Field(min_length=1, max_length=20)


@router.get("/connecteurs")
async def connecteurs() -> list[dict]:
    """Le catalogue des sources branchables.

    Écrit à la main plutôt que découvert : il en compte un aujourd'hui, et une
    liste honnête vaut mieux qu'un catalogue qui promet ce qui n'existe pas.
    """
    return [
        {
            "type": "postgresql",
            "libelle": "PostgreSQL",
            "resume": "Une base PostgreSQL joignable depuis Internet.",
            "disponible": True,
        }
    ]


@router.post("/workspaces/{workspace_id}/sources", status_code=201)
@limiteur.limit(LIMITE_DEPOT)
async def connecter(
    workspace_id: str,
    connexion: Connexion,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Teste la connexion, puis enregistre la source si elle répond."""
    await espaces.recuperer(session, workspace_id)
    source = await sources.enregistrer(session, workspace_id, connexion.nom, connexion.en_config())
    return sources.en_lecture(source)


@router.get("/workspaces/{workspace_id}/sources")
async def lister(workspace_id: str, session: AsyncSession = Depends(get_session)) -> list[dict]:
    await espaces.recuperer(session, workspace_id)
    return [sources.en_lecture(s) for s in await sources.lister(session, workspace_id)]


@router.get("/sources/{source_id}/tables")
async def tables(source_id: str, session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Les tables lisibles, avec une estimation de leur taille."""
    return [
        {"schema": t.schema, "nom": t.nom, "lignes": t.lignes}
        for t in await sources.tables(session, source_id)
    ]


@router.post("/sources/{source_id}/synchroniser")
@limiteur.limit(LIMITE_DEPOT)
async def synchroniser(
    source_id: str,
    choix: ChoixTables,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Copie les tables choisies dans l'espace, comme autant de fichiers."""
    deposes = await sources.synchroniser(session, source_id, choix.tables, fichiers)
    return {"fichiers": deposes}
