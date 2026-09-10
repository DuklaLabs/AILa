"""Testy pro ailacore.llm – konfigurace + fallback bez běžícího LLM."""
import sys
import types

import pytest

from ailacore import llm


def test_host_and_model_defaults(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("AILA_AGENT_MODEL", raising=False)
    assert llm.ollama_host() == "http://ollama:11434"
    assert llm.default_model() == "llama3.2:8b-instruct"
    monkeypatch.setenv("OLLAMA_HOST", "http://lmstudio:1234")
    monkeypatch.setenv("AILA_AGENT_MODEL", "qwen2.5:14b")
    assert llm.ollama_host() == "http://lmstudio:1234"
    assert llm.default_model() == "qwen2.5:14b"


def test_is_fallback():
    assert llm.is_fallback({"_fallback": True}) is True
    assert llm.is_fallback({"ok": 1}) is False


def test_decide_without_ollama_package(monkeypatch):
    """Když `ollama` není nainstalované, decide vrátí _fallback, nespadne."""
    monkeypatch.setitem(sys.modules, "ollama", None)  # import ollama -> ImportError
    out = llm.decide("system", "user")
    assert llm.is_fallback(out)
    assert "_error" in out


def test_decide_parses_json_from_fake_ollama(monkeypatch):
    fake = types.ModuleType("ollama")

    class _Client:
        def __init__(self, *a, **k):
            pass

        def chat(self, *a, **k):
            return {"message": {"content": '{"verdict": "ok", "why": "vypadá dobře"}'}}

    fake.Client = _Client
    monkeypatch.setitem(sys.modules, "ollama", fake)

    out = llm.decide("s", "u", schema={"type": "object"})
    assert out == {"verdict": "ok", "why": "vypadá dobře"}


def test_decide_invalid_json_is_fallback(monkeypatch):
    fake = types.ModuleType("ollama")

    class _Client:
        def __init__(self, *a, **k):
            pass

        def chat(self, *a, **k):
            return {"message": {"content": "toto není JSON"}}

    fake.Client = _Client
    monkeypatch.setitem(sys.modules, "ollama", fake)

    out = llm.decide("s", "u")
    assert llm.is_fallback(out)


def test_decide_client_raises_is_fallback(monkeypatch):
    fake = types.ModuleType("ollama")

    class _Client:
        def __init__(self, *a, **k):
            pass

        def chat(self, *a, **k):
            raise RuntimeError("connection refused")

    fake.Client = _Client
    monkeypatch.setitem(sys.modules, "ollama", fake)

    out = llm.decide("s", "u")
    assert llm.is_fallback(out)
    assert "nedostupný" in out["_error"]
