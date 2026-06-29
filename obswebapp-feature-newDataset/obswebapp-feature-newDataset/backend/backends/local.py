"""
Local SQLite backend — same API as backends/bq.py so main.py works unchanged.

Uses a single SQLite file (default: backend/data/local.db) and pandas for any
aggregations that would be awkward in SQL. No google-cloud-bigquery imports
here, so this module is safe to use without GCP credentials.

Mirrors the wide_* table schema (migrated from otel_raw_* tables).
"""
import json as _json
import os
import sqlite3
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import seed_data
import pricing
from bq_client import current_project


# ── Connection ───────────────────────────────────────────────────────────────

DB_PATH = Path(os.getenv(
    "LOCAL_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "data" / "local.db"),
))

print(f"[local_backend] DB_PATH={DB_PATH}")


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _read(query: str, params: list | tuple | None = None,
          parse_dates: list[str] | None = None) -> pd.DataFrame:
    with _conn() as c:
        return pd.read_sql_query(query, c, params=tuple(params or ()),
                                 parse_dates=parse_dates or [])


# ── Filter helpers ────────────────────────────────────────────────────────────

def _ts(dt: datetime) -> str:
    """Convert tz-aware datetime to ISO string SQLite can string-compare."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _date(dt: datetime) -> str:
    """Convert datetime to YYYY-MM-DD string for daily table comparisons."""
    return dt.astimezone(timezone.utc).date().isoformat()


def _and(conditions: list[str], params: list, name: str, op: str, val: str | int):
    if val != "All":
        conditions.append(f"{name} {op} ?")
        params.append(val)


def _add_project(conditions: list[str], params: list):
    proj = current_project.get()
    if proj:
        conditions.append("project_id = ?")
        params.append(proj)


# ── Filter options ────────────────────────────────────────────────────────────

def get_filter_options(project: str = None) -> dict:
    """Distinct dropdown values from wide tables."""
    if project and project != "All":
        current_project.set(project)
    elif project == "All":
        current_project.set(None)

    proj      = current_project.get()
    p_cond    = " AND project_id = ?" if proj else ""
    p_params  = [proj] if proj else []

    services, environments, severities, agents = set(), set(), set(), set()
    metric_names, models, providers            = set(), set(), set()
    tool_names, tool_types, tool_statuses      = set(), set(), set()
    components, error_types, errors            = set(), set(), []

    if proj:
        p_params  = [proj]
        p_params_2 = [proj, proj]
        simple_queries = [
            ("logs_detail.service_id",
             "SELECT DISTINCT service_id AS v FROM wide_logs_detail WHERE service_id IS NOT NULL AND project_id = ?",
             p_params, services),
            ("spans_detail.service_id",
             f"SELECT DISTINCT service_id AS v FROM wide_spans_detail WHERE service_id IS NOT NULL{p_cond}",
             p_params, services),
            ("logs_detail.environment",
             "SELECT DISTINCT environment AS v FROM wide_logs_detail WHERE environment IS NOT NULL AND project_id = ?",
             p_params, environments),
            ("logs_detail.severity",
             "SELECT DISTINCT severity AS v FROM wide_logs_detail WHERE severity IS NOT NULL AND project_id = ?",
             p_params, severities),
            ("agent_steps.agent_name",
             "SELECT DISTINCT agent_name AS v FROM wide_agent_traces_detail WHERE agent_name IS NOT NULL AND trace_id IN (SELECT trace_id FROM wide_spans_detail WHERE project_id = ?)",
             p_params, agents),
            ("metrics_detail.metric_name",
             "SELECT DISTINCT metric_name AS v FROM wide_metrics_detail WHERE metric_name IS NOT NULL AND project_id = ?",
             p_params, metric_names),
            ("llm_usage.model_name",
             "SELECT DISTINCT model_name AS v FROM wide_llm_usage_daily WHERE model_name IS NOT NULL AND project_id = ?",
             p_params, models),
            ("llm_usage.provider",
             "SELECT DISTINCT provider AS v FROM wide_llm_usage_daily WHERE provider IS NOT NULL AND project_id = ?",
             p_params, providers),
            ("tool_detail.tool_name",
             "SELECT DISTINCT tool_name AS v FROM wide_tool_executions_detail WHERE tool_name IS NOT NULL AND trace_id IN (SELECT trace_id FROM wide_spans_detail WHERE project_id = ?)",
             p_params, tool_names),
            ("tool_detail.tool_type",
             "SELECT DISTINCT tool_type AS v FROM wide_tool_executions_detail WHERE tool_type IS NOT NULL AND trace_id IN (SELECT trace_id FROM wide_spans_detail WHERE project_id = ?)",
             p_params, tool_types),
            ("tool_detail.status",
             "SELECT DISTINCT status AS v FROM wide_tool_executions_detail WHERE status IS NOT NULL AND trace_id IN (SELECT trace_id FROM wide_spans_detail WHERE project_id = ?)",
             p_params, tool_statuses),
            ("errors_detail.service_id",
             "SELECT DISTINCT service_id AS v FROM wide_errors_detail WHERE service_id IS NOT NULL AND (trace_id IN (SELECT trace_id FROM wide_spans_detail WHERE project_id = ?) OR error_id IN (SELECT log_id FROM wide_logs_detail WHERE project_id = ?))",
             p_params_2, components),
            ("errors_detail.error_type",
             "SELECT DISTINCT error_type AS v FROM wide_errors_detail WHERE error_type IS NOT NULL AND (trace_id IN (SELECT trace_id FROM wide_spans_detail WHERE project_id = ?) OR error_id IN (SELECT log_id FROM wide_logs_detail WHERE project_id = ?))",
             p_params_2, error_types),
        ]
    else:
        simple_queries = [
            ("logs_daily.service_id",
             "SELECT DISTINCT service_id AS v FROM wide_logs_daily WHERE service_id IS NOT NULL",
             [], services),
            ("spans_detail.service_id",
             "SELECT DISTINCT service_id AS v FROM wide_spans_detail WHERE service_id IS NOT NULL",
             [], services),
            ("logs_daily.environment",
             "SELECT DISTINCT environment AS v FROM wide_logs_daily WHERE environment IS NOT NULL",
             [], environments),
            ("logs_daily.severity",
             "SELECT DISTINCT severity AS v FROM wide_logs_daily WHERE severity IS NOT NULL",
             [], severities),
            ("agent_steps.agent_name",
             "SELECT DISTINCT agent_name AS v FROM wide_agent_trace_steps_daily WHERE agent_name IS NOT NULL",
             [], agents),
            ("metrics_daily.metric_name",
             "SELECT DISTINCT metric_name AS v FROM wide_metrics_daily WHERE metric_name IS NOT NULL",
             [], metric_names),
            ("llm_usage.model_name",
             "SELECT DISTINCT model_name AS v FROM wide_llm_usage_daily WHERE model_name IS NOT NULL",
             [], models),
            ("llm_usage.provider",
             "SELECT DISTINCT provider AS v FROM wide_llm_usage_daily WHERE provider IS NOT NULL",
             [], providers),
            ("tool_usage.tool_name",
             "SELECT DISTINCT tool_name AS v FROM wide_tool_usage_daily WHERE tool_name IS NOT NULL",
             [], tool_names),
            ("tool_usage.tool_type",
             "SELECT DISTINCT tool_type AS v FROM wide_tool_usage_daily WHERE tool_type IS NOT NULL",
             [], tool_types),
            ("tool_detail.status",
             "SELECT DISTINCT status AS v FROM wide_tool_executions_detail WHERE status IS NOT NULL",
             [], tool_statuses),
            ("errors_daily.service_id",
             "SELECT DISTINCT service_id AS v FROM wide_error_summary_daily WHERE service_id IS NOT NULL",
             [], components),
            ("errors_daily.error_type",
             "SELECT DISTINCT error_type AS v FROM wide_error_summary_daily WHERE error_type IS NOT NULL",
             [], error_types),
        ]
    import concurrent.futures

    def _fetch(label, q, p_arr, tgt_set):
        try:
            df = _read(q, p_arr)
            if not df.empty:
                tgt_set.update(df["v"].dropna().tolist())
        except Exception as e:
            errors.append(label)
            print(f"[local_backend] {label}: {e}")

    projects = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futs = []
        for label, q, prm, target in simple_queries:
            futs.append(executor.submit(_fetch, label, q, prm, target))
            
        for tbl, col in [("wide_llm_interactions_detail", "project_id"),
                         ("wide_spans_detail",            "project_id")]:
            q = f"SELECT DISTINCT {col} AS v FROM {tbl} WHERE {col} IS NOT NULL"
            futs.append(executor.submit(_fetch, f"projects/{tbl}", q, [], projects))
            
        concurrent.futures.wait(futs)

    if not projects:
        projects.add("local-project")

    projects_list = sorted(projects)
    if "All" not in projects_list:
        projects_list.insert(0, "All")

    result = {
        "services":      sorted(services),
        "environments":  sorted(environments),
        "severities":    sorted(severities),
        "agents":        sorted(agents),
        "metric_names":  sorted(metric_names),
        "models":        sorted(models),
        "providers":     sorted(providers),
        "tool_names":    sorted(tool_names),
        "tool_types":    sorted(tool_types),
        "tool_statuses": sorted(tool_statuses),
        "components":    sorted(components),
        "error_types":   sorted(error_types),
        "errors":        errors,
        "projects":      projects_list,
    }
    print(f"[local_backend] get_filter_options -> services={result['services']} errors={errors}")
    return result


# ── Overview ──────────────────────────────────────────────────────────────────

def get_overview_stats(start_dt: datetime, end_dt: datetime, service: str = "All") -> dict:
    defaults = {
        "total_spans": 0, "error_spans": 0, "avg_duration_ms": 0.0,
        "total_cost_usd": 0.0, "total_input_tokens": 0, "total_output_tokens": 0,
        "total_logs": 0,
    }
    sd, ed = _ts(start_dt), _ts(end_dt)
    proj = current_project.get()
    proj_cond = " AND project_id = ?" if proj else ""

    def _build_params():
        base = [sd, ed]
        if service != "All":
            base.append(service)
        if proj:
            base.append(proj)
        return base

    svc_cond = " AND service_id = ?" if service != "All" else ""

    # Spans + errors + duration from wide_spans_detail
    try:
        params = _build_params()
        sql = f"""
            SELECT
                COUNT(*)                                               AS total_spans,
                SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) AS error_spans,
                AVG(duration_ms)                                       AS avg_duration_ms
            FROM wide_spans_detail
            WHERE start_time BETWEEN ? AND ?{svc_cond}{proj_cond}
        """
        row = _read(sql, params).iloc[0]
        defaults.update({
            "total_spans":     int(row.get("total_spans",     0) or 0),
            "error_spans":     int(row.get("error_spans",     0) or 0),
            "avg_duration_ms": round(float(row.get("avg_duration_ms", 0) or 0), 2),
        })
    except Exception as e:
        print(f"[local_backend] ERROR in get_overview_stats health: {e}")

    # Cost + tokens from wide_llm_interactions_detail
    try:
        params = _build_params()
        sql = f"""
            SELECT
                SUM(COALESCE(cost,          0)) AS total_cost_usd,
                SUM(COALESCE(tokens_input,  0)) AS total_input_tokens,
                SUM(COALESCE(tokens_output, 0)) AS total_output_tokens
            FROM wide_llm_interactions_detail
            WHERE timestamp BETWEEN ? AND ?{svc_cond}{proj_cond}
        """
        row = _read(sql, params).iloc[0]
        defaults.update({
            "total_cost_usd":      round(float(row.get("total_cost_usd",      0) or 0), 6),
            "total_input_tokens":  int(row.get("total_input_tokens",  0) or 0),
            "total_output_tokens": int(row.get("total_output_tokens", 0) or 0),
        })
    except Exception as e:
        print(f"[local_backend] ERROR in get_overview_stats llm: {e}")

    # Log count from wide_logs_detail
    try:
        params = _build_params()
        sql = f"""
            SELECT COUNT(*) AS total_logs
            FROM wide_logs_detail
            WHERE timestamp BETWEEN ? AND ?{svc_cond}{proj_cond}
        """
        row = _read(sql, params).iloc[0]
        defaults["total_logs"] = int(row.get("total_logs", 0) or 0)
    except Exception as e:
        print(f"[local_backend] ERROR in get_overview_stats logs: {e}")

    return defaults


# ── Logs ──────────────────────────────────────────────────────────────────────

def query_logs(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", severity: str = "All",
    environment: str = "All", limit: int = 500,
) -> pd.DataFrame:
    cond   = ["timestamp BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    _add_project(cond, params)
    _and(cond, params, "service_id",   "=", service)
    _and(cond, params, "severity",     "=", severity)
    _and(cond, params, "environment",  "=", environment)
    params.append(int(limit))
    try:
        return _read(f"""
            SELECT log_id, trace_id, span_id,
                   service_id AS service_name,
                   environment, project_id, severity, message, timestamp,
                   NULL AS model
            FROM wide_logs_detail
            WHERE {' AND '.join(cond)}
            ORDER BY timestamp DESC
            LIMIT ?
        """, params, parse_dates=["timestamp"])
    except Exception as e:
        print(f"[local_backend] ERROR in query_logs: {e}")
        return pd.DataFrame(columns=[
            "log_id","trace_id","span_id","service_name","environment",
            "project_id","severity","message","timestamp","model"])


def query_logs_severity_dist(start_dt: datetime, end_dt: datetime, service: str = "All") -> pd.DataFrame:
    sd, ed = _date(start_dt), _date(end_dt)
    cond   = ["date BETWEEN ? AND ?"]
    params: list = [sd, ed]
    _and(cond, params, "service_id", "=", service)
    try:
        return _read(f"""
            SELECT severity, SUM(log_count) AS count
            FROM wide_logs_daily
            WHERE {' AND '.join(cond)}
            GROUP BY severity ORDER BY count DESC
        """, params)
    except Exception as e:
        print(f"[local_backend] ERROR in query_logs_severity_dist: {e}")
        return pd.DataFrame(columns=["severity", "count"])


# ── Traces / Spans ────────────────────────────────────────────────────────────

def query_traces(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", agent: str = "All",
    status: str = "All", limit: int = 500,
) -> pd.DataFrame:
    cond   = ["start_time BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    _add_project(cond, params)
    _and(cond, params, "service_id",  "=", service)
    if agent != "All":
        cond.append("COALESCE(agent_name, agent_id) = ?")
        params.append(agent)
    _and(cond, params, "status_code", "=", status)
    params.append(int(limit))
    try:
        return _read(f"""
            SELECT
                trace_id, span_id, parent_span_id,
                span_name, span_kind,
                start_time, end_time, duration_ms,
                status_code, status_message,
                service_id AS service_name,
                agent_name, session_id, operation_name, environment, project_id
            FROM wide_spans_detail
            WHERE {' AND '.join(cond)}
            ORDER BY start_time DESC
            LIMIT ?
        """, params, parse_dates=["start_time", "end_time"])
    except Exception as e:
        print(f"[local_backend] ERROR in query_traces: {e}")
        return pd.DataFrame()


def query_traces_timeseries(start_dt: datetime, end_dt: datetime, service: str = "All") -> pd.DataFrame:
    cond   = ["start_time BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    _add_project(cond, params)
    _and(cond, params, "service_id", "=", service)
    try:
        df = _read(f"""
            SELECT date(start_time) AS hour,
                   AVG(duration_ms) AS avg_duration_ms,
                   SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) AS error_count,
                   COUNT(*)         AS span_count
            FROM wide_spans_detail
            WHERE {' AND '.join(cond)}
            GROUP BY hour ORDER BY hour
        """, params)

        llm_cond = [c.replace("start_time", "timestamp") for c in cond]
        # Supplement with daily cost/token data
        df_cost = _read(f"""
            SELECT date(timestamp)  AS hour,
                   SUM(COALESCE(cost,          0)) AS total_cost_usd,
                   SUM(COALESCE(tokens_input,  0)) AS input_tokens,
                   SUM(COALESCE(tokens_output, 0)) AS output_tokens
            FROM wide_llm_interactions_detail
            WHERE {' AND '.join(llm_cond)}
            GROUP BY hour
        """, params)
        if not df_cost.empty:
            if not df.empty:
                df = df.merge(df_cost, on="hour", how="outer")
                for c in ["avg_duration_ms", "error_count", "span_count", "total_cost_usd", "input_tokens", "output_tokens"]:
                    if c in df.columns:
                        df[c] = df[c].fillna(0)
            else:
                df = df_cost
        df["total_cost_usd"] = df.get("total_cost_usd", 0).fillna(0)
        return df
    except Exception as e:
        print(f"[local_backend] ERROR in query_traces_timeseries: {e}")
        return pd.DataFrame(columns=["hour","avg_duration_ms","error_count","span_count"])


def query_trace_list(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", agent: str = "All",
    status: str = "All", limit: int = 200,
) -> pd.DataFrame:
    df = query_traces(start_dt, end_dt, service=service, agent=agent,
                      limit=100_000)
    if df.empty:
        return pd.DataFrame(columns=[
            "trace_id","trace_start","total_duration_ms","span_count",
            "error_count","service_name","agents"])
    df = df.copy()
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df["end_time"]   = pd.to_datetime(df["end_time"],   utc=True, errors="coerce")

    grouped = df.groupby("trace_id").agg(
        trace_start      =("start_time",  "min"),
        _max_end         =("end_time",    "max"),
        span_count       =("span_id",     "count"),
        error_count      =("status_code", lambda s: int((s == "ERROR").sum())),
        service_name     =("service_name","first"),
        agents           =("agent_name",  lambda s: ", ".join(sorted({a for a in s.dropna()}))),
        session_status   =("status_code", lambda s: "failed" if (s == "ERROR").any() else "completed"),
    ).reset_index()
    grouped["total_duration_ms"] = (grouped["_max_end"] - grouped["trace_start"]).dt.total_seconds() * 1000
    grouped = grouped.drop(columns=["_max_end"])
    if status != "All":
        grouped = grouped[grouped["session_status"] == status]
    return grouped[["trace_id","trace_start","total_duration_ms","span_count",
                    "error_count","service_name","agents"]].sort_values(
        "trace_start", ascending=False).head(int(limit))


def query_trace_spans(trace_id: str) -> pd.DataFrame:
    proj      = current_project.get()
    proj_cond = " AND project_id = ?" if proj else ""
    params    = [trace_id, proj] if proj else [trace_id]
    try:
        return _read(f"""
            SELECT trace_id, span_id, parent_span_id,
                   span_name, span_kind,
                   start_time, end_time, duration_ms,
                   status_code, status_message,
                   service_id AS service_name, agent_name,
                   session_id, operation_name, environment, project_id,
                   attributes_json
            FROM wide_spans_detail
            WHERE trace_id = ?{proj_cond}
            ORDER BY start_time
        """, params, parse_dates=["start_time", "end_time"])
    except Exception as e:
        print(f"[local_backend] ERROR in query_trace_spans: {e}")
        return pd.DataFrame()


# ── Metrics ───────────────────────────────────────────────────────────────────

def query_metrics(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", agent: str = "All",
    metric_name: str = "All",
) -> pd.DataFrame:
    cond   = ["timestamp BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    _add_project(cond, params)
    _and(cond, params, "service_id",  "=", service)
    _and(cond, params, "agent_name",  "=", agent)
    _and(cond, params, "metric_name", "=", metric_name)
    try:
        return _read(f"""
            SELECT timestamp, metric_name, metric_type,
                   value_int, value_double, histogram_sum
            FROM wide_metrics_detail
            WHERE {' AND '.join(cond)}
            ORDER BY timestamp, metric_name
        """, params, parse_dates=["timestamp"])
    except Exception as e:
        print(f"[local_backend] ERROR in query_metrics: {e}")
        return pd.DataFrame()


# ── Sessions ──────────────────────────────────────────────────────────────────

def query_sessions(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", agent: str = "All", status: str = "All",
) -> pd.DataFrame:
    cond   = ["start_time BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    if service != "All":
        cond.append("session_id IN (SELECT session_id FROM wide_spans_detail WHERE service_id = ?)")
        params.append(service)
    if agent != "All":
        cond.append("COALESCE(agent_name, agent_id) = ?")
        params.append(agent)
    proj = current_project.get()
    if proj:
        cond.append("session_id IN (SELECT session_id FROM wide_spans_detail WHERE project_id = ?)")
        params.append(proj)
    try:
        df = _read(f"""
            SELECT session_id,
                   COALESCE(agent_id, agent_name) AS agent_id,
                   start_time, end_time,
                   total_spans AS total_turns,
                   'completed' AS status,
                   NULL        AS total_cost
            FROM wide_sessions_detail
            WHERE {' AND '.join(cond)}
            ORDER BY start_time DESC
            LIMIT 500
        """, params, parse_dates=["start_time", "end_time"])
        if status != "All" and not df.empty:
            df = df[df["status"] == status]
        return df
    except Exception as e:
        print(f"[local_backend] ERROR in query_sessions: {e}")
        return pd.DataFrame()


def query_sessions_timeseries(start_dt: datetime, end_dt: datetime, service: str = "All") -> pd.DataFrame:
    cond   = ["start_time BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    if service != "All":
        cond.append("session_id IN (SELECT session_id FROM wide_spans_detail WHERE service_id = ?)")
        params.append(service)
    proj = current_project.get()
    if proj:
        cond.append("session_id IN (SELECT session_id FROM wide_spans_detail WHERE project_id = ?)")
        params.append(proj)
    try:
        return _read(f"""
            SELECT date(start_time) AS hour, COUNT(*) AS count
            FROM wide_sessions_detail
            WHERE {' AND '.join(cond)}
            GROUP BY hour ORDER BY hour
        """, params)
    except Exception as e:
        print(f"[local_backend] ERROR in query_sessions_timeseries: {e}")
        return pd.DataFrame()


def query_session_detail(session_id: str) -> dict:
    lookback = _ts(datetime.now(tz=timezone.utc) - timedelta(days=30))
    params   = [session_id, lookback]

    empty = {
        "session":          pd.DataFrame(),
        "agent_traces":     pd.DataFrame(),
        "llm_interactions": pd.DataFrame(),
        "tool_executions":  pd.DataFrame(),
    }

    try:
        sess_df = _read("""
            SELECT session_id, COALESCE(agent_id, agent_name) AS agent_id,
                   start_time, end_time, total_spans, duration_sec
            FROM wide_sessions_detail
            WHERE session_id = ? AND start_time >= ?
            LIMIT 1
        """, params)
    except Exception as e:
        print(f"[local_backend] ERROR in query_session_detail/session: {e}")
        return empty

    if sess_df is None or sess_df.empty:
        return empty

    row  = sess_df.iloc[0]
    sess = pd.DataFrame([{
        "session_id":  session_id,
        "agent_id":    row.get("agent_id", ""),
        "start_time":  row.get("start_time"),
        "end_time":    row.get("end_time"),
        "total_turns": int(row.get("total_spans", 0) or 0),
        "status":      "completed",
        "total_cost":  0.0,
    }])

    # Agent trace steps
    try:
        at = _read("""
            SELECT step_number, step_type, latency_ms,
                   agent_name, tool_id, llm_call_id, timestamp
            FROM wide_agent_traces_detail
            WHERE session_id = ? AND timestamp >= ?
            ORDER BY step_number
        """, params)
        if not at.empty:
            at["decision"]  = ""
            at["tool_name"] = at["tool_id"].fillna("")
    except Exception as e:
        print(f"[local_backend] ERROR in query_session_detail/traces: {e}")
        at = pd.DataFrame()

    # LLM interactions
    try:
        llm = _read("""
            SELECT llm_call_id, model_name, provider, tokens_input, tokens_output,
                   cost, latency_ms, finish_reason, timestamp
            FROM wide_llm_interactions_detail
            WHERE session_id = ? AND timestamp >= ?
            ORDER BY timestamp
        """, params)
        if not llm.empty:
            llm["status"] = "success"
            sess.at[0, "total_cost"] = round(float(llm["cost"].fillna(0).sum()), 6)
    except Exception as e:
        print(f"[local_backend] ERROR in query_session_detail/llm: {e}")
        llm = pd.DataFrame()

    # Tool executions
    try:
        tools = _read("""
            SELECT execution_id, tool_name, tool_type, status, error_message,
                   latency_ms, trace_id, timestamp
            FROM wide_tool_executions_detail
            WHERE session_id = ? AND timestamp >= ?
            ORDER BY timestamp
        """, params)
    except Exception as e:
        print(f"[local_backend] ERROR in query_session_detail/tools: {e}")
        tools = pd.DataFrame()

    return {
        "session":          sess,
        "agent_traces":     at,
        "llm_interactions": llm,
        "tool_executions":  tools,
    }


# ── LLM Interactions ──────────────────────────────────────────────────────────

def query_llm_interactions(
    start_dt: datetime, end_dt: datetime,
    model_name: str = "All", provider: str = "All", status: str = "All",
) -> pd.DataFrame:
    cond   = ["timestamp BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    _add_project(cond, params)
    try:
        df = _read(f"""
            SELECT llm_call_id, trace_id, session_id,
                   agent_id, agent_name, model_name, provider,
                   service_id AS service_name, project_id, environment,
                   tokens_input, tokens_output, total_tokens,
                   cost, temperature, finish_reason, latency_ms, timestamp
            FROM wide_llm_interactions_detail
            WHERE {' AND '.join(cond)}
            ORDER BY timestamp DESC
            LIMIT 1000
        """, params, parse_dates=["timestamp"])
        if df.empty:
            return df
        # Pricing fallback where cost is null/zero
        df["cost"] = df.apply(
            lambda r: pricing.effective_cost(r["cost"], r["model_name"], r["tokens_input"], r["tokens_output"]),
            axis=1,
        )
        if model_name != "All":
            df = df[df["model_name"].str.lower().str.contains(model_name.lower(), na=False, regex=False)]
        if provider != "All":
            df = df[df["provider"] == provider]
        return df
    except Exception as e:
        print(f"[local_backend] ERROR in query_llm_interactions: {e}")
        return pd.DataFrame()


def query_llm_timeseries(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    sd, ed = _date(start_dt), _date(end_dt)
    try:
        return _read("""
            SELECT date AS hour,
                   SUM(total_tokens_input)  AS tokens_input,
                   SUM(total_tokens_output) AS tokens_output
            FROM wide_llm_usage_daily
            WHERE date BETWEEN ? AND ?
            GROUP BY date ORDER BY date
        """, [sd, ed])
    except Exception as e:
        print(f"[local_backend] ERROR in query_llm_timeseries: {e}")
        return pd.DataFrame()


# ── Tool Executions ───────────────────────────────────────────────────────────

def query_tool_executions(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", tool_name: str = "All", tool_type: str = "All", status: str = "All",
) -> pd.DataFrame:
    cond   = ["timestamp BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    _and(cond, params, "service_id", "=", service)
    _and(cond, params, "tool_name", "=", tool_name)
    _and(cond, params, "tool_type", "=", tool_type)
    _and(cond, params, "status",    "=", status)
    
    proj = current_project.get()
    if proj:
        cond.append("""service_id IN (
            SELECT DISTINCT service_id FROM wide_spans_detail WHERE project_id = ?
            UNION ALL
            SELECT DISTINCT service_id FROM wide_logs_detail WHERE project_id = ?
        )""")
        params.extend([proj, proj])
        
    try:
        return _read(f"""
            SELECT execution_id, trace_id, session_id,
                   agent_id, agent_name, tool_name,
                   tool_name AS tool_display_name,
                   tool_type, status, error_message,
                   latency_ms, tool_input, tool_output, timestamp
            FROM wide_tool_executions_detail
            WHERE {' AND '.join(cond)}
            ORDER BY timestamp DESC
            LIMIT 1000
        """, params, parse_dates=["timestamp"])
    except Exception as e:
        print(f"[local_backend] ERROR in query_tool_executions: {e}")
        return pd.DataFrame()


def query_tool_executions_timeseries(start_dt: datetime, end_dt: datetime, service: str = "All") -> pd.DataFrame:
    cond   = ["timestamp BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    _and(cond, params, "service_id", "=", service)
    proj = current_project.get()
    if proj:
        cond.append("""service_id IN (
            SELECT DISTINCT service_id FROM wide_spans_detail WHERE project_id = ?
            UNION ALL
            SELECT DISTINCT service_id FROM wide_logs_detail WHERE project_id = ?
        )""")
        params.extend([proj, proj])

    try:
        return _read(f"""
            SELECT date(timestamp) AS hour, COUNT(*) AS count
            FROM wide_tool_executions_detail
            WHERE {' AND '.join(cond)}
            GROUP BY hour ORDER BY hour
        """, params)
    except Exception as e:
        print(f"[local_backend] ERROR in query_tool_executions_timeseries: {e}")
        return pd.DataFrame()


# ── Errors ────────────────────────────────────────────────────────────────────

def query_errors(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", component: str = "All", error_type: str = "All", severity: str = "All",
) -> pd.DataFrame:
    cond   = ["timestamp BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    _and(cond, params, "service_id", "=", service)
    proj = current_project.get()
    if proj:
        cond.append("""service_id IN (
            SELECT DISTINCT service_id FROM wide_spans_detail WHERE project_id = ?
            UNION ALL
            SELECT DISTINCT service_id FROM wide_logs_detail WHERE project_id = ?
        )""")
        params.extend([proj, proj])
    _and(cond, params, "service_id",  "=", component)
    _and(cond, params, "error_type",  "=", error_type)
    if severity != "All":
        cond.append("UPPER(severity) = ?")
        params.append(str(severity).upper())
    try:
        df = _read(f"""
            SELECT error_id,
                   service_id AS component,
                   error_type, error_message, severity,
                   session_id, trace_id, span_id,
                   agent_id, agent_name, source, timestamp
            FROM wide_errors_detail
            WHERE {' AND '.join(cond)}
            ORDER BY timestamp DESC
            LIMIT 1000
        """, params, parse_dates=["timestamp"])
        if not df.empty:
            df["severity"] = df["severity"].astype(str).str.upper().replace({"WARN": "WARNING"})
        return df
    except Exception as e:
        print(f"[local_backend] ERROR in query_errors: {e}")
        return pd.DataFrame(columns=[
            "error_id","component","error_type","error_message",
            "severity","session_id","trace_id","timestamp"])


def query_errors_timeseries(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", component: str = "All", error_type: str = "All", severity: str = "All"
) -> pd.DataFrame:
    cond   = ["timestamp BETWEEN ? AND ?"]
    params: list = [_ts(start_dt), _ts(end_dt)]
    _and(cond, params, "service_id", "=", service)
    proj = current_project.get()
    if proj:
        cond.append("""service_id IN (
            SELECT DISTINCT service_id FROM wide_spans_detail WHERE project_id = ?
            UNION ALL
            SELECT DISTINCT service_id FROM wide_logs_detail WHERE project_id = ?
        )""")
        params.extend([proj, proj])
    _and(cond, params, "service_id",  "=", component)
    _and(cond, params, "error_type",  "=", error_type)
    if severity != "All":
        sel = str(severity).upper()
        if sel in ("WARN", "WARNING"):
            cond.append("UPPER(severity) IN ('WARN','WARNING')")
        else:
            cond.append("UPPER(severity) = ?")
            params.append(sel)
    try:
        return _read(f"""
            SELECT date(timestamp) AS hour, COUNT(*) AS count
            FROM wide_errors_detail
            WHERE {' AND '.join(cond)}
            GROUP BY hour ORDER BY hour
        """, params)
    except Exception as e:
        print(f"[local_backend] ERROR in query_errors_timeseries: {e}")
        return pd.DataFrame()


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def bootstrap() -> None:
    """Idempotent: create all 17 wide SQLite tables; seed if empty."""
    print(f"[bootstrap] Local SQLite mode — DB={DB_PATH}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(tz=timezone.utc)
    all_seed = seed_data.gen_all(now)

    with _conn() as c:
        for tname, cols in seed_data.TABLE_COLS.items():
            col_defs = ", ".join(f'"{n}" {t}' for n, t in cols)
            c.execute(f'CREATE TABLE IF NOT EXISTS "{tname}" ({col_defs})')
        c.commit()
        print(f"[bootstrap] all 17 wide tables created / verified")

        # Migration: Ensure attributes_json exists in wide_spans_detail table
        try:
            c.execute('SELECT "attributes_json" FROM "wide_spans_detail" LIMIT 1')
        except sqlite3.OperationalError:
            try:
                c.execute('ALTER TABLE "wide_spans_detail" ADD COLUMN "attributes_json" TEXT')
                c.commit()
                print("[bootstrap] migrated: added attributes_json column to wide_spans_detail")
            except Exception as e:
                print(f"[bootstrap] ERROR migrating wide_spans_detail: {e}")

        part_col = seed_data.PARTITION_COL
        for tname, rows in all_seed.items():
            pcol = part_col.get(tname, "timestamp")
            try:
                existing = c.execute(
                    f'SELECT COUNT(*) FROM "{tname}" WHERE "{pcol}" >= ?',
                    [(now - __import__("datetime").timedelta(days=30)).replace(microsecond=0).isoformat()],
                ).fetchone()[0]
            except Exception:
                existing = 0

            if existing > 0:
                print(f"[bootstrap] {tname} already has data — skipping seed")
                continue
            if not rows:
                continue

            cols_order = [n for n, _ in seed_data.TABLE_COLS[tname]]
            placeholders = ", ".join("?" for _ in cols_order)
            col_list     = ", ".join(f'"{c2}"' for c2 in cols_order)
            c.executemany(
                f'INSERT OR IGNORE INTO "{tname}" ({col_list}) VALUES ({placeholders})',
                [[row.get(col) for col in cols_order] for row in rows],
            )
            c.commit()
            print(f"[bootstrap] seeded {len(rows)} rows into {tname}")

    # Pricing table (unchanged)
    try:
        with _conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS "model_pricing" (
                    model_prefix TEXT PRIMARY KEY,
                    input_cost_per_1m_tokens  REAL,
                    output_cost_per_1m_tokens REAL
                )
            """)
            if c.execute("SELECT COUNT(*) FROM model_pricing").fetchone()[0] == 0:
                for row in seed_data.gen_pricing():
                    c.execute(
                        "INSERT OR REPLACE INTO model_pricing VALUES (?,?,?)",
                        [row["model_prefix"],
                         row["input_cost_per_1m_tokens"],
                         row["output_cost_per_1m_tokens"]],
                    )
                c.commit()
                print("[bootstrap] seeded model_pricing")
    except Exception as e:
        print(f"[bootstrap] ERROR seeding model_pricing: {e}")
