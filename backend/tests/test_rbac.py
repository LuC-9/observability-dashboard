"""RBAC end-to-end backend tests."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_USER = "admin1"
ADMIN_PASS = "pwd1"

# Project ids seeded by /app/backend/seed_data.py
PROJ_DV = "oa-apmena-techsandbox-ap-dv"
PROJ_PROD = "oa-apmena-techsandbox-ap-prod"


def _login(username: str, password: str):
    r = requests.post(f"{API}/login", json={"username": username, "password": password}, timeout=30)
    return r


@pytest.fixture(scope="module")
def admin_token():
    r = _login(ADMIN_USER, ADMIN_PASS)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["role"] == "admin"
    assert j["allowed_projects"] == []
    return j["token"]


@pytest.fixture
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# Unique test user (cleaned up via DELETE at end)
TEST_USER = f"TEST_alice_{uuid.uuid4().hex[:6]}"
TEST_PASS = "alicepwd"


@pytest.fixture(scope="module")
def user_setup(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    # cleanup if present
    requests.delete(f"{API}/admin/users/{TEST_USER}", headers=h, timeout=15)
    # create as user with one project
    r = requests.post(f"{API}/admin/users", headers=h, json={
        "username": TEST_USER, "password": TEST_PASS, "role": "user",
        "allowed_projects": [PROJ_DV],
    }, timeout=15)
    assert r.status_code == 200, r.text
    # login as user
    r2 = _login(TEST_USER, TEST_PASS)
    assert r2.status_code == 200, r2.text
    j = r2.json()
    assert j["role"] == "user"
    assert j["allowed_projects"] == [PROJ_DV]
    yield j["token"]
    # teardown
    requests.delete(f"{API}/admin/users/{TEST_USER}", headers=h, timeout=15)


@pytest.fixture
def user_h(user_setup):
    return {"Authorization": f"Bearer {user_setup}"}


# ───────── Login + /api/me ─────────
def test_admin_login_shape():
    r = _login(ADMIN_USER, ADMIN_PASS)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "token" in j and isinstance(j["token"], str) and len(j["token"]) > 20
    assert j["role"] == "admin"
    assert j["allowed_projects"] == []


def test_me_admin(admin_h):
    r = requests.get(f"{API}/me", headers=admin_h, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["username"] == ADMIN_USER
    assert j["role"] == "admin"
    assert j["allowed_projects"] == []


# ───────── Admin user CRUD ─────────
def test_admin_users_list(admin_h):
    r = requests.get(f"{API}/admin/users", headers=admin_h, timeout=15)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list)
    assert any(u["username"] == ADMIN_USER for u in rows)


def test_admin_projects_lists_all(admin_h):
    r = requests.get(f"{API}/admin/projects", headers=admin_h, timeout=15)
    assert r.status_code == 200, r.text
    rows = r.json()
    ids = [row.get("project_id") for row in rows]
    assert PROJ_DV in ids, f"expected {PROJ_DV} in {ids}"
    assert PROJ_PROD in ids, f"expected {PROJ_PROD} in {ids}"


def test_filters_projects_admin_sees_all(admin_h):
    r = requests.get(f"{API}/filters/projects", headers=admin_h, timeout=15)
    assert r.status_code == 200
    rows = r.json()
    ids = [row.get("project_id") for row in rows]
    assert PROJ_DV in ids and PROJ_PROD in ids


def test_create_update_delete_user_flow(admin_h):
    uname = f"TEST_bob_{uuid.uuid4().hex[:6]}"
    # create
    r = requests.post(f"{API}/admin/users", headers=admin_h, json={
        "username": uname, "password": "bobpwd", "role": "user", "allowed_projects": [PROJ_PROD],
    }, timeout=15)
    assert r.status_code == 200, r.text
    # verify in list
    rows = requests.get(f"{API}/admin/users", headers=admin_h, timeout=15).json()
    me = [u for u in rows if u["username"] == uname]
    assert len(me) == 1
    assert me[0]["role"] == "user"
    assert me[0]["allowed_projects"] == [PROJ_PROD]
    # patch
    r = requests.patch(f"{API}/admin/users/{uname}", headers=admin_h,
                       json={"allowed_projects": [PROJ_DV, PROJ_PROD]}, timeout=15)
    assert r.status_code == 200, r.text
    rows = requests.get(f"{API}/admin/users", headers=admin_h, timeout=15).json()
    me = [u for u in rows if u["username"] == uname][0]
    assert sorted(me["allowed_projects"]) == sorted([PROJ_DV, PROJ_PROD])
    # delete
    r = requests.delete(f"{API}/admin/users/{uname}", headers=admin_h, timeout=15)
    assert r.status_code == 200
    rows = requests.get(f"{API}/admin/users", headers=admin_h, timeout=15).json()
    assert not any(u["username"] == uname for u in rows)


def test_admin_cannot_delete_self(admin_h):
    r = requests.delete(f"{API}/admin/users/{ADMIN_USER}", headers=admin_h, timeout=15)
    assert r.status_code == 400, r.text


# ───────── Non-admin access control ─────────
def test_me_user(user_h):
    r = requests.get(f"{API}/me", headers=user_h, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["role"] == "user"
    assert j["allowed_projects"] == [PROJ_DV]


def test_non_admin_blocked_from_admin_endpoints(user_h):
    for ep in ["/admin/users", "/admin/projects"]:
        r = requests.get(f"{API}{ep}", headers=user_h, timeout=15)
        assert r.status_code == 403, f"{ep} -> {r.status_code} {r.text}"
        assert "admin" in r.text.lower()
    # also POST admin/users
    r = requests.post(f"{API}/admin/users", headers=user_h, json={
        "username": "x", "password": "x", "role": "user", "allowed_projects": []}, timeout=15)
    assert r.status_code == 403


def test_filters_projects_user_restricted(user_h):
    r = requests.get(f"{API}/filters/projects", headers=user_h, timeout=15)
    assert r.status_code == 200, r.text
    rows = r.json()
    ids = [row.get("project_id") for row in rows]
    assert ids == [PROJ_DV], f"user should see only {PROJ_DV}, got {ids}"


def test_overview_user_with_disallowed_project_403(user_h):
    r = requests.get(f"{API}/overview?project={PROJ_PROD}&time_range=30d", headers=user_h, timeout=30)
    assert r.status_code == 403, r.text


def test_overview_user_no_project_restricted_data(user_h, admin_h):
    """User without project param should aggregate only over allowed projects."""
    r = requests.get(f"{API}/overview?time_range=30d", headers=user_h, timeout=30)
    assert r.status_code == 200, r.text
    user_kpis = r.json()["kpis"]
    # admin over only allowed project
    r2 = requests.get(f"{API}/overview?project={PROJ_DV}&time_range=30d", headers=admin_h, timeout=30)
    assert r2.status_code == 200
    admin_kpis = r2.json()["kpis"]
    # Should match because the user is restricted to PROJ_DV only
    assert user_kpis["traces"] == admin_kpis["traces"], (user_kpis, admin_kpis)
    assert user_kpis["spans"] == admin_kpis["spans"]


def test_traces_detail_forbidden_for_disallowed_project(user_h, admin_h):
    """Find a trace in PROJ_PROD via admin, then assert user gets 403 on detail."""
    r = requests.get(f"{API}/traces?project={PROJ_PROD}&time_range=30d&page_size=5",
                     headers=admin_h, timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    if not rows:
        pytest.skip("no traces in PROD project to test against")
    tid = rows[0]["trace_id"]
    r2 = requests.get(f"{API}/traces/{tid}", headers=user_h, timeout=15)
    assert r2.status_code == 403, f"expected 403, got {r2.status_code} {r2.text}"
    # And user should still be able to fetch a trace from their allowed project
    r3 = requests.get(f"{API}/traces?project={PROJ_DV}&time_range=30d&page_size=5",
                      headers=admin_h, timeout=30)
    rows3 = r3.json()["rows"]
    if rows3:
        tid_ok = rows3[0]["trace_id"]
        r4 = requests.get(f"{API}/traces/{tid_ok}", headers=user_h, timeout=15)
        assert r4.status_code == 200, r4.text


def test_sessions_detail_forbidden_for_disallowed_project(user_h, admin_h):
    r = requests.get(f"{API}/sessions?project={PROJ_PROD}&time_range=30d",
                     headers=admin_h, timeout=30)
    assert r.status_code == 200, r.text
    rows = r.json()
    if not rows:
        pytest.skip("no sessions in PROD project")
    cid = rows[0]["conversation_id"]
    r2 = requests.get(f"{API}/sessions/{cid}", headers=user_h, timeout=15)
    assert r2.status_code == 403, f"got {r2.status_code} {r2.text}"


# ───────── User with NO projects ─────────
def test_user_with_no_projects_overview_empty(admin_h):
    uname = f"TEST_nobody_{uuid.uuid4().hex[:6]}"
    try:
        r = requests.post(f"{API}/admin/users", headers=admin_h, json={
            "username": uname, "password": "x", "role": "user", "allowed_projects": [],
        }, timeout=15)
        assert r.status_code == 200, r.text
        tok = _login(uname, "x").json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        # filters/projects should be empty
        r = requests.get(f"{API}/filters/projects", headers=h, timeout=15)
        assert r.status_code == 200
        assert r.json() == [] or len(r.json()) == 0
        # overview should not 500
        r = requests.get(f"{API}/overview?time_range=30d", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        k = r.json().get("kpis", {})
        assert k.get("traces", 0) == 0
        assert k.get("spans", 0) == 0
    finally:
        requests.delete(f"{API}/admin/users/{uname}", headers=admin_h, timeout=15)
