"""Le pipeline d'une question : de la phrase francaise a la reponse ecrite.

C'est le seul endroit ou la chaine complete est decrite. Les routes REST et le
serveur MCP appellent ici ; ils ne rejouent pas les etapes eux-memes, sinon deux
chemins divergeraient et un seul serait teste.

Le trajet nominal tient en deux appels au modele : l'orchestrateur comprend et
traduit, le redacteur interprete. Tout le reste — charger, profiler, valider,
executer — est du Python, sans modele et sans cout.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.analyst_agent import Analyste
from app.agents.data_agent import DataAgent
from app.agents.orchestrator import Echange, Orchestrateur
from app.agents.writer_agent import Redacteur
from app.core.duckdb_engine import ResultatSql, nom_de_table
from app.core.errors import ErreurUtilisateur
from app.core.events import JETON, Evenement, FluxEvenements
from app.models.chat_message import ChatMessage
from app.models.data_file import DataFile
from app.models.query_cache import QueryCache
from app.schemas.chat import Comprehension, Intention

# Deux echanges de plus que ce que l'orchestrateur en garde : la troncature est sa
# decision, pas celle de la base.
ECHANGES_RELUS = 6

ESPACES = re.compile(r"\s+")
PONCTUATION = re.compile(r"[^\w\s]")


@dataclass
class Reponse:
    """Ce qu'une question produit, quelle que soit l'interface qui l'a posee."""

    texte: str
    intention: Intention
    sql: str | None = None
    colonnes: list[str] = field(default_factory=list)
    lignes: list[list] = field(default_factory=list)
    tronque: bool = False
    besoin_visualisation: bool = False
    cout_centimes: float = 0.0
    depuis_cache: bool = False
    trace: list[dict] = field(default_factory=list)


