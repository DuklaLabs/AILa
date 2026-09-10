"""RBAC admin API + servírování React konzole – sdílené pro všechny AILa služby.

Služba si to zapojí dvěma řádky v `main.py`:

    from ailacore.admin import rbac_api_router, mount_admin_ui
    app.include_router(rbac_api_router)
    mount_admin_ui(app, os.getenv("RBAC_UI_DIST", "rbac-ui-dist"))

`rbac_api_router` je čisté JSON API pod `/api/rbac`, chráněné `require_permission`
z `ailacore.rbac` (katalog oprávnění z migrace 0014: `admin` má přes `*` vše,
`staff` tahle oprávnění nemá → konzole je defaultně jen pro adminy).

`mount_admin_ui` naservíruje buildnutou SPA (`UI/`, Vite `base=/admin/rbac/`) na
stejném originu jako API, aby fungovala cookie session `dl_session`. Když build
neexistuje (dev `pip install -e` bez `npm run build`), jen zaloguje a přeskočí.

Každá mutace zapisuje do `auth.audit_log` (přes `ailacore.audit.record_audit`,
ve stejné transakci) a invaliduje cache oprávnění (`clear_permission_cache`).
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .audit import record_audit
from .auth import SESSION_COOKIE, get_current_user, get_user_from_token
from .db import get_pool
from .models import User
from .rbac import (
    clear_permission_cache,
    get_effective_permissions,
    granted_covers,
    require_permission,
)

log = logging.getLogger(__name__)

rbac_api_router = APIRouter(prefix="/api/rbac", tags=["RBAC"])

_MANAGE = "auth.role:manage"
_USER_READ = "auth.user:read"
_USER_WRITE = "auth.user:write"
_GRANT = "auth.permission:grant"

# `require_permission` je factory – zavolat jednou, výsledek dát jako default
# hodnotu parametru handleru (`actor: User = _dep_manage`): guard i identita aktéra.
_dep_manage = Depends(require_permission(_MANAGE))
_dep_user_read = Depends(require_permission(_USER_READ))
_dep_user_write = Depends(require_permission(_USER_WRITE))
_dep_grant = Depends(require_permission(_GRANT))


# --- čisté pomocné funkce (testovatelné bez DB) -----------------------------

def diff_set(current, desired) -> tuple[set[str], set[str]]:
    """Vrátí (přidat, odebrat) pro přechod z `current` do `desired`."""
    cur, des = set(current), set(desired)
    return des - cur, cur - des


def validate_role_assignment(primary: str, secondary, known_roles) -> None:
    known = set(known_roles)
    if primary not in known:
        raise HTTPException(422, f"Neznámá role: {primary}")
    unknown = sorted({r for r in secondary if r not in known})
    if unknown:
        raise HTTPException(422, f"Neznámé role: {', '.join(unknown)}")
    if primary in set(secondary):
        raise HTTPException(422, f"Primární role '{primary}' nemůže být zároveň sekundární.")


def validate_permission_names(names, catalog, *, allow_wildcard: bool) -> None:
    cat = set(catalog)
    unknown = sorted({n for n in names if n not in cat})
    if unknown:
        raise HTTPException(422, f"Oprávnění mimo katalog: {', '.join(unknown)}")
    if not allow_wildcard and "*" in set(names):
        raise HTTPException(422, "Oprávnění '*' nelze přidělit přímo uživateli.")


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _jsonb(value):
    return json.loads(value) if isinstance(value, str) else value


# --- request modely --------------------------------------------------------

class PermissionIn(BaseModel):
    name: str
    description: Optional[str] = None


class RoleIn(BaseModel):
    name: str
    description: Optional[str] = None


class RolePatch(BaseModel):
    description: Optional[str] = None


class PermissionListIn(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class RoleAssignmentIn(BaseModel):
    primary: str
    secondary: list[str] = Field(default_factory=list)


# --- katalog oprávnění ---------------------------------------------------

@rbac_api_router.get("/permissions")
async def list_permissions(actor: User = _dep_manage):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT name, description FROM auth.permissions ORDER BY name"
        )
    return [dict(r) for r in rows]


@rbac_api_router.post("/permissions", status_code=201)
async def create_permission(body: PermissionIn, request: Request, actor: User = _dep_manage):
    name = body.name.strip()
    if not name or len(name) > 96:
        raise HTTPException(422, "Jméno oprávnění musí být 1–96 znaků.")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if await conn.fetchval("SELECT 1 FROM auth.permissions WHERE name = $1", name):
                raise HTTPException(409, f"Oprávnění '{name}' už existuje.")
            await conn.execute(
                "INSERT INTO auth.permissions (name, description) VALUES ($1, $2)",
                name, body.description,
            )
            await record_audit(
                conn, actor=actor, action="permission.create",
                target_type="permission", target_id=name,
                detail={"description": body.description}, ip=_ip(request),
            )
    return {"name": name, "description": body.description}


@rbac_api_router.delete("/permissions/{name}")
async def delete_permission(
    name: str, request: Request, cascade: bool = False, actor: User = _dep_manage
):
    if name == "*":
        raise HTTPException(403, "Oprávnění '*' nelze smazat.")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if not await conn.fetchval("SELECT 1 FROM auth.permissions WHERE name = $1", name):
                raise HTTPException(404, f"Oprávnění '{name}' neexistuje.")
            n_roles = await conn.fetchval(
                "SELECT count(*) FROM auth.role_permissions WHERE permission_name = $1", name
            )
            n_grants = await conn.fetchval(
                "SELECT count(*) FROM auth.user_permissions WHERE permission_name = $1", name
            )
            if (n_roles or n_grants) and not cascade:
                raise HTTPException(
                    409,
                    f"Používá se: {n_roles} rolí, {n_grants} přímých grantů. "
                    f"Pro smazání i s vazbami přidej ?cascade=true.",
                )
            # FK role_permissions/user_permissions -> permissions je ON DELETE CASCADE
            await conn.execute("DELETE FROM auth.permissions WHERE name = $1", name)
            await record_audit(
                conn, actor=actor, action="permission.delete",
                target_type="permission", target_id=name,
                detail={"cascade": bool(cascade), "roles": n_roles, "grants": n_grants},
                ip=_ip(request),
            )
    clear_permission_cache()
    return {"deleted": name}


# --- role ---------------------------------------------------------------

@rbac_api_router.get("/roles")
async def list_roles(actor: User = _dep_manage):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT r.name, r.description, r.is_system,
                   COALESCE(
                       array_agg(rp.permission_name ORDER BY rp.permission_name)
                       FILTER (WHERE rp.permission_name IS NOT NULL),
                       '{}'
                   ) AS permissions
            FROM auth.roles r
            LEFT JOIN auth.role_permissions rp ON rp.role_name = r.name
            GROUP BY r.name, r.description, r.is_system
            ORDER BY r.name
            """
        )
    return [dict(r) for r in rows]


