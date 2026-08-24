"""Contrat commun aux fournisseurs de modeles.

Chaque fournisseur traduit une `Requete` en appel natif et rend une `ReponseBrute`.
Il ne decide rien : ni le modele, ni les tentatives, ni le cout. Tout cela vit dans
`LlmClient`, qui est le seul endroit ou lire ces politiques.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Requete:
    """Ce qu'on demande a un modele, independamment du fournisseur."""

    modele: str
    instruction: str
    question: str
    max_tokens: int = 2048
    # Schema JSON attendu en sortie. Nul pour une reponse en texte libre.
    schema: dict | None = None
    nom_schema: str = "reponse"
    # Reduit la profondeur de raisonnement quand le fournisseur le permet. Mesure sur
    # Groq : passer a « low » divise les tokens de sortie par pres de 4 a reponse
    # identique — c'est le levier de frugalite le plus direct.
    effort: str | None = None


@dataclass(frozen=True)
class ReponseBrute:
    """Ce qu'un fournisseur rend, avant validation et comptage."""

    texte: str
    tokens_entree: int
    tokens_sortie: int
    tokens_caches: int = 0
    raison_arret: str = "stop"
    # Le raisonnement des modeles qui en produisent. Conserve pour le debogage, jamais
    # affiche a l'utilisateur ni renvoye au modele.
    raisonnement: str = ""
    avertissements: list[str] = field(default_factory=list)

    @property
    def tronquee(self) -> bool:
        """Vrai quand le modele a ete coupe avant d'avoir fini.

        A traiter comme un echec, pas comme une reponse : sur les modeles a
        raisonnement, une coupure produit un contenu VIDE sans lever d'erreur. On
        facturerait alors un appel qui ne rend rien.
        """
        return self.raison_arret == "length" or not self.texte.strip()


def adapter_strict(schema: dict) -> dict:
    """Rend un schema Pydantic acceptable par le mode strict de Groq et d'OpenAI.

    Les deux exigent la meme chose : chaque propriete listee dans `required`, et
    `additionalProperties: false`. Or Pydantic omet de `required` tout champ pourvu
    d'une valeur par defaut — un schema parfaitement valide, refuse avec un 400.

    Rendre un champ obligatoire ne le rend pas non nul : un `str | None` reste
    nullable, le modele doit simplement se prononcer explicitement. C'est meme
    preferable ici, une omission etant plus ambigue qu'un `null` assume.
    """
    adapte = dict(schema)
    proprietes = adapte.get("properties")
    if isinstance(proprietes, dict):
        adapte["required"] = list(proprietes)
        adapte["additionalProperties"] = False
        adapte["properties"] = {
            nom: adapter_strict(valeur) if isinstance(valeur, dict) else valeur
            for nom, valeur in proprietes.items()
        }

    # Les schemas imbriques que Pydantic sort dans `$defs` obeissent aux memes regles.
    definitions = adapte.get("$defs")
    if isinstance(definitions, dict):
        adapte["$defs"] = {nom: adapter_strict(valeur) for nom, valeur in definitions.items()}
    return adapte


@dataclass(frozen=True)
class Fragment:
    """Un morceau de reponse en cours d'arrivee.

    Le dernier fragment ne porte pas de texte mais le decompte complet : les jetons ne
    sont connus qu'a la fermeture du flux, et un appel diffuse doit etre facture comme
    les autres. Sans ce fragment terminal, le streaming serait un trou dans le compteur.
    """

    texte: str = ""
    fin: ReponseBrute | None = None


class Fournisseur(Protocol):
    """Un fournisseur de modeles de langage."""

    nom: str

    async def repondre(self, requete: Requete) -> ReponseBrute: ...

    def diffuser(self, requete: Requete) -> AsyncIterator[Fragment]:
        """Meme appel, rendu au fil de l'eau. Reserve au texte libre.

        La sortie structuree ne se diffuse pas : un JSON incomplet n'est pas
        validable, et on ne montre pas a l'utilisateur une structure a moitie ecrite.
        """
        ...
