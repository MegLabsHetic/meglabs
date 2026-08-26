"""La connexion a une base externe : ce qu'elle protege avant de se connecter.

Une chaine de connexion est fournie par l'utilisateur. Elle designe une machine,
porte des identifiants, et sert a construire des requetes : trois surfaces
d'attaque en une. Ces tests verrouillent ce qui est refuse AVANT qu'une
connexion soit tentee — le reste demande une vraie base et vit ailleurs.
"""

import pytest
from cryptography.fernet import Fernet

from app.core.errors import ErreurUtilisateur
from app.services.source_service import SourceService


@pytest.fixture
def service() -> SourceService:
    return SourceService(cle=Fernet.generate_key())


def config(**surcharges) -> dict:
    base = {
        "hote": "db.exemple.fr",
        "port": 5432,
        "base": "production",
        "utilisateur": "lecteur",
        "mot_de_passe": "secret-de-la-base",
        "schema": "public",
    }
    return {**base, **surcharges}


# --- Les identifiants --------------------------------------------------------


def test_credentials_survive_a_round_trip(service):
    chiffre = service.chiffrer(config())
    assert service.dechiffrer(chiffre) == config()


def test_the_password_never_appears_in_what_is_stored(service):
    """Une base tierce compromise par notre faute est plus grave qu'une des notres."""
    assert "secret-de-la-base" not in service.chiffrer(config())


def test_the_password_never_appears_in_what_is_returned(service):
    masquee = service.masquer(config())
    assert masquee["mot_de_passe"] == "••••••"
    assert masquee["hote"] == "db.exemple.fr"


def test_credentials_encrypted_with_another_key_are_refused(service):
    """Une cle changee doit donner une erreur lisible, pas un plantage."""
    autre = SourceService(cle=Fernet.generate_key())
    with pytest.raises(ErreurUtilisateur) as echec:
        autre.dechiffrer(service.chiffrer(config()))
    assert "Reconnectez" in str(echec.value)


# --- Ce qui est refuse avant de se connecter ---------------------------------


@pytest.mark.parametrize("hote", ["localhost", "127.0.0.1", "0.0.0.0", "::1", "postgres"])
def test_an_address_pointing_at_our_own_server_is_refused(service, hote):
    """Sans ce filtre, une chaine de connexion devient un moyen de faire scanner
    le reseau interne du serveur depuis l'exterieur — et d'atteindre notre propre
    base, qui porte les donnees de tous les espaces."""
    with pytest.raises(ErreurUtilisateur) as echec:
        service.tester(config(hote=hote))
    assert "serveur MegLabs" in str(echec.value)


def test_the_check_is_case_insensitive(service):
    with pytest.raises(ErreurUtilisateur):
        service.tester(config(hote="LocalHost"))


def test_an_empty_address_is_refused(service):
    with pytest.raises(ErreurUtilisateur) as echec:
        service.tester(config(hote="  "))
    assert "obligatoire" in str(echec.value)


# --- Les noms de table -------------------------------------------------------


@pytest.mark.parametrize(
    "nom",
    [
        'collaborateurs"; DROP TABLE clients; --',
        "collaborateurs; DELETE FROM x",
        "col onnes",
        "",
        "1chiffre_en_tete",
        "a" * 64,
    ],
)
def test_a_table_name_that_is_not_an_identifier_is_refused(service, nom):
    """PostgreSQL n'accepte pas d'identifiant lie : un nom de table est interpole
    dans la requete. La seule protection possible est de refuser tout ce qui n'est
    pas un identifiant valide AVANT de l'ecrire."""
    with pytest.raises(ErreurUtilisateur) as echec:
        service.lire(config(), "public", nom)
    assert "nom de table valide" in str(echec.value)


@pytest.mark.parametrize("nom", ["collaborateurs", "_prive", "table$1", "T2"])
def test_a_legitimate_table_name_passes_validation(service, nom):
    """Le refus ne doit pas ecarter des noms que PostgreSQL accepte."""
    service._valider_nom(nom)


def test_the_schema_is_validated_too(service):
    with pytest.raises(ErreurUtilisateur):
        service.lire(config(), 'public"; --', "collaborateurs")
