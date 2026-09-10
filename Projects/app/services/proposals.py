"""Návrhy změn od AI (§21 databanky).

Nevratná / bezpečnostně citlivá operace přes MCP nevytvoří přímou mutaci, ale
`projects.proposals` řádek ve stavu `pending`. Člověk s oprávněním
`projects.proposal:review` ho v SPA schválí nebo zamítne; teprve schválení
provede skutečnou změnu. Hranice „přímo vs. návrh“ je `classify_change` a je
společná pro MCP i REST.
"""
import json
from typing import Optional

from fastapi import HTTPException

from ailacore.audit import record_audit
from ailacore.db import get_pool
from ailacore.models import User

from app.services.base import PROJECT_STATUSES, require, validate_enum

# operace, které přes MCP jdou výhradně přes návrh ke schválení
PROPOSAL_KINDS = {
    "task.delete",
    "project.update",
    "finance.update",
    "project.lifecycle",
}

_PROPOSAL_COLS = (
    "id, requested_by_user_id, origin, kind, target_type, target_id, "
    "payload, summary, status, reviewed_by_user_id, reviewed_at, "
    "review_note, created_at"
)


def classify_change(kind: str) -> str:
    """'proposal' = musí projít schválením člověka, 'direct' = smí se provést hned
    (pod běžným RBAC uživatele)."""
    return "proposal" if kind in PROPOSAL_KINDS else "direct"


def _row(r) -> dict:
    d = dict(r)
    if isinstance(d.get("payload"), str):
        d["payload"] = json.loads(d["payload"])
    return d


async def create_proposal(
    user: User,
    *,
    kind: str,
    target_type: Optional[str],
    target_id: Optional[int],
    payload: dict,
    summary: Optional[str] = None,
    origin: str = "mcp",
) -> dict:
    await require(user, "projects.ai:use")
    if classify_change(kind) != "proposal":
        raise HTTPException(422, f"Operace {kind!r} není typu návrh (provádí se přímo).")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                f"""
                INSERT INTO projects.proposals
                    (requested_by_user_id, origin, kind, target_type, target_id,
                     payload, summary, status)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, 'pending')
                RETURNING {_PROPOSAL_COLS}
                """,
                user.id,
                origin,
                kind,
                target_type,
                target_id,
                json.dumps(payload or {}, ensure_ascii=False, default=str),
                summary,
            )
            await record_audit(
                conn,
                actor=user,
                action="projects.proposal.create",
                target_type="proposal",
                target_id=str(row["id"]),
                detail={"origin": origin, "kind": kind, "target": [target_type, target_id]},
            )
    return _row(row)


async def list_proposals(user: User, *, status: str = "pending") -> list[dict]:
    await require(user, "projects.proposal:review")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {_PROPOSAL_COLS} FROM projects.proposals
            WHERE ($1::text IS NULL OR status = $1)
            ORDER BY created_at DESC, id DESC
            """,
            status or None,
        )
    return [_row(r) for r in rows]


async def review_proposal(
    user: User, proposal_id: int, *, approve: bool, note: Optional[str] = None
) -> dict:
    await require(user, "projects.proposal:review")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            prop = await conn.fetchrow(
                f"SELECT {_PROPOSAL_COLS} FROM projects.proposals WHERE id = $1 FOR UPDATE",
                proposal_id,
            )
            if prop is None:
                raise HTTPException(404, "Návrh neexistuje.")
            if prop["status"] != "pending":
                raise HTTPException(409, f"Návrh už je {prop['status']}.")

            applied = None
            if approve:
                applied = await _apply_proposal(conn, _row(prop))

            row = await conn.fetchrow(
                f"""
                UPDATE projects.proposals
                SET status = $2, reviewed_by_user_id = $3, reviewed_at = NOW(),
                    review_note = $4
                WHERE id = $1
                RETURNING {_PROPOSAL_COLS}
                """,
                proposal_id,
                "approved" if approve else "rejected",
                user.id,
                note,
            )
            await record_audit(
                conn,
                actor=user,
                action="projects.proposal." + ("approve" if approve else "reject"),
                target_type="proposal",
                target_id=str(proposal_id),
                detail={"kind": prop["kind"], "applied": applied, "note": note},
            )
    return {**_row(row), "applied": applied}


# --- provedení schváleného návrhu (raw SQL; člověk už dal souhlas) ---------

_PROJECT_UPDATE_FIELDS = {
    "name", "description", "started_on", "due_on", "baseline_due_on", "lead_user_id",
}


async def _apply_proposal(conn, prop: dict) -> dict:
    kind = prop["kind"]
    tid = prop["target_id"]
    payload = prop["payload"] or {}

    if kind == "task.delete":
        res = await conn.execute("DELETE FROM projects.tasks WHERE id = $1", tid)
        if res == "DELETE 0":
            raise HTTPException(404, "Cílový úkol už neexistuje.")
        return {"deleted_task": tid}

    if kind == "project.update":
        changes = {k: v for k, v in payload.items() if k in _PROJECT_UPDATE_FIELDS}
        if not changes:
            raise HTTPException(422, "Návrh neobsahuje žádné platné pole projektu.")
        set_sql = ", ".join(f"{k} = ${i}" for i, k in enumerate(changes, start=2))
        upd = await conn.fetchval(
            f"UPDATE projects.projects SET {set_sql}, updated_at = NOW() "
            f"WHERE id = $1 RETURNING id",
            tid, *changes.values(),
        )
        if upd is None:
            raise HTTPException(404, "Cílový projekt už neexistuje.")
        return {"updated_project": tid, "fields": list(changes)}

    if kind == "finance.update":
        if prop["target_type"] == "task":
            val = payload.get("actual_cost_czk")
            upd = await conn.fetchval(
                "UPDATE projects.tasks SET actual_cost_czk = $2, updated_at = NOW() "
                "WHERE id = $1 RETURNING id",
                tid, val,
            )
            if upd is None:
                raise HTTPException(404, "Cílový úkol už neexistuje.")
            return {"updated_task_actual_cost": tid, "value": val}
        val = payload.get("planned_budget_czk")
        upd = await conn.fetchval(
            "UPDATE projects.projects SET planned_budget_czk = $2, updated_at = NOW() "
            "WHERE id = $1 RETURNING id",
            tid, val,
        )
        if upd is None:
            raise HTTPException(404, "Cílový projekt už neexistuje.")
        return {"updated_project_budget": tid, "value": val}

    if kind == "project.lifecycle":
        if payload.get("delete"):
            res = await conn.execute("DELETE FROM projects.projects WHERE id = $1", tid)
            if res == "DELETE 0":
                raise HTTPException(404, "Cílový projekt už neexistuje.")
            return {"deleted_project": tid}
        status = payload.get("status")
        validate_enum(status, PROJECT_STATUSES, "status")
        upd = await conn.fetchval(
            "UPDATE projects.projects SET status = $2, updated_at = NOW() "
            "WHERE id = $1 RETURNING id",
            tid, status,
        )
        if upd is None:
            raise HTTPException(404, "Cílový projekt už neexistuje.")
        return {"project_status": [tid, status]}

    raise HTTPException(422, f"Neznámý typ návrhu: {kind}")
