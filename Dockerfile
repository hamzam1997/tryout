# ── Stage 1: build the React app ─────────────────────────────────────────
FROM node:22-slim AS frontend

WORKDIR /build

# Copy manifests first so the dependency layer caches across code changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Stage 2: runtime ─────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Only the built assets cross over; node and the sources stay in stage 1.
COPY --from=frontend /build/dist ./frontend/dist

# Cloud Run injects PORT; default keeps local `docker run` working.
ENV PORT=8080

# One worker so attempt threads and their DB writes stay in one process. Each open live
# stream (SSE) holds a thread for up to 240s, hence more threads than CPU would suggest.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 16 app:app
