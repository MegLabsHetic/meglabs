"""Routes des fichiers. Couche fine : toute la logique vit dans les services."""

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.debit import LIMITE_DEPOT, limiteur
from app.core.errors import ErreurUtilisateur
from app.schemas.fichier import (
    DepotReponse,
    DetectionLecture,
    FichierLecture,
    PseudonymisationReponse,
)
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
@limiteur.limit(LIMITE_DEPOT)
async def deposer(
    workspace_id: str,
    request: Request,
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


@router.get("/files/{file_id}/pii", response_model=list[DetectionLecture])
async def donnees_personnelles(
    file_id: str, session: AsyncSession = Depends(get_session)
) -> list[DetectionLecture]:
    """Colonnes sensibles d'un fichier deja depose.

    Sans cette route, l'interface perdrait la banniere au premier rechargement : les
    detections n'etaient rendues qu'au moment du depot.
    """
    return service.detections_en_lecture(await service.detecter_pii(session, file_id))


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


@router.get("/files/{file_id}/nettoyage")
async def proposer_nettoyage(
    file_id: str, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    """Les corrections que les défauts détectés justifient, avec leur impact.

    Aucun appel à un modèle : les défauts sont dans le profil, qui les a comptés.
    """
    return await service.proposer_nettoyage(session, file_id)


class ChoixNettoyage(BaseModel):
    # Les types plutôt que des identifiants : une proposition est recalculée à
    # chaque lecture, donc un identifiant n'y survivrait pas.
    types: list[str] = Field(min_length=1)


@router.post("/files/{file_id}/nettoyage", response_model=DepotReponse)
async def appliquer_nettoyage(
    file_id: str,
    choix: ChoixNettoyage,
    session: AsyncSession = Depends(get_session),
) -> DepotReponse:
    """Applique les corrections choisies et rend le nouveau profil."""
    fichier, profil = await service.appliquer_nettoyage(session, file_id, choix.types)
    detections = await service.detecter_pii(session, file_id)
    return DepotReponse(
        fichier=service.en_lecture(fichier),
        profil=profil,
        donnees_personnelles=service.detections_en_lecture(detections),
    )
