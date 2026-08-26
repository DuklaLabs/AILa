from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import asyncpg

from ailacore.auth import SESSION_COOKIE, SESSION_TTL, create_session, hash_password
from ailacore.db import get_pool

router_students = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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


async def register_student(
    first_name: str, last_name: str, email: str, class_group: str, password: str
) -> int:
    """Creates both the login account (auth.users, role='student') and the
    roster row (internal.students, used by bookings/excused/reports),
    linked via internal.students.user_id — one identity, not two."""
    password_hash = hash_password(password)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                user_id = await conn.fetchval(
                    """
                    INSERT INTO auth.users (username, full_name, email, role, password_hash)
                    VALUES ($1, $2, $3, 'student', $4)
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

    user_id = await register_student(first_name, last_name, email, class_group, password)

    response = RedirectResponse(url="/student-hours", status_code=302)
    token, _expires_at = await create_session(user_id)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
    )
    return response


@router_students.get("/api/students")
async def api_get_students():
    students = await load_students()
    return [dict(s) for s in students]
