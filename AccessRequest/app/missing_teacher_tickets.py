"""Deduplicated tickets for DuklaMaps teachers with no usable email on
file — written by bookings.py when a booking is rejected for exactly that
reason, read/resolved by staff via the API in excuse_requests.py."""
from typing import Optional

from ailacore.db import get_pool


async def record_missing_teacher(teacher_id: str, teacher_name: Optional[str]) -> None:
    """Upsert, not insert: repeated failed lookups for the same teacher bump
    attempts_count/last_seen instead of piling up duplicate rows. A fresh
    sighting also reopens a previously-resolved ticket — if bookings are
    still hitting it, the underlying gap in DuklaMaps wasn't actually
    fixed."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO internal.missing_teacher_tickets (teacher_id, teacher_name)
            VALUES ($1, $2)
            ON CONFLICT (teacher_id) DO UPDATE SET
                last_seen = NOW(),
                attempts_count = internal.missing_teacher_tickets.attempts_count + 1,
                teacher_name = EXCLUDED.teacher_name,
                resolved = FALSE,
                resolved_at = NULL,
                resolved_by = NULL
            """,
            teacher_id,
            teacher_name,
        )


async def list_missing_teacher_tickets(include_resolved: bool = False) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, teacher_id, teacher_name, first_seen, last_seen,
                   attempts_count, resolved, resolved_at, resolved_by
            FROM internal.missing_teacher_tickets
            {"" if include_resolved else "WHERE resolved = FALSE"}
            ORDER BY last_seen DESC
            """
        )
    return [dict(r) for r in rows]


async def resolve_missing_teacher_ticket(ticket_id: int, resolved_by: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE internal.missing_teacher_tickets
            SET resolved = TRUE, resolved_at = NOW(), resolved_by = $2
            WHERE id = $1
            """,
            ticket_id,
            resolved_by,
        )
    return result != "UPDATE 0"
