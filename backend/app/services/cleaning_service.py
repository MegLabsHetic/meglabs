"""Nettoyage guide : ce qu'on propose de corriger, et ce que ca changerait.

**Aucun appel a un modele de langage.** Les defauts sont dans le profil, qui les a
comptes ; proposer une correction est une lecture de ce profil. Demander a un
modele quelles colonnes nettoyer reviendrait a payer un appel pour une reponse
moins fiable — il n'aura jamais compte les doublons, il les aura estimes.

**L'impact est calcule avant application, pas apres.** « 12 lignes seront
supprimees » se verifie en comptant ; c'est ce chiffre qui permet a quelqu'un de
decider, et c'est ce qui separe une proposition d'un bouton magique.

**Les valeurs calculees sont figees dans les parametres.** Une imputation par la
mediane doit rendre le meme resultat au premier rejeu et au centieme : si la
mediane etait recalculee a chaque fois, elle deriverait au fil des actions
precedentes. C'est ce que le modele `CleaningAction` demande explicitement.
"""

import re
from dataclasses import dataclass, field

import pandas as pd

# Types d'actions. Ce sont les valeurs stockees en base : les renommer casserait
# le rejeu des actions deja enregistrees.
DOUBLONS = "supprimer_doublons"
CASSE = "normaliser_casse"
DATES = "uniformiser_dates"
MEDIANE = "imputer_mediane"
FREQUENT = "imputer_frequent"
VIDES = "supprimer_lignes_vides"

# En dessous, corriger coute plus d'attention que le defaut n'en merite.
SEUIL_MANQUANTES = 0.02
SEUIL_LIGNES_VIDES = 0.3

FORMATS_DATE = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
ESPACES = re.compile(r"\s+")


@dataclass
class Proposition:
    """Une correction possible, son motif, et ce qu'elle changerait."""

    type: str
    libelle: str
    raison: str
    colonne: str | None = None
    lignes_affectees: int = 0
    params: dict = field(default_factory=dict)

    def en_dict(self) -> dict:
        return {
            "type": self.type,
            "libelle": self.libelle,
            "raison": self.raison,
            "colonne": self.colonne,
            "lignes_affectees": self.lignes_affectees,
            "params": self.params,
        }


