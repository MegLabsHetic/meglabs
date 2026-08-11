# Feuille de route

Quatre sprints d'une semaine. Le suivi au ticket près est sur
[le board](https://github.com/orgs/MegLabsHetic/projects/1) ; cette page donne l'intention.

## Sprint 1 — Fondations

**Livrable : on dépose un fichier, on voit son profil et la bannière de données personnelles.**

| Ticket | État |
|---|---|
| Socle du monorepo, conteneurisation, CI | ✅ |
| Modèles de données et session asynchrone | ✅ |
| Jeux de données synthétiques reproductibles | ✅ |
| Profilage complet | ✅ |
| Détection et masquage des données personnelles | ✅ |
| Dépôt de fichiers sécurisé | ✅ |
| Front : dépôt et restitution du profil | à faire |

## Sprint 2 — Cœur IA

**Livrable : une conversation en français de bout en bout, avec les agents visibles et le coût
affiché.**

La couche modèle d'abord, avec toutes ses optimisations d'un coup — mise en cache des prompts,
routage par tâche, fusion des appels, sorties structurées, comptage des jetons et du coût. Puis la
classe mère des agents et le bus d'événements qui rend leur travail visible.

Ensuite l'Orchestrateur avec sa mémoire, l'Analyste avec son garde-fou SQL et son auto-réparation,
le Rédacteur. Et côté interface : le flux en direct, la chaîne d'agents qui s'allume, le compteur de
coût.

Le nettoyage en un clic et la machine à remonter le temps ferment le sprint.

## Sprint 3 — Analyse, apprentissage, proactivité

**Livrable : un tableau de bord vivant et un modèle qu'on peut interroger.**

Les graphiques et leur interprétation systématique. Les insights proactifs, qui posent les questions
avant l'utilisateur. Les packs métier, qui règlent le problème de la page blanche. Le pipeline
d'apprentissage complet, et surtout le simulateur : on ne vend pas la performance du modèle, on vend
son usage. Les requêtes croisées entre fichiers.

## Sprint 4 — Rapport, MCP, scène

**Livrable : la soutenance est prête.**

Le rapport en dix sections avec son score de confiance. L'export en notebook Python. Le serveur MCP,
testé avec un vrai client avant le jour J. Le benchmark chiffré — et on montrera deux ou trois
échecs, parce que la lucidité est plus crédible qu'un taux parfait.

Puis le déploiement, le scénario minute par minute, et une répétition générale.

## Ce qu'on ne fera pas

Connecteurs vers des bases externes, marque blanche, gestion multi-utilisateurs complète, deep
learning, multilingue.

Ce n'est pas un manque d'ambition : c'est ce qui permet que le reste soit fini et fiable. Une
fonctionnalité à moitié faite le jour de la soutenance vaut moins que son absence assumée.

## La règle de la semaine précédant la soutenance

**Toute fonctionnalité qui n'est pas fiable à 100 % deux jours avant sort du scénario.** On ne
démontre que ce qui marche à tous les coups. Une démonstration qui plante efface tout le reste.
