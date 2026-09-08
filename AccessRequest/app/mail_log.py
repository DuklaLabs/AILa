"""Čtení logu odeslaných e-mailů (messaging.mail_log – zapisuje Messenger).

    GET /api/mail-log?limit=100&status=ERROR&to=nekdo@spssecb.cz&q=uvoln

Admin/staff. Slouží k ověření, že (a kdy) mail skutečně odešel.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ailacore.auth import require_role
from ailacore.db import get_pool

router_mail_log = APIRouter(tags=["MailLog"])


@router_mail_log.get(
    "/api/mail-log",
    dependencies=[Depends(require_role("admin", "staff"))],
)
async def mail_log(
    limit: int = Query(100, ge=1, le=1000),
    status: str | None = Query(None),
    to: str | None = Query(None),
    q: str | None = Query(None, description="hledání v předmětu"),
):
    where = ["TRUE"]
    args: list = []
    if status:
        args.append(status.upper())
        where.append(f"status = ${len(args)}")
    if to:
        args.append(to)
        where.append(f"${len(args)} = ANY(to_addrs)")
    if q:
        args.append(f"%{q}%")
        where.append(f"subject ILIKE ${len(args)}")
    args.append(limit)

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                   backend, to_addrs, cc_addrs, subject, status, error,
                   delivered_to, redirected_from, has_ics, body_bytes, source
            FROM messaging.mail_log
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT ${len(args)}
            """,
            *args,
        )
        stats = await conn.fetch(
            "SELECT status, COUNT(*) AS n FROM messaging.mail_log GROUP BY status"
        )
    return {
        "rows": [dict(r) for r in rows],
        "counts": {r["status"]: r["n"] for r in stats},
    }
