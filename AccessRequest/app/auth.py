from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import json
import os

router_auth = APIRouter()
templates = Jinja2Templates(directory="app/templates")

USER_DB = "app/data/users.json"
SESSION_COOKIE = "dl_session"


def load_users():
    """Naivní user DB v JSON – můžeš nahradit za Postgres."""
    if not os.path.exists(USER_DB):
        # jednoduchý default user: admin / admin
        os.makedirs(os.path.dirname(USER_DB), exist_ok=True)
        with open(USER_DB, "w") as f:
            json.dump({"admin": "admin"}, f)
    with open(USER_DB, "r") as f:
        return json.load(f)


def authenticate(username: str, password: str) -> bool:
    users = load_users()
    return users.get(username) == password


def require_login(request: Request) -> bool:
    return request.cookies.get(SESSION_COOKIE) is not None


@router_auth.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router_auth.post("/login-check")
async def login_check(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    if authenticate(username, password):
        response = RedirectResponse(url="/admin", status_code=302)
        response.set_cookie(
            SESSION_COOKIE,
            username,
            httponly=True,
            samesite="lax",
        )
        return response

    # špatné heslo → zobrazení chyby
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "Nesprávné přihlašovací údaje.",
        },
        status_code=401,
    )


@router_auth.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/")
    response.delete_cookie(SESSION_COOKIE)
    return response
