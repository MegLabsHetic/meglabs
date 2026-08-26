"""Connexion a une base externe : la deuxieme porte d'entree des donnees.

Jusqu'ici, la seule facon de faire entrer une donnee etait de deposer un fichier
a la main. Cette classe branche une base PostgreSQL et rend ses tables au reste
du pipeline — profilage, detection de donnees personnelles, DuckDB — sans que
rien en aval sache d'ou elles viennent.

**Un connecteur natif plutot qu'un tap externe, et c'est un choix.** SQLAlchemy
est deja une dependance : lire une table demande dix lignes, pas un ecosysteme.
Le protocole generique (`core/connecteur.py`) reste la pour les sources qui n'ont
pas de client Python evident — un CRM, une messagerie — et les deux cohabitent
derriere la meme interface.

**Ce qui est lu est fige dans un fichier.** La table distante n'est pas
interrogee a chaque question : elle est copiee au moment de la synchronisation.
Sans cela, une base lente ou coupee rendrait la conversation lente ou cassee, et
une question posee deux fois pourrait donner deux reponses.
"""

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ErreurUtilisateur, RessourceIntrouvable
from app.core.journal import obtenir
from app.models.data_source import DataSource

journal = obtenir(__name__)

# Un identifiant PostgreSQL valide. Les noms de table viennent de la base, mais
# ils transitent par le client : les valider avant de les inserer dans une
# requete est la seule protection qui ne depende pas de la bonne foi de personne.
IDENTIFIANT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]{0,62}$")

# Au-dela, on ne copie plus une table, on deplace une base. La borne protege la
# memoire du serveur, et elle est annoncee a l'utilisateur.
LIGNES_MAX = 200_000

# Une base qui ne repond pas doit echouer vite. Sans delai, un hote injoignable
# retient un fil d'execution jusqu'a epuisement du systeme.
DELAI_CONNEXION = 10
DELAI_REQUETE = 60_000

# Hotes qu'une source ne doit jamais viser. Une chaine de connexion est fournie
# par l'utilisateur : sans ce filtre, elle devient un moyen de faire scanner le
# reseau interne du serveur depuis l'exterieur.
HOTES_INTERDITS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "postgres"})


@dataclass(frozen=True)
class TableDistante:
    """Une table telle que la base la decrit, avant toute copie."""

    schema: str
    nom: str
    lignes: int | None

    @property
    def qualifie(self) -> str:
        return f"{self.schema}.{self.nom}"


