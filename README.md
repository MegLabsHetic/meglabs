# DataVox

**Déposez un fichier, posez vos questions en français, en anglais ou en arabe.**
Vous obtenez le chiffre, le graphique, et **la requête SQL qui l'a produit**.

Le principe fondateur : le modèle n'écrit jamais un chiffre, il écrit la *recette*.
C'est l'entrepôt de données qui calcule. Aucun chiffre inventé, et chaque
indicateur reste auditable — la requête est affichée sous le graphique.

> ✅ **Voici le projet fini.**
>
> **Propriété & licence** — Wassim Megrad reste seul propriétaire de cette
> solution. Elle est fournie en l'état pour usage et évaluation ; **aucune
> autorisation de revente, de redistribution commerciale ou de cession n'est
> accordée** sans son accord écrit préalable. Tous droits réservés.

---

## Ce que fait la plateforme

| | |
|---|---|
| **Pipeline ETL** | Un CSV déposé est analysé (encodage, séparateur), nettoyé, ses colonnes normalisées en identifiants SQL, ses types déduits, puis chargé dans un entrepôt DuckDB propre au projet. Les intitulés d'origine sont conservés, y compris en écriture arabe. |
| **Assistant conversationnel** | La question devient une requête SQL exécutée en lecture seule. La réponse arrive dans la langue de la question, avec le graphique et le SQL. |
| **Tableau de bord vivant** | Chaque indicateur stocke sa **requête**, jamais son résultat : le rouvrir ne coûte aucun appel au moteur et suit les données du moment. |
| **Édition en langage naturel** | « Ajoute le panier moyen par pays », « le chiffre d'affaires doit exclure les annulations » — l'indicateur est créé ou recalculé immédiatement. Le SQL reste modifiable à la main. |
| **Mise à jour des données** | La structure du nouveau fichier est comparée à l'existante : identique, compatible (renommage détecté et proposé), ou incompatible — auquel cas on l'explique au lieu de tout casser. |
| **Organisation** | Espaces de travail → projets → sources + tableau de bord. |

## Architecture

```
web (Next.js)  ──HTTP──▶  api (Rust/axum)  ──HTTP──▶  engine (Python/FastAPI)
                                │                            │
                                ▼ SQL                        ▼ SQL
                          PostgreSQL                  Entrepôt DuckDB
                          (métadonnée)                (1 fichier / projet)
```

- **`saas/web`** — interface Next.js 15 / React 19 / Tailwind / Recharts
- **`saas/api`** — Rust (axum, sqlx) : authentification, espaces, projets, quotas, file de jobs
- **`saas/engine`** — Python (FastAPI, pandas, DuckDB) : ETL, exécution SQL, agents
- **`agents/`, `utils/`** — code d'analyse partagé, réutilisé sans duplication par l'engine
- **`app.py`** — prototype Streamlit d'origine, conservé comme référence

Détail complet : [`saas/ARCHITECTURE.md`](saas/ARCHITECTURE.md).

## Démarrage

```bash
cd saas
cp .env.example .env      # renseignez ANTHROPIC_API_KEY
docker compose up --build
```

| Service | URL |
|---------|-----|
| Interface | http://localhost:3001 |
| API | http://localhost:8090 |
| Engine | http://localhost:8000 |

`AUTH_MODE=dev` par défaut : aucun compte à créer, l'interface s'authentifie
avec un UUID de développement. Voir [`saas/README.md`](saas/README.md) pour le
mode production (Supabase), la liste des endpoints et la feuille de route.

> **Secrets** : les fichiers `.env` ne sont pas versionnés. N'y placez jamais de
> clé dans un `.env.example`.
