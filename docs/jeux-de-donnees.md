# Jeux de données

Deux fichiers, dans `backend/data/` :

| Fichier | Lignes | Ce qu'il contient |
|---|---|---|
| `collaborateurs.csv` | 232 | Un effectif : identité, service, poste, ancienneté, salaire, absences, performance, départ |
| `transactions.csv` | 3 012 | Des ventes rattachées à un collaborateur : date, client, catégorie, montant, statut |

Ils sont générés avec une graine fixe. **Deux exécutions produisent des fichiers identiques au octet
près** — on l'a vérifié par empreinte, et un test le garantit. Sans ça, aucun résultat de démo ne
serait rejouable.

```bash
cd backend && python -m data.generate_datasets
```

## ⚠️ Leurs défauts sont volontaires

**Ne les corrigez pas.** Ce sont eux qui donnent matière au profilage, au nettoyage et à la
détection de données personnelles. Un jeu propre ne prouverait rien.

Quinze tests les verrouillent. Si vous « améliorez » les données, la suite passe au rouge — c'est
fait exprès.

| Défaut | Combien | Ce qu'il sert à démontrer |
|---|---|---|
| Valeurs manquantes | ~8 % sur trois colonnes | Imputation, score de qualité |
| Doublons exacts | 12 lignes | Déduplication |
| Formats de date concurrents | 3 écritures | Unification au nettoyage |
| Casse et espaces incohérents | `service` remonte à 18 modalités pour 5 réelles | Regroupement de modalités |
| Salaires multipliés par dix | 8 valeurs | Détection de valeurs aberrantes |
| Montants négatifs | 8 valeurs | Anomalies métier |
| Transactions orphelines | 15 lignes vers `C9999`, inexistant | Qualité de jointure |

Le détail parlant : le profileur retrouve **exactement les huit salaires aberrants**, sans rien
savoir du générateur. C'est ce qu'on montrera.

## Ce que les démos y trouvent

**Une clé de jointure.** `id_collaborateur` relie les deux fichiers. C'est ce qui permet la question
croisée : « Quel est le CA généré par les consultants du service Data ? »

**Des colonnes personnelles réalistes.** E-mail, téléphone en format national **et** international,
IBAN, numéro de sécurité sociale, prénoms et noms. La détection en repère six sur quinze colonnes,
sans faux positif.

**Un vrai signal pour le modèle.** Le départ est corrélé à une faible ancienneté. Sans ça, le
modèle de risque de départ n'aurait rien à apprendre et la démonstration serait creuse.

## ⚠️ Le piège des colonnes d'identité

Lu sans précaution, pandas transforme `+33617025658` en flottant `33617025658.0` et fait perdre à un
numéro de sécurité sociale son zéro initial.

Ce n'est pas anodin : après cette conversion, **plus rien dans la colonne ne ressemble à un
téléphone**. La détection de données personnelles ne trouve rien, la bannière ne s'affiche jamais,
et aucune erreur n'est levée. On a failli ne le découvrir qu'à la démonstration.

`FileLoader` s'en charge : il lit tout en texte, puis ne convertit en nombre que ce qui ne perd
rien. Si vous lisez ces fichiers directement dans un script, forcez le type :

```python
pd.read_csv("collaborateurs.csv", dtype={
    "telephone": str, "iban": str, "numero_securite_sociale": str, "id_collaborateur": str,
})
```

Ou passez par `FileLoader`, qui gère aussi la détection du séparateur.

## Régler le curseur

`GenerationConfig` porte les proportions : part de valeurs manquantes, nombre de doublons, nombre de
valeurs aberrantes, part de dates mal formatées.

Les huit valeurs aberrantes sur 220 lignes (~3,6 %) sont un compromis : assez pour être détectées,
assez peu pour ne pas déformer les moyennes au point de rendre les autres analyses absurdes. Si la
détection d'anomalies s'avère trop facile, c'est le premier curseur à bouger.

**Changer la graine change tout.** Les tests qui vérifient des nombres exacts échoueront. C'est
voulu : ces valeurs sont des repères de démonstration.
