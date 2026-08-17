"""Point de passage unique vers les modeles de langage.

Tout ce qui doit etre vrai de CHAQUE appel vit ici : le choix du modele, la validation
de la sortie, la tentative de rattrapage, le comptage des jetons et du cout. Un agent
qui appellerait un fournisseur directement echapperait a tout cela — et le compteur de
cout montre au jury deviendrait faux.
"""

import time
from dataclasses import dataclass, replace
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import (
    Provider,
    Settings,
    Task,
    cost_in_cents,
    get_settings,
    model_for,
    savings_in_cents,
)
from app.core.errors import ErreurUtilisateur
from app.core.providers.base import Fournisseur, ReponseBrute, Requete

Sortie = TypeVar("Sortie", bound=BaseModel)

MESSAGE_ECHEC = (
    "L'assistant n'a pas réussi à formuler une réponse exploitable. "
    "Reformule ta question en une phrase, puis réessaie."
)


@dataclass(frozen=True)
class Trace:
    """Ce qu'a coute un appel. Alimente le compteur de cout et le journal."""

    agent: str
    fournisseur: str
    modele: str
    tokens_entree: int
    tokens_sortie: int
    tokens_caches: int
    cout_centimes: float
    economie_centimes: float
    duree_ms: int
    tentatives: int


@dataclass(frozen=True)
class Resultat[T]:
    valeur: T
    trace: Trace


