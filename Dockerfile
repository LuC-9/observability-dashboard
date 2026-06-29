# ── Stage 1: build the React SPA ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /fe
COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile --silent
COPY frontend/ ./
RUN yarn build   # vite.config.ts writes to ../backend/static → /backend/static

# ── Stage 2: Python runtime ──────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /backend/static ./backend/static

# Writable spot for SQLite when APP_ENV=local (Cloud Run gives us /app rw)
RUN mkdir -p /app/data
ENV DB_PATH=/app/data/local.db
ENV PORT=7860

# All other config (APP_ENV, GCP_PROJECT, BQ_DATASET, GOOGLE_CLIENT_ID,
# ALLOWED_DOMAIN, JWT_SECRET, ADMIN_USER, ADMIN_PASS) is injected at deploy
# time via Cloud Run `--set-env-vars` / `--set-secrets`. We deliberately do
# NOT COPY .env so the image is environment-agnostic.

WORKDIR /app/backend
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
