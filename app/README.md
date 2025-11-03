# FicheCuisineManager

Application complète FastAPI + React pour gérer des réservations et générer des fiches cuisine PDF.

## Stack
- Backend: FastAPI, SQLModel (SQLite), ReportLab
- Frontend: React + Vite + TailwindCSS
- Déploiement: Docker (compatible Railway)

## Lancer en local (dev)
1. Backend
```
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r app/backend/requirements.txt
uvicorn app.backend.main:app --reload --port 8080
```
2. Frontend
```
cd app/frontend
npm install
npm run dev
```

## Build frontend et servir statiquement
```
cd app/frontend
npm install
npm run build
```
Le backend sert alors `app/frontend/dist` automatiquement si présent.

## Docker
```
docker build -t fichecuisine app
docker run -p 8080:8080 --env-file app/.env.example fichecuisine
```

## Endpoints principaux
- `GET /api/reservations` (q, service_date)
- `POST /api/reservations`
- `GET /api/reservations/{id}`
- `PUT /api/reservations/{id}`
- `DELETE /api/reservations/{id}`
- `POST /api/reservations/{id}/duplicate`
- `GET /api/reservations/{id}/pdf`
- `GET /api/reservations/day/{date}/pdf`
- `GET /api/menu-items`
- `GET /api/menu-items/search?q=..&type=..`

## Variables d'environnement
- `DATABASE_URL` (SQLite par défaut)
- `RESTAURANT_NAME`
- `RESTAURANT_LOGO`

## Structure PDF
Voir `app/backend/pdf_service.py`.
