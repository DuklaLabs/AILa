"""SMTP sending + email template rendering for the excuse-request workflow.

Uses stdlib smtplib (blocking) via asyncio.to_thread rather than an async
SMTP library — the codebase has no async mail dependency, and to_thread is
enough to keep a slow SMTP round-trip from stalling the whole event loop
(and every unrelated request on it).

Uses a plain jinja2.Environment, not FastAPI's Jinja2Templates — that
wrapper renders TemplateResponse around a Starlette Request object, which
doesn't exist when the weekly digest job (excuse_digest.py) renders emails
from a scheduler callback, not an HTTP handler.
"""
import asyncio
import logging
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from jinja2 import Environment, FileSystemLoader, select_autoescape

log = logging.getLogger(__name__)

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8003").rstrip("/")

_env = Environment(
    loader=FileSystemLoader("app/templates/email"),
    autoescape=select_autoescape(["html"]),
)


def render_email(template_name: str, **context) -> str:
    return _env.get_template(template_name).render(public_base_url=PUBLIC_BASE_URL, **context)


def _smtp_config() -> dict:
    return {
        "host": os.environ["SMTP_HOST"],
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.environ["SMTP_USER"],
        "password": os.environ["SMTP_PASSWORD"],
        "from_addr": os.getenv("SMTP_FROM_ADDR") or os.environ["SMTP_USER"],
        "from_name": os.getenv("SMTP_FROM_NAME", "DuklaLabs"),
    }


def _send_sync(to_addr: str, subject: str, html_body: str) -> None:
    cfg = _smtp_config()
    msg = EmailMessage()
    # `subject` must always be static, template-sourced text — never build
    # it from interpolated user data (student/teacher names). EmailMessage
    # doesn't strip embedded CRLF from header values, so that would be a
    # straightforward header-injection vector otherwise.
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg["from_name"], cfg["from_addr"]))
    msg["To"] = to_addr
    msg.set_content("Tento e-mail vyžaduje HTML klienta.")
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=10) as server:
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)


async def send_email(to_addr: str, subject: str, html_body: str) -> None:
    await asyncio.to_thread(_send_sync, to_addr, subject, html_body)
