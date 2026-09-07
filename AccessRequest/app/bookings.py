"""Real, deterministic slot booking — replaces the old flow where
/api/book-hour just forwarded the request as a natural-language prompt to
Security_agent's LLM ReAct loop (which then decided what raw SQL to run
via its `db_query` tool, with no actual capacity check anywhere). Nothing
here talks to an LLM; it's a plain transactional insert.

Booking now requires login: the student is identified from their session
(ailacore.auth), not from a freely-typed email — the old flow let anyone
book on behalf of any registered email with zero proof of identity.
"""
import secrets

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ailacore.auth import get_current_user
from ailacore.db import get_pool
from ailacore.models import User

from app.notify import notify_booking

router = APIRouter(prefix="/api", tags=["Bookings"])


class BookHourRequest(BaseModel):
    hour_id: int


@router.post("/book-hour")
async def book_hour(payload: BookHourRequest, user: User = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            student = await conn.fetchrow(
                "SELECT student_id FROM internal.students WHERE user_id = $1",
                user.id,
            )
            if student is None:
                raise HTTPException(
                    status_code=404,
                    detail="K tomuto účtu není přiřazený studentský profil.",
                )

            # FOR UPDATE locks the slot row for the rest of this transaction,
            # so two concurrent bookings into the same slot can't both pass
            # the capacity check below before either commits.
            slot = await conn.fetchrow(
                "SELECT id, capacity FROM internal.open_hours WHERE id = $1 FOR UPDATE",
                payload.hour_id,
            )
            if slot is None:
                raise HTTPException(status_code=404, detail="Termín neexistuje.")

            booked_count = await conn.fetchval(
                "SELECT COUNT(*) FROM internal.bookings WHERE open_hour_id = $1",
                payload.hour_id,
            )
            if booked_count >= slot["capacity"]:
                raise HTTPException(status_code=409, detail="Termín je plně obsazený.")

            decision_token = secrets.token_urlsafe(24)
            try:
                await conn.execute(
                    """
                    INSERT INTO internal.bookings
                        (student_id, open_hour_id, decision_token)
                    VALUES ($1, $2, $3)
                    """,
                    student["student_id"],
                    payload.hour_id,
                    decision_token,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(
                    status_code=409,
                    detail="Tento termín už máš zarezervovaný.",
                )

    # Rezervace je uložená. Teď (best-effort, mimo transakci) informujeme
    # dozora dané otevřené hodiny e-mailem. Selhání mailu nesmí shodit zápis.
    notify = {"error": "nespuštěno"}
    try:
        async with pool.acquire() as conn:
            info = await conn.fetchrow(
                """
                SELECT oh.date, oh.hour_number, oh.start_time, oh.end_time,
                       oh.note, oh.supervisor, oh.capacity,
                       (SELECT COUNT(*) FROM internal.bookings
                        WHERE open_hour_id = oh.id) AS booked_count,
                       s.first_name, s.last_name, s.class_group
                FROM internal.open_hours oh
                CROSS JOIN internal.students s
                WHERE oh.id = $1 AND s.student_id = $2
                """,
                payload.hour_id,
                student["student_id"],
            )
        if info is not None:
            notify = await notify_booking(
                supervisor_csv=info["supervisor"],
                student_name=f"{info['first_name']} {info['last_name']}",
                class_group=info["class_group"],
                day=info["date"],
                hour_number=info["hour_number"],
                start_time=info["start_time"],
                end_time=info["end_time"],
                note=info["note"],
                booked_count=info["booked_count"],
                capacity=info["capacity"],
                decision_token=decision_token,
            )
    except Exception as exc:  # noqa: BLE001 - notifikace je best-effort
        notify = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "detail": "Rezervace proběhla úspěšně.",
        "teacher_notified": bool(notify.get("notified")),
        "notify": notify,
    }


@router.get("/my-bookings")
async def my_bookings(user: User = Depends(get_current_user)):
    """IDs of the open hours the logged-in student is booked into — the
    registration grid uses this to mark cells the student already has."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        student = await conn.fetchrow(
            "SELECT student_id FROM internal.students WHERE user_id = $1", user.id
        )
        if student is None:
            return []
        rows = await conn.fetch(
            "SELECT open_hour_id FROM internal.bookings WHERE student_id = $1",
            student["student_id"],
        )
    return [r["open_hour_id"] for r in rows]


@router.delete("/book-hour/{hour_id}")
async def cancel_hour(hour_id: int, user: User = Depends(get_current_user)):
    """Student unregisters themselves from an open hour."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        student = await conn.fetchrow(
            "SELECT student_id FROM internal.students WHERE user_id = $1", user.id
        )
        if student is None:
            raise HTTPException(
                status_code=404,
                detail="K tomuto účtu není přiřazený studentský profil.",
            )
        result = await conn.execute(
            "DELETE FROM internal.bookings WHERE student_id = $1 AND open_hour_id = $2",
            student["student_id"],
            hour_id,
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Tuto rezervaci nemáš.")
    return {"detail": "Rezervace byla zrušena."}
