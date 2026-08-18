# DataAnalyst AI - Plateforme de preparation de donnees & BI pilotee par agents IA

## Le Besoin

Les entreprises et analystes de donnees font face a des defis recurrents :

- **Complexite technique** : L'analyse de donnees necessite des competences en programmation, statistiques et visualisation.
- **Temps perdu** : Le nettoyage, la transformation et la documentation representent 60 a 80% du temps d'un projet data.
- **Manque de confiance** : Les outils IA "boite noire" appliquent des transformations sans validation humaine.
- **Outils fragmentes** : Excel, Python, outils BI, documentation... tout est disperse.

**DataAnalyst AI** repond a ce besoin : une plateforme unique qui accompagne l'utilisateur
pas a pas, de la donnee brute au tableau de bord, en le laissant maitre des decisions cles.

---

## Le Parcours en 6 etapes

```
[ Donnees Brutes ] -> Diagnostic -> Nettoyage -> Exploration -> Documentation -> KPIs -> Dashboard
```

| # | Etape | Ce que fait la plateforme | Validation utilisateur |
|---|-------|---------------------------|------------------------|
| 1 | **Diagnostic & profilage** | Des le chargement : types de colonnes, anomalies (manquantes, doublons, outliers), score qualite, detection geo/temporel. Automatique et sans cle API. | — |
| 2 | **Nettoyage intelligent & guide** | L'agent Nettoyage propose un **plan sur-mesure** (doublons, valeurs nulles, types, casse, outliers) avec raison et **impact estime par action**. | ✅ L'utilisateur coche/decoche chaque action avant application. Donnee d'origine toujours preservee (restauration possible). |
| 3 | **Analyse exploratoire (EDA)** | Axes d'analyse strategiques (IA), matrice de correlations + relations les plus fortes, segmentation K-Means, saisonnalites, cartes interactives. | Choix des colonnes / parametres |
| 4 | **Documentation du modele** | Dictionnaire de donnees complet (descriptions metier, types semantiques, roles entrepot) + modelisation d'entrepot (table de faits / dimensions / cles). **Exports : Markdown + schema.yml compatible dbt.** | Relecture / export |
| 5 | **Co-creation des KPIs** | L'agent KPI suggere des indicateurs **calculables** avec formules transparentes (spec structuree : operation, colonne, ratio, group_by, granularite). Le calcul est execute **de maniere deterministe par pandas** — pas de boite noire. | ✅ Selection des KPIs, creation de KPIs personnalises via formulaire |
| 6 | **Tableau de bord** | Les KPIs valides deviennent des cartes + graphiques (evolution, repartition), **filtrables** par dimension et periode. Dashboards complementaires automatiques ou composes par l'IA. | Filtres interactifs, ajustements en langage naturel |

💬 **Chat transversal** : a toute etape, l'utilisateur peut piloter la plateforme en langage
naturel (francais / anglais) — l'orchestrateur route vers l'agent specialise.

---

## Architecture Multi-Agents (7 agents)

```
                        Utilisateur
                            |
                       [Chat NLP]
                            |
                    ┌───────┴───────┐
                    | ORCHESTRATEUR |
                    └───────┬───────┘
                            |
   ┌─────────┬─────────┬────┴────┬──────────────┬─────────┐
   v         v         v         v              v         v
PROFILER  NETTOYAGE  ANALYSE  VISUALISATION  DOCUMENTATION  KPI
```

| Agent | Etape | Role |
|-------|-------|------|
| **Orchestrateur** | Chat | Comprend le langage naturel, detecte l'intention, route |
| **Profiler** | 1 | Types, distributions, manquantes, geo/temporel, insights IA |
| **Nettoyage** | 2 | Plan de nettoyage justifie + impacts estimes, application deterministe |
| **Analyse** | 3 | Axes d'analyse, correlations, K-Means, series temporelles |
| **Documentation** | 4 | Dictionnaire de donnees, modele faits/dimensions, exports Markdown & dbt |
| **KPI** | 5-6 | Suggestions de KPIs calculables, calcul deterministe pandas, formatage |
| **Visualisation** | 6 | Graphiques Plotly, cartes Folium, dashboards auto/IA |

### Les 3 piliers

1. **Fiabilite (pas de boite noire)** : l'IA propose, l'humain valide (nettoyage, KPIs). Les calculs de KPIs sont executes par du code pandas deterministe a partir de specs transparentes.
2. **Gain de temps massif** : profiling, plan de nettoyage, documentation, dictionnaire, KPIs et dashboards generes en minutes.
3. **Accessibilite totale** : parcours guide en 6 etapes + pilotage en langage naturel.

---

## Stack Technique

| Composant | Technologie | Role |
|-----------|-------------|------|
| Interface | Streamlit | Application web, parcours guide en onglets + stepper |
| IA | API Claude (Anthropic) — `claude-sonnet-5` | Moteur NLP et intelligence des agents |
| Multi-Agents | Systeme custom Python | 7 agents specialises |
| Donnees | Pandas, NumPy | Manipulation, calculs KPI deterministes |
| ML | scikit-learn | Segmentation K-Means |
| Graphiques | Plotly (palette accessible daltonisme) | Visualisations interactives |
| Cartes | Folium, GeoPandas | Cartographie |
| Docs | Markdown + dbt schema.yml | Exports de documentation |

---

## Structure du Projet

```
data analyste AI/
├── app.py                          # Application Streamlit (parcours 6 etapes + chat)
├── config.py                       # Configuration API et parametres
├── requirements.txt
├── PROJET.md
├── agents/
│   ├── base_agent.py               # Communication Claude API
│   ├── orchestrator_agent.py       # Chat / routage d'intentions
│   ├── profiler_agent.py           # Etape 1 : diagnostic
│   ├── cleaning_agent.py           # Etape 2 : plan de nettoyage + impacts + application
│   ├── analysis_agent.py           # Etape 3 : EDA
│   ├── documentation_agent.py      # Etape 4 : dictionnaire + entrepot + exports
│   ├── kpi_agent.py                # Etape 5 : suggestion + calcul deterministe des KPIs
│   ├── visualization_agent.py      # Etape 6 : dashboards
│   └── reporter_agent.py           # Rapports (v2)
└── utils/
    ├── data_loader.py              # Chargement CSV/Excel
    ├── geo_utils.py                # Detection et traitement geo
    └── viz_theme.py                # Palette de charts validee (accessibilite)
```

---

## Lancement

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="votre-cle-api"   # (ou saisie dans la barre laterale)
streamlit run app.py
```

Application accessible sur **http://localhost:8501**.
Le diagnostic (etape 1) fonctionne sans cle API ; les fonctions IA (plan de
nettoyage, documentation, KPIs, chat) necessitent la cle.

---

## Pistes d'evolution (issues de la veille)

- **DuckDB + Text-to-SQL** : executer du SQL sur les fichiers charges et permettre au chat de repondre par requetes SQL generees (inspiration : agents d'analyse DuckDB, modeles sqlcoder/Qwen-Coder).
- **Semantic layer** : exposer les KPIs valides comme couche semantique interrogeable (inspiration : Cube.js, WrenAI).
- **dbt** : l'export `schema.yml` est deja compatible dbt ; aller plus loin en generant les modeles SQL de la table de faits et des dimensions proposees.
- **Connecteurs** : bases de donnees et APIs en plus des fichiers CSV/Excel.
