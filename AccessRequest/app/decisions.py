"""Rozhodování o uvolnění studentů z výuky.

Student se zapíše na otevřenou hodinu DuklaLabs. Rozhodnutí (povolit / zamítnout)
dělá **učitel, který studenta v tu dobu podle rozvrhu učí** – dohledaný z DB
duklamaps (`app.dukla_db.class_teachers`). Když se učitel nenajde (prázdný týden,
třída není v rozvrhu, DB nedostupná), spadne to na **dozora** otevřené hodiny.

    GET/POST /rozhodovani/{token}
        token = HMAC podpis identity (učitel nebo dozor), viz
        app.notify.decision_token / resolve_decision_token. Bez přihlášení.
        - učitel: vidí jen své studenty, u každého Povolit / Zamítnout
        - dozor: vidí všechny své otevřené hodiny po dnech, navíc přišel/nepřišel;
          smí přepsat rozhodnutí učitele

    POST /api/decisions/send-digest            (admin/staff)  -> rozhodovací maily učitelům
    POST /api/decisions/send-supervisor-roster (admin/staff)  -> přehled docházky dozorům
    GET  /api/decisions/timetable-debug        (admin/staff)  -> diagnostika rozvrhu

`internal.bookings`: `approved` (NULL=nové/TRUE/FALSE), `attended`
(NULL/TRUE=přišel/FALSE=nepřišel).
"""
from __future__ import annotations

import datetime
from datetime import date, time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ailacore.rbac import require_permission
from ailacore.db import get_pool

from app.dukla_db import class_lookup_debug, class_teachers
from app.notify import (
    configured_supervisors,
    notify_student_decision,
    resolve_decision_token,
    send_decision_digest,
    send_supervisor_roster,
    supervisor_email,
    supervisor_matches,
)

router_decisions = APIRouter(tags=["Decisions"])

_CZ_WEEKDAYS = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]
_STAVY = {"nove", "povolene", "zamitnute", "vse"}

_UPCOMING_SQL = """
    SELECT b.id, b.approved, b.attended,
           s.first_name, s.last_name, s.class_group,
           oh.date, oh.hour_number, oh.start_time, oh.end_time, oh.note,
           oh.supervisor
    FROM internal.bookings b
    JOIN internal.students s ON s.student_id = b.student_id
    JOIN internal.open_hours oh ON oh.id = b.open_hour_id
    WHERE oh.date >= CURRENT_DATE
    ORDER BY oh.date, oh.start_time, s.last_name, s.first_name
"""

_DECIDED_INFO_SQL = """
    SELECT b.id, b.approved, s.first_name, s.last_name, s.email,
           oh.date, oh.hour_number, oh.start_time, oh.end_time, oh.note
    FROM internal.bookings b
    JOIN internal.students s ON s.student_id = b.student_id
    JOIN internal.open_hours oh ON oh.id = b.open_hour_id
    WHERE b.id = ANY($1::int[])
"""


# ----------------------------------------------------------------------
# ROZVRH: kdo je pro daný zápis "rozhodovatel"
# ----------------------------------------------------------------------

async def _resolve(rows) -> tuple[dict[int, list[tuple]], dict[int, list[dict]]]:
    """Pro každý zápis vrátí:
      recipients[id] = [(kind, name, email), ...]  – komu jde rozhodnutí
      teachers[id]   = [{teacher_name, teacher_email, subject, ...}, ...]  – z rozvrhu
    Timetable lookup se cachuje dle (třída, datum, hodina)."""
    cache: dict[tuple, list[dict]] = {}
    recipients: dict[int, list[tuple]] = {}
    teachers: dict[int, list[dict]] = {}
    for r in rows:
        key = (r["class_group"], r["date"], r["hour_number"])
        if key not in cache:
            hour = r["hour_number"] if r["hour_number"] is not None else -1
            try:
                cache[key] = await class_teachers(
                    r["class_group"] or "", r["date"], hour
                )
            except Exception:  # noqa: BLE001 - best effort
                cache[key] = []
        tlist = cache[key]
        teachers[r["id"]] = tlist
        with_mail = [t for t in tlist if t.get("teacher_email")]
        if with_mail:
            recipients[r["id"]] = [
                ("teacher", t["teacher_name"], t["teacher_email"]) for t in with_mail
            ]
        else:
            recs = []
            for sup in configured_supervisors():
                if supervisor_matches(r["supervisor"], sup):
                    em = supervisor_email(sup)
                    if em:
                        recs.append(("supervisor", sup, em))
            recipients[r["id"]] = recs
    return recipients, teachers


