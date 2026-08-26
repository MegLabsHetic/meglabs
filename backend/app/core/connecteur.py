"""Execution d'un connecteur de donnees, quel que soit son ecosysteme.

Un connecteur est un programme qui ecrit du JSON ligne par ligne sur sa sortie
standard. C'est vrai des taps Singer comme des images Airbyte : seule la forme
des messages differe, pas le principe. Cette classe parle les deux et rend des
DataFrames — apres quoi le pipeline existant (profilage, donnees personnelles,
DuckDB) travaille sans savoir d'ou vient la table.

Ce module n'installe rien et ne connait aucune source : il recoit une commande
a lancer. Ajouter PostgreSQL, Odoo ou une messagerie ne le modifie pas.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pandas as pd

from app.core.errors import ErreurUtilisateur

# Types de messages du protocole. Les deux ecosystemes partagent ces noms.
SCHEMA = "SCHEMA"
CATALOGUE = "CATALOG"
ENREGISTREMENT = "RECORD"
ETAT = "STATE"
JOURNAL = "LOG"
TRACE = "TRACE"

# Une ligne de sortie anormalement longue signale un connecteur qui deraille
# (dump binaire, boucle). On coupe plutot que de remplir la memoire.
LONGUEUR_LIGNE_MAX = 4 * 1024 * 1024


@dataclass(frozen=True)
class Message:
    """Un message du connecteur, ramene a une forme unique.

    Singer place le nom du flux a la racine, Airbyte l'imbrique dans `record`.
    Normaliser ici evite que chaque appelant ait a connaitre les deux dialectes.
    """

    type: str
    flux: str | None = None
    donnees: dict | None = None
    etat: dict | None = None
    texte: str | None = None


@dataclass
class Extraction:
    """Ce qu'une lecture a produit."""

    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    # Rendu au connecteur a la prochaine lecture : c'est ce qui permet de ne
    # reprendre que les nouveautes plutot que de tout relire.
    etat: dict = field(default_factory=dict)
    journal: list[str] = field(default_factory=list)
    tronquee: bool = False

    @property
    def nb_lignes(self) -> int:
        return sum(len(table) for table in self.tables.values())


def analyser(ligne: str) -> Message | None:
    """Une ligne de sortie devient un message, ou rien si elle n'en est pas un.

    Les connecteurs ecrivent aussi des avertissements en texte brut sur stdout.
    Une ligne illisible est ignoree, jamais fatale : perdre un message de
    journal ne doit pas interrompre une synchronisation qui fonctionne.
    """
    ligne = ligne.strip()
    if not ligne or ligne[0] != "{":
        return None
    try:
        brut = json.loads(ligne)
    except json.JSONDecodeError:
        return None
    if not isinstance(brut, dict) or "type" not in brut:
        return None
    return _normaliser(brut)


def _normaliser(brut: dict) -> Message:
    """Ramene les deux dialectes a la meme structure."""
    type_message = str(brut["type"]).upper()

    if type_message == ENREGISTREMENT:
        # Airbyte : {"record": {"stream": ..., "data": {...}}}
        # Singer  : {"stream": ..., "record": {...}}
        interieur = brut.get("record") or {}
        if "data" in interieur:
            return Message(ENREGISTREMENT, interieur.get("stream"), interieur["data"])
        return Message(ENREGISTREMENT, brut.get("stream"), interieur)

    if type_message == ETAT:
        etat = brut.get("state") or brut.get("value") or {}
        return Message(ETAT, etat=etat.get("data", etat) if isinstance(etat, dict) else {})

    if type_message in (SCHEMA, CATALOGUE):
        contenu = brut.get("catalog") or brut.get("schema") or {}
        return Message(type_message, brut.get("stream"), contenu)

    if type_message in (JOURNAL, TRACE):
        bloc = brut.get("log") or brut.get("trace") or {}
        return Message(JOURNAL, texte=str(bloc.get("message", "")).strip() or None)

    return Message(type_message)


