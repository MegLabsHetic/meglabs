"""Generation des jeux de donnees synthetiques de demonstration.

Les imperfections de ces fichiers sont VOLONTAIRES : elles sont la matiere sur
laquelle le profilage, le nettoyage et la detection PII se demontrent. Ne jamais les
« corriger » — un dataset propre ne prouve rien.

Usage, depuis `backend/` :
    python -m data.generate_datasets
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from data.noms import NOMS, PRENOMS

SERVICES = ("Data", "Commercial", "Finance", "Technique", "Ressources Humaines")
POSTES = ("Consultant", "Analyste", "Ingenieur", "Manager", "Charge de mission")
CATEGORIES = ("Conseil", "Formation", "Licence", "Maintenance", "Audit")
CLIENTS = (
    "Groupe Lorrain",
    "Atelier Bastide",
    "Verne Industries",
    "Cabinet Ferrand",
    "Nord Logistique",
    "Maison Delaunay",
    "Sigma Sante",
    "Orion Energie",
)


@dataclass(frozen=True)
class GenerationConfig:
    """Parametres de generation. La graine fixe rend le resultat reproductible."""

    seed: int = 42
    nb_collaborateurs: int = 220
    nb_transactions: int = 3000
    part_valeurs_manquantes: float = 0.08
    part_dates_mal_formatees: float = 0.30
    nb_doublons: int = 12
    nb_valeurs_aberrantes: int = 8
    nb_transactions_orphelines: int = 15


class DatasetGenerator:
    """Produit `collaborateurs.csv` et `transactions.csv`, imperfections comprises."""

    def __init__(self, config: GenerationConfig | None = None) -> None:
        self._config = config or GenerationConfig()
        self._rng = np.random.default_rng(self._config.seed)

    def generer(self, destination: Path) -> dict[str, Path]:
        """Ecrit les deux fichiers et retourne leurs chemins."""
        destination.mkdir(parents=True, exist_ok=True)

        collaborateurs = self._degrader_collaborateurs(self._construire_collaborateurs())
        identifiants = collaborateurs["id_collaborateur"].tolist()
        transactions = self._degrader_transactions(self._construire_transactions(identifiants))

        chemins = {
            "collaborateurs": destination / "collaborateurs.csv",
            "transactions": destination / "transactions.csv",
        }
        collaborateurs.to_csv(chemins["collaborateurs"], index=False, encoding="utf-8")
        transactions.to_csv(chemins["transactions"], index=False, encoding="utf-8")
        return chemins

    # --- Construction des donnees propres ---------------------------------

    def _construire_collaborateurs(self) -> pd.DataFrame:
        nb = self._config.nb_collaborateurs
        prenoms = self._rng.choice(PRENOMS, nb)
        noms = self._rng.choice(NOMS, nb)
        anciennete = self._rng.integers(0, 21, nb)

        return pd.DataFrame(
            {
                "id_collaborateur": [f"C{i:04d}" for i in range(1, nb + 1)],
                "prenom": prenoms,
                "nom": noms,
                "email": [
                    f"{p}.{n}@meglabs.example".lower() for p, n in zip(prenoms, noms, strict=True)
                ],
                "telephone": [self._telephone() for _ in range(nb)],
                "iban": [self._iban() for _ in range(nb)],
                "numero_securite_sociale": [self._nir() for _ in range(nb)],
                "service": self._rng.choice(SERVICES, nb),
                "poste": self._rng.choice(POSTES, nb),
                "date_embauche": [self._date_embauche(a) for a in anciennete],
                "anciennete_annees": anciennete,
                "salaire_annuel": self._salaires(nb),
                "absences_jours": self._rng.poisson(6, nb),
                "score_performance": np.round(self._rng.normal(3.2, 0.8, nb), 1).clip(1, 5),
                "a_quitte": self._departs(anciennete),
            }
        )

    def _construire_transactions(self, identifiants: list[str]) -> pd.DataFrame:
        nb = self._config.nb_transactions
        return pd.DataFrame(
            {
                "id_transaction": [f"T{i:06d}" for i in range(1, nb + 1)],
                "id_collaborateur": self._rng.choice(identifiants, nb),
                "date_transaction": [self._date_transaction() for _ in range(nb)],
                "client": self._rng.choice(CLIENTS, nb),
                "categorie": self._rng.choice(CATEGORIES, nb),
                "montant_euros": np.round(self._rng.gamma(4, 900, nb), 2),
                "statut": self._rng.choice(
                    ("payee", "en attente", "annulee"), nb, p=(0.8, 0.15, 0.05)
                ),
            }
        )

    # --- Colonnes sensibles, pour que la detection PII ait de la matiere ---

    def _telephone(self) -> str:
        chiffres = "".join(str(d) for d in self._rng.integers(0, 10, 8))
        # Deux formats coexistent volontairement : la detection doit couvrir les deux.
        if self._rng.random() < 0.25:
            return f"+336{chiffres}"
        return f"0{self._rng.integers(6, 8)}{chiffres}"

    def _iban(self) -> str:
        return "FR76" + "".join(str(d) for d in self._rng.integers(0, 10, 23))

    def _nir(self) -> str:
        return "".join(str(d) for d in self._rng.integers(0, 10, 15))

    # --- Colonnes metier ---------------------------------------------------

    def _date_embauche(self, anciennete: int) -> date:
        jour = int(self._rng.integers(0, 365))
        return date(2026, 1, 1) - timedelta(days=int(anciennete) * 365 + jour)

    def _date_transaction(self) -> date:
        return date(2024, 1, 1) + timedelta(days=int(self._rng.integers(0, 730)))

    def _salaires(self, nb: int) -> np.ndarray:
        return np.round(self._rng.normal(42000, 9000, nb), -2).clip(24000, 95000)

    def _departs(self, anciennete: np.ndarray) -> np.ndarray:
        """Le depart correle a une faible anciennete : le modele doit avoir un signal."""
        probabilite = np.clip(0.45 - anciennete * 0.02, 0.03, 0.45)
        return (self._rng.random(len(anciennete)) < probabilite).astype(int)

    # --- Imperfections volontaires ----------------------------------------

    def _degrader_collaborateurs(self, table: pd.DataFrame) -> pd.DataFrame:
        table = self._melanger_formats_de_date(table, "date_embauche")
        table = self._desaligner_la_casse(table, "service")
        table = self._vider_des_valeurs(table, ("salaire_annuel", "score_performance", "telephone"))
        table = self._ajouter_des_salaires_aberrants(table)
        return self._dupliquer_des_lignes(table)

    def _degrader_transactions(self, table: pd.DataFrame) -> pd.DataFrame:
        table = self._melanger_formats_de_date(table, "date_transaction")
        table = self._ajouter_des_montants_aberrants(table)
        table = self._ajouter_des_transactions_orphelines(table)
        return self._dupliquer_des_lignes(table)

    def _melanger_formats_de_date(self, table: pd.DataFrame, colonne: str) -> pd.DataFrame:
        """Trois formats coexistent : le nettoyage doit savoir les unifier."""
        formats = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
        indices = self._echantillon(table, self._config.part_dates_mal_formatees)
        valeurs = table[colonne].map(lambda d: d.strftime(formats[0]))
        for position in indices:
            choisi = formats[int(self._rng.integers(1, len(formats)))]
            valeurs.iloc[position] = table[colonne].iloc[position].strftime(choisi)
        table[colonne] = valeurs
        return table

    def _desaligner_la_casse(self, table: pd.DataFrame, colonne: str) -> pd.DataFrame:
        """« Data », « data » et « DATA  » doivent etre regroupes par le nettoyage."""
        variantes = (str.upper, str.lower, lambda v: f" {v} ", lambda v: v)
        indices = self._echantillon(table, 0.25)
        valeurs = table[colonne].astype(str)
        for position in indices:
            transformation = variantes[int(self._rng.integers(0, len(variantes)))]
            valeurs.iloc[position] = transformation(valeurs.iloc[position])
        table[colonne] = valeurs
        return table

    def _vider_des_valeurs(self, table: pd.DataFrame, colonnes: tuple[str, ...]) -> pd.DataFrame:
        for colonne in colonnes:
            indices = self._echantillon(table, self._config.part_valeurs_manquantes)
            table.loc[table.index[indices], colonne] = np.nan
        return table

    def _ajouter_des_salaires_aberrants(self, table: pd.DataFrame) -> pd.DataFrame:
        """Salaires a dix chiffres : une erreur de saisie que la detection doit voir."""
        indices = self._rng.choice(len(table), self._config.nb_valeurs_aberrantes, replace=False)
        table.loc[table.index[indices], "salaire_annuel"] *= 10
        return table

    def _ajouter_des_montants_aberrants(self, table: pd.DataFrame) -> pd.DataFrame:
        """Montants nuls ou negatifs : ni impossibles, ni normaux."""
        indices = self._rng.choice(len(table), self._config.nb_valeurs_aberrantes, replace=False)
        table.loc[table.index[indices], "montant_euros"] = -table.loc[
            table.index[indices], "montant_euros"
        ]
        return table

    def _ajouter_des_transactions_orphelines(self, table: pd.DataFrame) -> pd.DataFrame:
        """Transactions rattachees a un collaborateur inexistant : la jointure doit le reveler."""
        indices = self._rng.choice(
            len(table), self._config.nb_transactions_orphelines, replace=False
        )
        table.loc[table.index[indices], "id_collaborateur"] = "C9999"
        return table

    def _dupliquer_des_lignes(self, table: pd.DataFrame) -> pd.DataFrame:
        indices = self._rng.choice(len(table), self._config.nb_doublons, replace=False)
        doublons = table.iloc[indices]
        return pd.concat([table, doublons], ignore_index=True)

    def _echantillon(self, table: pd.DataFrame, part: float) -> np.ndarray:
        nb = max(1, int(len(table) * part))
        return self._rng.choice(len(table), nb, replace=False)


def main() -> None:
    destination = Path(__file__).resolve().parent
    chemins = DatasetGenerator().generer(destination)
    for nom, chemin in chemins.items():
        lignes = sum(1 for _ in chemin.open(encoding="utf-8")) - 1
        print(f"{nom:16s} {lignes:6d} lignes  ->  {chemin}")


if __name__ == "__main__":
    main()
