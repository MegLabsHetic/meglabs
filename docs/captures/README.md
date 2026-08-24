# Captures d'écran

Les images de ce dossier sont produites par `scripts/captures.sh`. Elles ne sont pas
retouchées : ce sont des photographies de l'application telle qu'elle tourne, sur les
jeux de données du dépôt.

## Comment les régénérer

```bash
docker compose up -d          # la pile doit tourner
./scripts/captures.sh
```

Le script démarre un backend jetable, à part de celui de la pile : les captures
partent donc toujours d'une base vierge et ne touchent pas aux données de travail.
Il dépose `collaborateurs.csv` et `transactions.csv`, parcourt l'application et
photographie chaque écran. Une capture attendue qui ne part pas fait échouer le
script — une image manquante ne doit pas passer inaperçue.

Deux jeux d'images sont produits : l'application à la racine du dossier, et le
déroulé du projet dans `projet/`.

## L'application — racine du dossier

| Fichier | Écran | Ce qu'on y voit |
|---|---|---|
| `01-accueil.png` | Landing | Logo, chiffres mesurés, les cinq étapes et les cinq piliers |
| `02-donnees.png` | Étape 1 — Données | Espace de travail, zone de dépôt, les deux fichiers et leur score |
| `03-exploration-profil.png` | Étape 2 — Exploration | Profil complet : bannière de données personnelles, score de qualité détaillé, les 15 colonnes et leurs anomalies |
| `04-colonne-detail.png` | Étape 2 — Détail | Statistiques d'une colonne et, surtout, les trois seules valeurs qui peuvent sortir du serveur |
| `05-colonnes-a-corriger.png` | Étape 2 — Filtre | Les 6 colonnes qui demandent une correction, isolées |
| `06-pseudonymise.png` | Étape 2 — Après masquage | 944 valeurs remplacées par des jetons stables ; le compteur de colonnes sensibles retombe à zéro |
| `07` à `09` | Étapes 3 à 5 | Ce qui n'est pas encore livré, annoncé comme tel plutôt que maquetté |
| `10-accueil-mobile.png` | Landing, 414 px | Le premier écran sur téléphone |
| `11-chat-agents.png` | Étape 4 — Conversation | La chaîne d'agents en cours de travail, prise au vol |
| `12-chat-reponse.png` | Étape 4 — Conversation | La réponse en français et le compteur de coût de la session |
| `13-chat-transparence.png` | Étape 4 — Tout déplié | La requête exécutée, le tableau, l'auto-réparation et le coût par appel |
| `14-chat-securite.png` | Étape 4 — Refus | Une demande de suppression, refusée avec une alternative |

Les quatre dernières demandent une clé API et de vrais appels au modèle : elles sont
produites par `scripts/captures-chat.mjs`, lancé à part. Ce script redirige les appels
du navigateur vers le service Docker plutôt que de les relayer — sans quoi la réponse
arriverait d'un bloc et le streaming, justement, ne se verrait pas. Il faut donc que
`CORS_ORIGINS` contienne `http://frontend:3000` dans le `.env` local.

## Le déroulé du projet — `projet/`

Le second jeu ne montre pas le produit mais la façon dont il a été construit. Les
pages GitHub sont photographiées déconnecté : le dépôt étant public, ces images
correspondent exactement à ce qu'un lecteur extérieur voit.

| Fichier | Ce qu'on y voit |
|---|---|
| `01-graphe-des-branches.png` | Tout l'historique en une page : une branche par lot, partant de `dev` et y revenant par revue, aucune supprimée après fusion |
| `02-depot.png` | La page d'accueil du dépôt |
| `03-historique.png` | Les commits de `dev`, par petites touches |
| `04-revues.png` | Les pull requests, toutes relues avant fusion |
| `05-integration-continue.png` | Les exécutions de la CI : lint, tests, build Docker |
| `06-backlog.png` | Les tickets, avec jalons et étiquettes |
| `07-tableau.png` | Le tableau de suivi, ticket par ticket et sprint par sprint |
| `08-documentation.png` | Le wiki, miroir de `docs/` |

## Deux détails de fabrication

Les animations d'entrée sont désactivées pendant la prise de vue (`reducedMotion`) :
belles à l'écran, elles ne donnent que du flou en photo. Le script fait défiler
chaque page avant de la photographier, sinon les sections basses — révélées au
défilement — seraient capturées vides.
