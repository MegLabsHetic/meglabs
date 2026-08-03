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

## Documentation

- `docs/architecture.md` — décisions techniques
- `docs/demo_scenario.md` — déroulé de la soutenance
