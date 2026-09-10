"""Schvalovací fronta a reporty agentní vrstvy (běží v access-request-server,
protože ten má session, RBAC konzoli a admin šablonu).

    GET  /api/agents/proposals?status=&kind=      agent.proposal:review
    POST /api/agents/proposals/{id}/approve       agent.proposal:review
    POST /api/agents/proposals/{id}/reject        agent.proposal:review
    GET  /api/agents/reports                      agent.report:read
    GET  /api/agents/reports/{id}                 agent.report:read
    GET  /api/agents/runs                         agent.proposal:review

Návrhy vytváří služba `access-agents` do sdílené `agent.proposals` (`module='access'`).
Schválení podle `kind` zavolá odpovídající „apply“ akci nad daty modulu; teprve
pak se návrh označí jako approved (vše v jedné transakci + audit).
"""
from __future__ import annotations

import datetime
import json
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ailacore.agents import get_proposal_for_update, list_proposals, mark_reviewed
from ailacore.db import get_pool
from ailacore.models import User
from ailacore.rbac import require_permission

router_agent_review = APIRouter(prefix="/api/agents", tags=["Agents"])

_REVIEW = [Depends(require_permission("agent.proposal:review"))]
_REPORT = [Depends(require_permission("agent.report:read"))]

MODULE = "access"


class ReviewIn(BaseModel):
    note: Optional[str] = None


@router_agent_review.get("/proposals", dependencies=_REVIEW)
async def get_proposals(
    status: Optional[str] = Query("pending"),
    kind: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await list_proposals(
            conn, module=MODULE, status=status or None, kind=kind, limit=limit
        )


async def _apply(conn, prop: dict) -> dict:
    """Provede schválený návrh nad daty modulu. Rozšiřuje se s dalšími agenty."""
    kind = prop["kind"]
    tid = prop["target_id"]

    if kind == "registration.approve":
        res = await conn.execute(
            "UPDATE auth.users SET is_active = TRUE "
            "WHERE id = $1 AND role = 'student'",
            int(tid),
        )
        if res == "UPDATE 0":
            raise HTTPException(404, "Studentský účet nenalezen.")
        return {"approved_student_user_id": int(tid)}

    if kind == "open_hours.week_plan":
        return await _apply_week_plan(conn, prop["payload"] or {})

    raise HTTPException(
        422, f"Schválení návrhu typu {kind!r} zatím není podporováno."
    )


async def _apply_week_plan(conn, payload: dict) -> dict:
    """Založí navržené otevřené hodiny stávající logikou z app.open_hours.
    Slot, který nejde založit (duplicita, dozor učí, neplatná hodina),
    se přeskočí – ostatní se založí."""
    from app.open_hours import (
        _PERIODS_BY_NUMBER, _clean_supervisor, _reject_if_supervisor_teaching,
        _require_supervisor,
    )

    created: list[dict] = []
    skipped: list[dict] = []
    for s in payload.get("slots") or []:
        try:
            hn = int(s["hour_number"])
            d = datetime.date.fromisoformat(str(s["date"]))
        except (KeyError, ValueError, TypeError):
            skipped.append({"slot": s, "why": "neplatné datum/hodina"})
            continue
        if hn not in _PERIODS_BY_NUMBER:
            skipped.append({"slot": s, "why": "neplatná vyučovací hodina"})
            continue
        sup = _clean_supervisor(s.get("supervisor"))
        try:
            _require_supervisor(sup)
            await _reject_if_supervisor_teaching(sup, d, hn)
        except HTTPException as e:
            skipped.append({"slot": s, "why": e.detail})
            continue
        if await conn.fetchval(
            "SELECT 1 FROM internal.open_hours WHERE date = $1 AND hour_number = $2",
            d, hn,
        ):
            skipped.append({"slot": s, "why": "termín už existuje"})
            continue
        start_t, end_t = _PERIODS_BY_NUMBER[hn]
        cap = max(1, int(s.get("capacity") or 4))
        try:
            async with conn.transaction():  # savepoint – chyba nezruší celý review
                await conn.execute(
                    """
                    INSERT INTO internal.open_hours
                        (weekday, date, hour_number, start_time, end_time,
                         capacity, note, supervisor)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    d.strftime("%A"), d, hn, start_t, end_t, cap,
                    s.get("reason") or "Návrh plánovače hodin", sup,
                )
            created.append({"date": s["date"], "hour_number": hn, "supervisor": sup})
        except asyncpg.UniqueViolationError:
            skipped.append({"slot": s, "why": "duplicita"})
    return {"created": created, "skipped": skipped}


async def _review(proposal_id: int, *, approve: bool, note: Optional[str], user: User):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            prop = await get_proposal_for_update(conn, proposal_id)
            if prop is None:
                raise HTTPException(404, "Návrh neexistuje.")
            if prop["module"] != MODULE:
                raise HTTPException(404, "Návrh neexistuje.")
            if prop["status"] != "pending":
                raise HTTPException(409, f"Návrh už je {prop['status']}.")
            applied = await _apply(conn, prop) if approve else None
            return await mark_reviewed(
                conn, proposal_id=proposal_id, reviewer=user,
                approve=approve, note=note, applied=applied,
            )


@router_agent_review.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: int,
    body: ReviewIn = ReviewIn(),
    user: User = Depends(require_permission("agent.proposal:review")),
):
    return await _review(proposal_id, approve=True, note=body.note, user=user)


@router_agent_review.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: int,
    body: ReviewIn = ReviewIn(),
    user: User = Depends(require_permission("agent.proposal:review")),
):
    return await _review(proposal_id, approve=False, note=body.note, user=user)


@router_agent_review.get("/reports", dependencies=_REPORT)
async def get_reports(limit: int = Query(24, ge=1, le=200)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, period, summary,
                   to_char(generated_at, 'YYYY-MM-DD HH24:MI') AS generated_at
            FROM agent.reports
            WHERE module = $1
            ORDER BY period DESC
            LIMIT $2
            """,
            MODULE, limit,
        )
    return [dict(r) for r in rows]


@router_agent_review.get("/reports/{report_id}", dependencies=_REPORT)
async def get_report(report_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, module, period, payload, summary,
                   to_char(generated_at, 'YYYY-MM-DD HH24:MI') AS generated_at
            FROM agent.reports WHERE id = $1 AND module = $2
            """,
            report_id, MODULE,
        )
    if row is None:
        raise HTTPException(404, "Report neexistuje.")
    d = dict(row)
    if isinstance(d.get("payload"), str):
        d["payload"] = json.loads(d["payload"])
    return d


@router_agent_review.get("/runs", dependencies=_REVIEW)
async def get_runs(limit: int = Query(50, ge=1, le=500)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS at,
                   action, target_type, target_id, detail
            FROM auth.audit_log
            WHERE action LIKE 'access.agent.%' AND target_type = 'agent_run'
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    out = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("detail"), str):
            d["detail"] = json.loads(d["detail"])
        out.append(d)
    return out
