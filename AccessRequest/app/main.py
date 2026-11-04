import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ailacore.db import close_pool
from ailacore.admin import rbac_api_router, mount_admin_ui

from app.router import router as admin_router
from app.auth import router_auth
from app.students import router_students
from app.decisions import router_decisions
from app.release import router_release
from app.mail_log import router_mail_log
from app.agent_review import router_agent_review

from app.open_hours import router as open_hours_router
from app.machines import router_machines
from app.dukla_db import close_dukla_pool
from app.scheduler import shutdown_scheduler, start_scheduler


app = FastAPI()

# Portálový shell (aila.localhost, viz Gateway/) čte přihlášeného uživatele
# přes fetch("/api/whoami", {credentials:"include"}) – cross-origin vůči
# tomuto originu, takže potřebuje CORS. Cookie dl_session je společná
# (SESSION_COOKIE_DOMAIN), CORS jen dovolí JS na portálu si přečíst odpověď.
_portal_origins = [
    o.strip() for o in os.getenv("PORTAL_ORIGINS", "http://aila.localhost").split(",")
    if o.strip()
]
if _portal_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_portal_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )


@app.on_event("startup")
async def _startup():
    start_scheduler()


@app.on_event("shutdown")
async def _shutdown():
    shutdown_scheduler()
    await close_pool()
    await close_dukla_pool()

# statické soubory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# šablony
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Hlavní rozcestník – obsahuje odkazy na login, admin, student dashboard atd.
    """
    return templates.TemplateResponse(request, "index.html")


# připojení routerů
app.include_router(router_auth)
app.include_router(router_students)
app.include_router(admin_router)
app.include_router(open_hours_router)
app.include_router(router_decisions)
app.include_router(router_release)
app.include_router(router_mail_log)
app.include_router(router_agent_review)
app.include_router(router_machines)

# Sdílená RBAC administrace z ailacore (API + React konzole na /admin/rbac/).
app.include_router(rbac_api_router)
mount_admin_ui(app, os.getenv("RBAC_UI_DIST", "rbac-ui-dist"))
