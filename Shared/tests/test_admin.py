"""Testy pro ailacore.admin – čisté pomocné funkce + guard wiring (bez DB)."""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from ailacore import admin, rbac
from ailacore.admin import (
    diff_set,
    mount_spa,
    validate_permission_names,
    validate_role_assignment,
)
from ailacore.auth import get_current_user
from ailacore.models import User


# --- čisté funkce ---------------------------------------------------------

def test_diff_set():
    assert diff_set({"a", "b"}, {"b", "c"}) == ({"c"}, {"a"})
    assert diff_set([], ["x"]) == ({"x"}, set())
    assert diff_set(["x"], ["x"]) == (set(), set())


def test_validate_role_assignment():
    known = {"admin", "staff", "member"}
    validate_role_assignment("staff", ["member"], known)  # ok
    with pytest.raises(HTTPException):
        validate_role_assignment("ghost", [], known)          # neznámá primární
    with pytest.raises(HTTPException):
        validate_role_assignment("staff", ["ghost"], known)   # neznámá sekundární
    with pytest.raises(HTTPException):
        validate_role_assignment("staff", ["staff"], known)   # primární == sekundární


def test_validate_permission_names():
    catalog = {"*", "orders.order:read", "orders.order:approve"}
    validate_permission_names(["orders.order:read"], catalog, allow_wildcard=False)
    validate_permission_names(["*"], catalog, allow_wildcard=True)
    with pytest.raises(HTTPException):
        validate_permission_names(["nope:nope"], catalog, allow_wildcard=True)
    with pytest.raises(HTTPException):
        validate_permission_names(["*"], catalog, allow_wildcard=False)  # '*' přímo uživateli ne


# --- guard wiring -------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(admin.rbac_api_router)

    perms = {"set": frozenset()}

    async def fake_effective(user_id, role):
        return perms["set"]

    monkeypatch.setattr(rbac, "get_effective_permissions", fake_effective)
    monkeypatch.setattr(admin, "get_effective_permissions", fake_effective)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="t", role="member", is_active=True
    )
    return TestClient(app), perms


def test_effective_endpoint(client):
    c, perms = client
    perms["set"] = frozenset({"auth.role:manage", "orders.order:read"})
    r = c.get("/api/rbac/effective")
    assert r.status_code == 200
    body = r.json()
    assert body["can_manage"] is True
    assert "orders.order:read" in body["permissions"]


def test_manage_route_forbidden_without_permission(client):
    c, perms = client
    perms["set"] = frozenset({"orders.order:read"})  # chybí auth.role:manage
    r = c.get("/api/rbac/roles")
    assert r.status_code == 403
    assert "auth.role:manage" in r.json()["detail"]


def test_manage_route_passes_guard_with_permission(client, monkeypatch):
    c, perms = client
    perms["set"] = frozenset({"auth.role:manage"})

    # guard projde -> handler sáhne na DB; podstrčíme fake pool a ověříme,
    # že se dostal za require_permission (vrací data, ne 403).
    class _Conn:
        async def fetch(self, *a, **k):
            return [{"name": "internal.open_hours:read", "description": None}]

    class _Acq:
        async def __aenter__(self): return _Conn()
        async def __aexit__(self, *a): return False

    class _Pool:
        def acquire(self): return _Acq()

    async def fake_pool():
        return _Pool()

    monkeypatch.setattr(admin, "get_pool", fake_pool)
    r = c.get("/api/rbac/permissions")
    assert r.status_code == 200
    assert r.json()[0]["name"] == "internal.open_hours:read"


# --- mount_spa --------------------------------------------------------

def test_mount_spa_missing_build_is_noop(tmp_path, caplog):
    """Chybějící build → jen varování, žádná routa se nepřidá."""
    app = FastAPI()
    before = len(app.routes)
    mount_spa(app, tmp_path / "nope", path="/app/projects")
    assert len(app.routes) == before


def test_mount_spa_serves_index_behind_login(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>projects</title>")

    app = FastAPI()
    mount_spa(app, dist, path="/app/projects", login_url="/login")
    client = TestClient(app)

    async def no_user(_token):
        return None

    monkeypatch.setattr(admin, "get_user_from_token", no_user)
    r = client.get("/app/projects", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/login"

    async def a_user(_token):
        return User(id=1, username="t", role="member", is_active=True)

    monkeypatch.setattr(admin, "get_user_from_token", a_user)
    r = client.get("/app/projects")
    assert r.status_code == 200
    assert "projects" in r.text
