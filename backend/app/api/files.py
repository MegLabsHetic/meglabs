"""Routes des fichiers. Couche fine : toute la logique vit dans les services."""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import ErreurUtilisateur
from app.schemas.fichier import DepotReponse, FichierLecture, PseudonymisationReponse
from app.services.file_service import FileService
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api", tags=["fichiers"])
service = FileService()
espaces = WorkspaceService()

TAILLE_LOT = 1024 * 1024


async def _lire_borne(fichier: UploadFile) -> bytes:
    """Lit le corps par lots en s'arretant des le depassement.

    La limite est verifiee pendant la lecture, pas apres : sinon un fichier de dix
    gigaoctets serait entierement charge en memoire avant d'etre refuse.
    """
    settings = get_settings()
    morceaux: list[bytes] = []
    total = 0
    while morceau := await fichier.read(TAILLE_LOT):
        total += len(morceau)
        if total > settings.max_file_size_bytes:
            raise ErreurUtilisateur(
                f"Ce fichier dépasse la limite de {settings.max_file_size_mb} Mo. "
                "Filtre-le ou découpe-le avant de le déposer."
            )
        morceaux.append(morceau)
    return b"".join(morceaux)


@router.post("/workspaces/{workspace_id}/files", response_model=DepotReponse, status_code=201)
async def deposer(
    workspace_id: str,
    fichier: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> DepotReponse:
    await espaces.recuperer(session, workspace_id)
    contenu = await _lire_borne(fichier)

    enregistre, profil, detections = await service.deposer(
        session, workspace_id, fichier.filename or "sans-nom", contenu
    )
    return DepotReponse(
        fichier=service.en_lecture(enregistre),
        profil=profil,
        donnees_personnelles=service.detections_en_lecture(detections),
    )


@router.get("/workspaces/{workspace_id}/files", response_model=list[FichierLecture])
async def lister(
    workspace_id: str, session: AsyncSession = Depends(get_session)
) -> list[FichierLecture]:
    await espaces.recuperer(session, workspace_id)
    return [service.en_lecture(f) for f in await service.lister(session, workspace_id)]


@router.get("/files/{file_id}", response_model=FichierLecture)
async def recuperer(file_id: str, session: AsyncSession = Depends(get_session)) -> FichierLecture:
    return service.en_lecture(await service.recuperer(session, file_id))


@router.get("/files/{file_id}/profile")
async def profil(file_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    fichier = await service.recuperer(session, file_id)
    return fichier.profile or {}


@router.post("/files/{file_id}/pseudonymise", response_model=PseudonymisationReponse)
async def pseudonymiser(
    file_id: str, session: AsyncSession = Depends(get_session)
) -> PseudonymisationReponse:
    fichier, colonnes, remplacees, profil = await service.pseudonymiser(session, file_id)
    return PseudonymisationReponse(
        fichier=service.en_lecture(fichier),
        colonnes_pseudonymisees=colonnes,
        valeurs_remplacees=remplacees,
        profil=profil,
    )
