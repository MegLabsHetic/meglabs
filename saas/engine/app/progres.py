"""Suivi d'avancement des traitements longs.

Charger un fichier de plusieurs dizaines de milliers de lignes prend quelques
secondes : le decodage, les corrections, le decoupage, l'ecriture dans
l'entrepot et le typage des colonnes s'enchainent. Sans retour, l'interface
n'a qu'un « en cours » a afficher — l'utilisateur ne sait ni ou en est le
traitement, ni ce qu'il reste.

Chaque etape s'annonce donc ici pendant qu'elle s'execute, et l'api vient
lire cet etat pour le relayer au navigateur. Ce qui est affiche correspond
au travail reellement effectue : rien n'est simule pour faire patienter.

Le suivi vit en memoire. Il n'a de valeur que pendant le traitement et le
perdre au redemarrage est sans consequence — le job, lui, est en base. Un
deploiement multi-processus demanderait un stockage partage (Redis).
"""

from collections import OrderedDict
from threading import Lock

# Au-dela, les suivis les plus anciens sont oublies : ils sont termines
# depuis longtemps et personne ne les relit.
_MAX_SUIVIS = 64

_suivis: "OrderedDict[str, dict]" = OrderedDict()
_verrou = Lock()


def _suivi(trace: str) -> dict | None:
    return _suivis.get(trace)


def planifier(trace: str, etapes: list[tuple[str, str]]) -> None:
    """Annonce le plan complet AVANT de commencer.

    L'interface peut ainsi montrer d'emblee ce qui va se passer, et non
    reveler les etapes une par une comme si le programme improvisait.
    """
    if not trace:
        return
    with _verrou:
        _suivis[trace] = {
            "etapes": [
                {"cle": cle, "libelle": libelle, "etat": "attente", "detail": None}
                for cle, libelle in etapes
            ],
            "termine": False,
            "erreur": None,
        }
        _suivis.move_to_end(trace)
        while len(_suivis) > _MAX_SUIVIS:
            _suivis.popitem(last=False)


def commencer(trace: str, cle: str) -> None:
    if not trace:
        return
    with _verrou:
        suivi = _suivi(trace)
        if not suivi:
            return
        for e in suivi["etapes"]:
            if e["cle"] == cle:
                e["etat"] = "cours"
                return


def achever(trace: str, cle: str, detail: str | None = None) -> None:
    if not trace:
        return
    with _verrou:
        suivi = _suivi(trace)
        if not suivi:
            return
        for e in suivi["etapes"]:
            if e["cle"] == cle:
                e["etat"] = "faite"
                if detail:
                    e["detail"] = detail
                return


def retirer(trace: str, cle: str) -> None:
    """Retire une etape devenue inutile (rien a corriger, aucun decoupage).

    La laisser en attente pour l'eternite donnerait une liste qui n'aboutit
    jamais.
    """
    if not trace:
        return
    with _verrou:
        suivi = _suivi(trace)
        if suivi:
            suivi["etapes"] = [e for e in suivi["etapes"] if e["cle"] != cle]


def terminer(trace: str) -> None:
    if not trace:
        return
    with _verrou:
        suivi = _suivi(trace)
        if suivi:
            suivi["termine"] = True


def echouer(trace: str, message: str) -> None:
    """L'etape en cours porte l'echec : c'est elle qui a lache."""
    if not trace:
        return
    with _verrou:
        suivi = _suivi(trace)
        if not suivi:
            return
        suivi["erreur"] = message
        suivi["termine"] = True
        for e in suivi["etapes"]:
            if e["etat"] == "cours":
                e["etat"] = "echec"


def lire(trace: str) -> dict:
    with _verrou:
        suivi = _suivi(trace)
        if not suivi:
            return {"etapes": [], "termine": False, "erreur": None, "connu": False}
        # Copie : l'appelant ne doit pas tenir une reference sur l'etat vivant.
        return {
            "etapes": [dict(e) for e in suivi["etapes"]],
            "termine": suivi["termine"],
            "erreur": suivi["erreur"],
            "connu": True,
        }
