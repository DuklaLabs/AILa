import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
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
from app.timetable_client import close_timetable_pool
from app.excuse_requests import router as excuse_requests_router, staff_router as excuse_requests_staff_router
from app.excuse_digest import run_weekly_digest


app = FastAPI()

# Cesta pod Gateway (viz Gateway/Caddyfile) – Caddy předává celou cestu
# beze stripu, takže služba musí sama mountovat statiku/šablony/routery
# pod tímhle prefixem místo na kořeni domény. Prázdné URL_PREFIX = služba
# běží samostatně na vlastním kořeni (lokální vývoj bez Gateway).
PREFIX = os.getenv("URL_PREFIX", "").rstrip("/")

# In-process scheduler for the weekly teacher digest (excuse_digest.py).
# AsyncIOScheduler (not BackgroundScheduler) because the job runs asyncpg
# queries against a pool bound to uvicorn's own running event loop —
# BackgroundScheduler would call into it from a separate thread, which
# asyncpg doesn't support. Assumes a single access-request-server replica;
# scaling out would need a distributed lock to avoid duplicate digests.
scheduler = AsyncIOScheduler(timezone="Europe/Prague")


@app.on_event("startup")
async def _startup():
    scheduler.add_job(
        run_weekly_digest,
        "cron",
        day_of_week="thu",
        hour=12,
        minute=0,
        id="weekly_excuse_digest",
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.start()
    start_scheduler()


@app.on_event("shutdown")
async def _shutdown():
    scheduler.shutdown(wait=False)
    shutdown_scheduler()
    await close_pool()
    await close_dukla_pool()
    await close_timetable_pool()

# statické soubory
app.mount(f"{PREFIX}/static", StaticFiles(directory="app/static"), name="static")

# šablony
templates = Jinja2Templates(directory="app/templates")
# Prefix dostupný v šablonách pro odkazy/static assety (viz app/templates/*.html).
templates.env.globals["BASE"] = PREFIX


@app.get(f"{PREFIX}/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Hlavní rozcestník – obsahuje odkazy na login, admin, student dashboard atd.
    """
    return templates.TemplateResponse(request, "index.html")


# připojení routerů
app.include_router(router_auth, prefix=PREFIX)
app.include_router(router_students, prefix=PREFIX)
app.include_router(admin_router, prefix=PREFIX)
app.include_router(open_hours_router, prefix=PREFIX)
app.include_router(router_decisions, prefix=PREFIX)
app.include_router(router_release, prefix=PREFIX)
app.include_router(router_mail_log, prefix=PREFIX)
app.include_router(excuse_requests_router, prefix=PREFIX)
app.include_router(excuse_requests_staff_router, prefix=PREFIX)
app.include_router(router_agent_review, prefix=PREFIX)
app.include_router(router_machines, prefix=PREFIX)

# Sdílená RBAC administrace z ailacore (API + React konzole na /admin/rbac/).
app.include_router(rbac_api_router, prefix=PREFIX)
mount_admin_ui(
    app,
    os.getenv("RBAC_UI_DIST", "rbac-ui-dist"),
    path=f"{PREFIX}/admin/rbac",
    login_url=f"{PREFIX}/login",
)
