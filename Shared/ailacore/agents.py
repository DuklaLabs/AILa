"""Sdílený základ agentní vrstvy (§21 databanky).

Agent = `trigger → data → LLM rozhodnutí → akce/návrh → audit log`. Tenhle modul
drží společné kusy, ať je nekopíruje každý modul zvlášť:

  - `ControlLevel` – čtyři úrovně lidské kontroly z databanky §21.
  - `emit_proposal` / `emit_flag` – zápis do `agent.proposals` (+ audit v téže
    transakci). `proposal` čeká na schválení, `flag` je jen upozornění na vědomí.
  - `emit_report` – uložení periodického reportu do `agent.reports`.
  - `record_agent_run` – jeden auditní řádek „agent proběhl“.
  - `list_proposals` / `mark_reviewed` – čtení fronty a zápis verdiktu; vlastní
    „provedení“ schváleného návrhu si dodává modul (mapa kind → apply funkce).

Všechny `emit_*` / `mark_reviewed` berou **živé `conn`** a spoléhají na to, že
volající je obalí transakcí – audit se pak zapíše atomicky se změnou.
"""
from __future__ import annotations

import enum
import json
from datetime import date
from typing import Optional

from .audit import record_audit
from .models import User


class ControlLevel(str, enum.Enum):
    """Úrovně lidské kontroly (databanka §21)."""

    INFORM = "inform"                 # jen upozorní, nic nemění
    PROPOSE = "propose"              # připraví návrh, člověk schválí/odešle
    ACT_REVERSIBLE = "act_reversible"  # koná vratnou akci sám, vždy zalogováno
    NEEDS_APPROVAL = "needs_approval"  # nevratné/citlivé → vždy přes člověka


_PROPOSAL_COLS = (
    "id, module, agent, kind, target_type, target_id, payload, summary, "
    "confidence, status, created_at, reviewed_by_user_id, reviewed_at, review_note"
)


def _row(r) -> dict:
    d = dict(r)
    if isinstance(d.get("payload"), str):
        d["payload"] = json.loads(d["payload"])
    return d


async def _insert_proposal(
    conn,
    *,
    module: str,
    agent: str,
    kind: str,
    status: str,
    target_type: Optional[str],
    target_id,
    payload: Optional[dict],
    summary: Optional[str],
    confidence: Optional[float],
) -> dict:
    row = await conn.fetchrow(
        f"""
        INSERT INTO agent.proposals
            (module, agent, kind, target_type, target_id, payload, summary,
             confidence, status)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
        RETURNING {_PROPOSAL_COLS}
        """,
        module,
        agent,
        kind,
        target_type,
        None if target_id is None else str(target_id),
        json.dumps(payload or {}, ensure_ascii=False, default=str),
        summary,
        confidence,
        status,
    )
    await record_audit(
        conn,
        actor=None,
        action=f"{module}.agent.{agent}",
        target_type="agent_proposal",
        target_id=str(row["id"]),
        detail={"kind": kind, "status": status, "summary": summary,
                "target": [target_type, target_id]},
    )
    return _row(row)


async def emit_proposal(
    conn,
    *,
    module: str,
    agent: str,
    kind: str,
    target_type: Optional[str] = None,
    target_id=None,
    payload: Optional[dict] = None,
    summary: Optional[str] = None,
    confidence: Optional[float] = None,
) -> dict:
    """Návrh ke schválení – `status='pending'`, čeká na `agent.proposal:review`."""
    return await _insert_proposal(
        conn, module=module, agent=agent, kind=kind, status="pending",
        target_type=target_type, target_id=target_id, payload=payload,
        summary=summary, confidence=confidence,
    )


async def emit_flag(
    conn,
    *,
    module: str,
    agent: str,
    kind: str,
    target_type: Optional[str] = None,
    target_id=None,
    payload: Optional[dict] = None,
    summary: Optional[str] = None,
    confidence: Optional[float] = None,
) -> dict:
    """Upozornění na vědomí – `status='info'`, neschvaluje se, jen se zobrazí."""
    return await _insert_proposal(
        conn, module=module, agent=agent, kind=kind, status="info",
        target_type=target_type, target_id=target_id, payload=payload,
        summary=summary, confidence=confidence,
    )


async def emit_report(
    conn,
    *,
    module: str,
    agent: str,
    period: date,
    payload: dict,
    summary: Optional[str] = None,
) -> dict:
    """Uloží periodický report (upsert dle `module` + `period`)."""
    row = await conn.fetchrow(
        """
        INSERT INTO agent.reports (module, period, payload, summary)
        VALUES ($1, $2, $3::jsonb, $4)
        ON CONFLICT (module, period) DO UPDATE
            SET payload = EXCLUDED.payload,
                summary = EXCLUDED.summary,
                generated_at = now()
        RETURNING id, module, period, payload, summary, generated_at
        """,
        module,
        period,
        json.dumps(payload or {}, ensure_ascii=False, default=str),
        summary,
    )
    await record_audit(
        conn,
        actor=None,
        action=f"{module}.agent.{agent}",
        target_type="agent_report",
        target_id=str(row["id"]),
        detail={"period": period.isoformat(), "summary": summary},
    )
    d = dict(row)
    if isinstance(d.get("payload"), str):
        d["payload"] = json.loads(d["payload"])
    return d


async def record_agent_run(
    conn,
    *,
    module: str,
    agent: str,
    trigger: str,
    detail: Optional[dict] = None,
) -> None:
    """Jeden auditní řádek „agent proběhl“ (trigger = 'scheduler' | 'manual')."""
    await record_audit(
        conn,
        actor=None,
        action=f"{module}.agent.{agent}",
        target_type="agent_run",
        target_id=agent,
        detail={"trigger": trigger, **(detail or {})},
    )


async def list_proposals(
    conn,
    *,
    module: str,
    status: Optional[str] = "pending",
    kind: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    rows = await conn.fetch(
        f"""
        SELECT {_PROPOSAL_COLS} FROM agent.proposals
        WHERE module = $1
          AND ($2::text IS NULL OR status = $2)
          AND ($3::text IS NULL OR kind = $3)
        ORDER BY created_at DESC, id DESC
        LIMIT $4
        """,
        module,
        status or None,
        kind or None,
        limit,
    )
    return [_row(r) for r in rows]


async def get_proposal_for_update(conn, proposal_id: int) -> Optional[dict]:
    r = await conn.fetchrow(
        f"SELECT {_PROPOSAL_COLS} FROM agent.proposals WHERE id = $1 FOR UPDATE",
        proposal_id,
    )
    return _row(r) if r is not None else None


async def mark_reviewed(
    conn,
    *,
    proposal_id: int,
    reviewer: User,
    approve: bool,
    note: Optional[str] = None,
    applied: Optional[dict] = None,
) -> dict:
    """Zapíše verdikt do `agent.proposals` + audit. Skutečné „provedení“
    schváleného návrhu si volající udělá sám před voláním téhle funkce a předá
    výsledek v `applied` (jde do auditu)."""
    row = await conn.fetchrow(
        f"""
        UPDATE agent.proposals
        SET status = $2, reviewed_by_user_id = $3, reviewed_at = now(),
            review_note = $4
        WHERE id = $1
        RETURNING {_PROPOSAL_COLS}
        """,
        proposal_id,
        "approved" if approve else "rejected",
        reviewer.id,
        note,
    )
    await record_audit(
        conn,
        actor=reviewer,
        action="agent.proposal." + ("approve" if approve else "reject"),
        target_type="agent_proposal",
        target_id=str(proposal_id),
        detail={"applied": applied, "note": note},
    )
    return {**_row(row), "applied": applied}
