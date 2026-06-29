"""
Cloud (BigQuery) FastAPI app — serves the dashboard frontend's GET API
contract against the obswebapp `wide_*` schema in `<GCP_PROJECT>.<BQ_DATASET>`.

Activated when APP_ENV=cloud. See server.py dispatcher.

The endpoint contract is identical to local_app.py (SQLite); only the SQL
dialect and table names change:

  • cds_otel.wide_spans_detail              (mapped to dashboard "spans")
  • cds_otel.wide_logs_detail               (mapped to "logs")
  • cds_otel.wide_metrics_detail            (mapped to "metrics")
  • cds_otel.wide_llm_interactions_detail   (cost + tokens, joined by trace_id)
  • cds_otel.wide_sessions_detail           (sessions)
  • cds_otel.wide_tool_executions_detail    (tools)
  • <project>.config_ds.llm_pricing         (pricing CRUD — best-effort)
"""
import datetime
import os
from pathlib import Path

import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from google.cloud import bigquery


# ─── config ───────────────────────────────────────────────────────────────────

PROJECT    = os.environ.get("GCP_PROJECT", "oa-apmena-observability-dv")
BQ_DATASET = os.environ.get("BQ_DATASET",  "cds_otel")

SPANS    = f"`{PROJECT}.{BQ_DATASET}.wide_spans_detail`"
LOGS     = f"`{PROJECT}.{BQ_DATASET}.wide_logs_detail`"
METRICS  = f"`{PROJECT}.{BQ_DATASET}.wide_metrics_detail`"
LLM      = f"`{PROJECT}.{BQ_DATASET}.wide_llm_interactions_detail`"
SESSIONS = f"`{PROJECT}.{BQ_DATASET}.wide_sessions_detail`"
TOOLS    = f"`{PROJECT}.{BQ_DATASET}.wide_tool_executions_detail`"
PRICING  = f"`{PROJECT}.config_ds.llm_pricing`"

WORKFLOW_LOCATION = os.environ.get("WORKFLOW_LOCATION", "us-central1")
WORKFLOW_NAME     = os.environ.get("WORKFLOW_NAME", "obs-pipeline")

ADMIN_USER       = os.environ.get("ADMIN_USER", "admin1")
ADMIN_PASS       = os.environ.get("ADMIN_PASS", "pwd1")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
ALLOWED_DOMAIN   = os.environ.get("ALLOWED_DOMAIN", "loreal.com")
JWT_SECRET       = os.environ.get("JWT_SECRET", "change-me-dev-secret")
JWT_TTL_HOURS    = int(os.environ.get("JWT_TTL_HOURS", "12"))
CORS_ORIGINS     = os.environ.get("CORS_ORIGINS", "*").split(",")

TIME_PRESETS = {"5m": 5, "10m": 10, "30m": 30, "1h": 60,
                "6h": 360, "12h": 720, "1d": 1440, "7d": 10080, "30d": 43200}


# ─── BigQuery client ──────────────────────────────────────────────────────────

_client: bigquery.Client | None = None


def client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=PROJECT)
    return _client


def run(sql: str, params: list | None = None) -> list[dict]:
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    rows = client().query(sql, job_config=job_config).result()
    out = []
    for r in rows:
        d = {}
        for k, v in dict(r).items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                d[k] = v.isoformat()
            elif isinstance(v, list):
                d[k] = [x.isoformat() if isinstance(x, (datetime.datetime, datetime.date)) else x for x in v]
            else:
                d[k] = v
        out.append(d)
    return out


# ─── filter / time helpers ────────────────────────────────────────────────────

def time_window(time_range: str | None, start: str | None, end: str | None):
    now = datetime.datetime.now(datetime.timezone.utc)
    if time_range == "custom" and start and end:
        return start, end
    minutes = TIME_PRESETS.get(time_range or "1h", 60)
    return (now - datetime.timedelta(minutes=minutes)).isoformat(), now.isoformat()


def time_clause(col: str, start_ts: str, end_ts: str):
    return (f"{col} BETWEEN @start_ts AND @end_ts",
            [bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", start_ts),
             bigquery.ScalarQueryParameter("end_ts",   "TIMESTAMP", end_ts)])


def _multi(col: str, val: str | None, name: str, params: list):
    vals = [v for v in (val.split(",") if val else []) if v]
    if not vals:
        return None
    if len(vals) == 1:
        params.append(bigquery.ScalarQueryParameter(name, "STRING", vals[0]))
        return f"{col} = @{name}"
    params.append(bigquery.ArrayQueryParameter(name, "STRING", vals))
    return f"{col} IN UNNEST(@{name})"


def dim_filters(project=None, platform=None, service=None, *, with_platform=True):
    """Build WHERE clauses against wide_spans_detail naming:
       service_name → service_id, source_platform → environment."""
    clauses, params = [], []
    if project:
        clauses.append("project_id = @project")
        params.append(bigquery.ScalarQueryParameter("project", "STRING", project))
    if with_platform:
        c = _multi("environment", platform, "platform", params)
        if c:
            clauses.append(c)
    c = _multi("service_id", service, "service", params)
    if c:
        clauses.append(c)
    return clauses, params


