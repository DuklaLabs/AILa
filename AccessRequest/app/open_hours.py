import datetime

import asyncpg
from fastapi import APIRouter, Depends, Form, HTTPException

from ailacore.auth import require_role
from ailacore.db import get_pool

router = APIRouter(prefix="/api/open-hours", tags=["Open Hours"])

_STAFF_ONLY = [Depends(require_role("admin", "staff"))]


# ----------------------------------------------------------------------
# CREATE / ADD OPEN HOURS (staff/admin only)
# ----------------------------------------------------------------------

@router.post("/add", dependencies=_STAFF_ONLY)
async def add_open_hours(
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    capacity: int = Form(...),
    note: str = Form(None),
):
    date_obj = datetime.date.fromisoformat(date)
    start_time_obj = datetime.time.fromisoformat(start_time)
    end_time_obj = datetime.time.fromisoformat(end_time)

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO internal.open_hours
                    (weekday, date, start_time, end_time, capacity, note)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                date_obj.strftime("%A"),
                date_obj,
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
