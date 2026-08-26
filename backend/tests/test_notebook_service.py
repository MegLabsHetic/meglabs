"""L'export notebook : ce qu'il reproduit, et ce qu'il ne trahit pas.

Un notebook exporte n'a de valeur que s'il tourne. Ces tests verrouillent les
deux choses qui le casseraient silencieusement : un format que Jupyter refuse, et
un code qui ne reproduit pas ce que la plateforme a montre.
"""

import json

from app.services.notebook_service import NotebookService


def carnet(rapport: dict | None = None, actions: list[dict] | None = None) -> dict:
    modele = {
        "espace": "Analyse RH",
        "sources": [
            {"nom": "collaborateurs.csv", "lignes": 232, "colonnes": 15, "score_qualite": 88.5}
        ],
        "questions": [],
        "confiance": {"score": 84.2},
    }
    return NotebookService().exporter(rapport or modele, actions or [])


def sources(cellules: list[dict], type_cellule: str) -> str:
    return "\n".join(
        "".join(cellule["source"]) for cellule in cellules if cellule["cell_type"] == type_cellule
    )


# --- Le format ---------------------------------------------------------------


def test_the_export_is_a_valid_notebook_document():
    """Un `.ipynb` mal forme ne s'ouvre pas, et rien ne le signale avant le clic."""
    resultat = carnet()
    assert resultat["nbformat"] == 4
    assert resultat["metadata"]["kernelspec"]["name"] == "python3"
    assert all(c["cell_type"] in ("markdown", "code") for c in resultat["cells"])
    assert all("source" in c for c in resultat["cells"])


def test_code_cells_carry_the_fields_jupyter_expects():
    code = [c for c in carnet()["cells"] if c["cell_type"] == "code"]
    assert all("outputs" in c and "execution_count" in c for c in code)


def test_the_document_survives_a_round_trip_through_json():
    service = NotebookService()
    rendu = service.en_json(carnet())
    assert json.loads(rendu)["nbformat"] == 4


def test_accents_are_not_escaped_into_unreadable_sequences():
    assert "qualité" in NotebookService().en_json(carnet())


# --- Ce qu'il reproduit ------------------------------------------------------


def test_reading_forces_text_so_identity_columns_survive():
    """Le meme piege que partout ailleurs, et il doit etre corrige DANS l'export.

    Un notebook qui lit sans `dtype=str` perd le `+` d'un telephone et les zeros
    initiaux d'un matricule — donc il ne reproduit pas ce que la plateforme a
    montre, tout en ayant l'air correct.
    """
    code = sources(carnet()["cells"], "code")
    assert "dtype=str" in code
    assert "collaborateurs.csv" in code


def test_each_cleaning_action_becomes_its_pandas_equivalent():
    actions = [
        {"type": "supprimer_doublons", "colonne": None, "lignes_affectees": 12, "params": {}},
        {"type": "normaliser_casse", "colonne": "service", "lignes_affectees": 97, "params": {}},
    ]
    code = sources(carnet(actions=actions)["cells"], "code")
    assert "drop_duplicates" in code
    assert 'df["service"]' in code


def test_the_frozen_imputation_value_is_written_not_recomputed():
    """Un notebook qui recalculerait la mediane ne reproduirait pas le resultat.

    Elle depend des actions appliquees avant elle : recalculee, elle deriverait.
    """
    actions = [
        {
            "type": "imputer_mediane",
            "colonne": "salaire_annuel",
            "lignes_affectees": 17,
            "params": {"valeur": 43200.0},
        }
    ]
    code = sources(carnet(actions=actions)["cells"], "code")
    assert "43200.0" in code
    assert "median()" not in code


def test_the_date_helper_appears_only_when_dates_are_cleaned():
    sans = sources(carnet(actions=[{"type": "supprimer_doublons", "params": {}}])["cells"], "code")
    assert "uniformiser_date" not in sans

    avec = sources(
        carnet(
            actions=[
                {
                    "type": "uniformiser_dates",
                    "colonne": "date_embauche",
                    "lignes_affectees": 70,
                    "params": {},
                }
            ]
        )["cells"],
        "code",
    )
    assert "def uniformiser_date" in avec


def test_each_question_carries_the_query_that_actually_ran():
    rapport = {
        "espace": "Analyse",
        "sources": [{"nom": "x.csv", "lignes": 1, "colonnes": 1, "score_qualite": 90}],
        "questions": [
            {
                "question": "Combien par service ?",
                "reponse": "63 en RH…",
                "sql": "SELECT service, COUNT(*) FROM collaborateurs GROUP BY service",
            }
        ],
        "confiance": {"score": 90},
    }
    resultat = carnet(rapport)
    assert "Combien par service ?" in sources(resultat["cells"], "markdown")
    assert "GROUP BY service" in sources(resultat["cells"], "code")


def test_a_question_without_a_query_is_left_out():
    """Une salutation ou un refus n'a pas de code a rejouer."""
    rapport = {
        "espace": "Analyse",
        "sources": [{"nom": "x.csv", "lignes": 1, "colonnes": 1, "score_qualite": 90}],
        "questions": [{"question": "Bonjour", "reponse": "Bonjour.", "sql": None}],
        "confiance": {"score": 90},
    }
    assert "Bonjour" not in sources(carnet(rapport)["cells"], "markdown")


def test_an_unknown_action_type_is_skipped_rather_than_written_wrong():
    """Un type ajoute plus tard sans equivalent pandas ne doit pas produire de
    code faux : mieux vaut une cellule manquante qu'une cellule mensongere."""
    actions = [{"type": "type_futur_inconnu", "colonne": "x", "params": {}}]
    code = sources(carnet(actions=actions)["cells"], "code")
    assert "type_futur_inconnu" not in code
