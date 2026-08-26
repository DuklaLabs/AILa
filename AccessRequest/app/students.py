from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncpg

from ailacore.auth import hash_password, require_role
from ailacore.db import get_pool

router_students = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_STAFF_ONLY = [Depends(require_role("admin", "staff"))]


async def load_students():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT student_id, first_name, last_name, email, class_group,
                   to_char(registration_date, 'YYYY-MM-DD') AS registration_date
            FROM internal.students
            ORDER BY student_id DESC
            """
        )
    return rows


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
) -> int:
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
                await conn.execute(
                    """
                    INSERT INTO internal.students (first_name, last_name, email, class_group, user_id)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    first_name,
                    last_name,
                    email,
                    class_group,
                    user_id,
                )
            except asyncpg.UniqueViolationError:
                raise HTTPException(status_code=400, detail="E-mail již existuje.")
    return user_id


@router_students.get("/student-dashboard")
async def student_dashboard(request: Request):
    students = await load_students()
    return templates.TemplateResponse(
        request,
        "student_dashboard.html",
        {"students": students},
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

    await register_student(first_name, last_name, email, class_group, password)

    return HTMLResponse(
        "<h1>Registrace přijata</h1>"
        "<p>Účet teď musí schválit administrátor DuklaLabs. "
        "Až se to stane, budeš se moct přihlásit a zapsat na volné hodiny.</p>"
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
