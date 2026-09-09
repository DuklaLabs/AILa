"""Hierarchie: workspace → složka → projekt → fáze.

Nový projekt se zakládá ze standardizované šablony – fáze se kopírují
z `projects.phase_templates` (5 kanonických fází).
"""
from datetime import date
from typing import Optional

from fastapi import HTTPException

from ailacore.db import get_pool
from ailacore.models import User

from app.services.base import PROJECT_STATUSES, require, validate_enum

_PROJECT_FIELDS = (
    "id", "folder_id", "name", "description", "status", "planned_budget_czk",
    "started_on", "due_on", "baseline_due_on", "lead_user_id", "created_by",
    "created_at", "updated_at",
)
_PROJECT_COLS = ", ".join(_PROJECT_FIELDS)
_PROJECT_COLS_P = ", ".join(f"p.{f}" for f in _PROJECT_FIELDS)


async def list_workspaces(user: User) -> list[dict]:
    await require(user, "projects.project:read")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, created_at FROM projects.workspaces ORDER BY id"
        )
    return [dict(r) for r in rows]


async def list_folders(user: User, *, workspace_id: Optional[int] = None) -> list[dict]:
    await require(user, "projects.project:read")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, workspace_id, name, kind, position, created_at
            FROM projects.folders
            WHERE ($1::int IS NULL OR workspace_id = $1)
            ORDER BY position, id
            """,
            workspace_id,
        )
    return [dict(r) for r in rows]


async def list_projects(
    user: User,
    *,
    folder_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[dict]:
    await require(user, "projects.project:read")
    validate_enum(status, PROJECT_STATUSES, "status")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {_PROJECT_COLS_P},
                   f.name AS folder_name, f.kind AS folder_kind,
                   (SELECT count(*) FROM projects.tasks t WHERE t.project_id = p.id) AS task_count
            FROM projects.projects p
            JOIN projects.folders f ON f.id = p.folder_id
            WHERE ($1::int IS NULL OR p.folder_id = $1)
              AND ($2::text IS NULL OR p.status = $2)
            ORDER BY p.created_at DESC, p.id DESC
            """,
            folder_id,
            status,
        )
    return [dict(r) for r in rows]


async def get_project(user: User, project_id: int) -> dict:
    await require(user, "projects.project:read")
    pool = await get_pool()
    async with pool.acquire() as conn:
        proj = await conn.fetchrow(
            f"""
            SELECT {_PROJECT_COLS_P}, f.name AS folder_name, f.kind AS folder_kind
            FROM projects.projects p
            JOIN projects.folders f ON f.id = p.folder_id
            WHERE p.id = $1
            """,
            project_id,
        )
        if proj is None:
            raise HTTPException(404, "Projekt neexistuje.")
        phases = await conn.fetch(
            "SELECT id, name, position FROM projects.phases "
            "WHERE project_id = $1 ORDER BY position",
            project_id,
        )
    return {**dict(proj), "phases": [dict(p) for p in phases]}


async def list_phases(user: User, project_id: int) -> list[dict]:
    await require(user, "projects.project:read")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, project_id, name, position FROM projects.phases "
            "WHERE project_id = $1 ORDER BY position",
            project_id,
        )
    return [dict(r) for r in rows]


async def create_project(
    user: User,
    *,
    folder_id: int,
    name: str,
    description: Optional[str] = None,
    planned_budget_czk: Optional[float] = None,
    started_on: Optional[date] = None,
    due_on: Optional[date] = None,
    lead_user_id: Optional[int] = None,
) -> dict:
    await require(user, "projects.project:write")
    if planned_budget_czk is not None:
        await require(user, "projects.finance:write")
    if not name or not name.strip():
        raise HTTPException(422, "Název projektu je povinný.")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if not await conn.fetchval(
                "SELECT 1 FROM projects.folders WHERE id = $1", folder_id
            ):
                raise HTTPException(404, "Složka neexistuje.")
            proj_id = await conn.fetchval(
                """
                INSERT INTO projects.projects
                    (folder_id, name, description, planned_budget_czk,
                     started_on, due_on, baseline_due_on, lead_user_id, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8)
                RETURNING id
                """,
                folder_id,
                name.strip(),
                description,
                planned_budget_czk,
                started_on,
                due_on,
                lead_user_id,
                user.id,
            )
            # fáze ze standardizované šablony
            await conn.execute(
                """
                INSERT INTO projects.phases (project_id, name, position)
                SELECT $1, name, position FROM projects.phase_templates ORDER BY position
                """,
                proj_id,
            )
    return await get_project(user, proj_id)


async def update_project(user: User, project_id: int, fields: dict) -> dict:
    """Úprava projektu. `planned_budget_czk` a `status` navíc vyžadují
    `projects.finance:write` (rozpočet je citlivý, změna stavu je lifecycle)."""
    await require(user, "projects.project:write")

    allowed = {
        "name", "description", "status", "planned_budget_czk",
        "started_on", "due_on", "baseline_due_on", "lead_user_id",
    }
    changes = {k: v for k, v in fields.items() if k in allowed}
    if not changes:
        raise HTTPException(422, "Žádné platné pole k úpravě.")
    if "planned_budget_czk" in changes or "status" in changes:
        await require(user, "projects.finance:write")
    validate_enum(changes.get("status"), PROJECT_STATUSES, "status")

    set_sql = ", ".join(f"{k} = ${i}" for i, k in enumerate(changes, start=2))
    pool = await get_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchval(
            f"UPDATE projects.projects SET {set_sql}, updated_at = NOW() "
            f"WHERE id = $1 RETURNING id",
            project_id,
            *changes.values(),
        )
    if updated is None:
        raise HTTPException(404, "Projekt neexistuje.")
    return await get_project(user, project_id)


async def delete_project(user: User, project_id: int) -> dict:
    """Nevratné – přes REST jen pro `projects.project:write` + `finance:write`;
    přes MCP jde tato operace výhradně cestou návrhu (`project.lifecycle`)."""
    await require(user, "projects.project:write")
    await require(user, "projects.finance:write")
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM projects.projects WHERE id = $1", project_id)
    if res == "DELETE 0":
        raise HTTPException(404, "Projekt neexistuje.")
    return {"deleted": project_id}
