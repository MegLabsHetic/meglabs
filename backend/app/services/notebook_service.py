"""Export de la session en notebook Python executable.

C'est la contrepartie du pilier transparence : les outils sans code enferment
leurs utilisateurs, on prefere leur rendre le code. Ce qui sort d'ici se relit,
se modifie et s'execute sans la plateforme — y compris pour verifier qu'elle
n'a pas menti.

Le cout est faible pour une raison d'architecture : l'etat courant d'un fichier
est deja le rejeu ordonne d'actions parametrees. Ecrire l'equivalent pandas de
chaque action, c'est parcourir la meme liste une seconde fois.

**Deux precautions valent d'etre notees dans le notebook lui-meme.** La lecture
force le type texte, sinon pandas detruit les colonnes d'identite — un numero de
telephone perd son `+`, un matricule ses zeros initiaux. Et les valeurs
d'imputation sont celles calculees au moment de l'application, pas recalculees :
un notebook qui les recalculerait ne reproduirait pas le resultat montre.
"""

import json

# Chaque action de nettoyage, dans sa version pandas. `{c}` est le nom de la
# colonne, `{v}` la valeur figee dans les parametres.
EQUIVALENTS: dict[str, str] = {
    "supprimer_doublons": "df = df.drop_duplicates(ignore_index=True)",
    "normaliser_casse": (
        'df["{c}"] = (\n'
        '    df["{c}"].str.replace(r"\\s+", " ", regex=True).str.strip().str.capitalize()\n'
        ")"
    ),
    "uniformiser_dates": 'df["{c}"] = df["{c}"].map(uniformiser_date)',
    "imputer_mediane": 'df["{c}"] = df["{c}"].fillna({v})',
    "imputer_frequent": 'df["{c}"] = df["{c}"].fillna({v})',
    "supprimer_lignes_vides": 'df = df[df["{c}"].notna()].reset_index(drop=True)',
}

LIBELLES: dict[str, str] = {
    "supprimer_doublons": "Suppression des lignes strictement identiques",
    "normaliser_casse": "Uniformisation de la casse et des espaces",
    "uniformiser_dates": "Uniformisation des formats de date",
    "imputer_mediane": "Remplacement des valeurs absentes par la médiane",
    "imputer_frequent": "Remplacement des valeurs absentes par la plus fréquente",
    "supprimer_lignes_vides": "Suppression des lignes sans valeur",
}

AIDE_DATES = '''def uniformiser_date(valeur):
    """Essaie chaque format connu, et laisse la valeur intacte si aucun ne prend.

    Perdre une donnée pour cause de format inattendu serait pire que le défaut
    qu'on corrige : c'est pourquoi rien n'est vidé ici.
    """
    if pd.isna(valeur):
        return valeur
    for format_essaye in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return pd.to_datetime(str(valeur), format=format_essaye).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return valeur'''


class NotebookService:
    """Traduit une session en notebook Jupyter."""

    def exporter(self, rapport: dict, actions: list[dict]) -> dict:
        """Le notebook complet, prêt à être écrit dans un fichier `.ipynb`."""
        cellules = [
            self._markdown(self._entete(rapport)),
            self._code(self._chargement(rapport)),
        ]

        if actions:
            cellules.append(
                self._markdown("## Nettoyage\n\nLes corrections appliquées, dans l'ordre.")
            )
            if any(action["type"] == "uniformiser_dates" for action in actions):
                cellules.append(self._code(AIDE_DATES))
            cellules.extend(self._nettoyage(actions))

        questions = [q for q in rapport.get("questions", []) if q.get("sql")]
        if questions:
            cellules.append(
                self._markdown(
                    "## Questions posées\n\nChaque requête est celle qui a réellement été exécutée."
                )
            )
            cellules.extend(self._questions(questions))

        return self._carnet(cellules)

    # --- Les sections --------------------------------------------------------

    @staticmethod
    def _entete(rapport: dict) -> str:
        sources = "\n".join(
            f"- **{source['nom']}** — {source['lignes']} lignes, {source['colonnes']} colonnes, "
            f"qualité {source['score_qualite']}/100"
            for source in rapport.get("sources", [])
        )
        return (
            f"# {rapport.get('espace', 'Analyse')}\n\n"
            "Exporté depuis MegLabs. Ce notebook reproduit l'analyse sans la plateforme : "
            "les mêmes fichiers, les mêmes corrections, les mêmes requêtes.\n\n"
            f"## Sources\n\n{sources or '_aucune_'}\n\n"
            f"**Confiance : {rapport.get('confiance', {}).get('score', '—')}/100**"
        )

    @staticmethod
    def _chargement(rapport: dict) -> str:
        lignes = [
            "import duckdb",
            "import pandas as pd",
            "",
            "# Le type texte est force a la lecture. Sans cela pandas lit",
            "# +33617025658 comme un flottant et perd le +, et fait perdre a un",
            "# matricule ses zeros initiaux — apres quoi plus rien dans la colonne",
            "# ne ressemble a ce qu'elle contient, sans qu'aucune erreur soit levee.",
        ]
        for source in rapport.get("sources", []):
            variable = "df" if len(rapport.get("sources", [])) == 1 else source["nom"].split(".")[0]
            lignes.append(f'{variable} = pd.read_csv("{source["nom"]}", dtype=str)')
        return "\n".join(lignes)

    def _nettoyage(self, actions: list[dict]) -> list[dict]:
        cellules = []
        for action in actions:
            modele = EQUIVALENTS.get(action["type"])
            if modele is None:
                continue
            valeur = action.get("params", {}).get("valeur")
            code = modele.format(c=action.get("colonne") or "", v=repr(valeur))
            libelle = LIBELLES.get(action["type"], action["type"])
            colonne = f" — `{action['colonne']}`" if action.get("colonne") else ""
            cellules.append(
                self._markdown(
                    f"**{libelle}**{colonne} · {action.get('lignes_affectees', 0)} lignes touchées"
                )
            )
            cellules.append(self._code(code))
        return cellules

    def _questions(self, questions: list[dict]) -> list[dict]:
        cellules = []
        for echange in questions:
            cellules.append(
                self._markdown(f"### {echange['question']}\n\n> {echange.get('reponse', '')}")
            )
            requete = echange["sql"].replace('"""', '\\"\\"\\"')
            cellules.append(self._code(f'duckdb.sql("""\n{requete}\n""").df()'))
        return cellules

    # --- La structure du carnet ---------------------------------------------

    @staticmethod
    def _markdown(texte: str) -> dict:
        return {"cell_type": "markdown", "metadata": {}, "source": texte.splitlines(keepends=True)}

    @staticmethod
    def _code(texte: str) -> dict:
        return {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": texte.splitlines(keepends=True),
        }

    @staticmethod
    def _carnet(cellules: list[dict]) -> dict:
        return {
            "cells": cellules,
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python", "version": "3.12"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }

    def en_json(self, carnet: dict) -> str:
        return json.dumps(carnet, ensure_ascii=False, indent=1)
