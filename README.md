# MegLabs

Plateforme SaaS d'analyse de données pilotée entièrement en français naturel, reposant sur une
architecture multi-agents IA custom.

Un utilisateur non technique charge ses fichiers, pose ses questions en français, et obtient
analyses, visualisations, prédictions ML et un rapport professionnel — sans écrire une ligne de
code ni de SQL.

> **Un backend, deux canaux :** un frontend SaaS (Next.js) et un serveur MCP (FastMCP) exposant les
> mêmes capacités, tous deux appuyés sur la même couche `services/`.

## Démarrage

```bash
cp .env.example .env      # renseigner au moins une clé de fournisseur LLM
docker compose up --build # front :3000 · back :8000 · swagger :8000/docs
```

## Commandes

```bash
cd backend && pytest                          # tests unitaires (aucune clé API requise)
cd backend && ruff check . && black --check . # lint
cd backend && python -m data.generate_datasets # régénérer les jeux de démonstration
cd frontend && npm run lint
```

## Jeux de données de démonstration

`backend/data/collaborateurs.csv` et `backend/data/transactions.csv` sont générés avec une graine
fixe : deux exécutions produisent des fichiers identiques au octet près.

**Leurs défauts sont volontaires** — valeurs manquantes, doublons, trois formats de date
concurrents, casse incohérente, salaires aberrants, montants négatifs, transactions rattachées à un
collaborateur inexistant. Ce sont eux qui donnent matière au profilage, au nettoyage et à la
détection de données personnelles. Les « corriger » viderait ces fonctionnalités de leur
démonstration ; des tests les verrouillent.

⚠️ Ces fichiers contiennent des colonnes d'identité (téléphone, IBAN, numéro de sécurité sociale)
que pandas convertit en nombres s'il est laissé à lui-même — ce qui détruit le `+` d'un numéro
international et les zéros initiaux. Tout chargement doit forcer le type texte sur ces colonnes.

## Documentation

La source est [docs/](docs/README.md), relue en PR comme le reste du code. Elle est publiée sur
[le wiki](https://github.com/MegLabsHetic/meglabs/wiki), qui se lit et se cherche mieux —
`./scripts/sync-wiki.sh` met le miroir à jour. **Modifiez `docs/`, jamais le wiki.**

| Page | Pour |
|---|---|
| [Démarrer](docs/demarrer.md) | installer, lancer, vérifier |
| [Architecture](docs/architecture.md) | pourquoi le code est structuré ainsi |
| [Conventions](docs/conventions.md) | branches, commits, PR, style |
| [API](docs/api.md) | les routes et leurs contrats |
| [Jeux de données](docs/jeux-de-donnees.md) | les fichiers de démo et leurs défauts volontaires |
| [Sécurité](docs/securite.md) | ce qu'on protège et comment |
| [Feuille de route](docs/feuille-de-route.md) | les quatre sprints |
