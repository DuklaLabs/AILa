import os
from contextlib import asynccontextmanager

from ailacore.auth import get_current_user
from ailacore.db import close_pool
from ailacore.models import User
from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app.history import load_history
from app.orchestrator import run_general_command

# Cesta pod Gateway (viz Gateway/Caddyfile) – Caddy předává celou cestu
# beze stripu, takže služba musí sama vědět o svém prefixu.
PREFIX = os.getenv("URL_PREFIX", "").rstrip("/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pool()


app = FastAPI(title="General AI Agent", lifespan=lifespan)


class PromptIn(BaseModel):
    prompt: str


@app.get(f"{PREFIX}/general/me")
async def general_me(user: User = Depends(get_current_user)):
    return user


@app.get(f"{PREFIX}/general/history")
async def general_history(user: User = Depends(get_current_user)):
    return await load_history(user.id)


@app.post(f"{PREFIX}/general")
async def general_command(data: PromptIn, user: User = Depends(get_current_user)):
    return await run_general_command(user.id, data.prompt)
