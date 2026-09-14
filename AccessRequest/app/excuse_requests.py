"""Public, token-authenticated confirmation flow for the excuse-request
approval workflow, plus a small staff API for missing-teacher tickets.

These routes deliberately do NOT use `get_current_user` — the teacher
clicking a link from an email isn't a logged-in `auth.users` row at all;
the token itself is the credential (same trust model as a password-reset
link). Every mutating action is a POST reached only via a GET landing page,
so an email client's link-prefetch bot (which only ever issues GET) can
never approve/deny anything by accident.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from ailacore.auth import require_role
from ailacore.db import get_pool
from ailacore.models import User

from app.mailer import render_email, send_email
from app.missing_teacher_tickets import list_missing_teacher_tickets, resolve_missing_teacher_ticket

router = APIRouter(prefix="/excuse-requests", tags=["Excuse Requests"])
staff_router = APIRouter(prefix="/api/excuse-requests", tags=["Excuse Requests (staff)"])
_STAFF_ONLY = [Depends(require_role("admin", "staff"))]

templates = Jinja2Templates(directory="app/templates")
log = logging.getLogger(__name__)


_REQUEST_COLUMNS = """
    er.id, er.student_id, er.lesson_id, er.booking_id, er.status,
    s.email AS student_email, s.first_name, s.last_name, s.class_group,
    lh.subject_name, lh.date, lh.hour_number
