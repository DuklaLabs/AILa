"""Testy agenta registration_triage."""
import pytest

from app.agents import registration_triage as t
from tests._support import FakeConn, FakePool


def test_school_domain(monkeypatch):
    monkeypatch.delenv("SCHOOL_EMAIL_DOMAIN", raising=False)
    monkeypatch.setenv("TEACHER_EMAIL_DOMAIN", "spssecb.cz")
    assert t._school_domain() == "spssecb.cz"
    monkeypatch.setenv("SCHOOL_EMAIL_DOMAIN", "@zaci.spssecb.cz")
    assert t._school_domain() == "zaci.spssecb.cz"


async def test_run_creates_proposal(monkeypatch):
    student = {
        "user_id": 42, "student_id": 7, "first_name": "Jan", "last_name": "Novák",
        "email": "novak@spssecb.cz", "class_group": "4.ER",
        "release_class_teacher": None,
    }
    conn = FakeConn(rows={"fetch": [student], "fetchval": 0})
    pool = FakePool(conn)

    monkeypatch.setenv("TEACHER_EMAIL_DOMAIN", "spssecb.cz")
    monkeypatch.setattr(t, "get_pool", lambda: _async(pool))
    monkeypatch.setattr(t.dukla, "class_week", lambda c, m: _async([{"day_index": 0,
                                                                     "hour_index": 1}]))
    monkeypatch.setattr(t.dukla, "class_teacher",
                        lambda c: _async({"name": "Petr Hána", "email": "h@x"}))
    monkeypatch.setattr(t, "decide", lambda **kw: {"_fallback": True})

    out = await t.run(trigger="manual")
    assert out["proposed"] == 1
    p = conn.proposals[0]
    assert p["kind"] == "registration.approve"
    assert p["target_type"] == "user"
    assert p["target_id"] == "42"
    assert p["status"] == "pending"
    assert out["items"][0]["suggestion"] == "ok"   # všechny kontroly prošly


async def test_run_flags_review_on_bad_domain(monkeypatch):
    student = {
        "user_id": 43, "student_id": 8, "first_name": "X", "last_name": "Y",
        "email": "someone@gmail.com", "class_group": "9.C",
        "release_class_teacher": None,
    }
    conn = FakeConn(rows={"fetch": [student], "fetchval": 0})
    pool = FakePool(conn)
    monkeypatch.setenv("TEACHER_EMAIL_DOMAIN", "spssecb.cz")
    monkeypatch.setattr(t, "get_pool", lambda: _async(pool))
    monkeypatch.setattr(t.dukla, "class_week", lambda c, m: _async([]))
    monkeypatch.setattr(t.dukla, "class_teacher", lambda c: _async(None))
    monkeypatch.setattr(t, "decide", lambda **kw: {"_fallback": True})

    out = await t.run(trigger="manual")
    assert out["items"][0]["suggestion"] == "review"


def _async(value):
    async def _c():
        return value
    return _c()
