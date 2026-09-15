"""Testy pro ailacore.llm – HTTP volání mockovaná přes httpx.MockTransport,
žádné reálné volání na Ollama ani 9Router."""
import httpx
import pytest

from ailacore import llm


class _Recorder:
    def __init__(self, json_body=None):
        self.requests: list[httpx.Request] = []
        self._json_body = json_body

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self._json_body if self._json_body is not None else {})


def _mock_client_for(monkeypatch, recorder):
    class _MockAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(recorder.handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(llm.httpx, "AsyncClient", _MockAsyncClient)


async def test_sensitive_true_calls_ollama(monkeypatch):
    recorder = _Recorder(json_body={"response": "hello from ollama"})
    _mock_client_for(monkeypatch, recorder)

    result = await llm.complete("ahoj", sensitive=True)

    req = recorder.requests[0]
    assert req.url.path == "/api/generate"
    assert result == "hello from ollama"


async def test_sensitive_true_uses_default_model_and_folds_system_into_prompt(monkeypatch):
    recorder = _Recorder(json_body={"response": "ok"})
    _mock_client_for(monkeypatch, recorder)

    await llm.complete("ahoj", sensitive=True, system="jsi asistent")

    body = recorder.requests[0].read()
    import json as _json
    payload = _json.loads(body)
    assert payload["model"] == llm.OLLAMA_MODEL
    assert payload["prompt"] == "jsi asistent\n\nahoj"
    assert payload["stream"] is False
    assert "format" not in payload


async def test_sensitive_true_json_mode_sets_format(monkeypatch):
    recorder = _Recorder(json_body={"response": "{}"})
    _mock_client_for(monkeypatch, recorder)

    await llm.complete("ahoj", sensitive=True, json_mode=True)

    import json as _json
    payload = _json.loads(recorder.requests[0].read())
    assert payload["format"] == "json"


async def test_sensitive_false_calls_router(monkeypatch):
    monkeypatch.setattr(llm, "ROUTER_API_KEY", "rk_test")
    monkeypatch.setattr(llm, "ROUTER_MODEL", "kr/claude-sonnet-4.5")
    recorder = _Recorder(json_body={"choices": [{"message": {"content": "hello from router"}}]})
    _mock_client_for(monkeypatch, recorder)

    result = await llm.complete("ahoj", sensitive=False)

    req = recorder.requests[0]
    assert req.url.path == "/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer rk_test"
    assert result == "hello from router"


async def test_sensitive_false_builds_messages_with_system(monkeypatch):
    monkeypatch.setattr(llm, "ROUTER_API_KEY", "rk_test")
    recorder = _Recorder(json_body={"choices": [{"message": {"content": "ok"}}]})
    _mock_client_for(monkeypatch, recorder)

    await llm.complete("ahoj", sensitive=False, model="some/model", system="jsi asistent")

    import json as _json
    payload = _json.loads(recorder.requests[0].read())
    assert payload["model"] == "some/model"
    assert payload["messages"] == [
        {"role": "system", "content": "jsi asistent"},
        {"role": "user", "content": "ahoj"},
    ]


async def test_sensitive_false_json_mode_sets_response_format(monkeypatch):
    monkeypatch.setattr(llm, "ROUTER_API_KEY", "rk_test")
    monkeypatch.setattr(llm, "ROUTER_MODEL", "some/model")
    recorder = _Recorder(json_body={"choices": [{"message": {"content": "{}"}}]})
    _mock_client_for(monkeypatch, recorder)

    await llm.complete("ahoj", sensitive=False, json_mode=True)

    import json as _json
    payload = _json.loads(recorder.requests[0].read())
    assert payload["response_format"] == {"type": "json_object"}


async def test_sensitive_false_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(llm, "ROUTER_API_KEY", "")
    with pytest.raises(RuntimeError):
        await llm.complete("ahoj", sensitive=False)


async def test_sensitive_false_missing_model_raises(monkeypatch):
    monkeypatch.setattr(llm, "ROUTER_API_KEY", "rk_test")
    monkeypatch.setattr(llm, "ROUTER_MODEL", "")
    with pytest.raises(RuntimeError):
        await llm.complete("ahoj", sensitive=False)
