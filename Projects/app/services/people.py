"""Roster uživatelů pro výběr řešitele / spolupracovníků v UI."""
from typing import Optional

from ailacore.db import get_pool
from ailacore.models import User

from app.services.base import require


async def list_people(user: User, *, q: Optional[str] = None) -> list[dict]:
    await require(user, "projects.task:read")
    like = f"%{q.strip()}%" if q and q.strip() else None
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, username, full_name
            FROM auth.users
            WHERE is_active
              AND ($1::text IS NULL OR username ILIKE $1 OR full_name ILIKE $1)
            ORDER BY full_name NULLS LAST, username
            LIMIT 500
            """,
            like,
        )
    return [
        {"id": r["id"], "username": r["username"], "name": r["full_name"] or r["username"]}
        for r in rows
    ]
