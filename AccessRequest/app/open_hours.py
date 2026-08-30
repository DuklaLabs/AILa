import datetime

import asyncpg
from fastapi import APIRouter, Depends, Form, HTTPException, Query

from ailacore.auth import require_role
from ailacore.db import get_pool

from app.dukla_db import (
    blocked_supervisors,
    diagnose as dukla_diagnose,
    fetch_supervisions,
    supervisor_names,
)

router = APIRouter(prefix="/api/open-hours", tags=["Open Hours"])

_STAFF_ONLY = [Depends(require_role("admin", "staff"))]

# Fixed bell schedule (period number -> start/end time) so every open hour
# lines up with a real school period and can be rendered as a timetable
# grid instead of a flat list of arbitrary time ranges.
PERIODS = [
    (0, datetime.time(7, 10), datetime.time(7, 55)),
    (1, datetime.time(8, 0), datetime.time(8, 45)),
    (2, datetime.time(8, 50), datetime.time(9, 35)),
    (3, datetime.time(9, 55), datetime.time(10, 40)),
    (4, datetime.time(10, 45), datetime.time(11, 30)),
    (5, datetime.time(11, 40), datetime.time(12, 25)),
    (6, datetime.time(12, 30), datetime.time(13, 15)),
    (7, datetime.time(13, 20), datetime.time(14, 5)),
    (8, datetime.time(14, 10), datetime.time(14, 55)),
    (9, datetime.time(15, 0), datetime.time(15, 45)),
    (10, datetime.time(15, 50), datetime.time(16, 35)),
]
_PERIODS_BY_NUMBER = {number: (start, end) for number, start, end in PERIODS}


def _clean_supervisor(value):
    """Normalise the supervisor field: a free hour can be assigned to one or
    more dozors, sent from the grid as a comma-separated list."""
    if not value:
        return None
    names = [part.strip() for part in value.split(",") if part.strip()]
    return ", ".join(names) or None


def _require_supervisor(supervisor_csv):
    """A free hour must have at least one dozor — but only enforce it when
    there are supervisors to choose from (DUKLA_SUPERVISORS set)."""
    if supervisor_names() and not supervisor_csv:
        raise HTTPException(
            status_code=400,
            detail="Volná hodina musí mít aspoň jednoho dozora.",
        )


async def _reject_if_supervisor_teaching(supervisor_csv, date_obj, hour_number):
    """A dozor who already has their own lesson at this day+period (per the
    duklamaps timetable) can't also be the free-hour supervisor then."""
    if not supervisor_csv:
        return
    names = [p.strip() for p in supervisor_csv.split(",") if p.strip()]
    blocked = await blocked_supervisors(date_obj, hour_number)
    clash = [n for n in names if n in blocked]
    if clash:
        raise HTTPException(
            status_code=400,
            detail=f"{', '.join(clash)} má v tuto hodinu vlastní výuku, nemůže být dozorem.",
        )


@router.get("/periods")
async def list_periods():
    return [
        {"hour_number": number, "start_time": start.isoformat(), "end_time": end.isoformat()}
        for number, start, end in PERIODS
    ]


# ----------------------------------------------------------------------
# CREATE / ADD OPEN HOURS (staff/admin only)
# ----------------------------------------------------------------------

@router.post("/add", dependencies=_STAFF_ONLY)
async def add_open_hours(
    date: str = Form(...),
    hour_number: int = Form(...),
    capacity: int = Form(...),
    note: str = Form(None),
    supervisor: str = Form(None),
):
    if hour_number not in _PERIODS_BY_NUMBER:
        raise HTTPException(status_code=400, detail="Neplatná vyučovací hodina.")

    date_obj = datetime.date.fromisoformat(date)
    start_time_obj, end_time_obj = _PERIODS_BY_NUMBER[hour_number]
    supervisor = _clean_supervisor(supervisor)
    _require_supervisor(supervisor)
    await _reject_if_supervisor_teaching(supervisor, date_obj, hour_number)

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO internal.open_hours
                    (weekday, date, hour_number, start_time, end_time, capacity, note, supervisor)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                date_obj.strftime("%A"),
                date_obj,
                hour_number,
                start_time_obj,
                end_time_obj,
                capacity,
                note,
                supervisor,
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=409,
                detail="Na tento termín už otevřená hodina existuje.",
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "msg": "Hodiny byly uloženy."}


# ----------------------------------------------------------------------
# UPDATE OPEN HOUR (staff/admin only) — capacity / note
# ----------------------------------------------------------------------

