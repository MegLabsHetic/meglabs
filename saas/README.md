# DataAnalyst AI — SaaS (Next.js + Rust + Python)

Refonte SaaS de la plateforme DataAnalyst AI en **architecture 3 tiers**. Le prototype
Streamlit reste la source de vérité du code data/IA (dossiers `../agents` et `../utils`),
réutilisé sans duplication par le service Python.

```
┌────────────┐      ┌──────────────────────────┐      ┌───────────────────────┐
│  web       │      │  api (Rust / axum)       │      │  engine (Python)      │
│  Next.js   │────▶ │  auth JWT · espaces      │────▶ │  FastAPI, SANS état   │
│  (UI)      │ HTTP │  projets · quotas        │ HTTP │  agents Claude,       │
└────────────┘      │  file de jobs · widgets  │      │  pandas, DuckDB       │
                    └───────────┬──────────────┘      └───────────┬───────────┘
                                │ SQL                             │ SQL
                          ┌─────▼─────┐                  ┌────────▼─────────┐
                          │ Postgres  │                  │ Entrepôt DuckDB  │
                          │ métadonnée│                  │ 1 fichier/projet │
                          └───────────┘                  └──────────────────┘
```

**Le CSV n'est chargé qu'une fois.** Une source passe par une pipeline ETL
(extraction → nettoyage → typage) et devient une **table DuckDB** dans l'entrepôt du
projet. Ensuite tout se calcule en SQL : le chat traduit la question en requête, le
tableau de bord stocke la requête de chaque indicateur. Postgres ne garde que la
métadonnée (espaces, projets, sources, widgets).

**Organisation** : `espace de travail` → `projets` → `sources` + `tableau de bord`.

**Choix d'architecture** : Rust porte la couche SaaS (sécurité, concurrence, quotas,
file de jobs) ; Python garde tout le code d'analyse déjà vérifié ; l'authentification
est gérée par l'API elle-même, sans service tiers. Voir la section Roadmap pour ce qui reste.

## Prérequis

- Docker + Docker Compose (tout tourne en conteneurs)
- Node 20+ (uniquement si vous lancez le frontend hors Docker)

## Démarrage rapide

```bash
cd saas
cp .env.example .env          # renseignez AUTH_SECRET et ANTHROPIC_API_KEY
docker compose up --build     # db + engine + api + web
```

