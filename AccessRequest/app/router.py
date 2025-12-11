from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx

from app.auth import require_login

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# URL n8n (interní server nebo docker service)
N8N_BASE = "http://n8n:5678"
N8N_WEBHOOK_book_hour = f"{N8N_BASE}/webhook/book-hour"

# ---------------------------
# HTML stránky (admin, agent)
# ---------------------------

@router.get("/admin")
async def render_admin(request: Request):
    if not require_login(request):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("admin.html", {"request": request})


@router.get("/agent")
async def render_agent(request: Request):
    if not require_login(request):
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("agent.html", {"request": request})

@router.get("/student-hours")
async def student_hours(request: Request):
    return templates.TemplateResponse("student_hours.html", {"request": request})


# ---------------------------
# n8n PROXY (UI → FastAPI → n8n)
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

    r.raise_for_status()
    return r.json()
import requests

AGENT_URL = "http://dukla-agent:8001/run"


@api.post("/book-hour")
async def send_excuse_request(email: str, hour_id: int):
    payload = {
        "email": email,
        "hour_id": hour_id
    }

    r = requests.post(AGENT_URL, json=payload, timeout=10)
    return {"detail": "Přihláška byla odeslána ke zpracování."}


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


router.include_router(api)
