"""Autorizační smoke testy – chráněné routy služby Projects jedou přes
`ailacore.rbac` (servisní vrstva volá `user_has_permission`). Ověřuje:
bez oprávnění 403, s oprávněním projde guard (handler smí spadnout dál na
odmocněnou DB, jen ne na 403), a že read≠write.

Bez DB: mockuje `get_pool` v každém service modulu a `get_effective_permissions`.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ailacore import rbac
from ailacore.auth import get_current_user
from ailacore.models import User

from app.routers import api_router

# (metoda, cesta, požadované oprávnění, tělo)
CASES = [
    ("GET", "/api/workspaces", "projects.project:read", None),
    ("GET", "/api/projects", "projects.project:read", None),
    ("POST", "/api/projects", "projects.project:write", {"folder_id": 1, "name": "X"}),
    ("GET", "/api/tasks?project_id=1", "projects.task:read", None),
    ("POST", "/api/tasks", "projects.task:write", {"phase_id": 1, "title": "X"}),
    ("POST", "/api/tasks/1/assignee", "projects.task:assign", {"assignee_user_id": 1}),
    ("GET", "/api/tasks/1/time", "projects.time:log", None),
    ("GET", "/api/projects/1/costs", "projects.finance:read", None),
    ("GET", "/api/proposals", "projects.proposal:review", None),
    ("GET", "/api/users", "projects.task:read", None),
]

_SERVICE_MODULES = (
    "app.services.tree",
    "app.services.tasks",
    "app.services.time_tracking",
    "app.services.costs",
    "app.services.proposals",
    "app.services.settings",
    "app.services.people",
)


class _Conn:
    async def fetch(self, *a, **k): return []
    async def fetchrow(self, *a, **k): return None
    async def fetchval(self, *a, **k): return 0
    async def execute(self, *a, **k): return "UPDATE 0"
    async def executemany(self, *a, **k): return None
    def transaction(self): return _Ctx()


class _Ctx:
    async def __aenter__(self): return _Conn()
    async def __aexit__(self, *a): return False


class _Pool:
    def acquire(self): return _Ctx()


async def _fake_pool():
    return _Pool()


@pytest.fixture
def env(monkeypatch):
    for mod in _SERVICE_MODULES:
        monkeypatch.setattr(f"{mod}.get_pool", _fake_pool, raising=True)

    perms = {"set": frozenset()}

    async def fake_effective(user_id, role):
        return perms["set"]

    monkeypatch.setattr(rbac, "get_effective_permissions", fake_effective)

    app = FastAPI()
    app.include_router(api_router)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="t", role="member", is_active=True
    )
    return TestClient(app), perms


@pytest.mark.parametrize("method,path,perm,body", CASES)
def test_denied_without_permission(env, method, path, perm, body):
    client, perms = env
    perms["set"] = frozenset()
    r = client.request(method, path, json=body)
    assert r.status_code == 403, (method, path, r.status_code, r.text)
    assert perm in r.json()["detail"]


@pytest.mark.parametrize("method,path,perm,body", CASES)
def test_passes_guard_with_permission(env, method, path, perm, body):
    client, perms = env
    perms["set"] = frozenset({perm})
    r = client.request(method, path, json=body)
    assert r.status_code != 403, (method, path, r.status_code, r.text)


def test_granularity_read_does_not_grant_write(env):
    client, perms = env
    perms["set"] = frozenset({"projects.task:read"})
    assert client.get("/api/tasks?project_id=1").status_code != 403
    assert client.request(
        "POST", "/api/tasks/1/assignee", json={"assignee_user_id": 1}
    ).status_code == 403


def test_finance_write_needed_for_actual_cost(env):
    """update_task s actual_cost_czk vyžaduje navíc projects.finance:write."""
    client, perms = env
    perms["set"] = frozenset({"projects.task:write"})
    r = client.patch("/api/tasks/1", json={"actual_cost_czk": 1200})
    assert r.status_code == 403
    assert "projects.finance:write" in r.json()["detail"]