@rbac_api_router.post("/roles", status_code=201)
async def create_role(body: RoleIn, request: Request, actor: User = _dep_manage):
    name = body.name.strip()
    if not name or len(name) > 32 or not all(c.isalnum() or c in "_-" for c in name):
        raise HTTPException(422, "Jméno role: 1–32 znaků, jen písmena/číslice/_/-.")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if await conn.fetchval("SELECT 1 FROM auth.roles WHERE name = $1", name):
                raise HTTPException(409, f"Role '{name}' už existuje.")
            await conn.execute(
                "INSERT INTO auth.roles (name, description, is_system) VALUES ($1, $2, FALSE)",
                name, body.description,
            )
            await record_audit(
                conn, actor=actor, action="role.create",
                target_type="role", target_id=name,
                detail={"description": body.description}, ip=_ip(request),
            )
    return {"name": name, "description": body.description, "is_system": False, "permissions": []}


@rbac_api_router.patch("/roles/{name}")
async def patch_role(name: str, body: RolePatch, request: Request, actor: User = _dep_manage):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT description FROM auth.roles WHERE name = $1", name
            )
            if row is None:
                raise HTTPException(404, f"Role '{name}' neexistuje.")
            await conn.execute(
                "UPDATE auth.roles SET description = $2 WHERE name = $1", name, body.description
            )
            await record_audit(
                conn, actor=actor, action="role.update",
                target_type="role", target_id=name,
                detail={"before": row["description"], "after": body.description},
                ip=_ip(request),
            )
    return {"name": name, "description": body.description}


