"""Testy agentů služby access-agents (fake LLM + fake pool, bez DB)."""
from datetime import date

import pytest

from app.agents import AGENTS
from app.agents import monthly_lab_report as mlr
from tests._support import FakeConn, FakePool


def test_registry_has_monthly_report():
    assert "monthly_lab_report" in AGENTS
    assert callable(AGENTS["monthly_lab_report"])


@pytest.mark.parametrize(
    "today, start, end",
    [
        (date(2026, 9, 10), date(2026, 8, 1), date(2026, 9, 1)),
        (date(2026, 1, 5), date(2025, 12, 1), date(2026, 1, 1)),
        (date(2026, 3, 1), date(2026, 2, 1), date(2026, 3, 1)),
    ],
)
def test_prev_month_range(today, start, end):
    assert mlr._prev_month_range(today) == (start, end)


def test_fallback_summary_is_text():
    payload = {
        "period_start": "2026-08-01", "period_end": "2026-09-01",
        "occupancy": {"slots": 12, "fill_ratio": 0.5, "empty_slots": 2},
        "decisions": {"bookings": 20, "approved": 15, "denied": 3, "undecided": 2},
        "attendance": {"came": 12, "no_show": 3, "no_show_ratio": 0.2},
        "new_registrations": 4, "pending_consents": 1,
        "failed_mails": {"count": 0},
    }
    s = mlr._fallback_summary(payload)
    assert "2026-08-01" in s and "12 otevřených hodin" in s


async def test_run_writes_report_and_audits(monkeypatch):
    conn = FakeConn(rows={"prev_report": None})
    pool = FakePool(conn)

    async def fake_pool():
        return pool

    monkeypatch.setattr(mlr, "get_pool", fake_pool)
    monkeypatch.setattr(mlr.m, "open_hours_occupancy",
                        lambda s, e: _async({"slots": 10, "fill_ratio": 0.4,
                                             "empty_slots": 3, "capacity_total": 40,
                                             "booked_total": 16, "full_slots": 1}))
    monkeypatch.setattr(mlr.m, "booking_decisions",
                        lambda s, e: _async({"bookings": 16, "approved": 12,
                                             "denied": 2, "undecided": 2}))
    monkeypatch.setattr(mlr.m, "attendance_stats",
                        lambda s, e: _async({"approved": 12, "came": 10, "no_show": 2,
                                             "unchecked": 0, "no_show_ratio": 0.17}))
    monkeypatch.setattr(mlr.m, "released_bookings", lambda s, e: _async([]))
    monkeypatch.setattr(mlr.m, "new_registrations", lambda s, e: _async(3))
    monkeypatch.setattr(mlr.m, "pending_release_consents", lambda: _async([]))
    monkeypatch.setattr(mlr.m, "failed_mails",
                        lambda s, e: _async({"count": 0, "samples": []}))
    monkeypatch.setattr(mlr.m, "agent_flag_counts", lambda s, e: _async([]))
    monkeypatch.setattr(mlr, "decide", lambda **kw: {"_fallback": True, "_error": "x"})

    async def fake_send(**kw):
        return {"sent_to": ["k@spssecb.cz"]}

    monkeypatch.setattr(mlr, "send_mail", fake_send)
    monkeypatch.setattr(mlr, "coordinator_emails", lambda: ["k@spssecb.cz"])

    out = await mlr.run(trigger="manual", period=date(2026, 9, 15))
    assert out["agent"] == "monthly_lab_report"
    assert out["report_id"] == 1
    assert out["llm_fallback"] is True
    assert conn.reports and conn.reports[0]["module"] == "access"
    # emit_report + record_agent_run => 2 auditní řádky
    assert len(conn.audit) == 2


def _async(value):
    async def _coro():
        return value
    return _coro()
