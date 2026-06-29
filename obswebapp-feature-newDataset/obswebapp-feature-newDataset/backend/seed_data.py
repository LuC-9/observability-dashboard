"""
Shared dummy-data generators + wide table column definitions used by both
the BigQuery bootstrap and the local SQLite bootstrap.

No BigQuery / Google imports here on purpose, so the module can be loaded
in local mode without GCP credentials.

Tables covered (wide_* schema):
  wide_agent_trace_steps_daily    wide_agent_traces_detail
  wide_error_summary_daily        wide_errors_detail
  wide_llm_interactions_detail    wide_llm_usage_daily
  wide_logs_daily                 wide_logs_detail
  wide_metrics_daily              wide_metrics_detail
  wide_service_health_daily       wide_session_summary_daily
  wide_sessions_detail            wide_spans_detail
  wide_tool_executions_detail     wide_tool_usage_daily
  wide_traces_daily
"""
import json
import random
import uuid
from datetime import date, datetime, timedelta, timezone


# ── Shared fixtures ───────────────────────────────────────────────────────────

SERVICES     = [
    "add_cloudrun_agentobs",
    "langgraph_summary_agentobs",
    "adk_calc_agentobs",
    "add_agentengine_agentobs",
]
ENVIRONMENTS = ["dev", "staging"]
AGENTS       = [
    "ADD_Orchestrator_Agent",
    "COMMERCE_DOMAIN_AGENT",
    "CONSUMER_DOMAIN_AGENT",
    "CALCULATION_AGENT",
    "ALL_DOMAIN_AGENT",
]
MODELS       = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"]
PROVIDERS    = ["gcp.vertex.agent", "vertex_ai"]
SEVERITIES   = ["INFO", "INFO", "INFO", "WARN", "DEBUG", "ERROR"]
STEP_TYPES   = ["llm", "tool", "other"]
TOOL_NAMES   = ["transfer_to_agent", "rag_query", "get_current_datetime", "PARALLEL_DOMAIN_AGENT"]
TOOL_TYPES   = ["TransferToAgentTool", "FunctionTool", "AgentTool"]
METRIC_NAMES = [
    ("agent.latency",             "Histogram"),
    ("gen_ai.client.token.usage", "Counter"),
    ("http.client.duration",      "Histogram"),
]
OPERATION_NAMES = ["llm", "tool", "other", "db"]
PROJECT_IDS  = ["oa-apmena-techsandbox-ap-dv", "oa-apmena-techsandbox-ap-prod"]
PROJECT_ID   = PROJECT_IDS[0]

LOG_MESSAGES = [
    '{"raw":"node.start node=router framework=langgraph"}',
    '{"raw":"AFC is enabled with max remote calls: 10."}',
    '{"raw":"HTTP Request: POST https://us-central1-aiplatform.googleapis.com/..."}',
    '{"raw":"node.done node=router duration_ms=3487.8"}',
    '{"raw":"request received"}',
    '{"raw":"agent invocation completed"}',
]

ERROR_MESSAGES = [
    '{"raw":"Failed to export logs batch due to timeout, max retries or shutdown."}',
    '{"raw":"Exception while exporting Log."}',
    '{"raw":"Error during async stream generation: 404 NOT_FOUND."}',
]

SPAN_KINDS   = ["CLIENT", "SERVER", "INTERNAL"]
FINISH_REASONS = ["stop", "length", "tool_calls"]


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _isodate(d: date) -> str:
    return d.isoformat()


# ── Column definitions (name, sqlite_type) ───────────────────────────────────
# SQLite columns; BigQuery schemas live in backends/bq.py.

AGENT_TRACES_STEPS_DAILY_COLS = [
    ("date",                 "TEXT"),
    ("agent_id",             "TEXT"),
    ("agent_name",           "TEXT"),
    ("step_type",            "TEXT"),
    ("environment",          "TEXT"),
    ("total_steps",          "INTEGER"),
    ("unique_sessions",      "INTEGER"),
    ("avg_latency_ms",       "REAL"),
    ("max_steps_in_session", "INTEGER"),
]

AGENT_TRACES_DETAIL_COLS = [
    ("agent_trace_id", "TEXT"),
    ("trace_id",       "TEXT"),
    ("session_id",     "TEXT"),
    ("agent_id",       "TEXT"),
    ("agent_name",     "TEXT"),
    ("tool_id",        "TEXT"),
    ("llm_call_id",    "TEXT"),
    ("service_id",     "TEXT"),
    ("environment",    "TEXT"),
    ("step_number",    "INTEGER"),
    ("step_type",      "TEXT"),
    ("latency_ms",     "REAL"),
    ("timestamp",      "TEXT"),
]

