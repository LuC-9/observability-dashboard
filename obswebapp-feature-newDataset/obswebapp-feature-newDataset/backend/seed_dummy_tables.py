"""
Creates the 6 new dummy BigQuery tables and seeds them with realistic fake data.
Run once: python backend/seed_dummy_tables.py

Tables created (all in $GCP_PROJECT.$BQ_DATASET):
  dummy_agent_sessions, dummy_agent_traces, dummy_cost_tracking,
  dummy_errors, dummy_llm_interactions, dummy_tool_executions
"""
import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

import seed_data

load_dotenv()

PROJECT    = os.getenv("GCP_PROJECT", "oa-apmena-observability-dv")
BQ_DATASET = os.getenv("BQ_DATASET", "cds_otel")

print(f"[seed] project={PROJECT!r}  dataset={BQ_DATASET!r}")
client = bigquery.Client(project=PROJECT)

# ── Schema definitions ────────────────────────────────────────────────────────

SCHEMAS = {
    "dummy_agent_sessions": {
        "partition": "start_time",
        "schema": [
            bigquery.SchemaField("session_id",   "STRING"),
            bigquery.SchemaField("user_id",      "STRING"),
            bigquery.SchemaField("agent_id",     "STRING"),
            bigquery.SchemaField("start_time",   "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("end_time",     "TIMESTAMP"),
            bigquery.SchemaField("total_turns",  "INT64"),
            bigquery.SchemaField("status",       "STRING"),
            bigquery.SchemaField("input_source", "STRING"),
            bigquery.SchemaField("region",       "STRING"),
            bigquery.SchemaField("metadata",     "STRING"),  # JSON stored as string
        ],
    },
    "dummy_agent_traces": {
        "partition": "timestamp",
        "schema": [
            bigquery.SchemaField("agent_trace_id", "STRING"),
            bigquery.SchemaField("session_id",     "STRING"),
            bigquery.SchemaField("trace_id",       "STRING"),
            bigquery.SchemaField("step_number",    "INT64"),
            bigquery.SchemaField("step_type",      "STRING"),
            bigquery.SchemaField("decision",       "STRING"),
            bigquery.SchemaField("reasoning",      "STRING"),
            bigquery.SchemaField("tool_name",      "STRING"),
            bigquery.SchemaField("llm_call_id",    "STRING"),
            bigquery.SchemaField("timestamp",      "TIMESTAMP", mode="REQUIRED"),
        ],
    },
    "dummy_cost_tracking": {
        "partition": "timestamp",
        "schema": [
            bigquery.SchemaField("record_id",     "STRING"),
            bigquery.SchemaField("session_id",    "STRING"),
            bigquery.SchemaField("agent_id",      "STRING"),
            bigquery.SchemaField("model_name",    "STRING"),
            bigquery.SchemaField("tokens_input",  "INT64"),
            bigquery.SchemaField("tokens_output", "INT64"),
            bigquery.SchemaField("cost",          "FLOAT64"),
            bigquery.SchemaField("currency",      "STRING"),
            bigquery.SchemaField("timestamp",     "TIMESTAMP", mode="REQUIRED"),
        ],
    },
    "dummy_errors": {
        "partition": "timestamp",
        "schema": [
            bigquery.SchemaField("error_id",      "STRING"),
            bigquery.SchemaField("session_id",    "STRING"),
            bigquery.SchemaField("trace_id",      "STRING"),
            bigquery.SchemaField("component",     "STRING"),
            bigquery.SchemaField("error_type",    "STRING"),
            bigquery.SchemaField("error_message", "STRING"),
            bigquery.SchemaField("severity",      "STRING"),
            bigquery.SchemaField("timestamp",     "TIMESTAMP", mode="REQUIRED"),
        ],
    },
    "dummy_llm_interactions": {
        "partition": "timestamp",
        "schema": [
            bigquery.SchemaField("llm_call_id",    "STRING"),
            bigquery.SchemaField("session_id",     "STRING"),
            bigquery.SchemaField("agent_trace_id", "STRING"),
            bigquery.SchemaField("model_name",     "STRING"),
            bigquery.SchemaField("provider",       "STRING"),
            bigquery.SchemaField("prompt",         "STRING"),
            bigquery.SchemaField("response",       "STRING"),
            bigquery.SchemaField("tokens_input",   "INT64"),
            bigquery.SchemaField("tokens_output",  "INT64"),
            bigquery.SchemaField("total_tokens",   "INT64"),
            bigquery.SchemaField("latency_ms",     "FLOAT64"),
            bigquery.SchemaField("cost",           "FLOAT64"),
            bigquery.SchemaField("temperature",    "FLOAT64"),
            bigquery.SchemaField("status",         "STRING"),
            bigquery.SchemaField("timestamp",      "TIMESTAMP", mode="REQUIRED"),
        ],
    },
    "dummy_tool_executions": {
        "partition": "timestamp",
        "schema": [
            bigquery.SchemaField("execution_id",   "STRING"),
            bigquery.SchemaField("session_id",     "STRING"),
            bigquery.SchemaField("agent_trace_id", "STRING"),
            bigquery.SchemaField("tool_name",      "STRING"),
            bigquery.SchemaField("tool_type",      "STRING"),
            bigquery.SchemaField("input_payload",  "STRING"),  # JSON stored as string
            bigquery.SchemaField("output_payload", "STRING"),  # JSON stored as string
            bigquery.SchemaField("status",         "STRING"),
            bigquery.SchemaField("error_message",  "STRING"),
            bigquery.SchemaField("latency_ms",     "FLOAT64"),
            bigquery.SchemaField("timestamp",      "TIMESTAMP", mode="REQUIRED"),
        ],
    },
    "pricing": {
        "partition": None,
        "schema": [
            bigquery.SchemaField("model_prefix",              "STRING", mode="REQUIRED"),
            bigquery.SchemaField("input_cost_per_1m_tokens",  "FLOAT64", mode="REQUIRED"),
            bigquery.SchemaField("output_cost_per_1m_tokens", "FLOAT64", mode="REQUIRED"),
        ],
    },
}

# ── Table creation ────────────────────────────────────────────────────────────

def create_tables():
    for tname, spec in SCHEMAS.items():
        table_ref = f"{PROJECT}.{BQ_DATASET}.{tname}"
        try:
            client.get_table(table_ref)
            print(f"[seed] table already exists: {tname}")
        except NotFound:
            print(f"[seed] creating table: {tname}")
            tbl = bigquery.Table(table_ref, schema=spec["schema"])
            if spec["partition"]:
                tbl.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field=spec["partition"],
                    require_partition_filter=True,
                )
            client.create_table(tbl)
            print(f"[seed] created: {tname}")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _uid():
    return str(uuid.uuid4())

