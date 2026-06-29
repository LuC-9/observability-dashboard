"""
Cloud (BigQuery) FastAPI app for the Central Observability Dashboard.

Lifted 1:1 from `dashboard/backend/app/{config,db,security,main}.py` and
flattened into one module. Only two intentional deltas from the upstream:

  • The authenticated services-health endpoint is renamed from `/api/health`
    to `/api/health/services` so it doesn't shadow the public `/api/health`
    probe (FastAPI registers both at the same path → first wins).
  • The SPA mount points at `/app/backend/static` by default instead of
    `/app/static`, matching this repo's layout.

Activated when APP_ENV=cloud in .env (see server.py dispatcher).
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

PROJECT       = os.environ.get("GCP_PROJECT", os.environ.get("CENTRAL_PROJECT", "oa-apmena-observability-dv"))
GOLD_DATASET  = os.environ.get("GOLD_DATASET", os.environ.get("BQ_DATASET", "gold"))
SPANS_TABLE   = f"{PROJECT}.{GOLD_DATASET}.spans"
LOGS_TABLE    = f"{PROJECT}.{GOLD_DATASET}.logs"
METRICS_TABLE = f"{PROJECT}.{GOLD_DATASET}.metrics"

WORKFLOW_LOCATION = os.environ.get("WORKFLOW_LOCATION", "us-central1")
WORKFLOW_NAME     = os.environ.get("WORKFLOW_NAME", "obs-pipeline")

ADMIN_USER       = os.environ.get("ADMIN_USER", "admin1")
ADMIN_PASS       = os.environ.get("ADMIN_PASS", "pwd1")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
ALLOWED_DOMAIN   = os.environ.get("ALLOWED_DOMAIN", "loreal.com")
JWT_SECRET       = os.environ.get("JWT_SECRET", "change-me-dev-secret")
JWT_TTL_HOURS    = int(os.environ.get("JWT_TTL_HOURS", "12"))

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

TIME_PRESETS = {
    "5m": 5, "10m": 10, "30m": 30,
    "1h": 60, "6h": 360, "12h": 720, "1d": 1440,
}


# ─── db helpers ───────────────────────────────────────────────────────────────

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
            d[k] = v.isoformat() if isinstance(v, (datetime.datetime, datetime.date)) else v
        out.append(d)
    return out


def time_window(time_range: str | None, start: str | None, end: str | None):
    now = datetime.datetime.now(datetime.timezone.utc)
    if time_range == "custom" and start and end:
        return start, end
    minutes = TIME_PRESETS.get(time_range or "1h", 60)
    return (now - datetime.timedelta(minutes=minutes)).isoformat(), now.isoformat()


def time_clause(col: str, start_ts: str, end_ts: str):
    clause = f"{col} BETWEEN @start_ts AND @end_ts"
    params = [
        bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", start_ts),
        bigquery.ScalarQueryParameter("end_ts", "TIMESTAMP", end_ts),
    ]
    return clause, params


def _multi(col, val, name, params):
    vals = [v for v in (val.split(",") if val else []) if v]
    if not vals:
        return None
    if len(vals) == 1:
        params.append(bigquery.ScalarQueryParameter(name, "STRING", vals[0]))
        return f"{col} = @{name}"
    params.append(bigquery.ArrayQueryParameter(name, "STRING", vals))
    return f"{col} IN UNNEST(@{name})"


def dim_filters(project=None, platform=None, service=None, *, with_platform=True):
    clauses, params = [], []
    if project:
        clauses.append("project_id = @project")
        params.append(bigquery.ScalarQueryParameter("project", "STRING", project))
    if with_platform:
        c = _multi("source_platform", platform, "platform", params)
        if c:
            clauses.append(c)
    c = _multi("service_name", service, "service", params)
    if c:
        clauses.append(c)
    return clauses, params


def where(*clause_lists) -> str:
    parts = [c for lst in clause_lists for c in (lst or [])]
    return ("WHERE " + " AND ".join(parts)) if parts else ""


# ─── auth ─────────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def make_token(username: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {"sub": username, "iat": now,
               "exp": now + datetime.timedelta(hours=JWT_TTL_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def login(username: str, password: str) -> str:
    if username == ADMIN_USER and password == ADMIN_PASS:
        return make_token(username)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")


def login_google(credential: str) -> tuple[str, str]:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "SSO not configured")
    from google.oauth2 import id_token
    from google.auth.transport import requests as grequests
    try:
        info = id_token.verify_oauth2_token(credential, grequests.Request(), GOOGLE_CLIENT_ID)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid Google token")
    email = (info.get("email") or "").lower()
    hd = info.get("hd")
    if ALLOWED_DOMAIN and not (email.endswith("@" + ALLOWED_DOMAIN) or hd == ALLOWED_DOMAIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"only {ALLOWED_DOMAIN} accounts allowed")
    return make_token(email), email


def require_auth(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid/expired token")


# ─── app & routes ─────────────────────────────────────────────────────────────

app = FastAPI(title="Central Observability API (BigQuery)")
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

SPANS, LOGS, METRICS = SPANS_TABLE, LOGS_TABLE, METRICS_TABLE


# ----- public probe (frontend pings before login) -----
@app.get("/api/health")
def health_public():
    return {"status": "ok"}


# ----- auth ----------------------------------------------------
class Creds(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def do_login(c: Creds):
    return {"token": login(c.username, c.password), "user": c.username}


@app.get("/api/config")
def public_config():
    return {"google_client_id": GOOGLE_CLIENT_ID, "allowed_domain": ALLOWED_DOMAIN}


class GoogleCreds(BaseModel):
    credential: str


@app.post("/api/login/google")
def do_login_google(c: GoogleCreds):
    tok, user = login_google(c.credential)
    return {"token": tok, "user": user}


PRICING = f"{PROJECT}.config_ds.llm_pricing"


@app.get("/api/config/pricing")
def list_pricing(user=Depends(require_auth)):
    return run(f"""
        SELECT id, model_prefix,
               input_cost_per_1m_tokens  AS input_cost,
               output_cost_per_1m_tokens AS output_cost,
               active, updated_at
        FROM `{PRICING}`
        ORDER BY model_prefix, active DESC, updated_at DESC
    """)


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
    mparam = bigquery.ScalarQueryParameter("m", "STRING", prefix)

    if p.active:
        dup = run(f"SELECT COUNT(*) AS n FROM `{PRICING}` WHERE model_prefix=@m AND active", [mparam])
        if dup and dup[0]["n"] > 0 and not p.force:
            raise HTTPException(409, f"An active price for '{prefix}' already exists. "
                                     f"Deactivate it first (SCD2) or confirm to auto-deactivate.")
        if p.force:
            run(f"UPDATE `{PRICING}` SET active=FALSE, updated_at=CURRENT_TIMESTAMP() "
                f"WHERE model_prefix=@m AND active", [mparam])

    run(f"""
        INSERT INTO `{PRICING}` (id, model_prefix, input_cost_per_1m_tokens, output_cost_per_1m_tokens, active, updated_at)
        VALUES (GENERATE_UUID(), @m, CAST(@i AS NUMERIC), CAST(@o AS NUMERIC), @a, CURRENT_TIMESTAMP())
    """, [mparam,
          bigquery.ScalarQueryParameter("i", "FLOAT64", p.input_cost),
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
        sets.append("active=@a"); params.append(bigquery.ScalarQueryParameter("a", "BOOL", p.active))
    if p.input_cost is not None:
        sets.append("input_cost_per_1m_tokens=CAST(@i AS NUMERIC)"); params.append(bigquery.ScalarQueryParameter("i", "FLOAT64", p.input_cost))
    if p.output_cost is not None:
        sets.append("output_cost_per_1m_tokens=CAST(@o AS NUMERIC)"); params.append(bigquery.ScalarQueryParameter("o", "FLOAT64", p.output_cost))
    if not sets:
        raise HTTPException(400, "nothing to update")
    sets.append("updated_at=CURRENT_TIMESTAMP()")
    run(f"UPDATE `{PRICING}` SET {', '.join(sets)} WHERE id=@id", params)
    return {"ok": True}


@app.get("/api/auth/iap")
def auth_iap(request: Request):
    raw = request.headers.get("X-Goog-Authenticated-User-Email", "")
    email = raw.split(":")[-1].lower() if raw else ""
    if not email:
        raise HTTPException(401, "no IAP identity")
    if ALLOWED_DOMAIN and not email.endswith("@" + ALLOWED_DOMAIN):
        raise HTTPException(403, f"only {ALLOWED_DOMAIN} accounts allowed")
    return {"token": make_token(email), "user": email}


# ----- scope helpers (filters + time) -----
def scope(project, platform, service, time_range, start, end, time_col, with_platform=True):
    s, e = time_window(time_range, start, end)
    tclause, tparams = time_clause(time_col, s, e)
    dclauses, dparams = dim_filters(project, platform, service, with_platform=with_platform)
    return where([tclause], dclauses), tparams + dparams, s, e


def _bucket(time_range: str | None) -> str:
    mins = TIME_PRESETS.get(time_range or "1h", 60)
    if mins <= 60:   return "MINUTE"
    if mins <= 1440: return "HOUR"
    return "DAY"


# ----- filters ----------------------------------------------------------------
@app.get("/api/filters/projects")
def projects(user=Depends(require_auth)):
    return run(f"SELECT DISTINCT project_id FROM `{SPANS}` "
               f"WHERE project_id IS NOT NULL ORDER BY project_id")


@app.get("/api/filters/platforms")
def platforms(project: str | None = None, user=Depends(require_auth)):
    cl, p = dim_filters(project, None, None)
    return run(f"SELECT DISTINCT source_platform FROM `{SPANS}` {where(cl)} "
               f"{'AND' if cl else 'WHERE'} source_platform IS NOT NULL ORDER BY source_platform", p)


@app.get("/api/filters/services")
def services(project: str | None = None, platform: str | None = None, user=Depends(require_auth)):
    cl, p = dim_filters(project, platform, None)
    return run(f"SELECT DISTINCT service_name FROM `{SPANS}` {where(cl)} "
               f"{'AND' if cl else 'WHERE'} service_name IS NOT NULL ORDER BY service_name", p)


# ----- overview ---------------------------------------------------------------
@app.get("/api/overview")
def overview(project: str | None = None, platform: str | None = None, service: str | None = None,
             time_range: str = "1h", start: str | None = None, end: str | None = None,
             user=Depends(require_auth)):
    w, p, s, e = scope(project, platform, service, time_range, start, end, "start_time")
    kpi = run(f"""
        SELECT
          COUNT(DISTINCT trace_id)                              AS traces,
          COUNT(*)                                              AS spans,
          ROUND(SUM(llm_cost_total_usd), 6)                     AS cost_usd,
          SUM(gen_ai_input_tokens)                              AS input_tokens,
          SUM(gen_ai_output_tokens)                             AS output_tokens,
          COUNT(DISTINCT service_name)                          AS services,
          COUNT(DISTINCT project_id)                            AS projects,
          ROUND(SAFE_DIVIDE(COUNTIF(status_code='ERROR'), COUNT(*)), 4) AS error_rate,
          ROUND(APPROX_QUANTILES(IF(parent_span_id IS NULL, duration_ms, NULL), 100)[OFFSET(50)],1) AS p50_ms,
          ROUND(APPROX_QUANTILES(IF(parent_span_id IS NULL, duration_ms, NULL), 100)[OFFSET(95)],1) AS p95_ms
        FROM `{SPANS}` {w}
    """, p)
    return {"range": {"start": s, "end": e}, "kpis": (kpi[0] if kpi else {})}


@app.get("/api/overview/timeseries")
def timeseries(project: str | None = None, platform: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    b = _bucket(time_range)
    return run(f"""
        SELECT TIMESTAMP_TRUNC(start_time, {b}) AS bucket,
               COUNT(DISTINCT trace_id)         AS traces,
               ROUND(SUM(llm_cost_total_usd),6) AS cost_usd,
               SUM(gen_ai_input_tokens)         AS input_tokens,
               SUM(gen_ai_output_tokens)        AS output_tokens,
               COUNTIF(status_code='ERROR')     AS errors
        FROM `{SPANS}` {w}
        GROUP BY bucket ORDER BY bucket
    """, p)


# ----- traces -----------------------------------------------------------------
@app.get("/api/traces")
def traces(project: str | None = None, platform: str | None = None, service: str | None = None,
           time_range: str = "1h", start: str | None = None, end: str | None = None,
           page: int = 1, page_size: int = 50, user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    total = run(f"SELECT COUNT(*) AS n FROM (SELECT trace_id FROM `{SPANS}` {w} GROUP BY trace_id)", p)
    off = (max(1, page) - 1) * page_size
    rows = run(f"""
        SELECT trace_id,
               ANY_VALUE(service_name)    AS service_name,
               ANY_VALUE(project_id)      AS project_id,
               ANY_VALUE(source_platform) AS source_platform,
               ANY_VALUE(agent_name)      AS agent_name,
               MIN(start_time)            AS start_time,
               MAX(IF(parent_span_id IS NULL, span_name, NULL))    AS root_span,
               MAX(IF(parent_span_id IS NULL, duration_ms, NULL))  AS duration_ms,
               MAX(IF(parent_span_id IS NULL, status_code, NULL))  AS status_code,
               ANY_VALUE(conversation_id) AS conversation_id,
               ROUND(SUM(llm_cost_total_usd),6) AS cost_usd,
               SUM(gen_ai_input_tokens)   AS input_tokens,
               SUM(gen_ai_output_tokens)  AS output_tokens,
               COUNT(*)                   AS spans
        FROM `{SPANS}` {w}
        GROUP BY trace_id
        ORDER BY start_time DESC
        LIMIT {int(page_size)} OFFSET {int(off)}
    """, p)
    return {"rows": rows, "total": (total[0]["n"] if total else 0)}


@app.get("/api/traces/{trace_id}")
def trace_detail(trace_id: str, user=Depends(require_auth)):
    return run(f"""
        SELECT trace_id, span_id, parent_span_id, span_name, span_kind,
               start_time, end_time, duration_ms, status_code, status_message,
               service_name, agent_name, conversation_id, model,
               gen_ai_input_tokens, gen_ai_output_tokens, llm_cost_total_usd,
               input_text, output_text, attributes_json
        FROM `{SPANS}`
        WHERE trace_id = @trace_id
        ORDER BY start_time
    """, [bigquery.ScalarQueryParameter("trace_id", "STRING", trace_id)])


# ----- logs -------------------------------------------------------------------
@app.get("/api/logs")
def logs(project: str | None = None, service: str | None = None, severity: str | None = None,
         time_range: str = "1h", start: str | None = None, end: str | None = None,
         page: int = 1, page_size: int = 50, user=Depends(require_auth)):
    w, p, _, _ = scope(project, None, service, time_range, start, end, "timestamp", with_platform=False)
    if severity:
        w = (w + " AND severity = @sev") if w else "WHERE severity = @sev"
        p = p + [bigquery.ScalarQueryParameter("sev", "STRING", severity)]
    total = run(f"SELECT COUNT(*) AS n FROM `{LOGS}` {w}", p)
    off = (max(1, page) - 1) * page_size
    rows = run(f"""
        SELECT timestamp, service_name, environment, severity, message,
               trace_id, span_id, project_id
        FROM `{LOGS}` {w}
        ORDER BY timestamp DESC
        LIMIT {int(page_size)} OFFSET {int(off)}
    """, p)
    return {"rows": rows, "total": (total[0]["n"] if total else 0)}


# ----- metrics ----------------------------------------------------------------
_METRIC_GROUPS = {"response_code_class", "state", "readiness_status", "service_name", "category", "metric_type"}
_METRIC_AGGS = {"sum": "SUM", "avg": "AVG", "max": "MAX"}


def _metric_scope(project, service, time_range, start, end,
                  category=None, metric_type=None, state=None, readiness=None, rclass=None):
    s, e = time_window(time_range, start, end)
    tclause, params = time_clause("timestamp", s, e)
    clauses = [tclause]
    dcl, dpar = dim_filters(project, None, service, with_platform=False)
    clauses += dcl; params += dpar
    for col, val, name in [("category", category, "cat"), ("metric_type", metric_type, "mt"),
                           ("state", state, "st"), ("readiness_status", readiness, "rd"),
                           ("response_code_class", rclass, "rc")]:
        if val:
            clauses.append(f"{col} = @{name}")
            params.append(bigquery.ScalarQueryParameter(name, "STRING", val))
    return where(clauses), params, s, e


@app.get("/api/metrics/catalog")
def metrics_catalog(project: str | None = None, service: str | None = None,
                    time_range: str = "1h", start: str | None = None, end: str | None = None,
                    user=Depends(require_auth)):
    w, p, _, _ = _metric_scope(project, service, time_range, start, end)
    try:
        r = run(f"""
            SELECT
              ARRAY_AGG(DISTINCT category IGNORE NULLS ORDER BY category)           AS categories,
              ARRAY_AGG(DISTINCT metric_type IGNORE NULLS ORDER BY metric_type)     AS metric_types,
              ARRAY_AGG(DISTINCT service_name IGNORE NULLS ORDER BY service_name)   AS services,
              ARRAY_AGG(DISTINCT state IGNORE NULLS)                                AS states,
              ARRAY_AGG(DISTINCT readiness_status IGNORE NULLS)                     AS readiness,
              ARRAY_AGG(DISTINCT response_code_class IGNORE NULLS)                  AS response_classes
            FROM `{METRICS}` {w}
        """, p)
        return r[0] if r else {}
    except Exception as ex:
        raise HTTPException(503, f"gold.metrics not available: {ex}")


@app.get("/api/metrics/summary")
def metrics_summary(project: str | None = None, service: str | None = None,
                    time_range: str = "1h", start: str | None = None, end: str | None = None,
                    state: str | None = None, readiness: str | None = None, rclass: str | None = None,
                    user=Depends(require_auth)):
    w, p, _, _ = _metric_scope(project, service, time_range, start, end,
                               state=state, readiness=readiness, rclass=rclass)
    try:
        r = run(f"""
            SELECT
              SUM(IF(category='requests', value, 0))                                       AS total_requests,
              ROUND(SAFE_DIVIDE(
                SUM(IF(category='requests' AND response_code_class IN ('4xx','5xx'), value, 0)),
                NULLIF(SUM(IF(category='requests', value, 0)), 0)), 4)                      AS error_rate,
              ROUND(AVG(IF(category='latency', value, NULL)), 1)                           AS mean_latency_ms,
              ROUND(MAX(IF(metric_type LIKE '%/instance_count', value, NULL)), 0)          AS peak_instances,
              ROUND(MAX(IF(metric_type LIKE '%/cpu/utilizations', value, NULL))*100, 1)    AS peak_cpu_pct,
              ROUND(MAX(IF(metric_type LIKE '%/memory/utilizations', value, NULL))*100, 1) AS peak_mem_pct,
              COUNT(DISTINCT service_name)                                                 AS services
            FROM `{METRICS}` {w}
        """, p)
        return r[0] if r else {}
    except Exception as ex:
        raise HTTPException(503, f"gold.metrics not available: {ex}")


@app.get("/api/metrics/timeseries")
def metrics_ts(category: str | None = None, group: str | None = None, agg: str | None = None,
               metric_type: str | None = None,
               project: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               state: str | None = None, readiness: str | None = None, rclass: str | None = None,
               user=Depends(require_auth)):
    g = "'all'" if group == "none" else (group if group in _METRIC_GROUPS else "service_name")
    a = _METRIC_AGGS.get(agg or "", "SUM" if category in ("requests", "network") else "AVG")
    w, p, _, _ = _metric_scope(project, service, time_range, start, end,
                               category, metric_type, state, readiness, rclass)
    b = _bucket(time_range)
    try:
        return run(f"""
            SELECT TIMESTAMP_TRUNC(timestamp, {b})       AS bucket,
                   COALESCE(CAST({g} AS STRING), '—')    AS k,
                   ROUND({a}(value), 4)                  AS v
            FROM `{METRICS}` {w}
            GROUP BY bucket, k ORDER BY bucket
        """, p)
    except Exception as ex:
        raise HTTPException(503, f"gold.metrics not available: {ex}")


@app.get("/api/metrics")
def metrics_table(project: str | None = None, service: str | None = None,
                  time_range: str = "1h", start: str | None = None, end: str | None = None,
                  category: str | None = None, metric_type: str | None = None,
                  state: str | None = None, readiness: str | None = None, rclass: str | None = None,
                  limit: int = 500, user=Depends(require_auth)):
    w, p, _, _ = _metric_scope(project, service, time_range, start, end,
                               category, metric_type, state, readiness, rclass)
    try:
        return run(f"""
            SELECT timestamp, service_name, project_id, environment, category, metric_type,
                   value, response_code, response_code_class, state, readiness_status,
                   hist_count, hist_min, hist_max
            FROM `{METRICS}` {w}
            ORDER BY timestamp DESC LIMIT {int(limit)}
        """, p)
    except Exception as ex:
        raise HTTPException(503, f"gold.metrics not available: {ex}")


# ----- cost -------------------------------------------------------------------
@app.get("/api/cost")
def cost(group_by: str = "service_name",
         project: str | None = None, platform: str | None = None, service: str | None = None,
         time_range: str = "1h", start: str | None = None, end: str | None = None,
         user=Depends(require_auth)):
    allowed = {"service_name", "model", "project_id", "source_platform"}
    if group_by not in allowed:
        raise HTTPException(400, f"group_by must be one of {sorted(allowed)}")
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    return run(f"""
        SELECT {group_by} AS key,
               ROUND(SUM(llm_cost_total_usd),6) AS cost_usd,
               SUM(gen_ai_input_tokens)  AS input_tokens,
               SUM(gen_ai_output_tokens) AS output_tokens,
               COUNT(DISTINCT trace_id)  AS traces
        FROM `{SPANS}` {w} {'AND' if w else 'WHERE'} llm_cost_total_usd IS NOT NULL
        GROUP BY key ORDER BY cost_usd DESC LIMIT 50
    """, p)


# ----- sessions ---------------------------------------------------------------
@app.get("/api/sessions")
def sessions(project: str | None = None, platform: str | None = None, service: str | None = None,
             time_range: str = "1h", start: str | None = None, end: str | None = None,
             limit: int = 200, user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    return run(f"""
        SELECT conversation_id,
               ANY_VALUE(service_name)   AS service_name,
               COUNT(DISTINCT trace_id)  AS turns,
               ROUND(SUM(llm_cost_total_usd),6) AS cost_usd,
               SUM(gen_ai_input_tokens)+SUM(gen_ai_output_tokens) AS tokens,
               MIN(start_time) AS first_seen, MAX(end_time) AS last_seen
        FROM `{SPANS}` {w} {'AND' if w else 'WHERE'} conversation_id IS NOT NULL
        GROUP BY conversation_id ORDER BY last_seen DESC LIMIT {int(limit)}
    """, p)


@app.get("/api/sessions/{conversation_id}")
def session_detail(conversation_id: str, user=Depends(require_auth)):
    return run(f"""
        SELECT trace_id, ANY_VALUE(service_name) AS service_name, MIN(start_time) AS start_time,
               MAX(IF(parent_span_id IS NULL, span_name, NULL)) AS root_span,
               MAX(IF(parent_span_id IS NULL, duration_ms, NULL)) AS duration_ms,
               ROUND(SUM(llm_cost_total_usd),6) AS cost_usd,
               SUM(gen_ai_input_tokens)+SUM(gen_ai_output_tokens) AS tokens
        FROM `{SPANS}` WHERE conversation_id = @cid
        GROUP BY trace_id ORDER BY start_time
    """, [bigquery.ScalarQueryParameter("cid", "STRING", conversation_id)])


# ----- tools ------------------------------------------------------------------
@app.get("/api/tools")
def tools(project: str | None = None, platform: str | None = None, service: str | None = None,
          time_range: str = "1h", start: str | None = None, end: str | None = None,
          user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    cond = ("(JSON_VALUE(attributes_json,'$.\"gen_ai.tool.name\"') IS NOT NULL "
            "OR JSON_VALUE(attributes_json,'$.\"gen_ai.operation.name\"') = 'execute_tool' "
            "OR LOWER(span_name) LIKE '%tool%')")
    return run(f"""
        SELECT COALESCE(JSON_VALUE(attributes_json,'$."gen_ai.tool.name"'), span_name) AS tool,
               ANY_VALUE(service_name) AS service_name,
               COUNT(*) AS calls,
               ROUND(AVG(duration_ms),1) AS avg_ms,
               COUNTIF(status_code='ERROR') AS errors
        FROM `{SPANS}` {w} {'AND' if w else 'WHERE'} {cond}
        GROUP BY tool ORDER BY calls DESC LIMIT 50
    """, p)


# ----- search -----------------------------------------------------------------
@app.get("/api/search")
def search(q: str, user=Depends(require_auth)):
    if not q or len(q) < 2:
        return {}
    recent = "start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)"
    like = bigquery.ScalarQueryParameter("like", "STRING", f"%{q}%")
    pre = bigquery.ScalarQueryParameter("pre", "STRING", f"{q}%")
    one = lambda sql, prm: [r["v"] for r in run(sql, prm) if r["v"]]
    return {
        "projects":      one(f"SELECT DISTINCT project_id AS v FROM `{SPANS}` WHERE {recent} AND project_id LIKE @like LIMIT 6", [like]),
        "services":      one(f"SELECT DISTINCT service_name AS v FROM `{SPANS}` WHERE {recent} AND service_name LIKE @like LIMIT 6", [like]),
        "models":        one(f"SELECT DISTINCT model AS v FROM `{SPANS}` WHERE {recent} AND model LIKE @like LIMIT 6", [like]),
        "traces":        one(f"SELECT DISTINCT trace_id AS v FROM `{SPANS}` WHERE {recent} AND STARTS_WITH(trace_id, @pre) LIMIT 6", [pre]),
        "conversations": one(f"SELECT DISTINCT conversation_id AS v FROM `{SPANS}` WHERE {recent} AND conversation_id LIKE @like LIMIT 6", [like]),
    }


# ----- top / insights ---------------------------------------------------------
@app.get("/api/top/traces")
def top_traces(by: str = "cost",
               project: str | None = None, platform: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               limit: int = 20, user=Depends(require_auth)):
    order = {"cost": "cost_usd", "latency": "duration_ms", "tokens": "tokens"}.get(by, "cost_usd")
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    return run(f"""
        SELECT trace_id, ANY_VALUE(service_name) AS service_name, ANY_VALUE(agent_name) AS agent_name,
               MIN(start_time) AS start_time,
               MAX(IF(parent_span_id IS NULL, duration_ms, NULL)) AS duration_ms,
               ROUND(SUM(llm_cost_total_usd),6) AS cost_usd,
               SUM(gen_ai_input_tokens)+SUM(gen_ai_output_tokens) AS tokens
        FROM `{SPANS}` {w}
        GROUP BY trace_id ORDER BY {order} DESC NULLS LAST LIMIT {int(limit)}
    """, p)


@app.get("/api/models")
def models(project: str | None = None, platform: str | None = None, service: str | None = None,
           time_range: str = "1h", start: str | None = None, end: str | None = None,
           user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    return run(f"""
        SELECT model,
               COUNT(*) AS calls, COUNT(DISTINCT trace_id) AS traces,
               SUM(gen_ai_input_tokens) AS input_tokens, SUM(gen_ai_output_tokens) AS output_tokens,
               ROUND(SUM(llm_cost_total_usd),6) AS cost_usd
        FROM `{SPANS}` {w} {'AND' if w else 'WHERE'} model IS NOT NULL
        GROUP BY model ORDER BY cost_usd DESC
    """, p)


@app.get("/api/errors/by-service")
def errors_by_service(project: str | None = None, platform: str | None = None, service: str | None = None,
                      time_range: str = "1h", start: str | None = None, end: str | None = None,
                      user=Depends(require_auth)):
    w, p, _, _ = scope(project, platform, service, time_range, start, end, "start_time")
    return run(f"""
        SELECT service_name, COUNT(*) AS spans, COUNTIF(status_code='ERROR') AS errors,
               ROUND(SAFE_DIVIDE(COUNTIF(status_code='ERROR'), COUNT(*)), 4) AS error_rate
        FROM `{SPANS}` {w}
        GROUP BY service_name HAVING errors > 0 ORDER BY errors DESC
    """, p)


@app.get("/api/errors/top")
def errors_top(project: str | None = None, service: str | None = None,
               time_range: str = "1h", start: str | None = None, end: str | None = None,
               user=Depends(require_auth)):
    w, p, _, _ = scope(project, None, service, time_range, start, end, "timestamp", with_platform=False)
    return run(f"""
        SELECT message, ANY_VALUE(service_name) AS service_name, COUNT(*) AS occurrences,
               MAX(timestamp) AS last_seen
        FROM `{LOGS}` {w} {'AND' if w else 'WHERE'} severity IN ('ERROR','FATAL') AND message IS NOT NULL
        GROUP BY message ORDER BY occurrences DESC LIMIT 30
    """, p)


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
        FROM `{SPANS}` {w}
        GROUP BY bucket ORDER BY bucket
    """, p)


