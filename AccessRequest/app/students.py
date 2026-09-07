import json
import secrets

from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncpg

from ailacore.auth import (
    SESSION_COOKIE,
    get_user_from_token,
    hash_password,
    require_role,
)
from ailacore.db import get_pool

from app.dukla_db import class_teacher
from app.notify import send_release_requests

router_students = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_STAFF_ONLY = [Depends(require_role("admin", "staff"))]

# Per-student list of the open hours they're booked into, so the dashboard
# can show *where* each student is already registered. Each entry has a
# ready-made Czech `label` ("Po 1.9. · 3. h") used verbatim by both the
# server-rendered table and the JS re-render.
_STUDENTS_SQL = """
    SELECT s.student_id, s.first_name, s.last_name, s.email, s.class_group,
           to_char(s.registration_date, 'YYYY-MM-DD') AS registration_date,
           COALESCE(
               jsonb_agg(
                   jsonb_build_object(
                       'open_hour_id', oh.id,
                       'date', to_char(oh.date, 'YYYY-MM-DD'),
                       'hour_number', oh.hour_number,
                       'label',
                           (ARRAY['Ne','Po','Út','St','Čt','Pá','So'])[EXTRACT(DOW FROM oh.date)::int + 1]
                           || ' ' || to_char(oh.date, 'FMDD.FMMM.')
                           || ' · ' || COALESCE(oh.hour_number::text, '?') || '. h'
                   ) ORDER BY oh.date, oh.start_time
               ) FILTER (WHERE b.id IS NOT NULL),
               '[]'::jsonb
           ) AS bookings
    FROM internal.students s
    LEFT JOIN internal.bookings b ON b.student_id = s.student_id
    LEFT JOIN internal.open_hours oh ON oh.id = b.open_hour_id
    GROUP BY s.student_id
    ORDER BY s.student_id DESC
"""


async def load_students():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_STUDENTS_SQL)
    out = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("bookings"), str):
            d["bookings"] = json.loads(d["bookings"])
        out.append(d)
    return out


async def current_student_id(request: Request):
    """student_id of the logged-in student (or None for anonymous / staff
    visitors). Lets the dashboard show an "unregister" control only on the
    viewer's own bookings — the DELETE endpoint is session-scoped anyway,
    but there's no point offering a button that can only fail on other rows."""
    user = await get_user_from_token(request.cookies.get(SESSION_COOKIE))
    if user is None:
        return None
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT student_id FROM internal.students WHERE user_id = $1", user.id
        )


async def load_pending_students():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.student_id, s.first_name, s.last_name, s.email, s.class_group,
                   u.id AS user_id,
                   to_char(s.registration_date, 'YYYY-MM-DD') AS registration_date
            FROM internal.students s
            JOIN auth.users u ON u.id = s.user_id
            WHERE u.role = 'student' AND u.is_active = FALSE
            ORDER BY s.student_id DESC
            """
        )
    return rows


async def register_student(
    first_name: str, last_name: str, email: str, class_group: str, password: str
) -> dict:
    """Creates both the login account (auth.users, role='student') and the
    roster row (internal.students, used by bookings/excused/reports),
    linked via internal.students.user_id — one identity, not two.

    New accounts start with is_active=FALSE: they can't log in — and so
    can't reach /student-hours or /api/book-hour, both gated on a valid
    session — until an admin/staff approves them (see /api/students/pending
    + /approve below)."""
    password_hash = hash_password(password)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                user_id = await conn.fetchval(
                    """
                    INSERT INTO auth.users (username, full_name, email, role, password_hash, is_active)
                    VALUES ($1, $2, $3, 'student', $4, FALSE)
                    RETURNING id
                    """,
                    email,
                    f"{first_name} {last_name}",
                    email,
                    password_hash,
                )
                student_id = await conn.fetchval(
                    """
                    INSERT INTO internal.students
                        (first_name, last_name, email, class_group, user_id, release_token)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING student_id
                    """,
                    first_name,
                    last_name,
                    email,
                    class_group,
                    user_id,
                    secrets.token_urlsafe(24),
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(status_code=400, detail="E-mail již existuje.")
    return {"user_id": user_id, "student_id": student_id}


async def request_release_consent(student_id: int, class_group: str) -> dict:
    """Po registraci: dohledá třídního učitele, uloží snapshot a rozešle
    žádost o souhlas (třídní + koordinátor). Best-effort."""
    try:
        ct = await class_teacher(class_group)
    except Exception:  # noqa: BLE001
        ct = None
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE internal.students SET release_class_teacher = $1 "
            "WHERE student_id = $2 "
            "RETURNING first_name, last_name, release_token",
            (ct or {}).get("name"), student_id,
        )
    if row is None:
        return {"error": "student nenalezen"}
    try:
        return await send_release_requests(
            student_name=f"{row['first_name']} {row['last_name']}",
            class_group=class_group,
            release_token=row["release_token"],
            class_teacher=ct,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


@router_students.get("/student-dashboard")
async def student_dashboard(request: Request):
    students = await load_students()
    return templates.TemplateResponse(
        request,
        "student_dashboard.html",
        {"students": students, "my_student_id": await current_student_id(request)},
    )


@router_students.get("/student-register")
async def student_register_page(request: Request):
    return templates.TemplateResponse(request, "student_register.html")


@router_students.post("/student-register")
async def register_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    class_group: str = Form(...),
    password: str = Form(...),
):
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "student_register.html",
            {"error": "Heslo musí mít alespoň 8 znaků."},
            status_code=400,
        )

    reg = await register_student(first_name, last_name, email, class_group, password)
    await request_release_consent(reg["student_id"], class_group)

    return HTMLResponse(
        "<h1>Registrace přijata</h1>"
        "<p>Účet teď musí schválit administrátor DuklaLabs. Zároveň jsme požádali "
        "tvého třídního učitele a koordinátora o souhlas s uvolňováním z výuky – "
        "než ho oba dají, budeš se moct zapisovat jen na hodiny, kdy nemáš výuku.</p>"
    )


@router_students.get("/api/students")
async def api_get_students():
    students = await load_students()
    return [dict(s) for s in students]


# ----------------------------------------------------------------------
# SCHVALOVÁNÍ REGISTRACÍ (staff/admin only)
# ----------------------------------------------------------------------

@router_students.get("/api/students/pending", dependencies=_STAFF_ONLY)
async def api_get_pending_students():
    students = await load_pending_students()
    return [dict(s) for s in students]


@router_students.post("/api/students/{user_id}/approve", dependencies=_STAFF_ONLY)
async def approve_student(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE auth.users SET is_active = TRUE WHERE id = $1 AND role = 'student'",
            user_id,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Studentský účet nenalezen.")
    return {"status": "ok", "msg": "Účet schválen."}


@router_students.post("/api/students/{user_id}/reject", dependencies=_STAFF_ONLY)
async def reject_student(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM internal.students WHERE user_id = $1", user_id
            )
            result = await conn.execute(
                "DELETE FROM auth.users WHERE id = $1 AND role = 'student'", user_id
            )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Studentský účet nenalezen.")
    return {"status": "ok", "msg": "Registrace zamítnuta."}
