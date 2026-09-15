"""Vstupní bod služby access-agents.

FastAPI s:
  GET  /healthz          – stav + seznam agentů a naplánovaných jobů
  POST /run/{agent}      – ruční spuštění agenta (mimo plánovač)
  GET  /agents           – registr agentů

Plánovač se spouští na startu (gated `ACCESS_AGENT_ENABLED`).

Autorizace `POST /run`: buď přihlášený uživatel s oprávněním `agent.run:trigger`
(cookie/bearer přes ailacore.auth), nebo shodný `X-Agent-Token` s env
`ACCESS_AGENT_RUN_TOKEN` (pro skripty a lokální testování).
"""
from __future__ import annotations

import os

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request

from ailacore.db import close_pool
from ailacore.dukla import close_dukla_pool
from ailacore.rbac import user_has_permission
from ailacore.auth import SESSION_COOKIE, get_user_from_token

from app.agents import AGENTS
from app.scheduler import enabled, get_jobs, shutdown_scheduler, start_scheduler

app = FastAPI(title="AccessAgents")


@app.on_event("startup")
async def _startup() -> None:
    start_scheduler()


@app.on_event("shutdown")
async def _shutdown() -> None:
    shutdown_scheduler()
    await close_pool()
    await close_dukla_pool()


async def _authorize_run(
    request: Request,
    x_agent_token: str | None = Header(default=None),
) -> None:
    secret = os.getenv("ACCESS_AGENT_RUN_TOKEN", "").strip()
    if secret and x_agent_token and x_agent_token == secret:
        return
    token = request.cookies.get(SESSION_COOKIE)
    auth = request.headers.get("Authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    user = await get_user_from_token(token) if token else None
    if user is None or not await user_has_permission(user, "agent.run:trigger"):
        raise HTTPException(
            status_code=403, detail="Missing permission: agent.run:trigger"
        )


@app.get("/healthz")
async def healthz() -> dict:
    return {
        "status": "ok",
        "scheduler_enabled": enabled(),
        "jobs": get_jobs(),
        "agents": sorted(AGENTS),
    }


@app.get("/agents")
async def list_agents() -> dict:
    return {"agents": sorted(AGENTS)}


@app.post("/run/{agent}", dependencies=[Depends(_authorize_run)])
async def run_agent(agent: str) -> dict:
    if agent not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Neznámý agent: {agent}")
    return await AGENTS[agent](trigger="manual")


if __name__ == "__main__":
    uvicorn.run(
        "app.run:app", host="0.0.0.0", port=int(os.getenv("PORT", "8007")),
    )
