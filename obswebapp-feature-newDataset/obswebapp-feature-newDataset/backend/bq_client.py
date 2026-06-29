"""
Data-client facade.

Routes every call to either the BigQuery backend (default) or the local SQLite
backend (APP_ENV=local). The local module never imports google-cloud-bigquery,
so running with APP_ENV=local works without any GCP credentials configured.

Public API (used by main.py and the bootstrap module) — exposes whichever
backend is active under the same names main.py expects:

    get_filter_options, get_overview_stats,
    query_logs, query_logs_severity_dist,
    query_traces, query_traces_timeseries,
    query_trace_list, query_trace_spans,
    query_metrics, bootstrap, MODE
"""
import os
from dotenv import load_dotenv
from contextvars import ContextVar

load_dotenv()

current_project: ContextVar[str] = ContextVar("current_project", default=None)

MODE = os.getenv("APP_ENV", "").strip().lower()

_COMMON = [
    "get_filter_options",
    "get_overview_stats",
    "query_logs",
    "query_logs_severity_dist",
    "query_traces",
    "query_traces_timeseries",
    "query_trace_list",
    "query_trace_spans",
    "query_metrics",
    "query_sessions",
    "query_sessions_timeseries",
    "query_session_detail",
    "query_llm_interactions",
    "query_llm_timeseries",
    "query_tool_executions",
    "query_tool_executions_timeseries",
    "query_errors",
    "query_errors_timeseries",
    "bootstrap",
]

if MODE == "local":
    print("[bq_client] APP_ENV=local -> using SQLite backend")
    from backends.local import (   # noqa: F401
        get_filter_options,
        get_overview_stats,
        query_logs,
        query_logs_severity_dist,
        query_traces,
        query_traces_timeseries,
        query_trace_list,
        query_trace_spans,
        query_metrics,
        query_sessions,
        query_sessions_timeseries,
        query_session_detail,
        query_llm_interactions,
        query_llm_timeseries,
        query_tool_executions,
        query_tool_executions_timeseries,
        query_errors,
        query_errors_timeseries,
        bootstrap,
    )
else:
    print(f"[bq_client] APP_ENV={MODE!r} -> using BigQuery backend")
    from backends.bq import (      # noqa: F401
        get_filter_options,
        get_overview_stats,
        query_logs,
        query_logs_severity_dist,
        query_traces,
        query_traces_timeseries,
        query_trace_list,
        query_trace_spans,
        query_metrics,
        query_sessions,
        query_sessions_timeseries,
        query_session_detail,
        query_llm_interactions,
        query_llm_timeseries,
        query_tool_executions,
        query_tool_executions_timeseries,
        query_errors,
        query_errors_timeseries,
        bootstrap,
    )
