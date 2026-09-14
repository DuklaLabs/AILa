"""Testy pro ailacore.pocket – HTTP volání mockovaná přes httpx.MockTransport,
žádné reálné volání na Pocket."""
import json

import httpx
import pytest

from ailacore import pocket


class _Recorder:
    def __init__(self):
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json={"ok": True})


@pytest.fixture
def mock_pocket(monkeypatch):
    monkeypatch.setattr(pocket, "POCKET_API_KEY", "pk_test")
    recorder = _Recorder()

    class _MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(recorder.handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(pocket.httpx, "AsyncClient", _MockAsyncClient)
    return recorder


async def test_list_recordings_sends_bearer_token_and_params(mock_pocket):
    await pocket.list_recordings(page=2, limit=5, start_date="2026-09-01", tag_ids="t1,t2")
    req = mock_pocket.requests[0]
    assert req.headers["authorization"] == "Bearer pk_test"
    assert req.url.path == "/api/v1/public/recordings"
    assert req.url.params["page"] == "2"
    assert req.url.params["limit"] == "5"
    assert req.url.params["start_date"] == "2026-09-01"
    assert req.url.params["tag_ids"] == "t1,t2"


async def test_get_recording_path_and_params(mock_pocket):
    await pocket.get_recording("rec_1", include_transcript=False, include_summarizations=True)
    req = mock_pocket.requests[0]
    assert req.url.path == "/api/v1/public/recordings/rec_1"
    assert req.url.params["include_transcript"] == "false"
    assert req.url.params["include_summarizations"] == "true"


async def test_search_recordings_posts_query_body(mock_pocket):
    await pocket.search_recordings("rozpočet", limit=3)
    req = mock_pocket.requests[0]
    assert req.method == "POST"
    assert req.url.path == "/api/v1/public/search"
    assert json.loads(req.content) == {"query": "rozpočet", "limit": 3}


async def test_search_recordings_includes_filters_when_given(mock_pocket):
    await pocket.search_recordings("rozpočet", filters={"tag_ids": ["t1"]})
    req = mock_pocket.requests[0]
    assert json.loads(req.content) == {
        "query": "rozpočet",
        "limit": 8,
        "filters": {"tag_ids": ["t1"]},
    }


async def test_list_tags_path(mock_pocket):
    await pocket.list_tags()
    req = mock_pocket.requests[0]
    assert req.method == "GET"
    assert req.url.path == "/api/v1/public/tags"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(pocket, "POCKET_API_KEY", "")
    with pytest.raises(RuntimeError):
        pocket._headers()
