# Central Observability Dashboard — PRD

## Problem Statement
Clone github.com/LuC-9/observability-dashboard. Use the `dashboard/` frontend
(React + Vite + AntD + ECharts) and the `obswebapp-feature-newDataset/` backend
data implementation (SQLite + wide_* seeded schema). Keep all dashboard charts.

## Architecture
- **Frontend**: Vite + React 18 + TypeScript + Ant Design + ECharts (from `dashboard/frontend`)
- **Backend**: FastAPI + SQLite, served via supervisor on :8001
- **Database**: SQLite file at `/app/backend/data/local.db`, seeded with 30 days of dummy data
- **Auth**: JWT (HS256), simple username/password (admin1 / pwd1)

## Data Source
The original dashboard backend queried BigQuery `gold.spans / gold.logs / gold.metrics`.
We replace it with SQLite tables seeded from `seed_data.py` (obswebapp folder):
- `wide_spans_detail` → spans (mapped: service_id→service_name, environment→source_platform, session_id→conversation_id, model_id→model)
- `wide_logs_detail` → logs
- `wide_metrics_detail` → metrics
- `wide_llm_interactions_detail` → cost/token aggregations (joined via trace_id/session_id)
- `wide_tool_executions_detail` → tool calls
- `llm_pricing` → SCD2 pricing table

## What's Implemented (2026-01-29)
- All dashboard tabs functional: Overview, Traces, Logs, Metrics, LLM Cost, Sessions, Tool Calls, Insights, Health, Compare
- 25+ API endpoints rewritten in SQLite (server.py): /api/login, /api/config, /api/overview, /api/overview/timeseries, /api/traces, /api/traces/{id}, /api/logs, /api/metrics/catalog|summary|timeseries|metrics, /api/cost, /api/sessions, /api/sessions/{id}, /api/tools, /api/search, /api/top/traces, /api/models, /api/errors/by-service|top, /api/latency/timeseries, /api/health, /api/meta/last-refresh, /api/refresh/*, /api/config/pricing (GET/POST/PATCH), /api/filters/projects|platforms|services, /api/auth/iap
- Bootstrap seeds 30 days of realistic observability data on first startup
- Charts confirmed rendering: KPI tiles, Cost & Errors trends, LLM cost bar/donut by service, log severity breakdown, traces table, latency distribution
- Default time range set to "Last 1 day" for better out-of-box data visibility

## Test Credentials
See `/app/memory/test_credentials.md`

## Backlog (P1/P2)
- Wire up metrics chart "Request throughput by response_code_class" — seed lacks this dimension
- Wire up Compare tab (UI exists but needs data)
- Google SSO (intentionally disabled in this local environment)
- Real BigQuery integration as alternative backend (currently SQLite-only)

## Next Action Items
- Optional: enrich seed_data with response_code_class for full Metrics tab parity
- Optional: add Refresh/pipeline real implementation (currently mocked)