# Renamed from /api/health to /api/health/services to avoid shadowing the
# public probe — the dashboard frontend already calls /api/health/services
# (see frontend/src/views/Health.tsx).
@app.get("/api/health/services")
def health_services(user=Depends(require_auth)):
    return run(f"""
        SELECT service_name,
               ANY_VALUE(source_platform) AS platform, ANY_VALUE(project_id) AS project_id,
               MAX(start_time) AS last_seen,
               TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(start_time), MINUTE) AS minutes_since,
               COUNT(DISTINCT trace_id) AS traces_48h,
               ROUND(SUM(llm_cost_total_usd),6) AS cost_48h,
               ROUND(SAFE_DIVIDE(COUNTIF(status_code='ERROR'), COUNT(*)), 4) AS error_rate
        FROM `{SPANS}`
        WHERE start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 48 HOUR)
        GROUP BY service_name ORDER BY last_seen DESC
    """)


# ----- meta / refresh ---------------------------------------------------------
@app.get("/api/meta/last-refresh")
def last_refresh(user=Depends(require_auth)):
    out = {}
    for name, tbl in (("spans", SPANS), ("logs", LOGS), ("metrics", METRICS)):
        try:
            r = run(f"SELECT MAX(ingested_at) AS t FROM `{tbl}`")
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


# ─── SPA mount (served by the same Cloud Run service) ─────────────────────────

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
