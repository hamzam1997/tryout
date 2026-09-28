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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Only the built assets cross over; node and the sources stay in stage 1.
COPY --from=frontend /build/dist ./frontend/dist

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app
