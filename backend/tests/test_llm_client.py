"""La couche LLM se teste sans clé d'API : le fournisseur est simulé."""

from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel

from app.core.config import Provider, Settings, Task
from app.core.errors import ErreurUtilisateur
from app.core.llm_client import LlmClient
from app.core.providers.base import ReponseBrute, Requete


class Analyse(BaseModel):
    intention: str
    sql: str | None
    besoin_graphique: bool


@dataclass
class FournisseurSimule:
    """Rend les réponses préparées, dans l'ordre, et garde trace des requêtes reçues."""

    reponses: list[ReponseBrute]
    nom: str = "simule"
    recues: list[Requete] = field(default_factory=list)

    async def repondre(self, requete: Requete) -> ReponseBrute:
        self.recues.append(requete)
        return self.reponses[min(len(self.recues) - 1, len(self.reponses) - 1)]


def brute(texte: str, **extra) -> ReponseBrute:
    valeurs = {"tokens_entree": 1000, "tokens_sortie": 200}
    valeurs.update(extra)
    return ReponseBrute(texte=texte, **valeurs)


VALIDE = '{"intention":"question_donnees","sql":"SELECT 1","besoin_graphique":false}'


def client(fournisseur: FournisseurSimule, provider: Provider = Provider.GROQ) -> LlmClient:
    return LlmClient(fournisseur=fournisseur, settings=Settings(llm_provider=provider))


# --- Le routage -------------------------------------------------------------


@pytest.mark.parametrize(
    ("provider", "tache", "attendu"),
    [
        (Provider.GROQ, Task.CLASSIFICATION, "openai/gpt-oss-20b"),
        (Provider.GROQ, Task.SQL_GENERATION, "openai/gpt-oss-120b"),
        (Provider.ANTHROPIC, Task.CLASSIFICATION, "claude-haiku-4-5"),
        (Provider.ANTHROPIC, Task.REPORT, "claude-sonnet-5"),
    ],
)
async def test_the_task_picks_the_model(provider: Provider, tache: Task, attendu: str):
    """Un agent ne choisit jamais son modèle : c'est la tâche qui le détermine."""
    fournisseur = FournisseurSimule([brute("bonjour")])

    await client(fournisseur, provider).repondre_texte(tache, "instruction", "question", "test")

    assert fournisseur.recues[0].modele == attendu


# --- La sortie structurée ---------------------------------------------------


async def test_a_valid_payload_is_returned_as_a_validated_model():
    fournisseur = FournisseurSimule([brute(VALIDE)])

    resultat = await client(fournisseur).repondre_structure(
        Task.SQL_GENERATION, "instruction", "question", Analyse, "test"
    )

    assert isinstance(resultat.valeur, Analyse)
    assert resultat.valeur.sql == "SELECT 1"
    assert resultat.trace.tentatives == 1


async def test_the_pydantic_schema_is_sent_as_the_contract():
    fournisseur = FournisseurSimule([brute(VALIDE)])

    await client(fournisseur).repondre_structure(
        Task.SQL_GENERATION, "instruction", "question", Analyse, "test"
    )

    schema = fournisseur.recues[0].schema
    assert schema is not None
    assert set(schema["properties"]) == {"intention", "sql", "besoin_graphique"}
    # Sans cette clé, un fournisseur strict accepte des champs en trop.
    assert schema["additionalProperties"] is False


async def test_syntactically_valid_json_with_wrong_keys_is_refused():
    """Le piège mesuré sur Groq : du JSON valide qui ne respecte pas le contrat.

    Le mode « JSON libre » d'un fournisseur ne garantit que la syntaxe. Le modèle
    invente ses propres noms de champs (`sql_query` au lieu de `sql`) et une analyse
    syntaxique naïve « réussit » — c'est la validation qui doit trancher.
    """
    invalide = '{"sql_query":"SELECT 1"}'
    fournisseur = FournisseurSimule([brute(invalide), brute(invalide)])

    with pytest.raises(ErreurUtilisateur):
        await client(fournisseur).repondre_structure(
            Task.SQL_GENERATION, "instruction", "question", Analyse, "test"
        )