def _teacher_candidates(recipients: dict[int, list[tuple]]) -> list[str]:
    seen, out = set(), []
    for recs in recipients.values():
        for kind, name, _email in recs:
            if kind == "teacher" and name not in seen:
                seen.add(name)
                out.append(name)
    return out


# ----------------------------------------------------------------------
# NOTIFIKACE STUDENTŮM
# ----------------------------------------------------------------------

async def _notify_students(conn, booking_ids: list[int]) -> None:
    if not booking_ids:
        return
    try:
        rows = await conn.fetch(_DECIDED_INFO_SQL, booking_ids)
    except Exception:  # noqa: BLE001
        return
    for r in rows:
        if r["approved"] is None:
            continue
        try:
            await notify_student_decision(
                student_email=r["email"],
                student_name=f"{r['first_name']} {r['last_name']}",
                approved=r["approved"],
                day=r["date"],
                hour_number=r["hour_number"],
                start_time=r["start_time"],
                end_time=r["end_time"],
                note=r["note"],
                booking_id=r["id"],
            )
        except Exception:  # noqa: BLE001
            pass


# ----------------------------------------------------------------------
# HTML pomůcky
# ----------------------------------------------------------------------

def _fmt_time(t) -> str:
    return t.strftime("%H:%M") if isinstance(t, time) else (str(t)[:5] if t else "")


def _lesson_line(row) -> str:
    d: date = row["date"]
    wd = _CZ_WEEKDAYS[d.weekday()]
    hour = f"{row['hour_number']}. h" if row["hour_number"] is not None else ""
    span = ""
    if row["start_time"] and row["end_time"]:
        span = f" {_fmt_time(row['start_time'])}–{_fmt_time(row['end_time'])}"
    return f"{wd} {d.day}.{d.month}.{d.year} {hour}{span}".strip()


