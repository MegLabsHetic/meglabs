# MegLabs

MegLabs est une plateforme d'analyse de données qui se pilote en français. On charge ses fichiers,
on pose ses questions comme on les poserait à un collègue, et on obtient des analyses, des
graphiques, des prédictions et un rapport — sans écrire une ligne de SQL.

C'est un projet de fin d'année, mené à cinq sur quatre sprints d'une semaine.

## Le pitch, en une phrase

> MegLabs, c'est un moteur d'analyse — vendu soit avec son cockpit, soit en pièce détachée.

Concrètement : un seul backend, deux façons de le consommer. Une interface web pour les
utilisateurs, et un serveur MCP pour brancher le moteur dans n'importe quel client compatible. Les
deux passent par le même code métier ; il n'y a pas une ligne de logique dupliquée entre les deux.
Si ce n'était pas vrai, la promesse tomberait à la première divergence de comportement.

## Ce qui nous distingue

Cinq idées, et chaque décision technique doit en servir au moins une. C'est notre garde-fou contre
la fonctionnalité qui fait joli mais ne raconte rien.

**Souveraineté.** Aucune donnée personnelle n'atteint le modèle de langage. Ce n'est pas une
intention, c'est vérifié par un test qui prend une vraie valeur dans le fichier et s'assure qu'elle
est absente de ce qui part au modèle.

**Transparence.** Le SQL généré est affiché. Chaque action est tracée et annulable. On peut exporter
la session en notebook Python. Les outils sans code enferment leurs utilisateurs ; on préfère leur
rendre le code.

**Proactivité.** La plateforme regarde les données et pose les questions avant qu'on y pense. C'est
la réponse au vrai problème des non-techniciens : la page blanche.

**Accessibilité.** Le français est la seule compétence requise. Pas de jargon dans l'interface, pas
de syntaxe à apprendre.

**Frugalité.** Chaque analyse affiche ce qu'elle coûte, et on travaille à ce que ce soit le moins
possible. Le bon modèle pour la bonne tâche, du Python pur quand un modèle de langage n'apporte
rien, du calcul local plutôt qu'une infrastructure permanente.

## Par où commencer

| Vous êtes… | Lisez |
|---|---|
| nouveau sur le projet | [Démarrer](demarrer.md) |
| en train de coder dessus | [Conventions](conventions.md) puis [Architecture](architecture.md) |
| en train d'appeler l'API | [API](api.md) |
| en train de tester le nettoyage | [Jeux de données](jeux-de-donnees.md) |
| curieux de nos choix | [Architecture](architecture.md) et [Sécurité](securite.md) |
| en train de planifier | [Feuille de route](feuille-de-route.md) |

## Où vivent les choses

- Le code : [MegLabsHetic/meglabs](https://github.com/MegLabsHetic/meglabs)
- Les tickets : [les issues](https://github.com/MegLabsHetic/meglabs/issues), un par livrable
- L'avancement : [le board](https://github.com/orgs/MegLabsHetic/projects/1)
