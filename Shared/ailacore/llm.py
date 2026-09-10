"""Sdílený LLM klient pro agentní vrstvu (§21 databanky).

Lokální model přes Ollamu – žádné API klíče, data neopouští infrastrukturu.
Konfigurace přes env:

    OLLAMA_HOST        adresa Ollama serveru (default http://ollama:11434)
    AILA_AGENT_MODEL   název modelu (default llama3.2:8b-instruct)

`decide()` je jediná vstupní funkce: dostane systémový + uživatelský prompt a
vrátí **strukturovaný dict** (JSON mode). Když LLM není dostupný nebo vrátí
nevalidní JSON, vrací `{"_fallback": True, "_error": "..."}` – volající to má
přeložit na „nevím → k ruční kontrole“ a **nikdy na tom nespadnout**
(best-effort, agent smí selhat tiše).

`ollama` balíček je nepovinná závislost (`pip install "ailacore[agents]"` nebo
ho má služba ve vlastním requirements). Import je líný, ať `ailacore` funguje
i tam, kde se agenti nepoužívají.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

_DEFAULT_HOST = "http://ollama:11434"
_DEFAULT_MODEL = "llama3.2:8b-instruct"


def ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", _DEFAULT_HOST).strip() or _DEFAULT_HOST


def default_model() -> str:
    return os.getenv("AILA_AGENT_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL


def is_fallback(result: dict) -> bool:
    """True, když `decide()` nevrátil skutečné rozhodnutí modelu."""
    return bool(result.get("_fallback"))


def _fallback(error: str) -> dict:
    print(f"[ailacore.llm] fallback: {error}", flush=True)
    return {"_fallback": True, "_error": error}


def decide(
    system: str,
    user: str,
    *,
    schema: Optional[dict] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
    timeout: float = 60.0,
) -> dict:
    """Zeptá se modelu a vrátí rozparsovaný JSON dict.

    `schema` je nepovinný JSON-schema fragment; když je zadaný, přilepí se do
    systémového promptu jako popis očekávaného tvaru odpovědi (a u novějších
    Ollam se předá i jako `format`). Při jakékoliv chybě → `_fallback`.
    """
    try:
        import ollama  # noqa: PLC0415 - líný import, nepovinná závislost
    except Exception as e:  # noqa: BLE001
        return _fallback(f"ollama balíček není k dispozici: {e}")

    sys_prompt = system.strip()
    if schema is not None:
        sys_prompt += (
            "\n\nOdpověz výhradně JSON objektem odpovídajícím tomuto schématu "
            "(žádný text okolo):\n" + json.dumps(schema, ensure_ascii=False)
        )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user},
    ]

    fmt: Any = "json"
    if schema is not None:
        # novější ollama umí strukturovaný výstup podle schématu; starší spadne
        # zpět na prosté "json" (řeší except níž retryem).
        fmt = schema

    try:
        client = ollama.Client(host=ollama_host(), timeout=timeout)
        resp = client.chat(
            model=model or default_model(),
            messages=messages,
            format=fmt,
            options={"temperature": temperature},
        )
    except Exception as e:  # noqa: BLE001 - zkus ještě prostý json format
        try:
            client = ollama.Client(host=ollama_host(), timeout=timeout)
            resp = client.chat(
                model=model or default_model(),
                messages=messages,
                format="json",
                options={"temperature": temperature},
            )
        except Exception as e2:  # noqa: BLE001
            return _fallback(f"LLM nedostupný: {e2 or e}")

    content = (resp.get("message") or {}).get("content") or ""
    try:
        parsed = json.loads(content)
    except (ValueError, TypeError) as e:
        return _fallback(f"nevalidní JSON z modelu: {e}: {content[:200]!r}")

    if not isinstance(parsed, dict):
        return _fallback(f"model nevrátil objekt, ale {type(parsed).__name__}")
    return parsed