ERROR_SUMMARY_DAILY_COLS = [
    ("date",              "TEXT"),
    ("service_id",        "TEXT"),
    ("agent_id",          "TEXT"),
    ("agent_name",        "TEXT"),
    ("error_type",        "TEXT"),
    ("severity",          "TEXT"),
    ("environment",       "TEXT"),
    ("error_count",       "INTEGER"),
    ("affected_traces",   "INTEGER"),
    ("affected_sessions", "INTEGER"),
    ("first_occurrence",  "TEXT"),
    ("last_occurrence",   "TEXT"),
    ("sample_message",    "TEXT"),
]

ERRORS_DETAIL_COLS = [
    ("error_id",      "TEXT"),
    ("trace_id",      "TEXT"),
    ("span_id",       "TEXT"),
    ("session_id",    "TEXT"),
    ("agent_id",      "TEXT"),
    ("agent_name",    "TEXT"),
    ("service_id",    "TEXT"),
    ("environment",   "TEXT"),
    ("error_type",    "TEXT"),
    ("severity",      "TEXT"),
    ("status_code",   "TEXT"),
    ("error_message", "TEXT"),
    ("source",        "TEXT"),
    ("timestamp",     "TEXT"),
]

LLM_INTERACTIONS_DETAIL_COLS = [
    ("llm_call_id",   "TEXT"),
    ("trace_id",      "TEXT"),
    ("session_id",    "TEXT"),
    ("agent_id",      "TEXT"),
    ("agent_name",    "TEXT"),
    ("model_name",    "TEXT"),
    ("provider",      "TEXT"),
    ("service_id",    "TEXT"),
    ("project_id",    "TEXT"),
    ("environment",   "TEXT"),
    ("tokens_input",  "INTEGER"),
    ("tokens_output", "INTEGER"),
    ("total_tokens",  "INTEGER"),
    ("cost",          "REAL"),
    ("temperature",   "REAL"),
    ("finish_reason", "TEXT"),
    ("latency_ms",    "REAL"),
    ("timestamp",     "TEXT"),
]

LLM_USAGE_DAILY_COLS = [
    ("date",                "TEXT"),
    ("agent_id",            "TEXT"),
    ("agent_name",          "TEXT"),
    ("model_name",          "TEXT"),
    ("provider",            "TEXT"),
    ("service_id",          "TEXT"),
    ("project_id",          "TEXT"),
    ("environment",         "TEXT"),
    ("total_llm_calls",     "INTEGER"),
    ("total_tokens_input",  "INTEGER"),
    ("total_tokens_output", "INTEGER"),
    ("total_tokens",        "INTEGER"),
    ("total_cost",          "REAL"),
    ("avg_latency_ms",      "REAL"),
    ("p95_latency_ms",      "REAL"),
]

LOGS_DAILY_COLS = [
    ("date",             "TEXT"),
    ("service_id",       "TEXT"),
    ("severity",         "TEXT"),
    ("environment",      "TEXT"),
    ("log_count",        "INTEGER"),
    ("unique_traces",    "INTEGER"),
    ("first_occurrence", "TEXT"),
    ("last_occurrence",  "TEXT"),
]

LOGS_DETAIL_COLS = [
    ("log_id",      "TEXT"),
    ("trace_id",    "TEXT"),
    ("span_id",     "TEXT"),
    ("service_id",  "TEXT"),
    ("environment", "TEXT"),
    ("project_id",  "TEXT"),
    ("severity",    "TEXT"),
    ("message",     "TEXT"),
    ("timestamp",   "TEXT"),
]

METRICS_DAILY_COLS = [
    ("date",             "TEXT"),
    ("service_id",       "TEXT"),
    ("metric_name",      "TEXT"),
    ("metric_type",      "TEXT"),
    ("environment",      "TEXT"),
    ("data_point_count", "INTEGER"),
    ("avg_value",        "REAL"),
    ("min_value",        "REAL"),
    ("max_value",        "REAL"),
    ("sum_value",        "REAL"),
]

METRICS_DETAIL_COLS = [
    ("metric_point_id", "TEXT"),
    ("metric_name",     "TEXT"),
    ("metric_type",     "TEXT"),
    ("service_id",      "TEXT"),
    ("environment",     "TEXT"),
    ("project_id",      "TEXT"),
    ("agent_name",      "TEXT"),
    ("value_int",       "INTEGER"),
    ("value_double",    "REAL"),
    ("histogram_sum",   "REAL"),
    ("histogram_count", "INTEGER"),
    ("histogram_min",   "REAL"),
    ("histogram_max",   "REAL"),
    ("timestamp",       "TEXT"),
]

