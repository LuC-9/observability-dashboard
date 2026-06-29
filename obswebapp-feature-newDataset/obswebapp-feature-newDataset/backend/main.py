"""
FastAPI shell for the OTel Observability Dashboard.

Endpoints replace the Gradio callbacks 1:1; charts come back as plain
{data, layout} JSON for react-plotly.js, tables come back as record dicts.
Static React build is mounted at / so a single container serves both.
"""
import json
import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import bq_client
import charts
from bootstrap import safe_bootstrap
from models import (
    FilterOptions,
    ErrorsRequest, ErrorsResponse,
    LlmRequest, LlmResponse,
    LogsRequest, LogsResponse,
    MetricsRequest, MetricsResponse,
    OverviewRequest, OverviewResponse, OverviewStats,
    SessionDetailResponse,
    SessionsRequest, SessionsResponse,
    ToolsRequest, ToolsResponse,
    TracesRequest, TracesResponse,
    WaterfallResponse,
)

load_dotenv()

# ── Date helpers (ported verbatim from app.py:28-57) ─────────────────────────

QUICK_RANGES: dict[str, timedelta | None] = {
    "Last 1 Hour":   timedelta(hours=1),
    "Last 6 Hours":  timedelta(hours=6),
    "Last 24 Hours": timedelta(hours=24),
    "Last 7 Days":   timedelta(days=7),
    "Last 30 Days":  timedelta(days=30),
    "Custom":        None,
}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def resolve_dates(quick: str, start_str: str, end_str: str) -> tuple[datetime, datetime]:
    delta = QUICK_RANGES.get(quick)
    if delta is not None:
        return _now() - delta, _now()
    try:
        start = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
    except Exception:
        start = _now() - timedelta(hours=24)
    try:
        end = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)
    except Exception:
        end = _now()
    return start, end


