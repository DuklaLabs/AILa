"""MCP server služby Projects – napojení AI na projektový systém.

HTTP (streamable) transport namountovaný v `app/main.py` na `/mcp` (stejný
kontejner a port 8006). Nástroje jsou tenké obaly nad servisní vrstvou
(`app/services/`):

  * autentizace: hlavička ``Authorization: Bearer <token>`` (token z
    ``auth.web_sessions``, stejný jako cookie ``dl_session``). Bez platného
    tokenu nebo bez oprávnění ``projects.ai:use`` nástroj nic neudělá.
  * přímý zápis běží pod RBAC daného uživatele (stejně jako REST).
  * nevratná / citlivá operace (mazání, změna rozpočtu / skutečné ceny,
    lifecycle projektu) se nedělá přímo – vytvoří se ``projects.proposals``
    záznam přes ``propose_change`` a čeká na schválení člověkem.

Když balíček ``mcp`` není nainstalovaný, ``build_mcp()`` vrátí ``None`` a služba
běží bez MCP (REST + SPA fungují dál).
"""
from __future__ import annotations

import contextvars
import json
import os
from typing import Any, Optional

from fastapi import HTTPException

from ailacore.audit import record_audit
from ailacore.auth import get_user_from_token
from ailacore.db import get_pool
from ailacore.models import User
from ailacore.rbac import user_has_permission

from app.services import costs, proposals, tasks, time_tracking, tree

# Balíček mcp je volitelný. Podporujeme obě API:
#   * mcp >= 2:  from mcp.server.mcpserver import MCPServer
#   * mcp 1.x:   from mcp.server.fastmcp import FastMCP
# Obě mají stejný povrch, který používáme (`.tool()` dekorátor,
# `.streamable_http_app()`).
_MCP_V2 = False
try:
    from mcp.server.mcpserver import MCPServer as _MCPImpl  # type: ignore

    _MCP_V2 = True
except Exception:  # noqa: BLE001
    try:
        from mcp.server.fastmcp import FastMCP as _MCPImpl  # type: ignore
    except Exception:  # noqa: BLE001
        _MCPImpl = None  # type: ignore

_MCP_AVAILABLE = _MCPImpl is not None


_bearer_token: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "projects_mcp_bearer", default=None
)


