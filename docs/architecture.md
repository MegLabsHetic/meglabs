# Architecture

Cette page explique **pourquoi** le code est structuré comme il l'est. Pour le *quoi*, le code est
plus à jour que n'importe quelle documentation.

## La règle qui tient tout le reste

> `services/` est la seule source de vérité métier.

Les routes HTTP et le serveur MCP sont des couches fines qui appellent `services/`. Elles valident
les entrées, appellent un service, mettent en forme la sortie. Rien d'autre.

Ce n'est pas de la propreté gratuite. Notre argument de vente, c'est que le moteur fonctionne avec
ou sans notre interface. Ça ne tient que si les deux canaux partagent réellement le même code : dès
qu'une règle métier vit dans une route, le serveur MCP ne l'applique plus, et la promesse devient
fausse. De la logique dans une route est donc un bug, pas un raccourci.

## Les agents

| Agent | Ce qu'il fait |
|---|---|
| Orchestrateur | Classe l'intention, se souvient des échanges précédents, distribue le travail |
| Data | Profile, nettoie, calcule, détecte les données personnelles et les insights |
| Analyste | Traduit une question en SQL, l'exécute, se corrige en cas d'échec |
| ML | Prépare les variables, entraîne, évalue, simule |
| Viz | Produit des spécifications de graphiques |
| Rédacteur | Écrit en français ce que les autres ont calculé |

### L'Agent Data n'appelle jamais de modèle de langage

C'est probablement notre décision la plus structurante. Profilage, statistiques, nettoyage,
détection PII, détection d'anomalies : tout est du Python.

Deux raisons. La première est le coût et la latence : profiler quinze colonnes prend quelques
millisecondes et coûte zéro. Le faire faire par un modèle coûterait un appel et serait moins fiable
— un modèle de langage n'aura jamais compté les valeurs manquantes, il les aura estimées.

La seconde est plus intéressante : **le calcul n'a pas besoin des données, donc les données ne
sortent pas.** C'est ce qui rend la souveraineté tenable plutôt que déclarative.

Le modèle n'intervient qu'en aval, pour formuler un résultat déjà calculé.

## Ce qui atteint le modèle

Jamais les données brutes. On construit une représentation compressée, et c'est la seule chose qui
part :

- le nom et le type de chaque colonne
- **trois** valeurs d'exemple par colonne, échappées et coupées à 80 caractères
- des agrégats calculés côté Python
- pour interpréter un résultat SQL : les vingt premières lignes et des agrégats

Sur `collaborateurs.csv`, ça fait 5 494 caractères contre 36 475 octets de fichier. Et si le fichier
a été pseudonymisé, ce sont les valeurs masquées qui partent.

Tout passe par `profiling_service.llm_context()`. Un seul point de passage, donc un seul endroit à
relire pour savoir ce qui sort.

## Plusieurs fournisseurs de modèles

Le sujet prévoyait un fournisseur unique. On en supporte trois : Anthropic, OpenAI et Groq.

Ça nous permet de router chaque tâche vers le meilleur rapport intelligence/coût, et de ne pas
dépendre de la disponibilité d'un seul. Ça nous a aussi permis de développer gratuitement sur le
palier libre de Groq avant d'avoir des crédits ailleurs.

Le prix à payer : une couche d'adaptation, et le fait que les fonctionnalités propres à un
fournisseur doivent soit exister dans l'interface commune, soit se dégrader proprement.

Le routage tâche → modèle est déclaratif dans `core/config.py`. Un agent ne choisit jamais son
modèle lui-même — sinon l'arbitrage coût/latence devient impossible à relire.

⚠️ **Les identifiants de modèles du sujet étaient périmés.** `llama-3.3-70b-versatile` est déprécié
chez Groq depuis juin 2026 ; OpenAI est passé à la famille GPT-5.6. On a vérifié les identifiants et
les tarifs à la source. **Il faudra les revérifier avant la soutenance** : un tarif périmé fausse le
compteur de coût, qu'on montre au jury.

## La base de données

SQLite, via SQLAlchemy en asynchrone. Zéro service à provisionner, la démo tourne sur un portable.

Le passage à PostgreSQL est prévu et ne doit coûter qu'un changement d'URL. Concrètement : aucun
`PRAGMA`, aucune fonction propre à SQLite, aucun type non portable. Un test vérifie qu'aucune
colonne n'utilise un type spécifique à un dialecte — c'est le genre de règle qui ne survit pas à
trois mois sans garde-fou automatique.

## Le SQL généré

Les requêtes analytiques tournent sur DuckDB, en lecture seule. Tout SQL produit par un modèle passe
par `sql_guard` avant exécution : analyse syntaxique, rejet de tout ce qui n'est pas `SELECT` ou
`WITH`, interdiction des fonctions de lecture de fichiers, des `PRAGMA` et de `ATTACH`.

On valide par liste blanche, pas par liste noire. Une liste noire se contourne toujours ; on ne veut
pas découvrir laquelle le jour de la soutenance.

## La machine à remonter le temps

Le fichier d'origine est immuable. L'état courant, c'est l'original plus le rejeu ordonné des
actions de nettoyage actives. Pas de photographies intermédiaires.

Un instantané par transformation multiplierait le stockage par le nombre d'actions, pour un gain nul
sur des fichiers de taille PME. Le rejeu donne en prime l'export notebook presque gratuitement :
rejouer une action et écrire son équivalent pandas, c'est le même parcours.

Ce que ça coûte : désactiver une action ancienne impose de tout recalculer derrière. Acceptable à
notre échelle. À surveiller si un rejeu dépasse trente secondes.

## Deux pièges qui nous ont coûté du temps

**Pandas détruit les colonnes d'identité.** Laissé à lui-même, il lit `+33617025658` comme un
flottant et perd le `+`, et fait perdre à un numéro de sécurité sociale son zéro initial. Après ça,
plus rien dans la colonne ne ressemble à un téléphone : la détection PII ne trouve rien et la
bannière ne s'affiche jamais, **sans qu'aucune erreur ne soit levée**. On lit donc tout en texte,
puis on ne convertit que ce qui ne perd rien.

**Un service qui lit sa configuration dans son constructeur la fige.** Les routes instancient leurs
services à l'import du module ; capturer les réglages à ce moment-là revient à les geler au
démarrage du processus, et tout changement d'environnement est ignoré en silence. La configuration
se lit à l'appel.

## Docker

Les deux services montent le code de la machine hôte et tournent en rechargement automatique.
`docker compose up --build` doit rester la commande unique pour démarrer le projet, y compris
pendant le développement — sans ça, chaque modification imposerait une reconstruction et on
cesserait tous de l'utiliser.

Ce n'est pas une configuration de production. Une image de déploiement devra copier les sources.
