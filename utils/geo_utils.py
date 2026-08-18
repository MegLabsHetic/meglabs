import json

import numpy as np
import pandas as pd

GEO_COL_PATTERNS = {
    "latitude": ["lat", "latitude", "latitud", "y", "lat_y"],
    "longitude": ["lon", "lng", "longitude", "longitud", "x", "lon_x", "long"],
    "geojson": ["geojson", "geo_json", "geometry", "geo"],
    "location_name": [
        "city",
        "ville",
        "country",
        "pays",
        "region",
        "province",
        "state",
        "locale_name",
        "location",
        "lieu",
        "commune",
        "departement",
        "department",
    ],
}


def detect_geo_columns(df: pd.DataFrame) -> dict:
    """Detect geographic columns in a DataFrame.

    Returns a dict like:
        {
            "latitude": "col_name" or None,
            "longitude": "col_name" or None,
            "geojson": "col_name" or None,
            "location_name": ["col1", ...],
            "has_geo": bool,
        }
    """
    result = {
        "latitude": None,
        "longitude": None,
        "geojson": None,
        "location_name": [],
        "has_geo": False,
    }

    cols_lower = {c.lower().strip(): c for c in df.columns}

    # Match by name patterns
    for geo_type, patterns in GEO_COL_PATTERNS.items():
        for pattern in patterns:
            if pattern in cols_lower:
                col = cols_lower[pattern]
                if geo_type == "location_name":
                    result["location_name"].append(col)
                elif result[geo_type] is None:
                    result[geo_type] = col

    # Detect lat/lon by value range if not found by name
    if result["latitude"] is None or result["longitude"] is None:
        for col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                continue
            vals = df[col].dropna()
            if len(vals) == 0:
                continue
            min_v, max_v = vals.min(), vals.max()
            if result["latitude"] is None and -90 <= min_v and max_v <= 90:
                std = vals.std()
                if 0.01 < std < 50:
                    result["latitude"] = col
            elif result["longitude"] is None and -180 <= min_v and max_v <= 180:
                std = vals.std()
                if 0.01 < std < 100:
                    result["longitude"] = col

    result["has_geo"] = (
        (result["latitude"] is not None and result["longitude"] is not None)
        or result["geojson"] is not None
        or len(result["location_name"]) > 0
    )
    return result


def parse_geojson_column(df: pd.DataFrame, geojson_col: str) -> list:
    """Parse a geojson column and return a list of geojson feature dicts."""
    features = []
    for idx, val in df[geojson_col].items():
        if pd.isna(val):
            continue
        try:
            if isinstance(val, str):
                geo = json.loads(val)
            else:
                geo = val
            features.append(geo)
        except (json.JSONDecodeError, TypeError):
            continue
    return features


def get_map_center(df: pd.DataFrame, lat_col: str, lon_col: str) -> tuple:
    """Get the center point for a map from lat/lon columns."""
    lat = df[lat_col].dropna().mean()
    lon = df[lon_col].dropna().mean()
    return (lat, lon)
