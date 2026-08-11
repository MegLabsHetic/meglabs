# Conventions

## Les branches

```
main  ←  dev  ←  feat/… , chore/… , fix/…
```

Personne ne commite directement sur `main` ni sur `dev`. Jamais, même pour une ligne de
configuration. Tout passe par une branche dédiée et une PR vers `dev`.

`main` ne reçoit que des merges depuis `dev`, quand un groupe de jalons est fini et testé.

### On garde toutes les branches

**Ne supprimez jamais une branche après son merge.** Pas de `--delete-branch`, pas de
`git branch -d`, pas de `git push origin --delete`.

L'arbre complet fait partie de ce qu'on rend : `git log --graph --all` doit montrer chaque branche
partir de `dev` et y revenir. Une branche supprimée, c'est une partie du travail qui disparaît du
rendu.

Pour la même raison : **pas de squash au merge.** L'historique des commits raconte comment on a
travaillé, c'est ce qu'on veut montrer.

## Les commits

Format conventionnel, en anglais :

```
feat(services): detect and pseudonymise french personal data without an llm
fix(frontend): drop the webpack config rejected by turbopack
test(data): lock the intentional flaws and the demo requirements
docs(readme): document dataset generation and the identity column trap
```

Types : `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.

**Beaucoup de petits commits.** Une branche en contient typiquement cinq à douze, jamais un seul
gros. On découpe comme on travaille vraiment : le squelette, puis chaque méthode, puis les
ajustements, puis les à-côtés découverts en chemin. Un `fix` qui retouche un commit précédent de la
même branche est normal — c'est le signe qu'on a testé.

Si deux fichiers changent pour deux raisons différentes, ça fait deux commits.

Messages sobres. Pas d'emojis.

## Les PR

Toujours vers `dev`, jamais vers `main` directement. Format :

```markdown
Closes #12

## Objet
Ce que la branche apporte, en deux ou trois phrases.

## Changements
- les modifications notables

## Comment tester
Les commandes exactes.

## Points d'attention
Ce qui est discutable, la dette assumée, les questions pour la relecture.
```

**La section « Points d'attention » est celle qui compte.** C'est là qu'on écrit ce qu'on hésite à
avouer : le seuil choisi arbitrairement, le raccourci pris, le cas non couvert. Une PR sans points
d'attention est soit triviale, soit malhonnête.

Un point de mécanique : GitHub ne ferme automatiquement les issues que sur la branche par défaut.
Comme on merge vers `dev`, il faut **fermer l'issue à la main** et mettre à jour le board.

## Le code

**Une classe par responsabilité, un module par classe.** De la POO simple : pas d'héritage sauf
nécessité évidente, pas d'interfaces abstraites, pas de décorateurs maison.

**Une méthode fait une chose et se comprend en une lecture.** Vingt lignes maximum ; au-delà, on
découpe en méthodes privées au nom explicite. Le test : est-ce que je peux expliquer cette méthode
ligne à ligne, à l'oral, sans hésiter ? Si non, elle est trop compliquée.

**Les noms disent ce qu'ils font.** Quelqu'un qui lit seulement les signatures doit comprendre le
pipeline.

**Les constructeurs sont légers.** Ils rangent la configuration, ils ne travaillent pas. Et ils ne
lisent pas les réglages — sinon ils les figent (voir [Architecture](architecture.md)).

**Les erreurs d'API sont gérées explicitement.** Jamais de `except Exception: pass`.

**Les commentaires expliquent le pourquoi**, jamais le quoi. Un commentaire qui paraphrase la ligne
en dessous est du bruit qui deviendra faux.

### Français ou anglais ?

Français pour tout ce que l'utilisateur voit : réponses, messages d'erreur, libellés, noms de
colonnes des profils. Anglais pour les commits.

Pour le code lui-même, on a mélangé : les modèles de données sont en anglais, les services et leurs
commentaires en français. Ce n'est pas idéal. Le raisonnement était que le jury lit le code en
direct pendant la soutenance, et que du français l'aide. **C'est à trancher si ça gêne** — la
conversion des noms de champs se fait de toute façon explicitement à la frontière de l'API.

## Les tests

Le nom du test dit ce qui est garanti, pas ce qui est appelé :

```python
def test_international_phone_numbers_keep_their_plus(): ...
def test_the_llm_context_never_carries_a_value_from_deep_in_the_file(): ...
def test_the_injected_salary_outliers_are_all_found(): ...
```

Quand un test protège quelque chose de subtil, on écrit pourquoi dans sa docstring. Le prochain à
le lire n'aura pas notre contexte.

Les tests unitaires tournent **sans clé d'API**. Les agents sont testés avec un modèle simulé. Ceux
qui ont besoin d'une vraie clé portent le marqueur `integration` et sont exclus de la CI.

## Ce qui doit être vrai avant de merger

- [ ] `docker compose up --build` fonctionne
- [ ] Lint vert, tests verts
- [ ] Aucune donnée brute complète transmise au modèle
- [ ] Les nouveaux appels au modèle sont comptés
- [ ] Les erreurs utilisateur sont en français et disent quoi faire
- [ ] Aucun secret dans le diff, `.env.example` à jour si nouvelle variable
- [ ] Si un prompt a changé : le benchmark a tourné et n'a pas régressé