class LlmClient:
    """Appelle le bon modele, valide sa sortie, et compte ce que ca coute."""

    def __init__(
        self,
        fournisseur: Fournisseur | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._fournisseur_impose = fournisseur
        self._settings_impose = settings

    # --- API publique -------------------------------------------------------

    async def repondre_texte(
        self,
        tache: Task,
        instruction: str,
        question: str,
        agent: str,
        effort: str | None = None,
        max_tokens: int = 2048,
    ) -> Resultat[str]:
        requete = self._requete(tache, instruction, question, effort, max_tokens)
        brute, duree, tentatives = await self._appeler(requete)
        return Resultat(brute.texte, self._tracer(agent, requete, brute, duree, tentatives))

    async def repondre_structure(
        self,
        tache: Task,
        instruction: str,
        question: str,
        schema: type[Sortie],
        agent: str,
        effort: str | None = None,
        max_tokens: int = 2048,
    ) -> Resultat[Sortie]:
        """Sortie validee par Pydantic. Jamais de JSON accepte sans verification.

        Le mode « JSON libre » d'un fournisseur ne garantit que la syntaxe : mesure sur
        Groq, le modele produit du JSON parfaitement valide avec ses propres noms de
        champs. C'est la validation qui tient le contrat, pas l'analyse syntaxique.
        """
        requete = self._requete(tache, instruction, question, effort, max_tokens, schema=schema)
        brute, duree, tentatives = await self._appeler(requete, schema)
        valeur = self._valider(brute.texte, schema)
        if valeur is None:
            raise ErreurUtilisateur(MESSAGE_ECHEC, code_http=502)
        return Resultat(valeur, self._tracer(agent, requete, brute, duree, tentatives))

    # --- Construction de la requete -----------------------------------------

    def _requete(
        self,
        tache: Task,
        instruction: str,
        question: str,
        effort: str | None,
        max_tokens: int,
        schema: type[BaseModel] | None = None,
    ) -> Requete:
        return Requete(
            modele=model_for(self._settings.llm_provider, tache),
            instruction=instruction,
            question=question,
            max_tokens=max_tokens,
            schema=self._schema_json(schema),
            nom_schema=schema.__name__.lower() if schema else "reponse",
            effort=effort,
        )

    def _schema_json(self, schema: type[BaseModel] | None) -> dict | None:
        """Le schema Pydantic devient le contrat envoye au fournisseur."""
        if schema is None:
            return None
        brut = schema.model_json_schema()
        brut["additionalProperties"] = False
        return brut

    # --- Appel et rattrapage ------------------------------------------------

    async def _appeler(
        self, requete: Requete, schema: type[BaseModel] | None = None
    ) -> tuple[ReponseBrute, int, int]:
        """Un appel, puis une seule seconde chance avec le probleme explicite."""
        debut = time.perf_counter()
        brute = await self._fournisseur.repondre(requete)

        if self._exploitable(brute, schema):
            return brute, self._ms(debut), 1

        brute = await self._fournisseur.repondre(self._reformuler(requete, brute, schema))
        return brute, self._ms(debut), 2

    def _exploitable(self, brute: ReponseBrute, schema: type[BaseModel] | None) -> bool:
        if brute.tronquee:
            return False
        return schema is None or self._valider(brute.texte, schema) is not None

    def _reformuler(
        self, requete: Requete, brute: ReponseBrute, schema: type[BaseModel] | None
    ) -> Requete:
        """Reinjecte le probleme rencontre : sans le dire, la seconde tentative echoue pareil."""
        if brute.tronquee:
            # Le budget est double : reprocher la longueur sans donner de place ne
            # servirait a rien.
            return replace(
                requete,
                max_tokens=requete.max_tokens * 2,
                question=(
                    f"{requete.question}\n\nTa réponse précédente a été coupée avant "
                    "la fin. Réponds de façon plus concise."
                ),
            )

        detail = self._erreur_de_validation(brute.texte, schema)
        return replace(
            requete,
            question=(
                f"{requete.question}\n\nTa réponse précédente ne respectait pas le "
                f"format attendu. Erreur : {detail}. Corrige et renvoie uniquement le "
                "format demandé."
            ),
        )

    # --- Validation ---------------------------------------------------------

    def _valider(self, texte: str, schema: type[Sortie]) -> Sortie | None:
        try:
            return schema.model_validate_json(texte)
        except (ValidationError, ValueError):
            return None

    def _erreur_de_validation(self, texte: str, schema: type[BaseModel] | None) -> str:
        if schema is None:
            return "format inattendu"
        try:
            schema.model_validate_json(texte)
        except ValidationError as erreur:
            premiere = erreur.errors()[0]
            champ = ".".join(str(p) for p in premiere["loc"]) or "racine"
            return f"champ « {champ} » : {premiere['msg']}"
        except ValueError:
            return "la réponse n'est pas du JSON"
        return "format inattendu"

    # --- Comptage -----------------------------------------------------------

    def _tracer(
        self, agent: str, requete: Requete, brute: ReponseBrute, duree_ms: int, tentatives: int
    ) -> Trace:
        return Trace(
            agent=agent,
            fournisseur=self._fournisseur.nom,
            modele=requete.modele,
            tokens_entree=brute.tokens_entree,
            tokens_sortie=brute.tokens_sortie,
            tokens_caches=brute.tokens_caches,
            cout_centimes=round(
                cost_in_cents(
                    requete.modele, brute.tokens_entree, brute.tokens_sortie, brute.tokens_caches
                ),
                6,
            ),
            economie_centimes=round(savings_in_cents(requete.modele, brute.tokens_caches), 6),
            duree_ms=duree_ms,
            tentatives=tentatives,
        )

    def _ms(self, debut: float) -> int:
        return int((time.perf_counter() - debut) * 1000)

    # --- Configuration paresseuse -------------------------------------------

    @property
    def _settings(self) -> Settings:
        """Relue a chaque appel : la figer au constructeur la gele au demarrage."""
        return self._settings_impose or get_settings()

    @property
    def _fournisseur(self) -> Fournisseur:
        if self._fournisseur_impose is not None:
            return self._fournisseur_impose
        return construire_fournisseur(self._settings)


def construire_fournisseur(settings: Settings) -> Fournisseur:
    """Instancie le fournisseur configure. Importe a la demande : un SDK inutilise
    n'a pas besoin d'etre charge."""
    fournisseur = settings.llm_provider
    cle = settings.api_key_for(fournisseur)

    if fournisseur is Provider.GROQ:
        from app.core.providers.groq_provider import FournisseurGroq

        return FournisseurGroq(cle)
    if fournisseur is Provider.OPENAI:
        from app.core.providers.openai_provider import FournisseurOpenAI

        return FournisseurOpenAI(cle)
    from app.core.providers.anthropic_provider import FournisseurAnthropic

    return FournisseurAnthropic(cle)

