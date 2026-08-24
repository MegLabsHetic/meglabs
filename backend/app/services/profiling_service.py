"""Profilage d'un jeu de donnees : types, statistiques, qualite.

Aucun appel LLM. Tout est calcule en Python : un modele de langage ne compte pas des
valeurs manquantes, il les estime. C'est aussi ce qui rend tenable la promesse de
souverainete — le calcul n'a pas besoin des donnees, donc les donnees ne sortent pas.
"""

import re

import numpy as np
import pandas as pd

# Libelles destines a l'utilisateur : en francais, sans jargon.
IDENTIFIANT = "identifiant"
ENTIER = "entier"
DECIMAL = "décimal"
DATE = "date"
BOOLEEN = "booléen"
CATEGORIE = "catégorie"
TEXTE = "texte"

MOTIFS_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})$")
TOKENS_BOOLEENS = {"0", "1", "true", "false", "vrai", "faux", "oui", "non", "o", "n"}

LONGUEUR_EXEMPLE_MAX = 80
NB_EXEMPLES = 3
NB_MODALITES = 5


class ProfilingService:
    """Decrit un jeu de donnees sans jamais en transmettre le contenu brut."""

    def profiler(self, table: pd.DataFrame) -> dict:
        """Profil complet : dimensions, doublons, qualite, et une entree par colonne."""
        doublons = int(table.duplicated().sum())
        colonnes = [self._profiler_colonne(table[nom]) for nom in table.columns]
        qualite = self._evaluer_qualite(table, doublons, colonnes)

        return {
            "nb_lignes": int(len(table)),
            "nb_colonnes": int(len(table.columns)),
            "doublons": {
                "nombre": doublons,
                "part": self._part(doublons, len(table)),
            },
            "score_qualite": qualite["score"],
            "explication_qualite": qualite["explication"],
            "colonnes": colonnes,
        }

    def llm_context(self, profil: dict) -> dict:
        """Representation compressee transmise au LLM.

        Point de passage unique : aucune ligne brute ne quitte le serveur, seulement
        des noms de colonnes, des types, trois exemples bornes et des agregats.
        """
        return {
            "nb_lignes": profil["nb_lignes"],
            "colonnes": [
                {
                    "nom": colonne["nom"],
                    "type": colonne["type"],
                    "cardinalite": colonne["cardinalite"],
                    "part_manquantes": colonne["part_manquantes"],
                    "exemples": colonne["exemples"],
                    "statistiques": colonne["statistiques"],
                    # Le modele doit savoir que la donnee est sale, sinon il ecrit du
                    # SQL juste sur des donnees fausses : sans cette ligne, un GROUP BY
                    # sur une colonne a modalites variantes rend « Data » et « data »
                    # comme deux services distincts.
                    "anomalies": colonne["anomalies"],
                }
                for colonne in profil["colonnes"]
            ],
        }

    # --- Profil d'une colonne ---------------------------------------------

    def _profiler_colonne(self, colonne: pd.Series) -> dict:
        renseignees = colonne.dropna()
        manquantes = int(colonne.isna().sum())
        type_semantique = self._type_semantique(colonne, renseignees)

        return {
            "nom": str(colonne.name),
            "type": type_semantique,
            "valeurs_manquantes": manquantes,
            "part_manquantes": self._part(manquantes, len(colonne)),
            "cardinalite": int(renseignees.nunique()),
            "exemples": self._exemples(renseignees),
            "statistiques": self._statistiques(renseignees, type_semantique),
            "anomalies": self._anomalies(renseignees, type_semantique),
        }

    # --- Anomalies detectables sans LLM ------------------------------------

    def _anomalies(self, renseignees: pd.Series, type_semantique: str) -> list[dict]:
        """Ce qui rend une colonne suspecte, et que le nettoyage saura corriger."""
        if renseignees.empty:
            return []
        if type_semantique == DATE:
            return self._anomalie_formats_de_date(renseignees)
        if type_semantique in (ENTIER, DECIMAL):
            return self._anomalie_valeurs_extremes(renseignees)
        if type_semantique in (CATEGORIE, TEXTE):
            return self._anomalie_modalites_variantes(renseignees)
        return []

    def _anomalie_formats_de_date(self, renseignees: pd.Series) -> list[dict]:
        valeurs = renseignees.astype(str).str.strip()
        formats = {self._forme_de_date(valeur) for valeur in valeurs} - {None}
        if len(formats) <= 1:
            return []
        return [
            {
                "type": "formats_multiples",
                "detail": f"{len(formats)} écritures de date coexistent dans la colonne.",
            }
        ]

    def _forme_de_date(self, valeur: str) -> str | None:
        for nom, motif in (
            ("AAAA-MM-JJ", r"^\d{4}-\d{2}-\d{2}$"),
            ("JJ/MM/AAAA", r"^\d{2}/\d{2}/\d{4}$"),
            ("JJ-MM-AAAA", r"^\d{2}-\d{2}-\d{4}$"),
        ):
            if re.match(motif, valeur):
                return nom
        return None

    def _anomalie_valeurs_extremes(self, renseignees: pd.Series) -> list[dict]:
        """Detection par ecart interquartile : insensible aux valeurs extremes elles-memes."""
        premier, troisieme = renseignees.quantile(0.25), renseignees.quantile(0.75)
        ecart = troisieme - premier
        if ecart == 0:
            return []
        extremes = renseignees[
            (renseignees < premier - 1.5 * ecart) | (renseignees > troisieme + 1.5 * ecart)
        ]
        if extremes.empty:
            return []
        return [
            {
                "type": "valeurs_extremes",
                "detail": f"{len(extremes)} valeur(s) très éloignée(s) du reste de la colonne.",
            }
        ]

    def _anomalie_modalites_variantes(self, renseignees: pd.Series) -> list[dict]:
        """« Data », « data » et « DATA  » comptent pour trois modalités distinctes."""
        valeurs = renseignees.astype(str)
        brutes = valeurs.nunique()
        normalisees = valeurs.str.strip().str.casefold().nunique()
        if brutes <= normalisees:
            return []
        return [
            {
                "type": "modalites_variantes",
                "detail": (
                    f"{brutes - normalisees} modalité(s) ne diffèrent que par la casse "
                    f"ou les espaces."
                ),
            }
        ]

    def _type_semantique(self, colonne: pd.Series, renseignees: pd.Series) -> str:
        if renseignees.empty:
            return TEXTE
        if pd.api.types.is_numeric_dtype(colonne):
            return self._type_numerique(renseignees)
        return self._type_textuel(renseignees)

    def _type_numerique(self, renseignees: pd.Series) -> str:
        entiers = bool(np.all(np.equal(np.mod(renseignees, 1), 0)))
        # Un indicateur 0/1 reste un booleen une fois converti en nombre.
        if entiers and set(renseignees.unique()) <= {0, 1}:
            return BOOLEEN
        if entiers and self._quasi_unique(renseignees, 0.98):
            return IDENTIFIANT
        return ENTIER if entiers else DECIMAL

    def _type_textuel(self, renseignees: pd.Series) -> str:
        valeurs = renseignees.astype(str).str.strip()
        if set(valeurs.str.casefold().unique()) <= TOKENS_BOOLEENS:
            return BOOLEEN
        if valeurs.str.match(MOTIFS_DATE).mean() > 0.8:
            return DATE
        # Seuil a 0.9 et non 1 : quelques lignes en double ne doivent pas empecher de
        # reconnaitre une colonne d'identifiants.
        if self._quasi_unique(valeurs, 0.9):
            return IDENTIFIANT
        if valeurs.nunique() <= max(20, len(valeurs) * 0.05):
            return CATEGORIE
        return TEXTE

    def _quasi_unique(self, valeurs: pd.Series, seuil: float) -> bool:
        return len(valeurs) > 0 and valeurs.nunique() / len(valeurs) >= seuil

    def _exemples(self, renseignees: pd.Series) -> list[str]:
        """Trois valeurs, echappees et bornees : ce sont les seules a atteindre le LLM."""
        return [self._borner(valeur) for valeur in renseignees.head(NB_EXEMPLES)]

    def _borner(self, valeur: object) -> str:
        texte = re.sub(r"\s+", " ", str(valeur)).strip()
        if len(texte) <= LONGUEUR_EXEMPLE_MAX:
            return texte
        return texte[: LONGUEUR_EXEMPLE_MAX - 1] + "…"

    def _statistiques(self, renseignees: pd.Series, type_semantique: str) -> dict:
        if renseignees.empty:
            return {}
        if type_semantique in (ENTIER, DECIMAL):
            return self._statistiques_numeriques(renseignees)
        return self._modalites_frequentes(renseignees)

    def _statistiques_numeriques(self, renseignees: pd.Series) -> dict:
        return {
            "minimum": round(float(renseignees.min()), 2),
            "maximum": round(float(renseignees.max()), 2),
            "moyenne": round(float(renseignees.mean()), 2),
            "mediane": round(float(renseignees.median()), 2),
            "ecart_type": round(float(renseignees.std(ddof=0)), 2),
        }

    def _modalites_frequentes(self, renseignees: pd.Series) -> dict:
        comptes = renseignees.astype(str).value_counts().head(NB_MODALITES)
        return {
            "modalites_frequentes": [
                {"valeur": self._borner(valeur), "occurrences": int(nombre)}
                for valeur, nombre in comptes.items()
            ]
        }

    # --- Qualite ------------------------------------------------------------

    def _evaluer_qualite(self, table: pd.DataFrame, doublons: int, colonnes: list[dict]) -> dict:
        """Score sur 100, accompagne de ce qui l'a fait baisser.

        Un score sans explication n'est pas actionnable : l'utilisateur doit savoir
        quoi corriger, et le rapport doit pouvoir le justifier.
        """
        penalites = [
            self._penalite_manquantes(colonnes),
            self._penalite_doublons(doublons, len(table)),
            self._penalite_colonnes_vides(colonnes),
            self._penalite_colonnes_constantes(colonnes),
            self._penalite_anomalies(colonnes),
        ]
        retenues = [penalite for penalite in penalites if penalite["impact"] < 0]
        score = max(0.0, min(100.0, 100.0 + sum(p["impact"] for p in retenues)))
        return {"score": round(score, 1), "explication": retenues}

    def _penalite_manquantes(self, colonnes: list[dict]) -> dict:
        part = float(np.mean([colonne["part_manquantes"] for colonne in colonnes] or [0.0]))
        return {
            "critere": "Valeurs manquantes",
            "impact": -round(part * 40, 1),
            "detail": f"{part:.1%} des valeurs sont absentes en moyenne par colonne.",
        }

    def _penalite_doublons(self, doublons: int, nb_lignes: int) -> dict:
        part = self._part(doublons, nb_lignes)
        return {
            "critere": "Lignes en double",
            "impact": -round(part * 30, 1),
            "detail": f"{doublons} ligne(s) identique(s) a une autre, soit {part:.1%}.",
        }

    def _penalite_anomalies(self, colonnes: list[dict]) -> dict:
        """Formats melanges, modalites variantes, valeurs extremes.

        Sans ce critere, un fichier truffe d'incoherences de saisie afficherait un score
        proche de 100 des lors qu'il est complet — ce que personne ne croirait.
        """
        touchees = [colonne["nom"] for colonne in colonnes if colonne["anomalies"]]
        part = self._part(len(touchees), len(colonnes))
        return {
            "critere": "Incohérences de saisie",
            "impact": -round(part * 35, 1),
            "detail": (
                f"{len(touchees)} colonne(s) présentent des formats mélangés, "
                f"des modalités variantes ou des valeurs extrêmes."
            ),
        }

    def _penalite_colonnes_vides(self, colonnes: list[dict]) -> dict:
        vides = [c["nom"] for c in colonnes if c["part_manquantes"] > 0.5]
        part = self._part(len(vides), len(colonnes))
        return {
            "critere": "Colonnes quasi vides",
            "impact": -round(part * 20, 1),
            "detail": f"{len(vides)} colonne(s) a plus de la moitie de valeurs absentes.",
        }

    def _penalite_colonnes_constantes(self, colonnes: list[dict]) -> dict:
        constantes = [c["nom"] for c in colonnes if c["cardinalite"] <= 1]
        part = self._part(len(constantes), len(colonnes))
        return {
            "critere": "Colonnes sans variation",
            "impact": -round(part * 10, 1),
            "detail": f"{len(constantes)} colonne(s) ne contiennent qu'une seule valeur.",
        }

    def _part(self, nombre: int, total: int) -> float:
        return round(nombre / total, 4) if total else 0.0
