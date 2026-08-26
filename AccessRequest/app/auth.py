from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ailacore.auth import (
    SESSION_COOKIE,
    SESSION_TTL,
    authenticate_password,
    authenticate_rfid,
    create_session,
    get_current_user,
    revoke_session,
)
from ailacore.models import User

router_auth = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class RFIDLoginRequest(BaseModel):
    card_uid: str


async def _attach_session_cookie(response, user_id: int) -> None:
    token, _expires_at = await create_session(user_id)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
    )


@router_auth.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router_auth.post("/login-check")
async def login_check(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = await authenticate_password(username, password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Nesprávné přihlašovací údaje."},
            status_code=401,
        )

    target = "/admin" if user.role in ("admin", "staff") else "/student-hours"
    response = RedirectResponse(url=target, status_code=302)
    await _attach_session_cookie(response, user.id)
    return response


@router_auth.post("/login/rfid")
async def login_rfid(payload: RFIDLoginRequest):
    """RFID SSO: přiložení karty na čtečce (funguje jako HID klávesnice)
    pošle card_uid sem, bez vlastního firmwaru na straně čtečky."""
    user = await authenticate_rfid(payload.card_uid)
    if user is None:
        raise HTTPException(status_code=401, detail="Neplatná nebo neaktivní karta.")

    response = JSONResponse({"status": "ok", "user": user.model_dump()})
    await _attach_session_cookie(response, user.id)
    return response


@router_auth.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/")
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await revoke_session(token)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router_auth.get("/api/whoami")
async def whoami(user: User = Depends(get_current_user)):
    return user
