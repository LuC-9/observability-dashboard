"""
BigQuery client for the OTel Observability Dashboard.

Queries wide_* pre-aggregated tables (migrated from otel_raw_* tables).
All user-supplied filter values use parameterized queries to prevent injection.
"""
import os
import traceback
import pandas as pd
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from dotenv import load_dotenv
import pricing

load_dotenv()

PROJECT    = os.getenv("GCP_PROJECT", "oa-apmena-observability-dv")
BQ_DATASET = os.getenv("BQ_DATASET",  "cds_otel")

print(f"[bq_client] project={PROJECT!r}  dataset={BQ_DATASET!r}")

# Create a single BigQuery client reused for all queries in this module
client = bigquery.Client(project=PROJECT)
print(f"[bq_client] BigQuery client initialised")

from bq_client import current_project


class DynamicTable:
    def __init__(self, name: str):
        self.name = name

    def __str__(self) -> str:
        return f"`{PROJECT}.{BQ_DATASET}.{self.name}`"

    def __format__(self, format_spec: str) -> str:
        return str(self)


# ── Wide table references ─────────────────────────────────────────────────────

AGENT_STEPS_DAILY   = DynamicTable("wide_agent_trace_steps_daily")
AGENT_DETAIL        = DynamicTable("wide_agent_traces_detail")
ERROR_SUMMARY_DAILY = DynamicTable("wide_error_summary_daily")
ERRORS_DETAIL       = DynamicTable("wide_errors_detail")
LLM_DETAIL          = DynamicTable("wide_llm_interactions_detail")
LLM_USAGE_DAILY     = DynamicTable("wide_llm_usage_daily")
LOGS_DAILY          = DynamicTable("wide_logs_daily")
LOGS_DETAIL         = DynamicTable("wide_logs_detail")
METRICS_DAILY       = DynamicTable("wide_metrics_daily")
METRICS_DETAIL      = DynamicTable("wide_metrics_detail")
SVC_HEALTH_DAILY    = DynamicTable("wide_service_health_daily")
SESSION_DAILY       = DynamicTable("wide_session_summary_daily")
SESSIONS_DETAIL     = DynamicTable("wide_sessions_detail")
SPANS_DETAIL        = DynamicTable("wide_spans_detail")
TOOL_DETAIL         = DynamicTable("wide_tool_executions_detail")
TOOL_USAGE_DAILY    = DynamicTable("wide_tool_usage_daily")
TRACES_DAILY        = DynamicTable("wide_traces_daily")


# ── Query helpers ─────────────────────────────────────────────────────────────

def _run(query: str, params: list | None = None) -> pd.DataFrame:
    """Execute a BigQuery SQL query and return a DataFrame."""
    job_config = bigquery.QueryJobConfig(query_parameters=params or [])
    # create_bqstorage_client=False forces REST endpoint, avoiding the need for
    # bigquery.readsessions.create (Storage Read API) permission.
    df = client.query(query, job_config=job_config).to_dataframe(create_bqstorage_client=False)
    # BQ INTEGER columns arrive as pandas nullable Int64; convert so NaN is preserved.
    nullable_int_cols = df.select_dtypes(
        include=["Int8","Int16","Int32","Int64","UInt8","UInt16","UInt32","UInt64"]).columns
    if len(nullable_int_cols):
        df[nullable_int_cols] = df[nullable_int_cols].astype("float64")
    return df


def _safe_run(label: str, query: str, params: list | None = None) -> pd.DataFrame | None:
    """Run a query and log any error; returns None on failure."""
    try:
        return _run(query, params)
    except Exception as e:
        print(f"[bq_client] ERROR in {label}: {e}")
        traceback.print_exc()
        return None


def _base_params(start_dt: datetime, end_dt: datetime) -> list:
    """Create the two time-range parameters used by almost every query."""
    params = [
        bigquery.ScalarQueryParameter("start", "TIMESTAMP", start_dt),
        bigquery.ScalarQueryParameter("end",   "TIMESTAMP", end_dt),
    ]
    proj = current_project.get()
    if proj and proj != "All":
        params.append(bigquery.ScalarQueryParameter("project_id", "STRING", proj))
    return params


def _proj_filter(col: str = "project_id") -> str:
    """Return a SQL snippet that filters by project_id if one is selected."""
    return f"AND {col} = @project_id" if current_project.get() else ""


def _date_range(col: str = "date") -> str:
    """Return a SQL date-range condition using the base @start/@end TIMESTAMP params."""
    return f"DATE({col}) BETWEEN DATE(@start) AND DATE(@end)"


def _safe_int(val, default: int = 0) -> int:
    """NaN/None-safe int cast — avoids 'cannot convert float NaN to integer'."""
    import math
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return int(val)
    except (TypeError, ValueError):
        return default



