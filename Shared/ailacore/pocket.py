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
    page: int = 1,
    limit: int = 20,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tag_ids: Optional[str] = None,
) -> Any:
    params: dict = {"page": page, "limit": limit}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if tag_ids:
        params["tag_ids"] = tag_ids
    return await _request("GET", "/public/recordings", params=params)


async def get_recording(
    recording_id: str,
    include_transcript: bool = True,
    include_summarizations: bool = True,
    summarization_id: Optional[str] = None,
) -> Any:
    params: dict = {
        "include_transcript": include_transcript,
        "include_summarizations": include_summarizations,
    }
    if summarization_id:
        params["summarization_id"] = summarization_id
    return await _request("GET", f"/public/recordings/{recording_id}", params=params)


async def search_recordings(query: str, limit: int = 8, filters: Optional[dict] = None) -> Any:
    body: dict = {"query": query, "limit": limit}
    if filters:
        body["filters"] = filters
    return await _request("POST", "/public/search", json=body)


async def list_tags() -> Any:
    return await _request("GET", "/public/tags")
