"""Registr strojů a jejich provozní stav – "kontrola strojů" (databanka
sekce 9/21): jedno místo, kde je vidět, co se s jakým strojem právě děje.
Rezervace budoucích termínů řeší jiný modul (`lab.reservation:*`); tohle je
aktuální stav "běží / volný / porucha / mimo provoz" + volná poznámka.

    GET    /api/machines               (přihlášený uživatel – i student)
    POST   /api/machines               (lab.machine:manage)  {name, type, location?}
    PATCH  /api/machines/{id}/status   (lab.machine:manage)  {status, note?}
    DELETE /api/machines/{id}          (lab.machine:manage)  – vyřadí (is_active=false)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ailacore.auth import get_current_user
from ailacore.db import get_pool
from ailacore.models import User
from ailacore.rbac import require_permission

router_machines = APIRouter(tags=["Machines"])

_STATUSES = {"idle", "running", "broken", "offline"}
_MANAGE = Depends(require_permission("lab.machine:manage"))

_SELECT = """
    SELECT id, name, type, location, is_active, status, status_note, status_updated_at
    FROM lab.machines
"""


class MachineIn(BaseModel):
    name: str
    type: str
    location: str | None = None


class StatusIn(BaseModel):
    status: str
    note: str | None = None


@router_machines.get("/api/machines")
async def list_machines(user: User = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            _SELECT + " WHERE is_active ORDER BY type, name"
        )
    return [dict(r) for r in rows]


@router_machines.post("/api/machines")
async def create_machine(payload: MachineIn, _: User = _MANAGE):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO lab.machines (name, type, location) VALUES ($1, $2, $3) "
            "RETURNING id",
            payload.name, payload.type, payload.location,
        )
    return {"status": "ok", "id": row["id"]}


@router_machines.patch("/api/machines/{machine_id}/status")
async def set_machine_status(machine_id: int, payload: StatusIn, _: User = _MANAGE):
    if payload.status not in _STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Neplatný stav: {payload.status} (povoleno: {', '.join(sorted(_STATUSES))})",
        )
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE lab.machines SET status=$1, status_note=$2, status_updated_at=NOW() "
            "WHERE id=$3",
            payload.status, payload.note, machine_id,
        )
    if res == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Stroj nenalezen.")
    return {"status": "ok"}


@router_machines.delete("/api/machines/{machine_id}")
async def deactivate_machine(machine_id: int, _: User = _MANAGE):
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE lab.machines SET is_active = FALSE WHERE id = $1", machine_id
        )
    if res == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Stroj nenalezen.")
    return {"status": "ok"}
