"""Parcours complet du depot d'un fichier, avec ses refus."""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import get_session
from app.main import app
from app.models import Base

DATASETS = Path(__file__).resolve().parents[1] / "data"


@pytest_asyncio.fixture
async def client(tmp_path: Path, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    """Application branchee sur une base en memoire et un stockage jetable."""
    get_settings.cache_clear()
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def session_de_test() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_de_test
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ouvert:
        yield ouvert

    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def workspace_id(client: AsyncClient) -> str:
    reponse = await client.post("/api/workspaces", json={"nom": "Analyse RH"})
    return reponse.json()["id"]


def fichier_reel(nom: str = "collaborateurs.csv") -> dict:
    return {"fichier": (nom, (DATASETS / nom).read_bytes(), "text/csv")}


# --- Espaces de travail -----------------------------------------------------


async def test_a_workspace_can_be_created_and_read_back(client: AsyncClient):
    creation = await client.post("/api/workspaces", json={"nom": "Analyse RH"})
    assert creation.status_code == 201

    lecture = await client.get(f"/api/workspaces/{creation.json()['id']}")
    assert lecture.json()["nom"] == "Analyse RH"


async def test_an_unknown_workspace_is_refused_in_plain_french(client: AsyncClient):
    reponse = await client.get("/api/workspaces/inexistant")

    assert reponse.status_code == 404
    assert "n'existe pas" in reponse.json()["detail"]


# --- Depot ------------------------------------------------------------------


async def test_uploading_a_file_returns_its_profile_and_its_personal_columns(
    client: AsyncClient, workspace_id: str
):
    reponse = await client.post(f"/api/workspaces/{workspace_id}/files", files=fichier_reel())

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["fichier"]["nom"] == "collaborateurs.csv"
    assert corps["profil"]["nb_lignes"] == 232
    assert corps["fichier"]["statut_pii"] == "detectee"

    colonnes = {d["colonne"] for d in corps["donnees_personnelles"]}
    assert {"email", "telephone", "iban", "numero_securite_sociale"} <= colonnes


async def test_the_stored_file_is_renamed_so_path_traversal_cannot_happen(
    client: AsyncClient, workspace_id: str, tmp_path: Path
):
    """Le nom fourni n'atteint jamais le disque : il ne peut donc pas designer un chemin."""
    piege = {
        "fichier": ("../../evasion.csv", (DATASETS / "collaborateurs.csv").read_bytes(), "text/csv")
    }

    reponse = await client.post(f"/api/workspaces/{workspace_id}/files", files=piege)

    assert reponse.status_code == 201
    stockes = list((tmp_path / "storage").iterdir())
    assert len(stockes) == 1
    assert "evasion" not in stockes[0].name
    assert stockes[0].suffix == ".csv"


async def test_an_unsupported_extension_is_refused(client: AsyncClient, workspace_id: str):
    reponse = await client.post(
        f"/api/workspaces/{workspace_id}/files",
        files={"fichier": ("notes.txt", b"bonjour", "text/plain")},
    )

    assert reponse.status_code == 400
    assert "n'est pas pris en charge" in reponse.json()["detail"]


async def test_a_file_lying_about_its_extension_is_refused(client: AsyncClient, workspace_id: str):
    """Une extension .xlsx ne suffit pas : le contenu doit etre une archive."""
    reponse = await client.post(
        f"/api/workspaces/{workspace_id}/files",
        files={"fichier": ("faux.xlsx", b"nom,age\nPaul,30\n", "application/vnd.ms-excel")},
    )

    assert reponse.status_code == 400
    assert "son contenu n'en est pas un" in reponse.json()["detail"]


async def test_an_empty_file_is_refused(client: AsyncClient, workspace_id: str):
    reponse = await client.post(
        f"/api/workspaces/{workspace_id}/files",
        files={"fichier": ("vide.csv", b"", "text/csv")},
    )

    assert reponse.status_code == 400
    assert "vide" in reponse.json()["detail"]


async def test_depositing_into_an_unknown_workspace_is_refused(client: AsyncClient):
    reponse = await client.post("/api/workspaces/inexistant/files", files=fichier_reel())

    assert reponse.status_code == 404


# --- Pseudonymisation -------------------------------------------------------


async def test_pseudonymising_replaces_the_values_on_disk(
    client: AsyncClient, workspace_id: str, tmp_path: Path
):
    depot = await client.post(f"/api/workspaces/{workspace_id}/files", files=fichier_reel())
    file_id = depot.json()["fichier"]["id"]

    reponse = await client.post(f"/api/files/{file_id}/pseudonymise")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["fichier"]["statut_pii"] == "masquee"
    assert corps["valeurs_remplacees"] > 0
    assert "email" in corps["colonnes_pseudonymisees"]

    stocke = next((tmp_path / "storage").iterdir()).read_text(encoding="utf-8")
    assert "chloe.petit@meglabs.example" not in stocke
    assert "email_001@masked.local" in stocke


async def test_pseudonymising_twice_is_refused(client: AsyncClient, workspace_id: str):
    depot = await client.post(f"/api/workspaces/{workspace_id}/files", files=fichier_reel())
    file_id = depot.json()["fichier"]["id"]
    await client.post(f"/api/files/{file_id}/pseudonymise")

    reponse = await client.post(f"/api/files/{file_id}/pseudonymise")

    assert reponse.status_code == 400
    assert "déjà" in reponse.json()["detail"]


async def test_the_profile_is_refreshed_after_pseudonymisation(
    client: AsyncClient, workspace_id: str
):
    depot = await client.post(f"/api/workspaces/{workspace_id}/files", files=fichier_reel())
    file_id = depot.json()["fichier"]["id"]

    await client.post(f"/api/files/{file_id}/pseudonymise")
    profil = (await client.get(f"/api/files/{file_id}/profile")).json()

    exemples = [e for c in profil["colonnes"] if c["nom"] == "email" for e in c["exemples"]]
    assert all(exemple.endswith("@masked.local") for exemple in exemples)


# --- Listing ----------------------------------------------------------------


async def test_files_are_listed_for_their_workspace(client: AsyncClient, workspace_id: str):
    await client.post(f"/api/workspaces/{workspace_id}/files", files=fichier_reel())
    await client.post(
        f"/api/workspaces/{workspace_id}/files", files=fichier_reel("transactions.csv")
    )

    reponse = await client.get(f"/api/workspaces/{workspace_id}/files")

    assert {f["nom"] for f in reponse.json()} == {"collaborateurs.csv", "transactions.csv"}


async def test_personal_columns_can_be_read_back_after_a_reload(
    client: AsyncClient, workspace_id: str
):
    """Sans cette route, l'interface perdrait la bannière au premier rechargement."""
    depot = await client.post(f"/api/workspaces/{workspace_id}/files", files=fichier_reel())
    file_id = depot.json()["fichier"]["id"]

    reponse = await client.get(f"/api/files/{file_id}/pii")

    assert reponse.status_code == 200
    assert {d["colonne"] for d in reponse.json()} == {
        d["colonne"] for d in depot.json()["donnees_personnelles"]
    }


async def test_reading_personal_columns_reflects_pseudonymisation(
    client: AsyncClient, workspace_id: str
):
    """La détection est recalculée : après masquage, il ne reste plus rien à protéger."""
    depot = await client.post(f"/api/workspaces/{workspace_id}/files", files=fichier_reel())
    file_id = depot.json()["fichier"]["id"]
    await client.post(f"/api/files/{file_id}/pseudonymise")

    restantes = (await client.get(f"/api/files/{file_id}/pii")).json()

    assert all(d["type_pii"] != "adresse e-mail" for d in restantes)
