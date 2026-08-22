"""Bus d'evenements : ce que les agents font, rendu visible en direct.

C'est un contrat d'interface, pas une commodite. La demonstration repose sur le fait
que le jury VOIT la chaine d'agents s'allumer ; si un agent travaille sans rien emettre,
l'ecran reste figé et l'architecture multi-agents redevient une affirmation.

Le meme flux transporte les evenements d'agents et les fragments de la reponse finale :
un seul canal a ouvrir, un seul a fermer.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

# Types transportes. Ce sont des identifiants de protocole, lus par le client — le
# francais vit dans les donnees, pas dans les noms d'evenements.
AGENT = "agent_status"
JETON = "token"
SQL = "sql"
REPARATION = "sql_healing"
ERREUR = "erreur"
FIN = "done"

# Etats d'un agent, tels que l'interface les affiche.
DEMARRE = "started"
TRAVAILLE = "working"
TERMINE = "done"


@dataclass(frozen=True)
class Evenement:
    type: str
    donnees: dict = field(default_factory=dict)

    def en_sse(self) -> str:
        """Format Server-Sent Events. La ligne vide finale termine l'evenement."""
        charge = json.dumps(self.donnees, ensure_ascii=False)
        return f"event: {self.type}\ndata: {charge}\n\n"


def evenement_agent(agent: str, etat: str, detail: str, duree_ms: int | None = None) -> Evenement:
    """Un agent signale ou il en est, en francais et sans jargon."""
    donnees: dict = {"agent": agent, "etat": etat, "detail": detail}
    if duree_ms is not None:
        donnees["duree_ms"] = duree_ms
    return Evenement(AGENT, donnees)


def evenement_sql(sql: str, duree_ms: int, nb_lignes: int, tronque: bool) -> Evenement:
    """La requete reellement executee. Elle est montree, jamais resumee."""
    return Evenement(
        SQL,
        {"sql": sql, "duree_ms": duree_ms, "nb_lignes": nb_lignes, "tronque": tronque},
    )


def evenement_reparation(sql_echoue: str, erreur: str, sql_corrige: str, explication: str) -> Evenement:
    """L'auto-reparation, rendue visible.

    Une correction silencieuse serait plus confortable et beaucoup moins credible :
    montrer l'echec puis la correction est ce qui prouve que le mecanisme existe.
    """
    return Evenement(
        REPARATION,
        {
            "sql_echoue": sql_echoue,
            "erreur": erreur,
            "sql_corrige": sql_corrige,
            "explication": explication,
        },
    )


class FluxEvenements:
    """File d'attente d'une conversation. Les agents publient, la route SSE consomme.

    Bornee volontairement : si le client se deconnecte sans consommer, une file
    illimitee garderait la memoire du serveur en otage. Au-dela de la borne, les
    evenements d'agents sont abandonnes plutot que de bloquer le traitement — perdre
    une animation est acceptable, bloquer une reponse ne l'est pas.
    """

    def __init__(self, taille_max: int = 256) -> None:
        self._file: asyncio.Queue[Evenement | None] = asyncio.Queue(maxsize=taille_max)
        self._clos = False
        self.abandonnes = 0

    async def publier(self, evenement: Evenement) -> None:
        if self._clos:
            return
        try:
            self._file.put_nowait(evenement)
        except asyncio.QueueFull:
            self.abandonnes += 1

    async def cloturer(self) -> None:
        """Signale la fin du flux. Idempotent : une double cloture ne casse rien."""
        if self._clos:
            return
        self._clos = True
        await self._file.put(None)

    async def __aiter__(self) -> AsyncIterator[Evenement]:
        while True:
            evenement = await self._file.get()
            if evenement is None:
                return
            yield evenement

    async def en_sse(self) -> AsyncIterator[str]:
        """Le flux pret a etre renvoye par une reponse HTTP."""
        async for evenement in self:
            yield evenement.en_sse()