def _where(*clause_lists) -> str:
    parts = [c for lst in clause_lists for c in (lst or [])]
    return ("WHERE " + " AND ".join(parts)) if parts else ""


def _bucket(time_range: str | None) -> str:
    mins = TIME_PRESETS.get(time_range or "1h", 60)
    if mins <= 60:
        return "MINUTE"
    if mins <= 1440:
        return "HOUR"
    return "DAY"


def scope(project, platform, service, time_range, start, end, time_col, with_platform=True):
    s, e = time_window(time_range, start, end)
    tcl, tp = time_clause(time_col, s, e)
    dcl, dp = dim_filters(project, platform, service, with_platform=with_platform)
    return _where([tcl], dcl), tp + dp, s, e


# ─── auth ─────────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def make_token(username: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return jwt.encode({"sub": username, "iat": now,
                       "exp": now + datetime.timedelta(hours=JWT_TTL_HOURS)},
                      JWT_SECRET, algorithm="HS256")


def login(username: str, password: str) -> str:
    if username == ADMIN_USER and password == ADMIN_PASS:
        return make_token(username)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")


def require_auth(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")
    try:
        return jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid/expired token")


# ─── app ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Central Observability API (BigQuery · wide_*)")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ----- public probes & auth ---------------------------------------------------

@app.get("/api/health")
def health_public():
    return {"status": "ok"}


class Creds(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def do_login(c: Creds):
    return {"token": login(c.username, c.password), "user": c.username}


@app.get("/api/config")
def public_config():
    return {"google_client_id": GOOGLE_CLIENT_ID, "allowed_domain": ALLOWED_DOMAIN}


@app.get("/api/auth/iap")
def auth_iap(request: Request):
    raw = request.headers.get("X-Goog-Authenticated-User-Email", "")
    email = raw.split(":")[-1].lower() if raw else ""
    if not email:
        raise HTTPException(401, "no IAP identity")
    if ALLOWED_DOMAIN and not email.endswith("@" + ALLOWED_DOMAIN):
        raise HTTPException(403, f"only {ALLOWED_DOMAIN} accounts allowed")
    return {"token": make_token(email), "user": email}


# ----- pricing (best-effort: succeeds only if config_ds.llm_pricing exists) --

@app.get("/api/config/pricing")
def list_pricing(user=Depends(require_auth)):
    try:
        return run(f"""
            SELECT id, model_prefix,
                   input_cost_per_1m_tokens  AS input_cost,
                   output_cost_per_1m_tokens AS output_cost,
                   active, updated_at
            FROM {PRICING}
            ORDER BY model_prefix, active DESC, updated_at DESC
        """)
    except Exception:
        return []


class PriceIn(BaseModel):
    model_prefix: str
    input_cost: float
    output_cost: float
    active: bool = True
    force: bool = False


@app.post("/api/config/pricing")
def add_pricing(p: PriceIn, user=Depends(require_auth)):
    prefix = (p.model_prefix or "").strip()
    if not prefix:
        raise HTTPException(400, "model name is required")
    mp = bigquery.ScalarQueryParameter("m", "STRING", prefix)
    if p.active:
        dup = run(f"SELECT COUNT(*) AS n FROM {PRICING} WHERE model_prefix=@m AND active", [mp])
        if dup and dup[0]["n"] > 0 and not p.force:
            raise HTTPException(409, f"An active price for '{prefix}' already exists.")
        if p.force:
            run(f"UPDATE {PRICING} SET active=FALSE, updated_at=CURRENT_TIMESTAMP() "
                f"WHERE model_prefix=@m AND active", [mp])
    run(f"""
        INSERT INTO {PRICING} (id, model_prefix, input_cost_per_1m_tokens, output_cost_per_1m_tokens, active, updated_at)
        VALUES (GENERATE_UUID(), @m, CAST(@i AS NUMERIC), CAST(@o AS NUMERIC), @a, CURRENT_TIMESTAMP())
    """, [mp, bigquery.ScalarQueryParameter("i", "FLOAT64", p.input_cost),
              bigquery.ScalarQueryParameter("o", "FLOAT64", p.output_cost),
              bigquery.ScalarQueryParameter("a", "BOOL", p.active)])
    return {"ok": True}


class PricePatch(BaseModel):
    active: bool | None = None
    input_cost: float | None = None
    output_cost: float | None = None


@app.patch("/api/config/pricing/{pid}")
def patch_pricing(pid: str, p: PricePatch, user=Depends(require_auth)):
    sets, params = [], [bigquery.ScalarQueryParameter("id", "STRING", pid)]
    if p.active is not None:
        sets.append("active=@a")
        params.append(bigquery.ScalarQueryParameter("a", "BOOL", p.active))
    if p.input_cost is not None:
        sets.append("input_cost_per_1m_tokens=CAST(@i AS NUMERIC)")
        params.append(bigquery.ScalarQueryParameter("i", "FLOAT64", p.input_cost))
    if p.output_cost is not None:
        sets.append("output_cost_per_1m_tokens=CAST(@o AS NUMERIC)")
        params.append(bigquery.ScalarQueryParameter("o", "FLOAT64", p.output_cost))
    if not sets:
        raise HTTPException(400, "nothing to update")
    sets.append("updated_at=CURRENT_TIMESTAMP()")
    run(f"UPDATE {PRICING} SET {', '.join(sets)} WHERE id=@id", params)
    return {"ok": True}


# ----- filters ----------------------------------------------------------------

@app.get("/api/filters/projects")
def projects(user=Depends(require_auth)):
    return run(f"SELECT DISTINCT project_id FROM {SPANS} "
               f"WHERE project_id IS NOT NULL ORDER BY project_id")


@app.get("/api/filters/platforms")
def platforms(project: str | None = None, user=Depends(require_auth)):
    cl, p = dim_filters(project, None, None, with_platform=False)
    return run(f"SELECT DISTINCT environment AS source_platform FROM {SPANS} {_where(cl)} "
               f"{'AND' if cl else 'WHERE'} environment IS NOT NULL ORDER BY source_platform", p)


@app.get("/api/filters/services")
def services(project: str | None = None, platform: str | None = None, user=Depends(require_auth)):
    cl, p = dim_filters(project, platform, None)
    return run(f"SELECT DISTINCT service_id AS service_name FROM {SPANS} {_where(cl)} "
               f"{'AND' if cl else 'WHERE'} service_id IS NOT NULL ORDER BY service_name", p)


# ----- overview ---------------------------------------------------------------

def _llm_window(s: str, e: str, project, platform, service):
    """WHERE conditions for wide_llm_interactions_detail in the same window."""
    cl = ["timestamp BETWEEN @start_ts AND @end_ts"]
    params = [bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", s),
              bigquery.ScalarQueryParameter("end_ts",   "TIMESTAMP", e)]
    if project:
        cl.append("project_id = @project")
        params.append(bigquery.ScalarQueryParameter("project", "STRING", project))
    if platform:
        plats = [p for p in platform.split(",") if p]
        if len(plats) == 1:
            cl.append("environment = @platform")
            params.append(bigquery.ScalarQueryParameter("platform", "STRING", plats[0]))
        elif plats:
            cl.append("environment IN UNNEST(@platforms)")
            params.append(bigquery.ArrayQueryParameter("platforms", "STRING", plats))
    if service:
        svs = [v for v in service.split(",") if v]
        if len(svs) == 1:
            cl.append("service_id = @service")
            params.append(bigquery.ScalarQueryParameter("service", "STRING", svs[0]))
        elif svs:
            cl.append("service_id IN UNNEST(@services)")
            params.append(bigquery.ArrayQueryParameter("services", "STRING", svs))
    return " AND ".join(cl), params


@app.get("/api/overview")
def overview(project: str | None = None, platform: str | None = None, service: str | None = None,
             time_range: str = "1h", start: str | None = None, end: str | None = None,
             user=Depends(require_auth)):
    w, p, s, e = scope(project, platform, service, time_range, start, end, "start_time")
    span_kpi = run(f"""
        SELECT
          COUNT(DISTINCT trace_id) AS traces,
          COUNT(*)                 AS spans,
          COUNT(DISTINCT service_id) AS services,
          COUNT(DISTINCT project_id) AS projects,
          ROUND(SAFE_DIVIDE(COUNTIF(status_code='ERROR'), COUNT(*)), 4) AS error_rate,
          ROUND(APPROX_QUANTILES(IF(parent_span_id IS NULL, duration_ms, NULL), 100)[OFFSET(50)],1) AS p50_ms,
          ROUND(APPROX_QUANTILES(IF(parent_span_id IS NULL, duration_ms, NULL), 100)[OFFSET(95)],1) AS p95_ms
        FROM {SPANS} {w}
    """, p)
    llm_w, llm_p = _llm_window(s, e, project, platform, service)
    llm_kpi = run(f"""
        SELECT
          ROUND(COALESCE(SUM(cost), 0), 6) AS cost_usd,
          COALESCE(SUM(tokens_input),  0)  AS input_tokens,
          COALESCE(SUM(tokens_output), 0)  AS output_tokens
        FROM {LLM}
        WHERE {llm_w}
    """, llm_p)
    return {"range": {"start": s, "end": e},
            "kpis": {**(span_kpi[0] if span_kpi else {}),
                     **(llm_kpi[0]  if llm_kpi  else {})}}


@app.get("/api/overview/timeseries")
def overview_ts(project: str | None = None, platform: str | None = None, service: str | None = None,
                time_range: str = "1h", start: str | None = None, end: str | None = None,
                user=Depends(require_auth)):
    w, p, s, e = scope(project, platform, service, time_range, start, end, "start_time")
    b = _bucket(time_range)
    spans = run(f"""
        SELECT TIMESTAMP_TRUNC(start_time, {b}) AS bucket,
               COUNT(DISTINCT trace_id)         AS traces,
               COUNTIF(status_code='ERROR')     AS errors
        FROM {SPANS} {w}
        GROUP BY bucket
    """, p)
    llm_w, llm_p = _llm_window(s, e, project, platform, service)
    llm = run(f"""
        SELECT TIMESTAMP_TRUNC(timestamp, {b}) AS bucket,
               ROUND(COALESCE(SUM(cost),0),6)  AS cost_usd,
               COALESCE(SUM(tokens_input), 0)  AS input_tokens,
               COALESCE(SUM(tokens_output), 0) AS output_tokens
        FROM {LLM}
        WHERE {llm_w}
        GROUP BY bucket
    """, llm_p)
    lmap = {r["bucket"]: r for r in llm}
    out = []
    for r in spans:
        b2 = r["bucket"]
        lr = lmap.get(b2, {})
        out.append({**r,
                    "cost_usd": lr.get("cost_usd", 0),
                    "input_tokens": lr.get("input_tokens", 0),
                    "output_tokens": lr.get("output_tokens", 0)})
    return sorted(out, key=lambda r: r["bucket"])


@app.get("/api/latency/timeseries")
def latency_ts(project: str | None = None, platform: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    b = _bucket(time_range)
    return run(f"""
        SELECT TIMESTAMP_TRUNC(start_time, {b}) AS bucket,
               ROUND(APPROX_QUANTILES(IF(parent_span_id IS NULL, duration_ms, NULL), 100)[OFFSET(50)],1) AS p50_ms,
               ROUND(APPROX_QUANTILES(IF(parent_span_id IS NULL, duration_ms, NULL), 100)[OFFSET(95)],1) AS p95_ms
        FROM {SPANS} {w}
        GROUP BY bucket ORDER BY bucket
    """, p)


# ----- traces -----------------------------------------------------------------

@app.get("/api/traces")
def traces(project: str | None = None, platform: str | None = None, service: str | None = None,
           time_range: str = "1h", start: str | None = None, end: str | None = None,
           page: int = 1, page_size: int = 50, user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    total = run(f"SELECT COUNT(*) AS n FROM (SELECT trace_id FROM {SPANS} {w} GROUP BY trace_id)", p)
    off = (max(1, page) - 1) * page_size
    rows = run(f"""
        SELECT trace_id,
               ANY_VALUE(service_id)   AS service_name,
               ANY_VALUE(project_id)   AS project_id,
               ANY_VALUE(environment)  AS source_platform,
               ANY_VALUE(agent_name)   AS agent_name,
               MIN(start_time)         AS start_time,
               MAX(IF(parent_span_id IS NULL, span_name, NULL))   AS root_span,
               MAX(IF(parent_span_id IS NULL, duration_ms, NULL)) AS duration_ms,
               MAX(IF(parent_span_id IS NULL, status_code, NULL)) AS status_code,
               ANY_VALUE(session_id)   AS conversation_id,
               COUNT(*)                AS spans
        FROM {SPANS} {w}
        GROUP BY trace_id ORDER BY start_time DESC
        LIMIT {int(page_size)} OFFSET {int(off)}
    """, p)
    if rows:
        tids = [r["trace_id"] for r in rows]
        llm = run(f"""
            SELECT trace_id,
                   ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
                   COALESCE(SUM(tokens_input),0)  AS input_tokens,
                   COALESCE(SUM(tokens_output),0) AS output_tokens
            FROM {LLM}
            WHERE trace_id IN UNNEST(@tids)
            GROUP BY trace_id
        """, [bigquery.ArrayQueryParameter("tids", "STRING", tids)])
        lmap = {r["trace_id"]: r for r in llm}
        for r in rows:
            lr = lmap.get(r["trace_id"], {})
            r["cost_usd"] = lr.get("cost_usd", 0)
            r["input_tokens"] = lr.get("input_tokens", 0)
            r["output_tokens"] = lr.get("output_tokens", 0)
    return {"rows": rows, "total": (total[0]["n"] if total else 0)}


@app.get("/api/traces/{trace_id}")
def trace_detail(trace_id: str, user=Depends(require_auth)):
    # 30-day lookback so partitioned tables with require_partition_filter=true
    # still accept the query. trace_id is the actual selector.
    lookback = (datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(days=30)).isoformat()
    params = [
        bigquery.ScalarQueryParameter("tid", "STRING", trace_id),
        bigquery.ScalarQueryParameter("since", "TIMESTAMP", lookback),
    ]
    return run(f"""
        SELECT trace_id, span_id, parent_span_id, span_name, span_kind,
               start_time, end_time, duration_ms, status_code, status_message,
               service_id  AS service_name, agent_name,
               session_id  AS conversation_id, model_id AS model
        FROM {SPANS}
        WHERE start_time >= @since AND trace_id = @tid
        ORDER BY start_time
    """, params)


# ----- logs -------------------------------------------------------------------

@app.get("/api/logs")
def logs(project: str | None = None, service: str | None = None, severity: str | None = None,
         time_range: str = "1h", start: str | None = None, end: str | None = None,
         page: int = 1, page_size: int = 50, user=Depends(require_auth)):
    s, e = time_window(time_range, start, end)
    cl, params = ["timestamp BETWEEN @start_ts AND @end_ts"], [
        bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", s),
        bigquery.ScalarQueryParameter("end_ts",   "TIMESTAMP", e),
    ]
    if project:
        cl.append("project_id = @project")
        params.append(bigquery.ScalarQueryParameter("project", "STRING", project))
    if service:
        cl.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))
    if severity:
        cl.append("severity = @sev")
        params.append(bigquery.ScalarQueryParameter("sev", "STRING", severity))
    where = "WHERE " + " AND ".join(cl)
    total = run(f"SELECT COUNT(*) AS n FROM {LOGS} {where}", params)
    off = (max(1, page) - 1) * page_size
    rows = run(f"""
        SELECT timestamp, service_id AS service_name, environment, severity, message,
               trace_id, span_id, project_id
        FROM {LOGS} {where}
        ORDER BY timestamp DESC
        LIMIT {int(page_size)} OFFSET {int(off)}
    """, params)
    return {"rows": rows, "total": (total[0]["n"] if total else 0)}


# ----- metrics ----------------------------------------------------------------

def _metric_scope(project, service, time_range, start, end,
                  category=None, metric_type=None):
    s, e = time_window(time_range, start, end)
    cl = ["timestamp BETWEEN @start_ts AND @end_ts"]
    params = [bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", s),
              bigquery.ScalarQueryParameter("end_ts",   "TIMESTAMP", e)]
    if project:
        cl.append("project_id = @project")
        params.append(bigquery.ScalarQueryParameter("project", "STRING", project))
    if service:
        cl.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))
    if category:
        cl.append("metric_type = @cat")
        params.append(bigquery.ScalarQueryParameter("cat", "STRING", category))
    if metric_type:
        cl.append("metric_name = @mt")
        params.append(bigquery.ScalarQueryParameter("mt", "STRING", metric_type))
    return "WHERE " + " AND ".join(cl), params, s, e


