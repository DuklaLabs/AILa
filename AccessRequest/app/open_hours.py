from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse
import asyncpg
import os
import datetime



router = APIRouter(prefix="/api/open-hours", tags=["Open Hours"])

DB_CONFIG = {
    "user": "agent",
    "password": "agentpass",
    "database": "agentdb",
    "host": "postgres",
    "port": 5432,
}

async def get_pool():
    return await asyncpg.create_pool(**DB_CONFIG)

# ----------------------------------------------------------------------
# CREATE / ADD OPEN HOURS
# ----------------------------------------------------------------------

@router.post("/add")
async def add_open_hours(
    date: str = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    capacity: int = Form(...),
    note: str = Form(None)
):
    date_obj = datetime.date.fromisoformat(date)
    start_time_obj = datetime.time.fromisoformat(start_time)
    end_time_obj = datetime.time.fromisoformat(end_time)
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute("""
                INSERT INTO internal.open_hours 
                    (date, start_time, end_time, capacity, note)
                VALUES ($1, $2, $3, $4, $5)
            """, date_obj, start_time_obj, end_time_obj, capacity, note)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "msg": "Hodiny byly uloženy."}


# ----------------------------------------------------------------------
# READ ALL OPEN HOURS
# ----------------------------------------------------------------------

@router.get("/list")
async def list_open_hours():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM internal.open_hours ORDER BY date, start_time")
        return [dict(r) for r in rows]


# ----------------------------------------------------------------------
# DELETE OPEN HOURS
# ----------------------------------------------------------------------

@router.delete("/delete/{id}")
async def delete_open_hours(id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM internal.open_hours WHERE id = $1", id)
        return {"status": "ok", "msg": "Záznam byl smazán."}
