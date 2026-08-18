"""Diagnostic de qualite d'un fichier, AVANT chargement dans l'entrepot.

Tout est deterministe : aucun appel a un modele. Les problemes d'un tableau
(doublons, colonnes vides, nombres stockes en texte) se constatent, ils ne
s'interpretent pas. Le modele n'apporterait ici qu'un risque et une latence.

Chaque anomalie devient une action PROPOSEE, avec son impact chiffre. Rien
n'est applique sans validation : c'est l'utilisateur qui decide ce qu'il
sacrifie de ses donnees.
"""

import re

import numpy as np
import pandas as pd

# Un nombre ecrit a la francaise ou avec une unite : « 1 234,56 € », « 12 % ».
# On tolere l'espace fine insecable, courant dans les exports de tableur.
_NOMBRE_HABILLE = re.compile(
    r"^\s*[-+]?\s*[\d   ]{1,20}(?:[.,]\d+)?\s*(?:%|€|\$|£|EUR|USD)?\s*$"
)

# Colonnes sans en-tete : pandas les nomme « Unnamed: 3 » a la lecture d'un
# tableur ou une cellule d'en-tete est vide.
_SANS_NOM = re.compile(r"^Unnamed:?\s*\d+$", re.IGNORECASE)

GRAVITE_BLOQUANT = "bloquant"
GRAVITE_IMPORTANT = "important"
GRAVITE_MINEUR = "mineur"


def _texte(serie: pd.Series) -> pd.Series:
    return serie.dropna().astype(str)


