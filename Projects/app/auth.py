"""Přihlášení pro službu Projects.

Převzato z `AccessRequest/app/auth.py` – primitiva (hash, session, RFID) jsou
ve sdíleném `ailacore.auth`, tady je jen HTML login stránka a nastavení cookie.
Po přihlášení se přesměruje rovnou do SPA na `/app/projects/`.

(Dedup do `ailacore.webauth` je vhodný follow-up – zatím to má i AccessRequest
u sebe.)
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ailacore.auth import (
    SESSION_COOKIE,
    SESSION_TTL,
    authenticate_password,
    authenticate_password_ignoring_active,
    authenticate_rfid,
    create_session,
    get_current_user,
    revoke_session,
)
from ailacore.models import User
from ailacore.rbac import get_effective_permissions

router_auth = APIRouter()
templates = Jinja2Templates(directory="app/templates")

SPA_HOME = "/app/projects/"


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
        pending = await authenticate_password_ignoring_active(username, password)
        if pending is not None and not pending.is_active:
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Účet zatím čeká na schválení administrátorem."},
                status_code=403,
            )
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Nesprávné přihlašovací údaje."},
            status_code=401,
        )

    response = RedirectResponse(url=SPA_HOME, status_code=302)
    await _attach_session_cookie(response, user.id)
    return response


@router_auth.post("/login/rfid")
async def login_rfid(payload: RFIDLoginRequest):
    """RFID SSO: přiložení karty na HID čtečce pošle card_uid sem."""
    user = await authenticate_rfid(payload.card_uid)
    if user is None:
        return JSONResponse(
            {"status": "error", "detail": "Neplatná nebo neaktivní karta."},
            status_code=401,
        )
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


@router_auth.get("/api/me")
async def me(user: User = Depends(get_current_user)):
    """Identita + efektivní oprávnění – SPA podle nich schovává akce."""
    perms = await get_effective_permissions(user.id, user.role)
    return {"user": user.model_dump(), "permissions": sorted(perms)}
