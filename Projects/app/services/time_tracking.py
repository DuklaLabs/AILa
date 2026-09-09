"""Time tracking: nativní stopky (Start/Stop) + ruční zápis.

Max jedny běžící stopky na uživatele (parciální unique index
`uq_time_entries_running` v migraci 0016).
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from ailacore.db import get_pool
from ailacore.models import User

from app.services.base import require

_ENTRY_COLS = (
    "id, task_id, user_id, started_at, ended_at, minutes, source, note, created_at"
)


async def list_time_entries(
    user: User,
    *,
    task_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
) -> list[dict]:
    """Bez `target_user_id` (nebo == vlastní) stačí `projects.time:log`;
    cizí čas vyžaduje `projects.time:read_all`."""
    if target_user_id is not None and target_user_id != user.id:
        await require(user, "projects.time:read_all")
    else:
        await require(user, "projects.time:log")
        target_user_id = target_user_id or user.id

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {_ENTRY_COLS} FROM projects.time_entries
            WHERE ($1::int IS NULL OR task_id = $1)
              AND ($2::int IS NULL OR user_id = $2)
            ORDER BY started_at DESC, id DESC
            """,
            task_id,
            target_user_id,
        )
    return [dict(r) for r in rows]


async def running_timer(user: User) -> Optional[dict]:
    await require(user, "projects.time:log")
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {_ENTRY_COLS} FROM projects.time_entries "
            f"WHERE user_id = $1 AND ended_at IS NULL",
            user.id,
        )
    return dict(row) if row else None


async def start_timer(user: User, task_id: int, note: Optional[str] = None) -> dict:
    await require(user, "projects.time:log")
    pool = await get_pool()
    async with pool.acquire() as conn:
        if not await conn.fetchval("SELECT 1 FROM projects.tasks WHERE id = $1", task_id):
            raise HTTPException(404, "Úkol neexistuje.")
        if await conn.fetchval(
            "SELECT 1 FROM projects.time_entries WHERE user_id = $1 AND ended_at IS NULL",
            user.id,
        ):
            raise HTTPException(409, "Už máš běžící stopky – nejdřív je zastav.")
        row = await conn.fetchrow(
            f"""
            INSERT INTO projects.time_entries (task_id, user_id, started_at, source, note)
            VALUES ($1, $2, NOW(), 'timer', $3)
            RETURNING {_ENTRY_COLS}
            """,
            task_id,
            user.id,
            note,
        )
    return dict(row)


async def stop_timer(user: User, entry_id: Optional[int] = None) -> dict:
    await require(user, "projects.time:log")
    pool = await get_pool()
    async with pool.acquire() as conn:
        running = await conn.fetchrow(
            "SELECT id, started_at FROM projects.time_entries "
            "WHERE user_id = $1 AND ended_at IS NULL "
            "  AND ($2::int IS NULL OR id = $2)",
            user.id,
            entry_id,
        )
        if running is None:
            raise HTTPException(404, "Žádné běžící stopky k zastavení.")
        row = await conn.fetchrow(
            f"""
            UPDATE projects.time_entries
            SET ended_at = NOW(),
                minutes = GREATEST(1, ROUND(EXTRACT(EPOCH FROM (NOW() - started_at)) / 60)::int)
            WHERE id = $1
            RETURNING {_ENTRY_COLS}
            """,
            running["id"],
        )
    return dict(row)


async def add_manual_entry(
    user: User,
    task_id: int,
    *,
    minutes: int,
    started_at: Optional[datetime] = None,
    note: Optional[str] = None,
) -> dict:
    await require(user, "projects.time:log")
    if minutes is None or minutes <= 0:
        raise HTTPException(422, "minutes musí být kladné číslo.")
    start = started_at or (datetime.utcnow() - timedelta(minutes=minutes))
    end = start + timedelta(minutes=minutes)
    pool = await get_pool()
    async with pool.acquire() as conn:
        if not await conn.fetchval("SELECT 1 FROM projects.tasks WHERE id = $1", task_id):
            raise HTTPException(404, "Úkol neexistuje.")
        row = await conn.fetchrow(
            f"""
            INSERT INTO projects.time_entries
                (task_id, user_id, started_at, ended_at, minutes, source, note)
            VALUES ($1, $2, $3, $4, $5, 'manual', $6)
            RETURNING {_ENTRY_COLS}
            """,
            task_id,
            user.id,
            start,
            end,
            int(minutes),
            note,
        )
    return dict(row)