# ── Filter options ────────────────────────────────────────────────────────────

def get_filter_options(project: str = None) -> dict:
    """Return distinct dropdown values from wide tables."""
    if project and project != "All":
        current_project.set(project)
    elif project == "All":
        current_project.set(None)

    proj        = current_project.get()
    proj_filter = "AND project_id = @project_id" if proj else ""
    params      = [bigquery.ScalarQueryParameter("project_id", "STRING", proj)] if proj else []

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=30)).date().isoformat()
    today  =  datetime.now(tz=timezone.utc).date().isoformat()
    df_cond = f"AND date BETWEEN '{cutoff}' AND '{today}'"
    ts_cond = f"AND DATE(timestamp)  BETWEEN '{cutoff}' AND '{today}'"
    st_cond = f"AND DATE(start_time) BETWEEN '{cutoff}' AND '{today}'"

    services, environments, severities, agents = set(), set(), set(), set()
    metric_names, models, providers            = set(), set(), set()
    tool_names, tool_types, tool_statuses      = set(), set(), set()
    components, error_types, errors            = set(), set(), []

    if proj:
        # If project is selected, fetch distinct values from scoped detail tables
        proj_filter_llm = "AND project_id = @project_id"
        err_scope = f"AND (trace_id IN (SELECT trace_id FROM {SPANS_DETAIL} WHERE project_id = @project_id) OR error_id IN (SELECT log_id FROM {LOGS_DETAIL} WHERE project_id = @project_id))"
        tool_scope = f"AND trace_id IN (SELECT trace_id FROM {SPANS_DETAIL} WHERE project_id = @project_id)"
        agent_scope = f"AND trace_id IN (SELECT trace_id FROM {SPANS_DETAIL} WHERE project_id = @project_id)"

        simple_queries = [
            ("logs_detail.service_id",
             f"SELECT DISTINCT service_id AS v FROM {LOGS_DETAIL} WHERE service_id IS NOT NULL {ts_cond} AND project_id = @project_id", services),
            ("spans_detail.service_id",
             f"SELECT DISTINCT service_id AS v FROM {SPANS_DETAIL} WHERE service_id IS NOT NULL {st_cond} {proj_filter}", services),
            ("logs_detail.environment",
             f"SELECT DISTINCT environment AS v FROM {LOGS_DETAIL} WHERE environment IS NOT NULL {ts_cond} AND project_id = @project_id", environments),
            ("logs_detail.severity",
             f"SELECT DISTINCT severity AS v FROM {LOGS_DETAIL} WHERE severity IS NOT NULL {ts_cond} AND project_id = @project_id", severities),
            ("agent_steps.agent_name",
             f"SELECT DISTINCT agent_name AS v FROM {AGENT_DETAIL} WHERE agent_name IS NOT NULL {ts_cond} {agent_scope}", agents),
            ("metrics_detail.metric_name",
             f"SELECT DISTINCT metric_name AS v FROM {METRICS_DETAIL} WHERE metric_name IS NOT NULL {ts_cond} AND project_id = @project_id", metric_names),
            ("llm_usage.model_name",
             f"SELECT DISTINCT model_name AS v FROM {LLM_USAGE_DAILY} WHERE model_name IS NOT NULL {df_cond} {proj_filter_llm}", models),
            ("llm_usage.provider",
             f"SELECT DISTINCT provider AS v FROM {LLM_USAGE_DAILY} WHERE provider IS NOT NULL {df_cond} {proj_filter_llm}", providers),
            ("tool_detail.tool_name",
             f"SELECT DISTINCT tool_name AS v FROM {TOOL_DETAIL} WHERE tool_name IS NOT NULL {ts_cond} {tool_scope}", tool_names),
            ("tool_detail.tool_type",
             f"SELECT DISTINCT tool_type AS v FROM {TOOL_DETAIL} WHERE tool_type IS NOT NULL {ts_cond} {tool_scope}", tool_types),
            ("tool_detail.status",
             f"SELECT DISTINCT status AS v FROM {TOOL_DETAIL} WHERE status IS NOT NULL {ts_cond} {tool_scope}", tool_statuses),
            ("errors_detail.service_id",
             f"SELECT DISTINCT service_id AS v FROM {ERRORS_DETAIL} WHERE service_id IS NOT NULL {ts_cond} {err_scope}", components),
            ("errors_detail.error_type",
             f"SELECT DISTINCT error_type AS v FROM {ERRORS_DETAIL} WHERE error_type IS NOT NULL {ts_cond} {err_scope}", error_types),
        ]
    else:
        # Default global queries
        simple_queries = [
            ("logs_daily.service_id",
             f"SELECT DISTINCT service_id AS v FROM {LOGS_DAILY} WHERE service_id IS NOT NULL {df_cond}", services),
            ("spans_detail.service_id",
             f"SELECT DISTINCT service_id AS v FROM {SPANS_DETAIL} WHERE service_id IS NOT NULL {st_cond}", services),
            ("logs_daily.environment",
             f"SELECT DISTINCT environment AS v FROM {LOGS_DAILY} WHERE environment IS NOT NULL {df_cond}", environments),
            ("logs_daily.severity",
             f"SELECT DISTINCT severity AS v FROM {LOGS_DAILY} WHERE severity IS NOT NULL {df_cond}", severities),
            ("agent_steps.agent_name",
             f"SELECT DISTINCT agent_name AS v FROM {AGENT_STEPS_DAILY} WHERE agent_name IS NOT NULL {df_cond}", agents),
            ("metrics_daily.metric_name",
             f"SELECT DISTINCT metric_name AS v FROM {METRICS_DAILY} WHERE metric_name IS NOT NULL {df_cond}", metric_names),
            ("llm_usage.model_name",
             f"SELECT DISTINCT model_name AS v FROM {LLM_USAGE_DAILY} WHERE model_name IS NOT NULL {df_cond}", models),
            ("llm_usage.provider",
             f"SELECT DISTINCT provider AS v FROM {LLM_USAGE_DAILY} WHERE provider IS NOT NULL {df_cond}", providers),
            ("tool_usage.tool_name",
             f"SELECT DISTINCT tool_name AS v FROM {TOOL_USAGE_DAILY} WHERE tool_name IS NOT NULL {df_cond}", tool_names),
            ("tool_usage.tool_type",
             f"SELECT DISTINCT tool_type AS v FROM {TOOL_USAGE_DAILY} WHERE tool_type IS NOT NULL {df_cond}", tool_types),
            ("tool_detail.status",
             f"SELECT DISTINCT status AS v FROM {TOOL_DETAIL} WHERE status IS NOT NULL {ts_cond}", tool_statuses),
            ("errors_daily.service_id",
             f"SELECT DISTINCT service_id AS v FROM {ERROR_SUMMARY_DAILY} WHERE service_id IS NOT NULL {df_cond}", components),
            ("errors_daily.error_type",
             f"SELECT DISTINCT error_type AS v FROM {ERROR_SUMMARY_DAILY} WHERE error_type IS NOT NULL {df_cond}", error_types),
        ]
    import concurrent.futures

    def _fetch(label, q, p_arr, tgt_set):
        df = _safe_run(f"get_filter_options/{label}", q, p_arr)
        if df is not None and not df.empty:
            tgt_set.update(df["v"].dropna().tolist())
        elif df is None:
            errors.append(label)

    projects = set()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futs = []
        for label, q, target in simple_queries:
            futs.append(executor.submit(_fetch, label, q, params, target))
            
        for label, q in [
            ("projects/llm_detail", f"SELECT DISTINCT project_id AS v FROM {LLM_DETAIL} WHERE project_id IS NOT NULL {ts_cond}"),
            ("projects/spans_detail", f"SELECT DISTINCT project_id AS v FROM {SPANS_DETAIL} WHERE project_id IS NOT NULL {st_cond}"),
        ]:
            futs.append(executor.submit(_fetch, label, q, None, projects))
            
        concurrent.futures.wait(futs)

    projects_list = sorted(projects)
    if "All" not in projects_list:
        projects_list.insert(0, "All")
    if PROJECT not in projects_list and PROJECT != "All":
        projects_list.append(PROJECT)

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
    print(f"[bq_client] get_filter_options -> services={result['services']} errors={errors}")
    return result


