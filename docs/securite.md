# Sécurité

Deux choses à protéger : les données de l'utilisateur, et le serveur qui les traite.

## Les fichiers déposés

Un fichier arrive d'un utilisateur. Rien de ce qu'il annonce n'est cru sur parole : ni son
extension, ni son type déclaré, ni son nom.

**L'extension est vérifiée** contre une liste fermée : `.csv`, `.xlsx`, `.xls`.

**Le contenu est vérifié aussi.** Un `.xlsx` est une archive ZIP, un `.xls` un conteneur OLE : les
premiers octets doivent le confirmer. Un fichier texte renommé en `.xlsx` est refusé. Le CSV n'a pas
de signature — il est validé en le lisant vraiment.

**Le nom fourni n'atteint jamais le disque.** Le fichier est écrit sous un identifiant aléatoire.
C'est ce qui rend la traversée de chemin impossible : il n'y a rien à filtrer, puisque rien de ce
que l'utilisateur écrit ne devient un chemin. Un dépôt nommé `../../evasion.csv` est testé, et
atterrit sous un UUID comme les autres.

**La taille est vérifiée pendant la lecture**, par lots d'un mégaoctet. Un fichier de dix gigaoctets
est refusé avant d'avoir été chargé en mémoire. Vérifier après aurait suffi à faire tomber le
serveur.

## Les données personnelles

La détection cherche les e-mails, les téléphones français (national et international), les IBAN, les
numéros de sécurité sociale, et les colonnes de noms de personnes.

**Aucun modèle de langage n'intervient.** C'est le point : un service qui enverrait les colonnes à
un modèle pour lui demander si elles sont sensibles aurait déjà divulgué ce qu'il cherchait à
protéger.

La pseudonymisation remplace chaque valeur par un jeton stable — la même valeur donne toujours le
même jeton, y compris entre deux fichiers.

⚠️ **Elle est à sens unique, et c'est volontaire.** Seule l'empreinte SHA-256 est conservée, jamais
la valeur. On ne peut pas reconstituer le fichier d'origine depuis la base. C'est une propriété de
confidentialité plus forte, mais c'est définitif : si l'équipe veut pouvoir démasquer, il faut le
décider avant que des fichiers ne soient traités.

La table des correspondances n'est exposée par aucune route, sous aucune forme.

## Ce qui part au modèle

Jamais les données brutes. Une représentation compressée est construite en un seul endroit
(`profiling_service.llm_context`) : noms et types de colonnes, trois valeurs d'exemple échappées et
coupées à 80 caractères, agrégats calculés côté Python.

Si le fichier a été pseudonymisé, ce sont les valeurs masquées qui partent.

Un test prend une valeur réelle en centième ligne du fichier et vérifie qu'elle est absente de ce
qui est transmis. La garantie est vérifiée, pas affirmée.

## Le SQL généré

Le SQL est produit par un modèle de langage à partir d'un texte écrit par un utilisateur. Il est
donc traité comme non fiable de bout en bout.

Chaque requête est analysée avant exécution. Tout ce qui n'est pas `SELECT` ou `WITH` est rejeté,
ainsi que les fonctions de lecture de fichiers, les `PRAGMA` et `ATTACH`. La base est ouverte en
lecture seule, avec un délai maximal.

**On valide par liste blanche.** Une liste noire se contourne toujours, et on ne veut pas découvrir
laquelle pendant la démonstration. Le refus est formulé en français, avec une alternative proposée —
c'est une des démonstrations prévues : demander « supprime toutes les lignes » et montrer le refus.

## L'injection par les données

Le contenu des cellules n'est jamais interprété comme une instruction. De toute façon il n'est
quasiment jamais transmis, et les valeurs d'exemple qui le sont sont échappées et bornées.

## Les secrets

Uniquement dans `.env`, qui est ignoré par git depuis le tout premier commit — l'ordre compte, un
secret commité reste dans l'historique même après suppression.

`.env.example` liste les variables avec des valeurs factices. Aucune clé n'apparaît jamais dans les
logs, même tronquée. Le front n'appelle jamais un fournisseur de modèles directement : tout passe
par le serveur, qui seul détient les clés.

Avant chaque commit, regardez `git diff --staged` et cherchez ce qui ressemble à un secret. En cas
de doute, ne commitez pas.

## Ce qui reste à faire

- Limitation du débit par IP sur le chat, pour éviter qu'une démonstration publique n'épuise le
  budget d'API
- Journalisation des refus de `sql_guard`, pour pouvoir montrer qu'ils ont eu lieu