@app.get("/api/metrics/catalog")
def metrics_catalog(project: str | None = None, service: str | None = None,
                    time_range: str = "1h", start: str | None = None, end: str | None = None,
                    user=Depends(require_auth)):
    w, p, _, _ = _metric_scope(project, service, time_range, start, end)
    r = run(f"""
        SELECT
          ARRAY_AGG(DISTINCT metric_type IGNORE NULLS ORDER BY metric_type) AS categories,
          ARRAY_AGG(DISTINCT metric_name IGNORE NULLS ORDER BY metric_name) AS metric_types,
          ARRAY_AGG(DISTINCT service_id  IGNORE NULLS ORDER BY service_id)  AS services
        FROM {METRICS} {w}
    """, p)
    out = r[0] if r else {}
    out.setdefault("states", [])
    out.setdefault("readiness", [])
    out.setdefault("response_classes", [])
    return out


@app.get("/api/metrics/summary")
def metrics_summary(project: str | None = None, service: str | None = None,
                    time_range: str = "1h", start: str | None = None, end: str | None = None,
                    state: str | None = None, readiness: str | None = None, rclass: str | None = None,
                    user=Depends(require_auth)):
    w, p, _, _ = _metric_scope(project, service, time_range, start, end)
    r = run(f"""
        SELECT
          COALESCE(SUM(CASE WHEN metric_name='gen_ai.client.token.usage' THEN value_int ELSE 0 END), 0) AS total_requests,
          0.0 AS error_rate,
          ROUND(AVG(CASE WHEN metric_type='Histogram' THEN SAFE_DIVIDE(histogram_sum, histogram_count) END), 1) AS mean_latency_ms,
          0 AS peak_instances, 0 AS peak_cpu_pct, 0 AS peak_mem_pct,
          COUNT(DISTINCT service_id) AS services
        FROM {METRICS} {w}
    """, p)
    return r[0] if r else {}


