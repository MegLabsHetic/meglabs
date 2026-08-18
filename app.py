import os
import sys

import folium
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

# Add project root to path
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

# Recharge le .env a chaque rerun : une cle ajoutee dans le fichier est prise
# en compte sans redemarrer l'application. On n'ecrase jamais avec une valeur vide.
try:
    from dotenv import dotenv_values

    _env_key = (dotenv_values(os.path.join(_ROOT, ".env")) or {}).get(
        "ANTHROPIC_API_KEY"
    )
    if _env_key:
        os.environ["ANTHROPIC_API_KEY"] = _env_key
except ImportError:
    pass

from agents.analysis_agent import AnalysisAgent
from agents.cleaning_agent import CleaningAgent
from agents.documentation_agent import DocumentationAgent
from agents.kpi_agent import KPIAgent
from agents.orchestrator_agent import OrchestratorAgent
from agents.profiler_agent import ProfilerAgent
from agents.visualization_agent import VisualizationAgent
from config import APP_ICON, APP_NAME, SUPPORTED_EXTENSIONS
from utils.data_loader import load_file
from utils.geo_utils import get_map_center, parse_geojson_column
from utils.viz_theme import (
    CATEGORICAL,
    DIVERGING_SCALE,
    SEQUENTIAL_BLUES,
    apply_plotly_theme,
)

apply_plotly_theme()

