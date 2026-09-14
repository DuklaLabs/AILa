"""Client for the Pocket meeting-recording API (heypocketai.com).

Any AILa agent that needs meeting recordings, transcripts, or AI summaries
— to answer questions about a past meeting, pull action items, or use a
transcript as instruction material for another agent — goes through this
module instead of rolling its own httpx calls against Pocket. That keeps
the base URL and the org's API key (`POCKET_API_KEY`, a `pk_xxx` bearer
token minted in the Pocket org settings, see
https://docs.heypocketai.com/docs/api) in one place.
"""
import os
from typing import Any, Optional

import httpx

POCKET_BASE_URL = os.getenv("POCKET_BASE_URL", "https://public.heypocketai.com/api/v1")
POCKET_API_KEY = os.getenv("POCKET_API_KEY", "")


def _headers() -> dict:
    if not POCKET_API_KEY:
        raise RuntimeError("POCKET_API_KEY is not set")
    return {"Authorization": f"Bearer {POCKET_API_KEY}"}


async def _request(method: str, path: str, **kwargs) -> Any:
    async with httpx.AsyncClient(base_url=POCKET_BASE_URL, timeout=30) as client:
        resp = await client.request(method, path, headers=_headers(), **kwargs)
        resp.raise_for_status()
        return resp.json()


async def list_recordings(
    limit: int = 20,
    cursor: Optional[str] = None,
    folder_id: Optional[str] = None,
) -> Any:
    params: dict = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    if folder_id:
        params["folder_id"] = folder_id
    return await _request("GET", "/public/recordings", params=params)


async def get_recording(
    recording_id: str,
    include_transcript: bool = True,
    include_summarizations: bool = True,
) -> Any:
    params = {
        "include_transcript": include_transcript,
        "include_summarizations": include_summarizations,
    }
    return await _request("GET", f"/public/recordings/{recording_id}", params=params)


async def search_recordings(query: str, limit: int = 20) -> Any:
    return await _request(
        "POST", "/public/recordings/search", json={"query": query, "limit": limit}
    )


async def list_tags() -> Any:
    return await _request("GET", "/public/tags")
