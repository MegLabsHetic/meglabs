"""Mesure ce que le systeme repond vraiment, plutot que ce qu'on affirme qu'il repond.

    python -m benchmark.executer                          # contre la production
    python -m benchmark.executer --api http://localhost:8000

Ce qui est mesure, et pourquoi.

**L'exactitude d'execution.** Chaque cas porte une requete de reference ecrite a
la main. On compare les RESULTATS, pas les requetes : deux formulations tres
differentes peuvent etre toutes deux justes, et une requete presque identique a
la reference peut etre fausse. C'est la mesure employee par Spider et BIRD.

**Le taux d'auto-reparation.** Il se lit dans la trace : un agent qui a fait deux
tentatives a echoue une fois. C'est un indicateur de sante du prompt.

**La latence, en distribution.** Une moyenne ne dit rien quand les temps vont de
4 a 30 secondes ; la mediane et le 95e centile disent ce qu'un utilisateur vit.

**Les refus.** Six demandes qui doivent etre refusees : suppressions, injection
de prompt, lecture de fichier, hors sujet. Un refus manque est plus grave qu'une
reponse fausse.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

RACINE = Path(__file__).resolve().parent
DONNEES = RACINE.parent / "data"
FICHIERS = ["collaborateurs.csv", "transactions.csv"]

# Au-dela, ce n'est plus une lenteur mais une panne : on marque le cas et on
# passe au suivant plutot que de bloquer toute la campagne.
DELAI = 180

# Deux montants qui different au centime ne sont pas deux resultats differents.
TOLERANCE = 0.01


@dataclass
class Resultat:
    id: str
    question: str
    juste: bool | None = None
    motif: str = ""
    sql: str | None = None
    duree_ms: int = 0
    cout_centimes: float = 0.0
    reparations: int = 0
    attendu: list = field(default_factory=list)
    obtenu: list = field(default_factory=list)


def normaliser(lignes: list) -> list[tuple]:
    """Rend deux resultats comparables sans les rendre identiques par force.

    Les nombres sont arrondis, les chaines mises en minuscules et deroulees : le
    systeme peut rendre « Ressources humaines » la ou la reference rend
    « ressources humaines », ce n'est pas une erreur. L'ordre est ignore, sauf
    quand la question portait explicitement sur un classement — et dans ce cas
    la reference porte un LIMIT, donc la comparaison de l'ensemble suffit.
    """
    normalisees = []
    for ligne in lignes:
        valeurs = []
        for valeur in ligne:
            if valeur is None:
                valeurs.append(None)
            elif isinstance(valeur, bool):
                valeurs.append(valeur)
            elif isinstance(valeur, (int, float)):
                valeurs.append(round(float(valeur) / TOLERANCE))
            else:
                valeurs.append(str(valeur).strip().lower())
        normalisees.append(tuple(valeurs))
    return sorted(normalisees, key=repr)


def contient(obtenu: list, attendu: list) -> bool:
    """Le resultat repond-il a la reference, sans avoir a lui etre identique ?

    Une comparaison stricte penalise un systeme qui repond MIEUX. Mesure sur nos
    propres cas : a « quel est le salaire moyen ? » il a rendu la moyenne ET la
    mediane, et a « quelle est la transaction la plus elevee ? » la ligne
    complete plutot que le seul montant. Les deux reponses contiennent la bonne,
    et les compter fausses aurait mesure la rigidite du benchmark, pas la
    justesse du systeme.

    La regle retenue : autant de lignes que la reference, et chaque ligne de la
    reference retrouvee dans une ligne du resultat — une colonne en plus est
    tolerée, une valeur fausse ou manquante ne l'est pas.
    """
    lignes_obtenues = normaliser(obtenu)
    lignes_attendues = normaliser(attendu)
    if len(lignes_obtenues) != len(lignes_attendues):
        return False

    # Appariement un pour un : sans consommer la ligne trouvee, deux lignes de
    # reference differentes pourraient se satisfaire de la meme ligne obtenue.
    restantes = list(lignes_obtenues)
    for ligne in lignes_attendues:
        correspondante = next(
            (candidate for candidate in restantes if set(ligne) <= set(candidate)), None
        )
        if correspondante is None:
            return False
        restantes.remove(correspondante)
    return True


class Campagne:
    """Deroule les cas contre une API et compare aux requetes de reference."""

    def __init__(self, api: str) -> None:
        self._api = api.rstrip("/")
        self._client = httpx.Client(timeout=DELAI)
        self._espace: str | None = None
        self._tables: dict[str, pd.DataFrame] = {}

    # --- Preparation ---------------------------------------------------------

    def preparer(self) -> None:
        """Un espace neuf a chaque campagne : sinon le cache de requetes rendrait
        les reponses de la campagne precedente, et on mesurerait le cache."""
        horodatage = time.strftime("%Y%m%d-%H%M%S")
        reponse = self._client.post(
            f"{self._api}/api/workspaces", json={"nom": f"Benchmark {horodatage}"}
        )
        reponse.raise_for_status()
        self._espace = reponse.json()["id"]

        for nom in FICHIERS:
            chemin = DONNEES / nom
            with chemin.open("rb") as flux:
                depot = self._client.post(
                    f"{self._api}/api/workspaces/{self._espace}/files",
                    files={"fichier": (nom, flux, "text/csv")},
                )
            depot.raise_for_status()

        # Les references s'executent sur exactement les memes tables que le
        # systeme mesure : le chargement passe par le loader de l'application.
        from app.services.file_loader import FileLoader

        loader = FileLoader()
        self._tables = {Path(nom).stem: loader.charger(DONNEES / nom) for nom in FICHIERS}

    # --- Un cas --------------------------------------------------------------

    def poser(self, question: str) -> dict[str, Any]:
        """Pose la question et rend l'evenement final du flux."""
        with self._client.stream(
            "POST", f"{self._api}/api/chat/{self._espace}", json={"question": question}
        ) as flux:
            bloc, final = "", None
            for ligne in flux.iter_lines():
                if ligne.startswith("data: ") and bloc == "done":
                    final = json.loads(ligne[6:])
                elif ligne.startswith("event: "):
                    bloc = ligne[7:].strip()
            return final or {}

    async def _executer_reference(self, sql: str) -> list:
        from app.core.duckdb_engine import MoteurDuckdb

        resultat = await MoteurDuckdb().executer(sql, self._tables)
        return resultat.lignes

    def mesurer(self, cas: dict) -> Resultat:
        mesure = Resultat(id=cas["id"], question=cas["question"])
        debut = time.perf_counter()
        reponse = self.poser(cas["question"])
        mesure.duree_ms = int((time.perf_counter() - debut) * 1000)

        if not reponse:
            mesure.juste, mesure.motif = False, "aucune réponse"
            return mesure

        mesure.sql = reponse.get("sql")
        mesure.cout_centimes = reponse.get("cout_centimes", 0.0)
        mesure.reparations = sum(1 for a in reponse.get("trace", []) if a.get("tentatives", 1) > 1)
        mesure.obtenu = reponse.get("lignes", [])
        return mesure

    def comparer(self, cas: dict, mesure: Resultat, attendu: list) -> None:
        mode = cas.get("comparaison", "exact")
        mesure.attendu = attendu

        if mesure.sql is None:
            mesure.juste, mesure.motif = False, "aucune requête produite"
        elif mode == "libre":
            mesure.juste = len(mesure.obtenu) > 0
            mesure.motif = "" if mesure.juste else "résultat vide"
        elif mode == "cardinalite":
            mesure.juste = len(mesure.obtenu) == len(attendu)
            mesure.motif = (
                "" if mesure.juste else f"{len(mesure.obtenu)} lignes au lieu de {len(attendu)}"
            )
        else:
            mesure.juste = contient(mesure.obtenu, attendu)
            mesure.motif = (
                "" if mesure.juste else "la référence n'est pas retrouvée dans le résultat"
            )

    # --- Les refus -----------------------------------------------------------

    def verifier_refus(self, demande: str) -> Resultat:
        """Un refus est un succes. Ce qui compte, c'est qu'aucun SQL n'ait tourne."""
        mesure = Resultat(id="refus", question=demande)
        debut = time.perf_counter()
        reponse = self.poser(demande)
        mesure.duree_ms = int((time.perf_counter() - debut) * 1000)

        mesure.sql = reponse.get("sql")
        mesure.cout_centimes = reponse.get("cout_centimes", 0.0)
        mesure.juste = mesure.sql is None
        mesure.motif = "" if mesure.juste else "une requête a été exécutée"
        return mesure

    def fermer(self) -> None:
        self._client.close()


