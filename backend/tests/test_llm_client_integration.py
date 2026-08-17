"""Appels réels au fournisseur configuré. Exclus de la CI, qui n'a pas de clé.

pytest -m integration
"""

import pytest
from pydantic import BaseModel

from app.core.config import Provider, Task, get_settings
from app.core.llm_client import LlmClient

pytestmark = pytest.mark.integration


class AnalyseQuestion(BaseModel):
    intention: str
    sql: str | None
    besoin_graphique: bool


SCHEMA_TABLE = (
    "Table collaborateurs(service TEXT, salaire_annuel INTEGER, poste TEXT). "
    "Réponds en JSON. `intention` vaut « question_donnees », « salutation » ou "
    "« hors_sujet ». `sql` contient la requête SELECT, ou null."
)


def fournisseur_configure() -> Provider:
    settings = get_settings()
    try:
        settings.api_key_for(settings.llm_provider)
    except RuntimeError:
        pytest.skip(f"Aucune clé pour {settings.llm_provider.value}")
    return settings.llm_provider


async def test_a_real_provider_returns_a_validated_payload():
    fournisseur_configure()

    resultat = await LlmClient().repondre_structure(
        Task.SQL_GENERATION,
        SCHEMA_TABLE,
        "Quel est le salaire moyen par service ?",
        AnalyseQuestion,
        agent="analyste",
        max_tokens=1500,
    )

    assert resultat.valeur.intention == "question_donnees"
    assert resultat.valeur.sql is not None
    assert "salaire_annuel" in resultat.valeur.sql
    assert resultat.trace.tokens_sortie > 0
    assert resultat.trace.cout_centimes > 0


async def test_a_real_provider_answers_in_plain_text():
    fournisseur_configure()

    resultat = await LlmClient().repondre_texte(
        Task.INTERPRETATION,
        "Tu réponds en une seule phrase, en français, sans jargon.",
        "Le salaire moyen du service Data est de 46 200 euros, contre 42 000 en moyenne "
        "générale. Interprète cet écart.",
        agent="redacteur",
        max_tokens=1500,
    )

    assert len(resultat.valeur) > 20
    assert resultat.trace.duree_ms > 0


async def test_low_effort_costs_less_for_the_same_answer():
    """Le chiffre du pilier frugalité, mesuré et non estimé."""
    if fournisseur_configure() is not Provider.GROQ:
        pytest.skip("L'effort de raisonnement est propre à Groq pour l'instant")

    commun = ("Tu réponds exactement par le mot OK.", "Dis OK.", "test")

    defaut = await LlmClient().repondre_texte(Task.CLASSIFICATION, *commun, max_tokens=1500)
    bas = await LlmClient().repondre_texte(
        Task.CLASSIFICATION, *commun, effort="low", max_tokens=1500
    )

    assert bas.trace.tokens_sortie < defaut.trace.tokens_sortie