@rbac_api_router.delete("/roles/{name}")
async def delete_role(name: str, request: Request, actor: User = _dep_manage):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT is_system FROM auth.roles WHERE name = $1", name
            )
            if row is None:
                raise HTTPException(404, f"Role '{name}' neexistuje.")
            if row["is_system"]:
                raise HTTPException(403, f"Systémovou roli '{name}' nelze smazat.")
            n_primary = await conn.fetchval(
                "SELECT count(*) FROM auth.users WHERE role = $1", name
            )
            if n_primary:
                raise HTTPException(
                    409,
                    f"Role '{name}' je primární rolí {n_primary} účtů – nejdřív je přeřaď.",
                )
            # auth.user_roles -> roles je ON DELETE CASCADE (sekundární přiřazení zmizí)
            n_secondary = await conn.fetchval(
                "SELECT count(*) FROM auth.user_roles WHERE role_name = $1", name
            )
            await conn.execute("DELETE FROM auth.roles WHERE name = $1", name)
            await record_audit(
                conn, actor=actor, action="role.delete",
                target_type="role", target_id=name,
                detail={"secondary_assignments_removed": n_secondary}, ip=_ip(request),
            )
    clear_permission_cache()
    return {"deleted": name}


@rbac_api_router.put("/roles/{name}/permissions")
async def set_role_permissions(
    name: str, body: PermissionListIn, request: Request, actor: User = _dep_manage
):
    desired = sorted(set(body.permissions))
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if not await conn.fetchval("SELECT 1 FROM auth.roles WHERE name = $1", name):
                raise HTTPException(404, f"Role '{name}' neexistuje.")
            catalog = [r["name"] for r in await conn.fetch("SELECT name FROM auth.permissions")]
            validate_permission_names(desired, catalog, allow_wildcard=True)
            current = [
                r["permission_name"] for r in await conn.fetch(
                    "SELECT permission_name FROM auth.role_permissions WHERE role_name = $1", name
                )
            ]
            to_add, to_remove = diff_set(current, desired)
            if to_remove:
                await conn.execute(
                    "DELETE FROM auth.role_permissions "
                    "WHERE role_name = $1 AND permission_name = ANY($2::text[])",
                    name, list(to_remove),
                )
            if to_add:
                await conn.executemany(
                    "INSERT INTO auth.role_permissions (role_name, permission_name) VALUES ($1, $2)",
                    [(name, p) for p in to_add],
                )
            if to_add or to_remove:
                await record_audit(
                    conn, actor=actor, action="role.permissions.set",
                    target_type="role", target_id=name,
                    detail={"added": sorted(to_add), "removed": sorted(to_remove)},
                    ip=_ip(request),
                )
    clear_permission_cache()
    return {"role": name, "permissions": desired}


# --- uživatelé ---------------------------------------------------------

