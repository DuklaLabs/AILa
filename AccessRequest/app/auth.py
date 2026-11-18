import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
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

PREFIX = os.getenv("URL_PREFIX", "").rstrip("/")

router_auth = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["BASE"] = PREFIX


class RFIDLoginRequest(BaseModel):
    card_uid: str


def _safe_next(url: str | None) -> str | None:
    """Guard against open redirects: only follow `next` if it's a plain
    relative path (and not protocol-relative, i.e. not starting with "//").
    Everything else (portal shell, other AILa modules) is same-origin now,
    so a relative path is all `next` ever needs to be."""
    if not url:
        return None
    if url.startswith("/") and not url.startswith("//"):
        return url
    return None


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
async def login_page(request: Request, next: str | None = None):
    return templates.TemplateResponse(request, "login.html", {"next": _safe_next(next)})


@router_auth.post("/login-check")
async def login_check(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(None),
):
    next_url = _safe_next(next)
    user = await authenticate_password(username, password)
    if user is None:
        pending = await authenticate_password_ignoring_active(username, password)
        if pending is not None and not pending.is_active:
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Účet zatím čeká na schválení administrátorem.", "next": next_url},
                status_code=403,
            )
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Nesprávné přihlašovací údaje.", "next": next_url},
            status_code=401,
        )

    target = next_url or (f"{PREFIX}/admin" if user.role in ("admin", "staff") else f"{PREFIX}/student-hours")
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
    target = _safe_next(request.query_params.get("next")) or f"{PREFIX}/"
    response = RedirectResponse(url=target)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await revoke_session(token)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router_auth.get("/api/whoami")
async def whoami(user: User = Depends(get_current_user)):
    return user
