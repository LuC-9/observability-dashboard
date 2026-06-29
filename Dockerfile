# ── Stage 1: build the React SPA ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /fe

# Install dependencies (uses yarn.lock for reproducible builds)
COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile --silent

# Build — vite.config.ts emits to ../backend/static, i.e. /backend/static
COPY frontend/ ./
RUN yarn build

# ── Stage 2: Python runtime ──────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# Backend deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ ./

# Frontend production bundle (index.html + assets/*) — produced in stage 1
COPY --from=frontend-builder /backend/static ./static

# SQLite DB lives here at runtime — Cloud Run gives us a writable /app
RUN mkdir -p /app/data
ENV DB_PATH=/app/data/local.db
ENV PORT=7860

EXPOSE 7860

# Cloud Run injects $PORT — honour it; default to 7860 otherwise.
CMD ["sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
