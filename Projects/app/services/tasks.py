"""Datová karta úkolu: CRUD, stav-semafor, řešitel + spolupracovníci, závislosti.

Model dle dodané specifikace + rozhodnutí uživatele (hybrid): 1 hlavní řešitel
(`assignee_user_id`) a volitelní spolupracovníci (`task_collaborators`).
Stav je 5stavový semafor (`TASK_STATUSES`).
"""
from datetime import date
from typing import Optional

from fastapi import HTTPException

from ailacore.db import get_pool
from ailacore.models import User

from app.services.base import (
    COST_TYPES,
    ORDER_STATUSES,
    TASK_STATUSES,
    require,
    validate_enum,
)

_TASK_FIELDS = (
    "id", "phase_id", "project_id", "title", "description", "assignee_user_id",
    "status", "start_on", "due_on", "baseline_due_on", "proto_version",
    "estimated_hours", "cost_type", "estimated_cost_czk", "actual_cost_czk",
    "order_status", "position", "created_by", "created_at", "updated_at", "done_at",
)
_TASK_COLS = ", ".join(_TASK_FIELDS)

# pole datové karty, která smí měnit běžný `projects.task:write`
_EDITABLE = {
    "title", "description", "status", "start_on", "due_on", "proto_version",
    "estimated_hours", "cost_type", "estimated_cost_czk", "order_status",
}
# změna těchto polí navíc vyžaduje `projects.finance:write`
_FINANCE_FIELDS = {"actual_cost_czk"}


async def _task_row(conn, task_id: int) -> dict:
    row = await conn.fetchrow(
        f"SELECT {_TASK_COLS} FROM projects.tasks WHERE id = $1", task_id
    )
    if row is None:
        raise HTTPException(404, "Úkol neexistuje.")
    collabs = await conn.fetch(
        "SELECT user_id FROM projects.task_collaborators WHERE task_id = $1", task_id
    )
    deps = await conn.fetch(
        "SELECT depends_on_task_id FROM projects.task_dependencies WHERE task_id = $1",
        task_id,
    )
    return {
        **dict(row),
        "collaborator_user_ids": [r["user_id"] for r in collabs],
        "depends_on_task_ids": [r["depends_on_task_id"] for r in deps],
    }


