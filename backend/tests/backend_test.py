"""End-to-end backend API tests for the observability dashboard."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://f91ea9ce-4f4b-4aed-87d3-4af955922294.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/login", json={"username": "admin1", "password": "pwd1"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Health / Auth / Config ────────────────────────────────────────
def test_health_public():
    r = requests.get(f"{API}/health", timeout=15)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_login_invalid():
    r = requests.post(f"{API}/login", json={"username": "admin1", "password": "wrong"}, timeout=15)
    assert r.status_code == 401


def test_login_success(token):
    assert isinstance(token, str) and len(token) > 20


def test_config():
    r = requests.get(f"{API}/config", timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert "google_client_id" in j and "allowed_domain" in j


def test_iap_unauth():
    r = requests.get(f"{API}/auth/iap", timeout=15)
    assert r.status_code == 401


def test_protected_without_token():
    for path in ["/filters/projects", "/overview", "/traces", "/logs"]:
        r = requests.get(f"{API}{path}", timeout=15)
        assert r.status_code == 401, f"{path} returned {r.status_code}"


def test_protected_with_invalid_token():
    r = requests.get(f"{API}/filters/projects", headers={"Authorization": "Bearer abc.def.ghi"}, timeout=15)
    assert r.status_code == 401


# ── Filters ───────────────────────────────────────────────────────
def test_filters(auth):
    for ep in ["projects", "platforms", "services"]:
        r = requests.get(f"{API}/filters/{ep}", headers=auth, timeout=15)
        assert r.status_code == 200, f"{ep} -> {r.text}"
        data = r.json()
        assert isinstance(data, list) and len(data) > 0, f"{ep} empty: {data}"


# ── Overview ──────────────────────────────────────────────────────
def test_overview(auth):
    r = requests.get(f"{API}/overview?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert "range" in j and "kpis" in j
    k = j["kpis"]
    for f in ["traces", "spans", "cost_usd", "input_tokens", "output_tokens", "p50_ms", "p95_ms"]:
        assert f in k, f"missing kpi {f}"
    assert k["traces"] > 0 and k["spans"] > 0
    assert k["cost_usd"] > 0


def test_overview_timeseries(auth):
    r = requests.get(f"{API}/overview/timeseries?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0
    keys = {"bucket", "traces", "errors", "cost_usd", "input_tokens", "output_tokens"}
    assert keys.issubset(set(rows[0].keys()))


def test_latency_timeseries(auth):
    r = requests.get(f"{API}/latency/timeseries?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0
    assert {"bucket", "p50_ms", "p95_ms"}.issubset(set(rows[0].keys()))


# ── Traces ────────────────────────────────────────────────────────
def test_traces_list_and_detail(auth):
    r = requests.get(f"{API}/traces?time_range=30d&page_size=10", headers=auth, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert "rows" in j and "total" in j
    assert j["total"] > 0
    row = j["rows"][0]
    for f in ["trace_id", "service_name", "duration_ms", "status_code", "conversation_id", "spans", "cost_usd"]:
        assert f in row, f"trace row missing {f}: keys={list(row.keys())}"
    # detail
    tid = row["trace_id"]
    r2 = requests.get(f"{API}/traces/{tid}", headers=auth, timeout=30)
    assert r2.status_code == 200
    spans = r2.json()
    assert isinstance(spans, list) and len(spans) > 0
    for sf in ["span_id", "parent_span_id", "span_name", "duration_ms", "status_code"]:
        assert sf in spans[0]


# ── Logs ──────────────────────────────────────────────────────────
def test_logs(auth):
    r = requests.get(f"{API}/logs?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["total"] > 0
    row = j["rows"][0]
    for f in ["timestamp", "service_name", "severity", "message"]:
        assert f in row


def test_logs_severity_filter(auth):
    r = requests.get(f"{API}/logs?time_range=30d&severity=ERROR", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()["rows"]
    if rows:
        assert all(row["severity"] == "ERROR" for row in rows)


# ── Metrics ───────────────────────────────────────────────────────
def test_metrics_catalog(auth):
    r = requests.get(f"{API}/metrics/catalog?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    j = r.json()
    for f in ["categories", "metric_types", "services"]:
        assert f in j and isinstance(j[f], list)


def test_metrics_summary(auth):
    r = requests.get(f"{API}/metrics/summary?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    j = r.json()
    for f in ["total_requests", "error_rate", "mean_latency_ms", "services"]:
        assert f in j


def test_metrics_timeseries(auth):
    r = requests.get(f"{API}/metrics/timeseries?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0
    assert {"bucket", "k", "v"}.issubset(set(rows[0].keys()))


def test_metrics_table(auth):
    r = requests.get(f"{API}/metrics?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0
    for f in ["timestamp", "service_name", "category", "metric_type", "value"]:
        assert f in rows[0]


# ── Cost ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("group_by", ["service_name", "model", "project_id"])
def test_cost_grouping(auth, group_by):
    r = requests.get(f"{API}/cost?group_by={group_by}&time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0, f"empty for {group_by}"
    for f in ["key", "cost_usd", "input_tokens", "output_tokens", "traces"]:
        assert f in rows[0]


# ── Sessions ──────────────────────────────────────────────────────
def test_sessions_and_detail(auth):
    r = requests.get(f"{API}/sessions?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0
    for f in ["conversation_id", "service_name", "turns", "cost_usd", "tokens"]:
        assert f in rows[0]
    cid = rows[0]["conversation_id"]
    r2 = requests.get(f"{API}/sessions/{cid}", headers=auth, timeout=30)
    assert r2.status_code == 200
    assert isinstance(r2.json(), list)


# ── Tools ─────────────────────────────────────────────────────────
def test_tools(auth):
    r = requests.get(f"{API}/tools?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0
    for f in ["tool", "calls", "avg_ms", "errors"]:
        assert f in rows[0]


# ── Search ────────────────────────────────────────────────────────
def test_search(auth):
    r = requests.get(f"{API}/search?q=add", headers=auth, timeout=15)
    assert r.status_code == 200
    j = r.json()
    for f in ["projects", "services", "models", "traces", "conversations"]:
        assert f in j, f"missing {f}"


# ── Insights / Top / Models / Errors / Health-services ────────────
@pytest.mark.parametrize("by", ["cost", "latency", "tokens"])
def test_top_traces(auth, by):
    r = requests.get(f"{API}/top/traces?by={by}&time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list)
    if len(rows) >= 2:
        key = {"cost": "cost_usd", "latency": "duration_ms", "tokens": "tokens"}[by]
        vals = [r.get(key) or 0 for r in rows]
        assert vals == sorted(vals, reverse=True), f"{by} not sorted desc: {vals[:5]}"


def test_models(auth):
    r = requests.get(f"{API}/models?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list) and len(rows) > 0
    for f in ["cost_usd", "calls", "traces", "input_tokens", "output_tokens"]:
        assert f in rows[0]


def test_errors_by_service(auth):
    r = requests.get(f"{API}/errors/by-service?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    if rows:
        for f in ["service_name", "errors", "error_rate"]:
            assert f in rows[0]


def test_errors_top(auth):
    r = requests.get(f"{API}/errors/top?time_range=30d", headers=auth, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    if rows:
        for f in ["message", "occurrences"]:
            assert f in rows[0]


def test_health_services_with_token(auth):
    """The /api/health route is defined twice. Authenticated version should return service rows."""
    r = requests.get(f"{API}/health", headers=auth, timeout=30)
    assert r.status_code == 200
    j = r.json()
    # If the public {status: ok} wins, this test should detect it as a bug
    assert isinstance(j, list), f"Expected list of services but got: {j}"
    if j:
        for f in ["service_name", "last_seen", "minutes_since", "traces_48h", "error_rate"]:
            assert f in j[0]


def test_meta_last_refresh(auth):
    r = requests.get(f"{API}/meta/last-refresh", headers=auth, timeout=15)
    assert r.status_code == 200
    j = r.json()
    for f in ["spans", "logs", "metrics"]:
        assert f in j


# ── Pricing CRUD ──────────────────────────────────────────────────
def test_pricing_crud(auth):
    r = requests.get(f"{API}/config/pricing", headers=auth, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    new = {"model_prefix": "TEST_model_x", "input_cost": 1.5, "output_cost": 3.0, "active": True}
    r = requests.post(f"{API}/config/pricing", json=new, headers=auth, timeout=15)
    assert r.status_code == 200, r.text

    # find it
    rows = requests.get(f"{API}/config/pricing", headers=auth, timeout=15).json()
    target = [x for x in rows if x["model_prefix"] == "TEST_model_x"]
    assert target, "newly added pricing not found"
    pid = target[0]["id"]

    r = requests.patch(f"{API}/config/pricing/{pid}", json={"input_cost": 2.0}, headers=auth, timeout=15)
    assert r.status_code == 200

    rows = requests.get(f"{API}/config/pricing", headers=auth, timeout=15).json()
    updated = [x for x in rows if x["id"] == pid][0]
    assert updated["input_cost"] == 2.0


# ── Refresh pipeline (mock) ───────────────────────────────────────
def test_refresh_pipeline(auth):
    r = requests.post(f"{API}/refresh/pipeline", headers=auth, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert "execution" in j or "started" in j


def test_refresh_status(auth):
    r = requests.get(f"{API}/refresh/status?execution=local-mock-execution", headers=auth, timeout=15)
    assert r.status_code == 200
    assert r.json().get("state") == "SUCCEEDED"
