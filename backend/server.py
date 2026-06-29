"""
Entrypoint dispatcher.

  APP_ENV=cloud  → BigQuery against <GCP_PROJECT>.<BQ_DATASET>.wide_*
  APP_ENV=local  (default) → local SQLite seeded with the same wide_* schema

Both apps serve the dashboard React frontend (ECharts) from ./static and expose
the same /api/* contract. Flip a single .env line to toggle.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level above backend/) — falls back to a
# local backend/.env if present, then to process env.
_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
if _ROOT_ENV.is_file():
    load_dotenv(_ROOT_ENV)
else:
    load_dotenv()

APP_ENV = os.environ.get("APP_ENV", "local").strip().lower()
print(f"[server] APP_ENV={APP_ENV!r}")

if APP_ENV == "cloud":
    from cloud_app import app  # noqa: F401
else:
    from local_app import app  # noqa: F401
