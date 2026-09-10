"""Sdílené agregační dotazy nad daty modulu AccessRequest (`internal.*`).

Používají je agenti (měsíční report, hlídač předmětů, plánovač hodin) a
klidně i budoucí dashboard – ať se stejné SQL nepíše na pěti místech.
Vrací čistá data (dict/list), žádný render. Kde je potřeba předmět k hodině,
si ho volající doplní přes `ailacore.dukla` (tenhle modul zůstává čistě SQL).

Rozsah se všude zadává jako polouzavřený interval `[start, end)` dat.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from .db import get_pool


async def _fetch(sql: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(sql, *args)


async def _fetchrow(sql: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(sql, *args)


async def open_hours_occupancy(start: date, end: date) -> dict:
    """Obsazenost otevřených hodin v intervalu `[start, end)`."""
    row = await _fetchrow(
        """
        WITH oh AS (
            SELECT o.id, o.capacity,
                   (SELECT COUNT(*) FROM internal.bookings b
                     WHERE b.open_hour_id = o.id) AS booked
            FROM internal.open_hours o
            WHERE o.date >= $1 AND o.date < $2
        )
        SELECT
            COUNT(*)                                             AS slots,
            COALESCE(SUM(capacity), 0)                           AS capacity_total,
            COALESCE(SUM(booked), 0)                             AS booked_total,
            COUNT(*) FILTER (WHERE booked >= capacity AND capacity > 0) AS full_slots,
            COUNT(*) FILTER (WHERE booked = 0)                   AS empty_slots,
            CASE WHEN COALESCE(SUM(capacity), 0) > 0
                 THEN ROUND(SUM(booked)::numeric / SUM(capacity), 3)
                 ELSE 0 END                                      AS fill_ratio
        FROM oh
        """,
        start, end,
    )
    return dict(row) if row else {}


async def booking_decisions(start: date, end: date) -> dict:
    """Počty rozhodnutí o uvolnění pro rezervace na hodiny v `[start, end)`."""
    row = await _fetchrow(
        """
        SELECT
            COUNT(*)                                   AS bookings,
            COUNT(*) FILTER (WHERE b.approved IS TRUE)  AS approved,
            COUNT(*) FILTER (WHERE b.approved IS FALSE) AS denied,
            COUNT(*) FILTER (WHERE b.approved IS NULL)  AS undecided
        FROM internal.bookings b
        JOIN internal.open_hours o ON o.id = b.open_hour_id
        WHERE o.date >= $1 AND o.date < $2
        """,
        start, end,
    )
    return dict(row) if row else {}


async def attendance_stats(start: date, end: date) -> dict:
    """Docházka u uvolněných (`approved IS TRUE`) rezervací v `[start, end)`."""
    row = await _fetchrow(
        """
        SELECT
            COUNT(*)                                    AS approved,
            COUNT(*) FILTER (WHERE b.attended IS TRUE)   AS came,
            COUNT(*) FILTER (WHERE b.attended IS FALSE)  AS no_show,
            COUNT(*) FILTER (WHERE b.attended IS NULL)   AS unchecked,
            CASE WHEN COUNT(*) FILTER (WHERE b.attended IS NOT NULL) > 0
                 THEN ROUND(
                     COUNT(*) FILTER (WHERE b.attended IS FALSE)::numeric
                     / COUNT(*) FILTER (WHERE b.attended IS NOT NULL), 3)
                 ELSE 0 END                             AS no_show_ratio
        FROM internal.bookings b
        JOIN internal.open_hours o ON o.id = b.open_hour_id
        WHERE o.date >= $1 AND o.date < $2 AND b.approved IS TRUE
        """,
        start, end,
    )
    return dict(row) if row else {}


async def released_bookings(start: date, end: date) -> list[dict]:
    """Uvolněné rezervace v `[start, end)` s třídou studenta – volající si
    doplní předmět přes `ailacore.dukla.class_teachers`."""
    rows = await _fetch(
        """
        SELECT b.id, b.attended,
               s.student_id, s.first_name, s.last_name, s.class_group,
               o.date, o.hour_number
        FROM internal.bookings b
        JOIN internal.students s ON s.student_id = b.student_id
        JOIN internal.open_hours o ON o.id = b.open_hour_id
        WHERE o.date >= $1 AND o.date < $2 AND b.approved IS TRUE
        ORDER BY o.date, o.hour_number
        """,
        start, end,
    )
    return [dict(r) for r in rows]


async def upcoming_bookings(today: Optional[date] = None) -> list[dict]:
    """Nadcházející rezervace (od dneška dál) – pro hlídač předmětů a asistenta.
    `approved`: NULL/TRUE/FALSE."""
    rows = await _fetch(
        """
        SELECT b.id, b.approved, b.attended,
               s.student_id, s.first_name, s.last_name, s.class_group, s.email,
               s.release_teacher_ok, s.release_coord_ok,
               o.id AS open_hour_id, o.date, o.hour_number, o.start_time,
               o.end_time, o.note, o.supervisor, o.capacity,
               (SELECT COUNT(*) FROM internal.bookings bb
                 WHERE bb.open_hour_id = o.id) AS booked_count
        FROM internal.bookings b
        JOIN internal.students s ON s.student_id = b.student_id
        JOIN internal.open_hours o ON o.id = b.open_hour_id
        WHERE o.date >= COALESCE($1, CURRENT_DATE)
        ORDER BY o.date, o.hour_number, s.last_name
        """,
        today,
    )
    return [dict(r) for r in rows]


async def student_release_history(student_ids: list[int]) -> dict[int, dict]:
    """Pro dané studenty souhrn dosavadních uvolnění: kolikrát povoleno /
    zamítnuto a jaká byla docházka (přišel / nepřišel)."""
    if not student_ids:
        return {}
    rows = await _fetch(
        """
        SELECT b.student_id,
               COUNT(*) FILTER (WHERE b.approved IS TRUE)  AS approved,
               COUNT(*) FILTER (WHERE b.approved IS FALSE) AS denied,
               COUNT(*) FILTER (WHERE b.approved IS TRUE AND b.attended IS TRUE)  AS came,
               COUNT(*) FILTER (WHERE b.approved IS TRUE AND b.attended IS FALSE) AS no_show
        FROM internal.bookings b
        WHERE b.student_id = ANY($1::int[])
        GROUP BY b.student_id
        """,
        student_ids,
    )
    return {r["student_id"]: dict(r) for r in rows}


async def new_registrations(start: date, end: date) -> int:
    row = await _fetchrow(
        """
        SELECT COUNT(*) AS n
        FROM internal.students s
        JOIN auth.users u ON u.id = s.user_id
        WHERE u.role = 'student'
          AND s.registration_date >= $1 AND s.registration_date < $2
        """,
        start, end,
    )
    return int(row["n"]) if row else 0


async def pending_release_consents() -> list[dict]:
    """Studenti, u kterých ještě není souhlas třídního I koordinátora."""
    rows = await _fetch(
        """
        SELECT s.student_id, s.first_name, s.last_name, s.class_group,
               s.release_teacher_ok, s.release_coord_ok, s.release_class_teacher
        FROM internal.students s
        JOIN auth.users u ON u.id = s.user_id
        WHERE u.role = 'student'
          AND NOT (s.release_teacher_ok IS TRUE AND s.release_coord_ok IS TRUE)
        ORDER BY s.student_id DESC
        """
    )
    return [dict(r) for r in rows]


async def failed_mails(start: date, end: date, limit: int = 20) -> dict:
    """Selhané odchozí e-maily v `[start, end)` z `messaging.mail_log`."""
    row = await _fetchrow(
        """
        SELECT COUNT(*) AS n
        FROM messaging.mail_log
        WHERE created_at >= $1 AND created_at < $2 AND status = 'ERROR'
        """,
        start, end,
    )
    samples = await _fetch(
        """
        SELECT created_at, subject, error, to_addrs, source
        FROM messaging.mail_log
        WHERE created_at >= $1 AND created_at < $2 AND status = 'ERROR'
        ORDER BY created_at DESC
        LIMIT $3
        """,
        start, end, limit,
    )
    return {"count": int(row["n"]) if row else 0,
            "samples": [dict(r) for r in samples]}


async def open_slots_between(start: date, end: date) -> list[dict]:
    """Otevřené hodiny s datem v `[start, end)` – aby plánovač nenavrhoval
    duplicity (UNIQUE (date, hour_number))."""
    rows = await _fetch(
        """
        SELECT id, date, hour_number, capacity, supervisor, note
        FROM internal.open_hours
        WHERE date >= $1 AND date < $2
        ORDER BY date, hour_number
        """,
        start, end,
    )
    return [dict(r) for r in rows]


async def demand_by_slot(since_days: int = 90) -> list[dict]:
    """Historická poptávka podle (den v týdnu, vyučovací hodina). `weekday`
    je 0=pondělí … 6=neděle. Pořadí od nejvytíženějších."""
    rows = await _fetch(
        """
        WITH oh AS (
            SELECT o.id, o.hour_number,
                   ((EXTRACT(DOW FROM o.date)::int + 6) % 7) AS weekday,
                   o.capacity,
                   (SELECT COUNT(*) FROM internal.bookings b
                     WHERE b.open_hour_id = o.id) AS booked
            FROM internal.open_hours o
            WHERE o.date >= CURRENT_DATE - ($1::int) AND o.hour_number IS NOT NULL
        )
        SELECT weekday, hour_number,
               COUNT(*)                               AS slots_opened,
               ROUND(AVG(booked), 2)                  AS avg_booked,
               COALESCE(MAX(booked), 0)               AS max_booked,
               CASE WHEN SUM(capacity) > 0
                    THEN ROUND(SUM(booked)::numeric / SUM(capacity), 3)
                    ELSE 0 END                        AS fill_ratio
        FROM oh
        GROUP BY weekday, hour_number
        ORDER BY avg_booked DESC, fill_ratio DESC
        """,
        since_days,
    )
    return [dict(r) for r in rows]


async def agent_flag_counts(start: date, end: date) -> list[dict]:
    """Kolik vlajek/návrhů agenti vytvořili v `[start, end)`, podle druhu."""
    rows = await _fetch(
        """
        SELECT kind, status, COUNT(*) AS n
        FROM agent.proposals
        WHERE module = 'access'
          AND created_at >= $1 AND created_at < $2
        GROUP BY kind, status
        ORDER BY n DESC
        """,
        start, end,
    )
    return [dict(r) for r in rows]
