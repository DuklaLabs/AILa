import os

from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ailacore.auth import get_current_user
from ailacore.db import close_pool
from ailacore.models import User

from app.documents import router as documents_router
from app.upload import router as upload_router

# Cesta pod Gateway (viz Gateway/Caddyfile) – Caddy předává celou cestu beze
# stripu, takže služba musí sama mountovat statiku/routery pod tímhle
# prefixem místo na kořeni domény.
PREFIX = os.getenv("URL_PREFIX", "").rstrip("/")

app = FastAPI()


@app.on_event("shutdown")
async def _shutdown():
    await close_pool()


# Portovaná statika prototypu (krouzek.css/js, logo, nahrané fotky) —
# samostatná stránka je index.html přímo v app/static/, žádné šablony.
app.mount(f"{PREFIX}/static", StaticFiles(directory="app/static"), name="static")


@app.get(f"{PREFIX}/")
async def read_root():
    """Stránka se vždy servíruje — read-only vs. editační režim rozhoduje
    portovaný frontend podle výsledku /api/whoami (stejný vzor jako
    useCurrentUser() v LabOrchestratorDashboard proti AccessRequest).
    index.html není šablona (Jinja) – prefix se do něj doplní jednoduchou
    náhradou placeholderu __URL_PREFIX__ (viz static/index.html)."""
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        html = f.read().replace("__URL_PREFIX__", PREFIX)
    return HTMLResponse(html)


@app.get(f"{PREFIX}/api/whoami")
async def whoami(user: User = Depends(get_current_user)):
    return user


app.include_router(documents_router, prefix=PREFIX)
app.include_router(upload_router, prefix=PREFIX)
