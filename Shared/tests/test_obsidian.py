"""Testy pro ailacore.obsidian – HTTP volání mockovaná přes httpx.MockTransport,
žádné reálné volání na Obsidian Local REST API."""
import httpx
import pytest

from ailacore import obsidian


class _Recorder:
    def __init__(self, json_body=None, text_body=None):
        self.requests: list[httpx.Request] = []
        self._json_body = json_body
        self._text_body = text_body

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._text_body is not None:
            return httpx.Response(200, text=self._text_body)
        return httpx.Response(200, json=self._json_body if self._json_body is not None else {"ok": True})


@pytest.fixture
def mock_obsidian(monkeypatch):
    monkeypatch.setattr(obsidian, "OBSIDIAN_API_KEY", "obs_test")
    recorder = _Recorder()

    class _MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(recorder.handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(obsidian.httpx, "AsyncClient", _MockAsyncClient)
    return recorder


def _mock_client_for(monkeypatch, recorder):
    class _MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(recorder.handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(obsidian.httpx, "AsyncClient", _MockAsyncClient)


async def test_get_status_does_not_require_api_key(monkeypatch):
    recorder = _Recorder(json_body={"status": "OK", "versions": {"obsidian": "1.5.0"}})
    _mock_client_for(monkeypatch, recorder)
    result = await obsidian.get_status()
    assert result["status"] == "OK"
    assert "authorization" not in recorder.requests[0].headers


async def test_list_notes_root(mock_obsidian):
    await obsidian.list_notes()
    req = mock_obsidian.requests[0]
    assert req.method == "GET"
    assert req.url.path == "/vault/"
    assert req.headers["authorization"] == "Bearer obs_test"


async def test_list_notes_folder_quotes_path(mock_obsidian):
    await obsidian.list_notes("Memory/Agents")
    req = mock_obsidian.requests[0]
    assert req.url.path == "/vault/Memory/Agents/"


async def test_get_note_raw_markdown(monkeypatch):
    recorder = _Recorder(text_body="# Hello\ncontent")
    _mock_client_for(monkeypatch, recorder)
    monkeypatch.setattr(obsidian, "OBSIDIAN_API_KEY", "obs_test")
    result = await obsidian.get_note("Memory/note.md")
    req = recorder.requests[0]
    assert req.url.path == "/vault/Memory/note.md"
    assert req.headers["accept"] == "text/markdown"
    assert result == "# Hello\ncontent"


async def test_get_note_as_json_sets_accept_header(mock_obsidian):
    await obsidian.get_note("note.md", as_json=True)
    req = mock_obsidian.requests[0]
    assert req.headers["accept"] == "application/vnd.olrapi.note+json"


async def test_create_or_update_note_puts_raw_content(mock_obsidian):
    await obsidian.create_or_update_note("Memory/note.md", "hello world")
    req = mock_obsidian.requests[0]
    assert req.method == "PUT"
    assert req.url.path == "/vault/Memory/note.md"
    assert req.headers["content-type"] == "text/markdown"
    assert req.content == b"hello world"


async def test_append_to_note_posts_content(mock_obsidian):
    await obsidian.append_to_note("note.md", "more text")
    req = mock_obsidian.requests[0]
    assert req.method == "POST"
    assert req.content == b"more text"


async def test_patch_note_sets_operation_headers(mock_obsidian):
    await obsidian.patch_note(
        "note.md",
        "new fact",
        operation="append",
        target_type="heading",
        target="Memory::Decisions",
    )
    req = mock_obsidian.requests[0]
    assert req.method == "PATCH"
    assert req.headers["operation"] == "append"
    assert req.headers["target-type"] == "heading"
    assert req.headers["target"] == "Memory%3A%3ADecisions"
    assert req.content == b"new fact"


async def test_delete_note(mock_obsidian):
    await obsidian.delete_note("note.md")
    req = mock_obsidian.requests[0]
    assert req.method == "DELETE"
    assert req.url.path == "/vault/note.md"


async def test_search_notes_sends_query_params(mock_obsidian):
    await obsidian.search_notes("rozpočet", context_length=50)
    req = mock_obsidian.requests[0]
    assert req.method == "POST"
    assert req.url.path == "/search/simple/"
    assert req.url.params["query"] == "rozpočet"
    assert req.url.params["contextLength"] == "50"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(obsidian, "OBSIDIAN_API_KEY", "")
    with pytest.raises(RuntimeError):
        obsidian._headers()