"""


async def _load_request_by_token(conn, token: str):
    return await conn.fetchrow(
        f"""
        SELECT {_REQUEST_COLUMNS}
        FROM internal.excuse_requests er
        JOIN internal.students s ON s.student_id = er.student_id
        JOIN internal.lesson_hours lh ON lh.lesson_id = er.lesson_id
        WHERE er.token = $1
        """,
        token,
    )


async def _decide_excuse_request(conn, excuse_request_id: int, approve: bool, via: str) -> tuple[str, Optional[dict]]:
    """Idempotent: a double-click or a stray repeat POST on an
    already-decided request is a harmless no-op, not a duplicate email or a
    500. Returns (outcome, info) where outcome is 'decided' or
    'already_decided'; info carries what the caller needs to send the
    student notification (None when already_decided, since that email
    already went out the first time)."""
    row = await conn.fetchrow(
        f"""
        SELECT {_REQUEST_COLUMNS}
        FROM internal.excuse_requests er
        JOIN internal.students s ON s.student_id = er.student_id
        JOIN internal.lesson_hours lh ON lh.lesson_id = er.lesson_id
        WHERE er.id = $1
        FOR UPDATE OF er
        """,
        excuse_request_id,
    )
    if row is None or row["status"] != "pending":
        return "already_decided", None

    if approve:
        await conn.execute(
            "INSERT INTO internal.excused (student_id, lesson_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            row["student_id"],
            row["lesson_id"],
        )
    else:
        await conn.execute(
            "UPDATE internal.bookings SET cancelled_at = NOW(), cancelled_reason = 'excuse_denied' WHERE id = $1",
            row["booking_id"],
        )

    await conn.execute(
        "UPDATE internal.excuse_requests SET status = $2, decided_at = NOW(), decided_via = $3 WHERE id = $1",
        excuse_request_id,
        "approved" if approve else "denied",
        via,
    )
    return "decided", dict(row)


async def _notify_student(approve: bool, info: dict) -> None:
    template = "student_approved.html" if approve else "student_denied.html"
    subject = "Omluvenka schválena – DuklaLabs" if approve else "Omluvenka zamítnuta – DuklaLabs"
    html = render_email(
        template,
        subject_name=info["subject_name"],
        date=info["date"],
        hour_number=info["hour_number"],
    )
    try:
        await send_email(info["student_email"], subject, html)
    except Exception:
        log.exception("Failed to send student decision email to %s", info["student_email"])


# ----------------------------------------------------------------------
# Individual request confirm
# ----------------------------------------------------------------------

@router.get("/{token}", response_class=HTMLResponse)
async def confirm_page(token: str, request: Request):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await _load_request_by_token(conn, token)
    if row is None:
        raise HTTPException(status_code=404, detail="Žádost nenalezena.")
    return templates.TemplateResponse(
        request, "excuse_confirm.html", {"token": token, "request_info": dict(row)}
    )


@router.post("/{token}/approve", response_class=HTMLResponse)
async def approve_request(token: str, request: Request):
    return await _handle_decision(token, request, approve=True)


@router.post("/{token}/deny", response_class=HTMLResponse)
async def deny_request(token: str, request: Request):
    return await _handle_decision(token, request, approve=False)


async def _handle_decision(token: str, request: Request, approve: bool) -> HTMLResponse:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await _load_request_by_token(conn, token)
        if row is None:
            raise HTTPException(status_code=404, detail="Žádost nenalezena.")
        async with conn.transaction():
            outcome, info = await _decide_excuse_request(conn, row["id"], approve, via="individual")

    if outcome == "decided":
        await _notify_student(approve, info)
        message = "Žádost byla uvolněna, student dostal potvrzení." if approve else "Žádost byla zamítnuta, rezervace studenta byla zrušena."
    else:
        message = "Tahle žádost už byla dřív vyřízená, nic se nezměnilo."

    return templates.TemplateResponse(request, "excuse_confirm_done.html", {"message": message})


# ----------------------------------------------------------------------
# Batch (weekly digest) confirm
# ----------------------------------------------------------------------

@router.get("/batch/{batch_token}", response_class=HTMLResponse)
async def confirm_batch_page(batch_token: str, request: Request, action: str = "approve"):
    if action not in ("approve", "deny"):
        raise HTTPException(status_code=400, detail="Neplatná akce.")
    pool = await get_pool()
    async with pool.acquire() as conn:
        batch = await conn.fetchrow(
            "SELECT id FROM internal.excuse_digest_batches WHERE token = $1", batch_token
        )
        if batch is None:
            raise HTTPException(status_code=404, detail="Souhrn nenalezen.")
        items = await conn.fetch(
            f"""
            SELECT {_REQUEST_COLUMNS}
            FROM internal.excuse_digest_batch_items bi
            JOIN internal.excuse_requests er ON er.id = bi.excuse_request_id
            JOIN internal.students s ON s.student_id = er.student_id
            JOIN internal.lesson_hours lh ON lh.lesson_id = er.lesson_id
            WHERE bi.batch_id = $1 AND er.status = 'pending'
            ORDER BY lh.date, lh.hour_number
            """,
            batch["id"],
        )
    return templates.TemplateResponse(
        request,
        "excuse_confirm_batch.html",
        {"batch_token": batch_token, "action": action, "items": [dict(i) for i in items]},
    )


@router.post("/batch/{batch_token}/approve-all", response_class=HTMLResponse)
async def approve_all(batch_token: str, request: Request):
    return await _handle_batch_decision(batch_token, request, approve=True)


@router.post("/batch/{batch_token}/deny-all", response_class=HTMLResponse)
async def deny_all(batch_token: str, request: Request):
    return await _handle_batch_decision(batch_token, request, approve=False)


async def _handle_batch_decision(batch_token: str, request: Request, approve: bool) -> HTMLResponse:
    pool = await get_pool()
    async with pool.acquire() as conn:
        batch = await conn.fetchrow(
            "SELECT id FROM internal.excuse_digest_batches WHERE token = $1", batch_token
        )
        if batch is None:
            raise HTTPException(status_code=404, detail="Souhrn nenalezen.")
        item_ids = await conn.fetch(
            """
            SELECT er.id FROM internal.excuse_digest_batch_items bi
            JOIN internal.excuse_requests er ON er.id = bi.excuse_request_id
            WHERE bi.batch_id = $1 AND er.status = 'pending'
            """,
            batch["id"],
        )
        decided_infos = []
        for row in item_ids:
            async with conn.transaction():
                outcome, info = await _decide_excuse_request(conn, row["id"], approve, via="bulk")
            if outcome == "decided":
                decided_infos.append(info)

    for info in decided_infos:
        await _notify_student(approve, info)

    count = len(decided_infos)
    if count == 0:
        message = "Všechny žádosti z tohoto e-mailu už byly vyřízené, nic se nezměnilo."
    elif approve:
        message = f"Uvolněno {count} žádostí, studenti dostali potvrzení."
    else:
        message = f"Zamítnuto {count} žádostí, rezervace studentů byly zrušené."

    return templates.TemplateResponse(request, "excuse_confirm_done.html", {"message": message})


# ----------------------------------------------------------------------
# Staff: missing-teacher-email tickets
# ----------------------------------------------------------------------

@staff_router.get("/missing-teacher-tickets", dependencies=_STAFF_ONLY)
async def api_list_missing_teacher_tickets(include_resolved: bool = False):
    return await list_missing_teacher_tickets(include_resolved=include_resolved)


@staff_router.post("/missing-teacher-tickets/{ticket_id}/resolve", dependencies=_STAFF_ONLY)
async def api_resolve_missing_teacher_ticket(ticket_id: int, user: User = Depends(require_role("admin", "staff"))):
    resolved = await resolve_missing_teacher_ticket(ticket_id, resolved_by=user.id)
    if not resolved:
        raise HTTPException(status_code=404, detail="Tiket nenalezen.")
    return {"status": "ok", "msg": "Tiket vyřešen."}