SERVICE_HEALTH_DAILY_COLS = [
    ("date",                 "TEXT"),
    ("service_id",           "TEXT"),
    ("environment",          "TEXT"),
    ("total_spans",          "INTEGER"),
    ("total_logs",           "INTEGER"),
    ("error_log_count",      "INTEGER"),
    ("avg_span_duration_ms", "REAL"),
    ("p95_span_duration_ms", "REAL"),
    ("error_rate",           "REAL"),
]

SESSION_SUMMARY_DAILY_COLS = [
    ("date",                     "TEXT"),
    ("agent_id",                 "TEXT"),
    ("agent_name",               "TEXT"),
    ("total_sessions",           "INTEGER"),
    ("unique_users",             "INTEGER"),
    ("avg_spans_per_session",    "REAL"),
    ("avg_session_duration_sec", "REAL"),
]

SESSIONS_DETAIL_COLS = [
    ("session_id",   "TEXT"),
    ("user_id",      "TEXT"),
    ("agent_id",     "TEXT"),
    ("agent_name",   "TEXT"),
    ("start_time",   "TEXT"),
    ("end_time",     "TEXT"),
    ("total_spans",  "INTEGER"),
    ("duration_sec", "REAL"),
]

SPANS_DETAIL_COLS = [
    ("trace_id",       "TEXT"),
    ("span_id",        "TEXT"),
    ("parent_span_id", "TEXT"),
    ("service_id",     "TEXT"),
    ("agent_id",       "TEXT"),
    ("agent_name",     "TEXT"),
    ("model_id",       "TEXT"),
    ("session_id",     "TEXT"),
    ("operation_name", "TEXT"),
    ("span_name",      "TEXT"),
    ("span_kind",      "TEXT"),
    ("environment",    "TEXT"),
    ("project_id",     "TEXT"),
    ("start_time",     "TEXT"),
    ("end_time",       "TEXT"),
    ("duration_ms",    "REAL"),
    ("status_code",    "TEXT"),
    ("status_message", "TEXT"),
    ("attributes_json", "TEXT"),
]

TOOL_EXECUTIONS_DETAIL_COLS = [
    ("execution_id",  "TEXT"),
    ("trace_id",      "TEXT"),
    ("session_id",    "TEXT"),
    ("agent_id",      "TEXT"),
    ("agent_name",    "TEXT"),
    ("tool_name",     "TEXT"),
    ("tool_type",     "TEXT"),
    ("service_id",    "TEXT"),
    ("environment",   "TEXT"),
    ("tool_input",    "TEXT"),
    ("tool_output",   "TEXT"),
    ("status",        "TEXT"),
    ("error_message", "TEXT"),
    ("latency_ms",    "REAL"),
    ("timestamp",     "TEXT"),
]

TOOL_USAGE_DAILY_COLS = [
    ("date",             "TEXT"),
    ("tool_name",        "TEXT"),
    ("tool_type",        "TEXT"),
    ("agent_id",         "TEXT"),
    ("agent_name",       "TEXT"),
    ("environment",      "TEXT"),
    ("total_executions", "INTEGER"),
    ("success_count",    "INTEGER"),
    ("failure_count",    "INTEGER"),
    ("success_rate",     "REAL"),
    ("avg_latency_ms",   "REAL"),
    ("p95_latency_ms",   "REAL"),
]

TRACES_DAILY_COLS = [
    ("date",            "TEXT"),
    ("service_id",      "TEXT"),
    ("operation_name",  "TEXT"),
    ("environment",     "TEXT"),
    ("total_spans",     "INTEGER"),
    ("avg_duration_ms", "REAL"),
    ("p50_duration_ms", "REAL"),
    ("p95_duration_ms", "REAL"),
    ("p99_duration_ms", "REAL"),
    ("error_count",     "INTEGER"),
    ("success_count",   "INTEGER"),
]


# ── Registry ─────────────────────────────────────────────────────────────────

