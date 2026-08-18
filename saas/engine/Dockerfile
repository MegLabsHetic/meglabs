# Contexte de build = racine du projet (voir docker-compose.yml).
# On réutilise agents/, utils/ et config.py existants sans duplication.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/srv

WORKDIR /srv

# Polices pour les rapports PDF. DejaVu couvre le latin ; Noto Arabic est
# indispensable pour les rapports en arabe, sinon le texte sort en carres.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

COPY saas/engine/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Code métier vérifié, réutilisé tel quel
COPY config.py ./config.py
COPY agents ./agents
COPY utils ./utils
# Service FastAPI
COPY saas/engine/app ./enginesvc

# Smoke-test d'import à la construction : échoue vite si une dépendance manque
RUN python -c "import enginesvc.main; print('engine import OK')"

EXPOSE 8000
CMD ["uvicorn", "enginesvc.main:app", "--host", "0.0.0.0", "--port", "8000"]
