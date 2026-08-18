"""Ce que tout agent doit faire, quel que soit son métier."""

import pytest
from pydantic import BaseModel

from app.agents.base import BaseAgent
from app.core.config import Provider, Settings, Task
from app.core.events import FluxEvenements
from app.core.llm_client import LlmClient
from app.core.providers.base import ReponseBrute, Requete


class Reponse(BaseModel):
    valeur: str


class FournisseurSimule:
    nom = "simule"

    def __init__(self, texte: str, **usage) -> None:
        self._reponse = ReponseBrute(
            texte=texte,
            tokens_entree=usage.get("entree", 1000),
            tokens_sortie=usage.get("sortie", 200),
            tokens_caches=usage.get("caches", 0),
        )

    async def repondre(self, requete: Requete) -> ReponseBrute:
        return self._reponse


def agent(texte: str = '{"valeur":"ok"}', flux: FluxEvenements | None = None, **usage) -> BaseAgent:
    client = LlmClient(
        fournisseur=FournisseurSimule(texte, **usage),
        settings=Settings(llm_provider=Provider.GROQ),
    )
    construit = BaseAgent(client=client, flux=flux)
    construit.nom, construit.libelle = "analyste", "Analyste"
    return construit


async def evenements(flux: FluxEvenements) -> list[dict]:
    await flux.cloturer()
    return [evenement.donnees async for evenement in flux]


# --- Ce que le jury voit ----------------------------------------------------


async def test_a_step_announces_its_start_and_its_end():
    flux = FluxEvenements()

    async with agent(flux=flux).etape("génère le SQL"):
        pass

    trace = await evenements(flux)
    assert [e["etat"] for e in trace] == ["started", "done"]
    assert all(e["detail"] == "génère le SQL" for e in trace)
    assert all(e["agent"] == "Analyste" for e in trace)


async def test_a_step_reports_how_long_it_took():
    flux = FluxEvenements()

    async with agent(flux=flux).etape("exécute la requête"):
        pass

    fin = (await evenements(flux))[-1]
    assert "duree_ms" in fin
    assert fin["duree_ms"] >= 0


async def test_a_failing_step_still_reports_its_end():
    """Une étape qui s'allume sans jamais s'éteindre laisse l'écran croire que ça continue."""
    flux = FluxEvenements()

    with pytest.raises(RuntimeError):
        async with agent(flux=flux).etape("exécute la requête"):
            raise RuntimeError("la base a refusé")

    assert [e["etat"] for e in await evenements(flux)] == ["started", "done"]


async def test_progress_can_be_reported_inside_a_step():
    flux = FluxEvenements()
    construit = agent(flux=flux)

    async with construit.etape("analyse"):
        await construit.progresser("relit le schéma")

    assert [e["etat"] for e in await evenements(flux)] == ["started", "working", "done"]


async def test_an_agent_without_a_stream_still_works():
    """Les tests unitaires et le serveur MCP n'ont pas d'écran à alimenter."""
    construit = agent()

    async with construit.etape("analyse"):
        await construit.progresser("relit le schéma")

    assert construit.nb_appels == 0


# --- Ce que ça coûte --------------------------------------------------------


async def test_every_call_is_recorded_without_the_agent_having_to_think_about_it():
    construit = agent()

    await construit.demander(Task.SQL_GENERATION, "instruction", "question", Reponse)
    await construit.rediger(Task.INTERPRETATION, "instruction", "question")

    assert construit.nb_appels == 2
    assert construit.cout_centimes > 0


async def test_the_cost_is_the_sum_of_the_calls():
    construit = agent(entree=1_000_000, sortie=0)

    await construit.demander(Task.SQL_GENERATION, "instruction", "question", Reponse)
    await construit.demander(Task.SQL_GENERATION, "instruction", "question", Reponse)

    # openai/gpt-oss-120b : 0,15 $ par million de jetons en entrée, deux fois.
    assert construit.cout_centimes == pytest.approx(30.0)


async def test_the_saving_from_caching_is_summed_too():
    construit = agent(entree=1_000_000, sortie=0, caches=1_000_000)

    await construit.demander(Task.SQL_GENERATION, "instruction", "question", Reponse)

    assert construit.economie_centimes == pytest.approx(13.5)


async def test_the_trace_carries_what_the_cost_counter_displays():
    construit = agent()

    await construit.demander(Task.SQL_GENERATION, "instruction", "question", Reponse)

    entree = construit.trace_json()[0]
    assert entree["agent"] == "analyste"
    assert entree["modele"] == "openai/gpt-oss-120b"
    assert set(entree) == {
        "agent",
        "fournisseur",
        "modele",
        "tokens_entree",
        "tokens_sortie",
        "tokens_caches",
        "cout_centimes",
        "economie_centimes",
        "duree_ms",
        "tentatives",
    }


async def test_a_structured_call_returns_a_validated_model():
    construit = agent('{"valeur":"quarante-deux"}')

    reponse = await construit.demander(Task.SQL_GENERATION, "instruction", "question", Reponse)

    assert isinstance(reponse, Reponse)
    assert reponse.valeur == "quarante-deux"