class NettoyageService:
    """Propose des corrections depuis un profil, et les rejoue a l'identique."""

    # --- Ce qu'on propose ----------------------------------------------------

    def proposer(self, table: pd.DataFrame, profil: dict) -> list[Proposition]:
        """Les corrections que les defauts detectes justifient, du plus lourd au moins.

        L'ordre compte a l'affichage : quelqu'un qui ne lit que la premiere ligne
        doit tomber sur ce qui coute le plus de qualite.
        """
        propositions = [
            *self._doublons(table, profil),
            *self._par_colonne(table, profil),
        ]
        return sorted(propositions, key=lambda p: -p.lignes_affectees)

    def _doublons(self, table: pd.DataFrame, profil: dict) -> list[Proposition]:
        nombre = profil.get("doublons", {}).get("nombre", 0)
        if nombre == 0:
            return []
        return [
            Proposition(
                type=DOUBLONS,
                libelle="Supprimer les lignes strictement identiques",
                raison=f"{nombre} ligne(s) apparaissent plusieurs fois à l'identique.",
                lignes_affectees=nombre,
            )
        ]

    def _par_colonne(self, table: pd.DataFrame, profil: dict) -> list[Proposition]:
        propositions: list[Proposition] = []
        for colonne in profil.get("colonnes", []):
            nom = colonne["nom"]
            if nom not in table.columns:
                continue
            propositions.extend(self._pour(table[nom], colonne))
        return propositions

    def _pour(self, valeurs: pd.Series, profil: dict) -> list[Proposition]:
        """Les corrections que cette colonne justifie, selon ses anomalies."""
        anomalies = {anomalie["type"] for anomalie in profil.get("anomalies", [])}
        propositions: list[Proposition] = []

        if "modalites_variantes" in anomalies:
            propositions.append(self._casse(valeurs, profil["nom"]))
        if "formats_multiples" in anomalies:
            propositions.append(self._dates(valeurs, profil["nom"]))

        manquante = self._imputation(valeurs, profil)
        if manquante is not None:
            propositions.append(manquante)

        return [p for p in propositions if p.lignes_affectees > 0]

    # --- Une proposition par defaut -----------------------------------------

    def _casse(self, valeurs: pd.Series, nom: str) -> Proposition:
        """La meme valeur ecrite de plusieurs facons compte comme plusieurs."""
        normalisees = self._normaliser(valeurs)
        distinctes_avant = valeurs.dropna().nunique()
        distinctes_apres = normalisees.dropna().nunique()
        affectees = int((valeurs.fillna("") != normalisees.fillna("")).sum())

        return Proposition(
            type=CASSE,
            libelle=f"Uniformiser la casse et les espaces de « {nom} »",
            raison=(
                f"{distinctes_avant} écritures différentes pour {distinctes_apres} "
                "valeurs réelles : sans correction, un regroupement les compte séparément."
            ),
            colonne=nom,
            lignes_affectees=affectees,
        )

    def _dates(self, valeurs: pd.Series, nom: str) -> Proposition:
        converties = self._convertir_dates(valeurs)
        affectees = int((valeurs.notna() & (valeurs.fillna("") != converties.fillna(""))).sum())

        return Proposition(
            type=DATES,
            libelle=f"Ramener « {nom} » à un format de date unique",
            raison=(
                "Plusieurs formats coexistent. Une comparaison ou un tri chronologique "
                "donne un résultat faux tant qu'ils ne sont pas uniformisés."
            ),
            colonne=nom,
            lignes_affectees=affectees,
        )

    def _imputation(self, valeurs: pd.Series, profil: dict) -> Proposition | None:
        """Remplacer les valeurs absentes, ou supprimer les lignes s'il y en a trop.

        Au-dela d'un tiers de valeurs manquantes, imputer inventerait plus de
        donnees qu'il n'en conserverait : on propose alors de retirer les lignes,
        et l'utilisateur tranche.
        """
        part = profil.get("part_manquantes", 0)
        manquantes = int(valeurs.isna().sum())
        if part < SEUIL_MANQUANTES or manquantes == 0:
            return None

        nom = profil["nom"]
        if part > SEUIL_LIGNES_VIDES:
            return Proposition(
                type=VIDES,
                libelle=f"Supprimer les lignes sans « {nom} »",
                raison=(
                    f"{part * 100:.1f} % des valeurs sont absentes : les remplacer "
                    "inventerait plus de données que la colonne n'en contient."
                ),
                colonne=nom,
                lignes_affectees=manquantes,
            )

        if profil.get("type") in ("entier", "décimal"):
            mediane = pd.to_numeric(valeurs, errors="coerce").median()
            if pd.isna(mediane):
                return None
            return Proposition(
                type=MEDIANE,
                libelle=f"Remplacer les valeurs absentes de « {nom} » par la médiane",
                raison=(
                    f"{manquantes} valeur(s) absente(s). La médiane ({mediane:g}) est "
                    "préférée à la moyenne : elle ne bouge pas avec les valeurs extrêmes."
                ),
                colonne=nom,
                lignes_affectees=manquantes,
                # Figee ici : recalculee au rejeu, elle deriverait selon les
                # actions appliquees avant celle-ci.
                params={"valeur": float(mediane)},
            )

        frequente = valeurs.dropna().mode()
        if frequente.empty:
            return None
        return Proposition(
            type=FREQUENT,
            libelle=f"Remplacer les valeurs absentes de « {nom} » par la plus fréquente",
            raison=f"{manquantes} valeur(s) absente(s). La plus fréquente est « {frequente[0]} ».",
            colonne=nom,
            lignes_affectees=manquantes,
            params={"valeur": str(frequente[0])},
        )

    # --- Le rejeu ------------------------------------------------------------

    def appliquer(self, table: pd.DataFrame, actions: list[dict]) -> pd.DataFrame:
        """Rejoue les actions dans l'ordre sur une copie.

        La table d'origine n'est jamais modifiee : c'est ce qui rend chaque action
        reversible sans conserver d'instantane intermediaire.
        """
        courante = table.copy()
        for action in actions:
            courante = self._rejouer(courante, action)
        return courante

    def _rejouer(self, table: pd.DataFrame, action: dict) -> pd.DataFrame:
        type_action = action.get("type") or action.get("action_type")
        colonne = action.get("colonne") or action.get("column_name")
        params = action.get("params") or {}

        if type_action == DOUBLONS:
            return table.drop_duplicates(ignore_index=True)
        if colonne is None or colonne not in table.columns:
            # Une colonne disparue rend l'action sans objet ; l'ignorer vaut mieux
            # que d'interrompre le rejeu de toutes les suivantes.
            return table

        if type_action == CASSE:
            table[colonne] = self._normaliser(table[colonne])
        elif type_action == DATES:
            table[colonne] = self._convertir_dates(table[colonne])
        elif type_action in (MEDIANE, FREQUENT):
            table[colonne] = table[colonne].fillna(params.get("valeur"))
        elif type_action == VIDES:
            table = table[table[colonne].notna()].reset_index(drop=True)
        return table

    # --- Transformations elementaires ---------------------------------------

    @staticmethod
    def _normaliser(valeurs: pd.Series) -> pd.Series:
        """Espaces reduits, bords coupes, premiere lettre en capitale.

        On ne met pas tout en minuscules : la colonne reste affichee a l'ecran, et
        « ressources humaines » se lit moins bien que « Ressources humaines ».
        """
        texte = valeurs.astype("object").where(valeurs.notna())
        propre = texte.map(
            lambda valeur: (
                ESPACES.sub(" ", str(valeur)).strip().capitalize() if pd.notna(valeur) else valeur
            )
        )
        return propre

    @staticmethod
    def _convertir_dates(valeurs: pd.Series) -> pd.Series:
        """Chaque format connu est essaye ; la sortie est en ISO.

        Une valeur qu'aucun format ne reconnait est laissee telle quelle plutot
        que vidée : perdre une donnee pour cause de format inattendu serait pire
        que le defaut qu'on corrige.
        """

        def convertir(valeur: object) -> object:
            if pd.isna(valeur):
                return valeur
            for format_essaye in FORMATS_DATE:
                try:
                    return pd.to_datetime(str(valeur), format=format_essaye).strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    continue
            return valeur

        return valeurs.map(convertir)
