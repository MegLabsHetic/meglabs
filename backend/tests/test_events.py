"""Le bus d'événements est un contrat d'interface : son format se teste au caractère près."""

import asyncio
import json

from app.core.events import (
    AGENT,
    DEMARRE,
    FIN,
    TERMINE,
    Evenement,
    FluxEvenements,
    evenement_agent,
)


async def collecter(flux: FluxEvenements) -> list[Evenement]:
    return [evenement async for evenement in flux]


def test_the_wire_format_is_valid_server_sent_events():
    rendu = Evenement(AGENT, {"agent": "Analyste", "detail": "génère le SQL"}).en_sse()

    lignes = rendu.split("\n")
    assert lignes[0] == "event: agent_status"
    assert lignes[1].startswith("data: ")
    # La ligne vide finale est ce qui termine un événement : sans elle, le client attend.
    assert rendu.endswith("\n\n")


def test_accents_survive_the_wire():
    """Les détails sont en français : les échapper en \\u les rendrait illisibles au débogage."""
    rendu = Evenement(AGENT, {"detail": "vérifie la requête"}).en_sse()

    assert "vérifie la requête" in rendu
    assert json.loads(rendu.split("data: ")[1])["detail"] == "vérifie la requête"


def test_an_agent_event_carries_what_the_screen_needs():
    evenement = evenement_agent("Analyste", DEMARRE, "génère le SQL")

    assert evenement.type == AGENT
    assert evenement.donnees == {
        "agent": "Analyste",
        "etat": "started",
        "detail": "génère le SQL",
    }


def test_a_duration_is_only_reported_when_known():
    """Un événement de démarrage sans durée ne doit pas porter un zéro trompeur."""
    assert "duree_ms" not in evenement_agent("A", DEMARRE, "x").donnees
    assert evenement_agent("A", TERMINE, "x", 42).donnees["duree_ms"] == 42


async def test_events_arrive_in_the_order_they_were_published():
    flux = FluxEvenements()

    for rang in range(5):
        await flux.publier(Evenement(AGENT, {"rang": rang}))
    await flux.cloturer()

    assert [e.donnees["rang"] for e in await collecter(flux)] == [0, 1, 2, 3, 4]


async def test_closing_ends_the_stream():
    flux = FluxEvenements()
    await flux.publier(Evenement(FIN))
    await flux.cloturer()

    # Sans terminaison, le client resterait connecté indéfiniment.
    assert await asyncio.wait_for(collecter(flux), timeout=1) == [Evenement(FIN)]


async def test_closing_twice_is_harmless():
    flux = FluxEvenements()
    await flux.cloturer()
    await flux.cloturer()

    assert await asyncio.wait_for(collecter(flux), timeout=1) == []


async def test_publishing_after_closing_is_ignored():
    flux = FluxEvenements()
    await flux.cloturer()
    await flux.publier(Evenement(AGENT))

    assert await asyncio.wait_for(collecter(flux), timeout=1) == []


async def test_a_full_queue_drops_events_rather_than_blocking():
    """Un client déconnecté ne doit pas figer le traitement.

    Perdre une animation est acceptable ; bloquer une réponse ne l'est pas.
    """
    flux = FluxEvenements(taille_max=3)

    for rang in range(10):
        await asyncio.wait_for(flux.publier(Evenement(AGENT, {"rang": rang})), timeout=1)

    assert flux.abandonnes == 7


async def test_the_sse_stream_is_ready_to_be_returned_as_is():
    flux = FluxEvenements()
    await flux.publier(evenement_agent("Rédacteur", DEMARRE, "rédige la réponse"))
    await flux.cloturer()

    morceaux = [morceau async for morceau in flux.en_sse()]

    assert morceaux[0].startswith("event: agent_status\ndata: {")
    assert "Rédacteur" in morceaux[0]
