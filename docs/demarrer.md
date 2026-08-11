# Démarrer

## Ce qu'il faut avoir

- Docker (c'est le chemin recommandé, tout le reste est optionnel)
- Python 3.12 si vous voulez lancer le backend sans Docker
- Node 20.9 ou plus si vous voulez lancer le front sans Docker

⚠️ **Node 18 ne suffit pas.** Next 16 exige Node 20.9 minimum. Si vous êtes en 18, le front tournera
dans Docker sans problème mais `npm run dev` échouera en local. Ça nous est arrivé, d'où l'image
`node:22` épinglée dans le Dockerfile.

## Tout lancer

```bash
git clone https://github.com/MegLabsHetic/meglabs.git
cd meglabs
cp .env.example .env
docker compose up --build
```

Et c'est tout. Le front est sur http://localhost:3000, l'API sur http://localhost:8000, et la
documentation interactive de l'API sur http://localhost:8000/docs.

Le fichier `.env` est ignoré par git et ne doit jamais y entrer. `.env.example` liste les variables
avec des valeurs factices : il sert de référence, pas de configuration.

## Les clés d'API

Le sprint 1 n'en a pas besoin. Le profilage, le nettoyage et la détection de données personnelles
sont du Python pur — c'est un choix, pas une limitation.

À partir du sprint 2, il faut au moins un fournisseur. Trois sont supportés :

```bash
LLM_PROVIDER=groq          # ou anthropic, ou openai
GROQ_API_KEY=gsk_...
```

**Groq a un palier gratuit** ([console.groq.com/keys](https://console.groq.com/keys)) et c'est ce
qu'on utilise pour développer. Anthropic et OpenAI demandent une carte. On bascule d'un fournisseur
à l'autre en changeant une seule variable : le routage tâche → modèle vit dans
`backend/app/core/config.py`.

## Sans Docker

Backend :

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # .venv\Scripts\pip sous Windows
uvicorn app.main:app --reload
```

Frontend :

```bash
cd frontend
npm ci
npm run dev
```

## Les commandes du quotidien

```bash
cd backend && pytest                             # les tests, sans clé d'API
cd backend && ruff check . && black --check .    # le lint, exactement comme en CI
cd backend && python -m data.generate_datasets   # régénérer les jeux de démonstration
cd frontend && npm run lint
```

La CI lance exactement ces commandes. Si elles passent chez vous, elles passent sur la PR — sauf
sur un point qui nous a piégés une fois : la CI appelle `pytest` directement, alors que
`python -m pytest` ajoute le dossier courant au chemin d'import. Les deux marchent maintenant, mais
c'est le genre d'écart qui fait qu'un test vert en local échoue en CI.

## Vérifier que tout tourne

```bash
curl http://localhost:8000/api/health
# {"status":"ok"}
```

Puis un dépôt de fichier de bout en bout :

```bash
WS=$(curl -s -X POST http://localhost:8000/api/workspaces \
      -H "Content-Type: application/json" -d '{"nom":"Essai"}' | jq -r .id)

curl -s -X POST "http://localhost:8000/api/workspaces/$WS/files" \
     -F "fichier=@backend/data/collaborateurs.csv" | jq '.donnees_personnelles'
```

Vous devriez voir six colonnes détectées comme personnelles.
