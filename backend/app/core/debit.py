"""Limitation de debit : ce qu'une meme adresse a le droit de demander.

Trois routes en ont besoin, pour trois raisons differentes.

**La conversation** appelle un fournisseur payant. Sans borne, une boucle — un
script, un onglet laisse ouvert, quelqu'un de mal intentionne — epuise le budget
d'API en quelques minutes. C'est la borne qui protege le portefeuille.

**Le depot de fichier** ecrit sur le disque et profile en memoire. C'est la borne
qui protege la machine.

**La lecture d'un rapport partage** est la seule route publique sans compte. Sans
borne, un jeton se cherche par force brute. Trente-deux octets d'alea rendent la
recherche impraticable en theorie ; la borne la rend inutile en pratique.

**L'adresse est lue derriere le proxy.** Caddy est le seul a parler au monde
exterieur, donc toutes les requetes semblent venir de lui : sans lire
`X-Forwarded-For`, la limite s'appliquerait a tous les visiteurs ensemble et le
premier gourmand bloquerait tous les autres.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Ce que Caddy renseigne. On lui fait confiance parce qu'il est le seul chemin
# vers l'application : les conteneurs ne publient aucun port. Exposer le backend
# directement rendrait cet en-tete falsifiable, et cette confiance fausse.
ENTETE_PROXY = "X-Forwarded-For"

# Chiffres choisis pour une demonstration, pas pour un service en charge : ils
# doivent laisser passer un utilisateur curieux et arreter une boucle.
LIMITE_CONVERSATION = "20/minute"
LIMITE_DEPOT = "10/minute"
LIMITE_PARTAGE = "60/minute"

MESSAGE = (
    "Trop de demandes en peu de temps. Patientez une minute avant de réessayer — "
    "c'est une limite volontaire, pas une panne."
)


def adresse(request: Request) -> str:
    """L'adresse du visiteur, et non celle du proxy.

    Le premier element de `X-Forwarded-For` est le client d'origine ; les
    suivants sont les relais traverses.

    **Le parametre s'appelle `request` et non `requete`, et ce n'est pas une
    negligence.** `slowapi` decide de passer ou non la requete en inspectant le
    NOM du parametre :

        if "request" in inspect.signature(lim.key_func).parameters.keys():
            limit_key = lim.key_func(request)
        else:
            limit_key = lim.key_func()

    Avec un nom francais, la fonction est appelee sans argument et leve une
    `TypeError` a chaque requete limitee. C'est le seul endroit du projet ou la
    convention de nommage cede, et elle cede a une contrainte de bibliotheque.
    """
    transmise = request.headers.get(ENTETE_PROXY)
    if transmise:
        return transmise.split(",")[0].strip()
    return get_remote_address(request)


limiteur = Limiter(key_func=adresse)
