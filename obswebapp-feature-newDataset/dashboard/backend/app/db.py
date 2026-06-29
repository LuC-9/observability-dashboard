"""BigQuery client + query helpers (parameterized, safe)."""
import datetime
from google.cloud import bigquery

from . import config

_client = None


def client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=config.PROJECT)
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
    """Return (start_ts, end_ts) as ISO strings. 'custom' uses start/end; presets use now-N..now."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if time_range == "custom" and start and end:
        return start, end
    minutes = config.TIME_PRESETS.get(time_range or "1h", 60)
    return (now - datetime.timedelta(minutes=minutes)).isoformat(), now.isoformat()


def time_clause(col: str, start_ts: str, end_ts: str):
    clause = f"{col} BETWEEN @start_ts AND @end_ts"
    params = [
        bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", start_ts),
        bigquery.ScalarQueryParameter("end_ts", "TIMESTAMP", end_ts),
    ]
    return clause, params


def _multi(col, val, name, params):
    """Support single or comma-separated multi-select -> '=' or 'IN UNNEST'."""
    vals = [v for v in (val.split(",") if val else []) if v]
    if not vals:
        return None
    if len(vals) == 1:
        params.append(bigquery.ScalarQueryParameter(name, "STRING", vals[0]))
        return f"{col} = @{name}"
    params.append(bigquery.ArrayQueryParameter(name, "STRING", vals))
    return f"{col} IN UNNEST(@{name})"


def dim_filters(project=None, platform=None, service=None, *, with_platform=True):
    """Build optional dimension WHERE clauses + params (project single; platform/service multi)."""
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