@rbac_api_router.get("/users")
async def list_users(
    q: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    actor: User = _dep_user_read,
):
    like = f"%{q}%" if q else None
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.id, u.username, u.full_name, u.role AS primary_role,
                   COALESCE(array_agg(DISTINCT ur.role_name)
                            FILTER (WHERE ur.role_name IS NOT NULL), '{}') AS secondary_roles,
                   COALESCE(array_agg(DISTINCT up.permission_name)
                            FILTER (WHERE up.permission_name IS NOT NULL), '{}') AS direct_permissions
            FROM auth.users u
            LEFT JOIN auth.user_roles ur ON ur.user_id = u.id
            LEFT JOIN auth.user_permissions up ON up.user_id = u.id AND up.resource_id IS NULL
            WHERE ($1::text IS NULL OR u.username ILIKE $1 OR u.full_name ILIKE $1)
            GROUP BY u.id
            ORDER BY u.username
            LIMIT $2
            """,
            like, limit,
        )
    return [dict(r) for r in rows]


@rbac_api_router.put("/users/{user_id}/roles")
async def set_user_roles(
    user_id: int, body: RoleAssignmentIn, request: Request, actor: User = _dep_user_write
):
    secondary = sorted(set(body.secondary))
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            urow = await conn.fetchrow(
                "SELECT role FROM auth.users WHERE id = $1", user_id
            )
            if urow is None:
                raise HTTPException(404, f"Uživatel {user_id} neexistuje.")
            known = [r["name"] for r in await conn.fetch("SELECT name FROM auth.roles")]
            validate_role_assignment(body.primary, secondary, known)

            primary_before = urow["role"]
            if body.primary != primary_before:
                await conn.execute(
                    "UPDATE auth.users SET role = $2, updated_at = NOW() WHERE id = $1",
                    user_id, body.primary,
                )
            current = [
                r["role_name"] for r in await conn.fetch(
                    "SELECT role_name FROM auth.user_roles WHERE user_id = $1", user_id
                )
            ]
            to_add, to_remove = diff_set(current, secondary)
            if to_remove:
                await conn.execute(
                    "DELETE FROM auth.user_roles "
                    "WHERE user_id = $1 AND role_name = ANY($2::text[])",
                    user_id, list(to_remove),
                )
            if to_add:
                await conn.executemany(
                    "INSERT INTO auth.user_roles (user_id, role_name, granted_by) VALUES ($1, $2, $3)",
                    [(user_id, r, actor.id) for r in to_add],
                )
            await record_audit(
                conn, actor=actor, action="user.roles.set",
                target_type="user", target_id=str(user_id),
                detail={
                    "primary_before": primary_before, "primary_after": body.primary,
                    "secondary_added": sorted(to_add), "secondary_removed": sorted(to_remove),
                },
                ip=_ip(request),
            )
    clear_permission_cache(user_id)
    return {"user_id": user_id, "primary": body.primary, "secondary": secondary}


@rbac_api_router.put("/users/{user_id}/permissions")
async def set_user_permissions(
    user_id: int, body: PermissionListIn, request: Request, actor: User = _dep_grant
):
    desired = sorted(set(body.permissions))
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if not await conn.fetchval("SELECT 1 FROM auth.users WHERE id = $1", user_id):
                raise HTTPException(404, f"Uživatel {user_id} neexistuje.")
            catalog = [r["name"] for r in await conn.fetch("SELECT name FROM auth.permissions")]
            validate_permission_names(desired, catalog, allow_wildcard=False)
            current = [
                r["permission_name"] for r in await conn.fetch(
                    "SELECT permission_name FROM auth.user_permissions "
                    "WHERE user_id = $1 AND resource_id IS NULL",
                    user_id,
                )
            ]
            to_add, to_remove = diff_set(current, desired)
            if to_remove:
                await conn.execute(
                    "DELETE FROM auth.user_permissions "
                    "WHERE user_id = $1 AND resource_id IS NULL "
                    "AND permission_name = ANY($2::text[])",
                    user_id, list(to_remove),
                )
            if to_add:
                await conn.executemany(
                    "INSERT INTO auth.user_permissions "
                    "(user_id, permission_name, granted_by) VALUES ($1, $2, $3)",
                    [(user_id, p, actor.id) for p in to_add],
                )
            if to_add or to_remove:
                await record_audit(
                    conn, actor=actor, action="user.grants.set",
                    target_type="user", target_id=str(user_id),
                    detail={"added": sorted(to_add), "removed": sorted(to_remove)},
                    ip=_ip(request),
                )
    clear_permission_cache(user_id)
    return {"user_id": user_id, "permissions": desired}


# --- audit + self ----------------------------------------------------

@rbac_api_router.get("/audit")
async def list_audit(
    limit: int = Query(100, ge=1, le=1000),
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    actor: User = _dep_manage,
):
    where = ["TRUE"]
    args: list = []
    if target_type:
        args.append(target_type)
        where.append(f"target_type = ${len(args)}")
    if target_id:
        args.append(str(target_id))
        where.append(f"target_id = ${len(args)}")
    args.append(limit)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                   actor_id, actor_name, action, target_type, target_id, detail, ip
            FROM auth.audit_log
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC, id DESC
            LIMIT ${len(args)}
            """,
            *args,
        )
    return [{**dict(r), "detail": _jsonb(r["detail"])} for r in rows]


