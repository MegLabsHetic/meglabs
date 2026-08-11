"""Detection et pseudonymisation des donnees personnelles.

Aucun appel LLM : la detection est faite de motifs et d'heuristiques. C'est ce qui rend
tenable la phrase « aucune donnee personnelle n'atteint jamais le LLM » — un service qui
enverrait les colonnes a un modele pour lui demander si elles sont sensibles aurait deja
divulgue ce qu'il cherchait a proteger.

La pseudonymisation est volontairement a sens unique : seule l'empreinte de la valeur
d'origine est conservee, jamais la valeur. Elle suffit a rendre le jeton stable — la meme
valeur donnera toujours le meme jeton — sans permettre de reconstituer le fichier
d'origine depuis la base.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

from data.noms import NOMS, PRENOMS

# Libelles destines a l'utilisateur.
EMAIL = "adresse e-mail"
TELEPHONE = "téléphone"
IBAN = "IBAN"
SECURITE_SOCIALE = "numéro de sécurité sociale"
NOM_PERSONNE = "nom de personne"

MOTIFS = {
    EMAIL: re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE),
    TELEPHONE: re.compile(r"^(?:0[1-9]\d{8}|\+33[1-9]\d{8})$"),
    IBAN: re.compile(r"^FR\d{2}[0-9A-Z]{23}$", re.IGNORECASE),
    SECURITE_SOCIALE: re.compile(r"^\d{13,15}$"),
}

# Un motif doit couvrir l'essentiel de la colonne : quelques valeurs isolees qui
# ressemblent a un telephone ne font pas une colonne de telephones.
SEUIL_MOTIF = 0.8
SEUIL_NOMS = 0.5

PREFIXES = {
    EMAIL: "email",
    TELEPHONE: "TEL",
    IBAN: "IBAN",
    SECURITE_SOCIALE: "NIR",
    NOM_PERSONNE: "PERS",
}


def _sans_accents(valeur: str) -> str:
    decompose = unicodedata.normalize("NFKD", valeur)
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold()


REPERTOIRE = {_sans_accents(nom) for nom in PRENOMS + NOMS}


@dataclass(frozen=True)
class Detection:
    """Une colonne reconnue comme sensible."""

    colonne: str
    type_pii: str
    confiance: float
    exemple_masque: str


@dataclass(frozen=True)
class Pseudonyme:
    """Correspondance a stocker : l'empreinte de la valeur, jamais la valeur."""

    colonne: str
    empreinte: str
    jeton: str


class PiiService:
    """Repere les colonnes sensibles et les remplace par des jetons stables."""

    def detecter(self, table: pd.DataFrame) -> list[Detection]:
        """Liste les colonnes portant des donnees personnelles."""
        detections = []
        for nom in table.columns:
            detection = self._detecter_colonne(table[nom])
            if detection is not None:
                detections.append(detection)
        return detections

    def pseudonymiser(
        self, table: pd.DataFrame, detections: list[Detection]
    ) -> tuple[pd.DataFrame, list[Pseudonyme]]:
        """Remplace les valeurs sensibles par des jetons, et retourne le mapping."""
        masquee = table.copy()
        pseudonymes: list[Pseudonyme] = []
        for detection in detections:
            colonne, correspondances = self._masquer_colonne(
                table[detection.colonne], detection.type_pii
            )
            masquee[detection.colonne] = colonne
            pseudonymes.extend(
                Pseudonyme(detection.colonne, empreinte, jeton)
                for empreinte, jeton in correspondances.items()
            )
        return masquee, pseudonymes

    # --- Detection ---------------------------------------------------------

    def _detecter_colonne(self, colonne: pd.Series) -> Detection | None:
        valeurs = colonne.dropna().astype(str).str.strip()
        if valeurs.empty:
            return None

        for type_pii, motif in MOTIFS.items():
            taux = float(valeurs.str.match(motif).mean())
            if taux >= SEUIL_MOTIF:
                return self._detection(colonne.name, type_pii, taux, valeurs)

        taux_noms = self._taux_de_noms(valeurs)
        if taux_noms >= SEUIL_NOMS:
            return self._detection(colonne.name, NOM_PERSONNE, taux_noms, valeurs)
        return None

    def _taux_de_noms(self, valeurs: pd.Series) -> float:
        """Part des valeurs dont le premier mot figure au repertoire des noms francais."""
        premiers_mots = valeurs.str.split().str[0].dropna()
        if premiers_mots.empty:
            return 0.0
        reconnus = premiers_mots.map(lambda mot: _sans_accents(mot) in REPERTOIRE)
        return float(reconnus.mean())

    def _detection(self, nom: object, type_pii: str, taux: float, valeurs: pd.Series) -> Detection:
        return Detection(
            colonne=str(nom),
            type_pii=type_pii,
            confiance=round(taux, 3),
            exemple_masque=self._jeton(type_pii, 1),
        )

    # --- Pseudonymisation --------------------------------------------------

    def _masquer_colonne(
        self, colonne: pd.Series, type_pii: str
    ) -> tuple[pd.Series, dict[str, str]]:
        """Un jeton par valeur distincte, numerote dans l'ordre d'apparition."""
        jetons: dict[str, str] = {}
        correspondances: dict[str, str] = {}

        for valeur in colonne.dropna().astype(str):
            if valeur in jetons:
                continue
            jeton = self._jeton(type_pii, len(jetons) + 1)
            jetons[valeur] = jeton
            correspondances[self._empreinte(valeur)] = jeton

        return colonne.map(lambda v: jetons.get(str(v)) if pd.notna(v) else v), correspondances

    def _jeton(self, type_pii: str, rang: int) -> str:
        prefixe = PREFIXES[type_pii]
        if type_pii == EMAIL:
            # Le jeton doit rester une adresse valide, sinon les traitements en aval
            # qui verifient le format rejetteraient la donnee pseudonymisee.
            return f"{prefixe}_{rang:03d}@masked.local"
        return f"{prefixe}_{rang:03d}"

    def _empreinte(self, valeur: str) -> str:
        return hashlib.sha256(valeur.encode("utf-8")).hexdigest()
