"""Společné pomůcky servisní vrstvy: RBAC guard a enum konstanty."""
from fastapi import HTTPException

from ailacore.models import User
from ailacore.rbac import user_has_permission

# --- stavy a číselníky datové karty úkolu (dle dodané specifikace) ---------

TASK_STATUSES = ("backlog", "in_progress", "design_review", "blocked", "done")
COST_TYPES = ("components", "pcb", "mechanical", "tools")
ORDER_STATUSES = ("cart", "ordered", "in_lab")
PROJECT_STATUSES = ("active", "on_hold", "done", "archived")


async def require(user: User, permission: str) -> None:
    """Vyhodí 403, pokud uživatel nemá dané oprávnění (admin projde přes `*`)."""
    if not await user_has_permission(user, permission):
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")


def validate_enum(value, allowed, field: str):
    if value is not None and value not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Neplatná hodnota pro {field}: {value!r} (povoleno: {', '.join(allowed)}).",
        )
