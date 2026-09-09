"""Granulární RBAC sdílený všemi AILa službami.

Doplněk k `ailacore.auth.require_role` (hrubá kontrola jedné role). Tady je
kontrola na úrovni jednotlivých oprávnění pojmenovaných `schema.resource:action`
(např. `internal.open_hours:write`).

Efektivní oprávnění uživatele = sjednocení:
  - oprávnění primární role (`auth.users.role` → `auth.role_permissions`),
  - oprávnění všech sekundárních rolí (`auth.user_roles`),
  - přímých per-user grantů (`auth.user_permissions`).

Wildcard je povolený jen v *přidělené* množině, ne v požadavku:
  - `*` pokryje cokoliv (drží ho role `admin`),
  - `inventory.*` pokryje `inventory.item:read` i `inventory.stock:adjust`.

Výsledek se drží v procesní TTL cache (`RBAC_CACHE_TTL`, výchozí 30 s, `0`
vypíná). Po změně grantů volej `clear_permission_cache(user_id)` – jinak se
změna projeví až po vypršení TTL.
"""
import os
import time
from typing import Optional

from fastapi import Depends, HTTPException, status

from .auth import get_current_user
from .db import get_pool
from .models import User

_CACHE_TTL = int(os.getenv("RBAC_CACHE_TTL", "30"))

# user_id -> (expires_at_monotonic, frozenset[str])
_cache: dict[int, tuple[float, frozenset[str]]] = {}


def permission_matches(granted: str, required: str) -> bool:
    """Pokrývá jedno přidělené oprávnění (`granted`) konkrétní požadavek
    (`required`)? `required` musí být konkrétní řetězec bez wildcardu."""
    if granted == "*" or granted == required:
        return True
    if granted.endswith(".*"):
        return required.startswith(granted[:-1])  # 'inventory.' prefix
    return False


def granted_covers(granted: set[str] | frozenset[str], required: str) -> bool:
    return any(permission_matches(g, required) for g in granted)


def clear_permission_cache(user_id: Optional[int] = None) -> None:
    if user_id is None:
        _cache.clear()
    else:
        _cache.pop(user_id, None)


async def _load_effective_permissions(user_id: int, role: str) -> frozenset[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT permission_name FROM auth.role_permissions
             WHERE role_name = $2
                OR role_name IN (SELECT role_name FROM auth.user_roles WHERE user_id = $1)
            UNION
            SELECT permission_name FROM auth.user_permissions WHERE user_id = $1
            """,
            user_id,
            role,
        )
    return frozenset(r["permission_name"] for r in rows)


async def get_effective_permissions(user_id: int, role: str) -> frozenset[str]:
    """Množina přidělených oprávnění (může obsahovat wildcardy `*` / `x.*`)."""
    if _CACHE_TTL > 0:
        hit = _cache.get(user_id)
        if hit is not None and hit[0] > time.monotonic():
            return hit[1]
    perms = await _load_effective_permissions(user_id, role)
    if _CACHE_TTL > 0:
        _cache[user_id] = (time.monotonic() + _CACHE_TTL, perms)
    return perms


async def user_has_permission(user: User, permission: str) -> bool:
    """Imperativní kontrola pro použití uvnitř handleru."""
    granted = await get_effective_permissions(user.id, user.role)
    return granted_covers(granted, permission)


def require_permission(*permissions: str, mode: str = "all"):
    """FastAPI dependency: routa vyžaduje daná oprávnění.

    `mode="all"` (výchozí) – uživatel musí mít všechna, `mode="any"` – stačí jedno.
    Vrací `User`, takže jde použít i jako `user = Depends(require_permission(...))`.
    """
    if mode not in ("all", "any"):
        raise ValueError("mode must be 'all' or 'any'")
    if not permissions:
        raise ValueError("require_permission needs at least one permission")

    async def _check(user: User = Depends(get_current_user)) -> User:
        granted = await get_effective_permissions(user.id, user.role)
        checks = [(p, granted_covers(granted, p)) for p in permissions]
        ok = all(c for _, c in checks) if mode == "all" else any(c for _, c in checks)
        if not ok:
            missing = next(p for p, c in checks if not c) if mode == "all" \
                else ", ".join(permissions)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {missing}",
            )
        return user

    return _check
