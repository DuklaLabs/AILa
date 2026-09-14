"""Real, deterministic slot booking — replaces the old flow where
/api/book-hour just forwarded the request as a natural-language prompt to
Security_agent's LLM ReAct loop (which then decided what raw SQL to run
via its `db_query` tool, with no actual capacity check anywhere). Nothing
here talks to an LLM; it's a plain transactional insert.

Booking now requires login: the student is identified from their session
(ailacore.auth), not from a freely-typed email — the old flow let anyone
book on behalf of any registered email with zero proof of identity.

If the booked slot overlaps a regular lesson (per DuklaMaps), this used to
auto-write internal.excused — now it queues a pending internal.excuse_requests
row instead; the teacher decides via the weekly digest (excuse_digest.py).
"""
import datetime
import logging
import secrets

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ailacore.auth import get_current_user
from ailacore.db import get_pool
from ailacore.models import User

from app import dukla_db
from app.dukla_db import class_teachers, class_week
from app.notify import notify_booking
from app.missing_teacher_tickets import record_missing_teacher
from app.timetable_client import find_class_lesson, find_teacher_email

router = APIRouter(prefix="/api", tags=["Bookings"])
log = logging.getLogger(__name__)


async def _precheck_lesson_conflict(student, slot) -> dict | None:
    """Checks DuklaMaps for a lesson conflict BEFORE the booking transaction
    opens — this is a cross-process network call, so it must not run under
    the open_hours row lock (FOR UPDATE), and a rejection here (missing
    teacher email) must not touch internal.bookings at all, so there's
    nothing to roll back.

    Returns None if there's no conflict, or DuklaMaps couldn't be reached
    (fail-open — a flaky DuklaMaps must never block booking, same principle
    as before). Returns a dict with the lesson + teacher_email if there IS
    a conflict and the teacher has a usable email on file. Raises
    HTTPException(422) directly — after recording a missing-teacher ticket —
    if there's a conflict but the teacher has no usable email (fail-closed:
    the booking is rejected outright, per product decision)."""
    class_group = student["class_group"]
    hour_number = slot["hour_number"]
    if hour_number is None or not class_group:
        return None

    try:
        lesson = await find_class_lesson(class_group, slot["date"], hour_number)
    except (OSError, asyncpg.PostgresError) as exc:
        log.warning("DuklaMaps timetable lookup failed (fail-open, booking proceeds): %s", exc)
        return None
    if lesson is None:
        return None

    teacher_id = lesson["teacher_id"]
    if not teacher_id:
        # Synced row with no teacher identity at all (older data / unassigned
        # substitution) — nothing to dedupe a ticket on, nothing to email.
        # Fail-open: proceed without the excuse workflow for this booking.
        log.warning("Lesson found but no teacher_id on file, skipping excuse workflow: %s", lesson)
        return None

    try:
        teacher_email = await find_teacher_email(teacher_id)
    except (OSError, asyncpg.PostgresError) as exc:
        level = log.error if isinstance(exc, asyncpg.InsufficientPrivilegeError) else log.warning
        level("DuklaMaps teacher-email lookup failed (fail-open, booking proceeds): %s", exc)
        return None

    if not teacher_email:
        await record_missing_teacher(teacher_id, lesson["teacher_name"])
        raise HTTPException(
            status_code=422,
            detail=(
                f"Tuto hodinu nelze zapsat: vyučující {lesson['teacher_name']} nemá v systému e-mail. "
                "Byl vytvořen tiket pro administrátora, zkus to prosím později."
            ),
        )

    lesson["teacher_email"] = teacher_email
    return lesson


async def _create_pending_excuse_request(conn, student_id: int, booking_id: int, lesson: dict, lesson_date) -> None:
    lesson_id = await conn.fetchval(
        """
        INSERT INTO internal.lesson_hours (weekday, date, class_name, subject_name, teacher_name, hour_number)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (date, class_name, hour_number) DO UPDATE SET
            subject_name = EXCLUDED.subject_name,
            teacher_name = EXCLUDED.teacher_name
        RETURNING lesson_id
        """,
        lesson["weekday"],
        lesson_date,
        lesson["class_name"],
        lesson["subject_name"],
        lesson["teacher_name"],
        lesson["hour_number"],
    )
    await conn.execute(
        """
        INSERT INTO internal.excuse_requests
            (student_id, booking_id, lesson_id, teacher_id, teacher_email, token)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (student_id, lesson_id) WHERE status = 'pending' DO NOTHING
        """,
        student_id,
        booking_id,
        lesson_id,
        lesson["teacher_id"],
        lesson["teacher_email"],
        secrets.token_urlsafe(32),
    )


class BookHourRequest(BaseModel):
    hour_id: int


