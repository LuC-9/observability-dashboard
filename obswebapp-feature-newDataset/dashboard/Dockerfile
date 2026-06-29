# --- build the frontend ---
FROM node:20-slim AS fe
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- backend + static frontend in one image ---
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=fe /fe/dist ./static
ENV CENTRAL_PROJECT=oa-apmena-observability-dv \
    GOLD_DATASET=gold \
    STATIC_DIR=/app/static
# Cloud Run sets $PORT
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
