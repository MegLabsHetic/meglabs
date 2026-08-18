import io

import chardet
import pandas as pd


def detect_encoding(file_bytes: bytes) -> str:
    """Detect file encoding using chardet."""
    result = chardet.detect(file_bytes)
    return result.get("encoding", "utf-8") or "utf-8"


def load_file(uploaded_file) -> pd.DataFrame:
    """Load a CSV or Excel file into a DataFrame with automatic encoding detection."""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    uploaded_file.seek(0)

    if name.endswith(".csv"):
        encoding = detect_encoding(raw)
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=encoding, sep=sep)
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue
        # Fallback: let pandas guess
        return pd.read_csv(io.BytesIO(raw), encoding=encoding)

    elif name.endswith(".xlsx"):
        return pd.read_excel(io.BytesIO(raw), engine="openpyxl")

    elif name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(raw), engine="xlrd")

    else:
        raise ValueError(f"Format non supporté : {name}")
