"""Bridge between Pocket (meeting recordings/transcripts) and Projects tasks.

Backs the dashboard's "Pocket" panel: record/upload audio, list recordings,
and turn a transcript into `task.create` proposals via the existing
AI-proposal review flow (`app.services.proposals`) — nothing here writes a
task directly. The LLM only *suggests* title/assignee/project/phase; a human
picks the real project/phase/assignee in the UI before `propose_tasks`
files anything, so no fuzzy name-matching happens server-side.
"""
import json
import os
import re
from typing import Any, Optional

import httpx
from fastapi import HTTPException

from ailacore import pocket
from ailacore.models import User

from app.services import proposals as proposals_service
from app.services.base import require

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

EXTRACTION_PROMPT = """Jsi asistent, který z přepisu schůzky vytáhne konkrétní úkoly (akční položky).

Pravidla:
- Vrať POUZE JSON pole, žádný další text, žádné markdown bloky.
- Každá položka: {{"title": str, "description": str|null, "assignee_name": str|null, "due_on": "YYYY-MM-DD"|null, "project_hint": str|null, "phase_hint": str|null}}
- "title" = krátký, konkrétní název úkolu (co se má udělat).
- "assignee_name" = jméno osoby, která úkol má udělat, pokud je to z přepisu jasné (jinak null).
- "project_hint" = klíčová slova nebo název projektu/tématu, kterého se úkol týká.
- "phase_hint" = vyber jednu z: Koncept & Specifikace, Vývoj & Návrh, Nákupy & Logistika, Výroba & Oživení, Firmware & Integrace.
- Pokud v přepisu není žádný konkrétní úkol, vrať prázdné pole [].

Přepis schůzky:
{transcript}

JSON:"""


async def list_recordings(user: User, **kwargs) -> Any:
    await require(user, "projects.ai:use")
    return await pocket.list_recordings(**kwargs)


async def get_recording(user: User, recording_id: str) -> Any:
    await require(user, "projects.ai:use")
    return await pocket.get_recording(recording_id)


async def upload_recording(
    user: User,
    *,
    audio_bytes: bytes,
    content_type: str,
    title: Optional[str] = None,
    file_name: Optional[str] = None,
) -> dict:
    await require(user, "projects.ai:use")
    if not audio_bytes:
        raise HTTPException(422, "Prázdný soubor.")
    created = await pocket.create_upload_url(
        title=title, content_type=content_type, file_name=file_name
    )
    data = created.get("data") or {}
    upload_url = data.get("upload_url") or data.get("url")
    if not upload_url:
        raise HTTPException(
            502, f"Pocket nevrátil upload URL (odpověď: {created})."
        )
    await pocket.upload_audio(upload_url, audio_bytes, content_type)
    return {"recording_id": data.get("recording_id") or data.get("id"), "raw": created}


def _transcript_text(recording: dict) -> str:
    segments = (recording.get("transcript") or {}).get("segments") or []
    return "\n".join(f"{s.get('speaker', '?')}: {s.get('text', '')}" for s in segments)


def _parse_json_array(raw: str) -> list[dict]:
    raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    return data if isinstance(data, list) else []


async def extract_task_candidates(user: User, recording_id: str) -> dict:
    """Transcript -> LLM guesses. Nothing is written; the UI shows these for
    the human to review/edit/reject before propose_tasks()."""
    await require(user, "projects.ai:use")
    detail = await pocket.get_recording(recording_id)
    recording = detail["data"]
    text = _transcript_text(recording)
    if not text.strip():
        return {"recording": _recording_summary(recording), "candidates": []}

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": EXTRACTION_PROMPT.format(transcript=text),
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()
        raw = resp.json()["response"]
    return {
        "recording": _recording_summary(recording),
        "candidates": _parse_json_array(raw),
    }


def _recording_summary(recording: dict) -> dict:
    return {
        "id": recording["id"],
        "title": recording.get("title"),
        "recording_at": recording.get("recording_at"),
    }


async def propose_tasks(user: User, recording_id: str, tasks_in: list[dict]) -> list[dict]:
    """`tasks_in`: candidates the human confirmed, each needs at least
    `title` and `phase_id` (picked from a real project's phase list in the
    UI). Every one becomes its own `task.create` proposal — reviewed and
    applied through the existing flow in app.services.proposals."""
    if not tasks_in:
        raise HTTPException(422, "Žádné úkoly k návrhu.")
    detail = await pocket.get_recording(recording_id)
    recording = detail["data"]
    date = str(recording.get("recording_at") or "")[:10]

    created = []
    for t in tasks_in:
        title = (t.get("title") or "").strip()
        phase_id = t.get("phase_id")
        if not title or not phase_id:
            raise HTTPException(422, "Každý úkol potřebuje title a phase_id.")
        payload = {
            "title": title,
            "description": t.get("description"),
            "due_on": t.get("due_on"),
            "assignee_user_id": t.get("assignee_user_id"),
        }
        summary = f"AI návrh ze schůzky „{recording.get('title')}“ ({date}): {title}"
        row = await proposals_service.create_proposal(
            user,
            kind="task.create",
            target_type="phase",
            target_id=phase_id,
            payload=payload,
            summary=summary,
            origin="pocket-dashboard",
        )
        created.append(row)
    return created