class _BearerCtxMiddleware:
    """Čistá ASGI middleware – vytáhne bearer token z hlavičky do contextvaru,
    ať ho nástroje vidí bez ohledu na verzi MCP SDK."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = {k.lower(): v for k, v in (scope.get("headers") or [])}
            raw = headers.get(b"authorization", b"").decode()
            token = raw[7:].strip() if raw[:7].lower() == "bearer " else None
            _bearer_token.set(token)
        await self.app(scope, receive, send)


async def _current_user() -> User:
    user = await get_user_from_token(_bearer_token.get())
    if user is None:
        raise ValueError(
            "Chybí nebo neplatný token. Pošli hlavičku 'Authorization: Bearer <token>' "
            "(token z přihlášené session)."
        )
    if not await user_has_permission(user, "projects.ai:use"):
        raise ValueError("Účet nemá oprávnění 'projects.ai:use'.")
    return user


def _unwrap(exc: HTTPException) -> ValueError:
    return ValueError(f"{exc.status_code}: {exc.detail}")


async def _audit(user: User, action: str, target_type: str, target_id: Any, detail: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await record_audit(
                conn,
                actor=user,
                action=action,
                target_type=target_type,
                target_id=str(target_id),
                detail={**detail, "origin": "mcp"},
            )


def build_mcp():
    """Vrátí (FastMCP instance, ASGI app) nebo None, když MCP není dostupné /
    je vypnuté přes MCP_ENABLED."""
    if not _MCP_AVAILABLE:
        return None
    if os.getenv("MCP_ENABLED", "true").strip().lower() not in {"1", "true", "yes", "on", "ano"}:
        return None

    mcp = _MCPImpl("projects")

    # ---------------- čtení ----------------

    @mcp.tool()
    async def list_projects(folder_id: Optional[int] = None, status: Optional[str] = None) -> list[dict]:
        """Seznam projektů (volitelně filtr podle složky a stavu)."""
        user = await _current_user()
        try:
            return await tree.list_projects(user, folder_id=folder_id, status=status)
        except HTTPException as e:
            raise _unwrap(e)

    @mcp.tool()
    async def get_project(project_id: int) -> dict:
        """Detail projektu včetně jeho 5 fází."""
        user = await _current_user()
        try:
            return await tree.get_project(user, project_id)
        except HTTPException as e:
            raise _unwrap(e)

    @mcp.tool()
    async def list_folders() -> list[dict]:
        """Seznam složek workspace (Komerční prototypy / Interní R&D / Globální přehledy)."""
        user = await _current_user()
        try:
            return await tree.list_folders(user)
        except HTTPException as e:
            raise _unwrap(e)

    @mcp.tool()
    async def list_tasks(phase_id: Optional[int] = None, project_id: Optional[int] = None) -> list[dict]:
        """Úkoly ve fázi nebo v celém projektu (zadej phase_id nebo project_id)."""
        user = await _current_user()
        try:
            return await tasks.list_tasks(user, phase_id=phase_id, project_id=project_id)
        except HTTPException as e:
            raise _unwrap(e)

    @mcp.tool()
    async def get_task(task_id: int) -> dict:
        """Datová karta úkolu (řešitel, spolupracovníci, stav, timeline, náklady, závislosti)."""
        user = await _current_user()
        try:
            return await tasks.get_task(user, task_id)
        except HTTPException as e:
            raise _unwrap(e)

    @mcp.tool()
    async def get_project_costs(project_id: int, proto_version: Optional[str] = None) -> dict:
        """Součet přímých nákladů projektu: materiál + odpracované hodiny × sazba,
        včetně % čerpání rozpočtu. Volitelně filtr na verzi prototypu."""
        user = await _current_user()
        try:
            return await costs.project_costs(user, project_id, proto_version=proto_version)
        except HTTPException as e:
            raise _unwrap(e)

    @mcp.tool()
    async def list_my_time(task_id: Optional[int] = None) -> list[dict]:
        """Vlastní záznamy odpracovaného času (volitelně jen k jednomu úkolu)."""
        user = await _current_user()
        try:
            return await time_tracking.list_time_entries(user, task_id=task_id)
        except HTTPException as e:
            raise _unwrap(e)

    @mcp.tool()
    async def list_proposals(status: str = "pending") -> list[dict]:
        """Seznam návrhů změn od AI (vyžaduje oprávnění projects.proposal:review)."""
        user = await _current_user()
        try:
            return await proposals.list_proposals(user, status=status)
        except HTTPException as e:
            raise _unwrap(e)

    # ---------------- přímý zápis (pod RBAC uživatele) ----------------

    @mcp.tool()
    async def create_task(
        phase_id: int,
        title: str,
        description: Optional[str] = None,
        assignee_user_id: Optional[int] = None,
        status: str = "backlog",
        start_on: Optional[str] = None,
        due_on: Optional[str] = None,
        proto_version: Optional[str] = None,
        estimated_hours: Optional[float] = None,
        cost_type: Optional[str] = None,
        estimated_cost_czk: Optional[float] = None,
        order_status: Optional[str] = None,
    ) -> dict:
        """Založí nový úkol ve fázi. Datum ve tvaru YYYY-MM-DD."""
        user = await _current_user()
        try:
            row = await tasks.create_task(
                user,
                phase_id=phase_id,
                title=title,
                description=description,
                assignee_user_id=assignee_user_id,
                status=status,
                start_on=start_on,
                due_on=due_on,
                proto_version=proto_version,
                estimated_hours=estimated_hours,
                cost_type=cost_type,
                estimated_cost_czk=estimated_cost_czk,
                order_status=order_status,
            )
        except HTTPException as e:
            raise _unwrap(e)
        await _audit(user, "projects.task.create", "task", row["id"], {"title": title})
        return row

    @mcp.tool()
    async def update_task_fields(task_id: int, fields: dict) -> dict:
        """Úprava polí datové karty (title, description, status, start_on, due_on,
        proto_version, estimated_hours, cost_type, estimated_cost_czk, order_status).
        Skutečná cena a mazání jdou přes propose_change."""
        user = await _current_user()
        try:
            row = await tasks.update_task(user, task_id, fields)
        except HTTPException as e:
            raise _unwrap(e)
        await _audit(user, "projects.task.update", "task", task_id, {"fields": list(fields)})
        return row

    @mcp.tool()
    async def set_task_status(task_id: int, status: str) -> dict:
        """Přesune úkol v semaforu (backlog / in_progress / design_review / blocked / done)."""
        user = await _current_user()
        try:
            row = await tasks.set_task_status(user, task_id, status)
        except HTTPException as e:
            raise _unwrap(e)
        await _audit(user, "projects.task.status", "task", task_id, {"status": status})
        return row

    @mcp.tool()
    async def set_task_assignee(task_id: int, assignee_user_id: Optional[int] = None) -> dict:
        """Nastaví (nebo zruší) hlavního řešitele úkolu."""
        user = await _current_user()
        try:
            row = await tasks.set_task_assignee(user, task_id, assignee_user_id)
        except HTTPException as e:
            raise _unwrap(e)
        await _audit(user, "projects.task.assign", "task", task_id, {"assignee": assignee_user_id})
        return row

    @mcp.tool()
    async def add_time_entry(task_id: int, minutes: int, note: Optional[str] = None) -> dict:
        """Ruční zápis odpracovaného času na úkol (v minutách)."""
        user = await _current_user()
        try:
            row = await time_tracking.add_manual_entry(user, task_id, minutes=minutes, note=note)
        except HTTPException as e:
            raise _unwrap(e)
        await _audit(user, "projects.time.add", "task", task_id, {"minutes": minutes})
        return row

    # ---------------- návrh ke schválení člověkem ----------------

    @mcp.tool()
    async def propose_change(
        kind: str,
        target_type: str,
        target_id: int,
        payload: dict,
        summary: str,
    ) -> dict:
        """Navrhne nevratnou / citlivou změnu ke schválení člověkem. Nic se
        neprovede hned – vznikne záznam v projects.proposals (pending).

        kind ∈ {task.delete, project.update, finance.update, project.lifecycle}
          * task.delete       – target_type='task',    payload={}
          * project.update    – target_type='project', payload={name?,description?,started_on?,due_on?,lead_user_id?}
          * finance.update    – target_type='project', payload={planned_budget_czk: N}
                                nebo target_type='task', payload={actual_cost_czk: N}
          * project.lifecycle – target_type='project', payload={status: 'archived'|...} nebo {delete: true}
        """
        user = await _current_user()
        if isinstance(payload, str):
            payload = json.loads(payload)
        try:
            return await proposals.create_proposal(
                user,
                kind=kind,
                target_type=target_type,
                target_id=target_id,
                payload=payload,
                summary=summary,
                origin="mcp",
            )
        except HTTPException as e:
            raise _unwrap(e)

    # sub-app se mountuje na /mcp v main.py – ať endpoint není /mcp/mcp,
    # servíruje se uvnitř na kořeni "/".
    if _MCP_V2:
        try:
            from mcp.server.transport_security import TransportSecuritySettings

            # closed-network lab služba za sdíleným SSO – DNS-rebinding ochrana
            # by jen blokovala interní docker hostname.
            sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
        except Exception:  # noqa: BLE001
            sec = None
        asgi = mcp.streamable_http_app(streamable_http_path="/", transport_security=sec)
    else:
        try:
            mcp.settings.streamable_http_path = "/"
        except Exception:  # noqa: BLE001
            pass
        asgi = mcp.streamable_http_app()

    return mcp, _BearerCtxMiddleware(asgi)
