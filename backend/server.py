"""
Central Observability API — SQLite-backed (wide_* schema from obswebapp).
Exposes the same endpoints expected by the dashboard frontend.
"""
import os
import sqlite3
import uuid
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import seed_data

load_dotenv()

DB_PATH = Path(os.environ.get("DB_PATH", str(Path(__file__).parent / "data" / "local.db")))
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-dev-secret")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin1")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "pwd1")

TIME_PRESETS = {"5m": 5, "10m": 10, "30m": 30, "1h": 60, "6h": 360, "12h": 720,
                "1d": 1440, "7d": 10080, "30d": 43200}


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def run(sql: str, params: tuple | list = ()) -> list[dict]:
    with _conn() as c:
        cur = c.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]


def execute(sql: str, params: tuple | list = ()):
    with _conn() as c:
        c.execute(sql, tuple(params))
        c.commit()


def bootstrap_db():
    """Create wide_* tables and seed with 30-day data."""
    now = datetime.now(tz=timezone.utc)
    with _conn() as c:
        for tname, cols in seed_data.TABLE_COLS.items():
            col_defs = ", ".join(f'"{n}" {t}' for n, t in cols)
            c.execute(f'CREATE TABLE IF NOT EXISTS "{tname}" ({col_defs})')
        # pricing table
        c.execute('''CREATE TABLE IF NOT EXISTS "llm_pricing" (
            id TEXT PRIMARY KEY, model_prefix TEXT, input_cost_per_1m_tokens REAL,
            output_cost_per_1m_tokens REAL, active INTEGER DEFAULT 1, updated_at TEXT)''')
        c.commit()

    # idempotent: only seed if spans empty
    existing = run("SELECT COUNT(*) AS n FROM wide_spans_detail")[0]["n"]
    if existing > 0:
        print(f"[bootstrap] already seeded (spans={existing})")
        return

    print("[bootstrap] seeding wide_* tables with 30 days of data...")
    # Generate larger dataset spread over 30 days
    random.seed(2026)
    all_seed = {
        "wide_agent_trace_steps_daily": seed_data.gen_agent_traces_steps_daily(now),
        "wide_agent_traces_detail":      seed_data.gen_agent_traces_detail(now, n=200),
        "wide_error_summary_daily":      seed_data.gen_error_summary_daily(now),
        "wide_errors_detail":            seed_data.gen_errors_detail(now, n=120),
        "wide_llm_interactions_detail":  seed_data.gen_llm_interactions(now, n=300),
        "wide_llm_usage_daily":          seed_data.gen_llm_usage_daily(now),
        "wide_logs_daily":               seed_data.gen_logs_daily(now),
        "wide_logs_detail":              seed_data.gen_logs_detail(now, n=400),
        "wide_metrics_daily":            seed_data.gen_metrics_daily(now),
        "wide_metrics_detail":           seed_data.gen_metrics_detail(now, n=250),
        "wide_service_health_daily":     seed_data.gen_service_health_daily(now),
        "wide_session_summary_daily":    seed_data.gen_session_summary_daily(now),
        "wide_sessions_detail":          seed_data.gen_sessions(now, n=80),
        "wide_spans_detail":             seed_data.gen_spans(now, n_traces=120),
        "wide_tool_executions_detail":   seed_data.gen_tool_executions(now, n=150),
        "wide_tool_usage_daily":         seed_data.gen_tool_usage_daily(now),
        "wide_traces_daily":             seed_data.gen_traces_daily(now),
    }
    with _conn() as c:
        for tname, rows in all_seed.items():
            if not rows:
                continue
            cols_order = [n for n, _ in seed_data.TABLE_COLS[tname]]
            placeholders = ", ".join("?" for _ in cols_order)
            col_list = ", ".join(f'"{x}"' for x in cols_order)
            c.executemany(
                f'INSERT INTO "{tname}" ({col_list}) VALUES ({placeholders})',
                [[row.get(col) for col in cols_order] for row in rows],
            )
        # pricing
        for p in seed_data.gen_pricing():
            c.execute('INSERT INTO llm_pricing VALUES (?,?,?,?,?,?)',
                      (str(uuid.uuid4()), p["model_prefix"],
                       p["input_cost_per_1m_tokens"], p["output_cost_per_1m_tokens"],
                       1, now.isoformat()))
        c.commit()
    print(f"[bootstrap] seeded {sum(len(v) for v in all_seed.values())} rows")


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def make_token(user: str) -> str:
    payload = {"sub": user, "exp": datetime.now(tz=timezone.utc) + timedelta(hours=24)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def require_auth(authorization: str | None = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid token")


# ─── Time / filter helpers ─────────────────────────────────────────────────────

def time_window(time_range: str | None, start: str | None, end: str | None):
    now = datetime.now(tz=timezone.utc)
    if time_range == "custom" and start and end:
        return start, end
    mins = TIME_PRESETS.get(time_range or "1h", 60)
    return (now - timedelta(minutes=mins)).isoformat(), now.isoformat()


def build_scope(project, platform, service, time_range, start, end, time_col,
                with_platform=True):
    """Returns (where_sql, params_list, start, end). Uses wide_spans_detail-like cols."""
    s, e = time_window(time_range, start, end)
    clauses = [f'"{time_col}" BETWEEN ? AND ?']
    params = [s, e]
    if project:
        clauses.append("project_id = ?")
        params.append(project)
    if with_platform and platform:
        plats = [p for p in platform.split(",") if p]
        if len(plats) == 1:
            clauses.append("environment = ?")
            params.append(plats[0])
        elif plats:
            clauses.append(f"environment IN ({','.join('?'*len(plats))})")
            params.extend(plats)
    if service:
        svcs = [v for v in service.split(",") if v]
        col = "service_id"
        if len(svcs) == 1:
            clauses.append(f"{col} = ?")
            params.append(svcs[0])
        elif svcs:
            clauses.append(f"{col} IN ({','.join('?'*len(svcs))})")
            params.extend(svcs)
    return "WHERE " + " AND ".join(clauses), params, s, e


def bucket_fmt(time_range: str | None) -> str:
    """SQLite strftime format for bucketing."""
    mins = TIME_PRESETS.get(time_range or "1h", 60)
    if mins <= 60:
        return "%Y-%m-%dT%H:%M:00"  # minute
    if mins <= 1440:
        return "%Y-%m-%dT%H:00:00"  # hour
    return "%Y-%m-%d"                              # day


# ─── App ───────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_db()
    yield


app = FastAPI(title="Central Observability API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Creds(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def do_login(c: Creds):
    if c.username != ADMIN_USER or c.password != ADMIN_PASS:
        raise HTTPException(401, "bad credentials")
    return {"token": make_token(c.username), "user": c.username}


@app.get("/api/config")
def get_config():
    return {"google_client_id": "", "allowed_domain": ""}


@app.get("/api/auth/iap")
def auth_iap():
    # Not behind IAP in this local env — frontend should fall back to user/pass.
    raise HTTPException(401, "no IAP identity")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ─── Pricing ───────────────────────────────────────────────────────────────────

@app.get("/api/config/pricing")
def list_pricing(_user=Depends(require_auth)):
    return run("""SELECT id, model_prefix,
                  input_cost_per_1m_tokens AS input_cost,
                  output_cost_per_1m_tokens AS output_cost,
                  active, updated_at
                  FROM llm_pricing ORDER BY model_prefix, active DESC, updated_at DESC""")


class PriceIn(BaseModel):
    model_prefix: str
    input_cost: float
    output_cost: float
    active: bool = True
    force: bool = False


@app.post("/api/config/pricing")
def add_pricing(p: PriceIn, _user=Depends(require_auth)):
    prefix = p.model_prefix.strip()
    if not prefix:
        raise HTTPException(400, "model name required")
    if p.active:
        dup = run("SELECT COUNT(*) AS n FROM llm_pricing WHERE model_prefix=? AND active=1", [prefix])
        if dup[0]["n"] > 0 and not p.force:
            raise HTTPException(409, f"active price exists for '{prefix}'")
        if p.force:
            execute("UPDATE llm_pricing SET active=0, updated_at=? WHERE model_prefix=? AND active=1",
                    [datetime.now(tz=timezone.utc).isoformat(), prefix])
    execute("INSERT INTO llm_pricing VALUES (?,?,?,?,?,?)",
            [str(uuid.uuid4()), prefix, p.input_cost, p.output_cost, 1 if p.active else 0,
             datetime.now(tz=timezone.utc).isoformat()])
    return {"ok": True}


class PricePatch(BaseModel):
    active: bool | None = None
    input_cost: float | None = None
    output_cost: float | None = None


@app.patch("/api/config/pricing/{pid}")
def patch_pricing(pid: str, p: PricePatch, _user=Depends(require_auth)):
    sets, params = [], []
    if p.active is not None:
        sets.append("active=?")
        params.append(1 if p.active else 0)
    if p.input_cost is not None:
        sets.append("input_cost_per_1m_tokens=?")
        params.append(p.input_cost)
    if p.output_cost is not None:
        sets.append("output_cost_per_1m_tokens=?")
        params.append(p.output_cost)
    if not sets:
        raise HTTPException(400, "nothing to update")
    sets.append("updated_at=?")
    params.append(datetime.now(tz=timezone.utc).isoformat())
    params.append(pid)
    execute(f"UPDATE llm_pricing SET {', '.join(sets)} WHERE id=?", params)
    return {"ok": True}


# ─── Filters ───────────────────────────────────────────────────────────────────

@app.get("/api/filters/projects")
def projects(_user=Depends(require_auth)):
    return run("SELECT DISTINCT project_id FROM wide_spans_detail WHERE project_id IS NOT NULL ORDER BY project_id")


@app.get("/api/filters/platforms")
def platforms(project: str | None = None, _user=Depends(require_auth)):
    sql = "SELECT DISTINCT environment AS source_platform FROM wide_spans_detail WHERE environment IS NOT NULL"
    params = []
    if project:
        sql += " AND project_id = ?"
        params.append(project)
    sql += " ORDER BY source_platform"
    return run(sql, params)


@app.get("/api/filters/services")
def services(project: str | None = None, platform: str | None = None, _user=Depends(require_auth)):
    sql = "SELECT DISTINCT service_id AS service_name FROM wide_spans_detail WHERE service_id IS NOT NULL"
    params = []
    if project:
        sql += " AND project_id = ?"
        params.append(project)
    if platform:
        sql += " AND environment = ?"
        params.append(platform)
    sql += " ORDER BY service_name"
    return run(sql, params)


# ─── Overview ──────────────────────────────────────────────────────────────────

def _llm_cost_subq(start, end, project, platform, service):
    """LLM cost/tokens via wide_llm_interactions_detail."""
    cl = ['timestamp BETWEEN ? AND ?']
    pp = [start, end]
    if project:
        cl.append("project_id=?")
        pp.append(project)
    if platform:
        cl.append("environment=?")
        pp.append(platform)
    if service:
        cl.append("service_id=?")
        pp.append(service)
    return " AND ".join(cl), pp


@app.get("/api/overview")
def overview(project: str | None = None, platform: str | None = None, service: str | None = None,
             time_range: str = "1h", start: str | None = None, end: str | None = None,
             _user=Depends(require_auth)):
    w, p, s, e = build_scope(project, platform, service, time_range, start, end, "start_time")
    span_kpi = run(f"""SELECT
        COUNT(DISTINCT trace_id) AS traces,
        COUNT(*) AS spans,
        COUNT(DISTINCT service_id) AS services,
        COUNT(DISTINCT project_id) AS projects,
        CAST(SUM(CASE WHEN status_code='ERROR' THEN 1 ELSE 0 END) AS REAL)/NULLIF(COUNT(*),0) AS error_rate
        FROM wide_spans_detail {w}""", p)
    llm_w, llm_p = _llm_cost_subq(s, e, project, platform, service)
    llm_kpi = run(f"""SELECT
        ROUND(COALESCE(SUM(cost),0), 6) AS cost_usd,
        COALESCE(SUM(tokens_input), 0) AS input_tokens,
        COALESCE(SUM(tokens_output), 0) AS output_tokens
        FROM wide_llm_interactions_detail WHERE {llm_w}""", llm_p)
    # latency p50/p95 from spans (only root spans where parent is NULL)
    lat = run(f"""SELECT duration_ms FROM wide_spans_detail {w}
        AND parent_span_id IS NULL ORDER BY duration_ms""".replace("WHERE", "WHERE", 1), p)
    durs = [r["duration_ms"] for r in lat if r["duration_ms"] is not None]
    p50 = durs[len(durs)//2] if durs else 0
    p95 = durs[int(len(durs)*0.95)] if durs else 0
    kpis = {**(span_kpi[0] if span_kpi else {}), **(llm_kpi[0] if llm_kpi else {}),
            "p50_ms": round(p50, 1) if p50 else 0, "p95_ms": round(p95, 1) if p95 else 0}
    return {"range": {"start": s, "end": e}, "kpis": kpis}


@app.get("/api/overview/timeseries")
def overview_ts(project: str | None = None, platform: str | None = None, service: str | None = None,
                time_range: str = "1h", start: str | None = None, end: str | None = None,
                _user=Depends(require_auth)):
    w, p, s, e = build_scope(project, platform, service, time_range, start, end, "start_time")
    fmt = bucket_fmt(time_range)
    spans = run(f"""SELECT strftime('{fmt}', start_time) AS bucket,
        COUNT(DISTINCT trace_id) AS traces,
        SUM(CASE WHEN status_code='ERROR' THEN 1 ELSE 0 END) AS errors
        FROM wide_spans_detail {w}
        GROUP BY bucket ORDER BY bucket""", p)
    llm_w, llm_p = _llm_cost_subq(s, e, project, platform, service)
    llm = run(f"""SELECT strftime('{fmt}', timestamp) AS bucket,
        ROUND(COALESCE(SUM(cost),0), 6) AS cost_usd,
        COALESCE(SUM(tokens_input), 0) AS input_tokens,
        COALESCE(SUM(tokens_output), 0) AS output_tokens
        FROM wide_llm_interactions_detail WHERE {llm_w}
        GROUP BY bucket""", llm_p)
    llm_map = {r["bucket"]: r for r in llm}
    out = []
    for r in spans:
        b = r["bucket"]
        lr = llm_map.get(b, {})
        out.append({**r, "cost_usd": lr.get("cost_usd", 0),
                    "input_tokens": lr.get("input_tokens", 0),
                    "output_tokens": lr.get("output_tokens", 0)})
    return out


@app.get("/api/latency/timeseries")
def latency_ts(project: str | None = None, platform: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               _user=Depends(require_auth)):
    w, p, _, _ = build_scope(project, platform, service, time_range, start, end, "start_time")
    fmt = bucket_fmt(time_range)
    rows = run(f"""SELECT strftime('{fmt}', start_time) AS bucket, duration_ms
        FROM wide_spans_detail {w} AND parent_span_id IS NULL
        ORDER BY bucket, duration_ms""", p)
    by_bucket: dict = {}
    for r in rows:
        by_bucket.setdefault(r["bucket"], []).append(r["duration_ms"])
    out = []
    for b, ds in sorted(by_bucket.items()):
        ds_sorted = sorted(d for d in ds if d is not None)
        if not ds_sorted:
            continue
        p50 = ds_sorted[len(ds_sorted)//2]
        p95 = ds_sorted[int(len(ds_sorted)*0.95)] if len(ds_sorted) > 1 else ds_sorted[-1]
        out.append({"bucket": b, "p50_ms": round(p50, 1), "p95_ms": round(p95, 1)})
    return out


# ─── Traces ────────────────────────────────────────────────────────────────────

@app.get("/api/traces")
def traces(project: str | None = None, platform: str | None = None, service: str | None = None,
           time_range: str = "1h", start: str | None = None, end: str | None = None,
           page: int = 1, page_size: int = 50, _user=Depends(require_auth)):
    w, p, _, _ = build_scope(project, platform, service, time_range, start, end, "start_time")
    total = run(f"SELECT COUNT(*) AS n FROM (SELECT trace_id FROM wide_spans_detail {w} GROUP BY trace_id)", p)
    off = max(0, (page - 1) * page_size)
    rows = run(f"""SELECT trace_id,
        MAX(service_id) AS service_name,
        MAX(project_id) AS project_id,
        MAX(environment) AS source_platform,
        MAX(agent_name) AS agent_name,
        MIN(start_time) AS start_time,
        MAX(CASE WHEN parent_span_id IS NULL THEN span_name END) AS root_span,
        MAX(CASE WHEN parent_span_id IS NULL THEN duration_ms END) AS duration_ms,
        MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) AS status_code,
        MAX(session_id) AS conversation_id,
        COUNT(*) AS spans
        FROM wide_spans_detail {w}
        GROUP BY trace_id ORDER BY start_time DESC LIMIT ? OFFSET ?""",
        p + [page_size, off])
    # Augment with LLM cost/tokens
    trace_ids = [r["trace_id"] for r in rows]
    if trace_ids:
        ph = ",".join("?"*len(trace_ids))
        llm = run(f"""SELECT trace_id, ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
            COALESCE(SUM(tokens_input),0) AS input_tokens,
            COALESCE(SUM(tokens_output),0) AS output_tokens
            FROM wide_llm_interactions_detail WHERE trace_id IN ({ph}) GROUP BY trace_id""", trace_ids)
        lmap = {r["trace_id"]: r for r in llm}
        for r in rows:
            lm = lmap.get(r["trace_id"], {})
            r["cost_usd"] = lm.get("cost_usd", 0)
            r["input_tokens"] = lm.get("input_tokens", 0)
            r["output_tokens"] = lm.get("output_tokens", 0)
    return {"rows": rows, "total": total[0]["n"] if total else 0}


@app.get("/api/traces/{trace_id}")
def trace_detail(trace_id: str, _user=Depends(require_auth)):
    return run("""SELECT trace_id, span_id, parent_span_id, span_name, span_kind,
        start_time, end_time, duration_ms, status_code, status_message,
        service_id AS service_name, agent_name, session_id AS conversation_id,
        model_id AS model, attributes_json
        FROM wide_spans_detail WHERE trace_id = ? ORDER BY start_time""", [trace_id])


# ─── Logs ──────────────────────────────────────────────────────────────────────

@app.get("/api/logs")
def logs(project: str | None = None, service: str | None = None, severity: str | None = None,
         time_range: str = "1h", start: str | None = None, end: str | None = None,
         page: int = 1, page_size: int = 50, _user=Depends(require_auth)):
    w, p, _, _ = build_scope(project, None, service, time_range, start, end, "timestamp", with_platform=False)
    if severity:
        w += " AND severity = ?"
        p.append(severity)
    total = run(f"SELECT COUNT(*) AS n FROM wide_logs_detail {w}", p)
    off = max(0, (page - 1) * page_size)
    rows = run(f"""SELECT timestamp, service_id AS service_name, environment, severity, message,
        trace_id, span_id, project_id FROM wide_logs_detail {w}
        ORDER BY timestamp DESC LIMIT ? OFFSET ?""", p + [page_size, off])
    return {"rows": rows, "total": total[0]["n"] if total else 0}


# ─── Metrics ───────────────────────────────────────────────────────────────────

@app.get("/api/metrics/catalog")
def metrics_catalog(project: str | None = None, service: str | None = None,
                    time_range: str = "1h", start: str | None = None, end: str | None = None,
                    _user=Depends(require_auth)):
    s, e = time_window(time_range, start, end)
    base = "FROM wide_metrics_detail WHERE timestamp BETWEEN ? AND ?"
    pa = [s, e]
    if project:
        base += " AND project_id = ?"
        pa.append(project)
    if service:
        base += " AND service_id = ?"
        pa.append(service)
    cats = [r["v"] for r in run(f"SELECT DISTINCT metric_type AS v {base} ORDER BY v", pa) if r["v"]]
    mtypes = [r["v"] for r in run(f"SELECT DISTINCT metric_name AS v {base} ORDER BY v", pa) if r["v"]]
    svcs = [r["v"] for r in run(f"SELECT DISTINCT service_id AS v {base} ORDER BY v", pa) if r["v"]]
    return {"categories": cats, "metric_types": mtypes, "services": svcs,
            "states": [], "readiness": [], "response_classes": []}


@app.get("/api/metrics/summary")
def metrics_summary(project: str | None = None, service: str | None = None,
                    time_range: str = "1h", start: str | None = None, end: str | None = None,
                    state: str | None = None, readiness: str | None = None, rclass: str | None = None,
                    _user=Depends(require_auth)):
    s, e = time_window(time_range, start, end)
    cl = ["timestamp BETWEEN ? AND ?"]
    pa = [s, e]
    if project:
        cl.append("project_id=?")
        pa.append(project)
    if service:
        cl.append("service_id=?")
        pa.append(service)
    w = " AND ".join(cl)
    r = run(f"""SELECT
        COALESCE(SUM(CASE WHEN metric_name='gen_ai.client.token.usage' THEN value_int ELSE 0 END), 0) AS total_requests,
        0.0 AS error_rate,
        ROUND(AVG(CASE WHEN metric_type='Histogram' THEN histogram_sum*1.0/NULLIF(histogram_count,0) END), 1) AS mean_latency_ms,
        0 AS peak_instances, 0 AS peak_cpu_pct, 0 AS peak_mem_pct,
        COUNT(DISTINCT service_id) AS services
        FROM wide_metrics_detail WHERE {w}""", pa)
    return r[0] if r else {}


@app.get("/api/metrics/timeseries")
def metrics_ts(category: str | None = None, group: str | None = None, agg: str | None = None,
               metric_type: str | None = None,
               project: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               **_kw):
    s, e = time_window(time_range, start, end)
    fmt = bucket_fmt(time_range)
    cl = ["timestamp BETWEEN ? AND ?"]
    pa = [s, e]
    if project:
        cl.append("project_id=?")
        pa.append(project)
    if service:
        cl.append("service_id=?")
        pa.append(service)
    if metric_type:
        cl.append("metric_name=?")
        pa.append(metric_type)
    if category:
        cl.append("metric_type=?")
        pa.append(category)
    w = " AND ".join(cl)
    grp = "service_id" if group != "none" else "'all'"
    agg_fn = "AVG" if (agg or "avg") == "avg" else ("SUM" if agg == "sum" else "MAX")
    return run(f"""SELECT strftime('{fmt}', timestamp) AS bucket,
        COALESCE({grp}, '—') AS k,
        ROUND({agg_fn}(COALESCE(value_int, value_double, histogram_sum)), 4) AS v
        FROM wide_metrics_detail WHERE {w}
        GROUP BY bucket, k ORDER BY bucket""", pa)


@app.get("/api/metrics")
def metrics_table(project: str | None = None, service: str | None = None,
                  time_range: str = "1h", start: str | None = None, end: str | None = None,
                  category: str | None = None, metric_type: str | None = None,
                  limit: int = 500, **_kw):
    s, e = time_window(time_range, start, end)
    cl = ["timestamp BETWEEN ? AND ?"]
    pa = [s, e]
    if project:
        cl.append("project_id=?")
        pa.append(project)
    if service:
        cl.append("service_id=?")
        pa.append(service)
    if metric_type:
        cl.append("metric_name=?")
        pa.append(metric_type)
    if category:
        cl.append("metric_type=?")
        pa.append(category)
    w = " AND ".join(cl)
    return run(f"""SELECT timestamp, service_id AS service_name, project_id, environment,
        metric_type AS category, metric_name AS metric_type,
        COALESCE(value_int, value_double, histogram_sum) AS value,
        NULL AS response_code, NULL AS response_code_class, NULL AS state, NULL AS readiness_status,
        histogram_count AS hist_count, histogram_min AS hist_min, histogram_max AS hist_max
        FROM wide_metrics_detail WHERE {w}
        ORDER BY timestamp DESC LIMIT ?""", pa + [limit])


# ─── Cost ──────────────────────────────────────────────────────────────────────

@app.get("/api/cost")
def cost(group_by: str = "service_name",
         project: str | None = None, platform: str | None = None, service: str | None = None,
         time_range: str = "1h", start: str | None = None, end: str | None = None,
         _user=Depends(require_auth)):
    allowed = {"service_name": "service_id", "model": "model_name", "project_id": "project_id",
               "source_platform": "environment"}
    if group_by not in allowed:
        raise HTTPException(400, f"group_by must be one of {sorted(allowed)}")
    col = allowed[group_by]
    s, e = time_window(time_range, start, end)
    cl = ["timestamp BETWEEN ? AND ?"]
    pa = [s, e]
    if project:
        cl.append("project_id=?")
        pa.append(project)
    if platform:
        cl.append("environment=?")
        pa.append(platform)
    if service:
        cl.append("service_id=?")
        pa.append(service)
    w = " AND ".join(cl)
    return run(f"""SELECT {col} AS key,
        ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
        COALESCE(SUM(tokens_input),0) AS input_tokens,
        COALESCE(SUM(tokens_output),0) AS output_tokens,
        COUNT(DISTINCT trace_id) AS traces
        FROM wide_llm_interactions_detail WHERE {w} AND cost IS NOT NULL
        GROUP BY key ORDER BY cost_usd DESC LIMIT 50""", pa)


# ─── Sessions ──────────────────────────────────────────────────────────────────

@app.get("/api/sessions")
def sessions(project: str | None = None, platform: str | None = None, service: str | None = None,
             time_range: str = "1h", start: str | None = None, end: str | None = None,
             limit: int = 200, _user=Depends(require_auth)):
    w, p, _, _ = build_scope(project, platform, service, time_range, start, end, "start_time")
    rows = run(f"""SELECT session_id AS conversation_id,
        MAX(service_id) AS service_name,
        COUNT(DISTINCT trace_id) AS turns,
        MIN(start_time) AS first_seen, MAX(end_time) AS last_seen
        FROM wide_spans_detail {w} AND session_id IS NOT NULL
        GROUP BY session_id ORDER BY last_seen DESC LIMIT ?""", p + [limit])
    # add cost/tokens
    sids = [r["conversation_id"] for r in rows]
    if sids:
        ph = ",".join("?"*len(sids))
        llm = run(f"""SELECT session_id, ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
            COALESCE(SUM(tokens_input),0)+COALESCE(SUM(tokens_output),0) AS tokens
            FROM wide_llm_interactions_detail WHERE session_id IN ({ph}) GROUP BY session_id""", sids)
        lmap = {r["session_id"]: r for r in llm}
        for r in rows:
            lm = lmap.get(r["conversation_id"], {})
            r["cost_usd"] = lm.get("cost_usd", 0)
            r["tokens"] = lm.get("tokens", 0)
    return rows


@app.get("/api/sessions/{conversation_id}")
def session_detail(conversation_id: str, _user=Depends(require_auth)):
    rows = run("""SELECT trace_id, MAX(service_id) AS service_name, MIN(start_time) AS start_time,
        MAX(CASE WHEN parent_span_id IS NULL THEN span_name END) AS root_span,
        MAX(CASE WHEN parent_span_id IS NULL THEN duration_ms END) AS duration_ms
        FROM wide_spans_detail WHERE session_id = ?
        GROUP BY trace_id ORDER BY start_time""", [conversation_id])
    trace_ids = [r["trace_id"] for r in rows]
    if trace_ids:
        ph = ",".join("?"*len(trace_ids))
        llm = run(f"""SELECT trace_id, ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
            COALESCE(SUM(tokens_input),0)+COALESCE(SUM(tokens_output),0) AS tokens
            FROM wide_llm_interactions_detail WHERE trace_id IN ({ph}) GROUP BY trace_id""", trace_ids)
        lmap = {r["trace_id"]: r for r in llm}
        for r in rows:
            lm = lmap.get(r["trace_id"], {})
            r["cost_usd"] = lm.get("cost_usd", 0)
            r["tokens"] = lm.get("tokens", 0)
    return rows


# ─── Tools ─────────────────────────────────────────────────────────────────────

@app.get("/api/tools")
def tools(project: str | None = None, platform: str | None = None, service: str | None = None,
          time_range: str = "1h", start: str | None = None, end: str | None = None,
          _user=Depends(require_auth)):
    s, e = time_window(time_range, start, end)
    cl = ["timestamp BETWEEN ? AND ?"]
    pa = [s, e]
    if platform:
        cl.append("environment=?")
        pa.append(platform)
    if service:
        cl.append("service_id=?")
        pa.append(service)
    w = " AND ".join(cl)
    return run(f"""SELECT tool_name AS tool, MAX(service_id) AS service_name,
        COUNT(*) AS calls,
        ROUND(AVG(latency_ms), 1) AS avg_ms,
        SUM(CASE WHEN status='ERROR' THEN 1 ELSE 0 END) AS errors
        FROM wide_tool_executions_detail WHERE {w}
        GROUP BY tool_name ORDER BY calls DESC LIMIT 50""", pa)


# ─── Search ────────────────────────────────────────────────────────────────────

@app.get("/api/search")
def search(q: str, _user=Depends(require_auth)):
    if len(q) < 2:
        return {}
    like = f"%{q}%"
    pre = f"{q}%"
    def one(sql, prm):
        return [r["v"] for r in run(sql, prm) if r["v"]]
    return {
        "projects": one("SELECT DISTINCT project_id AS v FROM wide_spans_detail WHERE project_id LIKE ? LIMIT 6", [like]),
        "services": one("SELECT DISTINCT service_id AS v FROM wide_spans_detail WHERE service_id LIKE ? LIMIT 6", [like]),
        "models": one("SELECT DISTINCT model_id AS v FROM wide_spans_detail WHERE model_id LIKE ? LIMIT 6", [like]),
        "traces": one("SELECT DISTINCT trace_id AS v FROM wide_spans_detail WHERE trace_id LIKE ? LIMIT 6", [pre]),
        "conversations": one("SELECT DISTINCT session_id AS v FROM wide_spans_detail WHERE session_id LIKE ? LIMIT 6", [like]),
    }


# ─── Insights ──────────────────────────────────────────────────────────────────

@app.get("/api/top/traces")
def top_traces(by: str = "cost",
               project: str | None = None, platform: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               limit: int = 20, _user=Depends(require_auth)):
    w, p, _, _ = build_scope(project, platform, service, time_range, start, end, "start_time")
    spans = run(f"""SELECT trace_id, MAX(service_id) AS service_name, MAX(agent_name) AS agent_name,
        MIN(start_time) AS start_time,
        MAX(CASE WHEN parent_span_id IS NULL THEN duration_ms END) AS duration_ms
        FROM wide_spans_detail {w} GROUP BY trace_id""", p)
    tids = [r["trace_id"] for r in spans]
    cost_map = {}
    if tids:
        ph = ",".join("?"*len(tids))
        llm = run(f"""SELECT trace_id, ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
            COALESCE(SUM(tokens_input),0)+COALESCE(SUM(tokens_output),0) AS tokens
            FROM wide_llm_interactions_detail WHERE trace_id IN ({ph}) GROUP BY trace_id""", tids)
        cost_map = {r["trace_id"]: r for r in llm}
    for r in spans:
        lm = cost_map.get(r["trace_id"], {})
        r["cost_usd"] = lm.get("cost_usd", 0)
        r["tokens"] = lm.get("tokens", 0)
    key = {"cost": "cost_usd", "latency": "duration_ms", "tokens": "tokens"}.get(by, "cost_usd")
    spans.sort(key=lambda r: r.get(key) or 0, reverse=True)
    return spans[:limit]


@app.get("/api/models")
def models(project: str | None = None, platform: str | None = None, service: str | None = None,
           time_range: str = "1h", start: str | None = None, end: str | None = None,
           _user=Depends(require_auth)):
    s, e = time_window(time_range, start, end)
    cl = ["timestamp BETWEEN ? AND ?"]
    pa = [s, e]
    if project:
        cl.append("project_id=?")
        pa.append(project)
    if platform:
        cl.append("environment=?")
        pa.append(platform)
    if service:
        cl.append("service_id=?")
        pa.append(service)
    w = " AND ".join(cl)
    return run(f"""SELECT model_name AS model, COUNT(*) AS calls,
        COUNT(DISTINCT trace_id) AS traces,
        COALESCE(SUM(tokens_input),0) AS input_tokens,
        COALESCE(SUM(tokens_output),0) AS output_tokens,
        ROUND(COALESCE(SUM(cost),0),6) AS cost_usd
        FROM wide_llm_interactions_detail WHERE {w} AND model_name IS NOT NULL
        GROUP BY model_name ORDER BY cost_usd DESC""", pa)


@app.get("/api/errors/by-service")
def errors_by_service(project: str | None = None, platform: str | None = None, service: str | None = None,
                      time_range: str = "1h", start: str | None = None, end: str | None = None,
                      _user=Depends(require_auth)):
    w, p, _, _ = build_scope(project, platform, service, time_range, start, end, "start_time")
    return run(f"""SELECT service_id AS service_name, COUNT(*) AS spans,
        SUM(CASE WHEN status_code='ERROR' THEN 1 ELSE 0 END) AS errors,
        ROUND(CAST(SUM(CASE WHEN status_code='ERROR' THEN 1 ELSE 0 END) AS REAL)/NULLIF(COUNT(*),0), 4) AS error_rate
        FROM wide_spans_detail {w}
        GROUP BY service_id HAVING errors > 0 ORDER BY errors DESC""", p)


@app.get("/api/errors/top")
def errors_top(project: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               _user=Depends(require_auth)):
    w, p, _, _ = build_scope(project, None, service, time_range, start, end, "timestamp", with_platform=False)
    return run(f"""SELECT message, MAX(service_id) AS service_name, COUNT(*) AS occurrences,
        MAX(timestamp) AS last_seen
        FROM wide_logs_detail {w} AND severity IN ('ERROR','FATAL') AND message IS NOT NULL
        GROUP BY message ORDER BY occurrences DESC LIMIT 30""", p)


@app.get("/api/health")
def health_services(_user=Depends(require_auth)):
    now = datetime.now(tz=timezone.utc)
    lookback = (now - timedelta(hours=48)).isoformat()
    rows = run("""SELECT service_id AS service_name, MAX(environment) AS platform,
        MAX(project_id) AS project_id, MAX(start_time) AS last_seen,
        COUNT(DISTINCT trace_id) AS traces_48h,
        ROUND(CAST(SUM(CASE WHEN status_code='ERROR' THEN 1 ELSE 0 END) AS REAL)/NULLIF(COUNT(*),0), 4) AS error_rate
        FROM wide_spans_detail WHERE start_time >= ?
        GROUP BY service_id ORDER BY last_seen DESC""", [lookback])
    # add minutes_since and cost_48h
    sids = [r["service_name"] for r in rows]
    cost_map = {}
    if sids:
        ph = ",".join("?"*len(sids))
        llm = run(f"""SELECT service_id, ROUND(COALESCE(SUM(cost),0),6) AS cost_48h
            FROM wide_llm_interactions_detail WHERE timestamp >= ? AND service_id IN ({ph})
            GROUP BY service_id""", [lookback] + sids)
        cost_map = {r["service_id"]: r["cost_48h"] for r in llm}
    for r in rows:
        if r["last_seen"]:
            try:
                last = datetime.fromisoformat(r["last_seen"].replace("Z", "+00:00"))
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                r["minutes_since"] = int((now - last).total_seconds() / 60)
            except Exception:
                r["minutes_since"] = 0
        else:
            r["minutes_since"] = 0
        r["cost_48h"] = cost_map.get(r["service_name"], 0)
    return rows


# ─── Meta / refresh ────────────────────────────────────────────────────────────

@app.get("/api/meta/last-refresh")
def last_refresh(_user=Depends(require_auth)):
    out = {}
    for name, tbl, col in (("spans", "wide_spans_detail", "start_time"),
                           ("logs", "wide_logs_detail", "timestamp"),
                           ("metrics", "wide_metrics_detail", "timestamp")):
        try:
            r = run(f"SELECT MAX({col}) AS t FROM {tbl}")
            out[name] = r[0]["t"] if r else None
        except Exception:
            out[name] = None
    return out


@app.post("/api/refresh/pipeline")
def refresh_pipeline(_user=Depends(require_auth)):
    return {"started": True, "execution": "local-mock-execution"}


@app.get("/api/refresh/status")
def refresh_status(execution: str, _user=Depends(require_auth)):
    return {"state": "SUCCEEDED"}