TABLE_COLS = {
    "wide_agent_trace_steps_daily": AGENT_TRACES_STEPS_DAILY_COLS,
    "wide_agent_traces_detail":      AGENT_TRACES_DETAIL_COLS,
    "wide_error_summary_daily":      ERROR_SUMMARY_DAILY_COLS,
    "wide_errors_detail":            ERRORS_DETAIL_COLS,
    "wide_llm_interactions_detail":  LLM_INTERACTIONS_DETAIL_COLS,
    "wide_llm_usage_daily":          LLM_USAGE_DAILY_COLS,
    "wide_logs_daily":               LOGS_DAILY_COLS,
    "wide_logs_detail":              LOGS_DETAIL_COLS,
    "wide_metrics_daily":            METRICS_DAILY_COLS,
    "wide_metrics_detail":           METRICS_DETAIL_COLS,
    "wide_service_health_daily":     SERVICE_HEALTH_DAILY_COLS,
    "wide_session_summary_daily":    SESSION_SUMMARY_DAILY_COLS,
    "wide_sessions_detail":          SESSIONS_DETAIL_COLS,
    "wide_spans_detail":             SPANS_DETAIL_COLS,
    "wide_tool_executions_detail":   TOOL_EXECUTIONS_DETAIL_COLS,
    "wide_tool_usage_daily":         TOOL_USAGE_DAILY_COLS,
    "wide_traces_daily":             TRACES_DAILY_COLS,
}

# Partition column per table — used by the local bootstrap data-presence check.
PARTITION_COL = {
    "wide_agent_trace_steps_daily": "date",
    "wide_agent_traces_detail":      "timestamp",
    "wide_error_summary_daily":      "date",
    "wide_errors_detail":            "timestamp",
    "wide_llm_interactions_detail":  "timestamp",
    "wide_llm_usage_daily":          "date",
    "wide_logs_daily":               "date",
    "wide_logs_detail":              "timestamp",
    "wide_metrics_daily":            "date",
    "wide_metrics_detail":           "timestamp",
    "wide_service_health_daily":     "date",
    "wide_session_summary_daily":    "date",
    "wide_sessions_detail":          "start_time",
    "wide_spans_detail":             "start_time",
    "wide_tool_executions_detail":   "timestamp",
    "wide_tool_usage_daily":         "date",
    "wide_traces_daily":             "date",
}


# ── Seed generators ───────────────────────────────────────────────────────────

def _days(now: datetime, n: int = 14) -> list[date]:
    return [(now - timedelta(days=i)).date() for i in range(n)]


def gen_sessions(now: datetime | None = None, n: int = 30) -> list[dict]:
    now = now or datetime.now(tz=timezone.utc)
    rows = []
    for _ in range(n):
        start = now - timedelta(seconds=random.randint(60, 7 * 24 * 3600))
        dur   = random.uniform(1, 120)
        end   = start + timedelta(seconds=dur)
        rows.append({
            "session_id":   str(uuid.uuid4()),
            "user_id":      None,
            "agent_id":     random.choice(AGENTS),
            "agent_name":   random.choice(AGENTS),
            "start_time":   _iso(start),
            "end_time":     _iso(end),
            "total_spans":  random.randint(1, 8),
            "duration_sec": round(dur, 2),
        })
    return rows


def gen_spans(now: datetime | None = None, n_traces: int = 25) -> list[dict]:
    now   = now or datetime.now(tz=timezone.utc)
    rows  = []
    for _ in range(n_traces):
        trace_id   = uuid.uuid4().hex
        service    = random.choice(SERVICES)
        agent      = random.choice(AGENTS)
        env        = random.choice(ENVIRONMENTS)
        session_id = str(uuid.uuid4())
        n_spans    = random.randint(2, 6)
        t0         = now - timedelta(seconds=random.randint(60, 7 * 24 * 3600))

        # root span
        root_id  = uuid.uuid4().hex[:16]
        root_dur = random.uniform(200, 5000)
        is_err   = random.random() < 0.10
        rows.append({
            "trace_id":       trace_id,
            "span_id":        root_id,
            "parent_span_id": None,
            "service_id":     service,
            "agent_id":       agent,
            "agent_name":     agent,
            "model_id":       None,
            "session_id":     session_id,
            "operation_name": "other",
            "span_name":      "handle_request",
            "span_kind":      "SERVER",
            "environment":    env,
            "project_id":     PROJECT_ID,
            "start_time":     _iso(t0),
            "end_time":       _iso(t0 + timedelta(milliseconds=root_dur)),
            "duration_ms":    round(root_dur, 3),
            "status_code":    "ERROR" if is_err else "OK",
            "status_message": "downstream failure" if is_err else "",
            "attributes_json": json.dumps({"http.method": "POST", "http.status_code": 500 if is_err else 200}),
        })
        cursor = t0
        for i in range(n_spans - 1):
            child_id  = uuid.uuid4().hex[:16]
            offset    = random.uniform(10, root_dur / n_spans)
            cursor    = cursor + timedelta(milliseconds=offset)
            dur       = random.uniform(30, root_dur / n_spans)
            op        = random.choice(OPERATION_NAMES)
            child_err = random.random() < 0.08
            model_id  = random.choice(MODELS) if op == "llm" else None

            attrs = {}
            if op == "llm":
                attrs = {
                    "gcp.vertex.agent.llm_request": json.dumps({
                        "model": model_id or "gemini-2.5-flash",
                        "contents": [
                            {"role": "user", "parts": [{"text": "Hello, how can I do research?"}]},
                        ]
                    }),
                    "gcp.vertex.agent.llm_response": json.dumps({
                        "content": {
                            "parts": [{"text": "I can help you search the web or analyze data."}]
                        },
                        "usage_metadata": {
                            "prompt_token_count": random.randint(100, 500),
                            "candidates_token_count": random.randint(50, 300)
                        },
                        "finish_reason": "stop"
                    }),
                    "gen_ai.request.model": model_id or "gemini-2.5-flash"
                }
            elif op == "tool":
                attrs = {
                    "gcp.vertex.agent.tool_call_args": json.dumps({
                        "query": "latest research in quantum computing"
                    }),
                    "gcp.vertex.agent.tool_response": json.dumps({
                        "response": "Found 3 papers on quantum computing from 2026."
                    })
                }

            rows.append({
                "trace_id":       trace_id,
                "span_id":        child_id,
                "parent_span_id": root_id,
                "service_id":     service,
                "agent_id":       agent,
                "agent_name":     agent,
                "model_id":       model_id,
                "session_id":     session_id,
                "operation_name": op,
                "span_name":      f"{op}_span_{i+1}",
                "span_kind":      random.choice(SPAN_KINDS),
                "environment":    env,
                "project_id":     PROJECT_ID,
                "start_time":     _iso(cursor),
                "end_time":       _iso(cursor + timedelta(milliseconds=dur)),
                "duration_ms":    round(dur, 3),
                "status_code":    "ERROR" if child_err else "OK",
                "status_message": "timeout" if child_err else "",
                "attributes_json": json.dumps(attrs),
            })
    return rows


