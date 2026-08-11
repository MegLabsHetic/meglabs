"""Agent Data : tout ce qui se calcule, sans jamais appeler un LLM.

Profilage, statistiques, nettoyage, detection de donnees personnelles et d'insights
passeront tous par ici. Le LLM n'intervient qu'en aval, pour FORMULER un resultat deja
calcule — jamais pour le produire. C'est l'argument cout et latence du projet : un
profilage de cinquante colonnes coute zero centime et quelques millisecondes.
"""

from pathlib import Path

import pandas as pd

from app.services.file_loader import FileLoader
from app.services.pii_service import Detection, PiiService, Pseudonyme
from app.services.profiling_service import ProfilingService


class DataAgent:
    """Compose le chargement, le profilage et la protection des donnees personnelles."""

    def __init__(
        self,
        loader: FileLoader | None = None,
        profiler: ProfilingService | None = None,
        pii: PiiService | None = None,
    ) -> None:
        self._loader = loader or FileLoader()
        self._profiler = profiler or ProfilingService()
        self._pii = pii or PiiService()

    def charger(self, chemin: Path) -> pd.DataFrame:
        return self._loader.charger(chemin)

    def profiler(self, chemin: Path) -> dict:
        """Charge le fichier et retourne son profil complet."""
        return self._profiler.profiler(self.charger(chemin))

    def llm_context(self, profil: dict) -> dict:
        """Representation compressee d'un profil, seule forme transmise au LLM."""
        return self._profiler.llm_context(profil)

    def detecter_pii(self, table: pd.DataFrame) -> list[Detection]:
        """Colonnes portant des donnees personnelles. Aucun appel LLM."""
        return self._pii.detecter(table)

    def pseudonymiser(
        self, table: pd.DataFrame, detections: list[Detection]
    ) -> tuple[pd.DataFrame, list[Pseudonyme]]:
        """Remplace les valeurs sensibles par des jetons stables."""
        return self._pii.pseudonymiser(table, detections)