def _decode_plotly(obj):
    """Recursively convert Plotly 6.x binary-encoded arrays to plain Python lists.

    Plotly ≥ 6 serialises numpy arrays as {"dtype": "f8", "bdata": "<base64>"}
    instead of plain JSON arrays. react-plotly.js doesn't parse this format, so
    we decode it back to lists here on the server before sending to the frontend.
    """
    import base64, struct
    _DTYPE_FMT = {
        "f8": ("d", 8), "f4": ("f", 4),
        "i8": ("q", 8), "i4": ("i", 4), "i2": ("h", 2), "i1": ("b", 1),
        "u8": ("Q", 8), "u4": ("I", 4), "u2": ("H", 2), "u1": ("B", 1),
    }
    if isinstance(obj, dict):
        if "bdata" in obj and "dtype" in obj:
            fmt, size = _DTYPE_FMT.get(obj["dtype"], ("d", 8))
            raw = base64.b64decode(obj["bdata"])
            n = len(raw) // size
            if n == 0:
                return []
            return list(struct.unpack(f"{n}{fmt}", raw[:n * size]))
        return {k: _decode_plotly(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode_plotly(v) for v in obj]
    return obj


def _fig(fig) -> dict:
    """Serialize a Plotly figure to a {data, layout} dict for the frontend."""
    return _decode_plotly(json.loads(fig.to_json()))


# ── DataFrame display helpers (mirror app.py formatting) ─────────────────────

_TRACE_LIST_COLS = ["trace_id", "trace_start", "total_duration_ms", "span_count",
                    "error_count", "service_name", "agents"]
_SPAN_COLS       = ["trace_id", "span_name", "span_kind", "start_time", "duration_ms",
                    "status_code", "service_name", "agent_name",
                    "gen_ai_input_tokens", "gen_ai_output_tokens", "llm_cost_total_usd"]
_WF_SPAN_COLS    = ["span_id", "parent_span_id", "span_name", "span_kind", "start_time",
                    "duration_ms", "status_code", "agent_name",
                    "gen_ai_input_tokens", "gen_ai_output_tokens", "llm_cost_total_usd"]


def _records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to JSON-safe records (NaN → None, datetimes → str)."""
    if df is None or df.empty:
        return []
    out = df.copy()
    # Stringify datetime columns so JSON is human-readable & timezone is preserved
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
    # Replace NaN/NaT with None for valid JSON
    return json.loads(out.to_json(orient="records", date_format="iso"))


# ── Lifespan (startup bootstrap) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[main] starting up — mode={bq_client.MODE or 'cloud'}")
    safe_bootstrap()
    yield


app = FastAPI(title="OTel Observability Dashboard", lifespan=lifespan)

from bq_client import current_project

@app.middleware("http")
async def set_project_context(request: Request, call_next):
    project = request.headers.get("x-gcp-project")
    if project and project.strip() and project != "All":
        token = current_project.set(project.strip())
        try:
            return await call_next(request)
        finally:
            current_project.reset(token)
    return await call_next(request)


# ── API routes ───────────────────────────────────────────────────────────────

@app.get("/api/filters", response_model=FilterOptions)
def get_filters(project: str = None) -> FilterOptions:
    """Replaces refresh_filters() (app.py:314)."""
    try:
        opts = bq_client.get_filter_options(project)
    except Exception as e:
        traceback.print_exc()
        opts = {"services": [], "environments": [], "severities": [],
                "agents": [], "metric_names": [], "errors": [str(e)], "projects": []}
    return FilterOptions(**opts)


@app.post("/api/overview", response_model=OverviewResponse)
def post_overview(req: OverviewRequest) -> OverviewResponse:
    """Replaces load_overview() (app.py:96)."""
    start, end = resolve_dates(req.quick, req.start, req.end)
    stats = bq_client.get_overview_stats(start, end, req.service)
    ts_df = bq_client.query_traces_timeseries(start, end, req.service)
    return OverviewResponse(
        stats=OverviewStats(**stats),
        charts={
            "cost":    _fig(charts.make_cost_timeseries(ts_df)),
            "latency": _fig(charts.make_avg_latency_timeseries(ts_df)),
            "tokens":  _fig(charts.make_token_timeseries(ts_df)),
            "errors":  _fig(charts.make_error_rate_timeseries(ts_df)),
        },
    )


@app.post("/api/logs", response_model=LogsResponse)
def post_logs(req: LogsRequest) -> LogsResponse:
    """Replaces load_logs() (app.py:111)."""
    start, end = resolve_dates(req.quick, req.start, req.end)
    df = bq_client.query_logs(start, end, req.service, req.severity, req.environment, int(req.limit))
    sev_df = bq_client.query_logs_severity_dist(start, end, req.service)
    pie = charts.make_severity_pie(sev_df)

    if df.empty:
        return LogsResponse(rows=[], severity_chart=_fig(pie))

    disp = df[["timestamp", "severity", "message", "service_name", "environment", "model"]].copy()
    disp["timestamp"] = pd.to_datetime(disp["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    return LogsResponse(rows=_records(disp), severity_chart=_fig(pie))


@app.post("/api/traces", response_model=TracesResponse)
def post_traces(req: TracesRequest) -> TracesResponse:
    """Replaces load_trace_list() (app.py:136)."""
    start, end = resolve_dates(req.quick, req.start, req.end)
    df    = bq_client.query_trace_list(start, end, req.service, req.agent, req.status, int(req.limit))
    ts_df = bq_client.query_traces_timeseries(start, end, req.service)
    spans = bq_client.query_traces(start, end, req.service, req.agent, req.status, int(req.limit))

    chart_payload = {
        "latency_hist": _fig(charts.make_latency_histogram(spans)),
        "cost":         _fig(charts.make_cost_timeseries(ts_df)),
        "tokens":       _fig(charts.make_token_timeseries(ts_df)),
        "by_agent":     _fig(charts.make_latency_by_agent(spans)),
    }

    if df.empty:
        return TracesResponse(trace_list=[], spans=[], charts=chart_payload)

    disp = df.copy()
    if "trace_start" in disp.columns:
        disp["trace_start"] = pd.to_datetime(disp["trace_start"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    if "total_duration_ms" in disp.columns:
        disp["total_duration_ms"] = disp["total_duration_ms"].round(1)

    span_disp = pd.DataFrame(columns=_SPAN_COLS)
    if not spans.empty:
        span_disp = spans[[c for c in _SPAN_COLS if c in spans.columns]].copy()
        if "start_time" in span_disp.columns:
            span_disp["start_time"] = pd.to_datetime(span_disp["start_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        if "duration_ms" in span_disp.columns:
            span_disp["duration_ms"] = span_disp["duration_ms"].round(2)

    return TracesResponse(
        trace_list=_records(disp[[c for c in _TRACE_LIST_COLS if c in disp.columns]]),
        spans=_records(span_disp),
        charts=chart_payload,
    )


@app.get("/api/trace/{trace_id}/waterfall", response_model=WaterfallResponse)
def get_waterfall(trace_id: str) -> WaterfallResponse:
    """Replaces load_trace_waterfall() (app.py:189). Includes attributes_json
    so the span-click handler can render JSON entirely client-side."""
    if not trace_id.strip():
        raise HTTPException(status_code=400, detail="trace_id required")
    df = bq_client.query_trace_spans(trace_id.strip())
    wf = charts.make_trace_waterfall(df, trace_id.strip())

    if df.empty:
        return WaterfallResponse(chart=_fig(wf), spans=[])

    # Send the full DataFrame including attributes_json and relative times
    out = df.copy()
    if "start_time" in out.columns and "end_time" in out.columns:
        start_ts = pd.to_datetime(out["start_time"], utc=True)
        end_ts = pd.to_datetime(out["end_time"], utc=True)
        trace_start = start_ts.min()
        out["rel_start_ms"] = ((start_ts - trace_start).dt.total_seconds() * 1000).round(2)
        out["rel_end_ms"] = ((end_ts - trace_start).dt.total_seconds() * 1000).round(2)
        
        # Keep high precision timestamp string representations for display
        out["start_time"] = start_ts.dt.strftime("%Y-%m-%d %H:%M:%S.%f").str[:-3]
        out["end_time"] = end_ts.dt.strftime("%Y-%m-%d %H:%M:%S.%f").str[:-3]

    if "duration_ms" in out.columns:
        out["duration_ms"] = out["duration_ms"].round(2)
    return WaterfallResponse(chart=_fig(wf), spans=_records(out))


@app.post("/api/metrics", response_model=MetricsResponse)
def post_metrics(req: MetricsRequest) -> MetricsResponse:
    """Replaces load_metrics() (app.py:252)."""
    start, end = resolve_dates(req.quick, req.start, req.end)
    df = bq_client.query_metrics(start, end, req.service, req.agent, req.metric_name)

    if df.empty:
        return MetricsResponse(rows=[], metric_charts=[], bar_chart={})

    metric_names = df["metric_name"].dropna().unique().tolist()
    palette = charts._PALETTE
    metric_charts = [
        _fig(charts.make_single_metric_chart(df, mname, palette[i % len(palette)]))
        for i, mname in enumerate(metric_names)
    ]

    return MetricsResponse(rows=[], metric_charts=metric_charts, bar_chart={})



# ── Sessions ─────────────────────────────────────────────────────────────────

@app.post("/api/sessions", response_model=SessionsResponse)
def post_sessions(req: SessionsRequest) -> SessionsResponse:
    start, end = resolve_dates(req.quick, req.start, req.end)
    df     = bq_client.query_sessions(start, end, req.service, req.agent, req.status)
    ts_df  = bq_client.query_sessions_timeseries(start, end, req.service)
    cost_df = df if not df.empty else pd.DataFrame()

    charts_payload = {
        "status_pie":        _fig(charts.make_sessions_status_pie(df)),
        "sessions_over_time": _fig(charts.make_sessions_over_time(ts_df)),
        "cost_by_agent":     _fig(charts.make_cost_by_agent(cost_df)),
        "turns_hist":        _fig(charts.make_turns_histogram(df)),
    }

    if df.empty:
        return SessionsResponse(sessions=[], charts=charts_payload)

    disp = df.copy()
    for col in ("start_time", "end_time"):
        if col in disp.columns:
            disp[col] = pd.to_datetime(disp[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
    if "total_cost" in disp.columns:
        disp["total_cost"] = pd.to_numeric(disp["total_cost"], errors="coerce").round(6)
    return SessionsResponse(sessions=_records(disp), charts=charts_payload)


@app.get("/api/session/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(session_id: str) -> SessionDetailResponse:
    if not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id required")
    result = bq_client.query_session_detail(session_id.strip())
    sess_df = result.get("session")
    session_row = _records(sess_df)[0] if (sess_df is not None and not sess_df.empty) else {}

    def _fmt_ts(df):
        if df is None or df.empty:
            return []
        out = df.copy()
        for col in out.columns:
            if pd.api.types.is_datetime64_any_dtype(out[col]):
                out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%d %H:%M:%S")
        return _records(out)

    return SessionDetailResponse(
        session=session_row,
        agent_traces=_fmt_ts(result.get("agent_traces")),
        llm_interactions=_fmt_ts(result.get("llm_interactions")),
        tool_executions=_fmt_ts(result.get("tool_executions")),
    )


# ── LLM Interactions ─────────────────────────────────────────────────────────

@app.post("/api/llm", response_model=LlmResponse)
def post_llm(req: LlmRequest) -> LlmResponse:
    start, end = resolve_dates(req.quick, req.start, req.end)
    df    = bq_client.query_llm_interactions(start, end, req.model_name, req.provider, req.status)
    ts_df = bq_client.query_llm_timeseries(start, end)

    charts_payload = {
        "cost_by_model":  _fig(charts.make_cost_by_model(df)),
        "latency_hist":   _fig(charts.make_llm_latency_hist(df)),
        "tokens_over_time": _fig(charts.make_llm_tokens_over_time(ts_df)),
        "provider_pie":   _fig(charts.make_provider_pie(df)),
    }

    if df.empty:
        return LlmResponse(rows=[], charts=charts_payload)

    disp = df.copy()
    if "timestamp" in disp.columns:
        disp["timestamp"] = pd.to_datetime(disp["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    if "cost" in disp.columns:
        disp["cost"] = disp["cost"].round(8)
    if "latency_ms" in disp.columns:
        disp["latency_ms"] = disp["latency_ms"].round(2)
    return LlmResponse(rows=_records(disp), charts=charts_payload)


# ── Tool Executions ──────────────────────────────────────────────────────────

@app.post("/api/tools", response_model=ToolsResponse)
def post_tools(req: ToolsRequest) -> ToolsResponse:
    start, end = resolve_dates(req.quick, req.start, req.end)
    df    = bq_client.query_tool_executions(start, end, req.service, req.tool_name, req.tool_type, req.status)
    ts_df = bq_client.query_tool_executions_timeseries(start, end, req.service)

    charts_payload = {
        "calls_by_tool":      _fig(charts.make_tool_calls_bar(df)),
        "latency_by_tool":    _fig(charts.make_tool_latency_bar(df)),
        "status_pie":         _fig(charts.make_tool_status_pie(df)),
        "executions_over_time": _fig(charts.make_tool_executions_over_time(ts_df)),
    }

    if df.empty:
        return ToolsResponse(rows=[], charts=charts_payload)

    disp = df.copy()
    if "timestamp" in disp.columns:
        disp["timestamp"] = pd.to_datetime(disp["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    if "latency_ms" in disp.columns:
        disp["latency_ms"] = disp["latency_ms"].round(2)
    return ToolsResponse(rows=_records(disp), charts=charts_payload)


# ── Errors ────────────────────────────────────────────────────────────────────

@app.post("/api/errors", response_model=ErrorsResponse)
def post_errors(req: ErrorsRequest) -> ErrorsResponse:
    start, end = resolve_dates(req.quick, req.start, req.end)
    df    = bq_client.query_errors(start, end, req.service, req.component, req.error_type, req.severity)
    ts_df = bq_client.query_errors_timeseries(start, end, req.service, req.component, req.error_type, req.severity)

    charts_payload = {
        "errors_over_time": _fig(charts.make_errors_over_time(ts_df)),
        "by_component":     _fig(charts.make_errors_by_component(df)),
        "by_type":          _fig(charts.make_errors_by_type(df)),
        "severity_pie":     _fig(charts.make_error_severity_pie(df)),
    }

    if df.empty:
        return ErrorsResponse(rows=[], charts=charts_payload)

    disp = df.copy()
    if "timestamp" in disp.columns:
        disp["timestamp"] = pd.to_datetime(disp["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    return ErrorsResponse(rows=_records(disp), charts=charts_payload)


# ── Quick-range labels (so the frontend doesn't hardcode them) ───────────────

@app.get("/api/quick-ranges")
def get_quick_ranges() -> list[str]:
    return list(QUICK_RANGES.keys())


# ── Static SPA ───────────────────────────────────────────────────────────────

# /app/static is where the Dockerfile copies the React build.
# In local dev, `cd backend && uvicorn main:app` works without a static dir
# because the SPA is served from `npm run dev` on a separate port.

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.is_dir():
    # assets first (CSS/JS chunks live under /assets/)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    _NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", headers=_NO_CACHE)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        # Anything not /api/* → serve index.html so SPA refresh works
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html", headers=_NO_CACHE)
else:
    print(f"[main] static dir not found at {STATIC_DIR} — frontend must run separately (npm run dev)")