@app.get("/api/metrics/timeseries")
def metrics_ts(category: str | None = None, group: str | None = None, agg: str | None = None,
               metric_type: str | None = None,
               project: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               user=Depends(require_auth)):
    w, p, _, _ = _metric_scope(project, service, time_range, start, end, category, metric_type)
    b = _bucket(time_range)
    grp_col = "service_id" if group != "none" else "'all'"
    agg_fn = {"sum": "SUM", "avg": "AVG", "max": "MAX"}.get(agg or "avg", "AVG")
    return run(f"""
        SELECT TIMESTAMP_TRUNC(timestamp, {b}) AS bucket,
               COALESCE(CAST({grp_col} AS STRING), '—') AS k,
               ROUND({agg_fn}(COALESCE(value_int, value_double, histogram_sum)), 4) AS v
        FROM {METRICS} {w}
        GROUP BY bucket, k ORDER BY bucket
    """, p)


@app.get("/api/metrics")
def metrics_table(project: str | None = None, service: str | None = None,
                  time_range: str = "1h", start: str | None = None, end: str | None = None,
                  category: str | None = None, metric_type: str | None = None,
                  limit: int = 500, user=Depends(require_auth)):
    w, p, _, _ = _metric_scope(project, service, time_range, start, end, category, metric_type)
    return run(f"""
        SELECT timestamp, service_id AS service_name, project_id, environment,
               metric_type AS category, metric_name AS metric_type,
               COALESCE(value_int, value_double, histogram_sum) AS value,
               CAST(NULL AS STRING) AS response_code, CAST(NULL AS STRING) AS response_code_class,
               CAST(NULL AS STRING) AS state,         CAST(NULL AS STRING) AS readiness_status,
               histogram_count AS hist_count, histogram_min AS hist_min, histogram_max AS hist_max
        FROM {METRICS} {w}
        ORDER BY timestamp DESC LIMIT {int(limit)}
    """, p)