class SourceService:
    """Teste, decouvre et lit une base PostgreSQL distante."""

    def __init__(self, cle: bytes | None = None) -> None:
        self._cle_imposee = cle

    # --- Les identifiants ----------------------------------------------------

    @property
    def _coffre(self) -> Fernet:
        """La cle de chiffrement, lue a l'appel et jamais figee au demarrage."""
        cle = self._cle_imposee or get_settings().cle_chiffrement.encode()
        return Fernet(cle)

    def chiffrer(self, config: dict) -> str:
        """Le mot de passe d'une base tierce ne se stocke pas en clair.

        Il ouvre un acces qui ne nous appartient pas : une base compromise par
        notre faute est plus grave qu'une de nos propres tables.
        """
        import json

        return self._coffre.encrypt(json.dumps(config).encode()).decode()

    def dechiffrer(self, chiffre: str) -> dict:
        import json

        try:
            return json.loads(self._coffre.decrypt(chiffre.encode()))
        except InvalidToken as erreur:
            raise ErreurUtilisateur(
                "Les identifiants de cette source ne sont plus lisibles. "
                "Reconnectez-la pour en enregistrer de nouveaux.",
                code_http=500,
            ) from erreur

    @staticmethod
    def masquer(config: dict) -> dict:
        """La configuration telle qu'on la renvoie : sans le secret."""
        return {
            cle: ("••••••" if cle == "mot_de_passe" else valeur) for cle, valeur in config.items()
        }

    # --- La connexion --------------------------------------------------------

    def _url(self, config: dict) -> str:
        hote = str(config.get("hote", "")).strip()
        if not hote:
            raise ErreurUtilisateur("L'adresse du serveur est obligatoire.")
        if hote.lower() in HOTES_INTERDITS:
            raise ErreurUtilisateur(
                "Cette adresse désigne le serveur MegLabs lui-même. "
                "Indiquez l'adresse publique de votre base de données."
            )
        from urllib.parse import quote_plus

        return (
            f"postgresql+psycopg2://{quote_plus(str(config.get('utilisateur', '')))}"
            f":{quote_plus(str(config.get('mot_de_passe', '')))}"
            f"@{hote}:{int(config.get('port', 5432))}/{config.get('base', '')}"
        )

    def _moteur(self, config: dict):
        return create_engine(
            self._url(config),
            connect_args={
                "connect_timeout": DELAI_CONNEXION,
                # Lecture seule et delai maximal, poses par la session elle-meme :
                # meme si une requete derapait, elle ne pourrait ni ecrire ni
                # retenir la base indefiniment.
                "options": (
                    "-c default_transaction_read_only=on " f"-c statement_timeout={DELAI_REQUETE}"
                ),
            },
            pool_pre_ping=True,
        )

    def tester(self, config: dict) -> str:
        """Verifie que la base repond, et rend sa version."""
        try:
            with self._moteur(config).connect() as connexion:
                return str(connexion.execute(text("SELECT version()")).scalar() or "")[:80]
        except ErreurUtilisateur:
            raise
        except Exception as echec:  # noqa: BLE001 - le detail technique est journalise
            journal.warning("connexion source refusee", exc_info=True)
            raise ErreurUtilisateur(
                "La connexion a échoué. Vérifiez l'adresse, le port, la base et les "
                f"identifiants. Message du serveur : {str(echec).splitlines()[0][:160]}"
            ) from echec

    # --- La decouverte -------------------------------------------------------

    def decouvrir(self, config: dict) -> list[TableDistante]:
        """Les tables lisibles, avec une estimation de leur taille.

        Le nombre de lignes vient des statistiques de PostgreSQL et non d'un
        `COUNT(*)` : compter chaque table d'une grosse base prendrait des minutes
        pour un chiffre qui ne sert qu'a choisir.
        """
        schema = str(config.get("schema") or "public")
        moteur = self._moteur(config)
        try:
            noms = inspect(moteur).get_table_names(schema=schema)
            estimations = self._estimations(moteur, schema)
        except ErreurUtilisateur:
            raise
        except Exception as echec:  # noqa: BLE001
            journal.warning("decouverte impossible", exc_info=True)
            raise ErreurUtilisateur(
                "Les tables n'ont pas pu être listées. Le compte a-t-il le droit de "
                f"lire le schéma « {schema} » ?"
            ) from echec

        return sorted(
            (TableDistante(schema, nom, estimations.get(nom)) for nom in noms),
            key=lambda table: (-(table.lignes or 0), table.nom),
        )

    @staticmethod
    def _estimations(moteur, schema: str) -> dict[str, int]:
        requete = text(
            "SELECT relname, GREATEST(n_live_tup, 0) AS lignes "
            "FROM pg_stat_user_tables WHERE schemaname = :schema"
        )
        with moteur.connect() as connexion:
            return {
                ligne.relname: int(ligne.lignes)
                for ligne in connexion.execute(requete, {"schema": schema})
            }

    # --- La lecture ----------------------------------------------------------

    def lire(self, config: dict, schema: str, table: str, limite: int = LIGNES_MAX) -> pd.DataFrame:
        """Copie une table distante, en texte.

        Le type texte est force comme pour un fichier depose : sans cela un
        numero de telephone perd son `+` et un identifiant ses zeros initiaux, et
        la detection de donnees personnelles ne trouve plus rien — sans qu'aucune
        erreur ne soit levee.
        """
        self._valider_nom(schema)
        self._valider_nom(table)

        moteur = self._moteur(config)
        requete = f'SELECT * FROM "{schema}"."{table}" LIMIT {int(limite)}'
        try:
            with moteur.connect() as connexion:
                brute = pd.read_sql(text(requete), connexion)
        except Exception as echec:  # noqa: BLE001
            journal.warning("lecture de table impossible", extra={"table": table}, exc_info=True)
            raise ErreurUtilisateur(
                f"La table « {table} » n'a pas pu être lue. Le compte a-t-il le droit "
                "de la consulter ?"
            ) from echec

        return brute.astype("string").astype("object").where(brute.notna(), None)

    @staticmethod
    def _valider_nom(nom: str) -> None:
        """Un nom de table entre dans une requete : il ne peut pas etre un parametre.

        PostgreSQL n'accepte pas d'identifiant lie ; il est donc interpole, et la
        seule protection possible est de refuser tout ce qui n'est pas un
        identifiant valide avant de l'ecrire.
        """
        if not IDENTIFIANT.match(nom or ""):
            raise ErreurUtilisateur(
                f"« {nom} » n'est pas un nom de table valide. "
                "Sélectionnez une table dans la liste proposée."
            )

    # --- Le cycle de vie d'une source ---------------------------------------

    async def enregistrer(
        self, session: AsyncSession, workspace_id: str, nom: str, config: dict
    ) -> DataSource:
        """Teste la connexion AVANT d'enregistrer quoi que ce soit.

        Enregistrer une source injoignable laisserait un objet mort dans
        l'interface, et l'utilisateur ne saurait pas si le probleme vient de sa
        saisie ou de sa base.
        """
        await asyncio.to_thread(self.tester, config)
        source = DataSource(
            workspace_id=workspace_id,
            source_type="postgresql",
            name=nom.strip() or config.get("base", "Base PostgreSQL"),
            config=self.chiffrer(config),
        )
        session.add(source)
        await session.commit()
        journal.info("source enregistree", extra={"espace": workspace_id, "type": "postgresql"})
        return source

    async def recuperer(self, session: AsyncSession, source_id: str) -> DataSource:
        source = await session.get(DataSource, source_id)
        if source is None:
            raise RessourceIntrouvable("Cette source n'existe pas.")
        return source

    async def lister(self, session: AsyncSession, workspace_id: str) -> list[DataSource]:
        resultat = await session.execute(
            select(DataSource)
            .where(DataSource.workspace_id == workspace_id)
            .order_by(DataSource.created_at.desc())
        )
        return list(resultat.scalars())

    async def tables(self, session: AsyncSession, source_id: str) -> list[TableDistante]:
        source = await self.recuperer(session, source_id)
        config = self.dechiffrer(source.config)
        return await asyncio.to_thread(self.decouvrir, config)

    async def synchroniser(
        self, session: AsyncSession, source_id: str, tables: list[str], fichiers
    ) -> list[str]:
        """Copie les tables choisies et les fait entrer par la porte des fichiers.

        Chaque table devient un CSV depose comme n'importe quel autre : elle
        traverse donc la meme validation, le meme profilage et la meme detection
        de donnees personnelles. Reutiliser ce chemin plutot que d'en ecrire un
        second est ce qui garantit qu'une table lue depuis une base et un fichier
        depose a la main se comportent exactement pareil.
        """
        source = await self.recuperer(session, source_id)
        config = self.dechiffrer(source.config)
        schema = str(config.get("schema") or "public")

        deposes: list[str] = []
        for nom in tables:
            table = await asyncio.to_thread(self.lire, config, schema, nom)
            if table.empty:
                journal.info("table vide ignoree", extra={"table": nom})
                continue
            contenu = table.to_csv(index=False).encode("utf-8")
            fichier, _, _ = await fichiers.deposer(
                session, source.workspace_id, f"{nom}.csv", contenu
            )
            deposes.append(fichier.name)

        source.last_sync = datetime.now(UTC)
        source.tables_synchronisees = len(deposes)
        await session.commit()
        journal.info("source synchronisee", extra={"source": source_id, "tables": len(deposes)})
        return deposes

    def en_lecture(self, source: DataSource) -> dict:
        """Ce qu'on renvoie d'une source : jamais ses identifiants."""
        return {
            "id": source.id,
            "nom": source.name,
            "type": source.source_type,
            "derniere_synchro": source.last_sync,
            "tables_synchronisees": source.tables_synchronisees,
            "config": self.masquer(self.dechiffrer(source.config)),
        }
