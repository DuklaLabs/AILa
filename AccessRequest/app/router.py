from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ailacore.auth import SESSION_COOKIE, get_user_from_token

from app.bookings import router as bookings_router

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


async def _require_staff(request: Request):
    """Page-level guard for HTML routes: redirect to /login instead of a
    raw 401, since these render templates rather than return JSON."""
    user = await get_user_from_token(request.cookies.get(SESSION_COOKIE))
    if user is None or user.role not in ("admin", "staff"):
        return None
    return user


async def _require_any_login(request: Request):
    return await get_user_from_token(request.cookies.get(SESSION_COOKIE))


@router.get("/admin")
async def render_admin(request: Request):
    if await _require_staff(request) is None:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "admin.html")


@router.get("/student-hours")
async def student_hours(request: Request):
    if await _require_any_login(request) is None:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "student_hours.html")


router.include_router(bookings_router)
