import os

# --- GCP / BigQuery ---
PROJECT      = os.environ.get("CENTRAL_PROJECT", "oa-apmena-observability-dv")
GOLD_DATASET = os.environ.get("GOLD_DATASET", "gold")          # persisted tables: spans, logs, metrics
SPANS_TABLE  = f"{PROJECT}.{GOLD_DATASET}.spans"
LOGS_TABLE   = f"{PROJECT}.{GOLD_DATASET}.logs"
METRICS_TABLE= f"{PROJECT}.{GOLD_DATASET}.metrics"
BRONZE_METRIC= f"{PROJECT}.bronze_metric.timeseries"   # beta: metrics tab reads bronze until gold metrics exists

# --- pipeline trigger (force-refresh "run pipeline now") ---
WORKFLOW_LOCATION = os.environ.get("WORKFLOW_LOCATION", "us-central1")
WORKFLOW_NAME     = os.environ.get("WORKFLOW_NAME", "obs-pipeline")

# --- auth (demo) ---
ADMIN_USER = os.environ.get("ADMIN_USER", "admin1")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "pwd1")
# Google SSO (app-level). Empty client id = SSO button hidden.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
ALLOWED_DOMAIN   = os.environ.get("ALLOWED_DOMAIN", "loreal.com")
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-dev-secret")
JWT_TTL_HOURS = int(os.environ.get("JWT_TTL_HOURS", "12"))

# --- CORS (frontend dev origin) ---
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

# preset time ranges -> minutes ("custom" handled via explicit start/end)
TIME_PRESETS = {
    "5m": 5, "10m": 10, "30m": 30,
    "1h": 60, "6h": 360, "12h": 720, "1d": 1440,
}
