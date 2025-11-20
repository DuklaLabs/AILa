import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")

async def ask_model(prompt: str):
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": "qwen2.5:14b",
                "prompt": prompt,
                "stream": False
            }
        )
        resp.raise_for_status()
        return resp.json()["response"]
