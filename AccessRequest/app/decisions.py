"""Rozhodnutí dozora o uvolnění studenta z výuky.

Otevřená hodina DuklaLabs -> student se zapíše -> dozorovi přijde e-mail
s tlačítky Povolit / Zamítnout. Tlačítko odkazuje sem:

    GET  /rozhodnuti/{token}?volba=povolit|zamitnout
         -> mezistránka s detailem a jedním potvrzovacím tlačítkem
    POST /rozhodnuti/{token}   (volba=povolit|zamitnout)
         -> zapíše rozhodnutí (přepsatelné) a zobrazí potvrzení

Bez přihlášení — dozor nemá účet, kapacitou je samotný token.
"""
from __future__ import annotations

from datetime import date, time

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from ailacore.db import get_pool

router_decisions = APIRouter(tags=["Decisions"])

_CZ_WEEKDAYS = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]
_VOLBA = {"povolit": True, "zamitnout": False}

_BOOKING_SQL = """
    SELECT b.id, b.approved, b.decided_at,
           s.first_name, s.last_name, s.class_group,
           oh.date, oh.hour_number, oh.start_time, oh.end_time, oh.note
    FROM internal.bookings b
    JOIN internal.students s ON s.student_id = b.student_id
    JOIN internal.open_hours oh ON oh.id = b.open_hour_id
    WHERE b.decision_token = $1
"""


def _fmt_time(t) -> str:
    return t.strftime("%H:%M") if isinstance(t, time) else (str(t)[:5] if t else "")


def _lesson_line(row) -> str:
    d: date = row["date"]
    wd = _CZ_WEEKDAYS[d.weekday()]
    hour = f"{row['hour_number']}. hodina" if row["hour_number"] is not None else "hodina"
    span = ""
    if row["start_time"] and row["end_time"]:
        span = f" ({_fmt_time(row['start_time'])}–{_fmt_time(row['end_time'])})"
    return f"{wd} {d.day}.{d.month}.{d.year}, {hour}{span}"


def _page(title: str, inner: str, status_code: int = 200) -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{title}</title>
<style>
  body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         background:#f4f5f7; margin:0; padding:2rem 1rem; color:#1a1a1a; }}
  .card {{ max-width:520px; margin:0 auto; background:#fff; border-radius:12px;
          padding:1.75rem; box-shadow:0 1px 4px rgba(0,0,0,.12); }}
  h1 {{ font-size:1.25rem; margin:0 0 1rem; }}
  dl {{ margin:1rem 0; }} dt {{ color:#666; font-size:.85rem; }}
  dd {{ margin:0 0 .6rem; font-weight:600; }}
  .btn {{ display:inline-block; padding:.7rem 1.4rem; border-radius:8px;
         font-size:1rem; font-weight:600; text-decoration:none; border:0;
         cursor:pointer; }}
  .btn-ok {{ background:#1a7f37; color:#fff; }}
  .btn-no {{ background:#b42318; color:#fff; }}
  .btn-alt {{ background:transparent; color:#555; text-decoration:underline;
             padding:.7rem .4rem; }}
  .muted {{ color:#666; font-size:.9rem; }}
  form {{ display:inline; }}
</style></head>
<body><div class="card">{inner}</div></body></html>"""
    return HTMLResponse(html, status_code=status_code)


def _detail_dl(row) -> str:
    student = f"{row['first_name']} {row['last_name']}"
    if row["class_group"]:
        student += f" ({row['class_group']})"
    note = f"<dt>Poznámka k hodině</dt><dd>{row['note']}</dd>" if row["note"] else ""
    return (
        f"<dl><dt>Student</dt><dd>{student}</dd>"
        f"<dt>Hodina</dt><dd>{_lesson_line(row)}</dd>{note}</dl>"
    )


def _state_text(approved) -> str:
    if approved is True:
        return "Aktuální stav: <strong>uvolnění povoleno</strong>."
    if approved is False:
        return "Aktuální stav: <strong>účast zamítnuta</strong>."
    return "Zatím nerozhodnuto."


@router_decisions.get("/rozhodnuti/{token}", response_class=HTMLResponse)
async def decision_page(token: str, request: Request):
    volba = (request.query_params.get("volba") or "").lower()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_BOOKING_SQL, token)

    if row is None:
        return _page(
            "Odkaz neplatný",
            "<h1>Odkaz neplatný</h1><p class='muted'>Tento odkaz na rozhodnutí "
            "už neplatí – rezervace byla nejspíš zrušena.</p>",
            status_code=404,
        )

    if volba in _VOLBA:
        chce = "povolit uvolnění studenta z výuky" if volba == "povolit" \
            else "zamítnout účast studenta"
        other = "zamitnout" if volba == "povolit" else "povolit"
        other_label = "Chci naopak zamítnout" if volba == "povolit" \
            else "Chci naopak povolit"
        btn_cls = "btn-ok" if volba == "povolit" else "btn-no"
        return _page(
            "Potvrzení rozhodnutí",
            f"<h1>Potvrďte rozhodnutí</h1>"
            f"{_detail_dl(row)}"
            f"<p>Chystáte se <strong>{chce}</strong>.</p>"
            f"<p class='muted'>{_state_text(row['approved'])}</p>"
            f"<form method='post' action='/rozhodnuti/{token}'>"
            f"<input type='hidden' name='volba' value='{volba}'>"
            f"<button class='btn {btn_cls}' type='submit'>Potvrdit</button></form> "
            f"<a class='btn btn-alt' href='/rozhodnuti/{token}?volba={other}'>"
            f"{other_label}</a>",
        )

    # Bez volby – rozcestník s oběma tlačítky.
    return _page(
        "Rozhodnutí o uvolnění",
        f"<h1>Uvolnění z výuky – DuklaLabs</h1>"
        f"{_detail_dl(row)}"
        f"<p class='muted'>{_state_text(row['approved'])}</p>"
        f"<a class='btn btn-ok' href='/rozhodnuti/{token}?volba=povolit'>Povolit</a> "
        f"<a class='btn btn-no' href='/rozhodnuti/{token}?volba=zamitnout'>Zamítnout</a>",
    )


@router_decisions.post("/rozhodnuti/{token}", response_class=HTMLResponse)
async def decision_submit(token: str, volba: str = Form(...)):
    approved = _VOLBA.get(volba.lower())
    if approved is None:
        return _page("Neplatná volba", "<h1>Neplatná volba</h1>", status_code=400)

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE internal.bookings
            SET approved = $1, decided_at = NOW()
            WHERE decision_token = $2
            RETURNING id
            """,
            approved,
            token,
        )

    if row is None:
        return _page(
            "Odkaz neplatný",
            "<h1>Odkaz neplatný</h1><p class='muted'>Rezervace už neexistuje.</p>",
            status_code=404,
        )

    if approved:
        msg = ("<h1>Uvolnění povoleno</h1>"
               "<p>Děkujeme. Student má uvolnění z výuky pro tuto hodinu.</p>")
    else:
        msg = ("<h1>Účast zamítnuta</h1>"
               "<p>Děkujeme. Zapsali jsme, že student uvolněn <strong>není</strong>.</p>")
    return _page(
        "Rozhodnutí zapsáno",
        msg + f"<p class='muted'>Rozhodnutí lze změnit "
              f"<a href='/rozhodnuti/{token}'>zde</a>.</p>",
    )
