# Version 2 — Restaurant Albert (fiches, devis, bons pour facturation, connecteur ChatGPT).
# Construire depuis le dossier v2 :  docker build -t albert-v2 v2

FROM node:20-alpine AS site
WORKDIR /site
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production FRONTEND_DIST=/app/site
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=site /site/dist /app/site
EXPOSE 8000
# Les migrations passent avant le démarrage ; un seul processus (connecteur ChatGPT et limitation des tentatives en mémoire).
CMD ["sh", "-c", "alembic upgrade head && uvicorn albert.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
