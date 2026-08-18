"""Export utilities for generating reports in CSV, Excel, and PDF formats."""

import io
import json
import os
from datetime import datetime

import pandas as pd

from config import EXPORT_DIR


def export_csv(df: pd.DataFrame, filename: str = None) -> bytes:
    """Export DataFrame to CSV bytes."""
    return df.to_csv(index=False).encode("utf-8")


def export_excel(df: pd.DataFrame, profile: dict = None, filename: str = None) -> bytes:
    """Export DataFrame to Excel with optional profile sheet."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Donnees", index=False)

        if profile:
            # Summary sheet
            summary_data = {
                "Metrique": ["Lignes", "Colonnes", "Doublons", "Memoire (MB)"],
                "Valeur": [
                    profile["shape"]["rows"],
                    profile["shape"]["columns"],
                    profile["duplicates"],
                    profile["memory_mb"],
                ],
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name="Resume", index=False)

            # Columns detail sheet
            col_data = []
            for col, info in profile["columns"].items():
                col_data.append({
                    "Colonne": col,
                    "Type": info.get("type", info["dtype"]),
                    "Uniques": info["nunique"],
                    "Manquantes": info["missing"],
                    "Manquantes (%)": info["missing_pct"],
                })
            pd.DataFrame(col_data).to_excel(writer, sheet_name="Colonnes", index=False)

    return output.getvalue()


def export_analysis_report(
    df: pd.DataFrame,
    profile: dict,
    analyses: dict = None,
    charts_html: list = None,
) -> str:
    """Generate a comprehensive HTML report.

    Returns HTML string that can be converted to PDF or displayed.
    """
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    html_parts = [
        "<!DOCTYPE html>",
        "<html><head>",
        '<meta charset="utf-8">',
        "<title>Rapport DataAnalyst AI</title>",
        "<style>",
        "body { font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #333; line-height: 1.6; }",
        "h1 { color: #4a00e0; border-bottom: 3px solid #4a00e0; padding-bottom: 10px; }",
        "h2 { color: #6c5ce7; margin-top: 30px; }",
        "h3 { color: #636e72; }",
        "table { border-collapse: collapse; width: 100%; margin: 15px 0; }",
        "th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }",
        "th { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }",
        "tr:nth-child(even) { background: #f8f9fa; }",
        ".metric-row { display: flex; gap: 20px; margin: 20px 0; }",
        ".metric-card { flex: 1; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); "
        "color: white; padding: 20px; border-radius: 12px; text-align: center; }",
        ".metric-card h3 { color: white; margin: 0; font-size: 2rem; }",
        ".metric-card p { margin: 5px 0 0; opacity: 0.9; }",
        ".section { margin: 30px 0; padding: 20px; background: #f8f9fa; border-radius: 12px; }",
        ".footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; "
        "color: #888; font-size: 0.85rem; text-align: center; }",
        ".badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }",
        ".badge-ok { background: #d4edda; color: #155724; }",
        ".badge-warn { background: #fff3cd; color: #856404; }",
        ".badge-danger { background: #f8d7da; color: #721c24; }",
        "</style>",
        "</head><body>",
        f"<h1>\U0001f4ca Rapport d'Analyse - DataAnalyst AI</h1>",
        f"<p>Genere le {now}</p>",
    ]

    # KPI cards
    total_missing = sum(v["count"] for v in profile["missing_values"].values())
    html_parts.append('<div class="metric-row">')
    for label, value in [
        ("Lignes", f"{profile['shape']['rows']:,}"),
        ("Colonnes", profile["shape"]["columns"]),
        ("Doublons", profile["duplicates"]),
        ("Valeurs manquantes", f"{total_missing:,}"),
    ]:
        html_parts.append(
            f'<div class="metric-card"><h3>{value}</h3><p>{label}</p></div>'
        )
    html_parts.append("</div>")

    # Column analysis
    html_parts.append("<h2>Detail des colonnes</h2>")
    html_parts.append("<table><tr><th>Colonne</th><th>Type</th><th>Uniques</th>"
                       "<th>Manquantes</th><th>Stats</th></tr>")
    for col, info in profile["columns"].items():
        missing_badge = "badge-ok" if info["missing"] == 0 else (
            "badge-warn" if info["missing_pct"] < 20 else "badge-danger"
        )
        stats = ""
        if "mean" in info:
            stats = f"moy={info['mean']}, std={info['std']}"
        elif "top_values" in info:
            top = list(info["top_values"].items())[:3]
            stats = ", ".join(f"{k}: {v}" for k, v in top)
        html_parts.append(
            f"<tr><td><b>{col}</b></td>"
            f"<td>{info.get('type', info['dtype'])}</td>"
            f"<td>{info['nunique']}</td>"
            f'<td><span class="badge {missing_badge}">{info["missing"]} ({info["missing_pct"]}%)</span></td>'
            f"<td>{stats}</td></tr>"
        )
    html_parts.append("</table>")

    # Data types summary
    html_parts.append('<div class="section">')
    html_parts.append("<h3>Types de donnees detectes</h3>")
    if profile["date_columns"]:
        html_parts.append(f"<p><b>Temporelles :</b> {', '.join(profile['date_columns'])}</p>")
    if profile["numeric_columns"]:
        html_parts.append(f"<p><b>Numeriques :</b> {', '.join(profile['numeric_columns'])}</p>")
    if profile["categorical_columns"]:
        html_parts.append(f"<p><b>Categorielles :</b> {', '.join(profile['categorical_columns'])}</p>")
    if profile["geo_info"]["has_geo"]:
        html_parts.append("<p><b>Donnees geographiques :</b> Detectees</p>")
    html_parts.append("</div>")

    # Analysis results
    if analyses:
        if "axes" in analyses and analyses["axes"]:
            html_parts.append("<h2>Axes d'analyse recommandes</h2>")
            for i, axe in enumerate(analyses["axes"], 1):
                html_parts.append(f'<div class="section">')
                html_parts.append(f"<h3>Axe {i} : {axe.get('titre', 'N/A')}</h3>")
                html_parts.append(f"<p>{axe.get('description', '')}</p>")
                if "colonnes" in axe:
                    html_parts.append(f"<p><b>Colonnes :</b> {', '.join(axe['colonnes'])}</p>")
                if "questions" in axe:
                    html_parts.append("<ul>")
                    for q in axe["questions"]:
                        html_parts.append(f"<li>{q}</li>")
                    html_parts.append("</ul>")
                html_parts.append("</div>")

    # Data preview
    html_parts.append("<h2>Apercu des donnees (20 premieres lignes)</h2>")
    html_parts.append(df.head(20).to_html(index=False, classes="data-table"))

    # Footer
    html_parts.append('<div class="footer">')
    html_parts.append(f"<p>Rapport genere par DataAnalyst AI v2.0 | {now}</p>")
    html_parts.append("<p>Propulse par Claude AI (Anthropic) - Multi-Agent System</p>")
    html_parts.append("</div>")
    html_parts.append("</body></html>")

    return "\n".join(html_parts)


def save_export_file(content: bytes, filename: str) -> str:
    """Save export file and return the path."""
    filepath = os.path.join(EXPORT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return filepath
