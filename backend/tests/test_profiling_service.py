"""Le profilage est du Python pur, et sa sortie est la seule chose qui atteint le LLM."""

import json
from pathlib import Path

import pandas as pd
import pytest

from app.agents.data_agent import DataAgent
from app.services.file_loader import FileLoader
from app.services.profiling_service import (
    BOOLEEN,
    CATEGORIE,
    DATE,
    DECIMAL,
    ENTIER,
    IDENTIFIANT,
    TEXTE,
    ProfilingService,
)

DATASETS = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def collaborateurs() -> pd.DataFrame:
    return FileLoader().charger(DATASETS / "collaborateurs.csv")


@pytest.fixture(scope="module")
def profil(collaborateurs: pd.DataFrame) -> dict:
    return ProfilingService().profiler(collaborateurs)


def colonne(profil: dict, nom: str) -> dict:
    return next(c for c in profil["colonnes"] if c["nom"] == nom)


# --- Detection des types ---------------------------------------------------


@pytest.mark.parametrize(
    ("nom", "attendu"),
    [
        ("id_collaborateur", IDENTIFIANT),
        # `email` n'est unique qu'a 88 % dans ce jeu (les prenoms et noms sont tires
        # de pools de 48, donc « paul.martin@ » se repete). Structurellement, ce n'est
        # donc pas un identifiant. C'est la detection PII qui le reconnaitra, par son
        # motif — le typage decrit la forme, pas la sensibilite.
        ("email", TEXTE),
        ("service", CATEGORIE),
        ("poste", CATEGORIE),
        ("date_embauche", DATE),
        ("anciennete_annees", ENTIER),
        ("score_performance", DECIMAL),
        ("a_quitte", BOOLEEN),
    ],
)
def test_semantic_types_are_recognised(profil: dict, nom: str, attendu: str):
    assert colonne(profil, nom)["type"] == attendu


def test_a_free_text_column_is_not_mistaken_for_a_category():
    table = pd.DataFrame(
        {"commentaire": [f"Retour client numero {i} sur le service" for i in range(200)]}
    )

    profil = ProfilingService().profiler(table)

    assert colonne(profil, "commentaire")["type"] in (TEXTE, IDENTIFIANT)


# --- Ce que le profil doit mesurer -----------------------------------------


def test_missing_values_are_counted(profil: dict):
    salaire = colonne(profil, "salaire_annuel")

    assert salaire["valeurs_manquantes"] > 0
    assert 0 < salaire["part_manquantes"] < 1


def test_duplicates_are_counted(profil: dict):
    assert profil["doublons"]["nombre"] > 0
    assert profil["doublons"]["part"] > 0


def test_numeric_columns_carry_aggregates(profil: dict):
    stats = colonne(profil, "salaire_annuel")["statistiques"]

    assert set(stats) == {"minimum", "maximum", "moyenne", "mediane", "ecart_type"}
    assert stats["minimum"] <= stats["mediane"] <= stats["maximum"]


def test_categorical_columns_carry_their_top_values(profil: dict):
    modalites = colonne(profil, "poste")["statistiques"]["modalites_frequentes"]

    assert 0 < len(modalites) <= 5
    assert all(m["occurrences"] > 0 for m in modalites)


# --- Les anomalies detectees -----------------------------------------------


def anomalies(profil: dict, nom: str) -> set[str]:
    return {a["type"] for a in colonne(profil, nom)["anomalies"]}


def test_casing_variants_are_flagged(profil: dict):
    """« Data », « data » et « DATA  » sont la meme modalite ecrite trois fois."""
    assert "modalites_variantes" in anomalies(profil, "service")


def test_mixed_date_formats_are_flagged(profil: dict):
    assert "formats_multiples" in anomalies(profil, "date_embauche")


