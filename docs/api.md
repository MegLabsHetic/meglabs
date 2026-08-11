# API

Base : `http://localhost:8000`. La documentation interactive, toujours à jour puisqu'elle est
générée depuis le code, est sur `/docs`.

Les noms de champs sont en français, comme les données qu'ils transportent. L'interface les affiche
directement ; une traduction supplémentaire serait un endroit de plus où se tromper.

## Espaces de travail

Un espace de travail contient des fichiers et, plus tard, une conversation.

```http
POST /api/workspaces
{"nom": "Analyse RH"}
→ 201  {"id": "...", "nom": "Analyse RH", "cree_le": "..."}

GET  /api/workspaces          → la liste, du plus récent au plus ancien
GET  /api/workspaces/{id}     → un seul
```

## Déposer un fichier

```http
POST /api/workspaces/{id}/files
Content-Type: multipart/form-data
fichier: <CSV ou XLSX>
```

Une seule requête fait tout : valider, stocker, profiler, chercher les données personnelles.

```json
{
  "fichier": {
    "id": "…", "nom": "collaborateurs.csv", "format": "csv",
    "taille_octets": 36475, "statut_pii": "detectee", "score_qualite": 88.5
  },
  "profil": {
    "nb_lignes": 232, "nb_colonnes": 15, "score_qualite": 88.5,
    "doublons": {"nombre": 12, "part": 0.0517},
    "explication_qualite": [
      {"critere": "Incohérences de saisie", "impact": -9.3, "detail": "4 colonne(s)…"}
    ],
    "colonnes": [
      {
        "nom": "salaire_annuel", "type": "entier",
        "valeurs_manquantes": 17, "part_manquantes": 0.0733, "cardinalite": 144,
        "exemples": ["41500.0", "38200.0", "45900.0"],
        "statistiques": {"minimum": 24000, "maximum": 590000, "moyenne": 44821.3, …},
        "anomalies": [{"type": "valeurs_extremes", "detail": "8 valeur(s)…"}]
      }
    ]
  },
  "donnees_personnelles": [
    {"colonne": "email", "type_pii": "adresse e-mail",
     "confiance": 1.0, "exemple_masque": "email_001@masked.local"}
  ]
}
```

`statut_pii` vaut `aucune`, `detectee` ou `masquee`.

Les types de colonnes sont `identifiant`, `entier`, `décimal`, `date`, `booléen`, `catégorie` ou
`texte`. Ils décrivent la **forme** de la donnée, pas sa sensibilité — c'est la détection PII qui
s'occupe de la seconde. Une colonne d'e-mails peut très bien être typée `texte`.

## Pseudonymiser

```http
POST /api/files/{id}/pseudonymise
→ 200
{
  "fichier": {…, "statut_pii": "masquee"},
  "colonnes_pseudonymisees": ["prenom", "nom", "email", "telephone", "iban", "numero_securite_sociale"],
  "valeurs_remplacees": 944,
  "profil": {…}
}
```

⚠️ **C'est irréversible.** Le fichier sur le disque est réécrit, et seule l'empreinte de chaque
valeur d'origine est conservée — jamais la valeur. C'est suffisant pour que le même e-mail donne
toujours le même jeton, y compris d'un fichier à l'autre, mais on ne peut pas revenir en arrière.

Un second appel renvoie 400.

## Autres lectures

```http
GET /api/workspaces/{id}/files    → les fichiers de l'espace
GET /api/files/{id}               → un fichier
GET /api/files/{id}/profile       → son profil complet
GET /api/health                   → {"status": "ok"}
```

## Les erreurs

Toujours la même forme, et toujours en français :

```json
{"detail": "Ce fichier porte l'extension .xlsx mais son contenu n'en est pas un. Réenregistre-le depuis ton tableur, puis réessaie."}
```

Un message d'erreur doit dire ce qui ne va pas **et** quoi faire. « 422 Unprocessable Entity »
n'aide personne.

| Code | Quand |
|---|---|
| 400 | La demande est refusée : format, taille, contenu, action impossible |
| 404 | L'espace ou le fichier n'existe pas |
| 201 | Créé |
| 200 | Lu ou modifié |

## Les limites, appliquées côté serveur

| Limite | Valeur | Où |
|---|---|---|
| Taille d'un fichier | 100 Mo | Vérifiée **pendant** la lecture, par lots de 1 Mo |
| Nombre de lignes | 1 000 000 | Après lecture |
| Formats acceptés | `.csv`, `.xlsx`, `.xls` | Extension **et** signature binaire |

Elles sont configurables dans `.env`, mais elles vivent côté serveur : un contrôle uniquement dans
le navigateur ne protège de rien.