@router.post("/book-hour")
async def book_hour(payload: BookHourRequest, user: User = Depends(get_current_user)):
    pool = await get_pool()

    # Step 1 — cheap, lock-free reads to get what the precheck needs.
    async with pool.acquire() as conn:
        student = await conn.fetchrow(
            "SELECT student_id, class_group FROM internal.students WHERE user_id = $1",
            user.id,
        )
        if student is None:
            raise HTTPException(
                status_code=404,
                detail="K tomuto účtu není přiřazený studentský profil.",
            )
        slot = await conn.fetchrow(
            "SELECT id, capacity, date, hour_number FROM internal.open_hours WHERE id = $1",
            payload.hour_id,
        )
        if slot is None:
            raise HTTPException(status_code=404, detail="Termín neexistuje.")

    # Step 2 — DuklaMaps precheck, outside any agentdb transaction/lock.
    conflict = await _precheck_lesson_conflict(student, slot)

    # Step 3 — the real transaction: lock, capacity check, insert booking,
    # and (if there's a conflict) queue a pending excuse request.
    async with pool.acquire() as conn:
        async with conn.transaction():
            student = await conn.fetchrow(
                "SELECT student_id, class_group, release_teacher_ok, release_coord_ok "
                "FROM internal.students WHERE user_id = $1",
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
            locked_slot = await conn.fetchrow(
                "SELECT id, capacity, date, hour_number "
                "FROM internal.open_hours WHERE id = $1 FOR UPDATE",
                payload.hour_id,
            )
            if locked_slot is None:
                raise HTTPException(status_code=404, detail="Termín neexistuje.")

            # Uvolňování z výuky: dokud nemá souhlas třídního učitele I
            # koordinátora, student se nesmí zapsat na hodinu, kdy má podle
            # rozvrhu vlastní výuku (na volné hodiny ano).
            release_ok = (
                student["release_teacher_ok"] is True
                and student["release_coord_ok"] is True
            )
            if not release_ok and locked_slot["hour_number"] is not None:
                try:
                    clash = await class_teachers(
                        student["class_group"] or "", locked_slot["date"], locked_slot["hour_number"]
                    )
                except Exception:  # noqa: BLE001 - rozvrh nedostupný → neblokovat
                    clash = []
                if clash:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "V tuto dobu máš podle rozvrhu vlastní výuku a zatím "
                            "nemáš schválené uvolňování z výuky (třídní učitel + "
                            "koordinátor). Zapiš se na hodinu, kdy výuku nemáš, "
                            "nebo počkej na schválení."
                        ),
                    )

            booked_count = await conn.fetchval(
                "SELECT COUNT(*) FROM internal.bookings WHERE open_hour_id = $1 AND cancelled_at IS NULL",
                payload.hour_id,
            )
            if booked_count >= locked_slot["capacity"]:
                raise HTTPException(status_code=409, detail="Termín je plně obsazený.")

            decision_token = secrets.token_urlsafe(24)
            try:
                booking_id = await conn.fetchval(
                    """
                    INSERT INTO internal.bookings
                        (student_id, open_hour_id, decision_token)
                    VALUES ($1, $2, $3)
                    RETURNING id
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

            if conflict is not None:
                await _create_pending_excuse_request(
                    conn, student["student_id"], booking_id, conflict, locked_slot["date"]
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


@router.get("/my-lessons")
async def my_lessons(
    user: User = Depends(get_current_user),
    from_: str = Query(None, alias="from"),
    to: str = Query(None),
):
    """Sloty (datum + číslo hodiny), kdy má přihlášený student podle rozvrhu
    své třídy vlastní výuku – mřížka jimi zašedí buňky, na které se (bez
    schváleného uvolňování) nejde zapsat. Plus `release_approved`."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        st = await conn.fetchrow(
            "SELECT class_group, release_teacher_ok, release_coord_ok "
            "FROM internal.students WHERE user_id = $1",
            user.id,
        )
    if st is None:
        return {"release_approved": False, "lessons": []}
    release_ok = (
        st["release_teacher_ok"] is True and st["release_coord_ok"] is True
    )

    try:
        d_from = datetime.date.fromisoformat(from_) if from_ else datetime.date.today()
        d_to = datetime.date.fromisoformat(to) if to else d_from + datetime.timedelta(days=6)
    except ValueError:
        return {"release_approved": release_ok, "lessons": []}

    lessons: list[dict] = []
    monday = d_from - datetime.timedelta(days=d_from.weekday())
    while monday <= d_to:
        try:
            slots = await class_week(st["class_group"] or "", monday)
        except Exception:  # noqa: BLE001
            slots = []
        for s in slots:
            offset = s["day_index"] - dukla_db._DAY_BASE
            if 0 <= offset <= 6:
                day = monday + datetime.timedelta(days=offset)
                if d_from <= day <= d_to:
                    lessons.append(
                        {"date": day.isoformat(), "hour_number": s["hour_index"]}
                    )
        monday += datetime.timedelta(days=7)
    return {"release_approved": release_ok, "lessons": lessons}


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