def test_the_injected_salary_outliers_are_all_found(profil: dict):
    """Le generateur en injecte huit ; le profileur doit les retrouver sans le savoir.

    Cette egalite exacte est le test le plus parlant du profilage : la detection est
    aveugle au generateur, et retombe pourtant sur son compte.
    """
    extremes = next(
        a for a in colonne(profil, "salaire_annuel")["anomalies"] if a["type"] == "valeurs_extremes"
    )

    assert "8 valeur(s)" in extremes["detail"]


def test_a_clean_column_carries_no_anomaly():
    table = pd.DataFrame({"note": [10, 11, 12, 11, 10, 12, 11]})

    profil = ProfilingService().profiler(table)

    assert colonne(profil, "note")["anomalies"] == []


# --- Le score de qualite ---------------------------------------------------


def test_quality_score_is_penalised_by_the_known_flaws(profil: dict):
    """Le dataset porte des defauts volontaires : un score quasi parfait ne serait pas credible.

    Le seuil a 95 est deliberement bas : un fichier complet mais truffe d'incoherences
    de saisie affichait 97,8 avant que le critere « incoherences » n'existe, ce qu'aucun
    utilisateur n'aurait cru en regardant ses donnees.
    """
    assert 0 <= profil["score_qualite"] < 95


def test_inconsistency_is_among_the_reasons_given(profil: dict):
    criteres = {penalite["critere"] for penalite in profil["explication_qualite"]}

    assert "Incohérences de saisie" in criteres


def test_quality_score_explains_itself(profil: dict):
    """Un score sans explication n'est pas actionnable, et le rapport doit le justifier."""
    explication = profil["explication_qualite"]

    assert explication
    for penalite in explication:
        assert set(penalite) == {"critere", "impact", "detail"}
        assert penalite["impact"] < 0
        assert penalite["detail"].strip()


def test_a_clean_dataset_scores_perfectly():
    table = pd.DataFrame({"a": [1, 2, 3, 4], "b": ["x", "y", "z", "w"]})

    profil = ProfilingService().profiler(table)

    assert profil["score_qualite"] == 100.0
    assert profil["explication_qualite"] == []


# --- La garantie de souverainete -------------------------------------------


def test_examples_are_bounded_and_stripped_of_whitespace():
    table = pd.DataFrame({"long": ["x" * 300, "a\nb\tc", "court"]})

    exemples = ProfilingService().profiler(table)["colonnes"][0]["exemples"]

    assert all(len(exemple) <= 80 for exemple in exemples)
    assert "\n" not in exemples[1] and "\t" not in exemples[1]


def test_at_most_three_examples_per_column(profil: dict):
    for entree in profil["colonnes"]:
        assert len(entree["exemples"]) <= 3


def test_the_llm_context_never_carries_a_value_from_deep_in_the_file(
    collaborateurs: pd.DataFrame, profil: dict
):
    """La garantie centrale : aucune ligne brute ne quitte le serveur.

    On prend une valeur qui existe reellement dans le fichier mais hors des trois
    premieres lignes, et on verifie qu'elle est absente de ce qui part au modele.
    """
    contexte = json.dumps(ProfilingService().llm_context(profil), ensure_ascii=False)

    for colonne_sensible in ("email", "numero_securite_sociale", "iban"):
        valeur_profonde = str(collaborateurs[colonne_sensible].dropna().iloc[100])
        assert valeur_profonde not in contexte, colonne_sensible


def test_the_llm_context_is_far_smaller_than_the_file(profil: dict):
    contexte = json.dumps(ProfilingService().llm_context(profil), ensure_ascii=False)
    fichier = (DATASETS / "collaborateurs.csv").stat().st_size

    assert len(contexte) < fichier / 4


# --- L'agent compose les deux ----------------------------------------------


def test_the_data_agent_profiles_a_file_end_to_end():
    profil = DataAgent().profiler(DATASETS / "transactions.csv")

    assert profil["nb_lignes"] == 3012
    assert profil["nb_colonnes"] == 7
    assert colonne(profil, "montant_euros")["type"] == DECIMAL
