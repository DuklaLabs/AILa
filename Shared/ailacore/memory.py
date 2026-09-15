"""Shared memory orchestration for AILa agents, built on top of `ailacore.obsidian`.

Multiple agents (the Pocket task translator, the General orchestrator, other
per-service agents, ...) end up working on the same DuklaLabs projects and
need to see what each other already found out or decided — without a shared
DB table, and without every agent inventing its own note layout in the
vault. This module is the one place that decides *where* a given piece of
memory lives:

    Projects/<project>/context.md   one running summary per project, kept as
                                     headed sections ("## Fakta",
                                     "## Rozhodnutí", ...) so an agent can
                                     add to a section without touching the
                                     rest of the note.
    Projects/<project>/log.md       append-only, timestamped timeline of
                                     what agents did/decided on that project
                                     — the shared "what happened" feed
                                     across agents.
    Knowledge Base/<topic>.md       things that stopped being specific to
                                     one project (a recurring decision, a
                                     fact about how some system works).
                                     Only ever reached via promote() — never
                                     written to automatically.

`project` is a vault-safe slug an agent already knows (e.g. the Projects
service's own project slug/id), not free text — two agents must agree on
the same string for their notes to land in the same place.
"""
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from . import obsidian

PROJECTS_ROOT = "Projects"
KB_ROOT = "Knowledge Base"


def _context_path(project: str) -> str:
    return f"{PROJECTS_ROOT}/{project}/context.md"


def _log_path(project: str) -> str:
    return f"{PROJECTS_ROOT}/{project}/log.md"


def _kb_path(topic: str) -> str:
    return f"{KB_ROOT}/{topic}.md"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _is_404(exc: httpx.HTTPStatusError) -> bool:
    return exc.response.status_code == 404


async def remember(project: str, section: str, content: str) -> None:
    """Add `content` under a `## {section}` heading in the project's context
    note. Creates the note, or just the heading, the first time either is
    missing — callers never need to pre-create anything."""
    path = _context_path(project)
    # The note opens with "# {project}" (H1), so "## {section}" is nested
    # under it — the plugin addresses nested headings as "H1::H2", not just
    # the leaf name, or it 400s with "invalid-target".
    heading_target = f"{project}::{section}"
    try:
        await obsidian.patch_note(
            path, f"\n{content}\n", operation="append", target_type="heading", target=heading_target,
        )
        return
    except httpx.HTTPStatusError:
        pass  # note and/or heading don't exist yet — fall through and create them

    try:
        await obsidian.get_note(path)
    except httpx.HTTPStatusError as exc:
        if not _is_404(exc):
            raise
        await obsidian.create_or_update_note(path, f"# {project}\n\n## {section}\n\n{content}\n")
        return
    # Note exists, the heading didn't — add it as a new section at the end.
    await obsidian.append_to_note(path, f"\n\n## {section}\n\n{content}\n")


async def log(project: str, content: str) -> None:
    """Append a timestamped entry to the project's shared timeline."""
    await obsidian.append_to_note(_log_path(project), f"\n- {_timestamp()} — {content}")


async def recall(project: str) -> str:
    """The project's full running-context note, or "" if nothing has been
    remembered for it yet."""
    try:
        return await obsidian.get_note(_context_path(project))
    except httpx.HTTPStatusError as exc:
        if _is_404(exc):
            return ""
        raise


async def recent_log(project: str, limit: int = 20) -> str:
    """The last `limit` non-empty lines of the project's timeline, oldest
    first within that window."""
    try:
        text = await obsidian.get_note(_log_path(project))
    except httpx.HTTPStatusError as exc:
        if _is_404(exc):
            return ""
        raise
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-limit:])


async def search(query: str, project: Optional[str] = None, context_length: int = 100) -> Any:
    """Vault-wide search; pass `project` to keep only hits inside that
    project's own folder."""
    results = await obsidian.search_notes(query, context_length=context_length)
    if project is None:
        return results
    prefix = f"{PROJECTS_ROOT}/{project}/"
    return [r for r in results if r.get("filename", "").startswith(prefix)]


async def promote(project: str, content: str, topic: str) -> None:
    """Copy something out of a project's memory into the cross-project
    Knowledge Base, tagged with the project it came from."""
    entry = f"\n\n## {_timestamp()} (z {project})\n\n{content}\n"
    await obsidian.append_to_note(_kb_path(topic), entry)


async def list_projects() -> list[str]:
    """Project slugs that currently have any memory in the vault."""
    result = await obsidian.list_notes(PROJECTS_ROOT)
    files = result.get("files", []) if isinstance(result, dict) else result
    return [f.rstrip("/") for f in files if f.endswith("/")]


async def list_kb_topics() -> list[str]:
    """Knowledge Base topic names (without the .md extension)."""
    result = await obsidian.list_notes(KB_ROOT)
    files = result.get("files", []) if isinstance(result, dict) else result
    return [f[:-3] for f in files if f.endswith(".md")]
