"""Odeslání e-mailů agentů přes službu Messenger.

Render (HTML těla) i adresář koordinátorů si držíme tady, ať služba
`access-agents` nemusí importovat `AccessRequest/app/notify.py` (jiný image).
Logika `coordinator_emails()` zrcadlí `AccessRequest/app/notify.py`.
"""
from __future__ import annotations

import os

import httpx

MESSENGER_URL = os.getenv("MESSENGER_URL", "http://messenger:8005").rstrip("/")
NOTIFY_ENABLED = os.getenv("NOTIFY_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on", "ano",
}


def _split(raw: str) -> list[str]:
    return [a.strip() for a in raw.replace("\n", ";").replace(";", ",").split(",") if a.strip()]


def coordinator_emails() -> list[str]:
    """RELEASE_COORDINATOR_EMAILS, jinak hodnoty ze SUPERVISOR_EMAILS mapy."""
    direct = _split(os.getenv("RELEASE_COORDINATOR_EMAILS", ""))
    if direct:
        return direct
    out: list[str] = []
    for chunk in os.getenv("SUPERVISOR_EMAILS", "").replace("\n", ";").split(";"):
        if "=" in chunk:
            _name, email = chunk.split("=", 1)
            email = email.strip()
            if email and email not in out:
                out.append(email)
    return out


async def send_mail(
    *, to: list[str], subject: str, body: str, source: str, html: bool = True
) -> dict:
    """Best-effort odeslání přes Messenger. Vrací {sent_to|error}."""
    if not NOTIFY_ENABLED:
        return {"error": "notifikace vypnuté (NOTIFY_ENABLED)"}
    if not to:
        return {"error": "žádný příjemce"}
    payload = {"to": to, "subject": subject, "body": body, "html": html}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{MESSENGER_URL}/send", json=payload,
                headers={"X-Mail-Source": source},
            )
    except httpx.HTTPError as exc:
        return {"error": f"Messenger nedostupný: {exc}"}
    if resp.status_code != 200:
        return {"error": f"Messenger vrátil {resp.status_code}: {resp.text}"}
    reply = resp.json()
    if reply.get("status") != "OK":
        return {"error": f"Messenger: {reply}"}
    return {"sent_to": to}


def esc(s) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def wrap_html(title: str, inner: str) -> str:
    return f"""<!doctype html><html lang="cs"><body style="margin:0;background:#f4f5f7;
 font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#f4f5f7;padding:24px 12px;"><tr><td align="center">
  <table role="presentation" width="640" cellpadding="0" cellspacing="0"
         style="background:#fff;border-radius:12px;padding:24px;max-width:640px;">
    <tr><td style="font-size:18px;font-weight:700;padding-bottom:12px;">{esc(title)}</td></tr>
    <tr><td style="color:#333;font-size:14px;line-height:1.5;">{inner}</td></tr>
    <tr><td style="padding-top:18px;color:#888;font-size:12px;">
      Automaticky sestavil agent DuklaLabs (access-agents).</td></tr>
  </table>
</td></tr></table></body></html>"""
