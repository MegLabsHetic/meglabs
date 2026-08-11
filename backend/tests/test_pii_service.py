"""La detection PII est le socle de la promesse de souverainete : elle se teste en dur."""

import json
from pathlib import Path

import pandas as pd
import pytest

from app.agents.data_agent import DataAgent
from app.services.file_loader import FileLoader
from app.services.pii_service import (
    EMAIL,
    IBAN,
    NOM_PERSONNE,
    SECURITE_SOCIALE,
    TELEPHONE,
    PiiService,
)
from app.services.profiling_service import ProfilingService

DATASETS = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def collaborateurs() -> pd.DataFrame:
    return FileLoader().charger(DATASETS / "collaborateurs.csv")


@pytest.fixture(scope="module")
def detections(collaborateurs: pd.DataFrame) -> dict[str, object]:
    return {d.colonne: d for d in PiiService().detecter(collaborateurs)}


# --- Ce qui doit etre repere -----------------------------------------------


@pytest.mark.parametrize(
    ("colonne", "attendu"),
    [
        ("email", EMAIL),
        ("telephone", TELEPHONE),
        ("iban", IBAN),
        ("numero_securite_sociale", SECURITE_SOCIALE),
        ("prenom", NOM_PERSONNE),
        ("nom", NOM_PERSONNE),
    ],
)
def test_sensitive_columns_are_detected(detections: dict, colonne: str, attendu: str):
    assert colonne in detections, f"{colonne} n'a pas ete detectee"
    assert detections[colonne].type_pii == attendu


@pytest.mark.parametrize(
    "colonne",
    ["id_collaborateur", "service", "poste", "salaire_annuel", "date_embauche", "a_quitte"],
)
def test_ordinary_columns_are_left_alone(detections: dict, colonne: str):
    """Une detection trop large ferait masquer des colonnes metier utiles a l'analyse."""
    assert colonne not in detections


def test_business_columns_of_another_file_are_not_flagged():
    """`client` contient des raisons sociales, pas des noms de personnes."""
    transactions = FileLoader().charger(DATASETS / "transactions.csv")

    reperees = {d.colonne for d in PiiService().detecter(transactions)}

    assert "client" not in reperees
    assert "categorie" not in reperees


def test_confidence_is_reported(detections: dict):
    for detection in detections.values():
        assert 0 < detection.confiance <= 1


def test_international_phone_numbers_are_recognised():
    table = pd.DataFrame({"tel": ["+33617025658", "+33612345678", "0612345678"]})

    detections = PiiService().detecter(table)

    assert detections[0].type_pii == TELEPHONE


def test_a_few_lookalike_values_do_not_make_a_sensitive_column():
    """Deux adresses dans une colonne de commentaires ne la rendent pas sensible."""
    table = pd.DataFrame(
        {"commentaire": ["rien a signaler"] * 18 + ["a@b.fr", "c@d.fr"]},
    )

    assert PiiService().detecter(table) == []


# --- La pseudonymisation ---------------------------------------------------


def test_tokens_are_stable_for_a_repeated_value():
    """La meme valeur doit toujours donner le meme jeton, sinon les jointures cassent."""
    table = pd.DataFrame({"email": ["a@b.fr", "c@d.fr", "a@b.fr"]})
    service = PiiService()

    masquee, _ = service.pseudonymiser(table, service.detecter(table))

    assert masquee["email"].iloc[0] == masquee["email"].iloc[2]
    assert masquee["email"].iloc[0] != masquee["email"].iloc[1]


def test_masked_emails_remain_valid_addresses():
    table = pd.DataFrame({"email": ["a@b.fr", "c@d.fr"]})
    service = PiiService()

    masquee, _ = service.pseudonymiser(table, service.detecter(table))

    assert masquee["email"].tolist() == ["email_001@masked.local", "email_002@masked.local"]


def test_missing_values_stay_missing():
    table = pd.DataFrame({"tel": ["0612345678", None, "0698765432"]})
    service = PiiService()

    masquee, _ = service.pseudonymiser(table, service.detecter(table))

    assert masquee["tel"].isna().sum() == 1


def test_no_original_value_survives_in_the_masked_table(collaborateurs: pd.DataFrame):
    service = PiiService()
    detections = service.detecter(collaborateurs)

    masquee, _ = service.pseudonymiser(collaborateurs, detections)

    contenu = masquee.to_csv(index=False)
    for colonne in ("email", "iban", "numero_securite_sociale"):
        for valeur in collaborateurs[colonne].dropna().astype(str).head(20):
            assert valeur not in contenu, f"{colonne} : {valeur} subsiste"


def test_business_columns_are_untouched(collaborateurs: pd.DataFrame):
    service = PiiService()

    masquee, _ = service.pseudonymiser(collaborateurs, service.detecter(collaborateurs))

    pd.testing.assert_series_equal(masquee["salaire_annuel"], collaborateurs["salaire_annuel"])
    pd.testing.assert_series_equal(masquee["service"], collaborateurs["service"])


# --- Ce que la base a le droit de conserver --------------------------------


def test_the_mapping_never_stores_the_original_value(collaborateurs: pd.DataFrame):
    """Seule l'empreinte est conservee : la base ne permet pas de reconstituer le fichier."""
    service = PiiService()
    detections = service.detecter(collaborateurs)

    _, pseudonymes = service.pseudonymiser(collaborateurs, detections)

    stocke = json.dumps([p.__dict__ for p in pseudonymes])
    for valeur in collaborateurs["email"].dropna().astype(str).head(20):
        assert valeur not in stocke
    assert all(len(p.empreinte) == 64 for p in pseudonymes)


def test_the_same_value_always_hashes_to_the_same_fingerprint():
    """C'est ce qui rend le jeton stable d'un fichier a l'autre."""
    table = pd.DataFrame({"email": ["a@b.fr", "c@d.fr"]})
    service = PiiService()

    _, premier = service.pseudonymiser(table, service.detecter(table))
    _, second = service.pseudonymiser(table, service.detecter(table))

    assert [p.empreinte for p in premier] == [p.empreinte for p in second]


# --- La garantie de bout en bout -------------------------------------------


def test_nothing_personal_reaches_the_llm_context(collaborateurs: pd.DataFrame):
    """Le test qui doit rendre vraie la phrase prononcee en soutenance.

    On masque, on profile le resultat, on construit le contexte destine au modele, et on
    verifie qu'aucune valeur personnelle du fichier d'origine ne s'y trouve.
    """
    agent = DataAgent()
    masquee, _ = agent.pseudonymiser(collaborateurs, agent.detecter_pii(collaborateurs))

    contexte = json.dumps(
        ProfilingService().llm_context(ProfilingService().profiler(masquee)), ensure_ascii=False
    )

    for colonne in ("email", "telephone", "iban", "numero_securite_sociale", "prenom", "nom"):
        for valeur in collaborateurs[colonne].dropna().astype(str).head(30):
            assert valeur not in contexte, f"{colonne} : « {valeur} » atteint le LLM"
