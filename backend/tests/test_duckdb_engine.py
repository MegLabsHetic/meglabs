"""Le moteur d'execution : ce qu'il rend, ce qu'il borne, ce qu'il refuse."""

import asyncio

import pandas as pd
import pytest

from app.core.duckdb_engine import ErreurSql, MoteurDuckdb, nom_de_table
from app.core.errors import ErreurUtilisateur


@pytest.fixture
def tables() -> dict[str, pd.DataFrame]:
    return {
        "collaborateurs": pd.DataFrame(
            {
                "id_collaborateur": ["C0001", "C0002", "C0003"],
                "service": ["Data", "Data", "Technique"],
                "salaire_annuel": [41500, 56000, 45300],
            }
        ),
        "transactions": pd.DataFrame(
            {"id_collaborateur": ["C0001", "C0003"], "montant": [1200.0, 800.0]}
        ),
    }


async def test_a_read_returns_its_columns_and_rows(tables) -> None:
    resultat = await MoteurDuckdb().executer(
        "SELECT service, COUNT(*) AS effectif FROM collaborateurs GROUP BY service "
        "ORDER BY service",
        tables,
    )

    assert resultat.colonnes == ["service", "effectif"]
    assert resultat.lignes == [["Data", 2], ["Technique", 1]]
    assert resultat.tronque is False
    assert resultat.en_dicts()[0] == {"service": "Data", "effectif": 2}


async def test_a_join_across_two_files(tables) -> None:
    """La question de demonstration : deux fichiers, une seule reponse."""
    resultat = await MoteurDuckdb().executer(
        "SELECT c.service, SUM(t.montant) AS total FROM transactions t "
        "JOIN collaborateurs c ON c.id_collaborateur = t.id_collaborateur "
        "GROUP BY c.service ORDER BY total DESC",
        tables,
    )

    assert resultat.en_dicts() == [
        {"service": "Data", "total": 1200.0},
        {"service": "Technique", "total": 800.0},
    ]


async def test_the_result_is_capped_and_says_so(tables) -> None:
    moteur = MoteurDuckdb(limite_lignes=2)
    resultat = await moteur.executer("SELECT * FROM collaborateurs", tables)

    assert resultat.nb_lignes == 2
    assert resultat.tronque is True


def test_truncation_is_not_reported_wrongly(tables) -> None:
    moteur = MoteurDuckdb(limite_lignes=3)
    resultat = asyncio.run(moteur.executer("SELECT * FROM collaborateurs", tables))

    assert resultat.nb_lignes == 3
    assert resultat.tronque is False


async def test_an_engine_error_stays_technical(tables) -> None:
    """Elle est destinee au modele qui va se corriger, pas a l'utilisateur."""
    with pytest.raises(ErreurSql) as erreur:
        await MoteurDuckdb().executer("SELECT colonne_absente FROM collaborateurs", tables)

    assert "colonne_absente" in erreur.value.message
    assert not isinstance(erreur.value, ErreurUtilisateur)


async def test_file_access_is_cut_off_in_the_engine(tables) -> None:
    """Deuxieme verrou, independant du garde-fou : meme si une requete lui echappait."""
    with pytest.raises(ErreurSql):
        await MoteurDuckdb().executer("SELECT * FROM read_csv('/etc/passwd')", tables)


async def test_a_query_that_runs_too_long_is_interrupted() -> None:
    grande = {"nombres": pd.DataFrame({"n": range(2_000)})}
    moteur = MoteurDuckdb(timeout_s=1)

    with pytest.raises(ErreurUtilisateur) as erreur:
        # Un produit cartesien triple : lent a coup sur, sans dependre de la machine.
        await moteur.executer(
            "SELECT COUNT(*) FROM nombres a, nombres b, nombres c WHERE a.n + b.n + c.n > 0",
            grande,
        )

    assert "secondes" in erreur.value.message


async def test_two_executions_cannot_see_each_other() -> None:
    """Une connexion par requete : ce qui est enregistre ici n'existe pas la-bas."""
    moteur = MoteurDuckdb()
    await moteur.executer("SELECT 1", {"a": pd.DataFrame({"x": [1]})})

    with pytest.raises(ErreurSql):
        await moteur.executer("SELECT * FROM a", {"b": pd.DataFrame({"x": [1]})})


# --- Nommage des tables ---------------------------------------------------


@pytest.mark.parametrize(
    ("fichier", "attendu"),
    [
        ("collaborateurs.csv", "collaborateurs"),
        ("Ventes 2024.xlsx", "ventes_2024"),
        ("rapport-final.csv", "rapport_final"),
        ("2024.csv", "t_2024"),
        ("___.csv", "fichier"),
    ],
)
def test_a_table_name_stays_an_identifier(fichier: str, attendu: str) -> None:
    assert nom_de_table(fichier, set()) == attendu


def test_two_files_with_the_same_name_do_not_collide() -> None:
    pris: set[str] = set()
    for attendu in ("ventes", "ventes_2", "ventes_3"):
        nom = nom_de_table("ventes.csv", pris)
        assert nom == attendu
        pris.add(nom)
