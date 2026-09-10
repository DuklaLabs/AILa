"""Testy agenta subject_release_watch."""
from datetime import date

import pytest

from app.agents import subject_release_watch as w
from tests._support import FakeConn, FakePool


def test_threshold_env(monkeypatch):
    monkeypatch.delenv("SUBJECT_RELEASE_STREAK", raising=False)
    assert w._threshold() == 3
    monkeypatch.setenv("SUBJECT_RELEASE_STREAK", "2")
    assert w._threshold() == 2
    monkeypatch.setenv("SUBJECT_RELEASE_STREAK", "xxx")
    assert w._threshold() == 3


def _mk_released(n, subject="Matematika"):
    return [
        {"id": i, "attended": None, "student_id": 1, "first_name": "Jan",
         "last_name": "Novák", "class_group": "4.ER",
         "date": date(2026, 6, i + 1), "hour_number": 2}
        for i in range(n)
    ]


async def test_flags_when_streak_reached(monkeypatch):
    conn = FakeConn(rows={"fetch": []})
    pool = FakePool(conn)

    monkeypatch.setenv("SUBJECT_RELEASE_STREAK", "3")
    monkeypatch.setattr(w, "get_pool", lambda: _async(pool))
    monkeypatch.setattr(w.m, "released_bookings",
                        lambda s, e: _async(_mk_released(3)))
    monkeypatch.setattr(w.m, "upcoming_bookings", lambda t: _async([
        {"id": 99, "approved": None, "student_id": 1, "first_name": "Jan",
         "last_name": "Novák", "class_group": "4.ER", "email": "j@x.cz",
         "open_hour_id": 5, "date": date(2026, 9, 17), "hour_number": 2,
         "start_time": None, "end_time": None, "note": None, "supervisor": None,
         "capacity": 5},
    ]))
    monkeypatch.setattr(
        w.dukla, "class_teachers",
        lambda cls, day, hour: _async([{"subject": "Matematika"}]),
    )
    monkeypatch.setattr(w, "decide", lambda **kw: {"_fallback": True})

    async def fake_send(**kw):
        return {"sent_to": ["k@x.cz"]}

    monkeypatch.setattr(w, "send_mail", fake_send)
    monkeypatch.setattr(w, "coordinator_emails", lambda: ["k@x.cz"])

    out = await w.run(trigger="manual", today=date(2026, 9, 15))
    assert out["alerts"] == 1
    assert conn.proposals[0]["status"] == "info"
    assert conn.proposals[0]["kind"] == "student.subject_release_alert"


async def test_no_flag_below_threshold(monkeypatch):
    conn = FakeConn(rows={"fetch": []})
    pool = FakePool(conn)
    monkeypatch.setenv("SUBJECT_RELEASE_STREAK", "3")
    monkeypatch.setattr(w, "get_pool", lambda: _async(pool))
    monkeypatch.setattr(w.m, "released_bookings",
                        lambda s, e: _async(_mk_released(2)))  # jen 2 < práh
    monkeypatch.setattr(w.m, "upcoming_bookings", lambda t: _async([
        {"id": 99, "approved": None, "student_id": 1, "first_name": "Jan",
         "last_name": "Novák", "class_group": "4.ER", "email": "j@x.cz",
         "open_hour_id": 5, "date": date(2026, 9, 17), "hour_number": 2,
         "start_time": None, "end_time": None, "note": None, "supervisor": None,
         "capacity": 5},
    ]))
    monkeypatch.setattr(
        w.dukla, "class_teachers",
        lambda cls, day, hour: _async([{"subject": "Matematika"}]),
    )
    out = await w.run(trigger="manual", today=date(2026, 9, 15))
    assert out["alerts"] == 0
    assert not conn.proposals


def _async(value):
    async def _c():
        return value
    return _c()
