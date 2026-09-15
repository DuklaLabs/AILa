from contextlib import asynccontextmanager

from ailacore.auth import get_current_user
from ailacore.db import close_pool
from ailacore.models import User
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.history import load_history
from app.orchestrator import run_general_command


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pool()


app = FastAPI(title="General AI Agent", lifespan=lifespan)

# Chat v portálovém shellu (UI/src/LabOrchestratorDashboard.jsx) běží na
# aila.localhost, General je za Gateway na vlastní subdoméně
# assistant.aila.localhost (viz Gateway/Caddyfile) – bez CORS by fetch
# z prohlížeče spadl. allow_credentials=True + explicitní origin (ne "*"),
# protože přihlášení jede přes dl_session cookie (ailacore.auth, sdílená
# doména .aila.localhost).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://aila.localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class PromptIn(BaseModel):
    prompt: str


@app.get("/general/me")
async def general_me(user: User = Depends(get_current_user)):
    return user


@app.get("/general/history")
async def general_history(user: User = Depends(get_current_user)):
    return await load_history(user.id)


@app.post("/general")
async def general_command(data: PromptIn, user: User = Depends(get_current_user)):
    return await run_general_command(user.id, data.prompt)
