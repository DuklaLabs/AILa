from ailacore.db import get_pool


async def active_student_emails() -> list[str]:
    """E-maily aktivních studentských účtů (vzor
    AccessRequest/app/students.py:load_pending_students, jen obrácená
    podmínka is_active)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.email
            FROM internal.students s
            JOIN auth.users u ON u.id = s.user_id
            WHERE u.role = 'student' AND u.is_active = TRUE AND s.email IS NOT NULL
            ORDER BY s.email
            """
        )
    return [r["email"] for r in rows]
