"""Apparence d'un indicateur : ce qui se demande en mots, sans toucher au calcul.

« mets cette courbe en orange », « entoure le pic », « affiche les valeurs sur
les barres » — ces demandes ne changent ni la requete ni le chiffre, seulement
la lecture. Elles vivent donc a part du SQL : rejouer l'indicateur redonne les
memes donnees, habillees comme l'utilisateur l'a voulu.

TOUT CE QUI VIENT DU MODELE EST FILTRE ICI. Un style part dans l'attribut
d'un element de page : recopier une valeur libre reviendrait a laisser un
texte produit par un modele decider de ce que le navigateur execute. Seules
les valeurs de la liste passent, plus une couleur hexadecimale dont on
verifie qu'elle reste lisible.
"""

import re

# Les huit teintes de la palette validee. Une couleur nommee est resolue en
# variable CSS cote interface : elle suit donc le theme clair ou sombre, ce
# qu'un hexadecimal fige ne sait pas faire.
COULEURS = {
    "bleu": 1,
    "orange": 2,
    "aqua": 3,
    "jaune": 4,
    "magenta": 5,
    "vert": 6,
    "violet": 7,
    "rouge": 8,
}

# Ce que les gens ecrivent vraiment.
SYNONYMES = {
    "bleue": "bleu", "blue": "bleu",
    "orangee": "orange", "orangé": "orange", "orangée": "orange",
    "turquoise": "aqua", "cyan": "aqua", "vert_deau": "aqua",
    "jaune_or": "jaune", "dore": "jaune", "doré": "jaune",
    "rose": "magenta", "fuchsia": "magenta",
    "verte": "vert", "green": "vert",
    "violette": "violet", "mauve": "violet", "pourpre": "violet",
    "rouges": "rouge", "red": "rouge",
}

ENTOURAGES = {"max", "min", "extremes"}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# Les deux surfaces sur lesquelles un graphique est reellement pose.
_SURFACES = ((255, 255, 255), (15, 23, 42))

# Seuil de refus d'une couleur libre.
#
# Ce n'est PAS le 3:1 de WCAG 1.4.11 : la palette livree descend elle-meme a
# 2.17 (le jaune sur fond blanc), assume, parce que chaque graphique porte une
# vue tableau jumelle ou la valeur se lit sans la couleur. Exiger 3:1 d'une
# couleur choisie refuserait un orange vif tout en gardant celui de la palette,
# a une nuance pres — un arbitraire que personne ne pourrait comprendre.
#
# On ne refuse donc que l'invisible : une marque a 1.0 de contraste est du
# blanc sur blanc. Le seuil se place sous le plancher de la palette, assez haut
# pour ecarter ce que l'oeil ne peut pas trouver.
_CONTRASTE_MIN = 1.8


def _luminance(rgb: tuple) -> float:
    def canal(c: int) -> float:
        x = c / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    r, v, b = (canal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * v + 0.0722 * b


def _contraste(a: tuple, b: tuple) -> float:
    la, lb = _luminance(a), _luminance(b)
    clair, sombre = max(la, lb), min(la, lb)
    return (clair + 0.05) / (sombre + 0.05)


def _lisible(hexa: str) -> bool:
    """La couleur reste-t-elle visible sur les DEUX surfaces ?

    Les deux, pas une seule : l'utilisateur bascule de theme quand il veut et
    un hexadecimal ne se decline pas, contrairement aux couleurs nommees. Un
    blanc casse disparait sur le mode clair, un bleu nuit sur le mode sombre —
    la marque est dessinee mais introuvable, ce qui est pire qu'un refus.

    Exiger « au moins une des deux » ne servirait a rien : aucune couleur ne
    peut echouer contre le blanc ET contre le bleu nuit a la fois, la
    condition serait toujours vraie.
    """
    rgb = tuple(int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return all(_contraste(rgb, s) >= _CONTRASTE_MIN for s in _SURFACES)


def valider(brut) -> tuple[dict, list]:
    """Filtre une apparence proposee. Renvoie (apparence, refus expliques)."""
    if not isinstance(brut, dict):
        return {}, []

    style: dict = {}
    refus: list = []

    couleur = brut.get("couleur")
    if isinstance(couleur, str) and couleur.strip():
        c = couleur.strip().lower().replace(" ", "_")
        c = SYNONYMES.get(c, c)
        if c in COULEURS:
            style["couleur"] = c
        elif _HEX.match(c):
            if _lisible(c):
                style["couleur"] = c
            else:
                refus.append(
                    f"couleur « {couleur} » ecartee : trop peu contrastee pour rester "
                    "lisible en mode clair comme en mode sombre"
                )
        else:
            refus.append(f"couleur « {couleur} » inconnue")

    entourer = brut.get("entourer")
    if isinstance(entourer, str) and entourer.strip().lower() not in ("", "aucun", "none"):
        e = entourer.strip().lower()
        if e in ENTOURAGES:
            style["entourer"] = e
        else:
            refus.append(f"mise en evidence « {entourer} » inconnue")
    elif entourer in (None, "", "aucun", "none") and "entourer" in brut:
        # Demande explicite de retrait : on l'enregistre pour effacer l'ancien.
        style["entourer"] = None

    if "etiquettes" in brut:
        style["etiquettes"] = bool(brut.get("etiquettes"))

    return style, refus
