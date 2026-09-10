import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ailacore.admin import mount_spa
from ailacore.db import close_pool

from app.auth import router_auth
from app.mcp_server import build_mcp
from app.routers import api_router

_mcp = build_mcp()
_mcp_app = _mcp[1] if _mcp else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _mcp_app is not None:
        # streamable_http_app() má vlastní lifespan (MCP session manager);
        # při app.mount() se sám nespustí, obalíme ho tady.
        inner = getattr(_mcp_app, "app", _mcp_app)
        async with inner.router.lifespan_context(inner):
            yield
    else:
        yield
    await close_pool()


app = FastAPI(title="Projects", lifespan=lifespan)

app.include_router(router_auth)
app.include_router(api_router)

if _mcp_app is not None:
    app.mount("/mcp", _mcp_app)

# sdílený brand look (převzato z AccessRequest/app/static/css)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# React SPA (druhý build v UI/, Vite base=/app/projects/, vstup index.projects.html)
mount_spa(
    app,
    os.getenv("PROJECTS_UI_DIST", "projects-ui-dist"),
    path="/app/projects",
    index_name="index.projects.html",
)

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "mcp": _mcp_app is not None}
