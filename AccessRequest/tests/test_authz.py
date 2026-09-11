"""Autorizační smoke testy – chráněné routy AccessRequestu jedou přes
`ailacore.rbac.require_permission`. Ověřuje: bez oprávnění 403, s oprávněním
projde guard (handler smí spadnout dál na odmocněné DB, jen ne na 403).

Bez DB: mockuje `get_pool` v každém app modulu a `get_effective_permissions`.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ailacore import rbac
from ailacore.auth import get_current_user
from ailacore.models import User

from app.mail_log import router_mail_log
from app.open_hours import router as open_hours_router
from app.students import router_students
from app.release import router_release
from app.decisions import router_decisions
from app.agent_review import router_agent_review
from app import router as router_mod


# (metoda, cesta, požadované oprávnění)
CASES = [
    ("GET", "/api/mail-log", "messaging.mail_log:read"),
    ("GET", "/api/open-hours/supervisors", "internal.open_hours:read"),
    ("DELETE", "/api/open-hours/delete/1", "internal.open_hours:write"),
    ("GET", "/api/open-hours/1/bookings", "internal.booking:read"),
    ("GET", "/api/students/pending", "internal.student:read"),
    ("POST", "/api/students/1/approve", "internal.student:write"),
    ("GET", "/api/students/release-pending", "internal.release:manage"),
    ("GET", "/api/decisions/scheduler", "internal.release:manage"),
    ("GET", "/api/agents/proposals", "agent.proposal:review"),
    ("POST", "/api/agents/proposals/1/approve", "agent.proposal:review"),
    ("POST", "/api/agents/proposals/1/reject", "agent.proposal:review"),
    ("POST", "/api/agents/proposals/1/ack", "agent.proposal:review"),
    ("GET", "/api/agents/reports", "agent.report:read"),
    ("GET", "/api/agents/reports/1", "agent.report:read"),
    ("GET", "/api/agents/runs", "agent.proposal:review"),
    ("GET", "/api/agents/registry", "agent.proposal:review"),
    ("POST", "/api/agents/run/monthly_lab_report", "agent.run:trigger"),
]


class _Conn:
    async def fetch(self, *a, **k): return []
    async def fetchrow(self, *a, **k): return None
    async def fetchval(self, *a, **k): return 0
    async def execute(self, *a, **k): return "UPDATE 0"
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
    for mod in ("app.mail_log", "app.open_hours", "app.students",
                "app.release", "app.decisions", "app.agent_review"):
        monkeypatch.setattr(f"{mod}.get_pool", _fake_pool, raising=True)

    perms = {"set": frozenset()}

    async def fake_effective(user_id, role):
        return perms["set"]

    monkeypatch.setattr(rbac, "get_effective_permissions", fake_effective)

    app = FastAPI()
    for r in (router_mail_log, open_hours_router, router_students,
              router_release, router_decisions, router_agent_review):
        app.include_router(r)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="t", role="member", is_active=True
    )
    return TestClient(app), perms


@pytest.mark.parametrize("method,path,perm", CASES)
def test_denied_without_permission(env, method, path, perm):
    client, perms = env
    perms["set"] = frozenset()
    r = client.request(method, path)
    assert r.status_code == 403, (method, path, r.status_code)
    assert perm in r.json()["detail"]


@pytest.mark.parametrize("method,path,perm", CASES)
def test_passes_guard_with_permission(env, method, path, perm):
    client, perms = env
    perms["set"] = frozenset({perm})
    r = client.request(method, path)
    assert r.status_code != 403, (method, path, r.status_code, r.text)


def test_granularity_read_does_not_grant_write(env):
    client, perms = env
    perms["set"] = frozenset({"internal.open_hours:read"})
    assert client.get("/api/open-hours/supervisors").status_code != 403
    assert client.delete("/api/open-hours/delete/1").status_code == 403


@pytest.mark.parametrize("has_perm,expected_user", [(False, False), (True, True)])
async def test_admin_page_guard(monkeypatch, has_perm, expected_user):
    """router._require_staff je teď na oprávnění internal.open_hours:read,
    ne na roli. Volá se přímo (routa /admin renderuje šablonu)."""
    user = User(id=9, username="p", role="member", is_active=True)

    async def fake_token(_):
        return user

    async def fake_effective(uid, role):
        return frozenset({"internal.open_hours:read"}) if has_perm else frozenset()

    monkeypatch.setattr(router_mod, "get_user_from_token", fake_token)
    monkeypatch.setattr(rbac, "get_effective_permissions", fake_effective)

    class _Req:
        cookies = {}

    result = await router_mod._require_staff(_Req())
    assert (result is not None) is expected_user
