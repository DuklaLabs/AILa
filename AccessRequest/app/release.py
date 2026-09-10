"""Souhlas s uvolňováním studenta z výuky pro DuklaLabs.

Při registraci se e-mailem zeptáme třídního učitele i koordinátora
(app.notify.send_release_requests). Odkaz vede sem:

    GET  /uvolneni/{token}?role=tridni|koordinator&volba=ano|ne
         -> mezistránka s potvrzením
    POST /uvolneni/{token}   (role, volba)
         -> zapíše souhlas (release_teacher_ok / release_coord_ok); přepsatelné

    GET  /api/students/release-pending           (admin/staff)
    POST /api/students/{student_id}/release-coord (admin/staff)  body {ok: bool}

Dokud NENÍ `release_teacher_ok AND release_coord_ok`, booking blokuje zápisy
na hodiny, kdy má student podle rozvrhu vlastní výuku (viz app.bookings).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ailacore.rbac import require_permission
from ailacore.db import get_pool

router_release = APIRouter(tags=["Release"])

_ROLE_COL = {"tridni": "release_teacher_ok", "koordinator": "release_coord_ok"}
_VOLBA = {"ano": True, "ne": False}

_STUDENT_SQL = """
    SELECT student_id, first_name, last_name, class_group,
           release_teacher_ok, release_coord_ok, release_class_teacher
    FROM internal.students WHERE release_token = $1
"""


def _esc(s) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _page(title: str, inner: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>{title}</title>
<style>
 body{{font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
   background:#f4f5f7;margin:0;padding:2rem 1rem;color:#1a1a1a;}}
 .card{{max-width:520px;margin:0 auto;background:#fff;border-radius:12px;
   padding:1.75rem;box-shadow:0 1px 4px rgba(0,0,0,.12);}}
 h1{{font-size:1.25rem;margin:0 0 1rem;}}
 .btn{{display:inline-block;padding:.7rem 1.3rem;border-radius:8px;font-weight:600;
   text-decoration:none;border:0;cursor:pointer;font-size:1rem;}}
 .ok{{background:#1a7f37;color:#fff;}} .no{{background:#b42318;color:#fff;}}
 .muted{{color:#777;font-size:.9rem;}} form{{display:inline;}}
 dl{{margin:1rem 0;}} dt{{color:#666;font-size:.85rem;}} dd{{margin:0 0 .5rem;font-weight:600;}}
</style></head><body><div class="card">{inner}</div></body></html>""",
        status_code=status_code,
    )


def _state(v) -> str:
    return ("souhlas" if v is True else "nesouhlas" if v is False else "zatím nevyjádřeno")


def _status_dl(row) -> str:
    return (
        f"<dl><dt>Student</dt><dd>{_esc(row['first_name'])} {_esc(row['last_name'])}"
        + (f" ({_esc(row['class_group'])})" if row["class_group"] else "")
        + "</dd>"
        + (f"<dt>Třídní učitel</dt><dd>{_esc(row['release_class_teacher'])}</dd>"
           if row["release_class_teacher"] else "")
        + f"<dt>Třídní učitel</dt><dd>{_state(row['release_teacher_ok'])}</dd>"
        + f"<dt>Koordinátor</dt><dd>{_state(row['release_coord_ok'])}</dd></dl>"
    )


@router_release.get("/uvolneni/{token}", response_class=HTMLResponse)
async def release_page(token: str, request: Request):
    role = (request.query_params.get("role") or "").lower()
    volba = (request.query_params.get("volba") or "").lower()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_STUDENT_SQL, token)
    if row is None:
        return _page("Odkaz neplatný", "<h1>Odkaz neplatný</h1>"
                     "<p class='muted'>Tento odkaz už neplatí.</p>", 404)

    if role in _ROLE_COL and volba in _VOLBA:
        jako = "třídní učitel" if role == "tridni" else "koordinátor"
        akce = "souhlasíte s uvolňováním" if volba == "ano" else "nesouhlasíte s uvolňováním"
        cls = "ok" if volba == "ano" else "no"
        return _page(
            "Potvrzení",
            f"<h1>Potvrďte rozhodnutí</h1>{_status_dl(row)}"
            f"<p>Jako <strong>{jako}</strong> {akce} studenta z výuky.</p>"
            f"<form method='post' action='/uvolneni/{token}'>"
            f"<input type='hidden' name='role' value='{role}'>"
            f"<input type='hidden' name='volba' value='{volba}'>"
            f"<button class='btn {cls}' type='submit'>Potvrdit</button></form>",
        )

    # bez parametrů – rozcestník obě role
    def pair(r):
        jako = "Třídní učitel" if r == "tridni" else "Koordinátor"
        return (
            f"<p><strong>{jako}:</strong> "
            f"<a class='btn ok' href='?role={r}&volba=ano'>Souhlasím</a> "
            f"<a class='btn no' href='?role={r}&volba=ne'>Nesouhlasím</a></p>"
        )

    return _page(
        "Uvolňování z výuky",
        f"<h1>Uvolňování z výuky – DuklaLabs</h1>{_status_dl(row)}"
        + pair("tridni") + pair("koordinator"),
    )


@router_release.post("/uvolneni/{token}")
async def release_submit(token: str, request: Request):
    form = await request.form()
    role = (form.get("role") or "").lower()
    ok = _VOLBA.get((form.get("volba") or "").lower())
    col = _ROLE_COL.get(role)
    if col is None or ok is None:
        return _page("Neplatná volba", "<h1>Neplatná volba</h1>", 400)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE internal.students SET {col} = $1 WHERE release_token = $2 "
            "RETURNING student_id, first_name, last_name, class_group, "
            "release_teacher_ok, release_coord_ok, release_class_teacher",
            ok, token,
        )
    if row is None:
        return _page("Odkaz neplatný", "<h1>Odkaz neplatný</h1>", 404)
    both = row["release_teacher_ok"] is True and row["release_coord_ok"] is True
    verdict = ("<p><strong>Student se teď smí uvolňovat z výuky</strong> "
               "(souhlas třídního i koordinátora).</p>" if both
               else "<p class='muted'>Uvolňování je stále blokované – chybí druhý souhlas "
                    "nebo padlo „nesouhlasím“.</p>")
    return _page(
        "Zapsáno",
        f"<h1>Rozhodnutí zapsáno</h1>{_status_dl(row)}{verdict}"
        f"<p class='muted'>Změnit lze <a href='/uvolneni/{token}'>zde</a>.</p>",
    )


@router_release.get(
    "/api/students/release-pending",
    dependencies=[Depends(require_permission("internal.release:manage"))],
)
async def release_pending():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.student_id, s.first_name, s.last_name, s.class_group,
                   s.release_teacher_ok, s.release_coord_ok, s.release_class_teacher,
                   s.release_token
            FROM internal.students s
            JOIN auth.users u ON u.id = s.user_id
            WHERE u.role = 'student'
              AND NOT (s.release_teacher_ok IS TRUE AND s.release_coord_ok IS TRUE)
            ORDER BY s.student_id DESC
            """
        )
    return [dict(r) for r in rows]


@router_release.post(
    "/api/students/{student_id}/release-coord",
    dependencies=[Depends(require_permission("internal.release:manage"))],
)
async def release_coord(student_id: int, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        pass
    ok = bool(body.get("ok", True))
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE internal.students SET release_coord_ok = $1 WHERE student_id = $2",
            ok, student_id,
        )
    if res == "UPDATE 0":
        return {"status": "error", "detail": "Student nenalezen."}
    return {"status": "ok", "release_coord_ok": ok}
