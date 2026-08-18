"""Decoupage d'un tableau plat en plusieurs tables liees.

Un export de tableur repete la meme information a chaque ligne : le nom du
client, sa ville et son segment reapparaissent a chacune de ses commandes.
Cette redondance fait grossir l'entrepot, et surtout elle rend les mises a
jour incoherentes — corriger une ville oblige a la corriger partout.

On detecte donc les DEPENDANCES FONCTIONNELLES : quand une colonne en
determine d'autres (un identifiant client determine toujours la meme ville),
ces colonnes forment une table a part, reliee par une cle.

Tout est deterministe : une dependance fonctionnelle se verifie, elle ne
s'interprete pas. Aucun appel a un modele.
"""

import re

import pandas as pd

# Une cle candidate doit se repeter : si chaque ligne a sa propre valeur,
# extraire une table ne factoriserait rien.
_REPETITION_MIN = 1.5
# Au-dela, la colonne ressemble a un identifiant de ligne, pas a une entite.
_PART_UNIQUE_MAX = 0.7

_MOTIF_CLE = re.compile(r"(^|_)(id|code|ref|reference|numero|num)($|_)", re.IGNORECASE)


def _est_cle_plausible(serie: pd.Series, lignes: int) -> bool:
    distinctes = serie.nunique(dropna=True)
    if distinctes < 2 or distinctes >= lignes:
        return False
    if lignes / distinctes < _REPETITION_MIN:
        return False
    return distinctes / lignes <= _PART_UNIQUE_MAX


def _determine(df: pd.DataFrame, cle: str, cible: str) -> bool:
    """`cle` determine-t-elle `cible` ? Une valeur de cle, une seule cible."""
    paires = df[[cle, cible]].dropna(subset=[cle])
    if paires.empty:
        return False
    return bool(paires.groupby(cle, observed=True)[cible].nunique(dropna=True).max() <= 1)


def _score_cle(nom: str, serie: pd.Series, lignes: int) -> float:
    """Une cle nommee « client_id » vaut mieux qu'une cle nommee « ville »."""
    score = 0.0
    if _MOTIF_CLE.search(str(nom)):
        score += 10
    # Moins il y a de valeurs distinctes, plus la factorisation est rentable.
    score += lignes / max(1, serie.nunique(dropna=True))
    return score


def _sans_information(serie: pd.Series) -> bool:
    """Colonne vide ou constante : elle est determinee par n'importe quoi.

    Sans ce filtre, une colonne « devise » toujours egale a « EUR » serait
    happee par la premiere dimension venue, ou elle n'a rien a faire.
    """
    return serie.nunique(dropna=True) <= 1


def proposer_decoupage(df: pd.DataFrame, min_attributs: int = 1) -> list[dict]:
    """Propose des tables a extraire du tableau plat.

    Renvoie une liste de {nom, cle, attributs, lignes, economie}.
    """
    lignes = len(df)
    if lignes < 10 or len(df.columns) < 3:
        return []

    # Les colonnes sans information sont ecartees d'emblee : elles ne peuvent
    # etre ni cle ni attribut pertinent.
    exploitables = [c for c in df.columns if not _sans_information(df[c])]
    if len(exploitables) < 3:
        return []
    df = df[exploitables]

    candidates = [c for c in df.columns if _est_cle_plausible(df[c], lignes)]
    if not candidates:
        return []

    # La meilleure cle d'abord : les colonnes qu'elle capte ne seront pas
    # reproposees a une cle moins pertinente.
    candidates.sort(key=lambda c: _score_cle(c, df[c], lignes), reverse=True)

    propositions: list[dict] = []
    deja_prises: set = set()

    for cle in candidates:
        if cle in deja_prises:
            continue
        attributs = [
            c
            for c in df.columns
            if c != cle and c not in deja_prises and _determine(df, cle, c)
        ]
        if len(attributs) < min_attributs:
            continue

        distinctes = int(df[cle].nunique(dropna=True))
        # Ce qu'on cesse de recopier : (lignes - lignes distinctes) x colonnes.
        economie = (lignes - distinctes) * len(attributs)

        propositions.append({
            "cle": str(cle),
            "attributs": [str(a) for a in attributs],
            "lignes": distinctes,
            "economie": int(economie),
            "nom_suggere": _nom_de_table(str(cle)),
        })
        deja_prises.update([cle, *attributs])

    # Le decoupage le plus rentable en tete.
    propositions.sort(key=lambda p: p["economie"], reverse=True)
    return propositions


def _nom_de_table(cle: str) -> str:
    """« client_id » -> « clients », « ville » -> « villes »."""
    base = _MOTIF_CLE.sub("_", cle).strip("_") or cle
    base = re.sub(r"[^a-z0-9_]+", "_", base.lower()).strip("_") or "dimension"
    return base if base.endswith("s") else base + "s"


def decouper(df: pd.DataFrame, decoupages: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    """Applique les decoupages retenus.

    Renvoie (table de faits, [{nom, dataframe, cle}]). La table de faits
    conserve les cles : ce sont elles qui relient l'ensemble.
    """
    faits = df.copy()
    dimensions: list[dict] = []

    for d in decoupages or []:
        cle = d.get("cle")
        attributs = [a for a in (d.get("attributs") or []) if a in faits.columns]
        if cle not in faits.columns or not attributs:
            continue

        # Une ligne par valeur de cle, avec ses attributs.
        table = (
            df[[cle, *attributs]]
            .dropna(subset=[cle])
            .drop_duplicates(subset=[cle])
            .reset_index(drop=True)
        )
        dimensions.append({
            "nom": d.get("nom") or _nom_de_table(str(cle)),
            "cle": str(cle),
            "dataframe": table,
        })
        # Les attributs quittent la table de faits ; la cle y reste.
        faits = faits.drop(columns=attributs)

    return faits, dimensions
