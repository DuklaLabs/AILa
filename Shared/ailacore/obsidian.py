"""Client for the Obsidian Local REST API plugin.

Agents that need durable, human-browsable memory — notes they've written for
themselves, summaries worth keeping across runs, anything a person should be
able to open in Obsidian and read or edit — go through this module instead of
rolling their own httpx calls. It talks to the "Local REST API" community
plugin (https://github.com/coddingtonbear/obsidian-local-rest-api) running
inside a real Obsidian instance that has the target vault open, so the vault
itself is just a folder of markdown files.

The plugin listens locally on the machine running Obsidian (default
`https://127.0.0.1:27124`, self-signed cert — hence `verify=False` below;
this is a loopback-only API, not something exposed over the network). Auth
is a bearer token shown in the plugin's settings tab in Obsidian.
"""
import os
from typing import Any, Optional
from urllib.parse import quote

import httpx

OBSIDIAN_BASE_URL = os.getenv("OBSIDIAN_BASE_URL", "https://127.0.0.1:27124")
OBSIDIAN_API_KEY = os.getenv("OBSIDIAN_API_KEY", "")

_NOTE_JSON_ACCEPT = "application/vnd.olrapi.note+json"


def _headers(**extra: str) -> dict:
    if not OBSIDIAN_API_KEY:
        raise RuntimeError("OBSIDIAN_API_KEY is not set")
    return {"Authorization": f"Bearer {OBSIDIAN_API_KEY}", **extra}


def _quote_path(path: str) -> str:
    return quote(path, safe="/")


async def _request(method: str, path: str, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(base_url=OBSIDIAN_BASE_URL, timeout=30, verify=False) as client:
        resp = await client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp


async def get_status() -> Any:
    """Plugin health/version info. Does not require an API key."""
    async with httpx.AsyncClient(base_url=OBSIDIAN_BASE_URL, timeout=30, verify=False) as client:
        resp = await client.get("/")
        resp.raise_for_status()
        return resp.json()


async def list_notes(folder: Optional[str] = None) -> Any:
    """List files directly inside `folder` (vault root if omitted, non-recursive)."""
    path = f"/vault/{_quote_path(folder)}/" if folder else "/vault/"
    resp = await _request("GET", path, headers=_headers())
    return resp.json()


async def get_note(path: str, as_json: bool = False) -> Any:
    """Read a note. `as_json=True` returns content + frontmatter + tags + stat
    instead of the raw markdown string."""
    accept = _NOTE_JSON_ACCEPT if as_json else "text/markdown"
    resp = await _request("GET", f"/vault/{_quote_path(path)}", headers=_headers(Accept=accept))
    return resp.json() if as_json else resp.text


async def create_or_update_note(path: str, content: str) -> None:
    """Create a note or overwrite it entirely if it already exists."""
    await _request(
        "PUT",
        f"/vault/{_quote_path(path)}",
        headers=_headers(**{"Content-Type": "text/markdown"}),
        content=content.encode("utf-8"),
    )


async def append_to_note(path: str, content: str) -> None:
    """Append to a note, creating it first if it doesn't exist yet."""
    await _request(
        "POST",
        f"/vault/{_quote_path(path)}",
        headers=_headers(**{"Content-Type": "text/markdown"}),
        content=content.encode("utf-8"),
    )


async def patch_note(
    path: str,
    content: str,
    operation: str,
    target_type: str,
    target: str,
    target_delimiter: Optional[str] = None,
) -> None:
    """Insert `content` relative to a heading, block reference, or frontmatter
    field, without rewriting the rest of the note.

    `operation`: "append" | "prepend" | "replace"
    `target_type`: "heading" | "block" | "frontmatter"
    `target`: the heading path (e.g. "Memory::Decisions"), block id, or
    frontmatter field name to act on.
    """
    headers = _headers(
        Operation=operation,
        **{
            "Target-Type": target_type,
            "Target": quote(target, safe=""),
            "Content-Type": "text/markdown",
        },
    )
    if target_delimiter:
        headers["Target-Delimiter"] = target_delimiter
    await _request("PATCH", f"/vault/{_quote_path(path)}", headers=headers, content=content.encode("utf-8"))


async def delete_note(path: str) -> None:
    await _request("DELETE", f"/vault/{_quote_path(path)}", headers=_headers())


async def search_notes(query: str, context_length: int = 100) -> Any:
    """Plain-text search across the vault; returns matches with surrounding context."""
    resp = await _request(
        "POST",
        "/search/simple/",
        headers=_headers(),
        params={"query": query, "contextLength": context_length},
    )
    return resp.json()
