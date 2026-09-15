"""Schvalovací fronta agentní vrstvy (`app.agent_review`).

Bez DB: `get_pool` je fake connection, `get_proposal_for_update` / `mark_reviewed`
/ `record_audit` se mockují. Ověřuje se větvení `_apply`, `ack` a proxy na
službu access-agents.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ailacore import rbac
from ailacore.auth import get_current_user
from ailacore.models import User

from app import agent_review
from app.agent_review import router_agent_review


# --- fake DB ----------------------------------------------------------------

class FakeConn:
    def __init__(self):
        self.execs = []       # (sql, args)
        self.fetchrows = []    # (sql, args)
        self.next_fetchrow = None

    async def execute(self, sql, *args):
        self.execs.append((sql, args))
        return "UPDATE 1"

    async def fetchrow(self, sql, *args):
        self.fetchrows.append((sql, args))
        r, self.next_fetchrow = self.next_fetchrow, None
        return r

    async def fetchval(self, sql, *args):
        return None

    def transaction(self):
        return _Ctx()


class _Ctx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *a):
        return False


class FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        pool = self

        class _Acq:
            async def __aenter__(self):
                return pool._conn

            async def __aexit__(self, *a):
                return False

        return _Acq()


PROP_REG = {
    "id": 7, "module": "access", "agent": "registration_triage",
    "kind": "registration.approve", "target_type": "user", "target_id": "42",
    "payload": {"student_id": 3, "checks": {}}, "summary": "x",
    "confidence": 0.7, "status": "pending",
}
PROP_PLAN = {
    "id": 8, "module": "access", "agent": "openhours_planner",
    "kind": "open_hours.week_plan", "target_type": "week",
    "target_id": "2026-09-14",
    "payload": {"slots": [
        {"date": "2026-09-15", "hour_number": 3, "supervisor": "A", "capacity": 4},
        {"date": "2026-09-16", "hour_number": 99, "supervisor": "A"},
    ]},
    "summary": "x", "confidence": None, "status": "pending",
}
PROP_INFO = {
    "id": 9, "module": "access", "agent": "release_advisor",
    "kind": "release.advice", "target_type": "booking", "target_id": "55",
    "payload": {}, "summary": "x", "confidence": 0.5, "status": "info",
}


@pytest.fixture
def env(monkeypatch):
    conn = FakeConn()

    async def fake_pool():
        return FakePool(conn)

    monkeypatch.setattr(agent_review, "get_pool", fake_pool)

    async def fake_audit(*a, **k):
        conn.execs.append(("AUDIT", (a, k)))

    monkeypatch.setattr(agent_review, "record_audit", fake_audit)

    reviewed = {}

    async def fake_mark_reviewed(c, *, proposal_id, reviewer, approve, note=None,
                                 applied=None):
        reviewed.update(proposal_id=proposal_id, approve=approve, applied=applied,
                        note=note)
        return {"id": proposal_id, "status": "approved" if approve else "rejected",
                "applied": applied}

    monkeypatch.setattr(agent_review, "mark_reviewed", fake_mark_reviewed)

    holder = {"prop": None}

    async def fake_get_for_update(c, pid):
        return holder["prop"]

    monkeypatch.setattr(agent_review, "get_proposal_for_update", fake_get_for_update)

    perms = {"set": frozenset({"agent.proposal:review", "agent.run:trigger"})}

    async def fake_effective(uid, role):
        return perms["set"]

    monkeypatch.setattr(rbac, "get_effective_permissions", fake_effective)

    app = FastAPI()
    app.include_router(router_agent_review)
    app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="admin", role="admin", is_active=True
    )
    return TestClient(app), conn, holder, reviewed, perms


# --- approve / reject -----------------------------------------------------

def test_approve_registration_activates_user(env):
    client, conn, holder, reviewed, _ = env
    holder["prop"] = dict(PROP_REG)
    conn.next_fetchrow = {"name": "Jan Novák"}  # RETURNING z UPDATE auth.users

    r = client.post("/api/agents/proposals/7/approve")
    assert r.status_code == 200, r.text
    assert reviewed["approve"] is True
    assert reviewed["applied"]["student_name"] == "Jan Novák"
    assert any("auth.users SET is_active = TRUE" in s for s, _ in conn.fetchrows)


def test_approve_week_plan_creates_and_skips(env, monkeypatch):
    client, conn, holder, reviewed, _ = env
    holder["prop"] = dict(PROP_PLAN)

    from app import open_hours as oh
    monkeypatch.setattr(oh, "_PERIODS_BY_NUMBER", {3: ("10:00", "10:45")},
                        raising=False)
    monkeypatch.setattr(oh, "_clean_supervisor", lambda s: s, raising=False)
    monkeypatch.setattr(oh, "_require_supervisor", lambda s: None, raising=False)

    async def _no_teach(sup, d, hn):
        return None

    monkeypatch.setattr(oh, "_reject_if_supervisor_teaching", _no_teach,
                        raising=False)

    r = client.post("/api/agents/proposals/8/approve")
    assert r.status_code == 200, r.text
    applied = reviewed["applied"]
    assert len(applied["created"]) == 1
    assert len(applied["skipped"]) == 1            # hodina 99 je mimo rozsah
    assert applied["skipped"][0]["slot"]["hour_number"] == 99


def test_approve_unknown_kind_422(env):
    client, conn, holder, reviewed, _ = env
    holder["prop"] = {**PROP_REG, "kind": "something.else"}
    r = client.post("/api/agents/proposals/7/approve")
    assert r.status_code == 422
    assert reviewed == {}                          # _apply spadl před mark_reviewed


def test_reject_does_not_apply(env):
    client, conn, holder, reviewed, _ = env
    holder["prop"] = dict(PROP_REG)
    r = client.post("/api/agents/proposals/7/reject")
    assert r.status_code == 200
    assert reviewed["approve"] is False
    assert reviewed["applied"] is None
    assert not any("auth.users" in s for s, _ in conn.fetchrows)


def test_second_review_conflicts(env):
    client, conn, holder, reviewed, _ = env
    holder["prop"] = {**PROP_REG, "status": "approved"}
    r = client.post("/api/agents/proposals/7/approve")
    assert r.status_code == 409


def test_review_missing_404(env):
    client, conn, holder, *_ = env
    holder["prop"] = None
    assert client.post("/api/agents/proposals/7/approve").status_code == 404


# --- ack ----------------------------------------------------------------

def test_ack_info_marks_acknowledged(env):
    client, conn, holder, *_ = env
    holder["prop"] = dict(PROP_INFO)
    r = client.post("/api/agents/proposals/9/ack")
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"
    assert any("status = 'acknowledged'" in s for s, _ in conn.execs)
    assert any(s == "AUDIT" for s, _ in conn.execs)


def test_ack_pending_conflicts(env):
    client, conn, holder, *_ = env
    holder["prop"] = dict(PROP_REG)           # status pending
    r = client.post("/api/agents/proposals/7/ack")
    assert r.status_code == 409


# --- proxy na access-agents -------------------------------------------

class _FakeResp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=None)


class _FakeClient:
    calls = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None):
        _FakeClient.calls.append(("POST", url, headers))
        return _FakeClient.resp

    async def get(self, url):
        _FakeClient.calls.append(("GET", url, None))
        return _FakeClient.resp


def test_run_proxy_forwards_token(env, monkeypatch):
    client, *_ = env
    _FakeClient.calls = []
    _FakeClient.resp = _FakeResp(200, {"agent": "x", "report_id": 5})
    monkeypatch.setattr(agent_review.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setenv("ACCESS_AGENTS_URL", "http://agents:8007")
    monkeypatch.setenv("ACCESS_AGENT_RUN_TOKEN", "sekret")

    r = client.post("/api/agents/run/monthly_lab_report")
    assert r.status_code == 200
    assert r.json()["report_id"] == 5
    method, url, headers = _FakeClient.calls[-1]
    assert url == "http://agents:8007/run/monthly_lab_report"
    assert headers["X-Agent-Token"] == "sekret"


def test_run_proxy_propagates_error(env, monkeypatch):
    client, *_ = env
    _FakeClient.calls = []
    _FakeClient.resp = _FakeResp(404, {"detail": "Neznámý agent: bogus"})
    monkeypatch.setattr(agent_review.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setenv("ACCESS_AGENT_RUN_TOKEN", "sekret")

    r = client.post("/api/agents/run/bogus")
    assert r.status_code == 404
    assert "bogus" in r.json()["detail"]


def test_run_proxy_without_token_503(env, monkeypatch):
    client, *_ = env
    monkeypatch.delenv("ACCESS_AGENT_RUN_TOKEN", raising=False)
    r = client.post("/api/agents/run/monthly_lab_report")
    assert r.status_code == 503


def test_registry_proxy_empty_on_failure(env, monkeypatch):
    client, *_ = env

    class _Boom(_FakeClient):
        async def get(self, url):
            import httpx
            raise httpx.ConnectError("down")

    monkeypatch.setattr(agent_review.httpx, "AsyncClient", _Boom)
    r = client.get("/api/agents/registry")
    assert r.status_code == 200
    assert r.json() == {"agents": []}


# --- guardy -----------------------------------------------------------

def test_ack_requires_review_permission(env):
    client, conn, holder, reviewed, perms = env
    perms["set"] = frozenset()
    holder["prop"] = dict(PROP_INFO)
    assert client.post("/api/agents/proposals/9/ack").status_code == 403


def test_run_requires_run_permission(env):
    client, conn, holder, reviewed, perms = env
    perms["set"] = frozenset({"agent.proposal:review"})
    assert client.post("/api/agents/run/monthly_lab_report").status_code == 403