@rbac_api_router.get("/effective")
async def my_effective(user: User = Depends(get_current_user)):
    perms = await get_effective_permissions(user.id, user.role)
    return {
        "user": {"id": user.id, "username": user.username, "role": user.role},
        "permissions": sorted(perms),
        "can_manage": granted_covers(perms, _MANAGE),
    }


# --- servírování SPA ------------------------------------------------

def mount_spa(
    app,
    dist_dir,
    *,
    path: str,
    login_url: str = "/login",
    assets_name: str | None = None,
    index_name: str = "index.html",
) -> None:
    """Naservíruje buildnutou React SPA (`dist_dir`, Vite `base=<path>/`) na `path`.

    - `path` musí sedět s Vite `base` (kvůli odkazům na `<path>/assets/...`).
    - `index_name` je název vstupního HTML v `dist_dir` (Vite ho pojmenuje podle
      zdrojového souboru – druhý build v jednom `UI/` má typicky `index.<x>.html`).
    - SPA je za přihlášením: bez platné session `dl_session` → redirect na `login_url`.
    - Když build neexistuje (dev `pip install -e` bez `npm run build`), jen zaloguje
      varování a nic nemountuje – API služby běží dál.

    Sdílené, ať to nemusí každá služba s vlastní SPA psát znovu
    (`mount_admin_ui` je jen tenké zavolání s `path="/admin/rbac"`).
    """
    dist = Path(dist_dir)
    index = dist / index_name
    if not index.is_file():
        log.warning(
            "SPA %s: %s neexistuje – nemountuje se (API služby běží dál).", path, index
        )
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount(
            f"{path}/assets",
            StaticFiles(directory=str(assets)),
            name=assets_name or f"spa-assets-{path.strip('/').replace('/', '-')}",
        )

    dist_root = dist.resolve()

    async def _serve_spa(request: Request, rest: str = ""):
        if await get_user_from_token(request.cookies.get(SESSION_COOKIE)) is None:
            return RedirectResponse(url=login_url)
        if rest:
            candidate = (dist / rest).resolve()
            if candidate.is_file() and dist_root in candidate.parents:
                return FileResponse(str(candidate))
        return FileResponse(str(index))

    app.add_api_route(path, _serve_spa, methods=["GET"], include_in_schema=False)
    app.add_api_route(f"{path}/{{rest:path}}", _serve_spa, methods=["GET"], include_in_schema=False)
    log.info("SPA namountováno na %s (z %s)", path, dist)


def mount_admin_ui(app, dist_dir, *, path: str = "/admin/rbac") -> None:
    """Naservíruje sdílenou RBAC konzoli (`UI/dist`) na `path`. Viz `mount_spa`."""
    mount_spa(app, dist_dir, path=path, assets_name="rbac-ui-assets")