def parse_nombre(serie: pd.Series) -> pd.Series:
    """« 1 234,56 € » -> 1234.56.

    pandas ne sait pas lire ces valeurs : elles restent du texte, et toute
    somme ou moyenne devient impossible. On retire les unites et les
    separateurs de milliers avant de convertir.
    """
    nettoye = (
        serie.astype(str)
        .str.replace(r"[€$£%]|EUR|USD", "", regex=True)
        .str.replace(r"[\s  ]", "", regex=True)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    return pd.to_numeric(nettoye, errors="coerce")


def _ressemble_a_des_nombres(serie: pd.Series, seuil: float = 0.9) -> bool:
    valeurs = _texte(serie)
    if valeurs.empty:
        return False
    habilles = valeurs.str.match(_NOMBRE_HABILLE).sum()
    if habilles / len(valeurs) < seuil:
        return False
    # Un identifiant ou un code postal ressemble a un nombre sans en etre un :
    # on exige qu'au moins une valeur porte une unite ou une decimale.
    return bool(valeurs.str.contains(r"[.,%€$£]").any())


def _ressemble_a_des_dates(serie: pd.Series, seuil: float = 0.9) -> bool:
    valeurs = _texte(serie).head(200)
    if valeurs.empty:
        return False
    motif = valeurs.str.match(r"^\s*\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}")
    return motif.sum() / len(valeurs) >= seuil


def diagnostiquer(df: pd.DataFrame, seuil_manquantes: float = 0.4) -> dict:
    """Inspecte un tableau et propose les corrections a lui appliquer."""
    lignes, colonnes = df.shape
    actions: list[dict] = []
    constats: list[str] = []

    # ── Lignes en double ──────────────────────
    doublons = int(df.duplicated().sum())
    if doublons:
        actions.append({
            "type": "drop_duplicates",
            "column": None,
            "params": {},
            "description": "Supprimer les lignes en double",
            "raison": f"{doublons} ligne(s) strictement identique(s) a une autre",
            "gravite": GRAVITE_IMPORTANT,
            "recommande": True,
        })

    for col in df.columns:
        serie = df[col]
        non_vides = int(serie.notna().sum())
        nom = str(col)

        # ── Colonne entierement vide ──────────
        if non_vides == 0:
            actions.append({
                "type": "drop_column",
                "column": col,
                "params": {},
                "description": f"Supprimer la colonne vide « {nom} »",
                "raison": "Aucune valeur renseignee",
                "gravite": GRAVITE_IMPORTANT,
                "recommande": True,
            })
            continue

        # ── Colonne sans en-tete ──────────────
        if _SANS_NOM.match(nom):
            actions.append({
                "type": "drop_column",
                "column": col,
                "params": {},
                "description": f"Supprimer la colonne sans nom « {nom} »",
                "raison": "En-tete absent dans le fichier d'origine",
                "gravite": GRAVITE_MINEUR,
                "recommande": True,
            })
            continue

        # ── Colonne a valeur unique ───────────
        if serie.nunique(dropna=True) == 1 and non_vides == lignes:
            valeur = str(serie.dropna().iloc[0])[:30]
            actions.append({
                "type": "drop_column",
                "column": col,
                "params": {},
                "description": f"Supprimer la colonne constante « {nom} »",
                "raison": f"Toujours « {valeur} » : aucune information a analyser",
                "gravite": GRAVITE_MINEUR,
                "recommande": False,
            })

        # ── Valeurs manquantes ────────────────
        manquantes = lignes - non_vides
        if manquantes and lignes:
            part = manquantes / lignes
            if part >= seuil_manquantes:
                actions.append({
                    "type": "drop_column",
                    "column": col,
                    "params": {},
                    "description": f"Supprimer « {nom} », trop incomplete",
                    "raison": f"{round(part * 100)} % de valeurs manquantes",
                    "gravite": GRAVITE_IMPORTANT,
                    "recommande": False,
                })
            else:
                constats.append(
                    f"« {nom} » : {manquantes} valeur(s) manquante(s) "
                    f"({round(part * 100, 1)} %)"
                )

        if not pd.api.types.is_object_dtype(serie):
            continue

        # ── Nombres stockes en texte ──────────
        if _ressemble_a_des_nombres(serie):
            converties = parse_nombre(serie)
            perdues = int(converties.isna().sum() - serie.isna().sum())
            actions.append({
                "type": "parse_number",
                "column": col,
                "params": {},
                "description": f"Convertir « {nom} » en nombre",
                "raison": (
                    "Valeurs stockees en texte (unite ou separateur de milliers) : "
                    "aucune somme ni moyenne n'est possible en l'etat"
                    + (f" — {perdues} valeur(s) non convertible(s)" if perdues > 0 else "")
                ),
                "gravite": GRAVITE_BLOQUANT,
                "recommande": True,
            })
            continue

        # ── Dates stockees en texte ───────────
        if _ressemble_a_des_dates(serie):
            actions.append({
                "type": "convert_type",
                "column": col,
                "params": {"target_type": "datetime"},
                "description": f"Convertir « {nom} » en date",
                "raison": "Dates stockees en texte : aucun regroupement temporel possible",
                "gravite": GRAVITE_BLOQUANT,
                "recommande": True,
            })
            continue

        # ── Espaces parasites ─────────────────
        valeurs = _texte(serie)
        if not valeurs.empty:
            avec_espaces = int((valeurs != valeurs.str.strip()).sum())
            if avec_espaces:
                actions.append({
                    "type": "normalize_text",
                    "column": col,
                    "params": {"mode": "strip"},
                    "description": f"Nettoyer les espaces de « {nom} »",
                    "raison": (
                        f"{avec_espaces} valeur(s) avec des espaces en trop : "
                        "« Paris » et « Paris  » comptent comme deux categories"
                    ),
                    "gravite": GRAVITE_IMPORTANT,
                    "recommande": True,
                })

    # L'ordre d'affichage suit la gravite : ce qui empeche d'analyser d'abord.
    rang = {GRAVITE_BLOQUANT: 0, GRAVITE_IMPORTANT: 1, GRAVITE_MINEUR: 2}
    actions.sort(key=lambda a: rang.get(a["gravite"], 3))

    return {
        "lignes": int(lignes),
        "colonnes": int(colonnes),
        "doublons": doublons,
        "actions": actions,
        "constats": constats[:10],
    }


def appliquer_supplementaires(df: pd.DataFrame, actions: list) -> tuple[pd.DataFrame, list]:
    """Applique les actions que l'agent de nettoyage historique ne connait pas.

    `CleaningAgent.apply_actions` couvre les types d'origine ; on traite ici
    ceux ajoutes par le diagnostic, et on lui laisse le reste.
    """
    sortie = df
    journal: list[str] = []
    restantes: list[dict] = []

    for action in actions or []:
        if action.get("type") != "parse_number":
            restantes.append(action)
            continue
        col = action.get("column")
        if col not in sortie.columns:
            journal.append(f"[IGNORE] colonne « {col} » absente")
            continue
        sortie = sortie.copy()
        avant = int(sortie[col].notna().sum())
        sortie[col] = parse_nombre(sortie[col])
        apres = int(sortie[col].notna().sum())
        journal.append(
            f"[OK] « {col} » convertie en nombre"
            + (f" ({avant - apres} valeur(s) non convertible(s))" if avant > apres else "")
        )

    return sortie, journal, restantes
