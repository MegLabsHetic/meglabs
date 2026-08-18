#!/usr/bin/env bash
# Produit les captures d'écran de l'application dans docs/captures/.
#
# Playwright tourne dans son image officielle : elle embarque les navigateurs, et
# le projet ne gagne aucune dépendance. L'application est jointe par le réseau
# Docker de la pile, donc sous ses noms de service.
#
# Prérequis : la pile doit tourner (`docker compose up -d`).
set -euo pipefail

# Sous Git Bash, les chemins absolus des arguments seraient réécrits en chemins
# Windows avant d'atteindre Docker, qui les refuse. Cette variable le désactive.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

DEPOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# --env-file est lu par le client Docker sur l'hôte, pas dans le conteneur : sous
# Git Bash il lui faut donc un chemin Windows, que la désactivation de conversion
# ci-dessus ne produit plus.
DEPOT_HOTE="$DEPOT"
if command -v cygpath >/dev/null 2>&1; then DEPOT_HOTE="$(cygpath -w "$DEPOT")"; fi
RESEAU="${RESEAU:-megslab_default}"
IMAGE="mcr.microsoft.com/playwright:v1.56.0-noble"

if ! docker network inspect "$RESEAU" >/dev/null 2>&1; then
  echo "Réseau « $RESEAU » introuvable. Démarrez la pile : docker compose up -d" >&2
  echo "Ou indiquez le bon nom : RESEAU=<nom> $0" >&2
  exit 1
fi

mkdir -p "$DEPOT/docs/captures"

# Les captures tournent contre un backend jetable, pas contre celui de la pile :
# elles partent donc toujours d'une base vierge, et n'ajoutent ni n'effacent rien
# dans les données de travail. Sa base et son stockage vivent en mémoire.
API_TEMPORAIRE="meglabs-captures-api"
docker rm -f "$API_TEMPORAIRE" >/dev/null 2>&1 || true
nettoyer() { docker rm -f "$API_TEMPORAIRE" >/dev/null 2>&1 || true; }
trap nettoyer EXIT

docker run -d --rm --name "$API_TEMPORAIRE" \
  --network "$RESEAU" \
  --env-file "$DEPOT_HOTE/.env" \
  -e DATABASE_URL=sqlite+aiosqlite:////scene/captures.db \
  -e STORAGE_DIR=/scene/storage \
  --tmpfs /scene \
  megslab-backend \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 >/dev/null

echo "Attente du backend de capture…"
for essai in $(seq 1 40); do
  if docker exec "$API_TEMPORAIRE" \
      python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/openapi.json')" \
      >/dev/null 2>&1; then
    break
  fi
  if [ "$essai" -eq 40 ]; then
    echo "Le backend de capture n'a pas démarré." >&2
    docker logs "$API_TEMPORAIRE" >&2
    exit 1
  fi
  sleep 1
done

# L'image embarque les navigateurs mais pas le paquet npm. On l'installe dans un
# dossier temporaire du conteneur, en sautant le téléchargement des navigateurs :
# ils sont déjà là, et à la bonne version.
docker run --rm \
  --network "$RESEAU" \
  -v "$DEPOT/scripts:/scripts:ro" \
  -v "$DEPOT/backend/data:/donnees:ro" \
  -v "$DEPOT/docs/captures:/captures" \
  -e PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
  -e API="http://$API_TEMPORAIRE:8000" \
  -w /work \
  "$IMAGE" \
  sh -c "mkdir -p /work && cd /work \
    && npm install --silent --no-fund --no-audit playwright@1.56.0 >/dev/null 2>&1 \
    && cp /scripts/captures.mjs . \
    && node captures.mjs"

echo "Captures écrites dans docs/captures/"