class QueryService:
    """Conduit une question de bout en bout, en annoncant chaque etape."""

    def __init__(self, agent_donnees: DataAgent | None = None) -> None:
        self._donnees = agent_donnees or DataAgent()

    async def repondre(
        self,
        session: AsyncSession,
        workspace_id: str,
        question: str,
        flux: FluxEvenements | None = None,
    ) -> Reponse:
        """Le pipeline complet. `flux` alimente le theatre des agents s'il est fourni."""
        question = question.strip()
        if not question:
            raise ErreurUtilisateur("Pose une question pour que je puisse y répondre.")

        fichiers = await self._fichiers(session, workspace_id)
        tables = {nom: self._charger(fichier) for nom, fichier in fichiers.items()}
        schemas = {nom: self._contexte(fichier) for nom, fichier in fichiers.items()}

        cle = self._cle_cache(question, fichiers)
        connue = await session.get(QueryCache, cle)
        if connue is not None:
            reponse = self._depuis_cache(connue.response)
            await self._diffuser(flux, reponse.texte)
            await self._archiver(session, workspace_id, question, reponse)
            return reponse

        reponse = await self._traiter(session, workspace_id, question, tables, schemas, flux)
        session.add(QueryCache(key_hash=cle, response=self._en_cache(reponse)))
        await self._archiver(session, workspace_id, question, reponse)
        return reponse

    # --- Le trajet ----------------------------------------------------------

    async def _traiter(
        self,
        session: AsyncSession,
        workspace_id: str,
        question: str,
        tables: dict[str, pd.DataFrame],
        schemas: dict[str, dict],
        flux: FluxEvenements | None,
    ) -> Reponse:
        analyste = Analyste(flux=flux)
        orchestrateur = Orchestrateur(flux=flux)
        redacteur = Redacteur(flux=flux)

        schema = analyste.decrire(schemas)
        memoire = await self._memoire(session, workspace_id)
        comprehension = await orchestrateur.comprendre(question, schema, memoire)

        resultat, sql = await self._executer(analyste, comprehension, tables, schema)
        texte = await self._formuler(redacteur, question, comprehension, resultat, flux)

        agents = (orchestrateur, analyste, redacteur)
        return Reponse(
            texte=texte,
            intention=comprehension.intention,
            sql=sql,
            colonnes=resultat.colonnes if resultat else [],
            lignes=resultat.lignes if resultat else [],
            tronque=bool(resultat and resultat.tronque),
            besoin_visualisation=comprehension.besoin_visualisation,
            cout_centimes=round(sum(agent.cout_centimes for agent in agents), 6),
            trace=[entree for agent in agents for entree in agent.trace_json()],
        )

    async def _executer(
        self,
        analyste: Analyste,
        comprehension: Comprehension,
        tables: dict[str, pd.DataFrame],
        schema: str,
    ) -> tuple[ResultatSql | None, str | None]:
        """Rien n'est execute si l'intention ne demande pas de donnees."""
        if comprehension.clarification or not comprehension.intention.demande_du_sql:
            return None, None
        if not comprehension.sql:
            raise ErreurUtilisateur(
                "Je n'ai pas réussi à traduire cette question en requête. "
                "Reformulez-la en nommant la donnée qui vous intéresse."
            )
        return await analyste.executer(comprehension.sql, tables, schema)

    async def _formuler(
        self,
        redacteur: Redacteur,
        question: str,
        comprehension: Comprehension,
        resultat: ResultatSql | None,
        flux: FluxEvenements | None,
    ) -> str:
        """Une reponse sans donnees ne merite pas un appel au modele.

        La clarification et les intentions hors perimetre ont deja leur texte : le
        faire reformuler couterait un appel pour ne rien ajouter.
        """
        if comprehension.clarification:
            await self._diffuser(flux, comprehension.clarification)
            return comprehension.clarification
        if resultat is None:
            texte = REPONSES_SANS_DONNEES[comprehension.intention]
            await self._diffuser(flux, texte)
            return texte

        morceaux: list[str] = []
        async for morceau in redacteur.interpreter(question, resultat):
            morceaux.append(morceau)
            if flux is not None:
                await flux.publier(Evenement(JETON, {"texte": morceau}))
        return "".join(morceaux)

    @staticmethod
    async def _diffuser(flux: FluxEvenements | None, texte: str) -> None:
        """Envoie un texte deja ecrit sur le flux, d'un seul bloc.

        Une reponse issue du cache ou d'un modele de phrase n'a rien a gagner a etre
        egrenee mot a mot : elle est instantanee, et la feindre lente serait un
        artifice. L'interface la recoit par le meme canal que les autres.
        """
        if flux is not None:
            await flux.publier(Evenement(JETON, {"texte": texte}))

    # --- Les fichiers de l'espace -------------------------------------------

    async def _fichiers(self, session: AsyncSession, workspace_id: str) -> dict[str, DataFile]:
        """Associe un nom de table interrogeable a chaque fichier de l'espace."""
        resultat = await session.execute(
            select(DataFile)
            .where(DataFile.workspace_id == workspace_id)
            .order_by(DataFile.created_at)
        )
        fichiers = list(resultat.scalars())
        if not fichiers:
            raise ErreurUtilisateur(
                "Cet espace ne contient aucun fichier. "
                "Déposez un CSV ou un Excel pour pouvoir poser des questions."
            )

        nommes: dict[str, DataFile] = {}
        for fichier in fichiers:
            nommes[nom_de_table(fichier.name, set(nommes))] = fichier
        return nommes

    def _charger(self, fichier: DataFile) -> pd.DataFrame:
        return self._donnees.charger(Path(fichier.path))

    def _contexte(self, fichier: DataFile) -> dict:
        """Le profil deja calcule, ou un profil recalcule si le fichier est ancien."""
        profil = fichier.profile or self._donnees.profiler(Path(fichier.path))
        return self._donnees.llm_context(profil)

    # --- Memoire et cache ---------------------------------------------------

    async def _memoire(self, session: AsyncSession, workspace_id: str) -> list[Echange]:
        """Les derniers echanges, du plus ancien au plus recent."""
        resultat = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.workspace_id == workspace_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(ECHANGES_RELUS * 2)
        )
        messages = list(reversed(list(resultat.scalars())))

        echanges: list[Echange] = []
        question: str | None = None
        for message in messages:
            if message.role == "user":
                question = message.content
            elif question is not None:
                echanges.append(Echange(question, message.content, message.sql_executed))
                question = None
        return echanges

    def _cle_cache(self, question: str, fichiers: dict[str, DataFile]) -> str:
        """Meme question, memes donnees, meme reponse.

        L'empreinte inclut l'etat des fichiers : un nettoyage ou une pseudonymisation
        change le resultat, et servir l'ancienne reponse serait un mensonge.
        """
        normalisee = PONCTUATION.sub(" ", question.lower())
        normalisee = ESPACES.sub(" ", normalisee).strip()
        empreinte = "|".join(
            f"{nom}:{fichier.id}:{fichier.pii_status}:{fichier.size_bytes}"
            for nom, fichier in sorted(fichiers.items())
        )
        return hashlib.sha256(f"{normalisee}||{empreinte}".encode()).hexdigest()

    @staticmethod
    def _depuis_cache(enregistre: dict) -> Reponse:
        """L'intention revient du JSON en simple chaine : on lui rend son type."""
        champs = dict(enregistre)
        champs["intention"] = Intention(champs["intention"])
        return Reponse(**champs, depuis_cache=True)

    @staticmethod
    def _en_cache(reponse: Reponse) -> dict:
        """Ce qu'on rejoue depuis le cache. La trace n'en fait pas partie : elle
        decrit un appel qui n'aura pas lieu la fois suivante."""
        return {
            "texte": reponse.texte,
            "intention": reponse.intention.value,
            "sql": reponse.sql,
            "colonnes": reponse.colonnes,
            "lignes": reponse.lignes,
            "tronque": reponse.tronque,
            "besoin_visualisation": reponse.besoin_visualisation,
        }

    async def _archiver(
        self, session: AsyncSession, workspace_id: str, question: str, reponse: Reponse
    ) -> None:
        session.add(ChatMessage(workspace_id=workspace_id, role="user", content=question))
        session.add(
            ChatMessage(
                workspace_id=workspace_id,
                role="assistant",
                content=reponse.texte,
                sql_executed=reponse.sql,
                agent_trace={"appels": reponse.trace},
                cost_cents=reponse.cout_centimes,
                cached=reponse.depuis_cache,
            )
        )
        await session.commit()


