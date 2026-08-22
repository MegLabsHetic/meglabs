"""Chargement des prompts.

Un prompt est du code : il vit dans un fichier versionne, il se relit en revue, et il
se modifie par une pull request. L'ecrire en dur dans une methode le rendrait invisible
dans un diff et impossible a comparer d'une version a l'autre.

La partie stable de chaque prompt est en tete de fichier : c'est elle que le
fournisseur met en cache (voir `llm_client`), et elle n'y arrive que si elle precede
les elements variables.
"""

from functools import lru_cache
from pathlib import Path

DOSSIER = Path(__file__).parent


@lru_cache
def charger(nom: str) -> str:
    """Le contenu d'un prompt, lu une seule fois par processus.

    Un prompt manquant est une erreur de programmation, pas une erreur d'utilisateur :
    on echoue au premier appel plutot que d'envoyer une instruction vide au modele.
    """
    fichier = DOSSIER / f"{nom}.md"
    if not fichier.is_file():
        disponibles = ", ".join(sorted(chemin.stem for chemin in DOSSIER.glob("*.md")))
        raise FileNotFoundError(f"Prompt « {nom} » introuvable. Disponibles : {disponibles}.")
    return fichier.read_text(encoding="utf-8").strip()
