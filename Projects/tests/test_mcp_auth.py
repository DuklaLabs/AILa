"""MCP nástroje běží jen s platným bearer tokenem a oprávněním projects.ai:use."""
import pytest

from ailacore.models import User
from app import mcp_server


@pytest.fixture
def token_ctx():
    tok = mcp_server._bearer_token.set(None)
    yield
    mcp_server._bearer_token.reset(tok)


async def test_no_token_rejected(token_ctx, monkeypatch):
    mcp_server._bearer_token.set(None)

    async def no_user(_):
        return None

    monkeypatch.setattr(mcp_server, "get_user_from_token", no_user)
    with pytest.raises(ValueError, match="token"):
        await mcp_server._current_user()


async def test_token_without_ai_use_rejected(token_ctx, monkeypatch):
    mcp_server._bearer_token.set("abc")
    user = User(id=5, username="ai", role="member", is_active=True)

    async def a_user(_):
        return user

    async def has_perm(u, perm):
        return False

    monkeypatch.setattr(mcp_server, "get_user_from_token", a_user)
    monkeypatch.setattr(mcp_server, "user_has_permission", has_perm)
    with pytest.raises(ValueError, match="projects.ai:use"):
        await mcp_server._current_user()


async def test_token_with_ai_use_ok(token_ctx, monkeypatch):
    mcp_server._bearer_token.set("abc")
    user = User(id=5, username="ai", role="member", is_active=True)

    async def a_user(_):
        return user

    async def has_perm(u, perm):
        return perm == "projects.ai:use"

    monkeypatch.setattr(mcp_server, "get_user_from_token", a_user)
    monkeypatch.setattr(mcp_server, "user_has_permission", has_perm)
    assert (await mcp_server._current_user()) is user
