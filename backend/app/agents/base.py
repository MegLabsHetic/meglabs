"""Classe mere des agents qui parlent a un modele de langage.

Elle porte tout ce qui doit etre vrai de CHAQUE agent : annoncer ce qu'il fait,
mesurer combien de temps ca prend, accumuler ce que ca coute. Un agent qui appellerait
`LlmClient` directement n'apparaitrait pas a l'ecran et ne serait pas compte.

L'Agent Data ne descend pas d'ici : il ne fait aucun appel LLM, donc il n'a ni trace
ni cout a declarer.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import BaseModel

from app.core.config import Task
from app.core.events import (
    DEMARRE,
    TERMINE,
    TRAVAILLE,
    FluxEvenements,
    evenement_agent,
)
from app.core.llm_client import LlmClient, Trace


class BaseAgent:
    """Un agent : un nom affichable, un flux ou s'annoncer, un client LLM."""

    nom = "agent"
    libelle = "Agent"

    def __init__(
        self,
        client: LlmClient | None = None,
        flux: FluxEvenements | None = None,
    ) -> None:
        self._client = client or LlmClient()
        self._flux = flux
        self.traces: list[Trace] = []

    # --- Ce que le jury voit ------------------------------------------------

    @asynccontextmanager
    async def etape(self, detail: str) -> AsyncIterator[None]:
        """Encadre une unite de travail : annonce, mesure, signale la fin.

        La duree est emise a la fin meme en cas d'echec : une etape qui s'allume sans
        jamais s'eteindre laisse l'interface croire que le travail continue.
        """
        debut = time.perf_counter()
        await self._annoncer(DEMARRE, detail)
        try:
            yield
        finally:
            duree = int((time.perf_counter() - debut) * 1000)
            await self._annoncer(TERMINE, detail, duree)

    async def progresser(self, detail: str) -> None:
        """Signale une avancee a l'interieur d'une etape."""
        await self._annoncer(TRAVAILLE, detail)

    async def _annoncer(self, etat: str, detail: str, duree_ms: int | None = None) -> None:
        if self._flux is None:
            return
        await self._flux.publier(evenement_agent(self.libelle, etat, detail, duree_ms))

    # --- Ce que ca coute ----------------------------------------------------

    @property
    def cout_centimes(self) -> float:
        return round(sum(trace.cout_centimes for trace in self.traces), 6)

    @property
    def economie_centimes(self) -> float:
        return round(sum(trace.economie_centimes for trace in self.traces), 6)

    @property
    def nb_appels(self) -> int:
        return len(self.traces)

    def trace_json(self) -> list[dict]:
        """Trace serialisable, rangee dans le message et affichee par le compteur."""
        return [
            {
                "agent": trace.agent,
                "fournisseur": trace.fournisseur,
                "modele": trace.modele,
                "tokens_entree": trace.tokens_entree,
                "tokens_sortie": trace.tokens_sortie,
                "tokens_caches": trace.tokens_caches,
                "cout_centimes": trace.cout_centimes,
                "economie_centimes": trace.economie_centimes,
                "duree_ms": trace.duree_ms,
                "tentatives": trace.tentatives,
            }
            for trace in self.traces
        ]

    # --- Appels au modele ---------------------------------------------------

    async def demander[T: BaseModel](
        self,
        tache: Task,
        instruction: str,
        question: str,
        schema: type[T],
        effort: str | None = None,
        max_tokens: int = 2048,
    ) -> T:
        """Appel a sortie structuree. La trace est conservee automatiquement."""
        resultat = await self._client.repondre_structure(
            tache,
            instruction,
            question,
            schema,
            agent=self.nom,
            effort=effort,
            max_tokens=max_tokens,
        )
        self.traces.append(resultat.trace)
        return resultat.valeur

    async def rediger(
        self,
        tache: Task,
        instruction: str,
        question: str,
        effort: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Appel en texte libre, pour ce qui est destine a etre lu tel quel."""
        resultat = await self._client.repondre_texte(
            tache, instruction, question, agent=self.nom, effort=effort, max_tokens=max_tokens
        )
        self.traces.append(resultat.trace)
        return resultat.valeur