def _esc(s) -> str:
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _page(title: str, inner: str, status_code: int = 200) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{title}</title>
<style>
  body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         background:#f4f5f7; margin:0; padding:2rem 1rem; color:#1a1a1a; }}
  .card {{ max-width:820px; margin:0 auto; background:#fff; border-radius:12px;
          padding:1.75rem; box-shadow:0 1px 4px rgba(0,0,0,.12); }}
  h1 {{ font-size:1.3rem; margin:0 0 .25rem; }}
  h2 {{ font-size:1rem; margin:1.4rem 0 .4rem; }}
  .sub {{ color:#666; margin:0 0 1.25rem; }}
  .tabs {{ margin:0 0 1rem; display:flex; gap:.5rem; flex-wrap:wrap; }}
  .tabs a {{ padding:.35rem .8rem; border-radius:999px; text-decoration:none;
            background:#eef0f3; color:#333; font-size:.9rem; }}
  .tabs a.active {{ background:#1a4fd6; color:#fff; }}
  table {{ width:100%; border-collapse:collapse; }}
  th, td {{ text-align:left; padding:.5rem .5rem; border-bottom:1px solid #eee;
           vertical-align:middle; font-size:.93rem; }}
  th {{ color:#666; font-weight:600; font-size:.78rem; text-transform:uppercase; }}
  .st-new {{ color:#9a6700; font-weight:600; }}
  .st-ok {{ color:#1a7f37; font-weight:600; }}
  .st-no {{ color:#b42318; font-weight:600; }}
  .choice label {{ margin-right:.55rem; white-space:nowrap; }}
  .bar {{ margin-top:1.25rem; display:flex; gap:.6rem; flex-wrap:wrap;
         align-items:center; }}
  .btn {{ display:inline-block; padding:.6rem 1.2rem; border-radius:8px;
         font-size:.95rem; font-weight:600; border:0; cursor:pointer; }}
  .btn-primary {{ background:#1a4fd6; color:#fff; }}
  .btn-ok {{ background:#1a7f37; color:#fff; }}
  .btn-no {{ background:#b42318; color:#fff; }}
  .flash {{ background:#e7f6ec; border:1px solid #bfe3cb; color:#1a7f37;
           padding:.6rem .9rem; border-radius:8px; margin-bottom:1rem; }}
  .muted {{ color:#777; font-size:.85rem; margin-top:1rem; }}
</style></head>
<body><div class="card">{inner}</div></body></html>"""
    return HTMLResponse(html, status_code=status_code)


def _decision_radio(bid: int, approved) -> str:
    def radio(val, label, checked):
        c = " checked" if checked else ""
        return f'<label><input type="radio" name="d_{bid}" value="{val}"{c}> {label}</label>'

    return (
        '<div class="choice">'
        + radio("povolit", "Povolit", approved is True)
        + radio("zamitnout", "Zamítnout", approved is False)
        + radio("", "beze změny", approved is None)
        + "</div>"
    )


def _attend_radio(bid: int, attended) -> str:
    def radio(val, label, checked):
        c = " checked" if checked else ""
        return f'<label><input type="radio" name="att_{bid}" value="{val}"{c}> {label}</label>'

    return (
        '<div class="choice">'
        + radio("prisel", "přišel", attended is True)
        + radio("neprisel", "nepřišel", attended is False)
        + radio("", "–", attended is None)
        + "</div>"
    )


def _status_html(approved) -> str:
    if approved is True:
        return '<span class="st-ok">povoleno</span>'
    if approved is False:
        return '<span class="st-no">zamítnuto</span>'
    return '<span class="st-new">nové</span>'


def _teacher_label(teachers_for_row: list[dict]) -> str:
    names = [t["teacher_name"] for t in (teachers_for_row or [])]
    return _esc(", ".join(names)) if names else "<span class='muted'>—</span>"


# ----------------------------------------------------------------------
# STRÁNKA /rozhodovani/{token}
# ----------------------------------------------------------------------

@router_decisions.get("/rozhodovani/{token}", response_class=HTMLResponse)
async def decision_list(token: str, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_UPCOMING_SQL)
    recipients, teachers = await _resolve(rows)

    ident = resolve_decision_token(token, _teacher_candidates(recipients))
    if ident is None:
        return _page(
            "Odkaz neplatný",
            "<h1>Odkaz neplatný</h1><p class='muted'>Tento rozhodovací odkaz "
            "už neplatí.</p>",
            status_code=404,
        )
    kind, name = ident

    if kind == "supervisor":
        mine = [r for r in rows if supervisor_matches(r["supervisor"], name)]
    else:
        mine = [
            r for r in rows
            if any(k == "teacher" and n == name for k, n, _e in recipients[r["id"]])
        ]

    try:
        ulozeno = int(request.query_params.get("ulozeno") or 0)
    except ValueError:
        ulozeno = 0
    flash = (
        f"<div class='flash'>Uloženo ({ulozeno} zm.).</div>" if ulozeno else ""
    )

    if kind == "supervisor":
        inner = _render_supervisor(token, name, mine, teachers)
    else:
        stav = (request.query_params.get("stav") or "nove").lower()
        if stav not in _STAVY:
            stav = "nove"
        inner = _render_teacher(token, name, mine, teachers, stav)

    return _page("Rozhodování o uvolnění", flash + inner)


def _render_teacher(token, name, mine, teachers, stav) -> str:
    n_new = sum(1 for r in mine if r["approved"] is None)
    n_ok = sum(1 for r in mine if r["approved"] is True)
    n_no = sum(1 for r in mine if r["approved"] is False)

    def keep(r):
        return (
            stav == "vse"
            or (stav == "nove" and r["approved"] is None)
            or (stav == "povolene" and r["approved"] is True)
            or (stav == "zamitnute" and r["approved"] is False)
        )

    visible = [r for r in mine if keep(r)]
    tabs = "".join(
        f'<a href="?stav={k}" class="{"active" if stav == k else ""}">{lbl}</a>'
        for k, lbl in (
            ("nove", f"Nové ({n_new})"), ("povolene", f"Povolené ({n_ok})"),
            ("zamitnute", f"Zamítnuté ({n_no})"), ("vse", f"Vše ({len(mine)})"),
        )
    )
    if visible:
        body = "".join(
            f"<tr><td>{_esc(r['first_name'])} {_esc(r['last_name'])}"
            + (f" <span class='muted'>({_esc(r['class_group'])})</span>"
               if r["class_group"] else "")
            + f"</td><td>{_esc(_lesson_line(r))}"
            + (f"<br><span class='muted'>{_esc(r['note'])}</span>" if r["note"] else "")
            + f"</td><td>{_status_html(r['approved'])}</td>"
            + f"<td>{_decision_radio(r['id'], r['approved'])}</td></tr>"
            for r in visible
        )
        table = ("<table><tr><th>Student</th><th>Hodina</th><th>Stav</th>"
                 "<th>Rozhodnutí</th></tr>" + body + "</table>")
    else:
        table = "<p class='muted'>V této kategorii nic není.</p>"

    return f"""
      <h1>Uvolnění z výuky – DuklaLabs</h1>
      <p class="sub">Učitel: <strong>{_esc(name)}</strong> – studenti, které podle
        rozvrhu učíte v době jejich zápisu na DuklaLabs.</p>
      <div class="tabs">{tabs}</div>
      <form method="post" action="/rozhodovani/{token}">
        <input type="hidden" name="stav" value="{stav}">
        {table}
        <div class="bar">
          <button class="btn btn-primary" type="submit">Uložit rozhodnutí</button>
          <button class="btn btn-ok" type="submit" name="bulk" value="povolit"
            onclick="return confirm('Povolit všechny nové ({n_new})?')">
            Povolit vše ({n_new})</button>
          <button class="btn btn-no" type="submit" name="bulk" value="zamitnout"
            onclick="return confirm('Zamítnout všechny nové ({n_new})?')">
            Zamítnout vše ({n_new})</button>
        </div>
      </form>
      <p class="muted">„Povolit vše / Zamítnout vše" platí na nové (dosud
        neposouzené) žádosti. Rozhodnutí lze kdykoli změnit i zpětně.</p>
    """


def _render_supervisor(token, name, mine, teachers) -> str:
    by_day: dict[date, list] = {}
    for r in mine:
        by_day.setdefault(r["date"], []).append(r)

    n_new = sum(1 for r in mine if r["approved"] is None)
    blocks = []
    for d in sorted(by_day):
        head = f"{_CZ_WEEKDAYS[d.weekday()]} {d.day}.{d.month}.{d.year}"
        body = "".join(
            f"<tr><td>{_esc(r['first_name'])} {_esc(r['last_name'])}"
            + (f" <span class='muted'>({_esc(r['class_group'])})</span>"
               if r["class_group"] else "")
            + f"</td><td>{r['hour_number']}. h</td>"
            + f"<td>{_teacher_label(teachers.get(r['id']))}</td>"
            + f"<td>{_status_html(r['approved'])}<br>{_decision_radio(r['id'], r['approved'])}</td>"
            + f"<td>{_attend_radio(r['id'], r['attended'])}</td></tr>"
            for r in by_day[d]
        )
        blocks.append(
            f"<h2>{_esc(head)}</h2><table><tr><th>Student</th><th>Hodina</th>"
            f"<th>Učitel</th><th>Uvolnění</th><th>Docházka</th></tr>{body}</table>"
        )
    tables = "".join(blocks) or "<p class='muted'>Žádné nadcházející zápisy.</p>"

    return f"""
      <h1>Docházka DuklaLabs – dozor</h1>
      <p class="sub">Dozor: <strong>{_esc(name)}</strong>. Studenti přihlášení na
        vaše otevřené hodiny. Můžete odklikat docházku i přepsat rozhodnutí učitele.</p>
      <form method="post" action="/rozhodovani/{token}">
        {tables}
        <div class="bar">
          <button class="btn btn-primary" type="submit">Uložit</button>
          <button class="btn btn-ok" type="submit" name="bulk" value="povolit"
            onclick="return confirm('Povolit všechny nové ({n_new})?')">
            Povolit vše ({n_new})</button>
          <button class="btn btn-no" type="submit" name="bulk" value="zamitnout"
            onclick="return confirm('Zamítnout všechny nové ({n_new})?')">
            Zamítnout vše ({n_new})</button>
        </div>
      </form>
    """


@router_decisions.post("/rozhodovani/{token}")
async def decision_list_submit(token: str, request: Request):
    form = await request.form()
    stav = (form.get("stav") or "nove").lower()
    if stav not in _STAVY:
        stav = "nove"
    bulk = (form.get("bulk") or "").lower()

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_UPCOMING_SQL)
        recipients, _teachers = await _resolve(rows)
        ident = resolve_decision_token(token, _teacher_candidates(recipients))
        if ident is None:
            return _page("Odkaz neplatný", "<h1>Odkaz neplatný</h1>", status_code=404)
        kind, name = ident

        if kind == "supervisor":
            owned = {
                r["id"]: r["approved"] for r in rows
                if supervisor_matches(r["supervisor"], name)
            }
        else:
            owned = {
                r["id"]: r["approved"] for r in rows
                if any(k == "teacher" and n == name for k, n, _e in recipients[r["id"]])
            }

        povolit, zamitnout = [], []
        att_yes, att_no = [], []
        if bulk in ("povolit", "zamitnout"):
            target = [bid for bid, ap in owned.items() if ap is None]
            (povolit if bulk == "povolit" else zamitnout).extend(target)
        else:
            for key, val in form.multi_items():
                if key.startswith("d_"):
                    try:
                        bid = int(key[2:])
                    except ValueError:
                        continue
                    if bid in owned and val in ("povolit", "zamitnout"):
                        (povolit if val == "povolit" else zamitnout).append(bid)
                elif key.startswith("att_") and kind == "supervisor":
                    try:
                        bid = int(key[4:])
                    except ValueError:
                        continue
                    if bid in owned and val in ("prisel", "neprisel"):
                        (att_yes if val == "prisel" else att_no).append(bid)

        changed = 0
        async with conn.transaction():
            if povolit:
                await conn.execute(
                    "UPDATE internal.bookings SET approved=TRUE, decided_at=NOW() "
                    "WHERE id = ANY($1::int[])", povolit)
                changed += len(povolit)
            if zamitnout:
                await conn.execute(
                    "UPDATE internal.bookings SET approved=FALSE, decided_at=NOW() "
                    "WHERE id = ANY($1::int[])", zamitnout)
                changed += len(zamitnout)
            if att_yes:
                await conn.execute(
                    "UPDATE internal.bookings SET attended=TRUE, attended_at=NOW() "
                    "WHERE id = ANY($1::int[])", att_yes)
                changed += len(att_yes)
            if att_no:
                await conn.execute(
                    "UPDATE internal.bookings SET attended=FALSE, attended_at=NOW() "
                    "WHERE id = ANY($1::int[])", att_no)
                changed += len(att_no)

        await _notify_students(conn, povolit + zamitnout)

    q = (f"?stav={stav}&ulozeno={changed}" if kind == "teacher"
         else f"?ulozeno={changed}")
    return RedirectResponse(url=f"/rozhodovani/{token}{q}", status_code=303)


# ----------------------------------------------------------------------
# ROZESLÁNÍ (admin/staff)
# ----------------------------------------------------------------------

def _item(r) -> dict:
    return {
        "id": r["id"],
        "first_name": r["first_name"], "last_name": r["last_name"],
        "class_group": r["class_group"], "day": r["date"],
        "hour_number": r["hour_number"], "start_time": r["start_time"],
        "end_time": r["end_time"], "note": r["note"], "approved": r["approved"],
    }


async def _load_release_advice(conn, booking_ids: list[int]) -> dict[int, dict]:
    """Doporučení agenta release_advisor k daným rezervacím
    (`agent.proposals` kind='release.advice'). Best-effort – když schéma
    `agent` ještě neexistuje, vrátí prázdno."""
    if not booking_ids:
        return {}
    try:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (target_id)
                   target_id, summary, confidence, payload
            FROM agent.proposals
            WHERE module = 'access' AND kind = 'release.advice'
              AND target_id = ANY($1::text[])
            ORDER BY target_id, created_at DESC
            """,
            [str(b) for b in booking_ids],
        )
    except Exception:  # noqa: BLE001 - agentní vrstva je volitelná
        return {}
    out: dict[int, dict] = {}
    for r in rows:
        payload = r["payload"]
        if isinstance(payload, str):
            import json as _json
            payload = _json.loads(payload)
        try:
            out[int(r["target_id"])] = {
                "recommendation": (payload or {}).get("recommendation"),
                "reason": (payload or {}).get("reason") or r["summary"],
                "confidence": r["confidence"],
            }
        except (TypeError, ValueError):
            continue
    return out


async def run_teacher_digest(send_all: bool = False) -> dict:
    """Rozhodovací digest běžným učitelům (fallback dozorům). Volá ji
    HTTP endpoint i plánovač (čtvrtek 13:00)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_UPCOMING_SQL)
        advice = await _load_release_advice(conn, [r["id"] for r in rows])
    recipients, _teachers = await _resolve(rows)
    by_id = {r["id"]: r for r in rows}

    groups: dict[tuple, list] = {}
    for bid, recs in recipients.items():
        for kind, name, email in recs:
            groups.setdefault((kind, name, email), []).append(by_id[bid])

    sent, skipped, errors = [], [], []
    for (kind, name, email), grp in sorted(groups.items()):
        has_new = any(r["approved"] is None for r in grp)
        if not has_new and not send_all:
            skipped.append({"kind": kind, "name": name, "duvod": "žádné nové"})
            continue
        res = await send_decision_digest(
            kind, name, email, [_item(r) for r in grp], advice=advice
        )
        if res.get("error"):
            errors.append(res)
        else:
            sent.append({"kind": kind, "name": name, "email": res["sent_to"],
                         "polozek": len(grp)})
    return {"sent": sent, "skipped": skipped, "errors": errors}


async def run_supervisor_roster(
    only_day: date | None = None, approved_only: bool = False
) -> dict:
    """Přehled docházky dozorům. `only_day` omezí na jeden den, `approved_only`
    jen na uvolněné studenty (denní kontrola v 7:00)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_UPCOMING_SQL)
    _recipients, teachers = await _resolve(rows)

    def _want(r):
        if only_day is not None and r["date"] != only_day:
            return False
        if approved_only and r["approved"] is not True:
            return False
        return True

    sent, skipped, errors = [], [], []
    for name in configured_supervisors():
        mine = [r for r in rows if supervisor_matches(r["supervisor"], name) and _want(r)]
        if not mine:
            skipped.append({"supervisor": name, "duvod": "nic k odeslání"})
            continue
        by_day: dict[date, list] = {}
        for r in mine:
            tnames = ", ".join(
                t["teacher_name"] for t in (teachers.get(r["id"]) or [])
            )
            by_day.setdefault(r["date"], []).append({
                "student_name": f"{r['first_name']} {r['last_name']}",
                "class_group": r["class_group"],
                "hour_number": r["hour_number"],
                "subject": ", ".join(
                    t.get("subject", "") for t in (teachers.get(r["id"]) or []) if t.get("subject")
                ),
                "teacher_name": tnames,
                "approved": r["approved"],
                "attended": r["attended"],
            })
        ordered = [(d, by_day[d]) for d in sorted(by_day)]
        res = await send_supervisor_roster(name, ordered)
        if res.get("error"):
            errors.append(res)
        else:
            sent.append({"supervisor": name, "email": res["sent_to"],
                         "dnu": len(ordered)})
    return {"sent": sent, "skipped": skipped, "errors": errors}


@router_decisions.post(
    "/api/decisions/send-digest",
    dependencies=[Depends(require_permission("internal.release:manage"))],
)
async def send_digests(request: Request):
    """Rozhodovací digest učitelům. `?all=1` i těm, co mají jen rozhodnuté."""
    send_all = (request.query_params.get("all") or "").lower() in {"1", "true", "yes"}
    return await run_teacher_digest(send_all=send_all)


@router_decisions.post(
    "/api/decisions/send-supervisor-roster",
    dependencies=[Depends(require_permission("internal.release:manage"))],
)
async def send_supervisor_rosters(request: Request):
    """Přehled docházky dozorům. `?day=YYYY-MM-DD` omezí na den,
    `?approved_only=1` jen uvolněné."""
    q = request.query_params
    only_day = None
    if q.get("day"):
        try:
            only_day = datetime.date.fromisoformat(q["day"])
        except ValueError:
            only_day = None
    approved_only = (q.get("approved_only") or "").lower() in {"1", "true", "yes"}
    return await run_supervisor_roster(only_day=only_day, approved_only=approved_only)


@router_decisions.get(
    "/api/decisions/scheduler",
    dependencies=[Depends(require_permission("internal.release:manage"))],
)
async def scheduler_status():
    """Naplánované úlohy + čas příštího spuštění."""
    from app.scheduler import get_jobs
    return {"jobs": get_jobs()}


@router_decisions.post(
    "/api/decisions/run-teacher-digest",
    dependencies=[Depends(require_permission("internal.release:manage"))],
)
async def run_teacher_digest_now():
    """Ruční spuštění naplánované úlohy (test)."""
    return await run_teacher_digest()


@router_decisions.post(
    "/api/decisions/run-supervisor-roster",
    dependencies=[Depends(require_permission("internal.release:manage"))],
)
async def run_supervisor_roster_now(request: Request):
    only_day = datetime.date.today()
    if (request.query_params.get("all_days") or "").lower() in {"1", "true", "yes"}:
        only_day = None
    return await run_supervisor_roster(only_day=only_day, approved_only=True)


@router_decisions.get(
    "/api/decisions/timetable-debug",
    dependencies=[Depends(require_permission("internal.release:manage"))],
)
async def timetable_debug(request: Request):
    """?class=4.ER&date=2026-09-14&hour=2 → co rozvrh vrátí pro daný zápis."""
    q = request.query_params
    cls = q.get("class") or ""
    hour = int(q.get("hour") or 0)
    try:
        day = datetime.date.fromisoformat(q.get("date") or "")
    except ValueError:
        day = datetime.date.today()
    return await class_lookup_debug(cls, day, hour)


# ----------------------------------------------------------------------
# JEDNORÁZOVÝ ODKAZ NA JEDNU REZERVACI (per-booking decision_token)
# – jen když je zapnutý okamžitý e-mail (NOTIFY_ON_BOOKING).
# ----------------------------------------------------------------------

_ONE_SQL = """
    SELECT b.id, b.approved, s.first_name, s.last_name, s.class_group,
           oh.date, oh.hour_number, oh.start_time, oh.end_time, oh.note
    FROM internal.bookings b
    JOIN internal.students s ON s.student_id = b.student_id
    JOIN internal.open_hours oh ON oh.id = b.open_hour_id
    WHERE b.decision_token = $1
"""
_VOLBA = {"povolit": True, "zamitnout": False}


def _one_detail(row) -> str:
    student = f"{_esc(row['first_name'])} {_esc(row['last_name'])}"
    if row["class_group"]:
        student += f" ({_esc(row['class_group'])})"
    note = (f"<p class='muted'>Poznámka: {_esc(row['note'])}</p>"
            if row["note"] else "")
    return (
        f"<p><strong>{student}</strong><br>{_esc(_lesson_line(row))}</p>{note}"
        f"<p class='muted'>Stav: {_status_html(row['approved'])}</p>"
    )


@router_decisions.get("/rozhodnuti/{token}", response_class=HTMLResponse)
async def decision_one(token: str, request: Request):
    volba = (request.query_params.get("volba") or "").lower()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_ONE_SQL, token)
    if row is None:
        return _page("Odkaz neplatný", "<h1>Odkaz neplatný</h1>", status_code=404)
    if volba in _VOLBA:
        chce = ("povolit uvolnění studenta z výuky" if volba == "povolit"
                else "zamítnout účast studenta")
        cls = "btn-ok" if volba == "povolit" else "btn-no"
        return _page(
            "Potvrzení",
            f"<h1>Potvrďte rozhodnutí</h1>{_one_detail(row)}"
            f"<p>Chystáte se <strong>{chce}</strong>.</p>"
            f"<form method='post' action='/rozhodnuti/{token}'>"
            f"<input type='hidden' name='volba' value='{volba}'>"
            f"<button class='btn {cls}' type='submit'>Potvrdit</button></form>",
        )
    return _page(
        "Rozhodnutí",
        f"<h1>Uvolnění z výuky – DuklaLabs</h1>{_one_detail(row)}"
        f"<p><a class='btn btn-ok' href='?volba=povolit'>Povolit</a> "
        f"<a class='btn btn-no' href='?volba=zamitnout'>Zamítnout</a></p>",
    )


@router_decisions.post("/rozhodnuti/{token}")
async def decision_one_submit(token: str, request: Request):
    form = await request.form()
    approved = _VOLBA.get((form.get("volba") or "").lower())
    if approved is None:
        return _page("Neplatná volba", "<h1>Neplatná volba</h1>", status_code=400)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE internal.bookings SET approved = $1, decided_at = NOW() "
            "WHERE decision_token = $2 RETURNING id",
            approved, token,
        )
        if row is not None:
            await _notify_students(conn, [row["id"]])
    if row is None:
        return _page("Odkaz neplatný", "<h1>Odkaz neplatný</h1>", status_code=404)
    msg = ("<h1>Uvolnění povoleno</h1>" if approved else "<h1>Účast zamítnuta</h1>")
    return _page(
        "Rozhodnutí zapsáno",
        msg + f"<p class='muted'>Změnit lze <a href='/rozhodnuti/{token}'>zde</a>.</p>",
    )
