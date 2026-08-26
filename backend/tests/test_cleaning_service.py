"""Le nettoyage guide : ce qu'il propose, ce qu'il annonce, ce qu'il rejoue.

Deux garanties comptent plus que les autres. L'impact annonce doit etre le vrai,
sinon la case a cocher ment. Et le rejeu doit rendre le meme resultat a chaque
fois, sinon l'etat courant d'un fichier depend du moment ou on le regarde.
"""

import pandas as pd
import pytest

from app.services.cleaning_service import (
    CASSE,
    DATES,
    DOUBLONS,
    MEDIANE,
    VIDES,
    NettoyageService,
)
from app.services.profiling_service import ProfilingService


@pytest.fixture
def service() -> NettoyageService:
    return NettoyageService()


@pytest.fixture
def sale() -> pd.DataFrame:
    """Les memes defauts que le jeu de demonstration, en douze lignes.

    Construites une par une plutot que par repetition : les deux dernieres
    doivent etre des copies EXACTES des lignes 1 et 7, et une repetition de
    motifs de longueurs differentes ne produit aucun doublon reel.
    """
    lignes = [
        ("Data", "2024-01-15", 41500),
        ("data", "15/02/2024", 39000),
        ("Data ", "2024-03-20", 45300),
        ("Technique", "20-04-2024", 52000),
        ("technique", "2024-05-10", None),
        ("Data", "12/06/2024", 38000),
        ("Technique", "2024-07-01", 47000),
        ("data", "03-08-2024", None),
        ("Data", "2024-09-15", 43000),
        ("Technique", "2024-10-20", 51000),
        ("Data", "2024-01-15", 41500),
        ("Technique", "2024-07-01", 47000),
    ]
    return pd.DataFrame(lignes, columns=["service", "embauche", "salaire"])


def propositions(service: NettoyageService, table: pd.DataFrame):
    return service.proposer(table, ProfilingService().profiler(table))


def par_type(liste, type_cherche):
    return next((p for p in liste if p.type == type_cherche), None)


# --- Ce qu'on propose --------------------------------------------------------


def test_variant_spellings_are_offered_for_normalisation(service, sale):
    """« Data », « data » et « Data » comptent comme trois services distincts."""
    proposition = par_type(propositions(service, sale), CASSE)
    assert proposition is not None
    assert proposition.colonne == "service"


def test_mixed_date_formats_are_offered_for_unification(service, sale):
    assert par_type(propositions(service, sale), DATES) is not None


def test_duplicate_rows_are_offered_for_removal(service, sale):
    proposition = par_type(propositions(service, sale), DOUBLONS)
    assert proposition is not None
    assert proposition.lignes_affectees > 0


def test_a_clean_table_is_offered_nothing():
    """Ne rien proposer est une reponse. Inventer du travail n'en est pas une."""
    propre = pd.DataFrame({"ville": ["Paris", "Lyon", "Nice"], "n": [1, 2, 3]})
    assert NettoyageService().proposer(propre, ProfilingService().profiler(propre)) == []


def test_the_heaviest_correction_comes_first(service, sale):
    """Qui ne lit que la premiere ligne doit tomber sur ce qui coute le plus."""
    liste = propositions(service, sale)
    affectees = [p.lignes_affectees for p in liste]
    assert affectees == sorted(affectees, reverse=True)


# --- Ce qu'on annonce --------------------------------------------------------


def test_the_announced_impact_is_the_real_one(service, sale):
    """Une case a cocher qui annonce un chiffre faux est pire que pas de chiffre."""
    proposition = par_type(propositions(service, sale), DOUBLONS)
    avant = len(sale)
    apres = len(service.appliquer(sale, [proposition.en_dict()]))
    assert avant - apres == proposition.lignes_affectees


def test_the_reason_names_what_was_found(service, sale):
    proposition = par_type(propositions(service, sale), CASSE)
    assert "écritures différentes" in proposition.raison


# --- Le rejeu ----------------------------------------------------------------


def test_normalising_collapses_the_variants(service, sale):
    proposition = par_type(propositions(service, sale), CASSE)
    nettoyee = service.appliquer(sale, [proposition.en_dict()])
    assert nettoyee["service"].nunique() == 2


def test_dates_come_out_in_one_format(service, sale):
    proposition = par_type(propositions(service, sale), DATES)
    nettoyee = service.appliquer(sale, [proposition.en_dict()])
    assert all(len(valeur) == 10 and valeur[4] == "-" for valeur in nettoyee["embauche"])


def test_an_unreadable_date_is_kept_rather_than_emptied():
    """Perdre une donnee pour cause de format inattendu est pire que le defaut."""
    table = pd.DataFrame({"quand": ["2024-01-15", "hier", "15/02/2024"]})
    nettoyee = NettoyageService().appliquer(table, [{"type": DATES, "colonne": "quand"}])
    assert nettoyee["quand"].tolist() == ["2024-01-15", "hier", "2024-02-15"]


def test_the_original_table_is_never_modified(service, sale):
    """Toute la machine a remonter le temps repose la-dessus."""
    avant = sale.copy()
    service.appliquer(sale, [{"type": DOUBLONS}])
    pd.testing.assert_frame_equal(sale, avant)


def test_replaying_twice_gives_the_same_result(service, sale):
    """L'etat courant ne doit pas dependre du moment ou on le calcule."""
    actions = [p.en_dict() for p in propositions(service, sale)]
    premier = service.appliquer(sale, actions)
    second = service.appliquer(sale, actions)
    pd.testing.assert_frame_equal(premier, second)


def test_the_imputed_value_is_frozen_in_the_parameters(service, sale):
    """Recalculee au rejeu, la mediane deriverait selon les actions precedentes."""
    proposition = par_type(propositions(service, sale), MEDIANE)
    assert proposition is not None
    assert "valeur" in proposition.params

    seule = service.appliquer(sale, [proposition.en_dict()])
    apres_normalisation = service.appliquer(
        sale, [{"type": CASSE, "colonne": "service"}, proposition.en_dict()]
    )
    assert seule["salaire"].tolist() == apres_normalisation["salaire"].tolist()


def test_an_action_on_a_missing_column_is_skipped_not_fatal(service, sale):
    """Une colonne disparue ne doit pas interrompre le rejeu des suivantes."""
    actions = [{"type": CASSE, "colonne": "colonne_absente"}, {"type": DOUBLONS}]
    nettoyee = service.appliquer(sale, actions)
    assert len(nettoyee) < len(sale)


def test_a_mostly_empty_column_is_offered_for_row_removal_not_imputation():
    """Au-dela d'un tiers d'absences, imputer inventerait plus qu'il ne conserve."""
    table = pd.DataFrame({"note": [5.0, None, None, None, None, 3.0]})
    liste = NettoyageService().proposer(table, ProfilingService().profiler(table))
    assert par_type(liste, VIDES) is not None
    assert par_type(liste, MEDIANE) is None
