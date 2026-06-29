# Dashboard Backend (FastAPI)

Thin REST API over the **gold** BigQuery tables (`gold.spans`, `gold.logs`, `gold.metrics`) —
fast reads, parameterized queries, JWT login.

## Run locally
```bash
cd dashboard/backend
python -m venv .venv && source .venv/bin/activate   # win: .venv\Scripts\activate
pip install -r requirements.txt
# ADC must be able to read the gold dataset:
gcloud auth application-default login
export CENTRAL_PROJECT=oa-apmena-observability-dv GOLD_DATASET=gold
uvicorn app.main:app --reload --port 8000
```
Docs at http://localhost:8000/docs.

## Auth
`POST /api/login {username,password}` → `{token}` (default `admin1`/`pwd1`, override via `ADMIN_USER`/`ADMIN_PASS`). Send `Authorization: Bearer <token>` on all other calls.

## Endpoints
- `GET /api/filters/projects|platforms|services`
- `GET /api/overview`, `GET /api/overview/timeseries`
- `GET /api/traces`, `GET /api/traces/{trace_id}` (full span list → tree)
- `GET /api/logs`, `GET /api/metrics`
- `GET /api/cost?group_by=service_name|model|project_id|source_platform`
- `GET /api/sessions`, `GET /api/tools`
- `GET /api/meta/last-refresh`, `POST /api/refresh/pipeline` (triggers Cloud Workflow `obs-pipeline`)

Common query params: `project`, `platform`, `service`, `time_range` (`5m|10m|30m|1h|6h|12h|1d|custom`), `start`, `end` (ISO, for `custom`).

## Metrics
Needs the gold metrics layer — run `sql/gold_metric.sql` first (verify bronze column names).

## Perms (backend service account)
- read the gold dataset (`bigquery.dataViewer` + `bigquery.jobUser` on central)
- `roles/workflows.invoker` if you use `POST /api/refresh/pipeline`