# --- Restitution --------------------------------------------------------------


def centile(valeurs: list[int], part: float) -> int:
    """Le 95e centile dit ce que vit le malchanceux, la moyenne ne dit rien."""
    if not valeurs:
        return 0
    ordonnees = sorted(valeurs)
    rang = min(int(len(ordonnees) * part), len(ordonnees) - 1)
    return ordonnees[rang]


def rapporter(mesures: list[Resultat], refus: list[Resultat]) -> dict:
    justes = [m for m in mesures if m.juste]
    durees = [m.duree_ms for m in mesures]

    resume = {
        "cas": len(mesures),
        "exactitude_execution": round(len(justes) / len(mesures) * 100, 1) if mesures else 0.0,
        "refus_tenus": f"{sum(1 for r in refus if r.juste)}/{len(refus)}",
        "auto_reparations": sum(m.reparations for m in mesures),
        "latence_mediane_ms": int(statistics.median(durees)) if durees else 0,
        "latence_p95_ms": centile(durees, 0.95),
        "cout_total_centimes": round(sum(m.cout_centimes for m in mesures + refus), 4),
    }

    print("\n" + "=" * 78)
    print("  RESULTATS PAR CAS")
    print("=" * 78)
    for mesure in mesures:
        marque = "OK  " if mesure.juste else "FAUX"
        detail = f"  {mesure.motif}" if mesure.motif else ""
        print(f"  {marque}  {mesure.id:<30} {mesure.duree_ms:>6} ms{detail}")

    print("\n  REFUS ATTENDUS")
    for mesure in refus:
        marque = "OK  " if mesure.juste else "PASSE"
        print(f"  {marque}  {mesure.question[:56]:<58}{mesure.motif}")

    echecs = [m for m in mesures if not m.juste]
    if echecs:
        print("\n" + "=" * 78)
        print("  ECHECS EN DETAIL — c'est ce qu'on montre au jury")
        print("=" * 78)
        for mesure in echecs:
            print(f"\n  [{mesure.id}] {mesure.question}")
            print(f"    motif    : {mesure.motif}")
            print(f"    sql      : {(mesure.sql or '—')[:200]}")
            print(f"    attendu  : {str(mesure.attendu)[:160]}")
            print(f"    obtenu   : {str(mesure.obtenu)[:160]}")

    print("\n" + "=" * 78)
    print("  RESUME")
    print("=" * 78)
    for cle, valeur in resume.items():
        print(f"  {cle:<26} {valeur}")
    print()

    return {"resume": resume, "cas": [vars(m) for m in mesures + refus]}


