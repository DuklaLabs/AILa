"""Informování dozorů e-mailem o dění na otevřených hodinách DuklaLabs.

Odesílání samotné řeší služba Messenger (`POST {MESSENGER_URL}/send`) – tady
jen sestavíme text a vyřešíme, komu ho poslat.

Dozor je v `internal.open_hours.supervisor` uložený jen jako zobrazované
jméno (CSV, např. "Bc. Jan Petrášek, Václav Hlaváč"), e-mail u něj nikde
není. Mapu jméno → e-mail bereme z env proměnné `SUPERVISOR_EMAILS`
ve tvaru:

    SUPERVISOR_EMAILS="Bc. Jan Petrášek=petrasek@spssecb.cz; Václav Hlaváč=hlavac@spssecb.cz"

Klíče se párují na jména z `DUKLA_SUPERVISORS` (nejdřív přesně, jinak
podle tokenů jména bez titulů a na pořadí nezáleží).
"""
from __future__ import annotations

import html as _html
import os
from datetime import date, time

import httpx

MESSENGER_URL = os.getenv("MESSENGER_URL", "http://messenger:8005")
NOTIFY_ENABLED = os.getenv("NOTIFY_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on", "ano",
}
# Nepovinná adresa v kopii (např. koordinátor DuklaLabs).
BOOKING_NOTIFY_CC = [
    a.strip() for a in os.getenv("BOOKING_NOTIFY_CC", "").split(",") if a.strip()
]
# Veřejná adresa AccessRequest serveru – odkazy v e-mailu musí být použitelné
# z prohlížeče učitele, ne interní docker hostname. V produkci nastavit na
# skutečnou URL (https://...).
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8003").rstrip("/")

_CZ_WEEKDAYS = [
    "pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle",
]
_TITLE_TOKENS = {
    "bc", "mgr", "ing", "mudr", "mvdr", "phdr", "rndr", "judr", "paeddr",
    "dis", "prof", "doc", "csc", "drsc", "ph", "d", "dr", "th", "mba",
}


def _name_tokens(name: str) -> list[str]:
    """Malá písmena, bez titulů/iniciál – ať na pořadí a titulech nezáleží.
    Stejná logika jako v dukla_db, držená tu zvlášť, aby byl modul nezávislý."""
    out: list[str] = []
    for raw in (name or "").replace(",", " ").split():
        tok = raw.strip(".").lower()
        if not tok or "." in raw or tok in _TITLE_TOKENS or len(tok) < 2:
            continue
        out.append(tok)
    return out


def _load_email_map() -> list[tuple[list[str], str, str]]:
    """[(tokeny_jména, původní_jméno, email)] z env SUPERVISOR_EMAILS."""
    raw = os.getenv("SUPERVISOR_EMAILS", "")
    entries: list[tuple[list[str], str, str]] = []
    for chunk in raw.replace("\n", ";").split(";"):
        if "=" not in chunk:
            continue
        name, email = chunk.split("=", 1)
        name, email = name.strip(), email.strip()
        if name and email:
            entries.append((_name_tokens(name), name, email))
    return entries


def resolve_supervisor_emails(supervisor_csv: str | None) -> tuple[list[str], list[str]]:
    """Rozdělí CSV jmen dozorů a vrátí (nalezené_emaily, jména_bez_emailu)."""
    if not supervisor_csv:
        return [], []
    email_map = _load_email_map()
    found: list[str] = []
    missing: list[str] = []
    for part in supervisor_csv.split(","):
        name = part.strip()
        if not name:
            continue
        toks = _name_tokens(name)
        match = None
        for map_toks, map_name, email in email_map:
            if name.lower() == map_name.lower() or (
                toks and map_toks and set(toks) == set(map_toks)
            ):
                match = email
                break
        if match and match not in found:
            found.append(match)
        elif not match:
            missing.append(name)
    return found, missing


def _fmt_time(t) -> str:
    if isinstance(t, time):
        return t.strftime("%H:%M")
    return str(t)[:5] if t else ""


def _decision_buttons(token: str) -> str:
    base = f"{PUBLIC_BASE_URL}/rozhodnuti/{token}"
    return f"""
      <tr><td style="padding:20px 0 6px;">
        <table role="presentation" cellpadding="0" cellspacing="0"><tr>
          <td style="padding-right:10px;">
            <a href="{base}?volba=povolit"
               style="display:inline-block;padding:12px 22px;background:#1a7f37;
                      color:#fff;font-weight:600;text-decoration:none;
                      border-radius:8px;">Povolit uvolnění</a>
          </td>
          <td>
            <a href="{base}?volba=zamitnout"
               style="display:inline-block;padding:12px 22px;background:#b42318;
                      color:#fff;font-weight:600;text-decoration:none;
                      border-radius:8px;">Zamítnout</a>
          </td>
        </tr></table>
      </td></tr>
      <tr><td style="padding:4px 0 0;color:#666;font-size:12px;">
        Tlačítko otevře stránku s potvrzením. Rozhodnutí lze později změnit.<br>
        Kdyby tlačítka nešla: {base}
      </td></tr>"""


