# PRD — Central GenAI Observability Dashboard

## Original Problem Statement
Clone https://github.com/LuC-9/observability-dashboard. The repo contains two implementations under `obswebapp-feature-newDataset/`:

1. `dashboard/` — full React + AntD + ECharts frontend with rich charts, plus a FastAPI backend that queries BigQuery.
2. `obswebapp-feature-newDataset/` — alternate FastAPI backend with SQLite "local" mode, seed data, and a `wide_*` star-schema.

Goal: **keep the `dashboard/` frontend (with all its charts) and use the database/seeding implementation from the second folder**.

## Architecture (as built — 2026-06-29)
- **Frontend** (`/app/frontend`): copy of `dashboard/frontend` — Vite + React 18 + TypeScript + AntD 5 + ECharts. `yarn start` → `vite --host 0.0.0.0 --port 3000`. Uses relative `/api` URLs proxied through Kubernetes ingress to backend port 8001.
- **Backend** (`/app/backend/server.py`): FastAPI app, ~850 lines. Uses **SQLite** at `/app/backend/data/local.db` with the `wide_*` schema from `obswebapp/seed_data.py`. Re-exposes the API contract the dashboard frontend expects:
  - Auth: `POST /api/login` (JWT, 24h), `GET /api/auth/iap` (401 stub), `GET /api/config`.
  - Filters: `/api/filters/{projects,platforms,services}`.
  - Overview: `/api/overview`, `/api/overview/timeseries`, `/api/latency/timeseries`.
  - Traces/Logs: `/api/traces`, `/api/traces/{id}`, `/api/logs`.
  - Metrics: `/api/metrics/{catalog,summary,timeseries}`, `/api/metrics`.
  - Cost & Sessions: `/api/cost`, `/api/sessions`, `/api/sessions/{id}`.
  - Insights: `/api/tools`, `/api/search`, `/api/top/traces`, `/api/models`, `/api/errors/by-service`, `/api/errors/top`.
  - Health & Meta: `/api/health` (public), `/api/health/services` (auth), `/api/meta/last-refresh`.
  - Pricing CRUD: `/api/config/pricing` GET/POST/PATCH.
  - Refresh: `/api/refresh/pipeline` POST + `/api/refresh/status` GET (mocked SUCCEEDED).
- **DB bootstrap**: on first start, `bootstrap_db()` creates 17 `wide_*` tables and seeds ~2000 rows spanning the last 30 days using the original `seed_data.gen_*` generators. Idempotent — skips if `wide_spans_detail` is non-empty.
- **Auth**: HS256 JWT, default credentials `admin1 / pwd1` (overridable via `ADMIN_USER`/`ADMIN_PASS` env). All `/api/*` endpoints except `/api/login`, `/api/config`, `/api/auth/iap`, `/api/health` require a Bearer token.

## What's implemented (2026-06-29)
- Full dashboard UI from the `dashboard/` folder rendering all 10 tabs (Overview, Traces, Logs, Metrics, LLM Cost, Sessions, Tool Calls, Insights, Health, Compare) with charts from ECharts.
- SQLite-backed implementation of every endpoint the frontend calls, mapped onto the `wide_*` star schema (cost & token data from `wide_llm_interactions_detail`, spans from `wide_spans_detail`, etc.).
- 30 days of seed data on first boot.
- JWT auth, Google SSO button auto-hidden when no `GOOGLE_CLIENT_ID` configured.
- Pricing config CRUD with active/inactive versioning.
- Refresh pipeline mocked (no Cloud Workflows in this env).
- 37/37 backend pytest tests pass; all 10 frontend tabs verified by the testing agent.

## Personas
- **Platform engineer** monitoring agent latency, error rates, and cost across services & projects.
- **GenAI app developer** drilling into traces, spans, prompts, and tool calls to debug a session.
- **FinOps owner** tracking LLM cost by model / service / project and trending it over time.

## Tech stack
- React 18 + TS + Vite + AntD 5 + ECharts (frontend)
- FastAPI + SQLite + PyJWT + python-dotenv (backend)
- Yarn (frontend deps), pip (backend deps)

## Backlog
- P1: Real ETL — wire bootstrap to ingest from OTLP / Cloud Storage / BigQuery instead of seed generators.
- P1: Persist pricing edits to a real source-of-truth (currently SQLite).
- P2: Split `server.py` into per-domain routers (`metrics`, `traces`, `cost`, `pricing`, etc.) — file is ~850 lines.
- P2: SQLite connection pool / WAL mode for higher concurrency.
- P2: Validate `pid` exists in `PATCH /api/config/pricing/{pid}` (currently silently no-ops on bad id).
- P3: Google OAuth real flow (currently only the button hides when client_id is empty).
- P3: Compare tab — confirm it renders meaningfully with non-empty datasets.
