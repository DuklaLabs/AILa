from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
import httpx

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()

# URL n8n webhooků
N8N_BASE = "http://localhost:5678"


# ---------------------------
# 🔵 RENDERING HTML STRÁNEK
# ---------------------------

@router.get("/admin")
async def render_admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@router.get("/login")
async def render_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/agent")
async def render_agent(request: Request):
    return templates.TemplateResponse("agent.html", {"request": request})


@router.get("/ui-test")
async def render_test(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------
# 🟣 N8N PROXY (UI → FastAPI → n8n)
# ---------------------------

api = APIRouter(prefix="/api", tags=["Proxy API"])


async def forward_to_n8n(method: str, path: str, data=None):
    url = f"{N8N_BASE}{path}"

    async with httpx.AsyncClient() as client:
        if method == "POST":
            r = await client.post(url, json=data)
        elif method == "GET":
            r = await client.get(url)
        else:
            raise RuntimeError("Unsupported HTTP method.")

    return r.json()


# ------- jednotlivé proxy endpointy -------

@api.post("/config-open-hours")
async def save_open_hours(request: Request):
    body = await request.json()
    return await forward_to_n8n("POST", "/webhook/config-open-hours", data=body)


@api.get("/list-slots")
async def list_slots():
    return await forward_to_n8n("GET", "/webhook/admin_list_slots")


@api.get("/agent-summary")
async def agent_summary():
    return await forward_to_n8n("GET", "/webhook/admin_agent_summary")


@api.get("/agent-log")
async def agent_log():
    return await forward_to_n8n("GET", "/webhook/admin_agent_log")


@api.post("/agent-chat")
async def agent_chat(request: Request):
    body = await request.json()
    return await forward_to_n8n("POST", "/webhook/admin_agent_chat", data=body)


# API router připojíme k hlavnímu routeru
router.include_router(api)
