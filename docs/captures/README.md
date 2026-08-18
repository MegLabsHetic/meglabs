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

## Ce que montre chaque image

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

## Deux détails de fabrication

Les animations d'entrée sont désactivées pendant la prise de vue (`reducedMotion`) :
belles à l'écran, elles ne donnent que du flou en photo. Le script fait défiler
chaque page avant de la photographier, sinon les sections basses — révélées au
défilement — seraient capturées vides.
