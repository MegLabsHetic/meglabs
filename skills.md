---
name: data-viz-rigueur
description: Méthode complète de data engineering et data analyse pour produire des visualisations et des restitutions de données rigoureuses, lisibles et honnêtes. Utilise ce skill dès qu'il est question de graphique, chart, dashboard, KPI, reporting, tableau de bord, analyse exploratoire (EDA), profiling de données, restitution de résultats chiffrés, comparaison de séries, ou dès qu'un jeu de données (CSV, Excel, SQL, DataFrame, parquet) doit être exploré, nettoyé, agrégé ou présenté — même si l'utilisateur ne demande pas explicitement "un graphique". Utilise-le aussi pour critiquer ou corriger une visualisation existante.
---

# Data viz & restitution : la méthode

Le but de ce skill : ne jamais produire un graphique joli mais faux, ni un graphique juste mais illisible. Un graphique est un **argument**, pas une décoration. S'il ne porte pas une phrase défendable, il ne doit pas exister.

## Ordre de travail non négociable

Ne jamais sauter directement au code de visualisation. Suivre cet enchaînement :

1. **Cadrer** — quelle question, pour qui, quelle décision derrière ?
2. **Profiler** — connaître la donnée avant de la tracer.
3. **Nettoyer / agréger** — de façon tracée et réversible.
4. **Choisir la forme** — la tâche visuelle détermine le type de graphique.
5. **Encoder** — respecter la hiérarchie perceptive.
6. **Annoter** — le titre porte la conclusion.
7. **Vérifier** — checklist finale avant livraison.

Si l'utilisateur fournit un jeu de données sans question précise, faire l'étape 2 d'abord et **restituer le profil avant de proposer des graphiques**. Le profiling révèle presque toujours des questions meilleures que celles posées au départ.

---

## 1. Cadrer

Trois questions à trancher (les poser si la réponse n'est pas déductible du contexte, en une seule fois, pas en interrogatoire) :

- **La question** : "Est-ce que X a augmenté ?" est une question. "Analyse mes ventes" n'en est pas une.
- **L'audience** : un COMEX veut 1 chiffre + 1 tendance + 1 décision. Un analyste métier veut la distribution et les cas limites. Un data scientist veut les résidus.
- **L'unité d'analyse** : une ligne = quoi ? Une transaction, un client, un client-mois ? Toute l'analyse dépend de ce choix, et c'est la source n°1 d'erreurs de double comptage.

## 2. Profiler (obligatoire avant toute viz)

Toujours produire ce profil, même rapidement, et **signaler ce qui cloche** :

| À vérifier | Pourquoi ça compte |
|---|---|
| Dimensions (lignes × colonnes) | Ordre de grandeur, faisabilité |
| Types réels vs types attendus | Dates en `object`, montants en `str` avec virgule décimale |
| Taux de nuls par colonne | Un nul n'est pas un zéro. Un nul structurel n'est pas un nul accidentel |
| Doublons (clé métier, pas `duplicated()` global) | Double comptage silencieux |
| Cardinalité des catégorielles | 3 modalités → barres ; 400 modalités → top N + "Autres" |
| Plage et granularité temporelle | Trous, doublons de période, fuseaux |
| Périodes incomplètes | **Le dernier mois/jour partiel provoque une fausse chute** — la plus fréquente des erreurs de dashboard |
| Distribution des numériques (min, q1, médiane, q3, max) | Asymétrie, valeurs sentinelles (-1, 9999, 0 pour "inconnu") |
| Unités et devises | Mélange k€/€, TTC/HT, m²/ha |
| Cohérence des jointures | Compter les lignes avant/après chaque merge, systématiquement |

En Python, privilégier une passe explicite plutôt qu'un `.describe()` seul :

```python
import pandas as pd

def profil(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "n_null": df.isna().sum(),
        "pct_null": (df.isna().mean() * 100).round(1),
        "n_unique": df.nunique(dropna=True),
        "exemple": df.apply(lambda s: s.dropna().iloc[0] if s.notna().any() else None),
    })
```

Pour des volumes importants, utiliser DuckDB ou Polars plutôt que pandas — `duckdb.sql("SUMMARIZE SELECT * FROM 'fichier.parquet'")` fait le profil en une ligne sans charger le fichier en mémoire.

## 3. Nettoyer et agréger

- Toute transformation doit être **explicite dans le code**, jamais dans un fichier modifié à la main. La chaîne source → figure doit être rejouable.
- Ne jamais supprimer une ligne sans compter combien et sans le dire dans le commentaire ou la restitution.
- Décider et **documenter** le traitement des nuls : exclus, imputés (par quoi), ou catégorie "Non renseigné" à part entière.
- Ne pas écraser les outliers sans les regarder : un outlier est souvent l'information la plus intéressante du jeu de données, ou un bug de saisie qui invalide tout le reste.
- Après chaque agrégation, vérifier que la somme des parties égale le total attendu.

## 4. Choisir la forme

Le type de graphique découle de la **tâche visuelle**, pas de l'esthétique.

| Tâche | Forme adaptée | À éviter |
|---|---|---|
| Comparer des catégories | Barres horizontales triées par valeur | Camembert, radar |
| Composition d'un tout | Barres empilées à 100 %, treemap, waterfall | Camembert au-delà de 4-5 parts |
| Évolution dans le temps | Ligne (temps continu), barres (périodes discrètes peu nombreuses) | Aires empilées avec >4 séries |
| Distribution | Histogramme, densité, boxplot, strip/beeswarm si n petit | Barres de moyennes seules |
| Relation entre 2 variables | Nuage de points (+ tendance si justifiée) | Double axe Y |
| Comparer beaucoup de séries | **Small multiples** (grille de mini-graphiques) | Spaghetti chart |
| Part vs total sur plusieurs entités | Barres groupées, dot plot, slopegraph | Camemberts côte à côte |
| Écart à une référence | Barres divergentes centrées sur 0, dumbbell | Barres classiques |
| Flux, parcours | Sankey, alluvial | Diagramme de réseau non ordonné |
| Données géographiques | Choroplèthe **avec taux, jamais avec effectifs bruts** | Bulles sur carte à surface mal calibrée |

Règles de décision utiles :
- Plus de 6-7 séries sur un même graphique → passer en small multiples.
- Deux échelles différentes → **deux graphiques empilés partageant l'axe X**, jamais un double axe Y (il permet de fabriquer n'importe quelle corrélation visuelle).
- Un tableau bien mis en forme bat souvent un graphique quand il y a moins de ~10 valeurs à lire précisément. Ne pas grapher par réflexe.

