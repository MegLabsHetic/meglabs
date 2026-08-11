"""Depot d'un fichier : validation, stockage, profilage, detection PII.

Le fichier arrive d'un utilisateur, donc rien de ce qu'il annonce n'est cru sur parole :
ni son extension, ni son type declare, ni son nom. Le nom d'origine n'est conserve que
pour l'affichage — le fichier est ecrit sous un identifiant aleatoire, ce qui rend une
traversee de chemin impossible par construction plutot que par filtrage.
"""

import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.data_agent import DataAgent
from app.core.config import Settings, get_settings
from app.core.errors import ErreurUtilisateur, RessourceIntrouvable
from app.models import DataFile, PiiMapping
from app.schemas.fichier import DetectionLecture, FichierLecture
from app.services.pii_service import Detection

EXTENSIONS = (".csv", ".xlsx", ".xls")

# Un fichier Excel est une archive ZIP, un .xls historique un conteneur OLE. Le CSV n'a
# pas de signature : il est valide en tentant reellement de le lire.
SIGNATURES = {
    ".xlsx": (b"PK\x03\x04",),
    ".xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
}

PII_ABSENTE = "aucune"
PII_DETECTEE = "detectee"
PII_MASQUEE = "masquee"


class FileService:
    """Fait entrer un fichier dans un espace de travail, en toute sécurité."""

    def __init__(self, agent: DataAgent | None = None, settings: Settings | None = None) -> None:
        self._agent = agent or DataAgent()
        self._settings_impose = settings

    @property
    def _settings(self) -> Settings:
        """Lue a chaque appel, jamais figee a la construction.

        Le router instancie ce service a l'import du module : capturer la configuration
        dans le constructeur reviendrait a la geler au demarrage du processus, et tout
        changement d'environnement serait ignore en silence.
        """
        return self._settings_impose or get_settings()

    # --- Depot --------------------------------------------------------------

    async def deposer(
        self, session: AsyncSession, workspace_id: str, nom_original: str, contenu: bytes
    ) -> tuple[DataFile, dict, list[Detection]]:
        """Valide, stocke, profile et analyse le fichier en une seule operation."""
        extension = self._valider(nom_original, contenu)
        chemin = self._stocker(extension, contenu)

        try:
            table = self._agent.charger(chemin)
        except Exception as erreur:  # noqa: BLE001 - le detail technique n'aide pas l'utilisateur
            chemin.unlink(missing_ok=True)
            raise ErreurUtilisateur(
                "Ce fichier n'a pas pu être lu. Vérifie qu'il s'agit bien d'un tableau "
                "avec une ligne d'en-têtes, puis réessaie."
            ) from erreur

        self._verifier_volume(table)
        profil = self._agent.profiler_table(table)
        detections = self._agent.detecter_pii(table)

        fichier = DataFile(
            workspace_id=workspace_id,
            name=nom_original,
            format=extension.lstrip("."),
            size_bytes=len(contenu),
            path=str(chemin),
            profile=profil,
            quality_score=profil["score_qualite"],
            pii_status=PII_DETECTEE if detections else PII_ABSENTE,
        )
        session.add(fichier)
        await session.commit()
        return fichier, profil, detections

    def _valider(self, nom_original: str, contenu: bytes) -> str:
        if not contenu:
            raise ErreurUtilisateur(
                "Ce fichier est vide. Choisis un fichier contenant des données."
            )

        extension = Path(nom_original).suffix.lower()
        if extension not in EXTENSIONS:
            raise ErreurUtilisateur(
                f"Le format « {extension or 'inconnu'} » n'est pas pris en charge. "
                f"Formats acceptés : {', '.join(EXTENSIONS)}."
            )

        attendues = SIGNATURES.get(extension)
        if attendues and not any(contenu.startswith(signature) for signature in attendues):
            raise ErreurUtilisateur(
                f"Ce fichier porte l'extension {extension} mais son contenu n'en est pas un. "
                "Réenregistre-le depuis ton tableur, puis réessaie."
            )
        return extension

    def _verifier_volume(self, table: pd.DataFrame) -> None:
        if len(table) > self._settings.max_rows:
            raise ErreurUtilisateur(
                f"Ce fichier contient {len(table):,} lignes, au-delà de la limite de "
                f"{self._settings.max_rows:,}. Filtre-le avant de le déposer.".replace(",", " ")
            )
        if table.empty or not len(table.columns):
            raise ErreurUtilisateur(
                "Ce fichier ne contient aucune donnée exploitable. "
                "Vérifie qu'il a bien une ligne d'en-têtes et au moins une ligne de données."
            )

    def _stocker(self, extension: str, contenu: bytes) -> Path:
        """Ecrit sous un nom aleatoire : le nom fourni n'atteint jamais le disque."""
        dossier = Path(self._settings.storage_dir)
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / f"{uuid.uuid4()}{extension}"
        chemin.write_bytes(contenu)
        return chemin

    # --- Lecture ------------------------------------------------------------

    async def recuperer(self, session: AsyncSession, file_id: str) -> DataFile:
        fichier = await session.get(DataFile, file_id)
        if fichier is None:
            raise RessourceIntrouvable("Ce fichier n'existe pas ou a été supprimé.")
        return fichier

    async def lister(self, session: AsyncSession, workspace_id: str) -> list[DataFile]:
        resultat = await session.execute(
            select(DataFile)
            .where(DataFile.workspace_id == workspace_id)
            .order_by(DataFile.created_at.desc())
        )
        return list(resultat.scalars())

    # --- Pseudonymisation ---------------------------------------------------

    async def pseudonymiser(
        self, session: AsyncSession, file_id: str
    ) -> tuple[DataFile, list[str], int, dict]:
        """Remplace les valeurs sensibles sur le disque, et conserve les empreintes."""
        fichier = await self.recuperer(session, file_id)
        if fichier.pii_status == PII_MASQUEE:
            raise ErreurUtilisateur("Ce fichier a déjà été pseudonymisé.")

        table = self._agent.charger(fichier.path)
        detections = self._agent.detecter_pii(table)
        if not detections:
            raise ErreurUtilisateur(
                "Aucune donnée personnelle n'a été détectée dans ce fichier : "
                "il n'y a rien à pseudonymiser."
            )

        masquee, pseudonymes = self._agent.pseudonymiser(table, detections)
        self._reecrire(Path(fichier.path), masquee)

        session.add_all(
            PiiMapping(
                file_id=fichier.id,
                column_name=pseudonyme.colonne,
                original_hash=pseudonyme.empreinte,
                token=pseudonyme.jeton,
            )
            for pseudonyme in pseudonymes
        )

        profil = self._agent.profiler_table(masquee)
        fichier.profile = profil
        fichier.quality_score = profil["score_qualite"]
        fichier.pii_status = PII_MASQUEE
        await session.commit()

        return fichier, [d.colonne for d in detections], len(pseudonymes), profil

    def _reecrire(self, chemin: Path, table: pd.DataFrame) -> None:
        """Le fichier pseudonymise remplace l'original : les valeurs d'origine disparaissent."""
        if chemin.suffix.lower() == ".csv":
            table.to_csv(chemin, index=False, encoding="utf-8")
        else:
            table.to_excel(chemin, index=False)

    # --- Conversions --------------------------------------------------------

    def en_lecture(self, fichier: DataFile) -> FichierLecture:
        return FichierLecture(
            id=fichier.id,
            nom=fichier.name,
            format=fichier.format,
            taille_octets=fichier.size_bytes,
            statut_pii=fichier.pii_status,
            score_qualite=fichier.quality_score,
            cree_le=fichier.created_at,
        )

    def detections_en_lecture(self, detections: list[Detection]) -> list[DetectionLecture]:
        return [
            DetectionLecture(
                colonne=detection.colonne,
                type_pii=detection.type_pii,
                confiance=detection.confiance,
                exemple_masque=detection.exemple_masque,
            )
            for detection in detections
        ]
