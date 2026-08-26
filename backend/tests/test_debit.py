"""La limitation de debit : qui est compte, et ce qui se passe au-dela.

Deux proprietes se cassent silencieusement si personne ne les verrouille.

L'adresse doit etre celle du visiteur et non celle du proxy : sinon la limite
s'applique a tous les visiteurs ensemble, et le premier gourmand bloque tous les
autres sans que rien ne le signale.

Et le refus doit arriver en francais avec la conduite a tenir. Un `429` nu se lit
comme une panne, alors que c'est une decision.
"""

from unittest.mock import Mock

from app.core.debit import LIMITE_CONVERSATION, LIMITE_DEPOT, LIMITE_PARTAGE, MESSAGE, adresse


def requete(entetes: dict[str, str] | None = None, client: str | None = "10.0.0.1") -> Mock:
    fausse = Mock()
    fausse.headers = entetes or {}
    fausse.client = Mock(host=client) if client else None
    return fausse


# --- Qui est compte ----------------------------------------------------------


def test_the_visitor_address_is_read_behind_the_proxy():
    """Caddy est seul a parler au monde exterieur : sans lire l'en-tete, toutes
    les requetes semblent venir de lui."""
    assert adresse(requete({"X-Forwarded-For": "203.0.113.7"})) == "203.0.113.7"


def test_only_the_first_hop_counts():
    """`X-Forwarded-For` accumule les relais ; le client d'origine est en tete."""
    entetes = {"X-Forwarded-For": "203.0.113.7, 198.51.100.2, 10.0.0.1"}
    assert adresse(requete(entetes)) == "203.0.113.7"


def test_surrounding_spaces_do_not_create_a_second_bucket():
    """« 203.0.113.7 » et « 203.0.113.7 » doivent compter comme une seule adresse."""
    assert adresse(requete({"X-Forwarded-For": "  203.0.113.7  , 10.0.0.1"})) == "203.0.113.7"


def test_without_a_proxy_the_direct_address_is_used():
    """En developpement il n'y a pas de proxy, et la limite doit fonctionner quand meme."""
    assert adresse(requete()) == "10.0.0.1"


# --- Le contrat avec la bibliotheque -----------------------------------------


def test_the_parameter_is_named_request_because_slowapi_inspects_that_name():
    """`slowapi` decide de passer la requete en lisant le NOM du parametre :

        if "request" in inspect.signature(lim.key_func).parameters.keys():

    Avec un nom francais la fonction est appelee sans argument et leve une
    TypeError a chaque requete limitee. Ce test existe pour qu'un futur
    renommage vers la convention du projet echoue ici plutot qu'en production.
    """
    import inspect

    assert "request" in inspect.signature(adresse).parameters


# --- Ce qui est borne --------------------------------------------------------


def test_every_limited_route_declares_a_per_minute_budget():
    for limite in (LIMITE_CONVERSATION, LIMITE_DEPOT, LIMITE_PARTAGE):
        nombre, _, periode = limite.partition("/")
        assert nombre.isdigit() and int(nombre) > 0
        assert periode == "minute"


def test_the_refusal_says_it_is_deliberate():
    """Un 429 nu se lit comme une panne. Celui-ci dit que c'est une decision."""
    assert "volontaire" in MESSAGE
    assert "patientez" in MESSAGE.lower()
