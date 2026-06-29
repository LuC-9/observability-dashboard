"""
Startup bootstrap router.

Called from main.py on app startup. Routes to whichever backend is active
(BigQuery or local SQLite) and runs its bootstrap(), wrapping in try/except
so a bootstrap failure doesn't prevent the app from starting.
"""
import traceback

import bq_client


def safe_bootstrap() -> None:
    try:
        bq_client.bootstrap()
    except Exception as e:
        print(f"[bootstrap] ERROR: {e}")
        traceback.print_exc()