# ──────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title=APP_NAME,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────
st.markdown(
    """
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1rem; color: #888; margin-bottom: 2rem; }
    .metric-card {
        background: linear-gradient(135deg, #2a78d6 0%, #4a3aa7 100%);
        padding: 1.2rem; border-radius: 12px; color: white; text-align: center;
    }
    .metric-card h3 { margin: 0; font-size: 1.6rem; }
    .metric-card p { margin: 0; font-size: 0.85rem; opacity: 0.85; }
    .step-done { color: #0ca30c; font-weight: 600; }
    .step-todo { color: #898781; }
    .agent-badge {
        display: inline-block; padding: 0.2rem 0.6rem; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600; margin-right: 0.5rem;
    }
    .agent-profiler { background: #e3f2fd; color: #1565c0; }
    .agent-cleaning { background: #e8f5e9; color: #2e7d32; }
    .agent-analysis { background: #fff3e0; color: #e65100; }
    .agent-viz { background: #fce4ec; color: #c62828; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] { padding: 8px 14px; border-radius: 8px 8px 0 0; }
</style>
""",
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────
# Session state initialization
# ──────────────────────────────────────────────
def init_session():
    defaults = {
        "df": None,
        "df_original": None,
        "profile": None,
        "uploaded_file_name": None,
        # Etape 2 - nettoyage
        "cleaning_plan": None,
        "cleaning_summary": "",
        "plan_version": 0,
        "df_cleaned": None,
        "cleaning_log": [],
        "cleaning_validated": False,
        # Etape 3 - exploration
        "analysis_results": {},
        # Etape 4 - documentation
        "data_dictionary": None,
        "warehouse_model": None,
        # Etape 5 - KPIs
        "kpi_suggestions": [],
        "kpi_selected": {},
        "kpi_results": {},
        "custom_kpi_count": 0,
        # Etape 6 - dashboard
        "charts": [],
        # Chat
        "chat_history": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session()


def reset_data_state():
    """Reset everything derived from the dataset."""
    st.session_state.profile = None
    st.session_state.cleaning_plan = None
    st.session_state.cleaning_summary = ""
    st.session_state.plan_version += 1
    st.session_state.df_cleaned = None
    st.session_state.cleaning_log = []
    st.session_state.cleaning_validated = False
    st.session_state.analysis_results = {}
    st.session_state.data_dictionary = None
    st.session_state.warehouse_model = None
    st.session_state.kpi_suggestions = []
    st.session_state.kpi_selected = {}
    st.session_state.kpi_results = {}
    st.session_state.charts = []


# ──────────────────────────────────────────────
# Agents (lazy)
# ──────────────────────────────────────────────
@st.cache_resource
def get_agents():
    return {
        "orchestrator": OrchestratorAgent(),
        "profiler": ProfilerAgent(),
        "cleaner": CleaningAgent(),
        "analyzer": AnalysisAgent(),
        "visualizer": VisualizationAgent(),
        "documentor": DocumentationAgent(),
        "kpi": KPIAgent(),
    }


def quality_score(profile: dict) -> int:
    """Deterministic 0-100 data quality score."""
    rows = max(profile["shape"]["rows"], 1)
    cols = max(profile["shape"]["columns"], 1)
    missing = sum(v["count"] for v in profile["missing_values"].values())
    missing_pct = missing / (rows * cols)
    dup_pct = profile["duplicates"] / rows
    n_num = max(len(profile["numeric_columns"]), 1)
    outliers = sum(i.get("outliers", 0) for i in profile["columns"].values())
    outlier_pct = outliers / (rows * n_num)
    penalty = missing_pct * 60 + dup_pct * 25 + min(outlier_pct, 1) * 15
    return max(0, round(100 - penalty * 100))


def steps_status() -> dict:
    s = st.session_state
    return {
        "1. Diagnostic": s.profile is not None,
        "2. Nettoyage": s.cleaning_validated,
        "3. Exploration": bool(s.analysis_results),
        "4. Documentation": s.data_dictionary is not None,
        "5. KPIs": bool(s.kpi_results),
        "6. Dashboard": bool(s.kpi_results) and bool(s.kpi_selected),
    }


# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## {APP_ICON} {APP_NAME}")
    st.markdown("**Plateforme de préparation de données & BI pilotée par agents IA**")
    st.divider()

    api_key = st.text_input(
        "Clé API Anthropic",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help=(
            "Nécessaire pour les fonctions IA (plan de nettoyage, documentation, "
            "KPIs...). Astuce : renseignez ANTHROPIC_API_KEY dans le fichier .env "
            "du projet pour la charger automatiquement."
        ),
    )
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        st.caption("🔑 Clé API chargée")
    else:
        st.caption("💡 Ajoutez votre clé dans le fichier `.env` du projet ou ci-dessus.")

    st.divider()
    st.markdown("### Charger vos données")
    uploaded_file = st.file_uploader(
        "Glissez votre fichier ici",
        type=SUPPORTED_EXTENSIONS,
        help="Formats supportés : CSV, Excel (.xlsx, .xls)",
    )

    if uploaded_file is not None:
        file_changed = st.session_state.uploaded_file_name != uploaded_file.name
        need_load = st.session_state.df is None or file_changed
        if need_load or st.button("Recharger le fichier"):
            with st.spinner("Chargement du fichier..."):
                try:
                    df_loaded = load_file(uploaded_file)
                    st.session_state.df = df_loaded
                    st.session_state.df_original = df_loaded.copy()
                    st.session_state.uploaded_file_name = uploaded_file.name
                    reset_data_state()
                    st.success(
                        f"Fichier chargé : {len(df_loaded)} lignes x "
                        f"{len(df_loaded.columns)} colonnes"
                    )
                except Exception as e:
                    st.error(f"Erreur de chargement : {e}")

    # Progression du parcours
    if st.session_state.df is not None:
        st.divider()
        st.markdown("### Votre parcours")
        for label, done in steps_status().items():
            icon = "✅" if done else "○"
            css = "step-done" if done else "step-todo"
            st.markdown(
                f'<span class="{css}">{icon} {label}</span>',
                unsafe_allow_html=True,
            )

        st.divider()
        df = st.session_state.df
        st.markdown("### Aperçu rapide")
        st.markdown(f"- **Lignes** : {len(df):,}")
        st.markdown(f"- **Colonnes** : {len(df.columns)}")
        missing = df.isna().sum().sum()
        if missing > 0:
            st.markdown(f"- **Valeurs manquantes** : {missing:,}")
        if st.session_state.df_original is not None and st.button(
            "Restaurer les données d'origine"
        ):
            st.session_state.df = st.session_state.df_original.copy()
            reset_data_state()
            st.rerun()

    st.divider()
    st.markdown(
        "<small>Propulsé par Claude AI (Anthropic)<br>Système multi-agents — 7 agents spécialisés</small>",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────
# LANDING PAGE
# ──────────────────────────────────────────────
if st.session_state.df is None:
    st.markdown(
        '<p class="main-header">Bienvenue sur DataAnalyst AI</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sub-header">De la donnée brute au tableau de bord, en 6 étapes guidées</p>',
        unsafe_allow_html=True,
    )

    steps_landing = [
        ("1", "Diagnostic automatique"),
        ("2", "Nettoyage guidé"),
        ("3", "Analyse exploratoire"),
        ("4", "Documentation du modèle"),
        ("5", "Co-création des KPIs"),
        ("6", "Tableau de bord"),
    ]
    cols = st.columns(6)
    for col, (num, label) in zip(cols, steps_landing):
        with col:
            st.markdown(
                f'<div class="metric-card"><h3>{num}</h3><p>{label}</p></div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.markdown("""
    ### Comment ça marche
    1. **Diagnostic & profilage** : dès le chargement, la structure, les types et les anomalies sont détectés automatiquement.
    2. **Nettoyage intelligent & guidé** : l'IA propose un plan de nettoyage sur-mesure — **vous validez chaque action** avant application. La donnée d'origine est toujours préservée.
    3. **Analyse exploratoire (EDA)** : axes d'analyse IA, corrélations, segmentation, saisonnalités, cartes.
    4. **Documentation** : dictionnaire de données généré automatiquement + modélisation d'entrepôt (faits / dimensions) — exports Markdown et dbt.
    5. **Co-création des KPIs** : l'IA suggère des indicateurs calculables, vous sélectionnez, ajustez ou créez les vôtres. Les formules sont transparentes et calculées de manière déterministe.
    6. **Tableau de bord** : vos KPIs validés deviennent un dashboard interactif et filtrable.

    💬 À toute étape, le **chat en langage naturel** vous accompagne (français / anglais).

    **Pour commencer : uploadez un fichier CSV ou Excel dans la barre latérale.**
    """)

else:
    df = st.session_state.df

    # Auto-profiling deterministe des le chargement (etape 1, sans cle API)
    if st.session_state.profile is None:
        with st.spinner("Diagnostic automatique du dataset..."):
            st.session_state.profile = get_agents()["profiler"].profile_dataframe(df)

    profile = st.session_state.profile
    geo_info = profile["geo_info"]
    has_geo = geo_info.get("has_geo", False)

    (
        tab_diag,
        tab_clean,
        tab_explore,
        tab_doc,
        tab_kpi,
        tab_dash,
        tab_chat,
    ) = st.tabs(
        [
            "🔍 1 · Diagnostic",
            "🧹 2 · Nettoyage",
            "📈 3 · Exploration",
            "📚 4 · Documentation",
            "🎯 5 · KPIs",
            "📊 6 · Dashboard",
            "💬 Chat IA",
        ]
    )

    # ══════════════════════════════════════════
    # ETAPE 1 : DIAGNOSTIC & PROFILAGE
    # ══════════════════════════════════════════
    with tab_diag:
        st.markdown("### Étape 1 — Diagnostic & profilage automatique")
        st.caption(
            "Analyse structurelle réalisée automatiquement au chargement : "
            "types de colonnes, anomalies, qualité globale."
        )

        score = quality_score(profile)
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Lignes", f"{profile['shape']['rows']:,}")
        col2.metric("Colonnes", profile["shape"]["columns"])
        col3.metric("Doublons", profile["duplicates"])
        total_missing = sum(v["count"] for v in profile["missing_values"].values())
        col4.metric("Valeurs manquantes", f"{total_missing:,}")
        col5.metric("Score qualité", f"{score}/100")

        st.divider()
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### Détail des colonnes")
            col_data = []
            for col, info in profile["columns"].items():
                col_data.append(
                    {
                        "Colonne": col,
                        "Type": info.get("type", info["dtype"]),
                        "Uniques": info["nunique"],
                        "Manquantes": f"{info['missing']} ({info['missing_pct']}%)",
                        "Outliers": info.get("outliers", ""),
                    }
                )
            st.dataframe(
                pd.DataFrame(col_data), use_container_width=True, hide_index=True
            )

        with col_right:
            st.markdown("#### Détection automatique")
            if profile["date_columns"]:
                st.info(f"🗓️ Colonnes temporelles : {', '.join(profile['date_columns'])}")
            if profile["numeric_columns"]:
                st.success(f"🔢 Colonnes numériques : {', '.join(profile['numeric_columns'])}")
            if profile["categorical_columns"]:
                st.warning(
                    f"🏷️ Colonnes catégorielles : {', '.join(profile['categorical_columns'])}"
                )
            if has_geo:
                st.info(
                    "🗺️ Données géographiques détectées !\n"
                    f"- Latitude : {geo_info['latitude']}\n"
                    f"- Longitude : {geo_info['longitude']}\n"
                    f"- GeoJSON : {geo_info['geojson']}\n"
                    f"- Lieux : {geo_info['location_name']}"
                )

            st.markdown("#### Problèmes détectés")
            issues = []
            if profile["duplicates"] > 0:
                issues.append(f"- {profile['duplicates']} lignes dupliquées")
            for col, mv in profile["missing_values"].items():
                issues.append(f"- `{col}` : {mv['count']} manquantes ({mv['pct']}%)")
            for col, info in profile["columns"].items():
                if info.get("outliers", 0) > 0:
                    issues.append(f"- `{col}` : {info['outliers']} outliers")
            if issues:
                for issue in issues[:12]:
                    st.markdown(issue)
                if len(issues) > 12:
                    st.caption(f"... et {len(issues) - 12} autres problèmes")
            else:
                st.success("Aucun problème majeur détecté !")

        st.divider()
        st.markdown("#### Aperçu des données")
        st.dataframe(df.head(50), use_container_width=True, hide_index=True)

        if api_key:
            st.divider()
            if st.button("🤖 Analyse IA du diagnostic", key="btn_ai_diag"):
                with st.spinner("L'agent Profiler analyse vos données..."):
                    insights = get_agents()["profiler"].get_ai_insights(profile)
                    st.session_state.analysis_results["diag_insights"] = insights
            if "diag_insights" in st.session_state.analysis_results:
                st.markdown(st.session_state.analysis_results["diag_insights"])

        st.divider()
        st.info("➡️ Étape suivante : **2 · Nettoyage** — l'IA vous propose un plan à valider.")

    # ══════════════════════════════════════════
    # ETAPE 2 : NETTOYAGE GUIDE (plan -> validation -> application)
    # ══════════════════════════════════════════
    with tab_clean:
        st.markdown("### Étape 2 — Nettoyage intelligent & guidé")
        st.caption(
            "L'agent Nettoyage propose un plan sur-mesure. Vous validez ou "
            "écartez chaque action avant application. La donnée d'origine est préservée."
        )

        col_a, col_b = st.columns([1, 1])
        with col_a:
            if st.button("🤖 Proposer un plan de nettoyage (IA)", type="primary"):
                if not api_key:
                    st.error("Clé API requise pour le plan IA.")
                else:
                    with st.spinner("L'agent Nettoyage prépare son plan..."):
                        agents = get_agents()
                        suggestions = agents["cleaner"].suggest_cleaning(profile)
                        actions = suggestions.get("actions", [])
                        for a in actions:
                            a["impact"] = agents["cleaner"].estimate_impact(df, a)
                        st.session_state.cleaning_plan = actions
                        st.session_state.cleaning_summary = suggestions.get("summary", "")
                        st.session_state.plan_version += 1
                        if not actions and "error" in suggestions:
                            st.error(suggestions["error"])
        with col_b:
            if st.button("Mes données sont déjà propres — passer cette étape"):
                st.session_state.cleaning_validated = True
                st.success("Étape validée. Vous pouvez passer à l'exploration.")

        plan = st.session_state.cleaning_plan
        if plan is not None:
            st.divider()
            if st.session_state.cleaning_summary:
                st.markdown(f"**Résumé du plan :** {st.session_state.cleaning_summary}")

            if not plan:
                st.success("L'agent n'a détecté aucune action de nettoyage nécessaire.")
            else:
                st.markdown("#### Plan proposé — cochez les actions à appliquer")
                pv = st.session_state.plan_version
                selected_actions = []
                for i, action in enumerate(plan):
                    label = action.get("description", action.get("type", "Action"))
                    col_target = action.get("column")
                    if col_target:
                        label = f"`{col_target}` — {label}"
                    checked = st.checkbox(label, value=True, key=f"act_{pv}_{i}")
                    detail = []
                    if action.get("raison"):
                        detail.append(f"💡 {action['raison']}")
                    if action.get("impact"):
                        detail.append(f"📏 Impact estimé : {action['impact']}")
                    if detail:
                        st.caption(" · ".join(detail))
                    if checked:
                        selected_actions.append(action)

                st.divider()
                if st.button(
                    f"✅ Appliquer les {len(selected_actions)} action(s) sélectionnée(s)",
                    type="primary",
                    disabled=len(selected_actions) == 0,
                ):
                    with st.spinner("Application du nettoyage..."):
                        cleaned, log = get_agents()["cleaner"].apply_actions(
                            df, selected_actions
                        )
                        st.session_state.df_cleaned = cleaned
                        st.session_state.cleaning_log = log

        # Journal + comparaison avant/apres
        if st.session_state.cleaning_log:
            st.divider()
            st.markdown("#### Journal des opérations")
            for entry in st.session_state.cleaning_log:
                if "[OK]" in entry:
                    st.success(entry)
                elif "[ERREUR]" in entry:
                    st.error(entry)
                else:
                    st.info(entry)

        if st.session_state.df_cleaned is not None:
            st.divider()
            st.markdown("#### Comparaison Avant / Après")
            cleaned = st.session_state.df_cleaned
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Avant** : {len(df)} lignes x {len(df.columns)} colonnes")
                st.dataframe(df.head(10), use_container_width=True, hide_index=True)
            with c2:
                st.markdown(
                    f"**Après** : {len(cleaned)} lignes x {len(cleaned.columns)} colonnes"
                )
                st.dataframe(cleaned.head(10), use_container_width=True, hide_index=True)

            if st.button("🎯 Valider : utiliser les données nettoyées pour la suite"):
                st.session_state.df = st.session_state.df_cleaned
                st.session_state.df_cleaned = None
                st.session_state.profile = None  # re-profilage automatique
                st.session_state.cleaning_validated = True
                # Les resultats derives deviennent obsoletes
                st.session_state.analysis_results = {}
                st.session_state.kpi_results = {}
                st.session_state.charts = []
                st.success("Dataset nettoyé validé ! Le diagnostic va se relancer automatiquement.")
                st.rerun()

    # ══════════════════════════════════════════
    # ETAPE 3 : EXPLORATION (EDA)
    # ══════════════════════════════════════════
    with tab_explore:
        st.markdown("### Étape 3 — Analyse exploratoire (EDA)")
        st.caption(
            "Tendances, corrélations, segments et saisonnalités — proposés par "
            "l'agent Analyse et calculés sur vos données."
        )

        explore_tabs = ["🧭 Axes d'analyse", "🔗 Corrélations", "🧩 Segmentation", "🗓️ Temporel"]
        if has_geo:
            explore_tabs.append("🗺️ Carte")
        sub = st.tabs(explore_tabs)
        tab_axes, tab_corr, tab_seg, tab_time = sub[0], sub[1], sub[2], sub[3]
        tab_map = sub[4] if has_geo else None

        with tab_axes:
            if st.button("🤖 Proposer des axes d'analyse (IA)", type="primary"):
                if not api_key:
                    st.error("Clé API requise.")
                else:
                    with st.spinner("L'agent Analyse réfléchit..."):
                        axes = get_agents()["analyzer"].suggest_axes(profile)
                        st.session_state.analysis_results["axes"] = axes.get("axes", [])

            for i, axe in enumerate(st.session_state.analysis_results.get("axes", []), 1):
                with st.expander(f"Axe {i} : {axe.get('titre', 'N/A')}", expanded=i <= 2):
                    st.markdown(f"**Description** : {axe.get('description', '')}")
                    if axe.get("colonnes"):
                        st.markdown(f"**Colonnes** : `{'`, `'.join(axe['colonnes'])}`")
                    if axe.get("questions"):
                        st.markdown("**Questions :**")
                        for q in axe["questions"]:
                            st.markdown(f"- {q}")
                    if axe.get("visualisations"):
                        st.markdown(
                            f"**Visualisations recommandées** : {', '.join(axe['visualisations'])}"
                        )

        with tab_corr:
            numeric_cols = profile["numeric_columns"]
            if len(numeric_cols) >= 2:
                st.markdown("#### Matrice de corrélation")
                corr = df[numeric_cols].corr()
                fig = go.Figure(
                    data=go.Heatmap(
                        z=corr.values,
                        x=corr.columns.tolist(),
                        y=corr.index.tolist(),
                        colorscale=DIVERGING_SCALE,
                        zmid=0,
                        zmin=-1,
                        zmax=1,
                        text=corr.round(2).values,
                        texttemplate="%{text}",
                    )
                )
                fig.update_layout(height=500, template="plotly_white")
                st.plotly_chart(fig, use_container_width=True)
                st.session_state.analysis_results.setdefault("correlations", True)

                upper = corr.where(
                    np.triu(np.ones(corr.shape, dtype=bool), k=1)
                )
                pairs = upper.stack().sort_values(key=abs, ascending=False).head(5)
                if len(pairs) > 0:
                    st.markdown("**Relations les plus fortes :**")
                    for (c1, c2), v in pairs.items():
                        sens = "positive" if v > 0 else "négative"
                        st.markdown(f"- `{c1}` ↔ `{c2}` : {v:.2f} (corrélation {sens})")
            else:
                st.info("Il faut au moins 2 colonnes numériques pour les corrélations.")

        with tab_seg:
            st.markdown("#### Segmentation K-Means")
            numeric_cols = profile["numeric_columns"]
            if len(numeric_cols) >= 2:
                seg_cols = st.multiselect(
                    "Colonnes pour la segmentation",
                    numeric_cols,
                    default=numeric_cols[:2],
                )
                n_clusters = st.slider("Nombre de segments", 2, 8, 3)

                if st.button("Lancer la segmentation") and len(seg_cols) >= 2:
                    with st.spinner("Segmentation en cours..."):
                        seg_df, seg_info = get_agents()["analyzer"].compute_segmentation(
                            df, seg_cols, n_clusters
                        )
                        st.session_state.analysis_results["segmentation"] = {
                            "df": seg_df,
                            "info": seg_info,
                            "cols": seg_cols,
                        }

                if "segmentation" in st.session_state.analysis_results:
                    seg_data = st.session_state.analysis_results["segmentation"]
                    seg_df, seg_info = seg_data["df"], seg_data["info"]
                    used_cols = seg_data.get("cols", seg_cols)

                    if "error" not in seg_info and len(used_cols) >= 2:
                        fig = px.scatter(
                            seg_df,
                            x=used_cols[0],
                            y=used_cols[1],
                            color=seg_df["segment"].astype(str),
                            title="Segmentation K-Means",
                            template="plotly_white",
                            color_discrete_sequence=CATEGORICAL,
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        for seg_name, info in seg_info["segments"].items():
                            st.markdown(
                                f"**{seg_name}** : {info['count']} éléments ({info['pct']}%)"
                            )
                    elif "error" in seg_info:
                        st.error(seg_info["error"])
            else:
                st.info("Il faut au moins 2 colonnes numériques pour la segmentation.")

        with tab_time:
            date_cols = profile["date_columns"]
            if date_cols:
                selected_date = st.selectbox("Colonne temporelle", date_cols)
                if st.button("Analyser la dimension temporelle"):
                    with st.spinner("Analyse temporelle..."):
                        time_result = get_agents()["analyzer"].compute_time_analysis(
                            df, selected_date
                        )
                        st.session_state.analysis_results["time"] = time_result

                if "time" in st.session_state.analysis_results:
                    tr = st.session_state.analysis_results["time"]
                    st.markdown(
                        f"**Période** : {tr['date_range']['min']} → {tr['date_range']['max']}"
                    )

                    if tr["count_by_year"]:
                        year_df = pd.DataFrame(
                            list(tr["count_by_year"].items()),
                            columns=["Année", "Nombre"],
                        )
                        fig = px.bar(
                            year_df, x="Année", y="Nombre",
                            title="Distribution par année", template="plotly_white",
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    if tr["count_by_month"]:
                        month_names = {
                            1: "Jan", 2: "Fév", 3: "Mar", 4: "Avr", 5: "Mai", 6: "Juin",
                            7: "Juil", 8: "Août", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Déc",
                        }
                        month_df = pd.DataFrame(
                            [(month_names.get(int(k), k), v)
                             for k, v in tr["count_by_month"].items()],
                            columns=["Mois", "Nombre"],
                        )
                        fig = px.bar(
                            month_df, x="Mois", y="Nombre",
                            title="Distribution par mois (saisonnalité)",
                            template="plotly_white",
                        )
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune colonne temporelle détectée dans le dataset.")

        if tab_map is not None:
            with tab_map:
                st.markdown("#### Carte géographique interactive")
                lat_col = geo_info.get("latitude")
                lon_col = geo_info.get("longitude")
                geojson_col = geo_info.get("geojson")
                location_names = geo_info.get("location_name", [])

                if lat_col and lon_col:
                    clean_geo = df.dropna(subset=[lat_col, lon_col]).copy()
                    n_points = len(clean_geo)
                    st.markdown(
                        f"**{n_points} points géographiques** détectés "
                        f"(colonnes : `{lat_col}`, `{lon_col}`)"
                    )

                    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)
                    with col_ctrl1:
                        map_type = st.selectbox(
                            "Type de carte",
                            ["Marqueurs", "Carte de densité (Heatmap)", "Marqueurs + Densité"],
                        )
                    with col_ctrl2:
                        tile_style = st.selectbox(
                            "Style de fond",
                            ["CartoDB positron", "CartoDB dark_matter", "OpenStreetMap"],
                        )
                    with col_ctrl3:
                        color_options = ["Aucune"] + location_names + [
                            c for c in df.select_dtypes(include=["object", "category"]).columns
                            if c not in [lat_col, lon_col, geojson_col or ""]
                            and df[c].nunique() <= 30
                        ]
                        color_by = st.selectbox("Colorer par", color_options)

                    center = get_map_center(clean_geo, lat_col, lon_col)
                    m = folium.Map(location=center, zoom_start=7, tiles=tile_style)

                    if map_type in ["Marqueurs", "Marqueurs + Densité"]:
                        from folium.plugins import MarkerCluster
                        cluster = MarkerCluster(name="Marqueurs").add_to(m)
                        popup_cols = [
                            c for c in df.columns
                            if c not in [lat_col, lon_col, geojson_col or ""]
                        ]
                        colors_list = [
                            "blue", "orange", "green", "purple", "pink", "darkgreen",
                            "darkblue", "red", "cadetblue", "darkred", "lightblue",
                            "lightgreen", "beige", "gray",
                        ]
                        color_map = {}
                        if color_by != "Aucune" and color_by in clean_geo.columns:
                            unique_vals = clean_geo[color_by].dropna().unique()
                            for idx, val in enumerate(unique_vals):
                                color_map[val] = colors_list[idx % len(colors_list)]

                        for _, row in clean_geo.iterrows():
                            popup_parts = []
                            for c in popup_cols[:8]:
                                val = row.get(c)
                                if pd.notna(val):
                                    val_str = str(val)
                                    if len(val_str) > 80:
                                        val_str = val_str[:80] + "..."
                                    popup_parts.append(f"<b>{c}</b>: {val_str}")
                            popup_html = "<br>".join(popup_parts)
                            marker_color = "blue"
                            if color_by != "Aucune" and color_by in clean_geo.columns:
                                marker_color = color_map.get(row.get(color_by), "gray")
                            folium.Marker(
                                location=[row[lat_col], row[lon_col]],
                                popup=folium.Popup(popup_html, max_width=350),
                                icon=folium.Icon(color=marker_color, icon="info-sign"),
                            ).add_to(cluster)

                    if map_type in ["Carte de densité (Heatmap)", "Marqueurs + Densité"]:
                        from folium.plugins import HeatMap
                        heat_data = clean_geo[[lat_col, lon_col]].values.tolist()
                        HeatMap(heat_data, radius=18, blur=15, max_zoom=10,
                                name="Densité").add_to(m)

                    if geojson_col and geojson_col in df.columns:
                        features = parse_geojson_column(df, geojson_col)
                        if features:
                            fc = {"type": "FeatureCollection", "features": features}
                            folium.GeoJson(
                                fc,
                                name="Zones géographiques",
                                style_function=lambda x: {
                                    "fillColor": "#2a78d6",
                                    "color": "#2a78d6",
                                    "weight": 2,
                                    "fillOpacity": 0.1,
                                },
                            ).add_to(m)

                    folium.LayerControl(collapsed=False).add_to(m)
                    st_folium(m, width=None, height=600, use_container_width=True)

                    if location_names:
                        st.divider()
                        loc_col = location_names[0]
                        loc_counts = df[loc_col].value_counts().head(15).reset_index()
                        loc_counts.columns = [loc_col, "Nombre"]
                        fig_loc = px.bar(
                            loc_counts, x=loc_col, y="Nombre",
                            title=f"Distribution par {loc_col}",
                            template="plotly_white",
                        )
                        fig_loc.update_layout(height=400)
                        st.plotly_chart(fig_loc, use_container_width=True)
                else:
                    st.warning("Colonnes latitude/longitude non détectées.")

    # ══════════════════════════════════════════
    # ETAPE 4 : DOCUMENTATION DU MODELE
    # ══════════════════════════════════════════
    with tab_doc:
        st.markdown("### Étape 4 — Documentation du modèle & entrepôt")
        st.caption(
            "Dictionnaire de données lisible + proposition de modélisation "
            "d'entrepôt (table de faits / dimensions), générés par l'agent Documentation."
        )

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            if st.button("🤖 Générer le dictionnaire de données", type="primary"):
                if not api_key:
                    st.error("Clé API requise.")
                else:
                    with st.spinner("Rédaction du dictionnaire de données..."):
                        result = get_agents()["documentor"].generate_dictionary(df, profile)
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.session_state.data_dictionary = result
        with col_d2:
            if st.button("🤖 Proposer le modèle d'entrepôt"):
                if not api_key:
                    st.error("Clé API requise.")
                else:
                    with st.spinner("Modélisation de l'entrepôt..."):
                        result = get_agents()["documentor"].propose_warehouse_model(
                            df, profile, st.session_state.data_dictionary
                        )
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.session_state.warehouse_model = result

        dictionary = st.session_state.data_dictionary
        if dictionary:
            st.divider()
            if dictionary.get("resume_dataset"):
                st.markdown(f"**Résumé du dataset :** {dictionary['resume_dataset']}")
            entries = dictionary.get("dictionnaire", [])
            if entries:
                st.markdown("#### Dictionnaire de données")
                dict_df = pd.DataFrame(entries)
                rename = {
                    "colonne": "Colonne",
                    "description": "Description",
                    "type_semantique": "Type",
                    "role_entrepot": "Rôle entrepôt",
                    "exemple": "Exemple",
                    "remarques_qualite": "Qualité",
                }
                dict_df = dict_df.rename(columns=rename)
                st.dataframe(dict_df, use_container_width=True, hide_index=True)

        model = st.session_state.warehouse_model
        if model:
            st.divider()
            st.markdown("#### Modèle d'entrepôt proposé")
            st.markdown(
                f"**Type de schéma** : `{model.get('type_schema', 'N/A')}` — "
                f"{model.get('justification', '')}"
            )
            fact = model.get("table_de_faits") or {}
            col_f, col_dims = st.columns(2)
            with col_f:
                if fact:
                    st.markdown(f"##### 📦 Table de faits : `{fact.get('nom', 'fact')}`")
                    st.markdown(fact.get("description", ""))
                    st.markdown(f"- **Mesures** : {', '.join(fact.get('mesures', []))}")
                    st.markdown(
                        f"- **Clés étrangères** : {', '.join(fact.get('cles_etrangeres', []))}"
                    )
            with col_dims:
                for dim in model.get("dimensions", []):
                    st.markdown(f"##### 🧭 Dimension : `{dim.get('nom', 'dim')}`")
                    st.markdown(
                        f"{dim.get('description', '')} — clé : `{dim.get('cle', '')}` "
                        f"({', '.join(dim.get('colonnes', []))})"
                    )
            if model.get("relations"):
                st.markdown("##### Relations")
                for r in model["relations"]:
                    st.markdown(f"- {r}")
            if model.get("recommandations"):
                st.markdown("##### Recommandations")
                for r in model["recommandations"]:
                    st.markdown(f"- {r}")

        if dictionary:
            st.divider()
            st.markdown("#### Exports")
            documentor = get_agents()["documentor"]
            dataset_name = st.session_state.uploaded_file_name or "dataset"
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                md = documentor.export_markdown(dictionary, model, dataset_name)
                st.download_button(
                    "⬇️ Documentation Markdown",
                    md,
                    file_name="documentation_donnees.md",
                    mime="text/markdown",
                )
            with col_e2:
                dbt_yaml = documentor.export_dbt_yaml(dictionary, dataset_name)
                st.download_button(
                    "⬇️ Schéma dbt (schema.yml)",
                    dbt_yaml,
                    file_name="schema.yml",
                    mime="text/yaml",
                    help="Fichier compatible dbt pour documenter le modèle dans votre entrepôt",
                )

    # ══════════════════════════════════════════
    # ETAPE 5 : CO-CREATION DES KPIs
    # ══════════════════════════════════════════
    with tab_kpi:
        st.markdown("### Étape 5 — Co-création des KPIs (IA + vous)")
        st.caption(
            "L'IA suggère des indicateurs calculables avec des formules transparentes. "
            "Vous sélectionnez ceux à suivre, ou créez les vôtres. Les calculs sont "
            "exécutés de manière déterministe (pandas) — pas de boîte noire."
        )

        if st.button("🤖 Suggérer des KPIs (IA)", type="primary"):
            if not api_key:
                st.error("Clé API requise.")
            else:
                with st.spinner("L'agent KPI analyse votre dataset..."):
                    result = get_agents()["kpi"].suggest_kpis(
                        profile, st.session_state.data_dictionary
                    )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.kpi_suggestions = result.get("kpis", [])

        # Suggestions IA
        if st.session_state.kpi_suggestions:
            st.divider()
            st.markdown("#### KPIs proposés — sélectionnez ceux à suivre")
            for kpi in st.session_state.kpi_suggestions:
                kpi_id = kpi.get("id", kpi.get("nom", ""))
                with st.expander(f"🎯 {kpi.get('nom', kpi_id)}", expanded=False):
                    st.markdown(f"**Description** : {kpi.get('description', '')}")
                    if kpi.get("interet"):
                        st.markdown(f"**Intérêt** : {kpi['interet']}")
                    st.markdown(f"**Formule** : `{kpi.get('formule', '')}`")
                    spec = kpi.get("spec", {})
                    st.caption(
                        f"operation={spec.get('operation')} · colonne={spec.get('colonne')} · "
                        f"group_by={spec.get('group_by')} · date={spec.get('date_col')}"
                    )
                    selected = st.checkbox(
                        "Suivre ce KPI",
                        value=kpi_id in st.session_state.kpi_selected,
                        key=f"kpi_sel_{kpi_id}",
                    )
                    if selected:
                        st.session_state.kpi_selected[kpi_id] = kpi
                    else:
                        st.session_state.kpi_selected.pop(kpi_id, None)

        # KPI personnalise
        st.divider()
        with st.expander("➕ Créer un KPI personnalisé"):
            with st.form("custom_kpi_form"):
                nom = st.text_input("Nom du KPI")
                c1, c2, c3 = st.columns(3)
                with c1:
                    operation = st.selectbox(
                        "Opération",
                        ["sum", "mean", "median", "min", "max", "count", "nunique"],
                    )
                with c2:
                    colonne = st.selectbox(
                        "Colonne", ["(aucune)"] + list(df.columns)
                    )
                with c3:
                    fmt = st.selectbox("Format", ["nombre", "pourcentage", "monetaire"])
                c4, c5, c6 = st.columns(3)
                with c4:
                    group_by = st.selectbox(
                        "Répartition par (optionnel)",
                        ["(aucune)"] + profile["categorical_columns"],
                    )
                with c5:
                    date_col = st.selectbox(
                        "Évolution temporelle (optionnel)",
                        ["(aucune)"] + profile["date_columns"],
                    )
                with c6:
                    granularite = st.selectbox(
                        "Granularité", ["mois", "jour", "semaine", "annee"]
                    )
                submitted = st.form_submit_button("Ajouter ce KPI")
                if submitted:
                    if not nom:
                        st.error("Donnez un nom au KPI.")
                    elif operation not in ("count",) and colonne == "(aucune)":
                        st.error("Choisissez une colonne pour cette opération.")
                    else:
                        st.session_state.custom_kpi_count += 1
                        kpi_id = f"custom_{st.session_state.custom_kpi_count}"
                        spec = {
                            "operation": operation,
                            "colonne": None if colonne == "(aucune)" else colonne,
                            "group_by": None if group_by == "(aucune)" else group_by,
                            "date_col": None if date_col == "(aucune)" else date_col,
                            "granularite": granularite,
                        }
                        graphique = (
                            "line" if spec["date_col"]
                            else ("bar" if spec["group_by"] else "none")
                        )
                        st.session_state.kpi_selected[kpi_id] = {
                            "id": kpi_id,
                            "nom": nom,
                            "description": "KPI personnalisé",
                            "formule": f"{operation}({colonne})",
                            "format": fmt,
                            "graphique": graphique,
                            "spec": spec,
                        }
                        st.success(f"KPI « {nom} » ajouté !")

        # Calcul
        n_selected = len(st.session_state.kpi_selected)
        st.divider()
        st.markdown(f"**{n_selected} KPI(s) sélectionné(s)**")
        if st.button(
            "🧮 Calculer les KPIs sélectionnés",
            type="primary",
            disabled=n_selected == 0,
        ):
            kpi_agent = get_agents()["kpi"]
            results = {}
            with st.spinner("Calcul déterministe des KPIs..."):
                for kpi_id, kpi in st.session_state.kpi_selected.items():
                    results[kpi_id] = kpi_agent.compute_kpi(df, kpi.get("spec", {}))
            st.session_state.kpi_results = results
            st.success("KPIs calculés ! Rendez-vous à l'étape 6 · Dashboard.")

        if st.session_state.kpi_results:
            st.markdown("#### Aperçu des valeurs")
            kpi_agent = get_agents()["kpi"]
            for kpi_id, res in st.session_state.kpi_results.items():
                kpi = st.session_state.kpi_selected.get(kpi_id, {})
                if res.get("erreur"):
                    st.error(f"{kpi.get('nom', kpi_id)} : {res['erreur']}")
                else:
                    st.markdown(
                        f"- **{kpi.get('nom', kpi_id)}** : "
                        f"{kpi_agent.format_value(res['valeur'], kpi.get('format', 'nombre'))}"
                    )

    # ══════════════════════════════════════════
    # ETAPE 6 : DASHBOARD
    # ══════════════════════════════════════════
    with tab_dash:
        st.markdown("### Étape 6 — Tableau de bord")

        if not st.session_state.kpi_selected:
            st.info(
                "Aucun KPI sélectionné pour l'instant. Passez par l'étape "
                "**5 · KPIs** pour co-créer vos indicateurs, ou générez un "
                "dashboard automatique ci-dessous."
            )

        # ---- Filtres interactifs ----
        df_filtered = df
        filter_desc = []
        cat_cols = [c for c in profile["categorical_columns"] if df[c].nunique() <= 50]
        with st.container():
            fcols = st.columns(3)
            with fcols[0]:
                filter_col = st.selectbox(
                    "Filtrer par dimension", ["Aucune"] + cat_cols
                )
            with fcols[1]:
                if filter_col != "Aucune":
                    options = sorted(df[filter_col].dropna().unique().tolist())
                    chosen = st.multiselect(
                        "Valeurs (vide = toutes)", options, default=[]
                    )
                    if chosen:
                        df_filtered = df_filtered[df_filtered[filter_col].isin(chosen)]
                        filter_desc.append(f"{filter_col} ∈ {chosen}")
            with fcols[2]:
                if profile["date_columns"]:
                    date_filter_col = st.selectbox(
                        "Filtre temporel", ["Aucun"] + profile["date_columns"]
                    )
                    if date_filter_col != "Aucun":
                        dates = pd.to_datetime(
                            df[date_filter_col], errors="coerce"
                        ).dropna()
                        if len(dates) > 0:
                            dmin, dmax = dates.min().date(), dates.max().date()
                            rng = st.date_input(
                                "Période", (dmin, dmax),
                                min_value=dmin, max_value=dmax,
                            )
                            if isinstance(rng, tuple) and len(rng) == 2:
                                parsed = pd.to_datetime(
                                    df_filtered[date_filter_col], errors="coerce"
                                )
                                mask = (parsed.dt.date >= rng[0]) & (
                                    parsed.dt.date <= rng[1]
                                )
                                df_filtered = df_filtered[mask]
                                if (rng[0], rng[1]) != (dmin, dmax):
                                    filter_desc.append(f"{rng[0]} → {rng[1]}")

        if filter_desc:
            st.caption(
                f"Filtres actifs : {' · '.join(filter_desc)} — "
                f"{len(df_filtered):,} lignes sur {len(df):,}"
            )

        # ---- Cartes KPI ----
        if st.session_state.kpi_selected:
            kpi_agent = get_agents()["kpi"]
            st.divider()
            st.markdown("#### Vos indicateurs")
            kpis = list(st.session_state.kpi_selected.items())
            live_results = {}
            for kpi_id, kpi in kpis:
                live_results[kpi_id] = kpi_agent.compute_kpi(
                    df_filtered, kpi.get("spec", {})
                )

            for row_start in range(0, len(kpis), 4):
                row = kpis[row_start:row_start + 4]
                cols = st.columns(4)
                for (kpi_id, kpi), col in zip(row, cols):
                    res = live_results[kpi_id]
                    with col:
                        if res.get("erreur"):
                            st.metric(kpi.get("nom", kpi_id), "—")
                            st.caption(f"⚠️ {res['erreur']}")
                        else:
                            st.metric(
                                kpi.get("nom", kpi_id),
                                kpi_agent.format_value(
                                    res["valeur"], kpi.get("format", "nombre")
                                ),
                            )

            # ---- Graphiques des KPIs ----
            kpi_figs = []
            for kpi_id, kpi in kpis:
                res = live_results[kpi_id]
                if res.get("erreur"):
                    continue
                nom = kpi.get("nom", kpi_id)
                serie = res.get("serie")
                groupes = res.get("groupes")
                if serie is not None and len(serie) > 1:
                    fig = px.line(
                        serie, x=serie.columns[0], y="valeur",
                        title=f"{nom} — évolution",
                        template="plotly_white", markers=True,
                    )
                    fig.update_traces(line=dict(width=2, color=CATEGORICAL[0]),
                                      marker=dict(size=6))
                    kpi_figs.append(fig)
                if groupes is not None and len(groupes) > 1:
                    fig = px.bar(
                        groupes, x=groupes.columns[0], y="valeur",
                        title=f"{nom} — répartition",
                        template="plotly_white",
                    )
                    fig.update_traces(marker_color=CATEGORICAL[0])
                    kpi_figs.append(fig)

            if kpi_figs:
                st.divider()
                st.markdown("#### Graphiques des KPIs")
                for i in range(0, len(kpi_figs), 2):
                    cols = st.columns(2)
                    for j, col in enumerate(cols):
                        if i + j < len(kpi_figs):
                            with col:
                                st.plotly_chart(
                                    kpi_figs[i + j], use_container_width=True
                                )

        # ---- Visualisations complementaires ----
        st.divider()
        st.markdown("#### Visualisations complémentaires")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Dashboard automatique"):
                with st.spinner("Génération du dashboard..."):
                    agents = get_agents()
                    chart_specs = agents["visualizer"].auto_dashboard(
                        df_filtered, profile
                    )
                    st.session_state.charts = agents["visualizer"].create_all_charts(
                        df_filtered, chart_specs, profile
                    )
        with col2:
            if st.button("Dashboard IA (Claude)"):
                if not api_key:
                    st.error("Clé API requise.")
                else:
                    with st.spinner("L'agent Visualisation compose le dashboard..."):
                        agents = get_agents()
                        ai_specs = agents["visualizer"].suggest_charts(profile)
                        chart_list = ai_specs.get("charts", [])
                        st.session_state.charts = agents["visualizer"].create_all_charts(
                            df_filtered, chart_list, profile
                        )

        if st.session_state.charts:
            plotly_charts = [
                c for c in st.session_state.charts
                if isinstance(c["figure"], go.Figure)
            ]
            folium_maps = [
                c for c in st.session_state.charts
                if isinstance(c["figure"], folium.Map)
            ]
            for i in range(0, len(plotly_charts), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx < len(plotly_charts):
                        with col:
                            st.plotly_chart(
                                plotly_charts[idx]["figure"],
                                use_container_width=True,
                            )
            for map_chart in folium_maps:
                st.markdown(f"##### {map_chart['spec'].get('title', 'Carte')}")
                st_folium(map_chart["figure"], width=None, height=500)

    # ══════════════════════════════════════════
    # CHAT IA (transversal)
    # ══════════════════════════════════════════
    with tab_chat:
        st.markdown("### Discutez avec vos données")
        st.markdown(
            "Posez vos questions en langage naturel — l'orchestrateur route vers "
            "l'agent spécialisé (profiling, nettoyage, analyse, visualisation)."
        )

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Ex : Propose-moi des axes d'analyse..."):
            if not api_key:
                st.error("Veuillez entrer votre clé API Anthropic dans la barre latérale.")
            else:
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("Les agents travaillent..."):
                        agents = get_agents()
                        orch = agents["orchestrator"]
                        result = orch.process_message(prompt, df, profile)
                        intent = result["intent"]
                        response_text = result["response"]

                        badge_map = {
                            "profile": ("Profiler", "profiler"),
                            "clean": ("Nettoyage", "cleaning"),
                            "analyze": ("Analyse", "analysis"),
                            "visualize": ("Visualisation", "viz"),
                        }
                        if intent in badge_map:
                            name, cls = badge_map[intent]
                            st.markdown(
                                f'<span class="agent-badge agent-{cls}">Agent {name}</span>',
                                unsafe_allow_html=True,
                            )
                        st.markdown(response_text)

                        action_result = orch.handle_intent(
                            intent, df, profile, agents, user_message=prompt
                        )

                        if action_result["type"] == "text":
                            st.markdown(action_result["content"])
                            response_text += "\n\n" + action_result["content"]

                        elif action_result["type"] == "cleaning":
                            st.session_state.df_cleaned = action_result["cleaned_df"]
                            st.session_state.cleaning_log = action_result["log"]
                            st.markdown("**Actions de nettoyage effectuées :**")
                            for entry in action_result["log"]:
                                st.markdown(f"- {entry}")
                            before, after = len(df), len(action_result["cleaned_df"])
                            st.info(
                                f"Avant : {before} lignes → Après : {after} lignes. "
                                "Validez le résultat dans l'onglet **2 · Nettoyage**."
                            )
                            response_text += (
                                f"\n\nNettoyage effectué : {before} → {after} lignes"
                            )

                        elif action_result["type"] == "analysis":
                            axes = action_result.get("axes", {})
                            if "axes" in axes:
                                st.session_state.analysis_results["axes"] = axes["axes"]
                                for i, axe in enumerate(axes["axes"], 1):
                                    st.markdown(f"**Axe {i} : {axe.get('titre', 'N/A')}**")
                                    st.markdown(f"_{axe.get('description', '')}_")
                                response_text += "\n\n" + "\n".join(
                                    f"Axe {i}: {a.get('titre', '')}"
                                    for i, a in enumerate(axes["axes"], 1)
                                )
                            else:
                                st.json(axes)

                        elif action_result["type"] == "dashboard":
                            st.session_state.charts = action_result["charts"]
                            st.success(
                                f"{len(action_result['charts'])} visualisations générées ! "
                                "Rendez-vous dans l'onglet **6 · Dashboard**."
                            )
                            response_text += (
                                f"\n\n{len(action_result['charts'])} graphiques créés."
                            )

                st.session_state.chat_history.append(
                    {"role": "assistant", "content": response_text}
                )
