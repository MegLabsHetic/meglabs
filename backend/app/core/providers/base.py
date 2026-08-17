"""Contrat commun aux fournisseurs de modeles.

Chaque fournisseur traduit une `Requete` en appel natif et rend une `ReponseBrute`.
Il ne decide rien : ni le modele, ni les tentatives, ni le cout. Tout cela vit dans
`LlmClient`, qui est le seul endroit ou lire ces politiques.
"""

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


class Fournisseur(Protocol):
    """Un fournisseur de modeles de langage."""

    nom: str

    async def repondre(self, requete: Requete) -> ReponseBrute: ...