def gen_llm_interactions(now: datetime | None = None, n: int = 60) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for _ in range(n):
        ts        = now - timedelta(seconds=random.randint(0, 7 * 24 * 3600))
        inp       = random.randint(50, 2000)
        out       = random.randint(10, 500)
        model     = random.choice(MODELS)
        provider  = random.choice(PROVIDERS)
        agent     = random.choice(AGENTS)
        latency   = round(random.uniform(500, 12000), 3)
        rows.append({
            "llm_call_id":   uuid.uuid4().hex[:16],
            "trace_id":      uuid.uuid4().hex,
            "session_id":    str(uuid.uuid4()),
            "agent_id":      agent,
            "agent_name":    agent,
            "model_name":    model,
            "provider":      provider,
            "service_id":    random.choice(SERVICES),
            "project_id":    random.choice(PROJECT_IDS),
            "environment":   random.choice(ENVIRONMENTS),
            "tokens_input":  inp,
            "tokens_output": out,
            "total_tokens":  inp + out,
            "cost":          round((inp * 0.00015 + out * 0.0006) / 1000, 6),
            "temperature":   round(random.uniform(0.0, 1.0), 2),
            "finish_reason": random.choice(FINISH_REASONS),
            "latency_ms":    latency,
            "timestamp":     _iso(ts),
        })
    return rows


def gen_llm_usage_daily(now: datetime | None = None) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for d in _days(now, 14):
        for agent in AGENTS[:3]:
            model    = random.choice(MODELS)
            provider = random.choice(PROVIDERS)
            service  = random.choice(SERVICES)
            n_calls  = random.randint(2, 30)
            inp      = random.randint(n_calls * 100, n_calls * 2000)
            out      = random.randint(n_calls * 20,  n_calls * 500)
            avg_lat  = round(random.uniform(800, 8000), 3)
            rows.append({
                "date":                _isodate(d),
                "agent_id":            agent,
                "agent_name":          agent,
                "model_name":          model,
                "provider":            provider,
                "service_id":          service,
                "project_id":          PROJECT_ID,
                "environment":         random.choice(ENVIRONMENTS),
                "total_llm_calls":     n_calls,
                "total_tokens_input":  inp,
                "total_tokens_output": out,
                "total_tokens":        inp + out,
                "total_cost":          round((inp * 0.00015 + out * 0.0006) / 1000, 6),
                "avg_latency_ms":      avg_lat,
                "p95_latency_ms":      round(avg_lat * 1.8, 3),
            })
    return rows


