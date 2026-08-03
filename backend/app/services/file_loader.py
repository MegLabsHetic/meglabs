"""Chargement d'un fichier en DataFrame, sans corrompre les colonnes d'identite.

Laisse a lui-meme, pandas convertit en nombres tout ce qui en a l'air. Un telephone
`+33617025658` devient alors le flottant `33617025658.0` et perd son `+`, un numero de
securite sociale commencant par zero perd ce zero. Ces colonnes deviennent alors
invisibles pour la detection de donnees personnelles, sans qu'aucune erreur ne soit
levee : la banniere ne s'affiche jamais et personne ne comprend pourquoi.

La strategie est donc l'inverse de celle de pandas : tout est lu en texte, puis chaque
colonne n'est convertie en nombre que si la conversion ne perd rien.
"""

import csv
import re
from pathlib import Path

import pandas as pd

ENTIER = re.compile(r"^-?\d+$")
DECIMAL = re.compile(r"^-?\d+[.,]\d+$")
# Un zero initial ou un `+` porte une information qu'un nombre ne sait pas representer.
SIGNIFIANT = re.compile(r"^(\+|0\d)")
SEPARATEURS = ",;\t|"


class FileLoader:
    """Transforme un fichier CSV ou Excel en DataFrame exploitable."""

    EXTENSIONS = (".csv", ".xlsx", ".xls")

    def charger(self, chemin: str | Path) -> pd.DataFrame:
        """Lit le fichier en texte, puis convertit ce qui peut l'etre sans perte."""
        table = self._lire_en_texte(Path(chemin))
        for colonne in table.columns:
            table[colonne] = self._convertir_si_sans_perte(table[colonne])
        return table

    def _lire_en_texte(self, chemin: Path) -> pd.DataFrame:
        extension = chemin.suffix.lower()
        if extension == ".csv":
            return self._lire_csv(chemin)
        if extension in (".xlsx", ".xls"):
            return pd.read_excel(chemin, dtype=str)
        raise ValueError(
            f"Format non pris en charge : « {extension} ». "
            f"Formats acceptes : {', '.join(self.EXTENSIONS)}."
        )

    def _lire_csv(self, chemin: Path) -> pd.DataFrame:
        """Detecte le separateur : un export francais utilise le point-virgule.

        Sans cette detection, un fichier `nom;age` se lirait comme une colonne unique
        et l'utilisateur verrait un profil absurde sans comprendre pourquoi.
        """
        return pd.read_csv(chemin, dtype=str, sep=self._detecter_separateur(chemin))

    def _detecter_separateur(self, chemin: Path) -> str:
        """Choisit parmi une liste fermee de separateurs plausibles.

        Laisse libre, le renifleur elit n'importe quel caractere frequent — sur une
        colonne unique de chiffres il peut retenir « 0 » et decouper les valeurs.
        """
        with chemin.open(encoding="utf-8", errors="replace") as fichier:
            echantillon = fichier.read(8192)
        try:
            return csv.Sniffer().sniff(echantillon, delimiters=SEPARATEURS).delimiter
        except csv.Error:
            return ","

    def _convertir_si_sans_perte(self, colonne: pd.Series) -> pd.Series:
        valeurs = colonne.dropna().astype(str).str.strip()
        if valeurs.empty or not self._entierement_numerique(valeurs):
            return colonne
        if valeurs.str.match(SIGNIFIANT).any():
            return colonne
        # `.str` propage les valeurs manquantes ; `astype(str)` les transformerait en
        # la chaine « nan », que la conversion numerique refuserait ensuite.
        normalisee = colonne.str.strip().str.replace(",", ".", regex=False)
        return pd.to_numeric(normalisee)

    def _entierement_numerique(self, valeurs: pd.Series) -> bool:
        return bool((valeurs.str.match(ENTIER) | valeurs.str.match(DECIMAL)).all())