# ----- cost / sessions / tools / search / insights ---------------------------

@app.get("/api/cost")
def cost(group_by: str = "service_name",
         project: str | None = None, platform: str | None = None, service: str | None = None,
         time_range: str = "1h", start: str | None = None, end: str | None = None,
         user=Depends(require_auth)):
    allowed = {"service_name": "service_id", "model": "model_name",
               "project_id": "project_id", "source_platform": "environment"}
    if group_by not in allowed:
        raise HTTPException(400, f"group_by must be one of {sorted(allowed)}")
    col = allowed[group_by]
    s, e = time_window(time_range, start, end)
    llm_w, llm_p = _llm_window(s, e, project, platform, service)
    return run(f"""
        SELECT {col} AS key,
               ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
               COALESCE(SUM(tokens_input),0)  AS input_tokens,
               COALESCE(SUM(tokens_output),0) AS output_tokens,
               COUNT(DISTINCT trace_id)       AS traces
        FROM {LLM}
        WHERE {llm_w} AND cost IS NOT NULL
        GROUP BY key ORDER BY cost_usd DESC LIMIT 50
    """, llm_p)


@app.get("/api/sessions")
def sessions_list(project: str | None = None, platform: str | None = None, service: str | None = None,
                  time_range: str = "1h", start: str | None = None, end: str | None = None,
                  limit: int = 200, user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    rows = run(f"""
        SELECT session_id AS conversation_id,
               ANY_VALUE(service_id)    AS service_name,
               COUNT(DISTINCT trace_id) AS turns,
               MIN(start_time) AS first_seen, MAX(end_time) AS last_seen
        FROM {SPANS} {w} {'AND' if w else 'WHERE'} session_id IS NOT NULL
        GROUP BY session_id ORDER BY last_seen DESC LIMIT {int(limit)}
    """, p)
    if rows:
        sids = [r["conversation_id"] for r in rows]
        llm = run(f"""
            SELECT session_id,
                   ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
                   COALESCE(SUM(tokens_input),0)+COALESCE(SUM(tokens_output),0) AS tokens
            FROM {LLM}
            WHERE session_id IN UNNEST(@sids)
            GROUP BY session_id
        """, [bigquery.ArrayQueryParameter("sids", "STRING", sids)])
        lmap = {r["session_id"]: r for r in llm}
        for r in rows:
            lm = lmap.get(r["conversation_id"], {})
            r["cost_usd"] = lm.get("cost_usd", 0)
            r["tokens"] = lm.get("tokens", 0)
    return rows


@app.get("/api/sessions/{conversation_id}")
def session_detail(conversation_id: str, user=Depends(require_auth)):
    rows = run(f"""
        SELECT trace_id, ANY_VALUE(service_id) AS service_name, MIN(start_time) AS start_time,
               MAX(IF(parent_span_id IS NULL, span_name, NULL)) AS root_span,
               MAX(IF(parent_span_id IS NULL, duration_ms, NULL)) AS duration_ms
        FROM {SPANS} WHERE session_id = @cid
        GROUP BY trace_id ORDER BY start_time
    """, [bigquery.ScalarQueryParameter("cid", "STRING", conversation_id)])
    if rows:
        tids = [r["trace_id"] for r in rows]
        llm = run(f"""
            SELECT trace_id,
                   ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
                   COALESCE(SUM(tokens_input),0)+COALESCE(SUM(tokens_output),0) AS tokens
            FROM {LLM}
            WHERE trace_id IN UNNEST(@tids)
            GROUP BY trace_id
        """, [bigquery.ArrayQueryParameter("tids", "STRING", tids)])
        lmap = {r["trace_id"]: r for r in llm}
        for r in rows:
            lm = lmap.get(r["trace_id"], {})
            r["cost_usd"] = lm.get("cost_usd", 0)
            r["tokens"] = lm.get("tokens", 0)
    return rows


@app.get("/api/tools")
def tools(project: str | None = None, platform: str | None = None, service: str | None = None,
          time_range: str = "1h", start: str | None = None, end: str | None = None,
          user=Depends(require_auth)):
    s, e = time_window(time_range, start, end)
    cl, params = ["timestamp BETWEEN @start_ts AND @end_ts"], [
        bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", s),
        bigquery.ScalarQueryParameter("end_ts",   "TIMESTAMP", e),
    ]
    if project:
        cl.append("trace_id IN (SELECT trace_id FROM {SPANS} WHERE project_id = @project)".format(SPANS=SPANS))
        params.append(bigquery.ScalarQueryParameter("project", "STRING", project))
    if platform:
        cl.append("environment = @platform")
        params.append(bigquery.ScalarQueryParameter("platform", "STRING", platform))
    if service:
        cl.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))
    where = "WHERE " + " AND ".join(cl)
    return run(f"""
        SELECT tool_name AS tool,
               ANY_VALUE(service_id) AS service_name,
               COUNT(*) AS calls,
               ROUND(AVG(latency_ms),1) AS avg_ms,
               COUNTIF(status='ERROR') AS errors
        FROM {TOOLS} {where}
        GROUP BY tool_name ORDER BY calls DESC LIMIT 50
    """, params)