async def list_tasks(
    user: User,
    *,
    phase_id: Optional[int] = None,
    project_id: Optional[int] = None,
) -> list[dict]:
    await require(user, "projects.task:read")
    if phase_id is None and project_id is None:
        raise HTTPException(422, "Zadej phase_id nebo project_id.")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {_TASK_COLS} FROM projects.tasks
            WHERE ($1::int IS NULL OR phase_id = $1)
              AND ($2::int IS NULL OR project_id = $2)
            ORDER BY position, id
            """,
            phase_id,
            project_id,
        )
    return [dict(r) for r in rows]


async def get_task(user: User, task_id: int) -> dict:
    await require(user, "projects.task:read")
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await _task_row(conn, task_id)


async def create_task(
    user: User,
    *,
    phase_id: int,
    title: str,
    description: Optional[str] = None,
    assignee_user_id: Optional[int] = None,
    status: str = "backlog",
    start_on: Optional[date] = None,
    due_on: Optional[date] = None,
    proto_version: Optional[str] = None,
    estimated_hours: Optional[float] = None,
    cost_type: Optional[str] = None,
    estimated_cost_czk: Optional[float] = None,
    actual_cost_czk: Optional[float] = None,
    order_status: Optional[str] = None,
) -> dict:
    await require(user, "projects.task:write")
    if assignee_user_id is not None:
        await require(user, "projects.task:assign")
    if actual_cost_czk is not None:
        await require(user, "projects.finance:write")
    if not title or not title.strip():
        raise HTTPException(422, "Název úkolu je povinný.")
    validate_enum(status, TASK_STATUSES, "status")
    validate_enum(cost_type, COST_TYPES, "cost_type")
    validate_enum(order_status, ORDER_STATUSES, "order_status")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            phase = await conn.fetchrow(
                "SELECT project_id FROM projects.phases WHERE id = $1", phase_id
            )
            if phase is None:
                raise HTTPException(404, "Fáze neexistuje.")
            position = await conn.fetchval(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM projects.tasks WHERE phase_id = $1",
                phase_id,
            )
            done_at = "NOW()" if status == "done" else None
            task_id = await conn.fetchval(
                """
                INSERT INTO projects.tasks
                    (phase_id, project_id, title, description, assignee_user_id,
                     status, start_on, due_on, baseline_due_on, proto_version,
                     estimated_hours, cost_type, estimated_cost_czk, actual_cost_czk,
                     order_status, position, created_by, done_at)
                VALUES ($1, $2, $3, $4, $5, $6::text, $7, $8, $8, $9, $10, $11, $12, $13,
                        $14, $15, $16, CASE WHEN $6::text = 'done' THEN NOW() END)
                RETURNING id
                """,
                phase_id,
                phase["project_id"],
                title.strip(),
                description,
                assignee_user_id,
                status,
                start_on,
                due_on,
                proto_version,
                estimated_hours,
                cost_type,
                estimated_cost_czk,
                actual_cost_czk,
                order_status,
                position,
                user.id,
            )
            return await _task_row(conn, task_id)


async def update_task(user: User, task_id: int, fields: dict) -> dict:
    await require(user, "projects.task:write")

    changes = {k: v for k, v in fields.items() if k in _EDITABLE or k in _FINANCE_FIELDS}
    if not changes:
        raise HTTPException(422, "Žádné platné pole k úpravě.")
    if changes.keys() & _FINANCE_FIELDS:
        await require(user, "projects.finance:write")
    validate_enum(changes.get("status"), TASK_STATUSES, "status")
    validate_enum(changes.get("cost_type"), COST_TYPES, "cost_type")
    validate_enum(changes.get("order_status"), ORDER_STATUSES, "order_status")

    # $N pro `status` castíme na ::text ve všech výskytech (i v přiřazení do
    # sloupce), jinak asyncpg deduces "text versus character varying".
    set_parts = []
    status_param = None
    for i, k in enumerate(changes, start=2):
        if k == "status":
            status_param = i
            set_parts.append(f"status = ${i}::text")
        else:
            set_parts.append(f"{k} = ${i}")
    if status_param is not None:
        # done_at se plní při přechodu na 'done', maže při odchodu z něj
        set_parts.append(
            f"done_at = CASE WHEN ${status_param}::text = 'done' "
            f"THEN COALESCE(done_at, NOW()) ELSE NULL END"
        )
    set_sql = ", ".join(set_parts)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            updated = await conn.fetchval(
                f"UPDATE projects.tasks SET {set_sql}, updated_at = NOW() "
                f"WHERE id = $1 RETURNING id",
                task_id,
                *changes.values(),
            )
            if updated is None:
                raise HTTPException(404, "Úkol neexistuje.")
            return await _task_row(conn, task_id)


async def set_task_status(user: User, task_id: int, status: str) -> dict:
    validate_enum(status, TASK_STATUSES, "status")
    return await update_task(user, task_id, {"status": status})


async def set_task_assignee(user: User, task_id: int, assignee_user_id: Optional[int]) -> dict:
    await require(user, "projects.task:assign")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            updated = await conn.fetchval(
                "UPDATE projects.tasks SET assignee_user_id = $2, updated_at = NOW() "
                "WHERE id = $1 RETURNING id",
                task_id,
                assignee_user_id,
            )
            if updated is None:
                raise HTTPException(404, "Úkol neexistuje.")
            return await _task_row(conn, task_id)


async def set_task_collaborators(user: User, task_id: int, user_ids: list[int]) -> dict:
    await require(user, "projects.task:assign")
    ids = sorted({int(u) for u in user_ids})
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if not await conn.fetchval("SELECT 1 FROM projects.tasks WHERE id = $1", task_id):
                raise HTTPException(404, "Úkol neexistuje.")
            await conn.execute(
                "DELETE FROM projects.task_collaborators WHERE task_id = $1", task_id
            )
            if ids:
                await conn.executemany(
                    "INSERT INTO projects.task_collaborators (task_id, user_id) VALUES ($1, $2)",
                    [(task_id, uid) for uid in ids],
                )
            return await _task_row(conn, task_id)


async def add_task_dependency(user: User, task_id: int, depends_on_task_id: int) -> dict:
    await require(user, "projects.task:write")
    if task_id == depends_on_task_id:
        raise HTTPException(422, "Úkol nemůže záviset sám na sobě.")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                "SELECT id, project_id FROM projects.tasks WHERE id = ANY($1::int[])",
                [task_id, depends_on_task_id],
            )
            if len(rows) != 2:
                raise HTTPException(404, "Úkol nebo závislý úkol neexistuje.")
            if len({r["project_id"] for r in rows}) != 1:
                raise HTTPException(422, "Závislost lze vytvořit jen mezi úkoly téhož projektu.")
            await conn.execute(
                """
                INSERT INTO projects.task_dependencies (task_id, depends_on_task_id)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
                """,
                task_id,
                depends_on_task_id,
            )
            return await _task_row(conn, task_id)


async def remove_task_dependency(user: User, task_id: int, depends_on_task_id: int) -> dict:
    await require(user, "projects.task:write")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM projects.task_dependencies "
                "WHERE task_id = $1 AND depends_on_task_id = $2",
                task_id,
                depends_on_task_id,
            )
            return await _task_row(conn, task_id)


async def delete_task(user: User, task_id: int) -> dict:
    """Nevratné – přes REST pro `projects.task:write`; přes MCP jde tato
    operace výhradně cestou návrhu (`task.delete`)."""
    await require(user, "projects.task:write")
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute("DELETE FROM projects.tasks WHERE id = $1", task_id)
    if res == "DELETE 0":
        raise HTTPException(404, "Úkol neexistuje.")
    return {"deleted": task_id}
