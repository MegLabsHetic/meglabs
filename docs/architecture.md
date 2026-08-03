# Architecture — décisions et justifications

Ce document trace les décisions structurantes. Chaque entrée dit *quoi*, *pourquoi*, et ce qu'on
abandonne en échange.

## 1. `services/` est la seule source de vérité métier

Les routers REST (`app/api/`) et le serveur MCP (`mcp_server/`) sont des couches fines qui appellent
`services/`. Aucun des deux ne contient de logique métier.

**Pourquoi** — la double distribution (SaaS + MCP) est un argument central du produit. Elle ne tient
que si les deux canaux partagent réellement le même code : si une règle métier vit dans un router,
le serveur MCP ne l'applique pas, et la promesse « le même moteur avec ou sans notre interface »
devient fausse.

**Conséquence** — de la logique métier trouvée dans un router est un bug à corriger, pas un
raccourci acceptable.

## 2. L'Agent Data ne fait aucun appel LLM pour le calcul

Profilage, nettoyage, statistiques, détection PII et détection d'insights sont du Python pur
(pandas / scipy / regex). Le LLM n'intervient que pour *formuler* un résultat déjà calculé.

**Pourquoi** — coût et latence. Un profilage de 50 colonnes coûte 0 centime et quelques
millisecondes ; le même travail délégué à un LLM coûterait un appel par colonne et serait moins
fiable (un modèle ne compte pas les valeurs manquantes, il les estime).

**Conséquence** — c'est aussi ce qui rend la promesse de souveraineté tenable : le calcul n'a pas
besoin des données, donc les données ne partent pas.

## 3. Multi-fournisseurs LLM derrière une interface unique

`core/llm_client.py` expose une interface unique ; les implémentations Anthropic, OpenAI et Groq
vivent derrière. Le mapping tâche → modèle est déclaratif dans `core/config.py` (`MODEL_ROUTING`),
jamais en dur dans un agent.

**Pourquoi** — écart assumé par rapport à un fournisseur unique : disposer de plusieurs
fournisseurs permet de router chaque tâche vers le meilleur rapport intelligence/coût, et évite de
dépendre de la disponibilité d'un seul.

**Ce qu'on paie** — une couche d'adaptation supplémentaire, et le fait que les fonctionnalités
spécifiques à un fournisseur (prompt caching, sorties structurées) doivent être exprimées dans
l'interface commune ou dégrader proprement quand le fournisseur ne les supporte pas.

## 4. SQLite via SQLAlchemy async, sans coupler au dialecte

La base applicative est SQLite en POC, accédée via SQLAlchemy en asynchrone.

**Pourquoi** — zéro service à provisionner, la démo tourne sur un portable. Le passage à PostgreSQL
est prévu et ne doit coûter qu'un changement de `DATABASE_URL` : aucun `PRAGMA`, aucune fonction
spécifique SQLite, aucun type non portable dans les modèles.

## 5. DuckDB en lecture seule, derrière un garde-fou

Les requêtes analytiques tournent sur DuckDB in-process. Tout SQL généré passe par `sql_guard`
avant exécution : parsing avec sqlglot, rejet de tout ce qui n'est pas `SELECT`/`WITH`, interdiction
des fonctions de lecture de fichiers, des `PRAGMA` et de `ATTACH`.

**Pourquoi** — le SQL est produit par un modèle de langage à partir d'un texte utilisateur. Il faut
donc traiter chaque requête comme non fiable, et valider par liste blanche (ce qui est autorisé)
plutôt que par liste noire (ce qui est interdit) : une liste noire est toujours contournable.

## 6. Time machine du nettoyage en mode replay

L'état courant d'un fichier = fichier original immuable + rejeu ordonné des `CleaningAction`
actives. Pas de snapshots.

**Pourquoi** — un snapshot par transformation multiplie le stockage par le nombre d'actions, pour
un bénéfice nul sur des fichiers de taille PME. Le replay donne en prime l'export notebook
quasiment gratuitement : rejouer une action et en écrire l'équivalent pandas sont le même parcours
de données.

**Ce qu'on paie** — désactiver une action ancienne impose de recalculer toute la chaîne. Acceptable
à cette échelle ; à profiler si un rejeu dépasse 30 s.

## 7. Docker Compose monte les sources en bind mount

Les deux services montent le code hôte et tournent en mode rechargement automatique.

**Pourquoi** — `docker compose up --build` doit rester la commande unique pour démarrer le projet,
y compris pendant le développement. Sans bind mount, chaque modification imposerait un rebuild et
l'équipe cesserait de l'utiliser.

**Ce qu'on paie** — ce n'est pas une configuration de production. Une image de déploiement devra
copier les sources et lancer un serveur en mode production.
