# OpenTelemetry Observability Dashboard

A web dashboard that visualizes OpenTelemetry (OTel) telemetry data — logs, traces, metrics — **plus AI agent observability data**: sessions, LLM interactions, tool executions, and errors. The backend is a Python **FastAPI** server, the frontend is a **React + TypeScript** single-page app, and the data lives in either **Google BigQuery** (production) or a **local SQLite** file (offline development). Charts are rendered with **Plotly**.

This README is written as both reference documentation and a tutorial. If you have never used FastAPI or React before, read it top to bottom and you will understand the entire codebase. If you already know the stack, jump to [Project structure](#project-structure) or the [API reference](#part-5--api-reference).

---

## Table of contents

1. [What this app does](#what-this-app-does)
2. [Quick start](#quick-start)
3. [Tech stack at a glance](#tech-stack-at-a-glance)
4. [How the app fits together](#how-the-app-fits-together-architecture)
5. [Project structure](#project-structure)
6. [Part 1 — Backend (FastAPI primer)](#part-1--backend-fastapi-primer)
7. [Part 2 — Frontend (React primer)](#part-2--frontend-react-primer)
8. [Part 3 — Data layer](#part-3--data-layer)
9. [Part 4 — Startup bootstrap](#part-4--startup-bootstrap)
10. [Part 5 — API reference](#part-5--api-reference)
11. [Part 6 — Frontend component reference](#part-6--frontend-component-reference)
12. [Part 7 — Tab walkthroughs](#part-7--tab-walkthroughs)
13. [Part 8 — Styling](#part-8--styling)
14. [Part 9 — Building and deploying](#part-9--building-and-deploying)
15. [Part 10 — Extending the app](#part-10--extending-the-app)
16. [Troubleshooting](#troubleshooting)
17. [Glossary](#glossary)

---

## What this app does

You point this dashboard at a data store that contains OTel and AI agent tables and it gives you eight interactive views:

| Tab | Question it answers |
|-----|---------------------|
| **Overview** | At a glance — span count, log count, error rate, average latency, total LLM cost, total tokens. Plus four trend charts. |
| **Logs** | Filter logs by severity / environment / service / time. Severity pie chart + a row-by-row log table; click a row to expand the full message. |
| **Traces** | Browse OTel trace summaries; click any trace to open a waterfall (Gantt-style timeline). Click a span row to inspect its full attributes as a JSON tree. |
| **Metrics** | Time-series of every metric (counters and histograms), latest-value bar chart, raw metric records. |
| **Sessions** | AI agent session list with cost aggregation. Click a session row to open a detail modal showing its agent traces, LLM calls, and tool executions. Tool executions with a `trace_id` link through to the OTel waterfall. |
| **LLM** | All LLM interactions across sessions. Filter by model, provider, status. Charts: cost by model, latency histogram, tokens over time, provider pie. Click a row to read the full prompt and response. |
| **Tools** | All tool executions. Filter by tool name, type, status. Charts: calls per tool, avg latency, status pie, executions over time. Click a row to view the input/output payloads, and jump to the OTel trace if available. |
| **Errors** | Application errors with severity classification. Filter by component, error type, severity. Charts: errors over time, by component, by type, severity pie. Click a row for full error detail and a direct link to the OTel waterfall. |

Every tab shares a common filter bar at the top: **Quick Range** (Last 1 Hour, 6 Hours, 24 Hours, 7 Days, 30 Days, or Custom dates), **Service**, and a **Refresh Filters** button.

---

## Quick start

### Run it locally with no cloud credentials

#### Single command (recommended)

Make sure `.env` has `APP_ENV=local`, then from the repo root:

```bash
./run.sh
# → http://localhost:7860
```

`run.sh` builds the React bundle, writes it into `backend/static/`, and starts the FastAPI server — one process, one port. Set `PORT=` to override the default 7860.

#### Development mode (two terminals, hot reload)

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt   # one time
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend dev server
cd frontend
npm install                        # one time
npm run dev
# → http://localhost:5173
```

The Vite dev server proxies `/api/*` to port 8000, so both servers must be running.

### Run it against BigQuery

Edit [.env](.env):

```bash
APP_ENV=          # blank, or anything other than "local"
GCP_PROJECT=your-project-id
BQ_DATASET=otel_raw_dataset
PORT=7860
```

Authenticate with `gcloud auth application-default login` (or set `GOOGLE_APPLICATION_CREDENTIALS` to a service-account key file). Ensure your account has **BigQuery Data Viewer** and **BigQuery Job User** IAM roles. Then run the same commands as above.

All eight tabs derive their data from the three OTel tables (`otel_raw_traces`, `otel_raw_logs`, `otel_raw_metrics`) — no additional tables are required. If the tables are empty, bootstrap seeds them with realistic dummy data automatically.

### Run the production single-container build

```bash
docker build -t otel-dashboard .
docker run --rm -p 7860:7860 --env-file .env otel-dashboard
# → http://localhost:7860
```

---

## Tech stack at a glance

| Layer | What we use | Why |
|-------|-------------|-----|
| HTTP server | **FastAPI** + Uvicorn | Async-first Python web framework with automatic JSON validation via type hints. |
| Data validation | **Pydantic v2** | Defines the shape of every request body and response. Errors at the boundary, not in the handler. |
| Frontend framework | **React 18** | Component-based UI library. JSX lets you write HTML-like syntax inside JavaScript. |
| Build tool / dev server | **Vite** | Lightning-fast bundler with hot module replacement. |
| Language (frontend) | **TypeScript** | JavaScript with types. Catches typos and shape mismatches at compile time. |
| Styling | **Tailwind CSS + raw CSS** | Tailwind for layout utilities; raw CSS for the dark theme and custom animations. |
| Charts | **Plotly** | Same chart library on backend (Python) and frontend (`react-plotly.js`). Backend builds figures, serializes to JSON, frontend renders them as-is. |
| JSON viewer | **react-json-view-lite** | Collapsible JSON tree for span attributes and tool payloads. |
| Cloud database | **Google BigQuery** | OTel and agent data partitioned by date. |
| Local database | **SQLite** (stdlib) | Zero-dependency file database for offline development. |
| Container | **Docker** (multi-stage) | Stage 1 builds the React bundle with Node; stage 2 runs Python and serves the bundle as static files. |

---

## How the app fits together (architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Browser (React SPA)                       │
│  ┌──────────────┐  ┌──────────────────────┐  ┌──────────────┐       │
│  │  FilterBar   │  │  Tabs (8)            │  │ StatusBanner │       │
│  └──────────────┘  └──────────┬───────────┘  └──────────────┘       │
│                               │ user switches tab / changes filter  │
│                               ▼                                     │
│                      api.sessions(filters)                          │
│                               │                                     │
└───────────────────────────────┼─────────────────────────────────────┘
                                │ POST /api/sessions {quick, …}
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI server (Uvicorn)                       │
│                                                                     │
│   main.py: @app.post("/api/sessions")                               │
│      │                                                              │
│      │  1. Pydantic parses JSON → SessionsRequest                   │
│      │  2. resolve_dates(quick, start, end) → (datetime, datetime)  │
│      │  3. bq_client.query_sessions(req)                            │
│      │  4. charts.make_sessions_status_pie(df) → Plotly Figure      │
│      │  5. fig.to_json() → {data, layout}  (+ Plotly binary decode) │
│      │                                                              │
│      ▼                                                              │
│   bq_client.py (router)                                             │
│      │                                                              │
│      ├── if APP_ENV=local  → backends/local.py  (SQLite + pandas)   │
│      │                                                              │
│      └── else              → backends/bq.py     (BigQuery client)   │
│                                                                     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  SQLite file     │ ← local mode
                  │  or BigQuery     │ ← cloud mode
                  └──────────────────┘
```

Key idea: the **chart and table-shaping logic is identical** in both modes. The two backend modules implement the same Python function signatures and return `pandas.DataFrame` objects with the same column names. Everything downstream (charts, JSON serialization, the React UI) is unaware of whether the data came from BigQuery or SQLite.

A note on Plotly serialization: Plotly 6.x encodes small integer arrays as base64 binary (`{"bdata": "...", "dtype": "i1"}`). `main.py` contains `_decode_plotly()` which walks the figure JSON and converts these back to plain Python lists before the response is sent, so the React side receives the standard `[number, …]` arrays it expects.

---

## Project structure

```
otel-dashboard/
├── README.md
├── run.sh                              ← single-command local build + serve
├── .env                                ← runtime config (APP_ENV, GCP_PROJECT, …)
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile                          ← multi-stage build (node → python)
│
├── backend/
│   ├── requirements.txt
│   ├── main.py                         ← FastAPI app + all HTTP routes
│   ├── models.py                       ← Pydantic request/response schemas
│   ├── bq_client.py                    ← router: picks backend based on APP_ENV
│   ├── bootstrap.py                    ← thin wrapper around backend.bootstrap()
│   ├── seed_data.py                    ← generators for the 3 OTel tables (no GCP imports)
│   ├── charts.py                       ← Plotly figure builders (18+ functions)
│   ├── pricing.py                      ← static Gemini cost-per-token table + compute helpers
│   └── backends/
│       ├── __init__.py
│       ├── bq.py                       ← BigQuery implementation + bootstrap
│       └── local.py                    ← SQLite implementation + bootstrap
│
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts                  ← Vite config (dev proxy, outDir → backend/static)
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.tsx                    ← React mount point
        ├── App.tsx                     ← top-level component, owns global state; 8 tabs
        ├── api.ts                      ← typed fetch wrappers for every endpoint
        ├── types.ts                    ← TypeScript interfaces (mirror models.py)
        ├── index.css                   ← dark theme CSS + animation keyframes
        ├── components/
        │   ├── FilterBar.tsx           ← shared date/service controls
        │   ├── StatusBanner.tsx        ← ok/warn/error banner with fade-out
        │   ├── KpiCard.tsx             ← KPI cards row
        │   ├── PlotlyChart.tsx         ← thin wrapper around react-plotly.js
        │   ├── DataTable.tsx           ← generic paginated table (clickable rows)
        │   ├── Tabs.tsx                ← tab navigation buttons
        │   ├── Spinner.tsx             ← animated loading spinner
        │   ├── Skeleton.tsx            ← skeleton placeholders (SkeletonTable, SkeletonCharts)
        │   ├── WaterfallModal.tsx      ← full-screen OTel waterfall + span JSON tree
        │   ├── SessionDetailModal.tsx  ← full-screen session detail (traces, LLM, tools)
        │   └── ChartModal.tsx          ← generic full-prompt / payload viewer
        └── tabs/
            ├── OverviewTab.tsx
            ├── LogsTab.tsx
            ├── TracesTab.tsx
            ├── MetricsTab.tsx
            ├── SessionsTab.tsx         ← NEW: AI agent sessions
            ├── LlmTab.tsx              ← NEW: LLM interaction log
            ├── ToolsTab.tsx            ← NEW: tool execution log
            └── ErrorsTab.tsx          ← NEW: application error log
```

---

## Part 1 — Backend (FastAPI primer)

> **If you know FastAPI**, skip to the [API reference](#part-5--api-reference).

### 1.1 What is FastAPI?

FastAPI is a Python web framework. You write Python functions, decorate them, and FastAPI turns them into HTTP endpoints. The killer feature is that FastAPI uses your **type hints** to:

1. Parse incoming JSON into typed Python objects (no `request.json["foo"]` — you just get `req.foo`).
2. Validate that the input matches the type. Wrong type → automatic 422 error response.
3. Serialize your return value to JSON.
4. Generate a live, interactive API docs page at `/docs` (Swagger UI).

The classic minimal example:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Greeting(BaseModel):
    name: str

@app.post("/hello")
def hello(g: Greeting) -> dict:
    return {"message": f"hello, {g.name}"}
```

A POST to `/hello` with `{"name": "ada"}` returns `{"message": "hello, ada"}`. A POST with `{"name": 42}` returns a 422 error explaining that `name` should be a string. You wrote zero parsing or validation code.

To run it: `uvicorn main:app --reload`. **Uvicorn** is the ASGI server that hosts FastAPI apps. `--reload` restarts the server when you save a file.

### 1.2 [backend/main.py](backend/main.py) walkthrough

This file does four things: defines the FastAPI app, registers a startup hook, defines all the HTTP routes, and mounts the React static files.

#### The FastAPI app + lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[main] starting up — mode={bq_client.MODE or 'cloud'}")
    safe_bootstrap()
    yield

app = FastAPI(title="OTel Observability Dashboard", lifespan=lifespan)
```

The `lifespan` async context manager runs code at startup (before `yield`) and shutdown (after). We use it to call `safe_bootstrap()`, which creates the database tables and seeds dummy data if needed.

#### Defining a route

```python
@app.post("/api/sessions", response_model=SessionsResponse)
def post_sessions(req: SessionsRequest) -> SessionsResponse:
    start, end = resolve_dates(req.quick, req.start, req.end)
    df = bq_client.query_sessions(req)
    return SessionsResponse(
        sessions=_records(df),
        charts={
            "status_pie":        _fig(charts.make_sessions_status_pie(df)),
            "sessions_over_time": _fig(charts.make_sessions_over_time(df)),
            "cost_by_agent":     _fig(charts.make_cost_by_agent(df)),
            "turns_hist":        _fig(charts.make_turns_hist(df)),
        },
    )
```

- `@app.post("/api/sessions")` — binds to `POST /api/sessions`.
- `req: SessionsRequest` — FastAPI parses the request body into this Pydantic model. Invalid JSON → 422, never reaches the function.
- `_fig(fig)` — calls `fig.to_json()`, parses back to a dict, then runs `_decode_plotly()` to convert Plotly's binary-encoded arrays to plain lists.
- `_records(df)` — converts the pandas DataFrame to `[{col: value, …}, …]` with datetimes stringified.

#### Pydantic models — [backend/models.py](backend/models.py)

```python
class DateRangeRequest(BaseModel):
    quick: str = "Last 24 Hours"
    start: str = ""
    end: str = ""
    service: str = "All"

class SessionsRequest(DateRangeRequest):
    agent:  str = "All"
    status: str = "All"

class LlmRequest(DateRangeRequest):
    model_name: str = "All"
    provider:   str = "All"
    status:     str = "All"
```

One base class for shared date/service filters, subclasses for per-endpoint fields. Mirrored in [frontend/src/types.ts](frontend/src/types.ts).

#### Plotly binary decode

Plotly 6.x serializes small integer arrays as base64 binary dicts (`{"bdata": "...", "dtype": "i1"}`). `_decode_plotly()` in `main.py` recursively walks the figure JSON and converts them back to plain Python lists using `struct.unpack`. It handles all numpy dtypes Plotly uses: `f8`, `f4`, `i8`, `i4`, `i2`, `i1`, `u8`, `u4`, `u2`, `u1`.

#### Static SPA mount

After all `/api/*` routes:

```python
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
```

In the Docker image the React build lives at `/app/static/`. The catch-all serves any file that exists, otherwise falls back to `index.html`. In local development this block is skipped — Vite handles the SPA on port 5173.

### 1.3 [backend/bq_client.py](backend/bq_client.py) — the backend router

```python
MODE = os.getenv("APP_ENV", "").strip().lower()

if MODE == "local":
    from backends.local import (get_filter_options, get_overview_stats,
                                 query_logs, query_traces, query_trace_waterfall,
                                 query_metrics, query_sessions, query_session_detail,
                                 query_llm_interactions, query_tool_executions,
                                 query_errors, bootstrap)
else:
    from backends.bq import (get_filter_options, get_overview_stats,
                              query_logs, query_traces, query_trace_waterfall,
                              query_metrics, query_sessions, query_session_detail,
                              query_llm_interactions, query_tool_executions,
                              query_errors, bootstrap)
```

In `local` mode, `google-cloud-bigquery` is never imported. The rest of the app calls `bq_client.query_sessions(…)` etc. without knowing which backend is active — the **router pattern**.

### 1.4 [backend/charts.py](backend/charts.py) — Plotly figure builders

One function per chart, each taking a DataFrame and returning a `go.Figure`. Shared `_LAYOUT` dict keeps every chart visually consistent. `_empty(msg)` returns a "no data" placeholder.

Chart functions by tab:

| Tab | Functions |
|-----|-----------|
| Overview | `make_cost_timeseries`, `make_latency_timeseries`, `make_tokens_timeseries`, `make_errors_timeseries` |
| Logs | `make_log_severity_pie` |
| Traces | `make_trace_waterfall`, `make_latency_hist`, `make_cost_by_agent`, `make_tokens_stacked` |
| Sessions | `make_sessions_status_pie`, `make_sessions_over_time`, `make_cost_by_agent`, `make_turns_hist` |
| LLM | `make_cost_by_model`, `make_llm_latency_hist`, `make_tokens_over_time`, `make_provider_pie` |
| Tools | `make_tool_calls_bar`, `make_tool_latency_bar`, `make_tool_status_pie`, `make_executions_over_time` |
| Errors | `make_errors_over_time`, `make_errors_by_component`, `make_errors_by_type`, `make_error_severity_pie` |

---

## Part 2 — Frontend (React primer)

> **If you know React**, skip to the [Component reference](#part-6--frontend-component-reference).

### 2.1 What is React?

React is a JavaScript library for building user interfaces from **components**. A component is a function that returns HTML-like markup (called **JSX**). React calls these functions whenever the data they depend on changes, and applies minimal DOM updates.

```tsx
function Greeting({ name }: { name: string }) {
  return <h1>Hello, {name}!</h1>;
}
```

`name` is a **prop** — data passed in from the parent.

### 2.2 The React concepts you need

#### State

Data that, when it changes, causes a re-render:

```tsx
const [count, setCount] = useState(0);
```

#### Effects

Code that runs after a render — typically to fetch data:

```tsx
useEffect(() => {
  api.sessions(filters).then(setData);
}, [filters]);   // re-run when filters changes
```

#### TypeScript

- `interface Foo { bar: string }` — defines a shape.
- `useState<Foo | null>(null)` — typed state.
- Types are erased at build time; benefits are entirely at author time.

### 2.3 What is Vite?

1. **Dev server** (`npm run dev`) — serves TypeScript/TSX files on the fly with instant hot reload.
2. **Production build** (`npm run build`) — bundles everything into `backend/static/` (via `outDir` in [vite.config.ts](frontend/vite.config.ts)).

Dev proxy:
```ts
proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } }
```

When the browser asks for `localhost:5173/api/sessions`, Vite forwards it to FastAPI on port 8000.

### 2.4 Entry point

`index.html` loads `src/main.tsx`, which mounts `<App />` into `<div id="root">`.

### 2.5 [frontend/src/App.tsx](frontend/src/App.tsx) — the top-level component

`App` owns the state shared across all tabs:

- `filters: SharedFilters` — date range and service.
- `options: FilterOptions` — dropdown choices from `/api/filters`.
- `status: StatusMsg` — the green/amber/red banner.
- `active: string` — which tab is currently selected.

```
<App>
  <FilterBar ... />
  <StatusBanner msg={status} />
  <Tabs tabs={["Overview","Logs","Traces","Metrics","Sessions","LLM","Tools","Errors"]} ... />
  <div hidden={active !== "Overview"}><OverviewTab /></div>
  <div hidden={active !== "Logs"}><LogsTab /></div>
  <div hidden={active !== "Traces"}><TracesTab /></div>
  <div hidden={active !== "Metrics"}><MetricsTab /></div>
  <div hidden={active !== "Sessions"}><SessionsTab /></div>
  <div hidden={active !== "LLM"}><LlmTab /></div>
  <div hidden={active !== "Tools"}><ToolsTab /></div>
  <div hidden={active !== "Errors"}><ErrorsTab /></div>
</App>
```

We use `hidden` instead of conditional rendering so each tab **keeps its loaded data** when you switch away and back.

### 2.6 [frontend/src/api.ts](frontend/src/api.ts)

Typed `fetch` wrappers:

```ts
export const api = {
  filters:       () => getJSON<FilterOptions>("/api/filters"),
  overview:      (f) => postJSON<OverviewResponse>("/api/overview", f),
  logs:          (f) => postJSON<LogsResponse>("/api/logs", f),
  traces:        (f) => postJSON<TracesResponse>("/api/traces", f),
  waterfall:     (id) => getJSON<WaterfallResponse>(`/api/trace/${id}/waterfall`),
  metrics:       (f) => postJSON<MetricsResponse>("/api/metrics", f),
  sessions:      (f) => postJSON<SessionsResponse>("/api/sessions", f),
  sessionDetail: (id) => getJSON<SessionDetailResponse>(`/api/session/${id}`),
  llm:           (f) => postJSON<LlmResponse>("/api/llm", f),
  tools:         (f) => postJSON<ToolsResponse>("/api/tools", f),
  errors:        (f) => postJSON<ErrorsResponse>("/api/errors", f),
};
```

### 2.7 [frontend/src/types.ts](frontend/src/types.ts)

Every Pydantic model has a TypeScript interface counterpart. If you add a field in [models.py](backend/models.py), update the matching interface here too.

`FilterOptions` includes fields derived from the OTel tables:

```ts
interface FilterOptions {
  services: string[];       // DISTINCT service_name from traces + logs
  environments: string[];   // DISTINCT environment from logs
  severities: string[];     // DISTINCT severity from logs
  agents: string[];         // DISTINCT COALESCE(agent_name, service_name) from traces
  metric_names: string[];   // DISTINCT metric_name from metrics
  models: string[];         // DISTINCT gen_ai.request.model from call_llm / gen_ai.chat spans
  providers: string[];      // derived from gen_ai.system / model name
  tool_names: string[];     // DISTINCT span_name from execute_tool* spans
  components: string[];     // DISTINCT service_name from ERROR spans + error logs
  errors: string[];         // list of sub-queries that failed (shown as red banner)
}
```

---

## Part 3 — Data layer

### 3.1 Tables

Everything is derived from **three OTel tables** — no separate application tables required:

| Table | Schema highlights | Derived views |
|-------|-------------------|---------------|
| `otel_raw_traces` | `trace_id`, `span_id`, `parent_span_id`, `span_name`, `start_time`, `end_time`, `duration_ms`, `status_code`, `agent_name`, `gen_ai_input_tokens`, `gen_ai_output_tokens`, `llm_cost_total_usd`, `attributes_json` | Overview, Traces, Sessions, LLM, Tools, Errors, Waterfall |
| `otel_raw_logs` | `timestamp`, `severity`, `message` (JSON), `service_name`, `trace_id` | Logs, Errors |
| `otel_raw_metrics` | `timestamp`, `metric_name`, `metric_type`, `agent_name`, `value_int`, `value_double`, `histogram_*` | Metrics |

**How agent-level concepts are derived from spans:**

| Concept | Source | Filter |
|---------|--------|--------|
| **Session** | `otel_raw_traces` | GROUP BY `trace_id` |
| **LLM interaction** | `otel_raw_traces` | `span_name IN ('call_llm', 'gen_ai.chat')` |
| **Tool execution** | `otel_raw_traces` | `span_name LIKE 'execute_tool%'` |
| **Error** | `otel_raw_traces` + `otel_raw_logs` | `status_code = 'ERROR'` ∪ `severity IN ('ERROR','FATAL','WARN')` |

**Key attributes extracted from `attributes_json`:**

| Field | JSON path | Used by |
|-------|-----------|---------|
| Model name | `gen_ai.request.model` | LLM tab, Session detail |
| Provider system | `gen_ai.system` (`vertex_ai` → google) | LLM tab, filter options |
| Agent name (fallback) | `COALESCE(agent_name, service_name)` | Sessions tab |
| Prompt text (LangGraph) | `gen_ai.prompt` | LLM tab, Session detail |
| Completion text (LangGraph) | `gen_ai.completion` | LLM tab, Session detail |
| Input tokens (LangGraph) | `gen_ai.usage.input_tokens` | LLM tab, Session detail |
| Output tokens (LangGraph) | `gen_ai.usage.output_tokens` | LLM tab, Session detail |
| Tool clean name | `tool.name` | Tools tab |
| Tool input payload | `tool.input` | Tools tab |
| Tool output payload | `tool.output` | Tools tab |

### 3.3 Cost computation — [backend/pricing.py](backend/pricing.py)

`llm_cost_total_usd` in `otel_raw_traces` is often `NULL` or `0` for LangGraph-instrumented agents. The app falls back to **static per-token pricing** sourced from the Google AI pricing page (May 2025):

| Model prefix | Input ($/1M tokens) | Output ($/1M tokens) |
|---|---|---|
| `gemini-2.5-pro` | $1.25 | $10.00 |
| `gemini-2.5-flash` | $0.15 | $0.60 |
| `gemini-2.5-flash-lite` | $0.10 | $0.40 |
| `gemini-2.0-flash` | $0.10 | $0.40 |
| `gemini-2.0-flash-lite` | $0.075 | $0.30 |
| `gemini-1.5-pro` | $1.25 | $5.00 |
| `gemini-1.5-flash` | $0.075 | $0.30 |
| `gemini-1.5-flash-8b` | $0.0375 | $0.15 |
| `gemini-1.0-pro` | $0.50 | $1.50 |

`pricing.effective_cost(stored, model, in_tokens, out_tokens)` returns the stored cost when it is > 0, otherwise computes from the table. Model matching uses longest-prefix-first so `gemini-2.5-flash` is preferred over `gemini-2.5`. Cost is computed in four places:

| Location | How |
|---|---|
| `query_llm_interactions` | Python `apply` after fetch |
| `query_session_detail` | Python `apply`; session `total_cost` summed from computed rows |
| `get_overview_stats` | Separate LLM-only query, Python `apply`, aggregated |
| `query_traces_timeseries` | BQ: inline SQL `CASE` via `pricing.sql_cost_expr()`; local: separate LLM query merged by hour |

### 3.7 Query internals

This section documents exactly how each key metric is derived, so the numbers displayed in the UI are unambiguous.

#### Average latency

`avg_duration_ms` is `AVG(duration_ms)` across **all spans** in the selected time window — root spans and child spans alike. Because a single trace produces multiple rows in `otel_raw_traces`, this number reflects the average individual-span duration, not the end-to-end trace time. It is intentionally broad: it gives a feel for span-level responsiveness across the whole service.

If you want per-trace end-to-end latency instead, the equivalent query would be:
```sql
-- per-trace latency (not currently used)
SELECT AVG(trace_duration_ms)
FROM (
  SELECT trace_id, (MAX(UNIX_MILLIS(end_time)) - MIN(UNIX_MILLIS(start_time))) AS trace_duration_ms
  FROM otel_raw_traces
  WHERE start_time BETWEEN @start AND @end
  GROUP BY trace_id
)
```

#### Token extraction

`gen_ai_input_tokens` and `gen_ai_output_tokens` are top-level columns in `otel_raw_traces` but are `NULL` for all LangGraph (`gen_ai.chat`) spans — tokens are only present in `attributes_json`. Every aggregation falls back to the JSON column:

**BigQuery** (`bq.py`):
```sql
COALESCE(
  gen_ai_input_tokens,
  CAST(REGEXP_EXTRACT(TO_JSON_STRING(attributes_json), '"gen_ai.usage.input_tokens":([0-9]+)') AS INT64)
) AS tokens_input
```
`TO_JSON_STRING` is required because `attributes_json` is a native BigQuery `JSON` type, not `STRING`. `REGEXP_EXTRACT` is used instead of `JSON_VALUE` because BigQuery's JSONPath does not support bracket notation for dotted keys, and the OTel attribute names (`gen_ai.usage.input_tokens`) contain dots that make them unreachable via dot-notation JSONPath.

**Local** (`local.py`):
```python
row["in_tok"] = float(row["gen_ai_input_tokens"] or 0) or _attr_float(row["attributes_json"], "gen_ai.usage.input_tokens")
```
`_attr_float` parses the JSON string and does a flat-key lookup (`dict.get("gen_ai.usage.input_tokens")`).

#### Model name extraction

**BigQuery**:
```sql
REGEXP_EXTRACT(TO_JSON_STRING(attributes_json), '"gen_ai.request.model":"([^"]+)"') AS model_name
```

**Local** (`query_session_detail`, `query_llm_interactions`):
```python
_json.loads(attrs_json).get("gen_ai.request.model") or ""
```
The local seed data stores the model under the key `"model"` (not `"gen_ai.request.model"`), so the local filter options query uses `attrs.get("model")` via `_extract_model`.

#### Session aggregation

Sessions are derived from `otel_raw_traces` — there is no separate sessions table. One session = one `trace_id`. The query groups all spans by `trace_id` and aggregates:

```sql
SELECT
  trace_id                                           AS session_id,
  MIN(agent_name)                                    AS agent_id,
  MIN(start_time)                                    AS start_time,
  MAX(end_time)                                      AS end_time,
  COUNT(*)                                           AS total_turns,
  MAX(CASE WHEN status_code='ERROR' THEN 1 ELSE 0 END) AS has_error,
  SUM(COALESCE(NULLIF(llm_cost_total_usd, 0), <cost_case>)) AS total_cost
FROM otel_raw_traces
WHERE start_time BETWEEN @start AND @end
GROUP BY trace_id
```

`total_cost` uses `COALESCE(NULLIF(stored, 0), computed)` — if the stored cost is non-zero it is used directly, otherwise the pricing CASE expression computes it from token counts and model name.

#### LLM span filter

All LLM-related queries (LLM tab, session detail, cost overview, token timeseries) filter on:
```sql
WHERE span_name IN ('call_llm', 'gen_ai.chat')
```
- `call_llm` — ADK (Agent Development Kit) spans
- `gen_ai.chat` — LangGraph spans (OpenTelemetry GenAI semantic conventions)

#### Tool span filter

Tool execution queries filter on:
```sql
WHERE span_name LIKE 'execute_tool%'
```
ADK emits spans named `execute_tool <tool-name>`. The display name is refined by extracting the `tool.name` attribute:
```sql
COALESCE(
  REGEXP_EXTRACT(TO_JSON_STRING(attributes_json), '"tool.name":"([^"]+)"'),
  span_name
) AS tool_display_name
```

#### Cost CASE expression (BigQuery)

`pricing.sql_cost_expr(in_col, out_col, model_col)` in [backend/pricing.py](backend/pricing.py) generates an inline BigQuery `CASE` statement used in GROUP BY queries where Python post-processing is not possible:

```sql
CASE
  WHEN STARTS_WITH(LOWER(<model_col>), 'gemini-2.5-pro') THEN
    (COALESCE(<in_col>, 0) * 1.25 + COALESCE(<out_col>, 0) * 10.00) / 1000000.0
  WHEN STARTS_WITH(LOWER(<model_col>), 'gemini-2.5-flash-lite') THEN
    ...
  ELSE 0.0
END
```

The prefixes are ordered longest-first so `gemini-2.5-flash-lite` is matched before `gemini-2.5-flash`.

#### Overview token KPIs

The token KPI cards (Input Tokens, Output Tokens) in the Overview tab are computed separately from the main span-count query. A secondary query fetches only `call_llm` / `gen_ai.chat` spans and sums token counts with the fallback pattern above, then `pricing.effective_cost` is applied per row to produce `total_cost_usd`. This avoids double-counting tokens from non-LLM parent spans.

### 3.4 [backend/backends/bq.py](backend/backends/bq.py) — BigQuery

One Python function per query, all using **parameterized queries** (never string concatenation) to prevent SQL injection. Example:

```python
def query_sessions(start_dt, end_dt, agent="All", status="All") -> pd.DataFrame:
    conditions = ["start_time BETWEEN @start AND @end"]
    params = _base_params(start_dt, end_dt)
    if agent != "All":
        conditions.append("(agent_name = @agent OR service_name = @agent)")
        params.append(bigquery.ScalarQueryParameter("agent", "STRING", agent))
    # GROUP BY trace_id to produce one session row per trace
    ...
```

### 3.5 [backend/backends/local.py](backend/backends/local.py) — SQLite

Same function signatures, same return shapes. For aggregations awkward in SQLite (like `TIMESTAMP_TRUNC` or cross-table joins), the local backend pulls rows into pandas and aggregates there. Acceptable for the small local dataset.

### 3.6 [backend/bq_client.py](backend/bq_client.py)

Already covered in [Part 1.3](#13-backendbq_clientpy--the-backend-router). The entire import list must be kept in sync between the two `if/else` branches.

---

## Part 4 — Startup bootstrap

The [lifespan](backend/main.py) hook runs `safe_bootstrap()` → `bq_client.bootstrap()` on every start. It is **idempotent**: creates tables and seeds data only when they're missing.

### 4.1 Local bootstrap

1. Creates `backend/data/` if missing.
2. For each of the three OTel tables: `CREATE TABLE IF NOT EXISTS …`, then inserts dummy rows from `seed_data.py` if the table is empty.

### 4.2 BigQuery bootstrap

1. `client.create_dataset(ds_ref, exists_ok=True)`.
2. For each of the three OTel tables: create with day-level time partitioning (`require_partition_filter=True`), then insert rows from `seed_data.py` if empty.

When connecting to an existing BigQuery dataset that already contains real OTel data, bootstrap detects the tables as non-empty and skips seeding.

### 4.3 [backend/seed_data.py](backend/seed_data.py) — OTel dummy fixtures

Generators `gen_logs`, `gen_traces`, `gen_metrics` produce realistic data: 2 services, 2 environments, 3 agents, weighted severities, traces with 3-6 spans in a parent-child tree, ~10% errors. No GCP imports.

---

## Part 5 — API reference

All endpoints are JSON. Client: [frontend/src/api.ts](frontend/src/api.ts). Interactive docs at **http://localhost:8000/docs**.

### `GET /api/filters` → `FilterOptions`

Lists distinct values for every dropdown across all tables.

```json
{
  "services":     ["adk_calc_agentobs", "langgraph_nl_agentobs"],
  "environments": ["dev", "prod"],
  "severities":   ["DEBUG", "ERROR", "INFO", "WARN"],
  "agents":       ["adk_calc_agentobs", "langgraph_nl_agentobs"],
  "metric_names": ["llm_tokens_total", "llm_cost_usd_total"],
  "models":       ["gemini-2.0-flash-001", "claude-haiku-4-5"],
  "providers":    ["google", "anthropic"],
  "tool_names":   ["execute_tool add", "execute_tool multiply"],
  "components":   ["adk_calc_agentobs"],
  "errors":       []
}
```

`errors` lists which sub-queries failed (shown as a red banner in the UI).

### `GET /api/quick-ranges` → `string[]`

The labels for the Quick Range dropdown.

### `POST /api/overview` ← `OverviewRequest` → `OverviewResponse`

```json
// request
{ "quick": "Last 24 Hours", "start": "", "end": "", "service": "All" }

// response
{
  "stats": { "total_spans": 129, "error_spans": 15, "avg_duration_ms": 142.3,
             "total_cost_usd": 0.043, "total_input_tokens": 12000,
             "total_output_tokens": 4800, "total_logs": 340 },
  "charts": { "cost": {…}, "latency": {…}, "tokens": {…}, "errors": {…} }
}
```

### `POST /api/logs` ← `LogsRequest` → `LogsResponse`

Filterable by `service`, `severity`, `environment`, `limit`. Returns rows and a severity pie chart.

### `POST /api/traces` ← `TracesRequest` → `TracesResponse`

```json
{
  "trace_list": [ { "trace_id": "...", "trace_start": "...", "total_duration_ms": 980, … } ],
  "spans":      [ { "trace_id": "...", "span_id": "...", "attributes_json": "...", … } ],
  "charts": { "latency_hist": {…}, "cost": {…}, "tokens": {…}, "by_agent": {…} }
}
```

### `GET /api/trace/{trace_id}/waterfall` → `WaterfallResponse`

```json
{
  "chart": { "data": […], "layout": {…} },
  "spans": [ { "span_id": "...", "duration_ms": 120, "attributes_json": "{…}", … } ]
}
```

`spans` includes raw `attributes_json` — the frontend parses it on click to populate the JSON tree.

### `POST /api/metrics` ← `MetricsRequest` → `MetricsResponse`

Returns `rows`, `metric_charts` (one Plotly figure per metric name), and `bar_chart` (latest values).

### `POST /api/sessions` ← `SessionsRequest` → `SessionsResponse`

Filterable by `agent`, `status`. Sessions are derived from `otel_raw_traces` — one row per `trace_id`, with `total_cost` computed via `pricing.effective_cost` (stored `llm_cost_total_usd` when > 0, otherwise static per-token pricing from `pricing.py`) and `status` set to `failed` if any span has `status_code = 'ERROR'`. Returns session rows and four charts.

### `GET /api/session/{session_id}` → `SessionDetailResponse`

```json
{
  "session":          { "session_id": "...", "agent_id": "...", "status": "completed", … },
  "agent_traces":     [ { "step_number": 1, "step_type": "plan", "decision": "...", … } ],
  "llm_interactions": [ { "model_name": "gpt-4o", "tokens_input": 800, … } ],
  "tool_executions":  [ { "tool_name": "web_search", "status": "success", "trace_id": "...", … } ]
}
```

`trace_id` on tool executions links to the OTel waterfall.

### `POST /api/llm` ← `LlmRequest` → `LlmResponse`

Filterable by `model_name`, `provider`, `status`. Returns rows and four charts: cost by model, latency histogram, tokens over time, provider pie.

### `POST /api/tools` ← `ToolsRequest` → `ToolsResponse`

Filterable by `tool_name`, `tool_type`, `status`. Returns rows and four charts: calls by tool, latency by tool, status pie, executions over time.

### `POST /api/errors` ← `ErrorsRequest` → `ErrorsResponse`

Filterable by `component`, `error_type`, `severity`. Returns rows and four charts: errors over time, by component, by type, severity pie.

---

## Part 6 — Frontend component reference

### [components/FilterBar.tsx](frontend/src/components/FilterBar.tsx)

Shared filter row: Quick Range dropdown, Start/End date inputs (only active on "Custom"), Service dropdown, Refresh Filters button. Never fetches anything itself — state bubbles up via `onChange(nextFilters)`.

### [components/StatusBanner.tsx](frontend/src/components/StatusBanner.tsx)

Green/amber/red message after `/api/filters`. Uses `@keyframes status-fadeout` (3 s) for ok/warn variants. Errors stay visible. Restarted by changing `key={msg.key}`.

### [components/KpiCard.tsx](frontend/src/components/KpiCard.tsx)

`KpiRow` renders 7 colored cards (Total Spans, Total Logs, Error Spans, Avg Latency, Total LLM Cost, Input Tokens, Output Tokens) from an `OverviewStats` object.

### [components/PlotlyChart.tsx](frontend/src/components/PlotlyChart.tsx)

Thin wrapper around `react-plotly.js`: passes `fig.data` and `fig.layout` through, forces `autosize: true`, hides the toolbar.

### [components/DataTable.tsx](frontend/src/components/DataTable.tsx)

Generic paginated table:

```tsx
interface Props {
  columns: string[];
  rows: Record<string, any>[];
  onRowClick?: (row, index) => void;
  emptyText?: string;
  pageSize?: number;
  truncateColumns?: string[];
}
```

When `pageSize` is set, shows Prev/Next buttons and a "X–Y of N" counter. `truncateColumns` applies CSS truncation with ellipsis for long values (e.g. IDs, long messages). Passing `onRowClick` makes rows hoverable and clickable.

### [components/Tabs.tsx](frontend/src/components/Tabs.tsx)

Renders tab buttons. Active tab gets the `.selected` CSS class.

### [components/Spinner.tsx](frontend/src/components/Spinner.tsx)

Animated ring spinner for inline loading states:

```tsx
<Spinner size={16} />   // small, in filter bar
<Spinner size={28} />   // larger, in modal loading state
```

Uses the `@keyframes spin` animation from `index.css`.

### [components/Skeleton.tsx](frontend/src/components/Skeleton.tsx)

Skeleton placeholders for first-load states:

- `<SkeletonTable rows={8} />` — placeholder rows for a data table.
- `<SkeletonCharts cols={2} rows={2} height={320} />` — placeholder grid of chart panels.

Both use the `.skeleton` class with `@keyframes skeleton-pulse` (slow fade in/out). Tabs show skeletons only on first load (`data === null && loading`). On subsequent filter changes the stale data stays visible and only the inline spinner appears — avoiding layout shift.

### [components/WaterfallModal.tsx](frontend/src/components/WaterfallModal.tsx)

Full-screen modal fetched by `trace_id`. Shows:
1. A Plotly Gantt waterfall chart.
2. A paginated span table.
3. On row click — the selected span's scalar fields + parsed `attributes_json` in a collapsible JSON tree (`react-json-view-lite`).

Opened from: TracesTab, ToolsTab (via `trace_id` button), ErrorsTab (via `trace_id` button), and SessionDetailModal (via tool execution row click).

### [components/SessionDetailModal.tsx](frontend/src/components/SessionDetailModal.tsx)

Full-screen modal fetched by `session_id`. Three paginated sections:
1. **Agent Traces** — step_number, step_type, decision, tool_name, llm_call_id, timestamp.
2. **LLM Interactions** — model_name, provider, tokens_input, tokens_output, latency_ms, cost, status, timestamp.
3. **Tool Executions** — tool_name, tool_type, status, latency_ms, `trace_id`, timestamp. Clicking a row with a `trace_id` opens the WaterfallModal.

### [components/ChartModal.tsx](frontend/src/components/ChartModal.tsx)

Generic detail popup used by LlmTab and ToolsTab to display full prompt/response text or input/output JSON payloads for a selected row.

---

## Part 7 — Tab walkthroughs

### 7.1 [OverviewTab.tsx](frontend/src/tabs/OverviewTab.tsx)

Loads automatically when the tab mounts (no button click needed). Renders `<KpiRow>` and a 2×2 grid of charts.

### 7.2 [LogsTab.tsx](frontend/src/tabs/LogsTab.tsx)

Filters: severity, environment, row-limit slider. Shows a severity pie chart above a paginated log table. Clicking a row opens a `LogModal` with the full message text.

### 7.3 [TracesTab.tsx](frontend/src/tabs/TracesTab.tsx)

Filters: agent, status code, trace-limit slider. Shows a paginated trace list. Click a row → opens `WaterfallModal`. A collapsible Analytics section shows four trace-level charts.

### 7.4 [MetricsTab.tsx](frontend/src/tabs/MetricsTab.tsx)

Filters: metric name, agent. Shows a time-series subplot grid, a latest-values bar chart, and a raw metric records table.

### 7.5 [SessionsTab.tsx](frontend/src/tabs/SessionsTab.tsx)

Filters: agent (derived from `COALESCE(agent_name, service_name)`), status. Shows a 2×2 chart grid (sessions over time, status pie, cost by agent, turns histogram) and a paginated sessions table. Clicking a row opens `SessionDetailModal`.

First load uses `<SkeletonCharts />` and `<SkeletonTable />`; filter-change refreshes keep stale data visible with a spinner in the filter bar.

### 7.6 [LlmTab.tsx](frontend/src/tabs/LlmTab.tsx)

Filters: model_name, provider, status. Spans matched: `call_llm` (ADK and some LangGraph) and `gen_ai.chat` (LangGraph). Shows cost by model, latency histogram, tokens over time, provider pie, plus a paginated LLM interactions table. Clicking a row opens `LlmDetailModal`, which renders:

- **System Instruction** — collapsible `<details>` block (ADK only, from `gcp.vertex.agent.llm_request`)
- **Conversation** — chat bubbles per turn extracted from `llm_request.contents[]` (ADK)
- **Model Response** — bubble rendered from `llm_response.content.parts[]` (ADK)
- **LangGraph fallback** — when no ADK attributes, shows `gen_ai.prompt` as a user bubble and `gen_ai.completion` as a model bubble

Token counts come from top-level `gen_ai_input_tokens`/`gen_ai_output_tokens` columns (ADK) with a fallback to `gen_ai.usage.input_tokens`/`output_tokens` in `attributes_json` (LangGraph). The `cost` column uses `pricing.effective_cost`: the stored `llm_cost_total_usd` when it is > 0, otherwise the model-matched static price from [backend/pricing.py](backend/pricing.py).

### 7.7 [ToolsTab.tsx](frontend/src/tabs/ToolsTab.tsx)

Filters: tool_name, tool_type, status. Shows four charts and a paginated tool executions table. Clicking a row opens `ToolDetailModal`, which renders:

- **LangGraph path** (when `tool.input` or `tool.output` present): shows Input and Output as scrollable `<pre>` blocks; display name comes from the `tool.name` attribute
- **ADK fallback**: renders the full `attributes_json` as a collapsible JSON tree via `react-json-view-lite`
- **Trace link**: if `trace_id` is set, a button opens the OTel waterfall directly

### 7.8 [ErrorsTab.tsx](frontend/src/tabs/ErrorsTab.tsx)

Filters: component, error_type, severity. Shows four charts and a paginated errors table. Clicking a row opens `ErrorDetailModal` with the full error message. If the row has a `trace_id`, a button opens the OTel waterfall.

---

## Part 8 — Styling

The styling is in [frontend/src/index.css](frontend/src/index.css) — explicit raw CSS rather than utility classes, so the rules are named and easy to audit.

### Color palette

```
#0f172a   page background
#1e293b   card / panel background
#334155   borders
#e2e8f0   primary text
#94a3b8   muted text
#60a5fa   accent blue (links, info)
#34d399   accent green (tokens)
#a78bfa   accent violet (latency)
#fbbf24   accent amber (cost)
#f87171   accent red (errors)
```

### Important classes

- `.app-container` — 1400px max-width centered container.
- `.kpi-row` / `.kpi-card` — KPI card layout.
- `.filter-bar` — shared filter row.
- `.status-ok` / `.status-warn` / `.status-error` — banner colors.
- `.status-fade` — 3-second fade-out animation (`@keyframes status-fadeout`).
- `.tab-nav` / `.selected` — tab navigation.
- `.dataframe` — table styling; `tr.clickable` adds hover cursor.
- `.table-wrap` — scrollable table container with max-height.
- `.accordion` — native `<details>/<summary>` styled as an accordion.
- `.skeleton` — pulsing placeholder block (`@keyframes skeleton-pulse`).
- `.json-viewer` — dark-themed container for `react-json-view-lite`.
- `.section-h` — section header label (small caps, slate color).
- `.field-label` / `.field-select` — filter bar label and select styling.

### Animation keyframes

```css
@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes skeleton-pulse {
  0%, 100% { opacity: 0.35; }
  50%       { opacity: 0.6;  }
}

@keyframes status-fadeout {
  0%   { opacity: 1; }
  70%  { opacity: 1; }
  100% { opacity: 0; }
}
```

---

## Part 9 — Building and deploying

### Local single-command build (no Docker)

```bash
./run.sh            # PORT defaults to 7860
PORT=8080 ./run.sh  # override port
```

`run.sh` runs `npm run build` (bundle → `backend/static/`), then starts `uvicorn`. FastAPI serves both the API and the SPA on one port.

### The Dockerfile (multi-stage)

```dockerfile
# Stage 1: build the React bundle with Node
FROM node:20-alpine AS frontend-builder
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build     # → /backend/static (via vite outDir)

# Stage 2: Python runtime
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-builder /backend/static ./static
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
```

Stage 1 builds with Node; stage 2 runs Python only — Node is left behind, keeping the image small.

### Local single-container test

```bash
docker build -t otel-dashboard .
docker run --rm -p 7860:7860 --env-file .env otel-dashboard
```

### Cloud Build CI/CD (GitHub → Cloud Run)

This project ships with [cloudbuild.yaml](cloudbuild.yaml) for automated deploys triggered by GitHub pushes.

**One-time setup:**

1. Create the Artifact Registry Docker repository (required before first push):
   ```bash
   gcloud artifacts repositories create gcr.io \
     --repository-format=docker --location=us \
     --project=$GCP_PROJECT
   ```

2. Grant the required IAM roles:
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT --format='value(projectNumber)')
   CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
   COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

   # Cloud Build SA: push images + write logs
   gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:$CB_SA" --role="roles/artifactregistry.writer"
   gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:$CB_SA" --role="roles/logging.logWriter"

   # Compute SA (used by the deploy step): manage Cloud Run services
   gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:$COMPUTE_SA" --role="roles/run.admin"
   gcloud projects add-iam-policy-binding $GCP_PROJECT --member="serviceAccount:$COMPUTE_SA" --role="roles/iam.serviceAccountUser"
   ```

3. In **Cloud Build → Triggers**, create a Push-to-branch trigger pointing at this repo, targeting the `main` branch, with **cloudbuild.yaml** as the build config.

Every push to `main` builds the Docker image, pushes to GCR, and deploys to Cloud Run (`us-central1`, `APP_ENV=cloud`). Cloud Run injects `PORT` automatically; `CMD` in [Dockerfile](Dockerfile) reads it.

### Manual Cloud Run deploy

```bash
gcloud builds submit --tag gcr.io/$GCP_PROJECT/otel-dashboard
gcloud run deploy otel-dashboard \
  --image gcr.io/$GCP_PROJECT/otel-dashboard \
  --region us-central1 \
  --set-env-vars="GCP_PROJECT=$GCP_PROJECT,BQ_DATASET=otel_raw_dataset,APP_ENV=cloud" \
  --allow-unauthenticated
```

Cloud Run sets `PORT` automatically; our `CMD` reads it via `${PORT}`.

---

## Part 10 — Extending the app

### Add a new chart to an existing tab

1. Write the figure builder in [charts.py](backend/charts.py): `def make_my_chart(df) -> go.Figure`.
2. Include it in the relevant route in [main.py](backend/main.py).
3. Add it to the response model in [models.py](backend/models.py) and the TypeScript interface in [types.ts](frontend/src/types.ts).
4. Render it in the tab: `<PlotlyChart fig={data.charts.my_chart} />`.

### Add a new endpoint

1. Define request/response Pydantic models in [models.py](backend/models.py).
2. Add a route in [main.py](backend/main.py).
3. Add a query function in **both** [backends/bq.py](backend/backends/bq.py) and [backends/local.py](backend/backends/local.py) with identical signatures and return shapes.
4. Re-export the function from [bq_client.py](backend/bq_client.py) in both `if/else` branches.
5. Add a fetch wrapper in [api.ts](frontend/src/api.ts) and a response interface in [types.ts](frontend/src/types.ts).

### Add a new tab

1. Create `frontend/src/tabs/MyTab.tsx` — props: `filters: SharedFilters`, `options: FilterOptions`.
2. Add to `TAB_NAMES` in [App.tsx](frontend/src/App.tsx) and add a `<div hidden={active !== "MyTab"}>` mount.
3. For first-load skeletons: render `data === null && loading ? <SkeletonCharts /> : data && <charts/>` and `data === null && loading ? <SkeletonTable /> : <DataTable ... />`.

### Add a cross-linking modal

If a table has a `trace_id` column and you want clicking a row to open the OTel waterfall:

1. Add `const [waterfallTraceId, setWaterfallTraceId] = useState<string | null>(null)` to the tab.
2. Pass `onViewTrace={(id) => setWaterfallTraceId(id)}` to the detail modal.
3. Render `{waterfallTraceId && <WaterfallModal traceId={waterfallTraceId} onClose={() => setWaterfallTraceId(null)} />}`.

---

## Troubleshooting

### Vite dev server says `connect ECONNREFUSED 127.0.0.1:8000`

The Vite proxy expects FastAPI on port 8000. Start uvicorn with `--port 8000`.

### `APP_ENV='' → using BigQuery backend` but I wanted local mode

Set `APP_ENV=local` in [.env](.env). The router prints its decision at startup.

### Bootstrap printed IAM permission errors

In cloud mode you need **BigQuery Data Viewer** + **BigQuery Job User** to read, plus **BigQuery Data Editor** the first time (to create dataset/tables).

### Sessions / LLM / Tools / Errors tabs return no data in BigQuery mode

All tabs derive from `otel_raw_traces` and `otel_raw_logs`. Check that:
1. Your time range matches when your agent ran (LLM spans: `span_name IN ('call_llm', 'gen_ai.chat')`; tool spans: `span_name LIKE 'execute_tool%'`).
2. Your IAM account has **BigQuery Data Viewer** + **BigQuery Job User**.
3. The `errors` field in `/api/filters` response lists any sub-queries that failed — check the red banner in the UI.

### The dashboard loads but charts show "No data available"

Check your time range. The seeded local data covers the last 24 hours. In BigQuery mode, the time range must overlap with when spans were ingested.

### How do I reset the local SQLite database?

```bash
rm backend/data/local.db
```

Restart the backend — bootstrap re-creates and re-seeds it.

### Pie charts or bar charts render blank

This is caused by a Plotly 6.x binary encoding issue. `main.py`'s `_decode_plotly()` handles it by converting base64 binary arrays back to plain lists. If a new dtype appears, add it to `_DTYPE_FMT` in `main.py`:

```python
_DTYPE_FMT = {
    "f8": ("d", 8), "f4": ("f", 4),
    "i8": ("q", 8), "i4": ("i", 4), "i2": ("h", 2), "i1": ("b", 1),
    "u8": ("Q", 8), "u4": ("I", 4), "u2": ("H", 2), "u1": ("B", 1),
}
```

---

## Glossary

| Term | Meaning |
|------|---------|
| **OTel / OpenTelemetry** | An open standard for emitting telemetry data — logs, traces, metrics. |
| **Span** | One unit of work inside a trace (e.g. an HTTP request). Has a start time, duration, parent, status, and arbitrary attributes. |
| **Trace (OTel)** | A tree of spans representing one logical operation, captured by infrastructure instrumentation. |
| **Trace (Agent)** | A single reasoning step in an AI agent session (plan, act, reflect, …). Derived from spans in `otel_raw_traces`, distinct from OTel traces. |
| **Waterfall** | A Gantt-style chart showing each span as a horizontal bar positioned by start time and sized by duration. |
| **Session** | One end-to-end run of an AI agent: a sequence of agent trace steps, LLM calls, and tool executions. |
| **Tool** | An external capability an AI agent can invoke. ADK emits `execute_tool *` spans; LangGraph emits spans with `tool.name`, `tool.input`, `tool.output` in `attributes_json`. |
| **ADK** | Agent Development Kit (Google). OTel spans use `call_llm`; full LLM request/response stored in `gcp.vertex.agent.llm_request`/`llm_response` attributes. |
| **LangGraph** | Python framework for stateful multi-actor AI apps. OTel spans use `gen_ai.chat` for LLM calls; prompts/completions in `gen_ai.prompt`/`gen_ai.completion` attributes. |
| **Skeleton** | A pulsing placeholder block shown while data is loading on first visit to a tab. Replaced by real content once the API responds. |
| **Counter / Histogram** | Two kinds of OTel metric. A counter accumulates. A histogram tracks distributions (sum, count, min, max). |
| **ASGI** | Asynchronous Server Gateway Interface — the Python protocol that lets FastAPI run on Uvicorn. |
| **Pydantic** | Python data-validation library. Validates incoming JSON against model types automatically. |
| **JSX / TSX** | HTML-like syntax inside JavaScript / TypeScript. Compiled to `React.createElement` calls. |
| **Hook** | A React function that lets a component use state, effects, etc. (`useState`, `useEffect`). Always called at the top level of a component. |
| **Vite** | Frontend build tool — fast dev server with HMR, and a production bundler. |
| **SPA** | Single-Page Application. The server returns one HTML file; routing happens in the browser. |
| **Bootstrap** (in this app) | The startup routine that creates OTel database tables and seeds dummy data if empty. Idempotent. |
| **`require_partition_filter`** | A BigQuery table option that forces every query to include a `WHERE` clause on the partition column, preventing accidental full-table scans. |
| **Router pattern** | `bq_client.py` selects either the BigQuery or SQLite backend at import time, exposing the same function names to the rest of the app. |
| **`pricing.py`** | Module holding static Google Gemini cost-per-token rates. `effective_cost()` returns the stored cost when > 0, otherwise falls back to computed cost. Used in LLM interactions, session detail, overview KPI, and the cost timeseries chart. |
