# --- Frontend build stage ---
FROM node:20-alpine AS fe
WORKDIR /fe
COPY app/frontend/package.json app/frontend/package-lock.json* ./
RUN npm ci || npm install
COPY app/frontend/ ./
RUN npm run build

# --- Backend runtime stage ---
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Copy backend
COPY app/backend /app/backend

# Copy built frontend into expected path
COPY --from=fe /fe/dist /app/frontend/dist

# Install backend deps
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