# ── Overview ──────────────────────────────────────────────────────────────────

def get_overview_stats(start_dt: datetime, end_dt: datetime, service: str = "All") -> dict:
    """KPI numbers for the Overview tab — sourced from daily wide tables."""
    svc_filter = "AND service_id = @service" if service != "All" else ""
    params     = _base_params(start_dt, end_dt)
    if service != "All":
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))

    defaults = {
        "total_spans": 0, "error_spans": 0, "avg_duration_ms": 0.0,
        "total_cost_usd": 0.0, "total_input_tokens": 0, "total_output_tokens": 0,
        "total_logs": 0,
    }

    # Spans + duration + errors from wide_spans_detail
    df_h = _safe_run("overview/spans", f"""
        SELECT
            COUNT(*)                       AS total_spans,
            COUNTIF(status_code = 'ERROR') AS error_spans,
            AVG(duration_ms)               AS avg_duration_ms
        FROM {SPANS_DETAIL}
        WHERE start_time BETWEEN @start AND @end {svc_filter} {_proj_filter()}
    """, params)
    if df_h is not None and not df_h.empty:
        row = df_h.iloc[0]
        avg_val = row.get("avg_duration_ms")
        import math
        if avg_val is None or (isinstance(avg_val, float) and math.isnan(avg_val)):
            avg_val = 0.0
            
        defaults.update({
            "total_spans":     _safe_int(row.get("total_spans")),
            "error_spans":     _safe_int(row.get("error_spans")),
            "avg_duration_ms": round(float(avg_val), 2),
        })

    # LLM cost + tokens from wide_llm_interactions_detail
    df_l = _safe_run("overview/llm", f"""
        SELECT
            SUM(COALESCE(cost,          0)) AS total_cost_usd,
            SUM(COALESCE(tokens_input,  0)) AS total_input_tokens,
            SUM(COALESCE(tokens_output, 0)) AS total_output_tokens
        FROM {LLM_DETAIL}
        WHERE timestamp BETWEEN @start AND @end {svc_filter} {_proj_filter()}
    """, params)
    if df_l is not None and not df_l.empty:
        row = df_l.iloc[0]
        cost_val = row.get("total_cost_usd", 0)
        import math
        if cost_val is None or (isinstance(cost_val, float) and math.isnan(cost_val)):
            cost_val = 0.0
            
        defaults.update({
            "total_cost_usd":      round(float(cost_val), 6),
            "total_input_tokens":  _safe_int(row.get("total_input_tokens", 0)),
            "total_output_tokens": _safe_int(row.get("total_output_tokens", 0)),
        })

    # Log count from wide_logs_detail
    df_ld = _safe_run("overview/logs", f"""
        SELECT COUNT(*) AS total_logs
        FROM {LOGS_DETAIL}
        WHERE timestamp BETWEEN @start AND @end {svc_filter} {_proj_filter()}
    """, params)
    if df_ld is not None and not df_ld.empty:
        defaults["total_logs"] = _safe_int(df_ld.iloc[0].get("total_logs", 0))

    return defaults


