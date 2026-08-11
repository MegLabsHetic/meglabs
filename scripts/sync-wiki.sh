#!/usr/bin/env bash
# Publie docs/ vers le wiki GitHub.
#
# Le depot est la source : la documentation y est relue en PR comme du code. Le wiki
# n'en est que la vitrine, parce qu'il se lit mieux et se cherche mieux. Toute
# modification faite directement dans le wiki sera ecrasee au prochain passage.
#
# Usage : ./scripts/sync-wiki.sh
set -euo pipefail

DEPOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WIKI="$(mktemp -d)"
trap 'rm -rf "$WIKI"' EXIT

git clone --quiet https://github.com/MegLabsHetic/meglabs.wiki.git "$WIKI"

# Les noms de fichiers du depot sont sans accent (portabilite), ceux du wiki les
# portent parce qu'ils deviennent des titres de page.
copier() {
  local source="$DEPOT/docs/$1" cible="$WIKI/$2"
  sed \
    -e 's|(demarrer\.md)|(Démarrer)|g' \
    -e 's|(architecture\.md)|(Architecture)|g' \
    -e 's|(conventions\.md)|(Conventions)|g' \
    -e 's|(api\.md)|(API)|g' \
    -e 's|(jeux-de-donnees\.md)|(Jeux-de-données)|g' \
    -e 's|(securite\.md)|(Sécurité)|g' \
    -e 's|(feuille-de-route\.md)|(Feuille-de-route)|g' \
    -e 's|(README\.md)|(Home)|g' \
    "$source" > "$cible"
  printf '\n---\n\n> Miroir de `docs/` dans le dépôt. Modifiez le dépôt, pas le wiki.\n' >> "$cible"
}

copier README.md          Home.md
copier demarrer.md        "Démarrer.md"
copier architecture.md    Architecture.md
copier conventions.md     Conventions.md
copier api.md             API.md
copier jeux-de-donnees.md "Jeux-de-données.md"
copier securite.md        "Sécurité.md"
copier feuille-de-route.md Feuille-de-route.md

cd "$WIKI"
if git diff --quiet; then
  echo "Le wiki est deja a jour."
  exit 0
fi

git add -A
git commit --quiet -m "Synchronisation depuis docs/"
git push --quiet origin master
echo "Wiki mis a jour : https://github.com/MegLabsHetic/meglabs/wiki"
