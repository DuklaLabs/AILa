"""Shared LLM access point for AILa agents.

Routes each completion to one of two backends, chosen explicitly by the
caller via `sensitive`:

- `sensitive=True`  -> the local Ollama model (stays on our own hardware,
  never leaves the network). Use for anything touching real people's data
  — names, emails, DB contents, meeting transcripts — or whenever unsure.
- `sensitive=False` -> 9Router (https://9router.com, see docker-compose.yml
  service `router`), a self-hosted OpenAI-compatible router in front of
  40+ cloud/subscription/free providers. Use for requests that don't carry
  anything sensitive, to get access to bigger/cheaper/free models than
  what runs locally.

There is no default for `sensitive` on purpose — a caller has to say which
one it means, rather than silently inheriting a guess that could send
something sensitive to a third-party provider.
"""
import os
from typing import Optional

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
    if sensitive:
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
    body: dict = {"model": chosen_model, "messages": messages}
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