# ── Logs ──────────────────────────────────────────────────────────────────────

def query_logs(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", severity: str = "All",
    environment: str = "All", limit: int = 500,
) -> pd.DataFrame:
    """Individual log rows from wide_logs_detail."""
    conditions = ["timestamp BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    proj = current_project.get()
    if proj:
        conditions.append("project_id = @project_id")

    if service     != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service",     "STRING", service))
    if severity    != "All":
        conditions.append("severity = @severity")
        params.append(bigquery.ScalarQueryParameter("severity",    "STRING", severity))
    if environment != "All":
        conditions.append("environment = @environment")
        params.append(bigquery.ScalarQueryParameter("environment", "STRING", environment))

    where = " AND ".join(conditions)
    try:
        return _run(f"""
            SELECT log_id, trace_id, span_id,
                   service_id  AS service_name,
                   environment, project_id, severity, message, timestamp,
                   CAST(NULL AS STRING) AS model
            FROM {LOGS_DETAIL}
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT {int(limit)}
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_logs: {e}")
        return pd.DataFrame(columns=[
            "log_id","trace_id","span_id","service_name","environment",
            "project_id","severity","message","timestamp","model"])


def query_logs_severity_dist(start_dt: datetime, end_dt: datetime, service: str = "All") -> pd.DataFrame:
    """Severity distribution from wide_logs_daily aggregates."""
    conditions = [_date_range("date")]
    params     = _base_params(start_dt, end_dt)

    if service != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))

    where = " AND ".join(conditions)
    try:
        return _run(f"""
            SELECT severity, SUM(log_count) AS count
            FROM {LOGS_DAILY}
            WHERE {where}
            GROUP BY severity
            ORDER BY count DESC
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_logs_severity_dist: {e}")
        return pd.DataFrame(columns=["severity", "count"])


# ── Traces / Spans ────────────────────────────────────────────────────────────

def query_traces(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", agent: str = "All",
    status: str = "All", limit: int = 500,
) -> pd.DataFrame:
    """Individual span rows from wide_spans_detail."""
    conditions = ["start_time BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    proj = current_project.get()
    if proj:
        conditions.append("project_id = @project_id")

    if service != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))
    if agent != "All":
        conditions.append("COALESCE(agent_name, agent_id) = @agent")
        params.append(bigquery.ScalarQueryParameter("agent", "STRING", agent))
    if status != "All":
        conditions.append("status_code = @status")
        params.append(bigquery.ScalarQueryParameter("status", "STRING", status))

    where = " AND ".join(conditions)
    try:
        return _run(f"""
            SELECT
                trace_id, span_id, parent_span_id,
                span_name, span_kind,
                start_time, end_time, duration_ms,
                status_code, status_message,
                service_id  AS service_name,
                agent_name,
                session_id, operation_name, environment, project_id
            FROM {SPANS_DETAIL}
            WHERE {where}
            ORDER BY start_time DESC
            LIMIT {int(limit)}
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_traces: {e}")
        return pd.DataFrame()


def query_traces_timeseries(start_dt: datetime, end_dt: datetime, service: str = "All") -> pd.DataFrame:
    """Daily span aggregates from wide_spans_detail to support project filtering."""
    conditions = ["start_time BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    if service != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))

    where = " AND ".join(conditions) + " " + _proj_filter()
    try:
        df = _run(f"""
            SELECT
                DATE(start_time)               AS hour,
                AVG(duration_ms)               AS avg_duration_ms,
                COUNTIF(status_code = 'ERROR') AS error_count,
                COUNT(*)                       AS span_count
            FROM {SPANS_DETAIL}
            WHERE {where}
            GROUP BY hour
            ORDER BY hour
        """, params)

        llm_where = " AND ".join([c.replace("start_time", "timestamp") for c in conditions]) + " " + _proj_filter()
        # Supplement with daily cost/token data
        df_cost = _safe_run("traces_timeseries/cost", f"""
            SELECT
                DATE(timestamp)                 AS hour,
                SUM(COALESCE(cost, 0))          AS total_cost_usd,
                SUM(COALESCE(tokens_input, 0))  AS input_tokens,
                SUM(COALESCE(tokens_output, 0)) AS output_tokens
            FROM {LLM_DETAIL}
            WHERE {llm_where}
            GROUP BY hour
        """, params)
        if df_cost is not None and not df_cost.empty:
            if not df.empty:
                df = df.merge(df_cost, on="hour", how="outer")
                for c in ["avg_duration_ms", "error_count", "span_count", "total_cost_usd", "input_tokens", "output_tokens"]:
                    if c in df.columns:
                        df[c] = df[c].fillna(0)
            else:
                df = df_cost
        return df
    except Exception as e:
        print(f"[bq_client] ERROR in query_traces_timeseries: {e}")
        return pd.DataFrame()


def query_trace_list(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", agent: str = "All",
    status: str = "All", limit: int = 200,
) -> pd.DataFrame:
    """One row per trace_id — summary from wide_spans_detail."""
    conditions = ["start_time BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    proj = current_project.get()
    if proj:
        conditions.append("project_id = @project_id")

    if service != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))
    if agent != "All":
        conditions.append("COALESCE(agent_name, agent_id) = @agent")
        params.append(bigquery.ScalarQueryParameter("agent", "STRING", agent))

    where     = " AND ".join(conditions)
    err_having = f"HAVING session_status = '{status}'" if status != "All" else ""
    try:
        return _run(f"""
            SELECT
                trace_id,
                MIN(start_time)                                              AS trace_start,
                TIMESTAMP_DIFF(MAX(end_time), MIN(start_time), MILLISECOND) AS total_duration_ms,
                COUNT(*)                                                     AS span_count,
                COUNTIF(status_code = 'ERROR')                               AS error_count,
                ANY_VALUE(service_id)                                        AS service_name,
                STRING_AGG(DISTINCT agent_name)                              AS agents,
                IF(COUNTIF(status_code='ERROR') > 0, 'failed', 'completed') AS session_status
            FROM {SPANS_DETAIL}
            WHERE {where}
            GROUP BY trace_id
            {err_having}
            ORDER BY trace_start DESC
            LIMIT {int(limit)}
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_trace_list: {e}")
        return pd.DataFrame(columns=[
            "trace_id","trace_start","total_duration_ms","span_count",
            "error_count","service_name","agents"])


def query_trace_spans(trace_id: str) -> pd.DataFrame:
    """All spans for a single trace_id from wide_spans_detail."""
    lookback = datetime.now(tz=timezone.utc) - timedelta(days=30)
    params   = [
        bigquery.ScalarQueryParameter("trace_id",  "STRING",    trace_id),
        bigquery.ScalarQueryParameter("lookback",  "TIMESTAMP", lookback),
    ]
    proj = current_project.get()
    proj_cond = "AND project_id = @project_id" if proj else ""
    if proj:
        params.append(bigquery.ScalarQueryParameter("project_id", "STRING", proj))
    try:
        return _run(f"""
            SELECT
                trace_id, span_id, parent_span_id,
                span_name, span_kind,
                start_time, end_time, duration_ms,
                status_code, status_message,
                service_id AS service_name, agent_name,
                session_id, operation_name, environment, project_id,
                CAST(NULL AS STRING) AS attributes_json
            FROM {SPANS_DETAIL}
            WHERE start_time >= @lookback AND trace_id = @trace_id {proj_cond}
            ORDER BY start_time
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_trace_spans: {e}")
        return pd.DataFrame()


# ── Metrics ───────────────────────────────────────────────────────────────────

def query_metrics(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", agent: str = "All",
    metric_name: str = "All",
) -> pd.DataFrame:
    """Individual metric data points from wide_metrics_detail."""
    conditions = ["timestamp BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    proj = current_project.get()
    if proj:
        conditions.append("project_id = @project_id")

    if service     != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service",     "STRING", service))
    if agent       != "All":
        conditions.append("agent_name = @agent")
        params.append(bigquery.ScalarQueryParameter("agent",       "STRING", agent))
    if metric_name != "All":
        conditions.append("metric_name = @metric_name")
        params.append(bigquery.ScalarQueryParameter("metric_name", "STRING", metric_name))

    where = " AND ".join(conditions)
    try:
        return _run(f"""
            SELECT
                timestamp, metric_name, metric_type,
                value_int, value_double,
                histogram_sum
            FROM {METRICS_DETAIL}
            WHERE {where}
            ORDER BY timestamp, metric_name
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_metrics: {e}")
        return pd.DataFrame()


# ── Sessions ──────────────────────────────────────────────────────────────────

def query_sessions(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", agent: str = "All", status: str = "All",
) -> pd.DataFrame:
    """One session per row from wide_sessions_detail."""
    conditions = ["start_time BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    if service != "All":
        conditions.append(f"session_id IN (SELECT session_id FROM {SPANS_DETAIL} WHERE service_id = @service)")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))

    if agent != "All":
        conditions.append("COALESCE(agent_name, agent_id) = @agent")
        params.append(bigquery.ScalarQueryParameter("agent", "STRING", agent))

    proj = current_project.get()
    if proj:
        conditions.append(f"session_id IN (SELECT session_id FROM {SPANS_DETAIL} WHERE project_id = @project_id)")

    where = " AND ".join(conditions)
    try:
        df = _run(f"""
            SELECT
                session_id,
                COALESCE(agent_id, agent_name) AS agent_id,
                start_time, end_time,
                total_spans                    AS total_turns,
                'completed'                    AS status,
                CAST(NULL AS FLOAT64)          AS total_cost
            FROM {SESSIONS_DETAIL}
            WHERE {where}
            ORDER BY start_time DESC
            LIMIT 500
        """, params)
        if status != "All" and not df.empty:
            df = df[df["status"] == status]
        return df
    except Exception as e:
        print(f"[bq_client] ERROR in query_sessions: {e}")
        return pd.DataFrame()


def query_sessions_timeseries(start_dt: datetime, end_dt: datetime, service: str = "All") -> pd.DataFrame:
    """Daily session counts from wide_sessions_detail."""
    conditions = ["start_time BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    if service != "All":
        conditions.append(f"session_id IN (SELECT session_id FROM {SPANS_DETAIL} WHERE service_id = @service)")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))

    proj = current_project.get()
    if proj:
        conditions.append(f"session_id IN (SELECT session_id FROM {SPANS_DETAIL} WHERE project_id = @project_id)")

    where = " AND ".join(conditions)
    try:
        return _run(f"""
            SELECT DATE(start_time) AS hour, COUNT(*) AS count
            FROM {SESSIONS_DETAIL}
            WHERE {where}
            GROUP BY hour ORDER BY hour
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_sessions_timeseries: {e}")
        return pd.DataFrame()


def query_session_detail(session_id: str) -> dict:
    """Full detail for one session — multi-table join."""
    lookback = datetime.now(tz=timezone.utc) - timedelta(days=30)
    params_base = [
        bigquery.ScalarQueryParameter("session_id", "STRING",    session_id),
        bigquery.ScalarQueryParameter("lookback",   "TIMESTAMP", lookback),
    ]

    # Session header
    sess_df = _safe_run("session_detail/session", f"""
        SELECT session_id, COALESCE(agent_id, agent_name) AS agent_id,
               start_time, end_time, total_spans, duration_sec
        FROM {SESSIONS_DETAIL}
        WHERE session_id = @session_id AND start_time >= @lookback
        LIMIT 1
    """, params_base)

    empty = {
        "session":          pd.DataFrame(),
        "agent_traces":     pd.DataFrame(),
        "llm_interactions": pd.DataFrame(),
        "tool_executions":  pd.DataFrame(),
    }
    if sess_df is None or sess_df.empty:
        return empty

    row = sess_df.iloc[0]
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
    at = _safe_run("session_detail/agent_traces", f"""
        SELECT step_number, step_type, latency_ms,
               agent_name, tool_id, llm_call_id, timestamp
        FROM {AGENT_DETAIL}
        WHERE session_id = @session_id AND timestamp >= @lookback
        ORDER BY step_number
    """, params_base)
    if at is not None and not at.empty:
        at["decision"]  = ""
        at["tool_name"] = at["tool_id"].fillna("")
        at["step_type"] = at["step_type"].fillna("")
    else:
        at = pd.DataFrame()

    # LLM interactions
    llm = _safe_run("session_detail/llm", f"""
        SELECT llm_call_id, model_name, provider, tokens_input, tokens_output,
               cost, latency_ms, finish_reason, timestamp
        FROM {LLM_DETAIL}
        WHERE session_id = @session_id AND timestamp >= @lookback
        ORDER BY timestamp
    """, params_base)
    if llm is not None and not llm.empty:
        llm["status"] = "success"
        sess.at[0, "total_cost"] = round(float(llm["cost"].fillna(0).sum()), 6)
    else:
        llm = pd.DataFrame()

    # Tool executions
    tools = _safe_run("session_detail/tools", f"""
        SELECT execution_id, tool_name, tool_type, status, error_message,
               latency_ms, trace_id, timestamp
        FROM {TOOL_DETAIL}
        WHERE session_id = @session_id AND timestamp >= @lookback
        ORDER BY timestamp
    """, params_base)
    if tools is None:
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
    """Individual LLM calls from wide_llm_interactions_detail."""
    conditions = ["timestamp BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    proj = current_project.get()
    if proj:
        conditions.append("project_id = @project_id")

    where = " AND ".join(conditions)
    try:
        df = _run(f"""
            SELECT
                llm_call_id, trace_id, session_id,
                agent_id, agent_name, model_name, provider,
                service_id AS service_name, project_id, environment,
                tokens_input, tokens_output, total_tokens,
                cost, temperature, finish_reason, latency_ms, timestamp
            FROM {LLM_DETAIL}
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT 1000
        """, params)
        if df.empty:
            return df
        # Apply pricing fallback where cost is null/zero
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
        print(f"[bq_client] ERROR in query_llm_interactions: {e}")
        return pd.DataFrame()


def query_llm_timeseries(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Daily LLM token aggregates from wide_llm_usage_daily."""
    params = _base_params(start_dt, end_dt)
    try:
        return _run(f"""
            SELECT date AS hour,
                   SUM(total_tokens_input)  AS tokens_input,
                   SUM(total_tokens_output) AS tokens_output
            FROM {LLM_USAGE_DAILY}
            WHERE {_date_range("date")}
            GROUP BY date ORDER BY date
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_llm_timeseries: {e}")
        return pd.DataFrame()


# ── Tool Executions ───────────────────────────────────────────────────────────

def query_tool_executions(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", tool_name: str = "All", tool_type: str = "All", status: str = "All",
) -> pd.DataFrame:
    """Individual tool calls from wide_tool_executions_detail."""
    conditions = ["timestamp BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    if service != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))

    if tool_name != "All":
        conditions.append("tool_name = @tool_name")
        params.append(bigquery.ScalarQueryParameter("tool_name", "STRING", tool_name))
    if tool_type != "All":
        conditions.append("tool_type = @tool_type")
        params.append(bigquery.ScalarQueryParameter("tool_type", "STRING", tool_type))
    if status != "All":
        conditions.append("status = @status")
        params.append(bigquery.ScalarQueryParameter("status", "STRING", status))

    proj = current_project.get()
    if proj:
        conditions.append(f"trace_id IN (SELECT trace_id FROM {SPANS_DETAIL} WHERE project_id = @project_id)")

    where = " AND ".join(conditions)
    try:
        return _run(f"""
            SELECT
                execution_id, trace_id, session_id,
                agent_id, agent_name, tool_name,
                tool_name  AS tool_display_name,
                tool_type, status, error_message,
                latency_ms, tool_input, tool_output, timestamp
            FROM {TOOL_DETAIL}
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT 1000
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_tool_executions: {e}")
        return pd.DataFrame()


def query_tool_executions_timeseries(start_dt: datetime, end_dt: datetime, service: str = "All") -> pd.DataFrame:
    """Daily tool execution counts from wide_tool_executions_detail."""
    conditions = ["timestamp BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    if service != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))

    proj = current_project.get()
    if proj:
        conditions.append(f"trace_id IN (SELECT trace_id FROM {SPANS_DETAIL} WHERE project_id = @project_id)")

    where = " AND ".join(conditions)
    try:
        return _run(f"""
            SELECT DATE(timestamp) AS hour, COUNT(*) AS count
            FROM {TOOL_DETAIL}
            WHERE {where}
            GROUP BY hour ORDER BY hour
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_tool_executions_timeseries: {e}")
        return pd.DataFrame()


# ── Errors ────────────────────────────────────────────────────────────────────

def query_errors(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", component: str = "All", error_type: str = "All", severity: str = "All",
) -> pd.DataFrame:
    """Individual error records from wide_errors_detail."""
    conditions = ["timestamp BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    if service != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))

    if component != "All":
        conditions.append("service_id = @component")
        params.append(bigquery.ScalarQueryParameter("component", "STRING", component))
    if error_type != "All":
        conditions.append("error_type = @error_type")
        params.append(bigquery.ScalarQueryParameter("error_type", "STRING", error_type))
    if severity != "All":
        conditions.append("UPPER(severity) = @severity_upper")
        params.append(bigquery.ScalarQueryParameter("severity_upper", "STRING", str(severity).upper()))

    proj = current_project.get()
    if proj:
        conditions.append(f"""(
            trace_id IN (SELECT trace_id FROM {SPANS_DETAIL} WHERE project_id = @project_id)
            OR
            error_id IN (SELECT log_id FROM {LOGS_DETAIL} WHERE project_id = @project_id)
        )""")

    where = " AND ".join(conditions)
    try:
        df = _run(f"""
            SELECT
                error_id,
                service_id  AS component,
                error_type, error_message, severity,
                session_id, trace_id, span_id,
                agent_id, agent_name, source, timestamp
            FROM {ERRORS_DETAIL}
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT 1000
        """, params)
        if not df.empty:
            df["severity"] = df["severity"].astype(str).str.upper().replace({"WARN": "WARNING"})
        return df
    except Exception as e:
        print(f"[bq_client] ERROR in query_errors: {e}")
        return pd.DataFrame(columns=[
            "error_id","component","error_type","error_message",
            "severity","session_id","trace_id","timestamp"])


def query_errors_timeseries(
    start_dt: datetime, end_dt: datetime,
    service: str = "All", component: str = "All", error_type: str = "All", severity: str = "All"
) -> pd.DataFrame:
    """Daily error counts from wide_errors_detail."""
    conditions = ["timestamp BETWEEN @start AND @end"]
    params     = _base_params(start_dt, end_dt)

    if service != "All":
        conditions.append("service_id = @service")
        params.append(bigquery.ScalarQueryParameter("service", "STRING", service))

    if component != "All":
        conditions.append("service_id = @component")
        params.append(bigquery.ScalarQueryParameter("component", "STRING", component))
    if error_type != "All":
        conditions.append("error_type = @error_type")
        params.append(bigquery.ScalarQueryParameter("error_type", "STRING", error_type))
    if severity != "All":
        sel = str(severity).upper()
        if sel in ("WARN", "WARNING"):
            conditions.append("UPPER(severity) IN ('WARN','WARNING')")
        else:
            conditions.append("UPPER(severity) = @severity_upper")
            params.append(bigquery.ScalarQueryParameter("severity_upper", "STRING", sel))

    proj = current_project.get()
    if proj:
        conditions.append(f"""(
            trace_id IN (SELECT trace_id FROM {SPANS_DETAIL} WHERE project_id = @project_id)
            OR
            error_id IN (SELECT log_id FROM {LOGS_DETAIL} WHERE project_id = @project_id)
        )""")

    where = " AND ".join(conditions)
    try:
        return _run(f"""
            SELECT DATE(timestamp) AS hour, COUNT(*) AS count
            FROM {ERRORS_DETAIL}
            WHERE {where}
            GROUP BY hour ORDER BY hour
        """, params)
    except Exception as e:
        print(f"[bq_client] ERROR in query_errors_timeseries: {e}")
        return pd.DataFrame()


# ── Bootstrap (local-dev check only — wide tables are externally maintained) ──

def bootstrap() -> None:
    """
    Wide tables are pre-built by the data pipeline and are not created/seeded here.
    This function verifies that the expected tables are reachable and prints their status.
    """
    print(f"[bootstrap] BigQuery mode — project={PROJECT!r} dataset={BQ_DATASET!r}")
    tables = [
        "wide_agent_trace_steps_daily", "wide_agent_traces_detail",
        "wide_error_summary_daily",       "wide_errors_detail",
        "wide_llm_interactions_detail",   "wide_llm_usage_daily",
        "wide_logs_daily",                "wide_logs_detail",
        "wide_metrics_daily",             "wide_metrics_detail",
        "wide_service_health_daily",      "wide_session_summary_daily",
        "wide_sessions_detail",           "wide_spans_detail",
        "wide_tool_executions_detail",    "wide_tool_usage_daily",
        "wide_traces_daily",
    ]
    for tname in tables:
        table_ref = f"{PROJECT}.{BQ_DATASET}.{tname}"
        try:
            client.get_table(table_ref)
            print(f"[bootstrap] ✓ {tname}")
        except Exception as e:
            print(f"[bootstrap] ✗ {tname}: {e}")
