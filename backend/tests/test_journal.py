"""La journalisation : ce qu'elle publie, ce qu'elle correle, ce qu'elle retient.

Un journal est un contrat avec le futur : quand une panne arrive, on ne peut plus
rien ajouter. Ces tests verrouillent donc ce qui doit s'y trouver — et surtout ce
qui ne doit jamais s'y trouver.
"""

import json
import logging

import pytest

from app.core.journal import FormateurJson, configurer, id_requete, obtenir


def ligne(record: logging.LogRecord) -> dict:
    return json.loads(FormateurJson().format(record))


def enregistrement(message: str = "essai", **extra) -> logging.LogRecord:
    record = logging.LogRecord("test", logging.INFO, "f.py", 1, message, None, None)
    for cle, valeur in extra.items():
        setattr(record, cle, valeur)
    return record


# --- Ce qui sort -------------------------------------------------------------


def test_an_event_is_one_json_line():
    rendu = FormateurJson().format(enregistrement())
    assert "\n" not in rendu
    assert json.loads(rendu)["message"] == "essai"


def test_the_event_carries_its_level_and_source():
    evenement = ligne(enregistrement())
    assert evenement["niveau"] == "INFO"
    assert evenement["source"] == "test"
    assert evenement["horodatage"].startswith("20")


def test_extra_fields_are_published():
    """Sans cela, un journal ne dit que « il s'est passe quelque chose »."""
    evenement = ligne(enregistrement(modele="gpt-oss-120b", duree_ms=1324, cout_centimes=0.09))
    assert evenement["modele"] == "gpt-oss-120b"
    assert evenement["duree_ms"] == 1324
    assert evenement["cout_centimes"] == 0.09


def test_accents_survive_the_journal():
    evenement = ligne(enregistrement("requête refusée : donnée protégée"))
    assert evenement["message"] == "requête refusée : donnée protégée"


def test_a_value_that_is_not_json_does_not_break_the_line():
    """Un objet inattendu ne doit pas faire disparaitre l'evenement entier."""
    evenement = ligne(enregistrement(objet=object()))
    assert "objet" in evenement


# --- Ce qui ne sort jamais ---------------------------------------------------


@pytest.mark.parametrize(
    "cle", ["api_key", "password", "mot_de_passe", "token", "secret", "authorization"]
)
def test_a_secret_never_reaches_the_journal(cle: str):
    """Un secret journalise est un secret divulgue.

    Les journaux se copient, se transmettent et survivent au serveur qui les a
    produits. Le filtre est ici plutot que chez l'appelant : une regle qui repose
    sur la discipline de celui qui ecrit finit par ceder.
    """
    rendu = FormateurJson().format(enregistrement(**{cle: "sk-ant-valeur-tres-secrete"}))
    assert "sk-ant-valeur-tres-secrete" not in rendu
    assert cle not in json.loads(rendu)


# --- La correlation ----------------------------------------------------------


def test_the_request_id_is_attached_when_there_is_one():
    """C'est ce qui permet de relier les dix lignes d'une meme conversation."""
    jeton = id_requete.set("abc123")
    try:
        assert ligne(enregistrement())["requete"] == "abc123"
    finally:
        id_requete.reset(jeton)


def test_there_is_no_request_id_outside_a_request():
    """Au demarrage ou dans un script, l'absence est normale — pas une valeur vide."""
    assert "requete" not in ligne(enregistrement())


# --- Les erreurs -------------------------------------------------------------


def test_an_exception_is_recorded_with_its_type_and_its_stack():
    try:
        raise ValueError("cle invalide")
    except ValueError:
        import sys

        record = enregistrement("appel echoue")
        record.exc_info = sys.exc_info()

    evenement = ligne(record)
    assert evenement["erreur"] == "ValueError"
    assert evenement["detail"] == "cle invalide"
    assert "ValueError" in evenement["pile"]


# --- La configuration --------------------------------------------------------


def test_configuring_twice_does_not_double_the_output():
    """Le module est importe par plusieurs points d'entree : sans cette garantie,
    chaque evenement sortirait en double ou en triple."""
    configurer()
    configurer()
    racine = logging.getLogger()
    formateurs = [h for h in racine.handlers if isinstance(h.formatter, FormateurJson)]
    assert len(formateurs) == 1


def test_a_logger_is_obtained_by_module_name():
    assert obtenir("app.core.essai").name == "app.core.essai"
