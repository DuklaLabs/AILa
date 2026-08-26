import datetime

import asyncpg
from fastapi import APIRouter, Depends, Form, HTTPException

from ailacore.auth import require_role
from ailacore.db import get_pool

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
):
    if hour_number not in _PERIODS_BY_NUMBER:
        raise HTTPException(status_code=400, detail="Neplatná vyučovací hodina.")

    date_obj = datetime.date.fromisoformat(date)
    start_time_obj, end_time_obj = _PERIODS_BY_NUMBER[hour_number]

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO internal.open_hours
                    (weekday, date, hour_number, start_time, end_time, capacity, note)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                date_obj.strftime("%A"),
                date_obj,
                hour_number,
                start_time_obj,
                end_time_obj,
                capacity,
                note,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "msg": "Hodiny byly uloženy."}


# ----------------------------------------------------------------------
# READ ALL OPEN HOURS (public — students need this to book, no account)
# ----------------------------------------------------------------------

@router.get("/list")
async def list_open_hours():
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
            ORDER BY oh.date, oh.start_time
            """
        )
        return [dict(r) for r in rows]


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
