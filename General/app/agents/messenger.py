import os

import httpx

MESSENGER_URL = os.getenv("MESSENGER_URL", "http://messenger:8005")


async def send_email(to: list[str], subject: str, body: str, html: bool = False) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{MESSENGER_URL}/send",
            json={"to": to, "subject": subject, "body": body, "html": html},
            headers={"X-Mail-Source": "general"},
        )
        resp.raise_for_status()
        return resp.json()