class Connecteur:
    """Lance un connecteur et transforme sa sortie en tables.

    La commande est fournie par l'appelant : un tap Singer est un executable
    Python, une image Airbyte se lance par `docker run`. La classe ne choisit
    pas — elle execute ce qu'on lui donne.
    """

    def __init__(self, commande: list[str], delai_secondes: int = 900) -> None:
        if not commande:
            raise ValueError("La commande du connecteur est vide.")
        self._commande = commande
        self._delai = delai_secondes

    # --- Lecture -------------------------------------------------------------

    async def lire(self, lignes_max: int = 200_000) -> Extraction:
        """Execute le connecteur et accumule ce qu'il produit.

        `lignes_max` est une protection, pas un reglage : une source volumineuse
        remplirait la memoire du serveur avant qu'on s'en apercoive. Au-dela, on
        s'arrete et on le dit — un resultat partiel annonce vaut mieux qu'un
        service tue par le noyau.
        """
        extraction = Extraction()
        accumulation: dict[str, list[dict]] = {}

        async for message in self._messages():
            if message.type == ENREGISTREMENT and message.donnees is not None:
                flux = message.flux or "donnees"
                accumulation.setdefault(flux, []).append(message.donnees)
                if sum(len(lignes) for lignes in accumulation.values()) >= lignes_max:
                    extraction.tronquee = True
                    break
            elif message.type == ETAT and message.etat:
                extraction.etat = message.etat
            elif message.type == JOURNAL and message.texte:
                extraction.journal.append(message.texte)

        extraction.tables = {flux: self._en_table(lignes) for flux, lignes in accumulation.items()}
        return extraction

    @staticmethod
    def _en_table(lignes: list[dict]) -> pd.DataFrame:
        """Les enregistrements deviennent une table, en texte d'abord.

        Meme piege que pour les fichiers deposes : laisse a lui-meme, pandas lit
        un numero de telephone comme un flottant et lui fait perdre son `+`, un
        identifiant long comme un entier et ses zeros initiaux. La detection de
        donnees personnelles ne trouverait alors plus rien, sans lever d'erreur.
        """
        return pd.DataFrame(lignes, dtype="object")

    # --- Execution du processus ---------------------------------------------

    async def _messages(self) -> AsyncIterator[Message]:
        processus = await self._demarrer()
        try:
            async for ligne in self._sortie(processus):
                message = analyser(ligne)
                if message is not None:
                    yield message
            await self._verifier_sortie(processus)
        finally:
            if processus.returncode is None:
                processus.kill()
                await processus.wait()

    async def _demarrer(self) -> asyncio.subprocess.Process:
        try:
            return await asyncio.create_subprocess_exec(
                *self._commande,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=LONGUEUR_LIGNE_MAX,
            )
        except FileNotFoundError as absent:
            raise ErreurUtilisateur(
                f"Le connecteur « {self._commande[0]} » n'est pas installé sur le serveur.",
                code_http=500,
            ) from absent

    async def _sortie(self, processus: asyncio.subprocess.Process) -> AsyncIterator[str]:
        """Les lignes au fil de l'eau, sous un delai global."""
        assert processus.stdout is not None
        try:
            async with asyncio.timeout(self._delai):
                async for brut in processus.stdout:
                    yield brut.decode("utf-8", errors="replace")
        except TimeoutError as expire:
            raise ErreurUtilisateur(
                f"La source n'a pas répondu en moins de {self._delai} secondes. "
                "Réduisez la période ou le nombre de tables sélectionnées."
            ) from expire
        except ValueError as trop_long:
            # asyncio leve ValueError quand une ligne depasse `limit`.
            raise ErreurUtilisateur(
                "La source a renvoyé une ligne anormalement longue. "
                "Ce connecteur ne semble pas produire le format attendu."
            ) from trop_long

    async def _verifier_sortie(self, processus: asyncio.subprocess.Process) -> None:
        """Un code de retour non nul est une erreur, meme si des lignes sont sorties.

        Le message d'erreur du connecteur part sur stderr : il est technique et
        souvent en anglais, donc il est journalise, pas affiche tel quel.
        """
        assert processus.stderr is not None
        details = (await processus.stderr.read()).decode("utf-8", errors="replace")
        await processus.wait()
        if processus.returncode:
            derniere = details.strip().splitlines()[-1:] or ["aucun détail"]
            raise ErreurUtilisateur(
                "La source a refusé la connexion ou la lecture. "
                f"Message du connecteur : {derniere[0][:200]}"
            )
