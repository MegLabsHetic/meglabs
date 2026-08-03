"""Les imperfections des datasets sont volontaires : ces tests empechent qu'on les « corrige »."""

import re
from pathlib import Path

import pandas as pd
import pytest

from data.generate_datasets import DatasetGenerator, GenerationConfig

# Colonnes que pandas convertirait en nombres si on le laissait faire, detruisant
# au passage le « + » d'un telephone international et les zeros initiaux d'un NIR.
COLONNES_TEXTE = {
    "collaborateurs": {
        "id_collaborateur": str,
        "telephone": str,
        "iban": str,
        "numero_securite_sociale": str,
    },
    "transactions": {"id_transaction": str, "id_collaborateur": str},
}


@pytest.fixture(scope="module")
def datasets(tmp_path_factory) -> dict[str, pd.DataFrame]:
    destination = tmp_path_factory.mktemp("datasets")
    chemins = DatasetGenerator().generer(destination)
    return {nom: pd.read_csv(chemin, dtype=COLONNES_TEXTE[nom]) for nom, chemin in chemins.items()}


def test_two_runs_produce_byte_identical_files(tmp_path: Path):
    """La graine est fixe : sans cette garantie, aucun resultat de demo n'est rejouable."""
    premier = DatasetGenerator().generer(tmp_path / "a")
    second = DatasetGenerator().generer(tmp_path / "b")

    for nom in premier:
        assert premier[nom].read_bytes() == second[nom].read_bytes(), nom


def test_a_different_seed_produces_different_files(tmp_path: Path):
    reference = DatasetGenerator().generer(tmp_path / "ref")
    autre = DatasetGenerator(GenerationConfig(seed=7)).generer(tmp_path / "autre")

    assert reference["collaborateurs"].read_bytes() != autre["collaborateurs"].read_bytes()


# --- Les imperfections attendues ------------------------------------------


def test_some_values_are_missing(datasets):
    collaborateurs = datasets["collaborateurs"]

    for colonne in ("salaire_annuel", "score_performance", "telephone"):
        assert collaborateurs[colonne].isna().any(), colonne


def test_duplicate_rows_exist(datasets):
    for nom, table in datasets.items():
        assert table.duplicated().any(), nom


def test_dates_use_several_incompatible_formats(datasets):
    """Le nettoyage doit unifier trois ecritures de la meme date."""
    dates = datasets["collaborateurs"]["date_embauche"].astype(str)

    iso = dates.str.match(r"^\d{4}-\d{2}-\d{2}$").sum()
    slash = dates.str.match(r"^\d{2}/\d{2}/\d{4}$").sum()
    tiret = dates.str.match(r"^\d{2}-\d{2}-\d{4}$").sum()

    assert iso > 0 and slash > 0 and tiret > 0


def test_the_same_service_appears_under_several_spellings(datasets):
    services = datasets["collaborateurs"]["service"].astype(str)
    brutes = set(services.unique())
    normalisees = {valeur.strip().casefold() for valeur in brutes}

    assert len(brutes) > len(normalisees)


def test_salary_outliers_are_present(datasets):
    salaires = datasets["collaborateurs"]["salaire_annuel"].dropna()

    assert (salaires > 200_000).any()


def test_negative_amounts_are_present(datasets):
    assert (datasets["transactions"]["montant_euros"] < 0).any()


def test_some_transactions_reference_an_unknown_collaborator(datasets):
    """La jointure doit reveler ces orphelines plutot que de les avaler silencieusement."""
    connus = set(datasets["collaborateurs"]["id_collaborateur"])
    references = set(datasets["transactions"]["id_collaborateur"])

    assert references - connus


# --- Ce dont les demonstrations ont besoin ---------------------------------


def test_the_two_files_share_a_join_key(datasets):
    """La question de demo croise les deux fichiers : la cle doit majoritairement resoudre."""
    connus = set(datasets["collaborateurs"]["id_collaborateur"])
    resolues = datasets["transactions"]["id_collaborateur"].isin(connus)

    assert resolues.mean() > 0.95


def test_personal_columns_look_real_enough_for_pii_detection(datasets):
    collaborateurs = datasets["collaborateurs"]

    assert collaborateurs["email"].str.contains("@").all()
    assert collaborateurs["iban"].str.match(r"^FR76\d{23}$").all()
    assert collaborateurs["numero_securite_sociale"].astype(str).str.match(r"^\d{15}$").all()

    telephones = collaborateurs["telephone"].dropna().astype(str)
    francais = telephones.str.match(r"^(0[1-9]\d{8}|\+33\d{9})$")
    assert francais.all()


def test_the_dataset_supports_a_departure_risk_model(datasets):
    collaborateurs = datasets["collaborateurs"]

    assert len(collaborateurs) >= 50
    assert set(collaborateurs["a_quitte"].unique()) == {0, 1}
    # Sans les deux classes en quantite suffisante, l'entrainement n'a pas de sens.
    assert collaborateurs["a_quitte"].mean() > 0.05


def test_seniority_carries_signal_about_departures(datasets):
    """Un modele doit avoir quelque chose a apprendre, sinon la demo ML est creuse."""
    collaborateurs = datasets["collaborateurs"]
    partis = collaborateurs[collaborateurs["a_quitte"] == 1]["anciennete_annees"].mean()
    restes = collaborateurs[collaborateurs["a_quitte"] == 0]["anciennete_annees"].mean()

    assert partis < restes


def test_amounts_allow_a_revenue_question(datasets):
    """« Quel est le CA genere par les consultants du service Data ? » doit avoir une reponse."""
    transactions = datasets["transactions"]
    collaborateurs = datasets["collaborateurs"].copy()
    collaborateurs["service_propre"] = (
        collaborateurs["service"].astype(str).str.strip().str.casefold()
    )

    jointure = transactions.merge(collaborateurs, on="id_collaborateur", how="inner")
    consultants_data = jointure[
        (jointure["service_propre"] == "data") & (jointure["poste"] == "Consultant")
    ]

    assert len(consultants_data) > 0
    assert consultants_data["montant_euros"].sum() > 0


def test_phone_numbers_use_both_national_and_international_formats(datasets):
    telephones = datasets["collaborateurs"]["telephone"].dropna().astype(str)

    assert telephones.str.startswith("+33").any()
    assert telephones.str.match(r"^0[1-9]").any()
    assert re.match(r"^(0|\+)", telephones.iloc[0])


def test_naive_csv_reading_destroys_the_identity_columns(tmp_path: Path):
    """Piege a connaitre avant d'ecrire le chargement applicatif.

    Laisse a lui-meme, pandas lit `+33617025658` comme un flottant et perd le « + »,
    et lit un NIR commencant par zero comme un entier qui perd ce zero. Les colonnes
    deviennent alors invisibles pour la detection PII : il n'y a plus rien qui
    ressemble a un telephone ou a un numero de securite sociale. Le chargement doit
    donc forcer le type texte sur ces colonnes.
    """
    chemins = DatasetGenerator().generer(tmp_path)

    naif = pd.read_csv(chemins["collaborateurs"])
    prudent = pd.read_csv(chemins["collaborateurs"], dtype={"telephone": str})

    internationaux_perdus = naif["telephone"].dropna().astype(str).str.startswith("+33").any()
    internationaux_gardes = prudent["telephone"].dropna().str.startswith("+33").any()

    assert not internationaux_perdus
    assert internationaux_gardes