def principal() -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--api", default="https://api.faridb.site")
    analyseur.add_argument("--sortie", default=str(RACINE / "resultats.json"))
    # Sert a verifier la mecanique sans payer une campagne complete.
    analyseur.add_argument(
        "--limite", type=int, default=0, help="ne traiter que les N premiers cas"
    )
    options = analyseur.parse_args()

    donnees = json.loads((RACINE / "questions.json").read_text(encoding="utf-8"))
    if options.limite:
        donnees["cas"] = donnees["cas"][: options.limite]
        donnees["refus_attendus"] = donnees["refus_attendus"][:1]
    campagne = Campagne(options.api)

    print(f"Campagne contre {options.api}")
    try:
        campagne.preparer()
        print(
            f"espace prepare, {len(donnees['cas'])} cas + {len(donnees['refus_attendus'])} refus\n"
        )

        mesures = []
        for numero, cas in enumerate(donnees["cas"], 1):
            print(f"  [{numero:>2}/{len(donnees['cas'])}] {cas['id']}", flush=True)
            mesure = campagne.mesurer(cas)
            try:
                attendu = asyncio.run(campagne._executer_reference(cas["reference"]))
            except Exception as echec:  # noqa: BLE001 - une reference fausse doit se voir
                mesure.juste, mesure.motif = None, f"référence invalide : {echec}"
                mesures.append(mesure)
                continue
            campagne.comparer(cas, mesure, attendu)
            mesures.append(mesure)

        print()
        refus = []
        for demande in donnees["refus_attendus"]:
            print(f"  [refus] {demande[:50]}", flush=True)
            refus.append(campagne.verifier_refus(demande))

        rapport = rapporter(mesures, refus)
        Path(options.sortie).write_text(
            json.dumps(rapport, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(f"  rapport ecrit dans {options.sortie}\n")
        return 0
    finally:
        campagne.fermer()


if __name__ == "__main__":
    sys.exit(principal())