@router.patch("/{id}", dependencies=_STAFF_ONLY)
async def update_open_hours(
    id: int,
    capacity: int = Form(None),
    note: str = Form(None),
    supervisor: str = Form(None),
):
    if capacity is not None and capacity < 1:
        raise HTTPException(status_code=400, detail="Kapacita musí být alespoň 1.")

    supervisor = _clean_supervisor(supervisor)
    _require_supervisor(supervisor)

    pool = await get_pool()
    async with pool.acquire() as conn:
        base = await conn.fetchrow(
            "SELECT date, hour_number FROM internal.open_hours WHERE id = $1", id
        )
        if base is None:
            raise HTTPException(status_code=404, detail="Termín neexistuje.")
        if base["hour_number"] is not None:
            await _reject_if_supervisor_teaching(
                supervisor, base["date"], base["hour_number"]
            )

        async with conn.transaction():
            slot = await conn.fetchrow(
                "SELECT id, capacity FROM internal.open_hours WHERE id = $1 FOR UPDATE",
                id,
            )
            if slot is None:
                raise HTTPException(status_code=404, detail="Termín neexistuje.")

            booked_count = await conn.fetchval(
                "SELECT COUNT(*) FROM internal.bookings WHERE open_hour_id = $1",
                id,
            )
            if capacity is not None and capacity < booked_count:
                raise HTTPException(
                    status_code=400,
                    detail=f"Kapacita nemůže být nižší než počet rezervací ({booked_count}).",
                )

            await conn.execute(
                """
                UPDATE internal.open_hours
                SET capacity = COALESCE($2, capacity),
                    note = $3,
                    supervisor = $4,
                    updated_at = NOW()
                WHERE id = $1
                """,
                id,
                capacity,
                note,
                supervisor,
            )
    return {"status": "ok", "msg": "Změny byly uloženy."}


# ----------------------------------------------------------------------
# WHO BOOKED A GIVEN OPEN HOUR (staff/admin only) — feeds the "this week"
# overview: click a slot to see who is coming and from which class.
# ----------------------------------------------------------------------

@router.get("/{id}/bookings", dependencies=_STAFF_ONLY)
async def open_hour_bookings(id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.first_name, s.last_name, s.class_group, s.email,
                   to_char(b.created_at, 'DD.MM. HH24:MI') AS booked_at
            FROM internal.bookings b
            JOIN internal.students s ON s.student_id = b.student_id
            WHERE b.open_hour_id = $1
            ORDER BY b.created_at
            """,
            id,
        )
    return [dict(r) for r in rows]


# ----------------------------------------------------------------------
# READ ALL OPEN HOURS (public — students need this to book, no account)
# ----------------------------------------------------------------------

@router.get("/list")
async def list_open_hours(
    from_: str = Query(None, alias="from"),
    to: str = Query(None),
):
    date_from = datetime.date.fromisoformat(from_) if from_ else None
    date_to = datetime.date.fromisoformat(to) if to else None

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                oh.*,
                COALESCE(b.booked_count, 0) AS booked_count,
                oh.capacity - COALESCE(b.booked_count, 0) AS free_spots
            FROM internal.open_hours oh
            LEFT JOIN (
                SELECT open_hour_id, COUNT(*) AS booked_count
                FROM internal.bookings
                GROUP BY open_hour_id
            ) b ON b.open_hour_id = oh.id
            WHERE ($1::date IS NULL OR oh.date >= $1)
              AND ($2::date IS NULL OR oh.date <= $2)
            ORDER BY oh.date, oh.start_time
            """,
            date_from,
            date_to,
        )
        return [dict(r) for r in rows]


# ----------------------------------------------------------------------
# READ SUPERVISING-TEACHER LESSONS from the separate duklamaps DB
# (staff/admin only — used to plan free hours around a supervisor's
# existing lesson). Best-effort: returns [] if that DB is unconfigured
# or unreachable.
# ----------------------------------------------------------------------

@router.get("/supervisors", dependencies=_STAFF_ONLY)
async def list_supervisor_names():
    """Configured supervisor display names — the grid uses this to build
    the per-supervisor filter toggle."""
    return supervisor_names()


@router.get("/supervisions", dependencies=_STAFF_ONLY)
async def list_supervisions(
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    week: str = Query("actual"),
):
    date_from = datetime.date.fromisoformat(from_)
    date_to = datetime.date.fromisoformat(to)
    return await fetch_supervisions(date_from, date_to, week)


@router.get("/supervisions/debug", dependencies=_STAFF_ONLY)
async def debug_supervisions():
    """Why is the duklamaps overlay empty? Shows the connection config,
    whether we can reach that DB, the resolved date column, and a sample
    of teacher names actually present (so DUKLA_SUPERVISORS can be matched
    to the real spelling)."""
    return await dukla_diagnose()


# ----------------------------------------------------------------------
# DELETE OPEN HOURS (staff/admin only)
# ----------------------------------------------------------------------

@router.delete("/delete/{id}", dependencies=_STAFF_ONLY)
async def delete_open_hours(id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute("DELETE FROM internal.open_hours WHERE id = $1", id)
        except asyncpg.ForeignKeyViolationError:
            raise HTTPException(
                status_code=409,
                detail="Termín má existující rezervace, nelze ho smazat.",
            )
        return {"status": "ok", "msg": "Záznam byl smazán."}
