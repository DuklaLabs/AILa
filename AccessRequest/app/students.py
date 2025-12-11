from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import asyncpg
import os

router_students = APIRouter()
templates = Jinja2Templates(directory="app/templates")



DB_CONFIG = {
    "user": os.getenv("POSTGRES_USER", "agent"),
    "password": os.getenv("POSTGRES_PASSWORD", "agentpass"),
    "database": os.getenv("POSTGRES_DB", "agentdb"),
    "host": os.getenv("POSTGRES_HOST", "postgres"),  # 👈 DŮLEŽITÉ: jméno služby z docker-compose
    "port": 5432,
}



async def get_pool():
    return await asyncpg.create_pool(**DB_CONFIG)


async def load_students():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT student_id, first_name, last_name, email,
                   to_char(registration_date, 'YYYY-MM-DD') AS registration_date
            FROM internal.students
            ORDER BY student_id DESC
            """
        )
    await pool.close()
    return rows


async def save_student(first_name: str, last_name: str, email: str, class_group: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO internal.students (first_name, last_name, email, class_group)
                VALUES ($1, $2, $3, $4)
                """,
                first_name,
                last_name,
                email,
                class_group
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(status_code=400, detail="E-mail již existuje.")
    await pool.close()



@router_students.get("/student-dashboard")
async def student_dashboard(request: Request):
    students = await load_students()
    return templates.TemplateResponse(
        "student_dashboard.html",
        {"request": request, "students": students},
    )

@router_students.get("/student-register")
async def student_register_page(request: Request):
    return templates.TemplateResponse("student_register.html", {"request": request})


@router_students.post("/student-register")
async def register_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    class_group: str = Form(...)
):
    await save_student(first_name, last_name, email, class_group)
    return HTMLResponse("<h1>Registrace proběhla úspěšně!</h1>")


@router_students.post("/student-register")
async def register_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
):
    await save_student(first_name, last_name, email)
    # Můžeš vracet i šablonu „díky“
    return HTMLResponse("<h1>Registrace proběhla úspěšně!</h1>")

@router_students.post("/book-hour")
async def book_hour(
    request: Request,
    hour_id: int = Form(...),
    email: str = Form(...)
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row_student = await conn.execute(
        """
            SELECT student_id, first_name, last_name, email,
            FROM internal.students
            WHERE email = $1 
            """, email
            
        )
        
    


    return HTMLResponse("<h1> O rezervaci stavu rezervace budete informavání emailem.</h1>")



@router_students.get("/api/students")
async def api_get_students():
    students = await load_students()
    # asyncpg Record → dict
    return [dict(s) for s in students]