@app.get("/api/search")
def search(q: str, user=Depends(require_auth)):
    if not q or len(q) < 2:
        return {}
    recent = "start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)"
    like = bigquery.ScalarQueryParameter("like", "STRING", f"%{q}%")
    pre  = bigquery.ScalarQueryParameter("pre",  "STRING", f"{q}%")

    def one(sql: str, prm: list) -> list:
        return [r["v"] for r in run(sql, prm) if r["v"]]
    return {
        "projects":      one(f"SELECT DISTINCT project_id AS v FROM {SPANS} WHERE {recent} AND project_id LIKE @like LIMIT 6", [like]),
        "services":      one(f"SELECT DISTINCT service_id AS v FROM {SPANS} WHERE {recent} AND service_id LIKE @like LIMIT 6", [like]),
        "models":        one(f"SELECT DISTINCT model_id  AS v FROM {SPANS} WHERE {recent} AND model_id  LIKE @like LIMIT 6", [like]),
        "traces":        one(f"SELECT DISTINCT trace_id  AS v FROM {SPANS} WHERE {recent} AND STARTS_WITH(trace_id, @pre) LIMIT 6", [pre]),
        "conversations": one(f"SELECT DISTINCT session_id AS v FROM {SPANS} WHERE {recent} AND session_id LIKE @like LIMIT 6", [like]),
    }


