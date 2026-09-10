"""Unit testy pro ailacore.rbac – čistá logika, bez DB."""
import pytest
from fastapi import HTTPException

from ailacore import rbac
from ailacore.models import User


# --- permission_matches -------------------------------------------------------

@pytest.mark.parametrize(
    "granted, required, expected",
    [
        ("internal.open_hours:write", "internal.open_hours:write", True),   # přesná shoda
        ("internal.open_hours:write", "internal.open_hours:read", False),   # jiná akce
        ("*", "cokoliv.jineho:action", True),                              # globální wildcard
        ("internal.*", "internal.open_hours:write", True),                  # prefix wildcard
        ("internal.*", "orders.order:approve", False),                      # jiný prefix
        ("inventory.*", "inventory.item:read", True),
        ("internal.open_hours:write", "internal.open_hours", False),        # required není prefix
    ],
)
def test_permission_matches(granted, required, expected):
    assert rbac.permission_matches(granted, required) is expected


def test_granted_covers_set():
    granted = {"internal.*", "messaging.mail:send"}
    assert rbac.granted_covers(granted, "internal.booking:decide") is True
    assert rbac.granted_covers(granted, "messaging.mail:send") is True
    assert rbac.granted_covers(granted, "orders.order:approve") is False
    assert rbac.granted_covers(set(), "internal.booking:decide") is False


# --- require_permission -----------------------------------------------------

def _user() -> User:
    return User(id=1, username="tester", role="member", is_active=True)


@pytest.fixture
def granted(monkeypatch):
    """Nechá test nastavit efektivní oprávnění bez DB."""
    box = {"perms": frozenset()}

    async def fake(user_id: int, role: str):
        return box["perms"]

    monkeypatch.setattr(rbac, "get_effective_permissions", fake)
    return box


async def test_require_permission_all_pass(granted):
    granted["perms"] = frozenset({"internal.booking:read", "internal.booking:decide"})
    check = rbac.require_permission("internal.booking:read", "internal.booking:decide")
    assert await check(user=_user()) is not None


async def test_require_permission_all_missing_one(granted):
    granted["perms"] = frozenset({"internal.booking:read"})
    check = rbac.require_permission("internal.booking:read", "internal.booking:decide")
    with pytest.raises(HTTPException) as exc:
        await check(user=_user())
    assert exc.value.status_code == 403
    assert "internal.booking:decide" in exc.value.detail


async def test_require_permission_any_pass(granted):
    granted["perms"] = frozenset({"internal.booking:read"})
    check = rbac.require_permission(
        "internal.booking:read", "internal.booking:decide", mode="any"
    )
    assert await check(user=_user()) is not None


async def test_require_permission_any_none(granted):
    granted["perms"] = frozenset({"orders.order:read"})
    check = rbac.require_permission(
        "internal.booking:read", "internal.booking:decide", mode="any"
    )
    with pytest.raises(HTTPException) as exc:
        await check(user=_user())
    assert exc.value.status_code == 403


async def test_require_permission_admin_wildcard(granted):
    granted["perms"] = frozenset({"*"})
    check = rbac.require_permission("anything.at:all")
    assert await check(user=_user()) is not None


def test_require_permission_bad_args():
    with pytest.raises(ValueError):
        rbac.require_permission()
    with pytest.raises(ValueError):
        rbac.require_permission("x:y", mode="nonsense")


async def test_user_has_permission(granted):
    granted["perms"] = frozenset({"inventory.*"})
    assert await rbac.user_has_permission(_user(), "inventory.stock:adjust") is True
    assert await rbac.user_has_permission(_user(), "orders.order:approve") is False
