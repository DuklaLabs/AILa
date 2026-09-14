"""Read-only client for the DuklaMaps timetable database.

DuklaMaps already scrapes Bakaláři (real REST API, not HTML) and keeps its
own Postgres continuously in sync — see its `Sync_Doc.py`/`dataconnector.py`.
Re-scraping the same data into `internal.lesson_hours` here (the old
`scrape_classes.py`, now deleted) duplicated that work with a much more
fragile HTML scraper and pointed at a DB that no longer exists. Instead this
module reads DuklaMaps' `timetable_actual`/`timetable_permanent` live over a
second, separate asyncpg pool — it's a different database on a different
host, so it can't share `ailacore.db`'s pool.

Connects as `access_request_ro`, a role scoped to SELECT only on the
timetable tables (see the migration note in this repo's chat history / ops
notes for the exact GRANTs) — this service has no business writing into
DuklaMaps' DB.
"""
import os
from datetime import date
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None

# DuklaMaps day_index/hour_index are the raw Bakalari period numbers, the
# same numbering AccessRequest already uses for internal.open_hours.hour_number
# (see PERIODS in open_hours.py) — no translation needed between the two.
_WEEKDAY_NAMES = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek"]


def _connection_kwargs() -> dict:
    return {
        "user": os.getenv("TIMETABLE_DB_USER", "access_request_ro"),
        "password": os.getenv("TIMETABLE_DB_PASSWORD", ""),
        "database": os.getenv("TIMETABLE_DB_NAME", "duklamaps"),
        "host": os.getenv("TIMETABLE_DB_HOST", "host.docker.internal"),
        "port": int(os.getenv("TIMETABLE_DB_PORT", "5433")),
    }


async def get_timetable_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(**_connection_kwargs(), min_size=1, max_size=3)
    return _pool


async def close_timetable_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _monday_of(d: date) -> date:
    return d.fromordinal(d.toordinal() - d.weekday())


_WEEKLY_TABLES = ("timetable_actual", "timetable_next")


async def find_class_lesson(class_abbrev: str, lesson_date: date, hour_number: int) -> Optional[dict]:
    """Looks up whether `class_abbrev` has a regular lesson on `lesson_date`
    at period `hour_number`, per DuklaMaps. Open-hour bookings in
    AccessRequest are made a week ahead, so the relevant week is usually
    `timetable_next` (DuklaMaps' upcoming-week table, already carrying any
    confirmed substitutions), not `timetable_actual` (the current week) —
    both are tried by matching `week_date`, in that order, before falling
    back to `timetable_permanent` (the baseline schedule, no substitutions)
    for dates further out than DuklaMaps has synced yet.

    Returns None on a weekend or when the class has no lesson at that slot.
    """
    day_index = lesson_date.weekday()
    if day_index > 4:
        return None

    pool = await get_timetable_pool()
    monday = _monday_of(lesson_date)
    async with pool.acquire() as conn:
        row = None
        for table in _WEEKLY_TABLES:
            row = await conn.fetchrow(
                f"""
                SELECT t.subject_name, t.teacher_name, t.teacher_id
                FROM {table} t
                WHERE t.entity_type = 'classes' AND t.class_abbrev = $1
                  AND t.week_date = $2 AND t.day_index = $3 AND t.hour_index = $4
                LIMIT 1
                """,
                class_abbrev,
                monday,
                day_index,
                hour_number,
            )
            if row is not None:
                break
        if row is None:
            row = await conn.fetchrow(
                """
                SELECT t.subject_name, t.teacher_name, t.teacher_id
                FROM timetable_permanent t
                WHERE t.entity_type = 'classes' AND t.class_abbrev = $1
                  AND t.day_index = $2 AND t.hour_index = $3
                LIMIT 1
                """,
                class_abbrev,
                day_index,
                hour_number,
            )
        if row is None:
            return None

    return {
        "weekday": _WEEKDAY_NAMES[day_index],
        "class_name": class_abbrev,
        "subject_name": row["subject_name"] or "?",
        "teacher_name": row["teacher_name"] or "?",
        "teacher_id": row["teacher_id"],
        "hour_number": hour_number,
    }


async def find_teacher_email(teacher_id: Optional[str]) -> Optional[str]:
    """Resolves a DuklaMaps teacher (Bakalari short code, e.g. 'U0035') to
    an email address. Returns None if there's no usable email on file —
    caller must treat that as fail-closed (reject the booking), distinct
    from this function *raising* (OSError/asyncpg.PostgresError), which the
    caller fail-opens on (DuklaMaps being unreachable is not the same thing
    as "this teacher has no email")."""
    if not teacher_id:
        return None
    pool = await get_timetable_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT email FROM teachers WHERE id = $1 AND deleted = FALSE",
            teacher_id,
        )
    if row is None:
        return None
    email = (row["email"] or "").strip()
    return email if email and "@" in email else None
