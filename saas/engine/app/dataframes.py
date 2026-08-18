"""Construction de DataFrame a partir des payloads JSON envoyes par l'API Rust.

Le service est sans etat : il recoit les donnees (texte CSV ou enregistrements),
calcule, et renvoie du JSON. Rien n'est persiste ici.
"""

import base64
import io

import chardet
import numpy as np
import pandas as pd

# Signatures de fichiers. On reconnait le format au CONTENU, pas a l'extension :
# un tableur exporte en « .csv » mais reellement au format Excel est un grand
# classique, et l'inverse aussi.
_SIGNATURE_XLSX = b"PK\x03\x04"          # .xlsx = archive zip
_SIGNATURE_XLS = b"\xd0\xcf\x11\xe0"     # .xls historique = conteneur OLE2


def format_fichier(donnees: bytes) -> str:
    """Renvoie 'xlsx', 'xls' ou 'csv' d'apres les premiers octets."""
    if donnees.startswith(_SIGNATURE_XLSX):
        return "xlsx"
    if donnees.startswith(_SIGNATURE_XLS):
        return "xls"
    return "csv"


def octets_du_payload(payload: dict) -> bytes | None:
    """Extrait le contenu binaire d'un payload, quelle que soit sa forme."""
    encode = payload.get("file_base64")
    if encode:
        return base64.b64decode(encode)
    texte = payload.get("csv_text")
    if texte is not None:
        return texte.encode("utf-8") if isinstance(texte, str) else bytes(texte)
    return None


def _lire_csv(donnees: bytes) -> pd.DataFrame:
    """CSV : detection de l'encodage puis du separateur."""
    encodage = chardet.detect(donnees).get("encoding") or "utf-8"
    for sep in [",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(io.BytesIO(donnees), encoding=encodage, sep=sep)
            if len(df.columns) > 1:
                return df
        except Exception:
            continue
    return pd.read_csv(io.BytesIO(donnees), encoding=encodage)


def _moteur_excel(format_: str) -> str:
    # xlrd ne lit plus que le .xls historique depuis sa version 2.
    return "xlrd" if format_ == "xls" else "openpyxl"


def feuilles_du_classeur(donnees: bytes) -> list[dict]:
    """Inventaire des feuilles d'un classeur : nom, dimensions, apercu.

    Sert a demander a l'utilisateur ce qu'il veut importer. Prendre
    silencieusement la premiere feuille ferait disparaitre les autres sans
    qu'il le sache.
    """
    format_ = format_fichier(donnees)
    if format_ == "csv":
        return []

    classeur = pd.ExcelFile(io.BytesIO(donnees), engine=_moteur_excel(format_))
    inventaire = []
    for nom in classeur.sheet_names:
        try:
            df = classeur.parse(nom)
        except Exception:
            continue
        df = df.dropna(how="all").dropna(axis=1, how="all")
        inventaire.append({
            "nom": nom,
            "lignes": int(len(df)),
            "colonnes": [str(c) for c in df.columns],
            "vide": bool(df.empty),
        })
    return inventaire


def _clean_for_json(obj):
    """Rend une structure serialisable en JSON (NaN/inf -> None, numpy -> natif)."""
    if isinstance(obj, dict):
        return {str(k): _clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_for_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        f = float(obj)
        return None if (np.isnan(f) or np.isinf(f)) else f
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float):
        return None if (pd.isna(obj) or np.isinf(obj)) else obj
    return obj


def dataframe_from_payload(payload: dict) -> pd.DataFrame:
    """Construit un DataFrame depuis {records}, {csv_text} ou {file_base64}.

    Le format est reconnu au contenu : CSV (avec detection d'encodage et de
    separateur) ou classeur Excel. Pour un classeur, `sheet` designe la
    feuille voulue ; a defaut la premiere non vide.
    """
    if payload.get("records") is not None:
        return pd.DataFrame(payload["records"])

    donnees = octets_du_payload(payload)
    if donnees is None:
        raise ValueError("Payload sans 'file_base64', 'csv_text' ni 'records'")

    format_ = format_fichier(donnees)
    if format_ == "csv":
        return _lire_csv(donnees)

    classeur = pd.ExcelFile(io.BytesIO(donnees), engine=_moteur_excel(format_))
    demandee = payload.get("sheet")
    if demandee and demandee in classeur.sheet_names:
        nom = demandee
    else:
        # Un classeur commence souvent par une feuille de garde vide : on
        # prend la premiere qui porte reellement des donnees.
        nom = next(
            (n for n in classeur.sheet_names
             if not classeur.parse(n).dropna(how="all").empty),
            classeur.sheet_names[0],
        )

    df = classeur.parse(nom)
    # Excel produit des lignes et colonnes entierement vides des qu'une
    # cellule a ete effleuree : elles deviendraient des colonnes fantomes.
    return df.dropna(how="all").dropna(axis=1, how="all")


def apply_filters(df: pd.DataFrame, filters: dict | None) -> pd.DataFrame:
    """Filtre le DataFrame selon {dimension:{column,values}, date:{column,start,end}}."""
    if not filters:
        return df
    dim = filters.get("dimension")
    if dim and dim.get("column") in df.columns and dim.get("values"):
        wanted = {str(v) for v in dim["values"]}
        df = df[df[dim["column"]].astype(str).isin(wanted)]
    dr = filters.get("date")
    if dr and dr.get("column") in df.columns:
        s = pd.to_datetime(df[dr["column"]], errors="coerce")
        if dr.get("start"):
            df = df[s >= pd.to_datetime(dr["start"])]
        if dr.get("end"):
            df = df[s <= pd.to_datetime(dr["end"])]
    return df


def column_values(df: pd.DataFrame, column: str, limit: int = 50) -> list:
    """Valeurs distinctes d'une colonne (triees, plafonnees) pour les filtres."""
    if column not in df.columns:
        return []
    vals = df[column].dropna().astype(str).unique().tolist()
    vals.sort()
    return vals[:limit]


def preview_records(df: pd.DataFrame, n: int = 20) -> list:
    """Apercu JSON-safe des n premieres lignes."""
    head = df.head(n).replace({np.nan: None})
    return _clean_for_json(head.to_dict(orient="records"))
