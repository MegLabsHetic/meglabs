"""Journalisation structuree : une ligne JSON par evenement, correlee par requete.

Sans elle, une panne en production ne laisse aucune trace : on constate qu'une
question echoue, et le serveur ne dit rien de plus qu'un code HTTP. Le diagnostic
se fait alors en rejouant l'appel a la main depuis un poste de developpement,
avec les identifiants de production — ce qui est lent et dangereux.

Deux choix expliquent le reste du module.

**Du JSON, pas du texte.** `docker logs` reste lisible, et n'importe quel
collecteur (Loki, un simple `jq`) filtre sans expression reguliere fragile.

**Un identifiant de requete propage par `contextvars`.** La chaine d'agents est
asynchrone et traverse une dizaine de fonctions ; passer l'identifiant en
parametre a chacune polluerait toutes les signatures pour un besoin technique.
Un contexte le rend disponible partout sans etre visible nulle part.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings

# Renseigne par le middleware HTTP, lu par le formateur. Absent hors requete —
# au demarrage, ou dans un script — et c'est normal.
id_requete: ContextVar[str | None] = ContextVar("id_requete", default=None)

# Attributs que `logging` pose sur chaque enregistrement. Tout ce qui n'est pas
# dans cette liste vient d'un `extra=` et merite donc d'etre publie.
STANDARD = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

# Ces cles ne doivent jamais sortir, meme si un appelant les passe par erreur.
# Un secret dans un journal est un secret divulgue : les journaux se copient,
# se transmettent et survivent au serveur qui les a produits.
INTERDITES = frozenset({"api_key", "password", "mot_de_passe", "token", "secret", "authorization"})


class FormateurJson(logging.Formatter):
    """Un evenement, une ligne JSON."""

    def format(self, record: logging.LogRecord) -> str:
        evenement: dict[str, Any] = {
            "horodatage": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "niveau": record.levelname,
            "source": record.name,
            "message": record.getMessage(),
        }

        requete = id_requete.get()
        if requete:
            evenement["requete"] = requete

        for cle, valeur in record.__dict__.items():
            if cle in STANDARD or cle.startswith("_") or cle in INTERDITES:
                continue
            evenement[cle] = valeur

        if record.exc_info:
            # Le type et le message suffisent au tri ; la pile complete est
            # gardee a part pour ne pas rendre la ligne illisible.
            type_erreur, valeur, _ = record.exc_info
            evenement["erreur"] = getattr(type_erreur, "__name__", str(type_erreur))
            evenement["detail"] = str(valeur)
            evenement["pile"] = self.formatException(record.exc_info)

        return json.dumps(evenement, ensure_ascii=False, default=str)


def configurer() -> None:
    """Installe le formateur sur la sortie standard. Idempotent.

    Docker capture stdout : ecrire ailleurs qu'en sortie standard reviendrait a
    produire des journaux que le conteneur n'expose pas.
    """
    settings = get_settings()
    racine = logging.getLogger()

    if any(isinstance(h.formatter, FormateurJson) for h in racine.handlers):
        return

    sortie = logging.StreamHandler(sys.stdout)
    sortie.setFormatter(FormateurJson())

    racine.handlers = [sortie]
    racine.setLevel(settings.log_level.upper())

    # Uvicorn installe ses propres gestionnaires : sans cette remise a zero, ses
    # lignes sortiraient en texte a cote des notres, et un collecteur verrait un
    # flux a moitie structure.
    for nom in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(nom)
        logger.handlers = []
        logger.propagate = True


def obtenir(nom: str) -> logging.Logger:
    """Le journal d'un module. `obtenir(__name__)` partout."""
    return logging.getLogger(nom)
