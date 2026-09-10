"""Testy agenta release_advisor."""
from datetime import date

import pytest

from app.agents import release_advisor as a
from tests._support import FakeConn, FakePool


def _ctx(**over):
    base = {
        "student": "Jan Novák", "class_group": "4.ER", "date": "2026-09-17",
        "hour_number": 3, "collides_with_lesson": False, "subject": "",
        "release_consent_ok": True, "occupancy": "1/6", "note": None,
        "history": {"approved": 2, "denied": 0, "came": 2, "no_show": 0},
        "subject_streak": 0,
    }
    base.update(over)
    return base


def test_fallback_advice_clean_is_povolit():
    out = a._fallback_advice(_ctx())
    assert out["recommendation"] == "povolit"


def test_fallback_advice_risky_is_zvazit():
    out = a._fallback_advice(_ctx(
        collides_with_lesson=True, subject="Matematika",
        release_consent_ok=False,
        history={"approved": 3, "denied": 1, "came": 1, "no_show": 3},
        subject_streak=3,
    ))
    assert out["recommendation"] == "zvazit"
    assert "koliduje s výukou" in out["reason"]


async def test_run_creates_advice_flag(monkeypatch):
    conn = FakeConn(rows={"fetch": []})
    pool = FakePool(conn)

    booking = {
        "id": 55, "approved": None, "attended": None, "student_id": 1,
        "first_name": "Jan", "last_name": "Novák", "class_group": "4.ER",
        "email": "j@x.cz", "release_teacher_ok": True, "release_coord_ok": True,
        "open_hour_id": 9, "date": date(2026, 9, 17), "hour_number": 3,
        "start_time": None, "end_time": None, "note": None, "supervisor": None,
        "capacity": 6, "booked_count": 1,
    }
    monkeypatch.setattr(a, "get_pool", lambda: _async(pool))
    monkeypatch.setattr(a.m, "upcoming_bookings", lambda t: _async([booking]))
    monkeypatch.setattr(a.m, "student_release_history",
                        lambda ids: _async({1: {"approved": 2, "denied": 0,
                                                "came": 2, "no_show": 0}}))
    monkeypatch.setattr(a.dukla, "class_teachers",
                        lambda c, d, h: _async([]))  # nekoliduje
    monkeypatch.setattr(a, "decide", lambda **kw: {"_fallback": True})

    out = await a.run(trigger="manual", today=date(2026, 9, 15))
    assert out["advice"] == 1
    assert conn.proposals[0]["kind"] == "release.advice"
    assert conn.proposals[0]["status"] == "info"
    assert conn.proposals[0]["target_id"] == "55"


async def test_run_dedup_skips_done(monkeypatch):
    conn = FakeConn(rows={"fetch": [{"target_id": "55"}]})  # už má doporučení
    pool = FakePool(conn)
    booking = {
        "id": 55, "approved": None, "attended": None, "student_id": 1,
        "first_name": "Jan", "last_name": "N", "class_group": "4.ER",
        "email": "j@x", "release_teacher_ok": True, "release_coord_ok": True,
        "open_hour_id": 9, "date": date(2026, 9, 17), "hour_number": 3,
        "start_time": None, "end_time": None, "note": None, "supervisor": None,
        "capacity": 6, "booked_count": 1,
    }
    monkeypatch.setattr(a, "get_pool", lambda: _async(pool))
    monkeypatch.setattr(a.m, "upcoming_bookings", lambda t: _async([booking]))
    monkeypatch.setattr(a.m, "student_release_history", lambda ids: _async({}))
    monkeypatch.setattr(a.dukla, "class_teachers", lambda c, d, h: _async([]))
    out = await a.run(trigger="manual", today=date(2026, 9, 15))
    assert out["advice"] == 0
    assert not conn.proposals


def _async(value):
    async def _c():
        return value
    return _c()