def gen_logs_detail(now: datetime | None = None, n: int = 150) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for _ in range(n):
        ts = now - timedelta(seconds=random.randint(0, 7 * 24 * 3600))
        rows.append({
            "log_id":      str(uuid.uuid4()),
            "trace_id":    uuid.uuid4().hex if random.random() > 0.3 else None,
            "span_id":     uuid.uuid4().hex[:16] if random.random() > 0.3 else None,
            "service_id":  random.choice(SERVICES),
            "environment": random.choice(ENVIRONMENTS),
            "project_id":  PROJECT_ID,
            "severity":    random.choice(SEVERITIES),
            "message":     random.choice(LOG_MESSAGES),
            "timestamp":   _iso(ts),
        })
    return rows


def gen_logs_daily(now: datetime | None = None) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for d in _days(now, 14):
        for service in SERVICES:
            for sev in ["INFO", "WARN", "ERROR", "DEBUG"]:
                count = random.randint(0, 300)
                if count == 0:
                    continue
                t0 = datetime(d.year, d.month, d.day, 0, random.randint(0, 59), tzinfo=timezone.utc)
                t1 = datetime(d.year, d.month, d.day, 23, random.randint(0, 59), tzinfo=timezone.utc)
                rows.append({
                    "date":             _isodate(d),
                    "service_id":       service,
                    "severity":         sev,
                    "environment":      random.choice(ENVIRONMENTS),
                    "log_count":        count,
                    "unique_traces":    random.randint(1, max(1, count // 10)),
                    "first_occurrence": _iso(t0),
                    "last_occurrence":  _iso(t1),
                })
    return rows


def gen_metrics_detail(now: datetime | None = None, n: int = 80) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for _ in range(n):
        ts          = now - timedelta(seconds=random.randint(0, 7 * 24 * 3600))
        mname, mtype = random.choice(METRIC_NAMES)
        is_hist     = mtype == "Histogram"
        rows.append({
            "metric_point_id": str(uuid.uuid4()),
            "metric_name":     mname,
            "metric_type":     mtype,
            "service_id":      random.choice(SERVICES),
            "environment":     random.choice(ENVIRONMENTS),
            "project_id":      PROJECT_ID,
            "agent_name":      random.choice(AGENTS),
            "value_int":       None if is_hist else random.randint(100, 5000),
            "value_double":    None,
            "histogram_sum":   round(random.uniform(0.5, 30000), 3) if is_hist else None,
            "histogram_count": random.randint(1, 200) if is_hist else None,
            "histogram_min":   round(random.uniform(0.1, 100), 3) if is_hist else None,
            "histogram_max":   round(random.uniform(100, 30000), 3) if is_hist else None,
            "timestamp":       _iso(ts),
        })
    return rows


def gen_metrics_daily(now: datetime | None = None) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for d in _days(now, 14):
        for service in SERVICES:
            for mname, mtype in METRIC_NAMES:
                cnt = random.randint(10, 500)
                is_hist = mtype == "Histogram"
                avg_val = round(random.uniform(100, 15000), 3) if is_hist else None
                rows.append({
                    "date":             _isodate(d),
                    "service_id":       service,
                    "metric_name":      mname,
                    "metric_type":      mtype,
                    "environment":      random.choice(ENVIRONMENTS),
                    "data_point_count": cnt,
                    "avg_value":        avg_val,
                    "min_value":        round(avg_val * 0.1, 3) if avg_val else None,
                    "max_value":        round(avg_val * 3.0, 3) if avg_val else None,
                    "sum_value":        round(avg_val * cnt, 3) if avg_val else round(random.uniform(1000, 100000), 3),
                })
    return rows


def gen_errors_detail(now: datetime | None = None, n: int = 40) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for _ in range(n):
        ts  = now - timedelta(seconds=random.randint(0, 7 * 24 * 3600))
        src = random.choice(["log", "trace"])
        rows.append({
            "error_id":      str(uuid.uuid4()),
            "trace_id":      uuid.uuid4().hex if src == "trace" else None,
            "span_id":       uuid.uuid4().hex[:16] if src == "trace" else None,
            "session_id":    str(uuid.uuid4()) if random.random() > 0.5 else None,
            "agent_id":      random.choice(AGENTS) if random.random() > 0.5 else None,
            "agent_name":    random.choice(AGENTS) if random.random() > 0.5 else None,
            "service_id":    random.choice(SERVICES),
            "environment":   random.choice(ENVIRONMENTS),
            "error_type":    random.choice(["ERROR", "FATAL", "timeout", "not_found"]),
            "severity":      "ERROR",
            "status_code":   "ERROR" if src == "trace" else None,
            "error_message": random.choice(ERROR_MESSAGES),
            "source":        src,
            "timestamp":     _iso(ts),
        })
    return rows


def gen_error_summary_daily(now: datetime | None = None) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for d in _days(now, 14):
        for service in SERVICES:
            cnt = random.randint(0, 100)
            if cnt == 0:
                continue
            t0 = datetime(d.year, d.month, d.day, 0, random.randint(0, 30), tzinfo=timezone.utc)
            t1 = datetime(d.year, d.month, d.day, 23, random.randint(30, 59), tzinfo=timezone.utc)
            rows.append({
                "date":              _isodate(d),
                "service_id":        service,
                "agent_id":          None,
                "agent_name":        None,
                "error_type":        None,
                "severity":          "ERROR",
                "environment":       random.choice(ENVIRONMENTS),
                "error_count":       cnt,
                "affected_traces":   random.randint(0, cnt),
                "affected_sessions": random.randint(0, max(1, cnt // 5)),
                "first_occurrence":  _iso(t0),
                "last_occurrence":   _iso(t1),
                "sample_message":    random.choice(ERROR_MESSAGES),
            })
    return rows


def gen_tool_executions(now: datetime | None = None, n: int = 50) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for _ in range(n):
        ts    = now - timedelta(seconds=random.randint(0, 7 * 24 * 3600))
        tool  = random.choice(TOOL_NAMES)
        ttype = random.choice(TOOL_TYPES)
        agent = random.choice(AGENTS)
        rows.append({
            "execution_id":  uuid.uuid4().hex[:16],
            "trace_id":      uuid.uuid4().hex,
            "session_id":    str(uuid.uuid4()) if random.random() > 0.4 else None,
            "agent_id":      agent,
            "agent_name":    agent,
            "tool_name":     tool,
            "tool_type":     ttype,
            "service_id":    random.choice(SERVICES),
            "environment":   random.choice(ENVIRONMENTS),
            "tool_input":    json.dumps({"query": "sample input"}),
            "tool_output":   json.dumps({"result": "sample output"}) if random.random() > 0.3 else None,
            "status":        random.choice(["OK", "UNSET", "ERROR"]),
            "error_message": None,
            "latency_ms":    round(random.uniform(0.3, 5000), 3),
            "timestamp":     _iso(ts),
        })
    return rows


def gen_tool_usage_daily(now: datetime | None = None) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for d in _days(now, 14):
        for tool, ttype in zip(TOOL_NAMES, TOOL_TYPES):
            total  = random.randint(1, 20)
            succ   = random.randint(0, total)
            fail   = total - succ
            avg_lat = round(random.uniform(0.5, 5000), 3)
            rows.append({
                "date":             _isodate(d),
                "tool_name":        tool,
                "tool_type":        ttype,
                "agent_id":         None,
                "agent_name":       None,
                "environment":      random.choice(ENVIRONMENTS),
                "total_executions": total,
                "success_count":    succ,
                "failure_count":    fail,
                "success_rate":     round(succ / total, 4) if total else 0.0,
                "avg_latency_ms":   avg_lat,
                "p95_latency_ms":   round(avg_lat * 1.9, 3),
            })
    return rows


def gen_agent_traces_detail(now: datetime | None = None, n: int = 80) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for step_num in range(1, n + 1):
        ts    = now - timedelta(seconds=random.randint(0, 7 * 24 * 3600))
        agent = random.choice(AGENTS)
        stype = random.choice(STEP_TYPES)
        rows.append({
            "agent_trace_id": uuid.uuid4().hex[:16],
            "trace_id":       uuid.uuid4().hex,
            "session_id":     str(uuid.uuid4()) if random.random() > 0.4 else None,
            "agent_id":       agent,
            "agent_name":     agent,
            "tool_id":        uuid.uuid4().hex[:16] if stype == "tool" else None,
            "llm_call_id":    uuid.uuid4().hex[:16] if stype == "llm"  else None,
            "service_id":     random.choice(SERVICES),
            "environment":    random.choice(ENVIRONMENTS),
            "step_number":    step_num,
            "step_type":      stype,
            "latency_ms":     round(random.uniform(100, 15000), 3),
            "timestamp":      _iso(ts),
        })
    return rows


def gen_agent_traces_steps_daily(now: datetime | None = None) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for d in _days(now, 14):
        for agent in AGENTS[:3]:
            for stype in STEP_TYPES:
                total = random.randint(1, 20)
                rows.append({
                    "date":                 _isodate(d),
                    "agent_id":             agent,
                    "agent_name":           agent,
                    "step_type":            stype,
                    "environment":          random.choice(ENVIRONMENTS),
                    "total_steps":          total,
                    "unique_sessions":      random.randint(0, max(1, total // 3)),
                    "avg_latency_ms":       round(random.uniform(500, 15000), 3),
                    "max_steps_in_session": random.randint(total, total + 50),
                })
    return rows


def gen_service_health_daily(now: datetime | None = None) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for d in _days(now, 14):
        for service in SERVICES:
            total_spans = random.randint(10, 200)
            total_logs  = random.randint(20, 500)
            err_logs    = random.randint(0, max(1, total_logs // 10))
            avg_dur     = round(random.uniform(100, 5000), 3)
            rows.append({
                "date":                 _isodate(d),
                "service_id":           service,
                "environment":          random.choice(ENVIRONMENTS),
                "total_spans":          total_spans,
                "total_logs":           total_logs,
                "error_log_count":      err_logs,
                "avg_span_duration_ms": avg_dur,
                "p95_span_duration_ms": round(avg_dur * 2.5, 3),
                "error_rate":           round(err_logs / max(total_spans, 1), 4),
            })
    return rows


def gen_session_summary_daily(now: datetime | None = None) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for d in _days(now, 14):
        for agent in AGENTS[:3]:
            sess = random.randint(1, 15)
            rows.append({
                "date":                     _isodate(d),
                "agent_id":                 agent,
                "agent_name":               agent,
                "total_sessions":           sess,
                "unique_users":             0,
                "avg_spans_per_session":    round(random.uniform(1, 5), 2),
                "avg_session_duration_sec": round(random.uniform(1, 120), 2),
            })
    return rows


def gen_traces_daily(now: datetime | None = None) -> list[dict]:
    now  = now or datetime.now(tz=timezone.utc)
    rows = []
    for d in _days(now, 14):
        for service in SERVICES:
            for op in OPERATION_NAMES:
                total = random.randint(2, 50)
                errs  = random.randint(0, max(1, total // 10))
                avg   = round(random.uniform(100, 8000), 3)
                rows.append({
                    "date":            _isodate(d),
                    "service_id":      service,
                    "operation_name":  op,
                    "environment":     random.choice(ENVIRONMENTS),
                    "total_spans":     total,
                    "avg_duration_ms": avg,
                    "p50_duration_ms": round(avg * 0.8, 3),
                    "p95_duration_ms": round(avg * 2.0, 3),
                    "p99_duration_ms": round(avg * 2.8, 3),
                    "error_count":     errs,
                    "success_count":   total - errs,
                })
    return rows


def gen_all(now: datetime | None = None) -> dict[str, list[dict]]:
    """Return seed rows for every wide table, keyed by table name."""
    now = now or datetime.now(tz=timezone.utc)
    return {
        "wide_agent_trace_steps_daily": gen_agent_traces_steps_daily(now),
        "wide_agent_traces_detail":      gen_agent_traces_detail(now),
        "wide_error_summary_daily":      gen_error_summary_daily(now),
        "wide_errors_detail":            gen_errors_detail(now),
        "wide_llm_interactions_detail":  gen_llm_interactions(now),
        "wide_llm_usage_daily":          gen_llm_usage_daily(now),
        "wide_logs_daily":               gen_logs_daily(now),
        "wide_logs_detail":              gen_logs_detail(now),
        "wide_metrics_daily":            gen_metrics_daily(now),
        "wide_metrics_detail":           gen_metrics_detail(now),
        "wide_service_health_daily":     gen_service_health_daily(now),
        "wide_session_summary_daily":    gen_session_summary_daily(now),
        "wide_sessions_detail":          gen_sessions(now),
        "wide_spans_detail":             gen_spans(now),
        "wide_tool_executions_detail":   gen_tool_executions(now),
        "wide_tool_usage_daily":         gen_tool_usage_daily(now),
        "wide_traces_daily":             gen_traces_daily(now),
    }


# ── Pricing (unchanged) ───────────────────────────────────────────────────────

def gen_pricing() -> list[dict]:
    """Gemini model pricing (USD per 1M tokens)."""
    prices = [
        ("gemini-2.5-pro",          1.25,  10.00),
        ("gemini-2.5-flash-lite",   0.10,   0.40),
        ("gemini-2.5-flash",        0.15,   0.60),
        ("gemini-2.0-flash-lite",   0.075,  0.30),
        ("gemini-2.0-flash",        0.10,   0.40),
        ("gemini-1.5-flash-8b",     0.0375, 0.15),
        ("gemini-1.5-flash",        0.075,  0.30),
        ("gemini-1.5-pro",          1.25,   5.00),
        ("gemini-1.0-pro",          0.50,   1.50),
        ("gemini-pro",              0.50,   1.50),
    ]
    return [
        {
            "model_prefix": prefix,
            "input_cost_per_1m_tokens": inp,
            "output_cost_per_1m_tokens": outp,
        }
        for prefix, inp, outp in prices
    ]
