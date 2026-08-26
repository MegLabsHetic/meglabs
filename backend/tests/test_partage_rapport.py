"""Le partage d'un rapport : ce qu'un lien montre, et ce qu'il ne dit pas.

Un lien de partage sort du perimetre habituel : il est destine a quelqu'un qui
n'a pas de compte, pas d'espace, et souvent aucune raison de faire confiance a
celui qui le lui a envoye. Ces tests verrouillent les deux proprietes qui
comptent alors — ce qu'il montre est fige, et ce qu'il refuse ne renseigne pas.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def espace_avec_fichier(client) -> str:
    reponse = await client.post("/api/workspaces", json={"nom": "Partage"})
    espace = reponse.json()["id"]
    # Lu d'un coup plutot qu'ouvert en flux : `open` bloque la boucle asyncio, et
    # le fichier de demonstration fait 36 Ko.
    contenu = Path("data/collaborateurs.csv").read_bytes()
    await client.post(
        f"/api/workspaces/{espace}/files",
        files={"fichier": ("collaborateurs.csv", contenu, "text/csv")},
    )
    return espace


# --- Ce qu'un lien montre ----------------------------------------------------


async def test_sharing_returns_a_token_that_reads_back(client):
    espace = await espace_avec_fichier(client)
    jeton = (await client.post(f"/api/workspaces/{espace}/rapport/partage")).json()["jeton"]

    lecture = await client.get(f"/api/partages/{jeton}")
    assert lecture.status_code == 200
    assert lecture.json()["sources"][0]["nom"] == "collaborateurs.csv"


async def test_the_shared_content_is_frozen_at_the_moment_of_sharing(client):
    """Un lien transmis doit montrer ce qu'on a voulu montrer.

    Sans cette copie, nettoyer un fichier apres coup changerait un document deja
    envoye — et personne ne saurait que ce n'est plus le meme.
    """
    espace = await espace_avec_fichier(client)
    jeton = (await client.post(f"/api/workspaces/{espace}/rapport/partage")).json()["jeton"]
    avant = (await client.get(f"/api/partages/{jeton}")).json()

    fichier = (await client.get(f"/api/workspaces/{espace}/files")).json()[0]["id"]
    await client.post(f"/api/files/{fichier}/nettoyage", json={"types": ["supprimer_doublons"]})

    apres = (await client.get(f"/api/partages/{jeton}")).json()
    assert apres["confiance"]["score"] == avant["confiance"]["score"]
    assert apres["sources"][0]["doublons"] == avant["sources"][0]["doublons"]


async def test_two_shares_have_different_tokens(client):
    espace = await espace_avec_fichier(client)
    premier = (await client.post(f"/api/workspaces/{espace}/rapport/partage")).json()["jeton"]
    second = (await client.post(f"/api/workspaces/{espace}/rapport/partage")).json()["jeton"]
    assert premier != second


async def test_the_token_is_long_enough_not_to_be_guessed(client):
    espace = await espace_avec_fichier(client)
    jeton = (await client.post(f"/api/workspaces/{espace}/rapport/partage")).json()["jeton"]
    assert len(jeton) >= 40


# --- Ce qu'il ne dit pas -----------------------------------------------------


async def test_revoking_kills_every_link_of_the_workspace(client):
    espace = await espace_avec_fichier(client)
    jeton = (await client.post(f"/api/workspaces/{espace}/rapport/partage")).json()["jeton"]

    revoques = (await client.delete(f"/api/workspaces/{espace}/rapport/partage")).json()
    assert revoques["liens_revoques"] == 1
    assert (await client.get(f"/api/partages/{jeton}")).status_code == 404


async def test_a_revoked_link_is_indistinguishable_from_one_that_never_existed(client):
    """Distinguer les deux dirait a un curieux qu'il a trouve quelque chose."""
    espace = await espace_avec_fichier(client)
    jeton = (await client.post(f"/api/workspaces/{espace}/rapport/partage")).json()["jeton"]
    await client.delete(f"/api/workspaces/{espace}/rapport/partage")

    revoque = await client.get(f"/api/partages/{jeton}")
    inexistant = await client.get("/api/partages/jamais-emis-celui-la")

    assert revoque.status_code == inexistant.status_code == 404
    assert revoque.json() == inexistant.json()


async def test_a_shared_report_never_carries_the_workspace_identifier(client):
    """Un lien public ne doit pas ouvrir la porte de l'espace qui l'a produit."""
    espace = await espace_avec_fichier(client)
    jeton = (await client.post(f"/api/workspaces/{espace}/rapport/partage")).json()["jeton"]

    contenu = (await client.get(f"/api/partages/{jeton}")).text
    assert espace not in contenu
