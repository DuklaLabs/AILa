"""Translate the latest transcribed Pocket recording into task proposals in Projects.

    python PocketPlayground/task_translator.py

Pipeline: latest completed Pocket recording -> local Ollama LLM pulls out
candidate tasks (title, assignee guess, project/phase guess) -> each
candidate is fuzzy-matched against real Projects/Phases/Users -> submitted
as a `task.create` proposal via the Projects MCP tool `propose_change`.

Nothing lands in `projects.tasks` directly: a `task.create` proposal sits
`pending` until a human with `projects.proposal:review` approves it in the
Projects UI (Návrhy změn od AI) — same review gate as every other
AI-originated write in that service. See Projects/app/services/proposals.py.

Needs in PocketPlayground/.env (see .env.example):
    POCKET_API_KEY        - already used by latest_transcript.py
    PROJECTS_BASE_URL      - e.g. http://localhost:8006
    AI_AGENT_USERNAME/PASSWORD - account from Database/seed_ai_agent.py
    OLLAMA_URL / OLLAMA_MODEL  - defaults assume a local Ollama on :11434
"""
import asyncio
import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv(Path(__file__).parent / ".env")

from ailacore import pocket  # noqa: E402 (must import after load_dotenv)

PROJECTS_BASE_URL = os.getenv("PROJECTS_BASE_URL", "http://localhost:8006")
AI_AGENT_USERNAME = os.getenv("AI_AGENT_USERNAME", "")
AI_AGENT_PASSWORD = os.getenv("AI_AGENT_PASSWORD", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
SESSION_COOKIE = "dl_session"

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


# --- Pocket: nejnovější přepsaná nahrávka -------------------------------------

async def latest_completed_recording() -> dict:
    listing = await pocket.list_recordings(limit=20)
    completed = [r for r in listing["data"] if r["state"] == "completed"]
    if not completed:
        raise RuntimeError("Žádná přepsaná nahrávka nenalezena.")
    detail = await pocket.get_recording(
        completed[0]["id"], include_transcript=True, include_summarizations=False
    )
    return detail["data"]


def transcript_text(recording: dict) -> str:
    return "\n".join(
        f"{seg['speaker']}: {seg['text']}" for seg in recording["transcript"]["segments"]
    )


# --- LLM extrakce úkolů --------------------------------------------------------

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


async def extract_tasks(transcript: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": EXTRACTION_PROMPT.format(transcript=transcript),
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()
        raw = resp.json()["response"]
    return _parse_json_array(raw)


# --- fuzzy shoda proti reálným projektům/fázím/uživatelům ---------------------

def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def best_match(hint: Optional[str], candidates: list[dict], *keys: str, threshold: float = 0.45) -> Optional[dict]:
    if not hint or not candidates:
        return None
    best, best_score = None, 0.0
    for c in candidates:
        for key in keys:
            name = (c.get(key) or "").strip()
            if not name:
                continue
            score = _similarity(hint, name)
            if hint.lower() in name.lower() or name.lower() in hint.lower():
                score = max(score, 0.9)
            if score > best_score:
                best, best_score = c, score
    return best if best_score >= threshold else None


# --- Projects REST + MCP -------------------------------------------------------

async def login() -> str:
    async with httpx.AsyncClient(base_url=PROJECTS_BASE_URL) as client:
        resp = await client.post(
            "/login-check",
            data={"username": AI_AGENT_USERNAME, "password": AI_AGENT_PASSWORD},
            follow_redirects=False,
        )
        token = resp.cookies.get(SESSION_COOKIE)
        if not token:
            raise RuntimeError(f"Přihlášení AI agenta do Projects selhalo (HTTP {resp.status_code}).")
        return token


async def get_json(token: str, path: str) -> Any:
    async with httpx.AsyncClient(base_url=PROJECTS_BASE_URL) as client:
        resp = await client.get(path, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp.json()


async def submit_task_proposal(token: str, *, phase_id: int, payload: dict, summary: str) -> dict:
    async with create_mcp_http_client(headers={"Authorization": f"Bearer {token}"}) as http_client:
        async with streamable_http_client(
            f"{PROJECTS_BASE_URL}/mcp", http_client=http_client
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "propose_change",
                    arguments={
                        "kind": "task.create",
                        "target_type": "phase",
                        "target_id": phase_id,
                        "payload": payload,
                        "summary": summary,
                    },
                )
    if result.structuredContent:
        return result.structuredContent
    for block in result.content:
        if block.type == "text":
            try:
                return json.loads(block.text)
            except json.JSONDecodeError:
                return {"raw": block.text}
    return {}


# --- orchestrace ----------------------------------------------------------------

async def main() -> None:
    recording = await latest_completed_recording()
    print(f"Zdroj: {recording['title']} ({recording['recording_at']})\n")

    candidates = await extract_tasks(transcript_text(recording))
    if not candidates:
        print("LLM v přepisu nenašel žádné konkrétní úkoly.")
        return
    print(f"LLM navrhl {len(candidates)} úkol(ů).\n")

    token = await login()
    projects = await get_json(token, "/api/projects")
    users = await get_json(token, "/api/users")

    for c in candidates:
        title = (c.get("title") or "").strip()
        if not title:
            continue
        print(f"--- {title} ---")

        project = best_match(c.get("project_hint"), projects, "name")
        if project is None:
            print("  ! projekt se z kontextu nepodařilo poznat -> přeskočeno, přiřaď ručně")
            continue

        phases = await get_json(token, f"/api/projects/{project['id']}/phases")
        phase = best_match(c.get("phase_hint"), phases, "name") or (phases[0] if phases else None)
        if phase is None:
            print(f"  ! projekt '{project['name']}' nemá žádnou fázi -> přeskočeno")
            continue

        assignee = best_match(c.get("assignee_name"), users, "name", "username")

        payload = {
            "title": title,
            "description": c.get("description"),
            "due_on": c.get("due_on"),
            "assignee_user_id": assignee["id"] if assignee else None,
        }
        summary = (
            f"AI návrh ze schůzky „{recording['title']}“ "
            f"({recording['recording_at'][:10]}): {title}"
        )
        result = await submit_task_proposal(
            token, phase_id=phase["id"], payload=payload, summary=summary
        )

        who = f", řešitel {assignee['name']}" if assignee else ""
        print(f"  -> projekt '{project['name']}' / fáze '{phase['name']}'{who}")
        print(f"  -> návrh (proposal) vytvořen: {result}")

    print("\nHotovo. Návrhy čekají na schválení v Projects (Návrhy změn od AI).")


if __name__ == "__main__":
    asyncio.run(main())