@app.get("/api/top/traces")
def top_traces(by: str = "cost",
               project: str | None = None, platform: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               limit: int = 20, user=Depends(require_auth)):
    w, p, s, e = scope(project, platform, service, time_range, start, end, "start_time")
    spans = run(f"""
        SELECT trace_id,
               ANY_VALUE(service_id) AS service_name,
               ANY_VALUE(agent_name) AS agent_name,
               MIN(start_time) AS start_time,
               MAX(IF(parent_span_id IS NULL, duration_ms, NULL)) AS duration_ms
        FROM {SPANS} {w}
        GROUP BY trace_id
    """, p)
    if spans:
        tids = [r["trace_id"] for r in spans]
        llm = run(f"""
            SELECT trace_id,
                   ROUND(COALESCE(SUM(cost),0),6) AS cost_usd,
                   COALESCE(SUM(tokens_input),0)+COALESCE(SUM(tokens_output),0) AS tokens
            FROM {LLM}
            WHERE trace_id IN UNNEST(@tids)
            GROUP BY trace_id
        """, [bigquery.ArrayQueryParameter("tids", "STRING", tids)])
        lmap = {r["trace_id"]: r for r in llm}
        for r in spans:
            lr = lmap.get(r["trace_id"], {})
            r["cost_usd"] = lr.get("cost_usd", 0)
            r["tokens"]   = lr.get("tokens", 0)
    key = {"cost": "cost_usd", "latency": "duration_ms", "tokens": "tokens"}.get(by, "cost_usd")
    spans.sort(key=lambda r: r.get(key) or 0, reverse=True)
    return spans[:int(limit)]