# Les intentions qui ne touchent pas aux donnees ont une reponse ecrite d'avance :
# c'est plus rapide, gratuit, et surtout previsible le jour de la demonstration.
REPONSES_SANS_DONNEES: dict[Intention, str] = {
    Intention.SALUTATION: (
        "Bonjour. Posez-moi une question sur vos fichiers — un total, une moyenne, "
        "une répartition par service — et je vous réponds en français, avec la requête "
        "que j'ai exécutée."
    ),
    Intention.HORS_SUJET: (
        "Cette question ne porte pas sur les fichiers de cet espace. "
        "Je ne sais répondre que sur les données que vous avez déposées."
    ),
    Intention.EXPLORATION: (
        "Le détail des colonnes, des types et des anomalies se trouve à l'étape "
        "Exploration. Pour une valeur précise, posez la question directement."
    ),
    Intention.NETTOYAGE: (
        "Je ne modifie jamais vos données depuis la conversation. Les corrections se "
        "font à l'étape Exploration, où chaque transformation est tracée et réversible."
    ),
    Intention.PREDICTION: (
        "Les prédictions arrivent à l'étape IA & prédictions. "
        "En attendant, je peux analyser ce que vos données contiennent aujourd'hui."
    ),
    Intention.RAPPORT: (
        "La synthèse écrite se génère à l'étape Rapport, à partir de tout ce qui a été "
        "analysé dans cet espace."
    ),
}
