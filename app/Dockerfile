FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Copy backend
COPY ./backend /app/backend

# Install deps
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Expose port
EXPOSE 8080

# Run
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