## 5. Encoder

Hiérarchie perceptive (du plus précis au moins précis) : **position > longueur > angle > aire > couleur/densité**. Mettre la variable la plus importante sur le canal le plus précis disponible.

- **Axe des barres : toujours ancré à zéro.** La longueur encode la valeur ; la tronquer ment. Un axe de graphique en ligne peut être tronqué, en le signalant.
- **Ordonner les catégories par valeur**, pas par ordre alphabétique — sauf ordre naturel (mois, tranches d'âge, échelle de Likert).
- **Couleur** : catégorielle (≤ 7 teintes, distinguables en deuil de couleur / daltonisme), séquentielle (une teinte, luminosité croissante) pour une grandeur ordonnée, divergente (deux teintes, neutre au centre) pour un écart à une référence. Ne jamais utiliser un dégradé arc-en-ciel type `jet` : il crée des frontières qui n'existent pas dans la donnée.
- **La couleur ne sert pas à décorer** : si toutes les barres représentent la même chose, elles ont la même couleur. Mettre en évidence une seule catégorie en couleur et le reste en gris est presque toujours plus lisible qu'une palette complète.
- **Pas de 3D, pas d'ombres, pas d'effets de perspective.** Ils déforment la lecture des surfaces.
- **Étiquetage direct** plutôt que légende quand c'est possible : le lecteur ne doit pas faire d'aller-retour entre la courbe et un encadré.
- Grille discrète, axes allégés, pas de bordure inutile : maximiser le ratio données/encre sans rendre la lecture ascétique.
- Formats de nombres lisibles : `1,2 M€` et non `1234567.891`. Séparateurs de milliers, unité dans le titre d'axe, décimales limitées à ce qui est significatif.

## 6. Annoter — la partie que tout le monde saute

Un graphique livré sans annotation est un graphique inachevé.

- **Le titre porte la conclusion**, pas le contenu.
  - Faible : « Chiffre d'affaires par trimestre »
  - Correct : « Le chiffre d'affaires recule de 12 % au T2, tiré par la région Nord »
- Sous-titre : périmètre, unité, période (« Périmètre France, hors filiales, en M€ HT, 2023-2025 »).
- Note de bas de figure : **source, date d'extraction, n, méthode de calcul**, et toute exclusion opérée.
- Annoter directement sur le graphique les points qui portent l'argument (rupture, pic, seuil réglementaire, changement de méthode de comptage).
- Marquer visuellement les périodes incomplètes ou les données estimées (hachures, ligne pointillée).

## 7. Honnêteté statistique

- Ne jamais présenter un pourcentage sans son dénominateur ou son effectif.
- Ne pas écrire « augmente » pour une variation dans le bruit : si l'incertitude est calculable, la montrer (intervalle, bande) ; sinon le dire.
- Corrélation ≠ causalité : formuler « X et Y évoluent ensemble », pas « X provoque Y », sauf design expérimental.
- Attention aux moyennes sur distributions asymétriques → préférer la médiane, ou montrer la distribution.
- Effets de composition (paradoxe de Simpson) : quand un agrégat contredit ses sous-groupes, montrer les sous-groupes.
- Ne pas comparer des périodes de longueurs différentes, ni des périmètres qui ont changé sans le signaler.
- Si la donnée ne permet pas de répondre à la question posée, **le dire** au lieu de produire un graphique qui fait semblant.

## 8. Formats de restitution

**Dashboard direction / COMEX**
Pyramide inversée : 3 à 5 KPI en haut avec variation vs période de référence, puis 2-3 graphiques d'explication, puis le détail. Chaque KPI porte une comparaison (vs N-1, vs objectif) — un chiffre seul n'est pas informatif. Pas de scroll pour l'essentiel.

**Rapport d'analyse**
Question → méthode et périmètre → résultats (un graphique = une idée) → limites → recommandations. Les limites ne sont pas une faiblesse, elles sont ce qui rend le reste crédible.

**One-pager**
Un graphique principal, un titre-conclusion, trois puces de lecture, la source. Rien d'autre.

**Notebook exploratoire**
Ordre de lecture linéaire, cellules courtes, une conclusion écrite en markdown après chaque bloc de code. Un notebook sans texte n'est pas une analyse, c'est un brouillon.

## 9. Stack et conventions de code

Choix par défaut, à adapter au contexte de l'utilisateur :

| Besoin | Outil |
|---|---|
| Manipulation < 1 Go | pandas |
| Volumes importants, pipelines | Polars, DuckDB |
| SQL sur fichiers locaux | DuckDB (`read_parquet`, `read_csv_auto`) |
| Figure statique publiable | matplotlib (contrôle total) |
| Statistique exploratoire rapide | seaborn |
| Grammaire des graphiques, déclaratif | Altair / plotnine |
| Interactif, dashboard web | Plotly, ECharts, Observable Plot |
| Dashboard applicatif Python | Streamlit (prototype), Dash / Panel (production) |

Conventions :
- Fonctions pures `donnée → figure`, paramétrées ; pas de constantes cachées dans le corps du graphique.
- Une seule source de vérité pour la palette, les polices et les formats de nombre (module `theme.py` ou dictionnaire de style importé).
- Toujours exporter en vectoriel (SVG/PDF) quand la figure sera imprimée ou insérée dans un document.
- Nommer les fichiers de sortie de façon parlante et datée : `ca_trimestriel_nord_2026-07.svg`.
- Ne jamais coder en dur des valeurs recopiées à la main depuis un résultat : recalculer dans le code, sinon la figure divergera de la donnée à la première mise à jour.

## 10. Checklist avant livraison

Passer chaque figure au crible :

- [ ] Le titre énonce la conclusion et elle est vraie
- [ ] Axes libellés, unités présentes, format de nombre lisible
- [ ] Barres ancrées à zéro ; toute troncature d'axe est signalée
- [ ] Catégories triées de façon intentionnelle
- [ ] Palette accessible, ≤ 7 couleurs, pas d'arc-en-ciel, sens de la couleur cohérent
- [ ] Pas de double axe Y, pas de 3D
- [ ] Source, date d'extraction, périmètre et n indiqués
- [ ] Périodes incomplètes et données estimées identifiées visuellement
- [ ] Les totaux se recoupent avec la source
- [ ] Lisible en niveaux de gris et en petite taille
- [ ] Un lecteur qui n'a pas fait l'analyse comprend le message en 10 secondes

## Corriger une visualisation existante

Quand on demande une critique de graphique : lire d'abord ce que le graphique **prétend** montrer, puis vérifier dans l'ordre — (1) le message est-il soutenu par la donnée, (2) l'encodage est-il honnête (zéro, échelles, aires), (3) la forme est-elle adaptée à la tâche, (4) est-ce lisible. Proposer ensuite une version corrigée, pas seulement une liste de reproches. Toujours indiquer laquelle des corrections change la conclusion, si c'est le cas — c'est la seule qui compte vraiment.
