"""Testy pro ailacore.agents – emit helpery zapisují řádek + audit ve stejné
transakci (fake conn, bez DB)."""
import json

import pytest

from ailacore import agents
from ailacore.agents import ControlLevel
from ailacore.models import User


class FakeConn:
    """Zachytává execute/fetchrow volání místo skutečné DB."""

    def __init__(self):
        self.audit: list[tuple] = []
        self.proposals: list[dict] = []

    async def execute(self, sql, *args):
        if "auth.audit_log" in sql:
            self.audit.append(args)
        return "INSERT 0 1"

    async def fetch(self, sql, *args):
        return []

    async def fetchrow(self, sql, *args):
        if "INSERT INTO agent.proposals" in sql:
            (module, agent, kind, tt, tid, payload, summary, conf, status) = args
            row = dict(
                id=len(self.proposals) + 1, module=module, agent=agent, kind=kind,
                target_type=tt, target_id=tid, payload=payload, summary=summary,
                confidence=conf, status=status, created_at=None,
                reviewed_by_user_id=None, reviewed_at=None, review_note=None,
            )
            self.proposals.append(row)
            return row
        if "INSERT INTO agent.reports" in sql:
            module, period, payload, summary = args
            return dict(id=1, module=module, period=period, payload=payload,
                        summary=summary, generated_at=None)
        if sql.strip().startswith("UPDATE agent.proposals"):
            pid, status, rid, note = args
            return dict(
                id=pid, module="access", agent="x", kind="k", target_type=None,
                target_id=None, payload="{}", summary=None, confidence=None,
                status=status, created_at=None, reviewed_by_user_id=rid,
                reviewed_at=None, review_note=note,
            )
        return None


def test_control_levels():
    assert [c.value for c in ControlLevel] == [
        "inform", "propose", "act_reversible", "needs_approval",
    ]


async def test_emit_proposal_is_pending_and_audited():
    conn = FakeConn()
    out = await agents.emit_proposal(
        conn, module="access", agent="registration_triage",
        kind="registration.approve", target_type="user", target_id=5,
        payload={"email": "a@b.cz"}, summary="vypadá ok", confidence=0.9,
    )
    assert out["status"] == "pending"
    assert out["payload"] == {"email": "a@b.cz"}
    assert out["target_id"] == "5"            # stringifikováno
    assert out["confidence"] == 0.9
    assert len(conn.audit) == 1               # audit ve stejné transakci
    assert conn.audit[0][2] == "access.agent.registration_triage"


async def test_emit_flag_is_info():
    conn = FakeConn()
    out = await agents.emit_flag(
        conn, module="access", agent="subject_release_watch",
        kind="student.subject_release_alert", target_type="student", target_id=12,
        payload={"subject": "Matematika", "streak": 3}, summary="3 hodiny za sebou",
    )
    assert out["status"] == "info"
    assert out["confidence"] is None
    assert len(conn.audit) == 1


async def test_emit_report_upsert_and_audit():
    from datetime import date

    conn = FakeConn()
    out = await agents.emit_report(
        conn, module="access", agent="monthly_lab_report",
        period=date(2026, 8, 1), payload={"slots": 10}, summary="srpen",
    )
    assert out["payload"] == {"slots": 10}
    assert len(conn.audit) == 1
    assert conn.audit[0][2] == "access.agent.monthly_lab_report"


async def test_record_agent_run():
    conn = FakeConn()
    await agents.record_agent_run(
        conn, module="access", agent="monthly_lab_report", trigger="manual",
        detail={"note": "test"},
    )
    assert len(conn.audit) == 1
    action, target_type, target_id, detail_json = conn.audit[0][2:6]
    assert action == "access.agent.monthly_lab_report"
    assert target_type == "agent_run"
    assert target_id == "monthly_lab_report"
    assert json.loads(detail_json)["trigger"] == "manual"


async def test_mark_reviewed_approve():
    conn = FakeConn()
    out = await agents.mark_reviewed(
        conn, proposal_id=7, reviewer=User(id=3, username="admin", role="admin",
                                           is_active=True),
        approve=True, note="ok", applied={"approved_student": 5},
    )
    assert out["status"] == "approved"
    assert out["reviewed_by_user_id"] == 3
    assert out["applied"] == {"approved_student": 5}
    assert conn.audit[0][2] == "agent.proposal.approve"
