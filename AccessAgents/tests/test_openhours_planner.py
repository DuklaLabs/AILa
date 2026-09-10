"""Testy agenta openhours_planner."""
from datetime import date

import pytest

from app.agents import openhours_planner as p
from tests._support import FakeConn, FakePool


@pytest.mark.parametrize(
    "today, monday",
    [
        (date(2026, 9, 10), date(2026, 9, 14)),   # čt → příští po
        (date(2026, 9, 14), date(2026, 9, 21)),   # po → příští po
        (date(2026, 9, 20), date(2026, 9, 21)),   # ne → příští po
    ],
)
def test_next_week_monday(today, monday):
    assert p._next_week_monday(today) == monday


async def test_rule_based_plan_emits_one_proposal(monkeypatch):
    conn = FakeConn(rows={"fetch": []})
    pool = FakePool(conn)

    monkeypatch.setattr(p, "get_pool", lambda: _async(pool))
    monkeypatch.setattr(p.dukla, "supervisor_names", lambda: ["Dozor A", "Dozor B"])
    monkeypatch.setattr(p.dukla, "fetch_supervisions",
                        lambda a, b, week="next": _async([]))
    monkeypatch.setattr(p.m, "demand_by_slot", lambda d: _async([
        {"weekday": 0, "hour_number": 3, "avg_booked": 5, "fill_ratio": 0.8},
        {"weekday": 2, "hour_number": 4, "avg_booked": 3, "fill_ratio": 0.5},
    ]))
    monkeypatch.setattr(p.m, "open_slots_between", lambda a, b: _async([]))
    monkeypatch.setattr(p, "decide", lambda **kw: {"_fallback": True})

    out = await p.run(trigger="manual", today=date(2026, 9, 10))
    assert out["slots"] == 2
    assert out["method"] == "rule_based"
    assert len(conn.proposals) == 1
    prop = conn.proposals[0]
    assert prop["kind"] == "open_hours.week_plan"
    import json
    body = json.loads(prop["payload"])
    assert len(body["slots"]) == 2
    assert body["slots"][0]["hour_number"] == 3
    assert body["slots"][0]["supervisor"] in ("Dozor A", "Dozor B")
    # 2 auditní řádky: emit_proposal + record_agent_run
    assert len(conn.audit) == 2


async def test_no_free_supervisors_returns_zero(monkeypatch):
    monkeypatch.setattr(p.dukla, "supervisor_names", lambda: [])
    monkeypatch.setattr(p.m, "demand_by_slot", lambda d: _async([]))
    monkeypatch.setattr(p.m, "open_slots_between", lambda a, b: _async([]))
    out = await p.run(trigger="manual", today=date(2026, 9, 10))
    assert out["slots"] == 0


def _async(value):
    async def _c():
        return value
    return _c()