@app.get("/api/models")
def models(project: str | None = None, platform: str | None = None, service: str | None = None,
           time_range: str = "1h", start: str | None = None, end: str | None = None,
           user=Depends(require_auth)):
    s, e = time_window(time_range, start, end)
    llm_w, llm_p = _llm_window(s, e, project, platform, service)
    return run(f"""
        SELECT model_name AS model,
               COUNT(*) AS calls,
               COUNT(DISTINCT trace_id) AS traces,
               COALESCE(SUM(tokens_input),0)  AS input_tokens,
               COALESCE(SUM(tokens_output),0) AS output_tokens,
               ROUND(COALESCE(SUM(cost),0),6) AS cost_usd
        FROM {LLM}
        WHERE {llm_w} AND model_name IS NOT NULL
        GROUP BY model ORDER BY cost_usd DESC
    """, llm_p)


@app.get("/api/errors/by-service")
def errors_by_service(project: str | None = None, platform: str | None = None, service: str | None = None,
                      time_range: str = "1h", start: str | None = None, end: str | None = None,
                      user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    return run(f"""
        SELECT service_id AS service_name,
               COUNT(*) AS spans,
               COUNTIF(status_code='ERROR') AS errors,
               ROUND(SAFE_DIVIDE(COUNTIF(status_code='ERROR'), COUNT(*)), 4) AS error_rate
        FROM {SPANS} {w}
        GROUP BY service_id HAVING errors > 0 ORDER BY errors DESC
    """, p)


@app.get("/api/errors/top")
def errors_top(project: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               user=Depends(require_auth)):
    s, e = time_window(time_range, start, end)
    cl, params = ["timestamp BETWEEN @start_ts AND @end_ts"], [
        bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", s),
        bigquery.ScalarQueryParameter("end_ts",   "TIMESTAMP", e),
    ]
    if project:
        cl.append("project_id = @project")
        params.append(bigquery.ScalarQueryParameter("project", "STRING", project))
    if service:
        cl.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))
    return run(f"""
        SELECT message, ANY_VALUE(service_id) AS service_name,
               COUNT(*) AS occurrences, MAX(timestamp) AS last_seen
        FROM {LOGS}
        WHERE {' AND '.join(cl)} AND severity IN ('ERROR','FATAL') AND message IS NOT NULL
        GROUP BY message ORDER BY occurrences DESC LIMIT 30
    """, params)


@app.get("/api/health/services")
def health_services(user=Depends(require_auth)):
    rows = run(f"""
        SELECT service_id AS service_name,
               ANY_VALUE(environment) AS platform,
               ANY_VALUE(project_id)  AS project_id,
               MAX(start_time) AS last_seen,
               TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(start_time), MINUTE) AS minutes_since,
               COUNT(DISTINCT trace_id) AS traces_48h,
               ROUND(SAFE_DIVIDE(COUNTIF(status_code='ERROR'), COUNT(*)), 4) AS error_rate
        FROM {SPANS}
        WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 48 HOUR)
        GROUP BY service_id ORDER BY last_seen DESC
    """)
    if rows:
        sids = [r["service_name"] for r in rows]
        llm = run(f"""
            SELECT service_id,
                   ROUND(COALESCE(SUM(cost),0),6) AS cost_48h
            FROM {LLM}
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 48 HOUR)
              AND service_id IN UNNEST(@sids)
            GROUP BY service_id
        """, [bigquery.ArrayQueryParameter("sids", "STRING", sids)])
        lmap = {r["service_id"]: r["cost_48h"] for r in llm}
        for r in rows:
            r["cost_48h"] = lmap.get(r["service_name"], 0)
    return rows


@app.get("/api/meta/last-refresh")
def last_refresh(user=Depends(require_auth)):
    out = {}
    for name, tbl, col in (("spans", SPANS, "start_time"),
                           ("logs",  LOGS,  "timestamp"),
                           ("metrics", METRICS, "timestamp")):
        try:
            r = run(f"SELECT MAX({col}) AS t FROM {tbl}")
            out[name] = r[0]["t"] if r else None
        except Exception:
            out[name] = None
    return out


@app.post("/api/refresh/pipeline")
def refresh_pipeline(user=Depends(require_auth)):
    try:
        from google.cloud.workflows.executions_v1 import ExecutionsClient
        c = ExecutionsClient()
        parent = c.workflow_path(PROJECT, WORKFLOW_LOCATION, WORKFLOW_NAME)
        ex = c.create_execution(parent=parent)
        return {"started": True, "execution": ex.name}
    except Exception as ex:
        raise HTTPException(500, f"could not trigger pipeline: {ex}")


@app.get("/api/refresh/status")
def refresh_status(execution: str, user=Depends(require_auth)):
    try:
        from google.cloud.workflows.executions_v1 import ExecutionsClient
        ex = ExecutionsClient().get_execution(name=execution)
        return {"state": ex.state.name}
    except Exception as ex:
        raise HTTPException(500, f"could not read execution: {ex}")


# ─── SPA mount ────────────────────────────────────────────────────────────────

_STATIC = Path(os.environ.get("STATIC_DIR", str(Path(__file__).parent / "static")))
if _STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_STATIC / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        candidate = _STATIC / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_STATIC / "index.html"))
