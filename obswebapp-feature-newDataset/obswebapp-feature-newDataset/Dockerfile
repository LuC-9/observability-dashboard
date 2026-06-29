# ── Stage 1: build React app ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ──────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-builder /backend/static ./static

ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]

# gcloud builds submit --tag gcr.io/oa-apmena-techsandbox-ap-dv/otel-dashboard

# https://otel-dashboard-786386076156.us-central1.run.app