def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

def _insert(tname: str, rows: list[dict]):
    table_ref = f"{PROJECT}.{BQ_DATASET}.{tname}"
    CHUNK = 200
    total = 0
    for i in range(0, len(rows), CHUNK):
        batch = rows[i:i + CHUNK]
        errors = client.insert_rows_json(table_ref, batch)
        if errors:
            print(f"[seed] insert errors for {tname}: {errors[:2]}")
            return
        total += len(batch)
    print(f"[seed] inserted {total} rows into {tname}")

# ── Fake data constants ───────────────────────────────────────────────────────

AGENTS       = [f"agent-{i:03d}" for i in range(1, 21)]
USERS        = [f"user-{i:03d}"  for i in range(1, 51)]
REGIONS      = ["us-central1", "us-east1", "eu-west1", "asia-southeast1", "me-central1"]
INPUT_SRC    = ["web", "api", "slack", "cli"]
SES_STATUS   = ["completed", "completed", "completed", "failed", "active", "expired"]
MODELS       = ["gemini-2.0-pro", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
PROVIDERS    = {"gemini-2.0-pro": "google", "gemini-2.0-flash": "google",
                "gemini-1.5-pro": "google", "gemini-1.5-flash": "google"}
COST_PER_TOK = {"gemini-2.0-pro": 0.000003, "gemini-2.0-flash": 0.0000005,
                "gemini-1.5-pro": 0.0000025, "gemini-1.5-flash": 0.00000035}
STEP_TYPES   = ["reasoning", "tool_call", "llm_call", "decision"]
TOOL_NAMES   = ["search_web", "query_database", "send_email", "read_file",
                "call_api", "write_file", "summarize_text", "translate_text"]
TOOL_TYPES   = {"search_web": "search", "query_database": "database",
                "send_email": "notification", "read_file": "file",
                "call_api": "api", "write_file": "file",
                "summarize_text": "computation", "translate_text": "computation"}
TOOL_STATUS  = ["success", "success", "success", "failure", "timeout"]
COMPONENTS   = ["api-gateway", "llm-service", "tool-executor", "session-manager", "cost-tracker"]
ERR_TYPES    = ["TimeoutError", "ValidationError", "AuthError", "RateLimitError", "NetworkError"]
ERR_SEVERITY = ["ERROR", "CRITICAL", "WARNING", "ERROR", "ERROR"]

SAMPLE_PROMPTS = [
    "Summarize the quarterly report and highlight key risks.",
    "Search for recent news about AI regulation in the EU.",
    "What is the current status of the deployment pipeline?",
    "Generate a SQL query to find all users who signed up in the last 7 days.",
    "Translate the following document to Arabic.",
    "Analyze the error logs from the last hour and identify root causes.",
    "Draft a response to the customer complaint about slow API latency.",
]
SAMPLE_RESPONSES = [
    "Based on the quarterly report, the key risks include supply chain disruption and regulatory uncertainty.",
    "Recent developments in EU AI regulation include the AI Act coming into effect with phased compliance deadlines.",
    "The deployment pipeline is currently in the build phase. 3 of 7 stages completed successfully.",
    "SELECT user_id, email, created_at FROM users WHERE created_at >= NOW() - INTERVAL 7 DAY;",
    "Translation complete. The document has been converted to Arabic with 98.7% confidence.",
    "Root cause analysis complete. 3 recurring errors identified: connection timeout, memory overflow, and auth token expiry.",
    "Draft response: We sincerely apologize for the latency issues. Our team has identified the bottleneck and deployed a fix.",
]
DECISIONS = ["proceed_with_tool", "ask_clarification", "complete_task", "escalate", "retry"]
REASONINGS = [
    "The query requires database access to retrieve current data.",
    "User intent is clear enough to proceed without clarification.",
    "All required information has been gathered; generating final response.",
    "Task complexity exceeds current context; escalating to human.",
    "Previous attempt failed with transient error; retrying with backoff.",
]

# ── Data generation ───────────────────────────────────────────────────────────

def generate_data():
    now = datetime.now(tz=timezone.utc)
    rng = random.Random(42)

    sessions       = []
    agent_traces   = []
    cost_records   = []
    errors         = []
    llm_ints       = []
    tool_execs     = []

    # Spread sessions over last 30 days; ~20% in last 24h for filter coverage
    for _ in range(200):
        hours_ago = rng.choices(
            [rng.uniform(0, 24), rng.uniform(24, 720)],
            weights=[20, 80],
        )[0]
        session_start = now - timedelta(hours=hours_ago)
        duration_min  = rng.uniform(2, 90)
        session_end   = session_start + timedelta(minutes=duration_min)
        turns         = rng.randint(3, 20)
        agent_id      = rng.choice(AGENTS)
        user_id       = rng.choice(USERS)
        status        = rng.choice(SES_STATUS)
        region        = rng.choice(REGIONS)
        session_id    = _uid()

        sessions.append({
            "session_id":   session_id,
            "user_id":      user_id,
            "agent_id":     agent_id,
            "start_time":   _ts(session_start),
            "end_time":     _ts(session_end),
            "total_turns":  turns, 
            "status":       status,
            "input_source": rng.choice(INPUT_SRC),
            "region":       region,
            "metadata":     json.dumps({"source_app": "dashboard", "version": "2.1"}),
        })

        # Generate 3–7 agent traces per session
        n_steps = rng.randint(3, 7)
        step_ts = session_start
        for step in range(1, n_steps + 1):
            step_ts += timedelta(seconds=rng.uniform(5, 60))
            at_id     = _uid()
            trace_id  = _uid()
            step_type = rng.choice(STEP_TYPES)
            tool      = rng.choice(TOOL_NAMES) if step_type == "tool_call" else None
            llm_id    = _uid() if step_type in ("llm_call", "reasoning") else None

            agent_traces.append({
                "agent_trace_id": at_id,
                "session_id":     session_id,
                "trace_id":       trace_id,
                "step_number":    step,
                "step_type":      step_type,
                "decision":       rng.choice(DECISIONS),
                "reasoning":      rng.choice(REASONINGS),
                "tool_name":      tool,
                "llm_call_id":    llm_id,
                "timestamp":      _ts(step_ts),
            })

            # LLM interaction for llm_call or reasoning steps
            if llm_id:
                model      = rng.choice(MODELS)
                tok_in     = rng.randint(100, 4000)
                tok_out    = rng.randint(50, 1500)
                latency    = rng.uniform(200, 8000)
                cost_val   = (tok_in + tok_out) * COST_PER_TOK[model]
                llm_status = rng.choices(["success", "error"], weights=[92, 8])[0]

                llm_ints.append({
                    "llm_call_id":    llm_id,
                    "session_id":     session_id,
                    "agent_trace_id": at_id,
                    "model_name":     model,
                    "provider":       PROVIDERS[model],
                    "prompt":         rng.choice(SAMPLE_PROMPTS),
                    "response":       rng.choice(SAMPLE_RESPONSES),
                    "tokens_input":   tok_in,
                    "tokens_output":  tok_out,
                    "total_tokens":   tok_in + tok_out,
                    "latency_ms":     round(latency, 2),
                    "cost":           round(cost_val, 8),
                    "temperature":    round(rng.uniform(0.0, 1.0), 2),
                    "status":         llm_status,
                    "timestamp":      _ts(step_ts),
                })

                cost_records.append({
                    "record_id":     _uid(),
                    "session_id":    session_id,
                    "agent_id":      agent_id,
                    "model_name":    model,
                    "tokens_input":  tok_in,
                    "tokens_output": tok_out,
                    "cost":          round(cost_val, 8),
                    "currency":      "USD",
                    "timestamp":     _ts(step_ts),
                })

            # Tool execution for tool_call steps
            if tool:
                exec_status = rng.choice(TOOL_STATUS)
                exec_latency = rng.uniform(50, 3000)
                tool_execs.append({
                    "execution_id":   _uid(),
                    "session_id":     session_id,
                    "agent_trace_id": at_id,
                    "tool_name":      tool,
                    "tool_type":      TOOL_TYPES[tool],
                    "input_payload":  json.dumps({"query": "example input", "params": {"limit": 10}}),
                    "output_payload": json.dumps({"result": "example output", "count": rng.randint(0, 100)}),
                    "status":         exec_status,
                    "error_message":  "Connection timed out" if exec_status == "timeout" else None,
                    "latency_ms":     round(exec_latency, 2),
                    "timestamp":      _ts(step_ts),
                })

        # ~20% of sessions generate errors
        if rng.random() < 0.20:
            for _ in range(rng.randint(1, 3)):
                err_ts = session_start + timedelta(seconds=rng.uniform(0, duration_min * 60))
                etype  = rng.choice(ERR_TYPES)
                errors.append({
                    "error_id":      _uid(),
                    "session_id":    session_id,
                    "trace_id":      _uid(),
                    "component":     rng.choice(COMPONENTS),
                    "error_type":    etype,
                    "error_message": f"{etype}: {rng.choice(['connection refused', 'request timed out after 30s', 'invalid token', 'rate limit exceeded', 'upstream unavailable'])}",
                    "severity":      rng.choice(ERR_SEVERITY),
                    "timestamp":     _ts(err_ts),
                })

    return sessions, agent_traces, llm_ints, cost_records, tool_execs, errors


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("[seed] creating tables…")
    create_tables()

    print("[seed] generating data…")
    sessions, agent_traces, llm_ints, cost_records, tool_execs, errors = generate_data()
    print(f"[seed] sessions={len(sessions)}, agent_traces={len(agent_traces)}, "
          f"llm_interactions={len(llm_ints)}, cost_records={len(cost_records)}, "
          f"tool_executions={len(tool_execs)}, errors={len(errors)}")

    _insert("dummy_agent_sessions",   sessions)
    _insert("dummy_agent_traces",     agent_traces)
    _insert("dummy_llm_interactions", llm_ints)
    _insert("dummy_cost_tracking",    cost_records)
    _insert("dummy_tool_executions",  tool_execs)
    _insert("dummy_errors",           errors)

    # Seed pricing table
    print("[seed] seeding pricing table…")
    pricing_rows = seed_data.gen_pricing()
    _insert("pricing", pricing_rows)

    print("[seed] done.")
