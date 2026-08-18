import json

import folium
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from folium.plugins import HeatMap, MarkerCluster

from agents.base_agent import BaseAgent
from config import AGENT_TEMPERATURES
from utils.geo_utils import detect_geo_columns, get_map_center, parse_geojson_column

VIZ_SYSTEM_PROMPT = """Tu es un agent spécialisé dans la visualisation de données et la création de dashboards.
Tu reçois un profil de données et tu dois proposer les meilleures visualisations.

Retourne tes recommandations en JSON :
```json
{
  "charts": [
    {
      "type": "bar|line|pie|scatter|heatmap|box|histogram|treemap|sunburst|map_markers|map_choropleth|map_heatmap",
      "title": "Titre du graphique",
      "x": "colonne_x (ou null)",
      "y": "colonne_y (ou null)",
      "color": "colonne_couleur (ou null)",
      "description": "Ce que montre ce graphique"
    }
  ]
}
```

Règles :
- Propose 6 à 10 visualisations variées et pertinentes
- Utilise les colonnes géo pour des cartes si disponibles
- Utilise les colonnes temporelles pour des séries temporelles
- Propose au moins 1 heatmap de corrélation si >2 colonnes numériques
- Propose un pie chart pour les distributions catégorielles
- Réponds UNIQUEMENT en JSON valide."""


PLOTLY_TEMPLATE = "plotly_white"


class VisualizationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Visualization",
            system_prompt=VIZ_SYSTEM_PROMPT,
            temperature=AGENT_TEMPERATURES["visualization"],
        )

    def suggest_charts(self, profile: dict) -> dict:
        """Ask Claude to suggest optimal charts for this dataset."""
        context = self._format_profile(profile)
        return self.ask_json(
            "Propose les meilleures visualisations pour ce dataset. "
            "Retourne le résultat en JSON.",
            context=context,
        )

    def create_chart(
        self, df: pd.DataFrame, chart_spec: dict, profile: dict = None
    ) -> go.Figure | folium.Map | None:
        """Create a single chart from a specification dict."""
        chart_type = chart_spec.get("type", "bar")
        title = chart_spec.get("title", "Graphique")
        x = chart_spec.get("x")
        y = chart_spec.get("y")
        color = chart_spec.get("color")

        # Validate columns exist
        for col in [x, y, color]:
            if col and col not in df.columns:
                return None

        try:
            if chart_type == "bar":
                if x and y:
                    fig = px.bar(
                        df, x=x, y=y, color=color, title=title, template=PLOTLY_TEMPLATE
                    )
                elif x:
                    counts = df[x].value_counts().head(20).reset_index()
                    counts.columns = [x, "count"]
                    fig = px.bar(
                        counts, x=x, y="count", title=title, template=PLOTLY_TEMPLATE
                    )
                else:
                    return None

            elif chart_type == "line":
                if x and y:
                    fig = px.line(
                        df.sort_values(x),
                        x=x,
                        y=y,
                        color=color,
                        title=title,
                        template=PLOTLY_TEMPLATE,
                    )
                elif x:
                    # No y specified: aggregate counts by x (useful for time series)
                    temp = df.copy()
                    temp[x] = pd.to_datetime(temp[x], errors="coerce")
                    temp = temp.dropna(subset=[x]).sort_values(x)
                    counts = temp.groupby(temp[x].dt.to_period("M")).size().reset_index(name="Nombre")
                    counts[x] = counts[x].astype(str)
                    fig = px.line(
                        counts,
                        x=x,
                        y="Nombre",
                        title=title,
                        template=PLOTLY_TEMPLATE,
                    )
                else:
                    return None

            elif chart_type == "pie":
                col = x or color
                if col:
                    counts = df[col].value_counts().head(10).reset_index()
                    counts.columns = [col, "count"]
                    fig = px.pie(
                        counts,
                        names=col,
                        values="count",
                        title=title,
                        template=PLOTLY_TEMPLATE,
                    )
                else:
                    return None

            elif chart_type == "scatter":
                fig = px.scatter(
                    df,
                    x=x,
                    y=y,
                    color=color,
                    title=title,
                    template=PLOTLY_TEMPLATE,
                    opacity=0.7,
                )

            elif chart_type == "heatmap":
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if len(numeric_cols) >= 2:
                    corr = df[numeric_cols].corr()
                    fig = go.Figure(
                        data=go.Heatmap(
                            z=corr.values,
                            x=corr.columns.tolist(),
                            y=corr.index.tolist(),
                            colorscale="RdBu_r",
                            zmid=0,
                            text=corr.round(2).values,
                            texttemplate="%{text}",
                            textfont={"size": 10},
                        )
                    )
                    fig.update_layout(title=title, template=PLOTLY_TEMPLATE)
                else:
                    return None

            elif chart_type == "box":
                fig = px.box(
                    df, x=x, y=y, color=color, title=title, template=PLOTLY_TEMPLATE
                )

            elif chart_type == "histogram":
                fig = px.histogram(
                    df,
                    x=x or y,
                    color=color,
                    title=title,
                    template=PLOTLY_TEMPLATE,
                    nbins=30,
                )

            elif chart_type == "treemap":
                if x:
                    agg = df.groupby(x).size().reset_index(name="count")
                    fig = px.treemap(
                        agg,
                        path=[x],
                        values="count",
                        title=title,
                        template=PLOTLY_TEMPLATE,
                    )
                else:
                    return None

            elif chart_type == "sunburst":
                cols = [c for c in [x, color] if c]
                if cols:
                    fig = px.sunburst(
                        df, path=cols, title=title, template=PLOTLY_TEMPLATE
                    )
                else:
                    return None

            elif chart_type in ("map_markers", "map_choropleth", "map_heatmap"):
                return self._create_map(df, chart_spec, profile)

            else:
                return None

            fig.update_layout(height=450, margin=dict(l=40, r=40, t=60, b=40))
            return fig

        except Exception:
            return None

    def _create_map(
        self, df: pd.DataFrame, chart_spec: dict, profile: dict = None
    ) -> folium.Map | None:
        """Create a Folium map."""
        geo = (
            detect_geo_columns(df)
            if profile is None
            else profile.get("geo_info", detect_geo_columns(df))
        )
        lat_col = geo.get("latitude")
        lon_col = geo.get("longitude")

        if not lat_col or not lon_col:
            return None

        clean = df.dropna(subset=[lat_col, lon_col])
        if len(clean) == 0:
            return None

        center = get_map_center(clean, lat_col, lon_col)
        m = folium.Map(location=center, zoom_start=7, tiles="CartoDB positron")

        chart_type = chart_spec.get("type", "map_markers")
        color_col = chart_spec.get("color")
        title = chart_spec.get("title", "Carte")

        if chart_type == "map_heatmap":
            heat_data = clean[[lat_col, lon_col]].values.tolist()
            HeatMap(heat_data, radius=15).add_to(m)

        elif chart_type == "map_markers":
            cluster = MarkerCluster(name=title).add_to(m)
            for _, row in clean.iterrows():
                popup_parts = []
                for c in df.columns:
                    if c not in [lat_col, lon_col, geo.get("geojson", "")] and pd.notna(
                        row.get(c)
                    ):
                        val = row[c]
                        if isinstance(val, str) and len(val) > 100:
                            continue
                        popup_parts.append(f"<b>{c}</b>: {val}")
                popup_html = "<br>".join(popup_parts[:8])
                folium.Marker(
                    location=[row[lat_col], row[lon_col]],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=str(row.get(color_col, "")) if color_col else None,
                ).add_to(cluster)

        # Add GeoJSON polygons if available
        geojson_col = geo.get("geojson")
        if geojson_col and geojson_col in df.columns:
            features = parse_geojson_column(df, geojson_col)
            if features:
                fc = {"type": "FeatureCollection", "features": features}
                folium.GeoJson(
                    fc,
                    style_function=lambda x: {
                        "fillColor": "#3388ff",
                        "color": "#3388ff",
                        "weight": 2,
                        "fillOpacity": 0.15,
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=["name"]
                        if features and "name" in features[0].get("properties", {})
                        else [],
                    ),
                ).add_to(m)

        folium.LayerControl().add_to(m)
        return m

    def create_all_charts(
        self, df: pd.DataFrame, chart_specs: list, profile: dict = None
    ) -> list:
        """Create all charts from a list of specifications."""
        results = []
        for spec in chart_specs:
            chart = self.create_chart(df, spec, profile)
            if chart is not None:
                results.append({"spec": spec, "figure": chart})
        return results

    def auto_dashboard(self, df: pd.DataFrame, profile: dict) -> list:
        """Generate a complete auto-dashboard based on data profile."""
        charts = []

        # 1. Distribution of categorical columns
        for col in profile["categorical_columns"][:3]:
            counts = df[col].value_counts()
            if 2 <= len(counts) <= 15:
                charts.append(
                    {"type": "pie", "x": col, "title": f"Distribution de {col}"}
                )
            elif len(counts) > 15:
                charts.append(
                    {"type": "bar", "x": col, "title": f"Top valeurs de {col}"}
                )

        # 2. Histograms for numeric columns
        for col in profile["numeric_columns"][:3]:
            charts.append(
                {"type": "histogram", "x": col, "title": f"Distribution de {col}"}
            )

        # 3. Correlation heatmap
        if len(profile["numeric_columns"]) >= 2:
            charts.append({"type": "heatmap", "title": "Matrice de corrélation"})

        # 4. Time series (count by date period)
        for date_col in profile["date_columns"][:1]:
            charts.append(
                {
                    "type": "line",
                    "x": date_col,
                    "title": f"Evolution temporelle ({date_col})",
                }
            )

        # 5. Box plots
        if profile["numeric_columns"] and profile["categorical_columns"]:
            charts.append(
                {
                    "type": "box",
                    "x": profile["categorical_columns"][0],
                    "y": profile["numeric_columns"][0],
                    "title": f"{profile['numeric_columns'][0]} par {profile['categorical_columns'][0]}",
                }
            )

        # 6. Geographic map
        if profile["geo_info"]["has_geo"]:
            charts.append(
                {"type": "map_markers", "title": "Carte des données géographiques"}
            )
            charts.append({"type": "map_heatmap", "title": "Carte de densité"})

        return charts

    def _format_profile(self, profile: dict) -> str:
        lines = [f"Dataset: {profile['shape']['rows']} x {profile['shape']['columns']}"]
        for col, info in profile["columns"].items():
            lines.append(
                f"- {col}: {info.get('type', info['dtype'])}, {info['nunique']} uniques"
            )
        if profile["geo_info"]["has_geo"]:
            lines.append(
                f"GEO: lat={profile['geo_info']['latitude']}, lon={profile['geo_info']['longitude']}"
            )
        return "\n".join(lines)
