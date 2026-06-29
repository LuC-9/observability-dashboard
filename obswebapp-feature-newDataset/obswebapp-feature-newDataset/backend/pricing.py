# Fetch Google Gemini pricing from BigQuery pricing table.
# Source: https://ai.google.dev/pricing
# Data is cached in memory after first load.

import os
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

PROJECT    = os.getenv("GCP_PROJECT", "oa-apmena-observability-dv")
BQ_DATASET = os.getenv("BQ_DATASET", "cds_otel")

# Module-level cache for pricing data
_PRICES = None
_client = None


def _get_bq_client():
    """Get or create BigQuery client."""
    global _client
    if _client is None:
        _client = bigquery.Client(project=PROJECT)
    return _client


def _load_prices():
    """Fetch pricing data from BigQuery and cache it."""
    global _PRICES
    if _PRICES is None:
        try:
            client = _get_bq_client()
            query = f"""
            SELECT model_prefix, input_cost_per_1m_tokens, output_cost_per_1m_tokens
            FROM `{PROJECT}.{BQ_DATASET}.pricing`
            ORDER BY LENGTH(model_prefix) DESC
            """
            df = client.query(query).to_dataframe(create_bqstorage_client=False)
            _PRICES = [
                (row['model_prefix'], row['input_cost_per_1m_tokens'], row['output_cost_per_1m_tokens'])
                for _, row in df.iterrows()
            ]
            print(f"[pricing] Loaded {len(_PRICES)} pricing rows from BigQuery")
        except Exception as e:
            print(f"[pricing] ERROR loading from BigQuery: {e}")
            # Fallback to empty list - pricing will return 0.0
            _PRICES = []
    return _PRICES


def compute_cost(model: str | None, in_tokens: float, out_tokens: float) -> float:
    """Return USD cost computed from BigQuery pricing table."""
    if not model:
        return 0.0
    prices = _load_prices()
    m = str(model).lower()
    # Strip provider prefix (e.g., "openai/gpt-4o" -> "gpt-4o", "anthropic/claude" -> "claude")
    if "/" in m:
        m = m.split("/", 1)[1]
    for prefix, inp, outp in prices:
        if m.startswith(prefix):
            return (float(in_tokens or 0) * inp + float(out_tokens or 0) * outp) / 1_000_000
    return 0.0


def effective_cost(
    stored: float | None,
    model: str | None,
    in_tokens: float,
    out_tokens: float,
) -> float:
    """Return stored cost when > 0, otherwise compute from pricing table."""
    c = float(stored or 0)
    return c if c > 0 else compute_cost(model, in_tokens, out_tokens)


def sql_cost_expr(input_col: str, output_col: str, model_col: str) -> str:
    """Generate a BigQuery SQL CASE expression that maps model name to cost.

    Handles both plain model names (e.g., 'gpt-4o') and provider-prefixed names (e.g., 'openai/gpt-4o').
    Returns an expression like:
        CASE
          WHEN STARTS_WITH(LOWER(REGEXP_REPLACE(model_col, r'^[^/]+/', '')), 'gemini-2.5-pro') THEN ...
          ...
          ELSE 0.0
        END
    """
    prices = _load_prices()
    # Strip provider prefix from model name: "openai/gpt-4o" -> "gpt-4o"
    model_col_stripped = f"REGEXP_REPLACE(LOWER({model_col}), r'^[^/]+/', '')"
    lines = ["CASE"]
    for prefix, inp, outp in prices:
        lines.append(
            f"  WHEN STARTS_WITH({model_col_stripped}, '{prefix}') THEN"
            f" (COALESCE({input_col}, 0) * {inp} + COALESCE({output_col}, 0) * {outp}) / 1000000.0"
        )
    lines.append("  ELSE 0.0")
    lines.append("END")
    return "\n".join(lines)
