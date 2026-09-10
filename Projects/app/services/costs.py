"""Finanční controlling prototypů.

Celkové přímé náklady projektu =
    Σ skutečných cen (materiál na úkolech)
  + (odpracované hodiny týmu × interní hodinová sazba)

Interní hodinová sazba je skryté fixní číslo (`projects.settings.hourly_rate_czk`,
default 500), viz `app/services/settings.py`.
"""
from typing import Optional

from fastapi import HTTPException

from ailacore.db import get_pool
from ailacore.models import User

from app.services.base import require
from app.services.settings import get_hourly_rate


def compute_project_costs(
    *,
    material_czk: float,
    minutes: float,
    hourly_rate_czk: float,
    planned_budget_czk: Optional[float],
) -> dict:
    """Čistá funkce – testovatelná bez DB."""
    material = round(float(material_czk or 0), 2)
    hours = round(float(minutes or 0) / 60, 2)
    labor = round(hours * float(hourly_rate_czk or 0), 2)
    total = round(material + labor, 2)
    budget = float(planned_budget_czk) if planned_budget_czk not in (None, 0) else None
    budget_pct = round(total / budget * 100, 1) if budget else None
    return {
        "material_czk": material,
        "labor_hours": hours,
        "labor_czk": labor,
        "total_czk": total,
        "hourly_rate_czk": round(float(hourly_rate_czk or 0), 2),
        "planned_budget_czk": budget,
        "budget_pct": budget_pct,
        "over_budget": bool(budget and total > budget),
    }


async def project_costs(
    user: User, project_id: int, *, proto_version: Optional[str] = None
) -> dict:
    await require(user, "projects.finance:read")
    pool = await get_pool()
    async with pool.acquire() as conn:
        proj = await conn.fetchrow(
            "SELECT id, name, planned_budget_czk FROM projects.projects WHERE id = $1",
            project_id,
        )
        if proj is None:
            raise HTTPException(404, "Projekt neexistuje.")
        material = await conn.fetchval(
            """
            SELECT COALESCE(SUM(actual_cost_czk), 0) FROM projects.tasks
            WHERE project_id = $1 AND ($2::text IS NULL OR proto_version = $2)
            """,
            project_id,
            proto_version,
        )
        minutes = await conn.fetchval(
            """
            SELECT COALESCE(SUM(te.minutes), 0)
            FROM projects.time_entries te
            JOIN projects.tasks t ON t.id = te.task_id
            WHERE t.project_id = $1
              AND te.minutes IS NOT NULL
              AND ($2::text IS NULL OR t.proto_version = $2)
            """,
            project_id,
            proto_version,
        )
    rate = await get_hourly_rate()
    result = compute_project_costs(
        material_czk=float(material),
        minutes=float(minutes),
        hourly_rate_czk=rate,
        planned_budget_czk=proj["planned_budget_czk"],
    )
    return {
        "project_id": project_id,
        "project_name": proj["name"],
        "proto_version": proto_version,
        **result,
    }
