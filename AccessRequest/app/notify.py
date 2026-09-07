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

import hashlib
import hmac
import html as _html
import os
from datetime import date, time

import httpx

MESSENGER_URL = os.getenv("MESSENGER_URL", "http://messenger:8005")
NOTIFY_ENABLED = os.getenv("NOTIFY_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on", "ano",
}
# Okamžitý e-mail při každém jednotlivém zápisu. Default vypnuto – primární
# cesta je souhrnný e-mail pro učitele (viz send_supervisor_digest).
NOTIFY_ON_BOOKING = os.getenv("NOTIFY_ON_BOOKING", "false").strip().lower() in {
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
# Tajný klíč pro podpis odkazů na rozhodovací stránku učitele. V produkci
# nastavit na náhodnou hodnotu; její změna zneplatní všechny staré odkazy.
DECISION_SECRET = os.getenv("DECISION_SECRET", "dev-decision-secret-change-me")
# Koordinátor(ři) uvolňování z výuky. Prázdné = použijí se adresy dozorů
# z SUPERVISOR_EMAILS.
RELEASE_COORDINATOR_EMAILS = [
    a.strip() for a in os.getenv("RELEASE_COORDINATOR_EMAILS", "").replace(";", ",").split(",")
    if a.strip()
]

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


def configured_supervisors() -> list[str]:
    """Kanonická jména dozorů, na která máme e-mail (klíče SUPERVISOR_EMAILS)."""
    return [name for _toks, name, _email in _load_email_map()]


def supervisor_email(canonical_name: str) -> str | None:
    for _toks, name, email in _load_email_map():
        if name.lower() == canonical_name.lower():
            return email
    return None


def supervisor_matches(supervisor_csv: str | None, canonical_name: str) -> bool:
    """Patří CSV dozorů z open_hours ke konkrétnímu kanonickému jménu?
    (Přesně, nebo shodná množina tokenů jména bez titulů.)"""
    if not supervisor_csv:
        return False
    target = set(_name_tokens(canonical_name))
    for part in supervisor_csv.split(","):
        p = part.strip()
        if not p:
            continue
        if p.lower() == canonical_name.lower():
            return True
        if target and set(_name_tokens(p)) == target:
            return True
    return False


def decision_token(kind: str, name: str) -> str:
    """Stabilní podepsaný token pro rozhodovací stránku dané identity.
    kind = "teacher" (běžný učitel z rozvrhu) nebo "supervisor" (dozor)."""
    mac = hmac.new(
        DECISION_SECRET.encode(), f"{kind}:{name}".encode(), hashlib.sha256
    )
    return mac.hexdigest()[:32]


def supervisor_token(canonical_name: str) -> str:
    return decision_token("supervisor", canonical_name)


def teacher_token(name: str) -> str:
    return decision_token("teacher", name)


def resolve_supervisor_token(token: str) -> str | None:
    """Token → kanonické jméno dozora (nebo None). Zpětná kompatibilita."""
    if not token:
        return None
    for name in configured_supervisors():
        if hmac.compare_digest(supervisor_token(name), token):
            return name
    return None


def resolve_decision_token(
    token: str, teacher_names: list[str]
) -> tuple[str, str] | None:
    """Token → (kind, jméno). Dozoři jsou konfigurovaní; učitele předává
    volající (kandidáti z nadcházejících zápisů)."""
    if not token:
        return None
    for name in configured_supervisors():
        if hmac.compare_digest(supervisor_token(name), token):
            return ("supervisor", name)
    for name in teacher_names:
        if hmac.compare_digest(teacher_token(name), token):
            return ("teacher", name)
    return None


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
    if not NOTIFY_ON_BOOKING:
        result["error"] = "okamžité notifikace vypnuté (NOTIFY_ON_BOOKING)"
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

    err = await _send_via_messenger(payload)
    if err:
        result["error"] = err
    else:
        result["notified"] = emails
    return result


async def _send_via_messenger(payload: dict) -> str | None:
    """Pošle payload službě Messenger. Vrací None při úspěchu, jinak text chyby."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{MESSENGER_URL}/send", json=payload)
    except httpx.HTTPError as exc:
        return f"Messenger nedostupný: {exc}"
    if resp.status_code != 200:
        return f"Messenger vrátil {resp.status_code}: {resp.text}"
    reply = resp.json()
    if reply.get("status") != "OK":
        return f"Messenger: {reply}"
    return None


# ----------------------------------------------------------------------
# SOUHRNNÝ E-MAIL PRO UČITELE (digest) – jeden mail = všichni jeho studenti,
# rozhodování probíhá na webové stránce /rozhodovani/{token}.
# ----------------------------------------------------------------------

def _digest_row_html(item: dict) -> str:
    e = _html.escape
    d: date = item["day"]
    weekday = _CZ_WEEKDAYS[d.weekday()]
    date_str = f"{d.day}.{d.month}.{d.year}"
    hour = f"{item['hour_number']}. h" if item.get("hour_number") is not None else ""
    span = ""
    if item.get("start_time") and item.get("end_time"):
        span = f" {_fmt_time(item['start_time'])}–{_fmt_time(item['end_time'])}"
    approved = item.get("approved")
    if approved is True:
        stav = '<span style="color:#1a7f37;font-weight:600;">povoleno</span>'
    elif approved is False:
        stav = '<span style="color:#b42318;font-weight:600;">zamítnuto</span>'
    else:
        stav = '<span style="color:#9a6700;font-weight:600;">nové</span>'
    student = e(f"{item['first_name']} {item['last_name']}")
    if item.get("class_group"):
        student += f" ({e(item['class_group'])})"
    note = f" – {e(item['note'])}" if item.get("note") else ""
    return (
        f'<tr>'
        f'<td style="padding:6px 10px 6px 0;border-bottom:1px solid #eee;">{student}</td>'
        f'<td style="padding:6px 10px 6px 0;border-bottom:1px solid #eee;'
        f'white-space:nowrap;">{e(weekday)} {date_str} {e(hour)}{e(span)}{note}</td>'
        f'<td style="padding:6px 0;border-bottom:1px solid #eee;">{stav}</td>'
        f'</tr>'
    )


def _cz_zadost(n: int) -> str:
    """České skloňování: 1 žádost, 2–4 žádosti, 5+ žádostí."""
    if n == 1:
        return "žádost"
    if 2 <= n <= 4:
        return "žádosti"
    return "žádostí"


def build_digest_email(
    recipient_name: str, items: list[dict], *, link: str, intro: str | None = None
) -> tuple[str, str]:
    """items: dicts s klíči first_name,last_name,class_group,day,hour_number,
    start_time,end_time,note,approved. Předpokládá aspoň jednu položku."""
    new_count = sum(1 for it in items if it.get("approved") is None)
    rows = "".join(_digest_row_html(it) for it in items)

    if new_count:
        adj = "nová" if new_count == 1 else "nové" if new_count <= 4 else "nových"
        subject = (
            f"DuklaLabs: {new_count} {adj} {_cz_zadost(new_count)} "
            f"o uvolnění studentů z výuky"
        )
        headline = (
            f"Máte <strong>{new_count}</strong> {adj} {_cz_zadost(new_count)} "
            f"o uvolnění studenta z výuky."
        )
    else:
        subject = "DuklaLabs: přehled žádostí o uvolnění studentů"
        headline = "Aktuální přehled žádostí o uvolnění studentů z výuky."
    if intro:
        headline = f"{_html.escape(intro)} {headline}"

    html_body = f"""<!doctype html><html lang="cs"><body style="margin:0;
 background:#f4f5f7;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
 color:#1a1a1a;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#f4f5f7;padding:24px 12px;"><tr><td align="center">
  <table role="presentation" width="560" cellpadding="0" cellspacing="0"
         style="background:#fff;border-radius:12px;padding:24px;max-width:560px;">
    <tr><td style="font-size:18px;font-weight:700;padding-bottom:4px;">
      Uvolnění z výuky – DuklaLabs</td></tr>
    <tr><td style="color:#444;padding-bottom:14px;">{headline}</td></tr>
    <tr><td>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="font-size:14px;">{rows}</table>
    </td></tr>
    <tr><td style="padding:22px 0 6px;">
      <a href="{link}" style="display:inline-block;padding:12px 24px;
         background:#1a4fd6;color:#fff;font-weight:600;text-decoration:none;
         border-radius:8px;">Otevřít rozhodování</a>
    </td></tr>
    <tr><td style="padding-top:4px;color:#666;font-size:12px;">
      Na stránce lze u každého studenta zvlášť povolit / zamítnout, nebo
      použít „Povolit vše" / „Zamítnout vše". Rozhodnutí jde kdykoli změnit.<br>
      Kdyby tlačítko nešlo: {link}
    </td></tr>
  </table>
</td></tr></table></body></html>"""
    return subject, html_body


async def send_decision_digest(
    kind: str, name: str, email: str, items: list[dict]
) -> dict:
    """Pošle jedné identitě (učitel/dozor) rozhodovací digest.
    kind ∈ {"teacher","supervisor"}; email je předvyřešený volajícím."""
    result: dict = {"kind": kind, "name": name, "sent_to": None, "error": None}
    if not NOTIFY_ENABLED:
        result["error"] = "notifikace vypnuté (NOTIFY_ENABLED)"
        return result
    if not email:
        result["error"] = "bez e-mailu"
        return result
    if not items:
        result["error"] = "nic k odeslání"
        return result

    link = f"{PUBLIC_BASE_URL}/rozhodovani/{decision_token(kind, name)}"
    if kind == "teacher":
        intro = (
            "Podle rozvrhu tyto studenty učíte v době, kdy chtějí být uvolněni "
            "na DuklaLabs."
        )
    else:
        intro = "Tyto zápisy spadají pod vás jako dozora DuklaLabs."
    subject, body = build_digest_email(name, items, link=link, intro=intro)
    payload = {"to": [email], "subject": subject, "body": body, "html": True}
    if BOOKING_NOTIFY_CC:
        payload["cc"] = BOOKING_NOTIFY_CC

    err = await _send_via_messenger(payload)
    if err:
        result["error"] = err
    else:
        result["sent_to"] = email
    return result


# ----------------------------------------------------------------------
# DENNÍ PŘEHLED DOCHÁZKY PRO DOZORA
# ----------------------------------------------------------------------

def _roster_row_html(it: dict) -> str:
    e = _html.escape
    ap = it.get("approved")
    stav = (
        '<span style="color:#1a7f37;">povoleno</span>' if ap is True
        else '<span style="color:#b42318;">zamítnuto</span>' if ap is False
        else '<span style="color:#9a6700;">nerozhodnuto</span>'
    )
    at = it.get("attended")
    doch = "přišel" if at is True else "nepřišel" if at is False else "—"
    student = e(it["student_name"]) + (
        f' <span style="color:#888;">{e(it["class_group"])}</span>'
        if it.get("class_group") else ""
    )
    hour = f"{it['hour_number']}. h" if it.get("hour_number") is not None else ""
    teacher = e(it.get("teacher_name") or "—")
    subj = e(it.get("subject") or "")
    return (
        f'<tr>'
        f'<td style="padding:5px 10px 5px 0;border-bottom:1px solid #eee;">{student}</td>'
        f'<td style="padding:5px 10px 5px 0;border-bottom:1px solid #eee;'
        f'white-space:nowrap;">{e(hour)} {subj}</td>'
        f'<td style="padding:5px 10px 5px 0;border-bottom:1px solid #eee;">{teacher}</td>'
        f'<td style="padding:5px 10px 5px 0;border-bottom:1px solid #eee;">{stav}</td>'
        f'<td style="padding:5px 0;border-bottom:1px solid #eee;">{doch}</td>'
        f'</tr>'
    )


def build_supervisor_roster_email(
    supervisor_name: str, by_day: list[tuple[date, list[dict]]]
) -> tuple[str, str]:
    """by_day: [(date, [item,...])]; item = student_name, class_group, hour_number,
    subject, teacher_name, approved, attended."""
    link = f"{PUBLIC_BASE_URL}/rozhodovani/{supervisor_token(supervisor_name)}"
    total = sum(len(items) for _d, items in by_day)

    blocks = []
    for d, items in by_day:
        head = f"{_CZ_WEEKDAYS[d.weekday()]} {d.day}.{d.month}.{d.year}"
        rows = "".join(_roster_row_html(it) for it in items)
        blocks.append(
            f'<tr><td style="padding:16px 0 4px;font-weight:700;">{head}</td></tr>'
            f'<tr><td><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" style="font-size:13px;">'
            f'<tr style="color:#666;"><td>Student</td><td>Hodina</td>'
            f'<td>Učitel</td><td>Uvolnění</td><td>Docházka</td></tr>'
            f'{rows}</table></td></tr>'
        )

    subject = f"DuklaLabs: přehled docházky ({total} zápisů)"
    html_body = f"""<!doctype html><html lang="cs"><body style="margin:0;
 background:#f4f5f7;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
 color:#1a1a1a;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#f4f5f7;padding:24px 12px;"><tr><td align="center">
  <table role="presentation" width="640" cellpadding="0" cellspacing="0"
         style="background:#fff;border-radius:12px;padding:24px;max-width:640px;">
    <tr><td style="font-size:18px;font-weight:700;">Docházka DuklaLabs – přehled</td></tr>
    <tr><td style="color:#444;padding-bottom:6px;">Dozor: <strong>{_html.escape(supervisor_name)}</strong>.
      Studenti, kteří se přihlásili na vaše otevřené hodiny.</td></tr>
    {''.join(blocks)}
    <tr><td style="padding:22px 0 6px;">
      <a href="{link}" style="display:inline-block;padding:12px 24px;
         background:#1a4fd6;color:#fff;font-weight:600;text-decoration:none;
         border-radius:8px;">Otevřít přehled a docházku</a>
    </td></tr>
    <tr><td style="padding-top:4px;color:#666;font-size:12px;">
      Na stránce lze u každého studenta odklikat „přišel / nepřišel" a případně
      přepsat rozhodnutí učitele. Kdyby tlačítko nešlo: {link}
    </td></tr>
  </table>
</td></tr></table></body></html>"""
    return subject, html_body


async def send_supervisor_roster(
    supervisor_name: str, by_day: list[tuple[date, list[dict]]]
) -> dict:
    result: dict = {"supervisor": supervisor_name, "sent_to": None, "error": None}
    if not NOTIFY_ENABLED:
        result["error"] = "notifikace vypnuté (NOTIFY_ENABLED)"
        return result
    email = supervisor_email(supervisor_name)
    if not email:
        result["error"] = "dozor bez namapovaného e-mailu"
        return result
    if not by_day:
        result["error"] = "nic k odeslání"
        return result

    subject, body = build_supervisor_roster_email(supervisor_name, by_day)
    payload = {"to": [email], "subject": subject, "body": body, "html": True}
    if BOOKING_NOTIFY_CC:
        payload["cc"] = BOOKING_NOTIFY_CC
    err = await _send_via_messenger(payload)
    if err:
        result["error"] = err
    else:
        result["sent_to"] = email
    return result


# ----------------------------------------------------------------------
# SOUHLAS S UVOLŇOVÁNÍM STUDENTA Z VÝUKY (při registraci)
# ----------------------------------------------------------------------

def coordinator_emails() -> list[str]:
    if RELEASE_COORDINATOR_EMAILS:
        return list(RELEASE_COORDINATOR_EMAILS)
    return [e for _t, _n, e in _load_email_map()]


def build_release_request_email(
    *, role: str, student_name: str, class_group: str | None,
    release_token: str, class_teacher_name: str | None,
) -> tuple[str, str]:
    e = _html.escape
    base = f"{PUBLIC_BASE_URL}/uvolneni/{release_token}"
    kdo = "třídního učitele" if role == "tridni" else "koordinátora DuklaLabs"
    who_line = (
        f"Jste veden(a) jako <strong>třídní učitel</strong> třídy "
        f"{e(class_group or '?')}." if role == "tridni"
        else "Rozhodujete jako <strong>koordinátor DuklaLabs</strong>."
    )
    ct = (
        f"<br>Třídní učitel: {e(class_teacher_name)}."
        if class_teacher_name and role == "koordinator" else ""
    )
    subject = (
        f"DuklaLabs: souhlas s uvolňováním studenta z výuky – "
        f"{student_name}"
    )
    html_body = f"""<!doctype html><html lang="cs"><body style="margin:0;
 background:#f4f5f7;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
 color:#1a1a1a;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#f4f5f7;padding:24px 12px;"><tr><td align="center">
  <table role="presentation" width="520" cellpadding="0" cellspacing="0"
         style="background:#fff;border-radius:12px;padding:24px;max-width:520px;">
    <tr><td style="font-size:18px;font-weight:700;padding-bottom:4px;">
      Uvolňování z výuky – DuklaLabs</td></tr>
    <tr><td style="color:#444;padding-bottom:12px;">
      Do DuklaLabs se zaregistroval student <strong>{e(student_name)}</strong>
      {('(' + e(class_group) + ')') if class_group else ''} a žádá, aby se mohl
      během školního roku uvolňovat z výuky na projektové hodiny.<br>{who_line}{ct}
    </td></tr>
    <tr><td style="color:#444;padding-bottom:6px;">
      Dokud <strong>třídní učitel i koordinátor</strong> neodsouhlasí, student se
      NEsmí zapsat na hodinu, kdy má podle rozvrhu vlastní výuku (na volné hodiny
      ano).</td></tr>
    <tr><td style="padding:18px 0 6px;">
      <a href="{base}?role={role}&amp;volba=ano"
         style="display:inline-block;padding:12px 22px;background:#1a7f37;color:#fff;
         font-weight:600;text-decoration:none;border-radius:8px;">Souhlasím</a>
      &nbsp;
      <a href="{base}?role={role}&amp;volba=ne"
         style="display:inline-block;padding:12px 22px;background:#b42318;color:#fff;
         font-weight:600;text-decoration:none;border-radius:8px;">Nesouhlasím</a>
    </td></tr>
    <tr><td style="padding-top:4px;color:#666;font-size:12px;">
      Tlačítko otevře stránku s potvrzením; rozhodnutí lze později změnit.<br>
      Kdyby tlačítka nešla: {base}
    </td></tr>
  </table>
</td></tr></table></body></html>"""
    return subject, html_body


async def send_release_requests(
    *, student_name: str, class_group: str | None, release_token: str,
    class_teacher: dict | None,
) -> dict:
    """Rozešle žádost o souhlas s uvolňováním: třídnímu učiteli + koordinátorům.
    Best-effort."""
    result: dict = {"sent": [], "skipped": [], "errors": []}
    if not NOTIFY_ENABLED:
        result["errors"].append("notifikace vypnuté (NOTIFY_ENABLED)")
        return result

    async def _one(role: str, email: str):
        subj, body = build_release_request_email(
            role=role, student_name=student_name, class_group=class_group,
            release_token=release_token,
            class_teacher_name=(class_teacher or {}).get("name"),
        )
        payload = {"to": [email], "subject": subj, "body": body, "html": True}
        err = await _send_via_messenger(payload)
        (result["errors"] if err else result["sent"]).append(
            {"role": role, "email": email, "error": err} if err
            else {"role": role, "email": email}
        )

    if class_teacher and class_teacher.get("email"):
        await _one("tridni", class_teacher["email"])
    else:
        result["skipped"].append({"role": "tridni", "duvod": "třídní učitel neznámý"})

    coords = coordinator_emails()
    if not coords:
        result["skipped"].append({"role": "koordinator", "duvod": "žádná adresa koordinátora"})
    for em in coords:
        await _one("koordinator", em)
    return result


# ----------------------------------------------------------------------
# E-MAIL STUDENTOVI O ROZHODNUTÍ (povoleno / zamítnuto)
# ----------------------------------------------------------------------

def build_student_decision_email(
    *,
    student_name: str,
    approved: bool,
    day: date,
    hour_number: int | None,
    start_time=None,
    end_time=None,
    note: str | None = None,
) -> tuple[str, str]:
    e = _html.escape
    weekday = _CZ_WEEKDAYS[day.weekday()]
    date_str = f"{day.day}.{day.month}.{day.year}"
    hour = f"{hour_number}. hodina" if hour_number is not None else "hodina"
    span = ""
    if start_time and end_time:
        span = f" ({_fmt_time(start_time)}–{_fmt_time(end_time)})"
    lesson = f"{weekday} {date_str}, {hour}{span}"

    if approved:
        subject = "DuklaLabs: uvolnění z výuky – povoleno"
        verdict = ('<span style="color:#1a7f37;font-weight:700;">POVOLENO</span>')
        line = "Tvá žádost o uvolnění z výuky byla schválena."
    else:
        subject = "DuklaLabs: uvolnění z výuky – zamítnuto"
        verdict = ('<span style="color:#b42318;font-weight:700;">ZAMÍTNUTO</span>')
        line = "Tvá žádost o uvolnění z výuky byla zamítnuta."

    note_html = (
        f'<tr><td style="color:#666;font-size:13px;">Poznámka k hodině</td></tr>'
        f'<tr><td style="font-weight:600;padding-bottom:8px;">{e(note)}</td></tr>'
        if note else ""
    )
    html_body = f"""<!doctype html><html lang="cs"><body style="margin:0;
 background:#f4f5f7;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
 color:#1a1a1a;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#f4f5f7;padding:24px 12px;"><tr><td align="center">
  <table role="presentation" width="520" cellpadding="0" cellspacing="0"
         style="background:#fff;border-radius:12px;padding:24px;max-width:520px;">
    <tr><td style="font-size:18px;font-weight:700;padding-bottom:4px;">
      Rozhodnutí o uvolnění – DuklaLabs</td></tr>
    <tr><td style="color:#444;padding-bottom:12px;">Ahoj {e(student_name)},<br>
      {line}</td></tr>
    <tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="color:#666;font-size:13px;">Hodina</td></tr>
      <tr><td style="font-weight:600;padding-bottom:8px;">{e(lesson)}</td></tr>
      {note_html}
      <tr><td style="color:#666;font-size:13px;">Výsledek</td></tr>
      <tr><td style="font-size:16px;padding-bottom:8px;">{verdict}</td></tr>
    </table></td></tr>
    <tr><td style="padding-top:14px;color:#888;font-size:12px;">
      Rozhodnutí se může ještě změnit – v tom případě ti přijde nový e-mail.</td></tr>
  </table>
</td></tr></table></body></html>"""
    return subject, html_body


def _ics_esc(s: str) -> str:
    return (
        str(s or "").replace("\\", "\\\\").replace("\n", "\\n")
        .replace(",", "\\,").replace(";", "\\;")
    )


def build_release_ics(
    *, uid: str, summary: str, day: date, start_time, end_time,
    description: str = "", cancelled: bool = False,
) -> str:
    """iCalendar událost (floating local time) – student si ji přidá do
    kalendáře. cancelled=True vygeneruje zrušení stejného UID."""
    import datetime as _dt

    dtstamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    if start_time and end_time:
        ds = _dt.datetime.combine(day, start_time if isinstance(start_time, _dt.time)
                                  else _dt.time.fromisoformat(str(start_time)[:5]))
        de = _dt.datetime.combine(day, end_time if isinstance(end_time, _dt.time)
                                  else _dt.time.fromisoformat(str(end_time)[:5]))
        dtstart = "DTSTART:" + ds.strftime("%Y%m%dT%H%M%S")
        dtend = "DTEND:" + de.strftime("%Y%m%dT%H%M%S")
    else:
        dtstart = "DTSTART;VALUE=DATE:" + day.strftime("%Y%m%d")
        dtend = "DTEND;VALUE=DATE:" + (day + _dt.timedelta(days=1)).strftime("%Y%m%d")

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//DuklaLabs//uvolneni//CS",
        "CALSCALE:GREGORIAN",
        "METHOD:CANCEL" if cancelled else "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}", f"DTSTAMP:{dtstamp}", dtstart, dtend,
        f"SUMMARY:{_ics_esc(summary)}",
        f"DESCRIPTION:{_ics_esc(description)}",
        "STATUS:CANCELLED" if cancelled else "STATUS:CONFIRMED",
        f"SEQUENCE:{1 if cancelled else 0}",
        "END:VEVENT", "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


async def notify_student_decision(
    *,
    student_email: str,
    student_name: str,
    approved: bool,
    day: date,
    hour_number: int | None,
    start_time=None,
    end_time=None,
    note: str | None = None,
    booking_id: int | None = None,
) -> dict:
    """Pošle studentovi e-mail o tom, že dozor rozhodl (+ .ics do kalendáře).
    Best-effort."""
    result: dict = {"sent_to": None, "error": None}
    if not NOTIFY_ENABLED:
        result["error"] = "notifikace vypnuté (NOTIFY_ENABLED)"
        return result
    if not student_email:
        result["error"] = "student bez e-mailu"
        return result

    subject, body = build_student_decision_email(
        student_name=student_name,
        approved=approved,
        day=day,
        hour_number=hour_number,
        start_time=start_time,
        end_time=end_time,
        note=note,
    )
    payload = {"to": [student_email], "subject": subject, "body": body, "html": True}
    if booking_id is not None:
        hour = f"{hour_number}. hodina" if hour_number is not None else "hodina"
        payload.update(
            ics=build_release_ics(
                uid=f"duklalabs-booking-{booking_id}@spssecb.cz",
                summary="DuklaLabs – uvolnění z výuky",
                day=day, start_time=start_time, end_time=end_time,
                description=f"{hour}"
                + (f" · {note}" if note else "")
                + ("" if approved else " · ZAMÍTNUTO"),
                cancelled=not approved,
            ),
            ics_name="duklalabs-uvolneni.ics",
            ics_method="CANCEL" if not approved else "PUBLISH",
        )
    err = await _send_via_messenger(payload)
    if err:
        result["error"] = err
    else:
        result["sent_to"] = student_email
    return result
