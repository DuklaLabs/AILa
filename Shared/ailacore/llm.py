"""Shared LLM access point for AILa agents.

Routes each completion to one of two backends, chosen explicitly by the
caller via `sensitive`:

- `sensitive=True`  -> the "trusted" backend. Use for anything touching real
  people's data — names, emails, DB contents, meeting transcripts — or
  whenever unsure. Which physical backend that actually is depends on
  `LLM_SENSITIVE_BACKEND` (see below) — it is NOT always local.
- `sensitive=False` -> always 9Router (https://9router.com, see
  docker-compose.yml service `router`), a self-hosted OpenAI-compatible
  router in front of 40+ cloud/subscription/free providers. Use for requests
  that don't carry anything sensitive, to get access to bigger/cheaper/free
  models than what runs locally.

There is no default for `sensitive` on purpose — a caller has to say which
one it means, rather than silently inheriting a guess that could send
something sensitive to a third-party provider.

`LLM_SENSITIVE_BACKEND` (env, default `"ollama"`) picks what `sensitive=True`
and `decide()` actually hit:
- `"ollama"` (default) -> local Ollama, stays on our own hardware.
- `"router"` -> 9Router, same as the `sensitive=False` path. This is an
  explicit operator override for when there is no local Ollama to send
  trusted traffic to (e.g. no GPU) — turning it on means real people's data
  (student names, meeting transcripts, ...) goes to whatever provider is
  configured for `ROUTER_MODEL` in the 9Router dashboard, same as any other
  cloud call. Only set this with the operator's explicit sign-off; flip it
  back to `"ollama"` (or unset it) once local inference is available again.

`decide()` is a synchronous, JSON-mode convenience wrapper around the same
`sensitive=True` backend, for scheduler-driven agents (AccessAgents/*) that
call it as a plain blocking function and always want a structured dict back.
It never raises: on any failure it returns `{"_fallback": True, "_error":
...}` so a caller can treat that as "needs manual review" and never crash on
a flaky or absent LLM (check with `is_fallback()`).
"""
import json
import os
from typing import Any, Optional

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# Client-side config for the 9Router service: ROUTER_URL points at its
# OpenAI-compatible endpoint, ROUTER_API_KEY is a key minted in the 9Router
# dashboard (Providers/models themselves are also configured there, not via
# env — see Shared/README.md).
ROUTER_URL = os.getenv("ROUTER_URL", "http://router:20128/v1")
ROUTER_API_KEY = os.getenv("ROUTER_API_KEY", "")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "")

# See module docstring. Anything other than "router" behaves like before
# (sensitive=True/decide() -> Ollama).
LLM_SENSITIVE_BACKEND = os.getenv("LLM_SENSITIVE_BACKEND", "ollama").strip().lower()


async def complete(
    prompt: str,
    *,
    sensitive: bool,
    model: Optional[str] = None,
    system: Optional[str] = None,
    json_mode: bool = False,
    timeout: float = 300,
) -> str:
    """Run `prompt` and return the plain-text completion.

    `model` overrides the module-level default model for whichever backend
    `sensitive` selects. `system` adds a system message (folded into the
    prompt for Ollama, which has no separate system role in
    `/api/generate`). `json_mode` asks the backend to constrain output to
    JSON, where supported.
    """
    if sensitive and LLM_SENSITIVE_BACKEND != "router":
        return await _complete_ollama(prompt, model=model, system=system, json_mode=json_mode, timeout=timeout)
    return await _complete_router(prompt, model=model, system=system, json_mode=json_mode, timeout=timeout)


async def _complete_ollama(
    prompt: str, *, model: Optional[str], system: Optional[str], json_mode: bool, timeout: float,
) -> str:
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    body: dict = {"model": model or OLLAMA_MODEL, "prompt": full_prompt, "stream": False}
    if json_mode:
        body["format"] = "json"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/generate", json=body)
        resp.raise_for_status()
        return resp.json()["response"]


async def _complete_router(
    prompt: str, *, model: Optional[str], system: Optional[str], json_mode: bool, timeout: float,
) -> str:
    if not ROUTER_API_KEY:
        raise RuntimeError("ROUTER_API_KEY is not set")
    chosen_model = model or ROUTER_MODEL
    if not chosen_model:
        raise RuntimeError("No model given and ROUTER_MODEL is not set")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body: dict = {"model": chosen_model, "messages": messages, "stream": False}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(base_url=ROUTER_URL, timeout=timeout) as client:
        resp = await client.post(
            "/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {ROUTER_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def is_fallback(result: dict) -> bool:
    """True when `decide()` didn't return a real model decision."""
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
    """Ask the local Ollama model a question, get a parsed JSON dict back.

    `schema` is an optional JSON-schema fragment describing the expected
    shape; when given it's both appended to the system prompt (so the model
    sees it in plain text) and passed as Ollama's structured-output `format`.
    Any failure — network, timeout, non-JSON or non-object response — is
    reported through the `_fallback` contract instead of an exception, since
    callers are scheduler jobs that must keep running.
    """
    sys_prompt = system.strip()
    if schema is not None:
        sys_prompt += (
            "\n\nOdpověz výhradně JSON objektem odpovídajícím tomuto schématu "
            "(žádný text okolo):\n" + json.dumps(schema, ensure_ascii=False)
        )

    try:
        if LLM_SENSITIVE_BACKEND == "router":
            content = _decide_router(sys_prompt, user, model=model, temperature=temperature, timeout=timeout)
        else:
            content = _decide_ollama(sys_prompt, user, schema=schema, model=model, temperature=temperature, timeout=timeout)
    except Exception as e:  # noqa: BLE001 - agent must never crash on LLM errors
        return _fallback(f"LLM nedostupný: {e}")

    try:
        parsed = json.loads(_strip_code_fence(content))
    except (ValueError, TypeError) as e:
        return _fallback(f"nevalidní JSON z modelu: {e}: {content[:200]!r}")

    if not isinstance(parsed, dict):
        return _fallback(f"model nevrátil objekt, ale {type(parsed).__name__}")
    return parsed


def _strip_code_fence(content: str) -> str:
    """Some chat models (seen via 9Router) wrap JSON in a markdown code
    fence even with response_format=json_object; Ollama's `format` doesn't.
    Strip a leading/trailing ```json ... ``` or ``` ... ``` if present."""
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```")
        text = text.removesuffix("```")
        text = text.strip()
    return text


def _decide_ollama(
    sys_prompt: str, user: str, *, schema: Optional[dict], model: Optional[str], temperature: float, timeout: float,
) -> str:
    fmt: Any = schema if schema is not None else "json"
    body = {
        "model": model or OLLAMA_MODEL,
        "prompt": f"{sys_prompt}\n\n{user}",
        "stream": False,
        "format": fmt,
        "options": {"temperature": temperature},
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{OLLAMA_URL}/api/generate", json=body)
        resp.raise_for_status()
        return resp.json().get("response") or ""


def _decide_router(
    sys_prompt: str, user: str, *, model: Optional[str], temperature: float, timeout: float,
) -> str:
    if not ROUTER_API_KEY:
        raise RuntimeError("ROUTER_API_KEY is not set")
    chosen_model = model or ROUTER_MODEL
    if not chosen_model:
        raise RuntimeError("No model given and ROUTER_MODEL is not set")
    body = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "stream": False,
    }
    with httpx.Client(base_url=ROUTER_URL, timeout=timeout) as client:
        resp = client.post(
            "/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {ROUTER_API_KEY}"},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
