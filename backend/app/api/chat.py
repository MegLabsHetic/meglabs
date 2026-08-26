"""Route de la conversation. Couche fine : le pipeline vit dans `query_service`.

La reponse est un flux Server-Sent Events. Le meme canal transporte trois choses :
l'avancee des agents, la reponse au fil de l'eau, et le recapitulatif final. Une
seule connexion a ouvrir, une seule a fermer, et l'interface n'a pas a deviner
l'ordre d'arrivee.
"""

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.debit import LIMITE_CONVERSATION, limiteur
from app.core.errors import ErreurUtilisateur
from app.core.events import ERREUR, FIN, Evenement, FluxEvenements
from app.services.query_service import QueryService

router = APIRouter(prefix="/api/chat", tags=["conversation"])
service = QueryService()

# Les proxys qui tamponnent les reponses retiennent un flux SSE jusqu'a sa fin, ce
# qui annule tout l'interet du direct. Cet en-tete le leur interdit.
ENTETES_SSE = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@router.post("/{workspace_id}")
@limiteur.limit(LIMITE_CONVERSATION)
async def poser(
    workspace_id: str,
    demande: Question,
    # `slowapi` lit l'adresse dans la requete : le parametre est obligatoire
    # meme quand la fonction ne s'en sert pas.
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    flux = FluxEvenements()
    tache = asyncio.create_task(_repondre(session, workspace_id, demande.question, flux))
    # La tache est referencee par la fermeture du generateur : sans cela, le
    # ramasse-miettes pourrait l'interrompre avant qu'elle ait termine.
    return StreamingResponse(
        _diffuser(flux, tache), media_type="text/event-stream", headers=ENTETES_SSE
    )


async def _repondre(
    session: AsyncSession, workspace_id: str, question: str, flux: FluxEvenements
) -> None:
    """Deroule le pipeline et cloture le flux, quoi qu'il arrive.

    Une erreur est publiee sur le flux plutot que levee : le client a deja recu un
    200 et des evenements, il ne verrait jamais un code d'erreur HTTP.
    """
    try:
        reponse = await service.repondre(session, workspace_id, question, flux)
        await flux.publier(Evenement(FIN, _recapituler(reponse)))
    except ErreurUtilisateur as erreur:
        await flux.publier(Evenement(ERREUR, {"message": erreur.message}))
    except Exception:
        await flux.publier(
            Evenement(
                ERREUR,
                {
                    "message": "Une erreur inattendue est survenue pendant l'analyse. "
                    "Reformulez votre question ou réessayez dans un instant."
                },
            )
        )
        raise
    finally:
        await flux.cloturer()


async def _diffuser(flux: FluxEvenements, tache: asyncio.Task):
    try:
        async for morceau in flux.en_sse():
            yield morceau
    finally:
        # Le client peut fermer l'onglet en cours de route : la tache doit s'arreter
        # plutot que de continuer a calculer pour personne.
        if not tache.done():
            tache.cancel()
        await asyncio.gather(tache, return_exceptions=True)


def _recapituler(reponse) -> dict:
    """Le dernier evenement porte tout ce qui n'etait pas diffusable au fil de l'eau."""
    return {
        "texte": reponse.texte,
        "intention": reponse.intention.value,
        "sql": reponse.sql,
        "colonnes": reponse.colonnes,
        "lignes": reponse.lignes,
        "tronque": reponse.tronque,
        "besoin_visualisation": reponse.besoin_visualisation,
        "cout_centimes": reponse.cout_centimes,
        "depuis_cache": reponse.depuis_cache,
        "trace": reponse.trace,
    }
