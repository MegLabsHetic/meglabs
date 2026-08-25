"""L'adaptateur de connecteurs : ce qu'il comprend, ce qu'il borne, ce qu'il refuse.

Aucun tap ni conteneur n'est installe : les tests lancent un faux connecteur,
un interpreteur Python qui imprime des messages connus. Le protocole est du
texte sur la sortie standard, donc il se simule exactement.
"""

import sys

import pytest

from app.core.connecteur import Connecteur, analyser
from app.core.errors import ErreurUtilisateur


def faux_connecteur(*lignes: str, code_sortie: int = 0, sur_stderr: str = "") -> list[str]:
    """Une commande qui imprime les lignes demandees puis s'arrete."""
    programme = (
        "import sys\n"
        # Un vrai connecteur ecrit en UTF-8. Sans cette ligne, l'interpreteur
        # suivrait l'encodage de la console Windows et les accents arriveraient
        # abimes — ce qui testerait le terminal, pas l'adaptateur.
        "sys.stdout.reconfigure(encoding='utf-8')\n"
        f"for l in {list(lignes)!r}: print(l)\n"
        f"sys.stderr.write({sur_stderr!r})\n"
        f"sys.exit({code_sortie})\n"
    )
    return [sys.executable, "-c", programme]


# --- Le protocole, dans ses deux dialectes -----------------------------------


def test_the_singer_dialect_is_understood():
    message = analyser('{"type":"RECORD","stream":"issues","record":{"id":1}}')
    assert message is not None
    assert (message.flux, message.donnees) == ("issues", {"id": 1})


def test_the_airbyte_dialect_is_understood():
    """Airbyte imbrique le flux et les donnees la ou Singer les met a la racine."""
    message = analyser('{"type":"RECORD","record":{"stream":"issues","data":{"id":1}}}')
    assert message is not None
    assert (message.flux, message.donnees) == ("issues", {"id": 1})


def test_a_line_that_is_not_a_message_is_ignored_rather_than_fatal():
    """Les connecteurs ecrivent aussi des avertissements en texte brut."""
    assert analyser("Warning: deprecated option --full") is None
    assert analyser("") is None
    assert analyser('{"pas_de_type": 1}') is None


def test_a_truncated_json_line_does_not_stop_the_run():
    assert analyser('{"type":"RECORD","stream":"iss') is None


# --- Ce qu'une lecture produit -----------------------------------------------


async def test_records_become_one_table_per_stream():
    connecteur = Connecteur(
        faux_connecteur(
            '{"type":"RECORD","stream":"clients","record":{"id":1,"nom":"ACME"}}',
            '{"type":"RECORD","stream":"clients","record":{"id":2,"nom":"Globex"}}',
            '{"type":"RECORD","stream":"factures","record":{"id":9,"montant":120}}',
        )
    )
    extraction = await connecteur.lire()

    assert set(extraction.tables) == {"clients", "factures"}
    assert len(extraction.tables["clients"]) == 2
    assert list(extraction.tables["clients"].columns) == ["id", "nom"]
    assert extraction.nb_lignes == 3


async def test_the_state_is_kept_so_the_next_run_reads_only_what_is_new():
    connecteur = Connecteur(
        faux_connecteur(
            '{"type":"RECORD","stream":"x","record":{"id":1}}',
            '{"type":"STATE","value":{"x":{"depuis":"2026-08-24"}}}',
        )
    )
    extraction = await connecteur.lire()
    assert extraction.etat == {"x": {"depuis": "2026-08-24"}}


async def test_log_messages_are_collected_without_becoming_rows():
    connecteur = Connecteur(
        faux_connecteur(
            '{"type":"LOG","log":{"level":"INFO","message":"3 tables trouvées"}}',
            '{"type":"RECORD","stream":"x","record":{"id":1}}',
        )
    )
    extraction = await connecteur.lire()
    assert extraction.journal == ["3 tables trouvées"]
    assert extraction.nb_lignes == 1


async def test_identity_columns_keep_their_leading_zeros_and_plus_sign():
    """Le meme piege que pour les fichiers deposes.

    Laisse a lui-meme, pandas lit `+33617025658` comme un flottant et perd le
    `+`, et fait perdre a un identifiant ses zeros initiaux. La detection de
    donnees personnelles ne trouverait alors plus rien, sans lever d'erreur.
    """
    connecteur = Connecteur(
        faux_connecteur(
            '{"type":"RECORD","stream":"x","record":'
            '{"telephone":"+33617025658","matricule":"007"}}',
        )
    )
    table = (await connecteur.lire()).tables["x"]

    assert table["telephone"].iloc[0] == "+33617025658"
    assert table["matricule"].iloc[0] == "007"


# --- Les bornes et les refus -------------------------------------------------


async def test_a_large_source_is_capped_and_says_so():
    """Une source volumineuse remplirait la memoire avant qu'on s'en apercoive."""
    lignes = [f'{{"type":"RECORD","stream":"x","record":{{"id":{i}}}}}' for i in range(50)]
    extraction = await Connecteur(faux_connecteur(*lignes)).lire(lignes_max=10)

    assert extraction.tronquee is True
    assert extraction.nb_lignes == 10


async def test_a_small_source_is_not_reported_as_truncated():
    extraction = await Connecteur(
        faux_connecteur('{"type":"RECORD","stream":"x","record":{"id":1}}')
    ).lire(lignes_max=10)
    assert extraction.tronquee is False


async def test_a_failing_connector_becomes_a_readable_french_error():
    connecteur = Connecteur(
        faux_connecteur(
            sur_stderr="psycopg2.OperationalError: password authentication failed", code_sortie=1
        )
    )
    with pytest.raises(ErreurUtilisateur) as echec:
        await connecteur.lire()

    assert "refusé la connexion" in str(echec.value)


async def test_a_failure_after_some_rows_is_still_a_failure():
    """Des lignes sorties ne prouvent pas que la lecture est allee au bout."""
    connecteur = Connecteur(
        faux_connecteur(
            '{"type":"RECORD","stream":"x","record":{"id":1}}',
            sur_stderr="connection reset",
            code_sortie=2,
        )
    )
    with pytest.raises(ErreurUtilisateur):
        await connecteur.lire()


async def test_a_connector_that_is_not_installed_names_the_problem():
    with pytest.raises(ErreurUtilisateur) as echec:
        await Connecteur(["tap-inexistant-xyz"]).lire()

    assert "n'est pas installé" in str(echec.value)


async def test_a_connector_that_never_finishes_is_interrupted():
    connecteur = Connecteur(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        delai_secondes=1,
    )
    with pytest.raises(ErreurUtilisateur) as echec:
        await connecteur.lire()

    assert "n'a pas répondu" in str(echec.value)


def test_an_empty_command_is_refused_at_construction():
    with pytest.raises(ValueError):
        Connecteur([])
