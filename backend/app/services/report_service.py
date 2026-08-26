"""Le rapport d'un espace : ce qui a ete depose, corrige, demande et trouve.

**Presque rien n'est redige par un modele.** Les fichiers, leurs defauts, les
corrections appliquees, les questions posees et le cout de la session sont des
faits deja enregistres : les assembler est du calcul. Un modele n'intervient que
pour la synthese d'ouverture, parce qu'ecrire trois phrases lisibles est
justement ce qu'il fait mieux que nous.

**Le score de confiance est explique, pas affiche.** Un chiffre seul se subit ;
avec ses composantes, il se discute. Il combine la qualite mesuree des donnees,
la part de questions qui ont abouti, et la presence de defauts non corriges —
trois choses que le lecteur peut verifier ailleurs dans le rapport.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Task
from app.core.journal import obtenir
from app.models.chat_message import ChatMessage
from app.models.cleaning_action import CleaningAction
from app.models.data_file import DataFile
from app.models.workspace import Workspace
from app.prompts import charger
from app.services.file_service import FileService

journal = obtenir(__name__)

# Au-dela, le rapport devient un journal de conversation plutot qu'une synthese.
MAX_ECHANGES = 15

# Ce que le score de confiance pese. Les trois se lisent ailleurs dans le
# rapport : personne n'a a croire le chiffre sur parole.
POIDS_QUALITE = 0.5
POIDS_REUSSITE = 0.3
POIDS_CORRECTIONS = 0.2


@dataclass
class Echange:
    question: str
    reponse: str
    sql: str | None
    cout_centimes: float


class ReportService:
    """Assemble un rapport a partir de ce que l'espace contient deja."""

    def __init__(self, fichiers: FileService | None = None) -> None:
        self._fichiers = fichiers or FileService()

    async def construire(self, session: AsyncSession, workspace_id: str) -> dict:
        """Le rapport complet, sans appel a un modele."""
        espace = await session.get(Workspace, workspace_id)
        fichiers = await self._fichiers.lister(session, workspace_id)
        echanges = await self._echanges(session, workspace_id)
        corrections = await self._corrections(session, fichiers)

        sources = [self._decrire(fichier) for fichier in fichiers]
        confiance = self._confiance(sources, echanges, corrections)

        return {
            "espace": espace.name if espace else "Espace",
            "genere_le": None,
            "sources": sources,
            "corrections": corrections,
            "questions": [vars(echange) for echange in echanges],
            "confiance": confiance,
            "cout": {
                "centimes": round(sum(e.cout_centimes for e in echanges), 4),
                "questions": len(echanges),
            },
        }

    # --- Les sources ---------------------------------------------------------

    def _decrire(self, fichier: DataFile) -> dict:
        """Ce qu'on sait d'un fichier, tel que le profilage l'a mesure."""
        profil = fichier.profile or {}
        colonnes = profil.get("colonnes", [])
        return {
            "nom": fichier.name,
            "lignes": profil.get("nb_lignes", 0),
            "colonnes": profil.get("nb_colonnes", 0),
            "score_qualite": profil.get("score_qualite"),
            "doublons": profil.get("doublons", {}).get("nombre", 0),
            "penalites": profil.get("explication_qualite", []),
            "statut_pii": fichier.pii_status,
            "anomalies": self._anomalies(colonnes),
        }

    @staticmethod
    def _anomalies(colonnes: list[dict]) -> list[dict]:
        """Les defauts encore presents, regroupes par nature."""
        par_type: dict[str, list[str]] = {}
        for colonne in colonnes:
            for anomalie in colonne.get("anomalies", []):
                par_type.setdefault(anomalie["type"], []).append(colonne["nom"])
        return [{"type": type_, "colonnes": noms} for type_, noms in par_type.items()]

    # --- Ce qui a ete fait ---------------------------------------------------

    async def _corrections(self, session: AsyncSession, fichiers: list[DataFile]) -> list[dict]:
        """Les nettoyages appliques, avec le fichier qu'ils concernent.

        Seules les actions actives sont listees : une action desactivee n'a plus
        d'effet sur l'etat courant, donc l'annoncer serait faux.
        """
        if not fichiers:
            return []
        identifiants = [fichier.id for fichier in fichiers]
        noms = {fichier.id: fichier.name for fichier in fichiers}

        resultat = await session.execute(
            select(CleaningAction)
            .where(
                CleaningAction.file_id.in_(identifiants),
                CleaningAction.enabled.is_(True),
            )
            .order_by(CleaningAction.order_index)
        )
        return [
            {
                "fichier": noms.get(action.file_id, "?"),
                "type": action.action_type,
                "colonne": action.column_name,
                "lignes_affectees": action.rows_affected,
                # Les valeurs figees servent a l'export notebook : sans elles il
                # recalculerait la mediane et ne reproduirait pas le resultat montre.
                "params": action.params or {},
            }
            for action in resultat.scalars()
        ]

    async def _echanges(self, session: AsyncSession, workspace_id: str) -> list[Echange]:
        """Les questions posees et ce qu'elles ont rendu."""
        resultat = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.workspace_id == workspace_id)
            .order_by(ChatMessage.created_at)
        )
        messages = list(resultat.scalars())

        echanges: list[Echange] = []
        question: str | None = None
        for message in messages:
            if message.role == "user":
                question = message.content
            elif question is not None:
                echanges.append(
                    Echange(question, message.content, message.sql_executed, message.cost_cents)
                )
                question = None
        return echanges[-MAX_ECHANGES:]

    # --- Le score ------------------------------------------------------------

    def _confiance(
        self, sources: list[dict], echanges: list[Echange], corrections: list[dict]
    ) -> dict:
        """Trois composantes, chacune verifiable ailleurs dans le rapport."""
        scores = [s["score_qualite"] for s in sources if s["score_qualite"] is not None]
        qualite = sum(scores) / len(scores) if scores else 0.0

        restantes = sum(len(a["colonnes"]) for s in sources for a in s["anomalies"])
        # Une anomalie corrigee ne compte plus ; il reste a mesurer celles qui
        # subsistent, rapportees au nombre de colonnes de l'espace.
        colonnes = sum(s["colonnes"] for s in sources) or 1
        proprete = max(0.0, 100.0 - (restantes / colonnes) * 100)

        composantes = [
            ("Qualité mesurée des données", qualite, POIDS_QUALITE),
            ("Colonnes sans anomalie restante", proprete, POIDS_CORRECTIONS),
        ]

        # Sans question posee, cette composante est retiree du calcul plutot que
        # comptee a zero : un espace ou personne n'a encore rien demande n'est pas
        # moins fiable, il est seulement moins exploite. La compter nulle punirait
        # l'utilisateur d'avoir ouvert son rapport trop tot.
        if echanges:
            avec_sql = sum(1 for echange in echanges if echange.sql)
            composantes.insert(
                1,
                (
                    "Questions ayant abouti à une requête",
                    avec_sql / len(echanges) * 100,
                    POIDS_REUSSITE,
                ),
            )

        total_poids = sum(poids for _, _, poids in composantes)
        score = sum(valeur * poids for _, valeur, poids in composantes) / total_poids

        return {
            "score": round(score, 1),
            "composantes": [
                {
                    "libelle": libelle,
                    "valeur": round(valeur, 1),
                    "poids": round(poids / total_poids, 2),
                }
                for libelle, valeur, poids in composantes
            ],
            "corrections_appliquees": len(corrections),
        }

    # --- La seule partie redigee --------------------------------------------

    async def resumer(self, rapport: dict, agent) -> str:
        """Trois phrases d'ouverture, ecrites par le modele.

        Il ne calcule rien : tout ce qu'il cite figure deja dans le rapport, et le
        rapport reste complet et lisible sans cette section — un modele
        indisponible ne doit pas empecher de rendre le document.
        """
        try:
            return await agent.rediger(
                Task.REPORT, charger("report_summary"), self._contexte(rapport), max_tokens=400
            )
        except Exception:  # noqa: BLE001 - un resume manquant n'invalide pas le rapport
            journal.warning("resume du rapport indisponible", exc_info=True)
            return ""

    @staticmethod
    def _contexte(rapport: dict) -> str:
        sources = "\n".join(
            f"- {s['nom']} : {s['lignes']} lignes, {s['colonnes']} colonnes, "
            f"qualité {s['score_qualite']}/100"
            for s in rapport["sources"]
        )
        questions = "\n".join(f"- {q['question']}" for q in rapport["questions"][:8])
        return (
            f"## Fichiers\n\n{sources}\n\n"
            f"## Corrections appliquées\n\n{len(rapport['corrections'])}\n\n"
            f"## Questions posées\n\n{questions or 'aucune'}\n\n"
            f"## Score de confiance\n\n{rapport['confiance']['score']}/100"
        )