Services (les ports hôte ont été choisis pour éviter les conflits avec d'autres projets) :

| Service | URL hôte              | Rôle                                  |
|---------|-----------------------|---------------------------------------|
| web     | http://localhost:3001 | Interface Next.js                     |
| api     | http://localhost:8090 | Backend Rust (REST)                   |
| engine  | http://localhost:8000 | Service de calcul Python (interne)    |
| db      | (réseau interne)      | Postgres                              |

> L'entrepôt vit dans le volume Docker `warehouse` (un fichier `.duckdb` par projet).

> Ces ports sont configurables dans `docker-compose.yml` et `.env`.

## Authentification

Trois modes, choisis par `AUTH_MODE` :

- **`local`** (défaut) — comptes e-mail + mot de passe gérés par l'API. Aucun
  service tiers. Le mot de passe n'est jamais stocké : seule une empreinte
  **Argon2id** l'est. Le jeton est un JWT signé par votre serveur, valable 7 jours.
  `AUTH_SECRET` est **obligatoire** (32 caractères minimum) — l'API refuse de
  démarrer sans, plutôt que de signer des jetons forgeables :
  ```bash
  openssl rand -hex 32
  ```
- **`dev`** — aucune authentification, l'API accepte l'en-tête
  `x-dev-user-id: <UUID>`. Pour les tests automatisés uniquement. Définissez
  alors aussi `NEXT_PUBLIC_DEV_USER_ID`, sinon l'interface ne s'authentifiera pas.
- **`prod`** — JWT Supabase (HS256), si vous préférez déléguer l'identité.

| Méthode | Chemin                  | Description                          |
|---------|-------------------------|--------------------------------------|
| POST    | `/v1/auth/register`     | Créer un compte, renvoie un jeton    |
| POST    | `/v1/auth/login`        | Se connecter, renvoie un jeton       |
| GET     | `/v1/auth/me`           | Compte de la session courante        |
| POST    | `/v1/auth/password`     | Changer de mot de passe              |

Un e-mail inconnu et un mot de passe faux donnent **le même refus** : distinguer
les deux révélerait quelles adresses sont enregistrées.

### Mode Supabase, si vous le préférez

1. Créez un projet sur supabase.com
2. `SUPABASE_JWT_SECRET` = *Project Settings → API → JWT Secret*
3. Frontend : `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY`
4. Passez `AUTH_MODE=prod`

## Frontend en local (hors Docker)

```bash
cd web
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8090
npm install
npm run dev                        # http://localhost:3000
```

## Endpoints de l'API

| Méthode | Chemin                                  | Description                                     |
|---------|-----------------------------------------|-------------------------------------------------|
| GET     | `/health`                               | Santé du service (public)                       |
| GET     | `/v1/billing/plans`                     | Paliers d'abonnement (public)                   |
| POST    | `/v1/auth/register` · `/v1/auth/login`  | Créer un compte / se connecter (public)         |
| GET     | `/v1/auth/me`                           | Compte de la session courante                   |
| POST    | `/v1/auth/password`                     | Changer de mot de passe                         |
| GET     | `/v1/me`                                | Profil + usage + quotas                         |
| GET/POST| `/v1/workspaces`                        | Lister / créer un espace de travail             |
| PATCH/DELETE | `/v1/workspaces/:id`               | Renommer / supprimer un espace (et son contenu) |
| GET/POST| `/v1/projects`                          | Lister / créer un projet                        |
| GET/DELETE | `/v1/projects/:id`                   | Détail / suppression d'un projet                |
| POST    | `/v1/files/inspect`                     | Format d'un fichier, feuilles d'un classeur      |
| GET/POST| `/v1/projects/:id/sources`              | Sources du projet / import → pipeline ETL       |
| POST    | `/v1/sources/:id/refresh/check`         | Contrôle de structure avant mise à jour         |
| POST    | `/v1/sources/:id/refresh`               | Rechargement des données (`replace`/`append`)   |
| GET     | `/v1/projects/:id/warehouse/schema`     | Schéma de l'entrepôt                            |
| POST    | `/v1/projects/:id/warehouse/sql`        | Requête SQL libre (lecture seule)               |
| POST    | `/v1/projects/:id/chat`                 | Question en langage naturel → SQL → résultat    |
| GET/POST| `/v1/projects/:id/dashboard`            | Tableau de bord / ajout d'indicateurs           |
| POST    | `/v1/projects/:id/dashboard/propose`    | Indicateurs proposés par l'IA                   |
| POST    | `/v1/projects/:id/dashboard/chat`       | Édition du tableau de bord en langage naturel   |
| PATCH/DELETE | `/v1/widgets/:id`                  | Modifier (SQL compris) / supprimer un indicateur|
| GET     | `/v1/jobs/:id`                          | Statut / résultat d'un job                      |

## État (livré et vérifié de bout en bout)

- ✅ **Organisation** : espaces de travail → projets, création **et suppression** des deux
  (cascade SQL + suppression de l'entrepôt), avec confirmation côté UI.
- ✅ **Pipeline ETL** : CSV **ou Excel** (.xlsx, .xls) → format reconnu au contenu et non
  à l'extension → détection encodage/séparateur → nettoyage → normalisation des noms de
  colonnes en identifiants SQL (le libellé d'origine est conservé) → typage → table DuckDB.
  Un classeur multi-feuilles est inspecté avant l'import : l'utilisateur choisit sa feuille,
  chacune devenant une table. Traité en tâche de fond par la file de jobs Rust.
  **Taille maximale : 24 Mo par fichier** (32 Mo de corps de requête ; un binaire
  voyage encodé en base64, ce qui l'alourdit d'un tiers). Le fichier est tenu en
  mémoire de bout en bout — au-delà, la réponse est l'object storage avec envoi
  direct, inscrit dans la feuille de route.
- ✅ **Chat SQL** : la question devient une requête, exécutée en lecture seule sur
  l'entrepôt. Le SQL est affiché et le graphique épinglable au tableau de bord.
  Une requête refusée par DuckDB est renvoyée à l'agent pour une correction.
- ✅ **Tableau de bord persistant** : chaque indicateur stocke sa **requête**, jamais son
  résultat — le rouvrir ne coûte aucun appel IA et suit les données du moment.
  Édition en langage naturel (ajout / modification du calcul / suppression) et
  édition manuelle du SQL.
- ✅ **Mise à jour des données** : comparaison de structure avant tout chargement
  (identique / compatible avec correction proposée / incompatible expliqué), puis
  rechargement en `replace` ou `append`.
- ✅ **Authentification native** : inscription et connexion e-mail + mot de passe,
  empreinte Argon2id, jeton JWT signé par l'API, isolation des données par compte —
  18 contrôles passés (doublons, mots de passe faibles, jeton forgé, accès croisé).
- ✅ **Infra** : `docker compose` (4 services), Postgres versionné, volume `warehouse`.

## Roadmap (prochaines étapes)

1. **Object storage** (S3/MinIO) pour l'upload de gros fichiers (aujourd'hui : CSV inline).
2. **Jointures multi-tables** : l'entrepôt les supporte déjà, l'agent SQL doit apprendre à
   les proposer (dictionnaire des relations entre sources).
3. **Stripe** : brancher les webhooks sur la table `subscriptions` (paliers déjà appliqués).
4. **Clé Anthropic par tenant** : passer la clé par requête plutôt que via l'env du
   process engine — c'est aussi ce qui permettra de retirer le verrou global `_ai_lock`
   qui sérialise aujourd'hui tous les appels IA de la plateforme.
5. **Tests automatisés** (Rust `#[tokio::test]`, pytest engine) + CI.
6. **Session en cookie httpOnly** plutôt que `localStorage` : à faire à la mise en
   ligne, quand le domaine partagé entre l'API et l'interface est connu.
7. **Réinitialisation de mot de passe** par e-mail (nécessite un service d'envoi).
7. **Connecteurs API** (Jira en premier) branchés sur la même file de jobs.
