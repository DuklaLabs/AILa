"""Zápis každého pokusu o odeslání do messaging.mail_log (v agentdb).

Best-effort: když se log nezapíše, odeslání e-mailu to nesmí ovlivnit.
Používá synchronní psycopg2 (endpoint /send je synchronní, malý objem pošty).
"""
from __future__ import annotations

import psycopg2

from app import config

_TRUE = {"1", "true", "yes", "on", "ano"}


def _enabled() -> bool:
    return str(config.MAIL_LOG_ENABLED).strip().lower() in _TRUE


def _with_body() -> bool:
    return str(config.MAIL_LOG_BODY).strip().lower() in _TRUE


def _as_list(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v]


def log_send(*, req, result: dict, source: str | None = None) -> None:
    """req = SendRequest (nebo dict), result = návrat mailer.send()."""
    if not _enabled():
        return
    try:
        get = req.get if isinstance(req, dict) else lambda k, d=None: getattr(req, k, d)
        body = get("body", "") or ""
        row = {
            "backend": result.get("backend"),
            "to": _as_list(get("to")),
            "cc": _as_list(get("cc")),
            "bcc": _as_list(get("bcc")),
            "subject": get("subject", "") or "",
            "status": result.get("status", "UNKNOWN"),
            "error": result.get("message") or result.get("error"),
            "delivered_to": result.get("redirected_to"),
            "redirected_from": result.get("redirected_from"),
            "has_ics": bool(get("ics")),
            "body_bytes": len(body.encode("utf-8")),
            "body": body if _with_body() else None,
            "source": source,
        }
        conn = psycopg2.connect(
            host=config.PG_HOST, port=config.PG_PORT, dbname=config.PG_DB,
            user=config.PG_USER, password=config.PG_PASSWORD, connect_timeout=3,
        )
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO messaging.mail_log
                        (backend, to_addrs, cc_addrs, bcc_addrs, subject, status,
                         error, delivered_to, redirected_from, has_ics, body_bytes,
                         body, source)
                    VALUES (%(backend)s, %(to)s, %(cc)s, %(bcc)s, %(subject)s,
                            %(status)s, %(error)s, %(delivered_to)s,
                            %(redirected_from)s, %(has_ics)s, %(body_bytes)s,
                            %(body)s, %(source)s)
                    """,
                    row,
                )
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 - log nikdy neshodí odeslání
        print(f"[maillog] zápis selhal: {type(exc).__name__}: {exc}", flush=True)
