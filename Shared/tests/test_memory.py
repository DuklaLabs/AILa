"""Testy pro ailacore.memory – HTTP volání mockovaná přes httpx.MockTransport,
žádné reálné volání na Obsidian Local REST API."""
from urllib.parse import quote

import httpx
import pytest

from ailacore import memory, obsidian


class _QueueRecorder:
    """Replays one canned response per request, in order; records every
    request it saw for assertions."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, kwargs = self.responses.pop(0)
        return httpx.Response(status, **kwargs)


def _mock_client_for(monkeypatch, recorder):
    monkeypatch.setattr(obsidian, "OBSIDIAN_API_KEY", "obs_test")

    class _MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(recorder.handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(obsidian.httpx, "AsyncClient", _MockAsyncClient)


async def test_remember_patches_existing_heading(monkeypatch):
    recorder = _QueueRecorder([(200, {"json": {"ok": True}})])
    _mock_client_for(monkeypatch, recorder)

    await memory.remember("kroky-uvolneni", "Rozhodnutí", "Termín posunut na pátek")

    assert len(recorder.requests) == 1
    req = recorder.requests[0]
    assert req.method == "PATCH"
    assert req.url.path == "/vault/Projects/kroky-uvolneni/context.md"
    assert req.headers["target"] == quote("kroky-uvolneni::Rozhodnutí", safe="")
    assert "Termín posunut na pátek".encode() in req.content


async def test_remember_creates_note_when_missing(monkeypatch):
    recorder = _QueueRecorder(
        [
            (404, {"json": {"error": "not found"}}),  # PATCH fails, note doesn't exist
            (404, {"json": {"error": "not found"}}),  # GET confirms it's missing
            (200, {"json": {"ok": True}}),  # PUT creates it
        ]
    )
    _mock_client_for(monkeypatch, recorder)

    await memory.remember("novy-projekt", "Fakta", "Založeno 2026-09-15")

    assert len(recorder.requests) == 3
    patch_req, get_req, put_req = recorder.requests
    assert patch_req.method == "PATCH"
    assert get_req.method == "GET"
    assert put_req.method == "PUT"
    assert put_req.url.path == "/vault/Projects/novy-projekt/context.md"
    body = put_req.content.decode()
    assert body.startswith("# novy-projekt")
    assert "## Fakta" in body
    assert "Založeno 2026-09-15" in body


async def test_remember_appends_new_heading_when_note_exists(monkeypatch):
    recorder = _QueueRecorder(
        [
            (404, {"json": {"error": "heading not found"}}),  # PATCH fails, heading missing
            (200, {"text": "# proj\n\n## Fakta\n\nněco\n"}),  # GET confirms note exists
            (200, {"json": {"ok": True}}),  # POST appends new heading
        ]
    )
    _mock_client_for(monkeypatch, recorder)

    await memory.remember("proj", "Otevřené otázky", "Kdo to schválí?")

    assert len(recorder.requests) == 3
    post_req = recorder.requests[2]
    assert post_req.method == "POST"
    body = post_req.content.decode()
    assert "## Otevřené otázky" in body
    assert "Kdo to schválí?" in body


async def test_remember_reraises_non_404_get_error(monkeypatch):
    recorder = _QueueRecorder(
        [
            (404, {"json": {"error": "not found"}}),
            (500, {"json": {"error": "boom"}}),
        ]
    )
    _mock_client_for(monkeypatch, recorder)

    with pytest.raises(httpx.HTTPStatusError):
        await memory.remember("proj", "Fakta", "x")


async def test_log_appends_timestamped_entry(monkeypatch):
    recorder = _QueueRecorder([(200, {"json": {"ok": True}})])
    _mock_client_for(monkeypatch, recorder)

    await memory.log("kroky-uvolneni", "Task translator vytvořil 3 úkoly")

    req = recorder.requests[0]
    assert req.method == "POST"
    assert req.url.path == "/vault/Projects/kroky-uvolneni/log.md"
    body = req.content.decode()
    assert body.startswith("\n- ")
    assert "UTC — Task translator vytvořil 3 úkoly" in body


async def test_recall_returns_note_content(monkeypatch):
    recorder = _QueueRecorder([(200, {"text": "# proj\n\n## Fakta\n\nněco\n"})])
    _mock_client_for(monkeypatch, recorder)

    result = await memory.recall("proj")

    assert result == "# proj\n\n## Fakta\n\nněco\n"
    assert recorder.requests[0].url.path == "/vault/Projects/proj/context.md"


async def test_recall_missing_project_returns_empty_string(monkeypatch):
    recorder = _QueueRecorder([(404, {"json": {"error": "not found"}})])
    _mock_client_for(monkeypatch, recorder)

    result = await memory.recall("neexistuje")

    assert result == ""


async def test_recent_log_limits_lines(monkeypatch):
    text = "\n".join(f"- entry {i}" for i in range(30))
    recorder = _QueueRecorder([(200, {"text": text})])
    _mock_client_for(monkeypatch, recorder)

    result = await memory.recent_log("proj", limit=5)

    lines = result.splitlines()
    assert lines == [f"- entry {i}" for i in range(25, 30)]


async def test_search_without_project_returns_all_hits(monkeypatch):
    hits = [{"filename": "Projects/a/context.md"}, {"filename": "Knowledge Base/x.md"}]
    recorder = _QueueRecorder([(200, {"json": hits})])
    _mock_client_for(monkeypatch, recorder)

    result = await memory.search("rozpočet")

    assert result == hits


async def test_search_with_project_filters_hits(monkeypatch):
    hits = [
        {"filename": "Projects/a/context.md"},
        {"filename": "Projects/b/context.md"},
        {"filename": "Knowledge Base/x.md"},
    ]
    recorder = _QueueRecorder([(200, {"json": hits})])
    _mock_client_for(monkeypatch, recorder)

    result = await memory.search("rozpočet", project="a")

    assert result == [{"filename": "Projects/a/context.md"}]


async def test_promote_appends_to_knowledge_base(monkeypatch):
    recorder = _QueueRecorder([(200, {"json": {"ok": True}})])
    _mock_client_for(monkeypatch, recorder)

    await memory.promote("proj", "RBAC kontrola je vždy na úrovni permission, ne role", "rbac")

    req = recorder.requests[0]
    assert req.method == "POST"
    assert req.url.path == "/vault/Knowledge Base/rbac.md"
    body = req.content.decode()
    assert "(z proj)" in body
    assert "RBAC kontrola" in body


async def test_list_projects_strips_trailing_slash(monkeypatch):
    recorder = _QueueRecorder([(200, {"json": {"files": ["a/", "b/", "readme.md"]}})])
    _mock_client_for(monkeypatch, recorder)

    result = await memory.list_projects()

    assert result == ["a", "b"]
    assert recorder.requests[0].url.path == "/vault/Projects/"


async def test_list_kb_topics_strips_md_extension(monkeypatch):
    recorder = _QueueRecorder([(200, {"json": {"files": ["rbac.md", "sub/"]}})])
    _mock_client_for(monkeypatch, recorder)

    result = await memory.list_kb_topics()

    assert result == ["rbac"]
    assert recorder.requests[0].url.path == "/vault/Knowledge Base/"
