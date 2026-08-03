"""Le chargement ne doit jamais detruire une colonne d'identite en la convertissant."""

from pathlib import Path

import pandas as pd
import pytest

from app.services.file_loader import FileLoader

DATASETS = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def loader() -> FileLoader:
    return FileLoader()


def ecrire_csv(chemin: Path, contenu: str) -> Path:
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


def test_international_phone_numbers_keep_their_plus(loader: FileLoader, tmp_path: Path):
    fichier = ecrire_csv(
        tmp_path / "t.csv", "telephone\n+33617025658\n+33612345678\n+33698765432\n"
    )

    table = loader.charger(fichier)

    assert table["telephone"].tolist() == ["+33617025658", "+33612345678", "+33698765432"]


def test_leading_zeros_survive(loader: FileLoader, tmp_path: Path):
    """Un NIR ou un code postal qui perd son zero initial devient une autre valeur."""
    fichier = ecrire_csv(tmp_path / "t.csv", "nir\n0123456789012\n0987654321098\n")

    table = loader.charger(fichier)

    assert table["nir"].tolist() == ["0123456789012", "0987654321098"]


def test_genuine_numbers_are_still_converted(loader: FileLoader, tmp_path: Path):
    fichier = ecrire_csv(tmp_path / "t.csv", "salaire\n42000\n38500\n51000\n")

    table = loader.charger(fichier)

    assert pd.api.types.is_numeric_dtype(table["salaire"])
    assert table["salaire"].sum() == 131_500


def test_a_french_export_is_read_with_the_right_separator(loader: FileLoader, tmp_path: Path):
    """Un export francais separe par des point-virgules et ecrit « 1234,56 ».

    Sans detection du separateur, tout se retrouverait dans une colonne unique.
    """
    fichier = ecrire_csv(tmp_path / "t.csv", "nom;montant\nDupont;1234,56\nMartin;78,90\n")

    table = loader.charger(fichier)

    assert list(table.columns) == ["nom", "montant"]
    assert pd.api.types.is_numeric_dtype(table["montant"])
    assert table["montant"].iloc[0] == pytest.approx(1234.56)


def test_a_column_mixing_text_and_numbers_stays_text(loader: FileLoader, tmp_path: Path):
    fichier = ecrire_csv(tmp_path / "t.csv", "reference\nA12\n34\nB56\n")

    table = loader.charger(fichier)

    assert not pd.api.types.is_numeric_dtype(table["reference"])


def test_an_unsupported_format_is_refused_in_french(loader: FileLoader, tmp_path: Path):
    fichier = ecrire_csv(tmp_path / "t.json", "{}")

    with pytest.raises(ValueError, match="Format non pris en charge"):
        loader.charger(fichier)


def test_the_real_dataset_keeps_its_sensitive_columns_as_text(loader: FileLoader):
    """Verification sur le fichier reellement livre, pas sur un cas fabrique."""
    table = loader.charger(DATASETS / "collaborateurs.csv")

    telephones = table["telephone"].dropna().astype(str)
    assert telephones.str.startswith("+33").any()
    assert not pd.api.types.is_numeric_dtype(table["numero_securite_sociale"])
    assert not pd.api.types.is_numeric_dtype(table["iban"])
    # Le salaire, lui, est bien un nombre : la prudence ne doit pas tout figer en texte.
    assert pd.api.types.is_numeric_dtype(table["salaire_annuel"])