async def test_a_malformed_payload_gets_exactly_one_second_chance():
    fournisseur = FournisseurSimule([brute("pas du json"), brute(VALIDE)])

    resultat = await client(fournisseur).repondre_structure(
        Task.SQL_GENERATION, "instruction", "question", Analyse, "test"
    )

    assert resultat.valeur.sql == "SELECT 1"
    assert resultat.trace.tentatives == 2
    assert len(fournisseur.recues) == 2


async def test_the_second_attempt_is_told_what_went_wrong():
    """Sans lui dire, la seconde tentative échoue exactement de la même façon."""
    fournisseur = FournisseurSimule([brute('{"intention":"x"}'), brute(VALIDE)])

    await client(fournisseur).repondre_structure(
        Task.SQL_GENERATION, "instruction", "question", Analyse, "test"
    )

    relance = fournisseur.recues[1].question
    assert "ne respectait pas le format attendu" in relance
    assert "sql" in relance


async def test_a_persistent_failure_becomes_an_actionable_french_error():
    fournisseur = FournisseurSimule([brute("non"), brute("toujours non")])

    with pytest.raises(ErreurUtilisateur) as capture:
        await client(fournisseur).repondre_structure(
            Task.SQL_GENERATION, "instruction", "question", Analyse, "test"
        )

    assert "Reformule ta question" in capture.value.message


# --- La troncature silencieuse ----------------------------------------------


async def test_an_empty_answer_counts_as_a_failure_not_a_result():
    """Mesuré sur Groq : un budget trop court consomme tout le raisonnement et laisse
    le contenu vide, sans lever d'erreur. On facturerait un appel qui ne rend rien."""
    fournisseur = FournisseurSimule([brute("", raison_arret="length"), brute("voici")])

    resultat = await client(fournisseur).repondre_texte(
        Task.INTERPRETATION, "instruction", "question", "test"
    )

    assert resultat.valeur == "voici"
    assert resultat.trace.tentatives == 2


async def test_a_truncated_answer_is_retried_with_more_room():
    fournisseur = FournisseurSimule([brute("début de", raison_arret="length"), brute("complet")])

    await client(fournisseur).repondre_texte(
        Task.INTERPRETATION, "instruction", "question", "test", max_tokens=500
    )

    assert fournisseur.recues[1].max_tokens == 1000
    assert "coupée avant la fin" in fournisseur.recues[1].question


# --- Le comptage ------------------------------------------------------------


async def test_every_call_is_costed():
    fournisseur = FournisseurSimule([brute(VALIDE, tokens_entree=1_000_000, tokens_sortie=0)])

    resultat = await client(fournisseur).repondre_structure(
        Task.SQL_GENERATION, "instruction", "question", Analyse, "test"
    )

    # openai/gpt-oss-120b : 0,15 $ par million de jetons en entrée, soit 15 centimes.
    assert resultat.trace.cout_centimes == pytest.approx(15.0)
    assert resultat.trace.modele == "openai/gpt-oss-120b"
    assert resultat.trace.fournisseur == "simule"


async def test_cached_tokens_cost_a_tenth_and_the_saving_is_reported():
    """C'est le chiffre du pilier frugalité : il doit venir d'une mesure, pas d'une estimation."""
    fournisseur = FournisseurSimule(
        [brute(VALIDE, tokens_entree=1_000_000, tokens_sortie=0, tokens_caches=1_000_000)]
    )

    resultat = await client(fournisseur).repondre_structure(
        Task.SQL_GENERATION, "instruction", "question", Analyse, "test"
    )

    assert resultat.trace.cout_centimes == pytest.approx(1.5)
    assert resultat.trace.economie_centimes == pytest.approx(13.5)


async def test_the_reasoning_effort_is_passed_through_when_asked():
    """Mesuré sur Groq : « low » divise les jetons de sortie par près de 4."""
    fournisseur = FournisseurSimule([brute("ok")])

    await client(fournisseur).repondre_texte(
        Task.CLASSIFICATION, "instruction", "question", "test", effort="low"
    )

    assert fournisseur.recues[0].effort == "low"