def build_booking_email(
    *,
    student_name: str,
    class_group: str | None,
    day: date,
    hour_number: int | None,
    start_time=None,
    end_time=None,
    note: str | None = None,
    booked_count: int | None = None,
    capacity: int | None = None,
    decision_token: str | None = None,
) -> tuple[str, str]:
    weekday = _CZ_WEEKDAYS[day.weekday()]
    date_str = f"{day.day}.{day.month}.{day.year}"
    hour_str = f"{hour_number}. hodina" if hour_number is not None else "hodina"
    time_range = ""
    if start_time and end_time:
        time_range = f" ({_fmt_time(start_time)}–{_fmt_time(end_time)})"

    subject = f"DuklaLabs: {student_name} se zapsal na {date_str} – {hour_str}"

    e = _html.escape
    student_line = e(student_name) + (f" ({e(class_group)})" if class_group else "")
    rows = [
        f'<tr><td style="color:#666;font-size:13px;">Student</td></tr>'
        f'<tr><td style="font-weight:600;padding-bottom:8px;">{student_line}</td></tr>',
        f'<tr><td style="color:#666;font-size:13px;">Hodina</td></tr>'
        f'<tr><td style="font-weight:600;padding-bottom:8px;">'
        f'{e(weekday)} {date_str}, {e(hour_str)}{e(time_range)}</td></tr>',
    ]
    if note:
        rows.append(
            f'<tr><td style="color:#666;font-size:13px;">Poznámka k hodině</td></tr>'
            f'<tr><td style="font-weight:600;padding-bottom:8px;">{e(note)}</td></tr>'
        )
    if booked_count is not None and capacity is not None:
        rows.append(
            f'<tr><td style="color:#666;font-size:13px;">Obsazenost</td></tr>'
            f'<tr><td style="font-weight:600;padding-bottom:8px;">'
            f'{booked_count}/{capacity}</td></tr>'
        )
    buttons = _decision_buttons(decision_token) if decision_token else ""

    html_body = f"""<!doctype html><html lang="cs"><body style="margin:0;
 background:#f4f5f7;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
 color:#1a1a1a;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#f4f5f7;padding:24px 12px;"><tr><td align="center">
  <table role="presentation" width="520" cellpadding="0" cellspacing="0"
         style="background:#fff;border-radius:12px;padding:24px;max-width:520px;">
    <tr><td style="font-size:18px;font-weight:700;padding-bottom:4px;">
      Uvolnění z výuky – DuklaLabs</td></tr>
    <tr><td style="color:#444;padding-bottom:12px;">
      Na otevřenou hodinu DuklaLabs se právě zapsal student. Rozhodněte prosím,
      zda může být uvolněn z výuky.</td></tr>
    <tr><td><table role="presentation" width="100%" cellpadding="0"
        cellspacing="0">{''.join(rows)}</table></td></tr>
    {buttons}
    <tr><td style="padding-top:18px;color:#888;font-size:12px;">
      Přehled zápisů najdete v administraci DuklaLabs.</td></tr>
  </table>
</td></tr></table></body></html>"""
    return subject, html_body


async def notify_booking(
    *,
    supervisor_csv: str | None,
    student_name: str,
    class_group: str | None,
    day: date,
    hour_number: int | None,
    start_time=None,
    end_time=None,
    note: str | None = None,
    booked_count: int | None = None,
    capacity: int | None = None,
    decision_token: str | None = None,
) -> dict:
    """Pošle dozorovi (dozorům) info o novém zápisu + tlačítka Povolit/Zamítnout.
    Nikdy nevyhazuje výjimku – rezervace už je uložená, případný problém
    s mailem ji nesmí shodit."""
    result: dict = {"notified": [], "skipped": [], "error": None}
    if not NOTIFY_ENABLED:
        result["error"] = "notifikace vypnuté (NOTIFY_ENABLED)"
        return result

    emails, missing = resolve_supervisor_emails(supervisor_csv)
    result["skipped"] = missing
    if not emails:
        if not result["error"]:
            result["error"] = "žádný dozor s namapovaným e-mailem"
        return result

    subject, body = build_booking_email(
        student_name=student_name,
        class_group=class_group,
        day=day,
        hour_number=hour_number,
        start_time=start_time,
        end_time=end_time,
        note=note,
        booked_count=booked_count,
        capacity=capacity,
        decision_token=decision_token,
    )
    payload = {"to": emails, "subject": subject, "body": body, "html": True}
    if BOOKING_NOTIFY_CC:
        payload["cc"] = BOOKING_NOTIFY_CC

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{MESSENGER_URL}/send", json=payload)
    except httpx.HTTPError as exc:
        result["error"] = f"Messenger nedostupný: {exc}"
        return result

    if resp.status_code != 200:
        result["error"] = f"Messenger vrátil {resp.status_code}: {resp.text}"
        return result

    reply = resp.json()
    if reply.get("status") == "OK":
        result["notified"] = emails
    else:
        result["error"] = f"Messenger: {reply}"
    return result
