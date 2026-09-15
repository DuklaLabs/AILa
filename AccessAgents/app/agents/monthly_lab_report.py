"""Agent #1 – měsíční report o využívání laborky.

Trigger: plánovač 1. den v měsíci (za předchozí kalendářní měsíc) nebo ruční
`POST /run/monthly_lab_report`. Úroveň kontroly: **pouze informuje + uloží** –
nic v modulu nemění, jen zapíše řádek do `agent.reports` a pošle e-mail
koordinátorům.
"""
from __future__ import annotations

from datetime import date, timedelta

from ailacore import access_metrics as m
from ailacore import dukla
from ailacore.agents import emit_report, record_agent_run
from ailacore.db import get_pool
from ailacore.llm import decide, is_fallback

from app.mail import coordinator_emails, esc, send_mail, wrap_html

NAME = "monthly_lab_report"
MODULE = "access"


def _prev_month_range(today: date) -> tuple[date, date]:
    first_this = today.replace(day=1)
    prev_last = first_this - timedelta(days=1)
    return prev_last.replace(day=1), first_this


async def _subject_breakdown(rows: list[dict]) -> dict[str, int]:
    """Uvolněné hodiny podle předmětu (best-effort přes duklamaps)."""
    counts: dict[str, int] = {}
    cache: dict[tuple, list] = {}
    for r in rows:
        key = (r["class_group"], r["date"], r["hour_number"])
        if key not in cache:
            try:
                cache[key] = await dukla.class_teachers(
                    r["class_group"] or "", r["date"],
                    r["hour_number"] if r["hour_number"] is not None else -1,
                )
            except Exception:  # noqa: BLE001 - best effort
                cache[key] = []
        subjects = {t.get("subject") for t in cache[key] if t.get("subject")}
        for subj in (subjects or {"(neznámý předmět)"}):
            counts[subj] = counts.get(subj, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def _fallback_summary(p: dict) -> str:
    occ = p["occupancy"]
    att = p["attendance"]
    dec = p["decisions"]
    return (
        f"Za období {p['period_start']}–{p['period_end']}: "
        f"{occ.get('slots', 0)} otevřených hodin (obsazenost "
        f"{float(occ.get('fill_ratio', 0)) * 100:.0f} %, "
        f"{occ.get('empty_slots', 0)} prázdných), "
        f"{dec.get('bookings', 0)} rezervací "
        f"({dec.get('approved', 0)} povoleno / {dec.get('denied', 0)} zamítnuto / "
        f"{dec.get('undecided', 0)} nerozhodnuto), "
        f"docházka: {att.get('came', 0)} přišlo, {att.get('no_show', 0)} nepřišlo "
        f"(no-show {float(att.get('no_show_ratio', 0)) * 100:.0f} %). "
        f"Nové registrace: {p['new_registrations']}, "
        f"čekající souhlasy: {p['pending_consents']}, "
        f"selhané maily: {p['failed_mails']['count']}."
    )


async def run(*, trigger: str = "scheduler", period: date | None = None) -> dict:
    today = date.today()
    start, end = _prev_month_range(period or today)

    occupancy = await m.open_hours_occupancy(start, end)
    decisions = await m.booking_decisions(start, end)
    attendance = await m.attendance_stats(start, end)
    released = await m.released_bookings(start, end)
    subjects = await _subject_breakdown(released)
    new_regs = await m.new_registrations(start, end)
    pending = await m.pending_release_consents()
    failed = await m.failed_mails(start, end)
    flags = await m.agent_flag_counts(start, end)

    # trend proti minulému měsíci
    prev_start, _ = _prev_month_range(start)
    prev_report = None
    pool = await get_pool()
    async with pool.acquire() as conn:
        prev_report = await conn.fetchrow(
            "SELECT payload, summary FROM agent.reports "
            "WHERE module = $1 AND period = $2",
            MODULE, prev_start,
        )

    payload = {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "occupancy": {k: (float(v) if hasattr(v, "__float__") else v)
                      for k, v in occupancy.items()},
        "decisions": dict(decisions),
        "attendance": {k: (float(v) if hasattr(v, "__float__") else v)
                       for k, v in attendance.items()},
        "released_by_subject": subjects,
        "new_registrations": new_regs,
        "pending_consents": len(pending),
        "failed_mails": {"count": failed["count"]},
        "agent_flags": flags,
        "has_previous": prev_report is not None,
    }

    llm = decide(
        system=(
            "Jsi provozní analytik školní laboratoře DuklaLabs. Z předaných čísel "
            "napiš stručný český měsíční přehled (4–8 vět) a seznam 2–4 věcí, na "
            "které si dát pozor (nízká obsazenost, vysoký no-show, předměty s "
            "nejvíc uvolněními, selhané maily). Nevymýšlej data, jen interpretuj."
        ),
        user=str(payload),
        schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "watch_outs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["summary"],
        },
    )
    if is_fallback(llm):
        summary = _fallback_summary(payload)
        watch_outs: list[str] = []
    else:
        summary = llm.get("summary") or _fallback_summary(payload)
        watch_outs = [str(x) for x in (llm.get("watch_outs") or [])]

    payload["watch_outs"] = watch_outs

    async with pool.acquire() as conn:
        async with conn.transaction():
            rep = await emit_report(
                conn, module=MODULE, agent=NAME, period=start,
                payload=payload, summary=summary,
            )
            await record_agent_run(
                conn, module=MODULE, agent=NAME, trigger=trigger,
                detail={"report_id": rep["id"], "llm_fallback": is_fallback(llm)},
            )

    # e-mail koordinátorům (best-effort)
    subj_rows = "".join(
        f"<tr><td style='padding:2px 12px 2px 0;'>{esc(k)}</td>"
        f"<td style='padding:2px 0;'>{v}</td></tr>"
        for k, v in list(subjects.items())[:12]
    )
    wo = "".join(f"<li>{esc(x)}</li>" for x in watch_outs)
    inner = (
        f"<p>{esc(summary)}</p>"
        + (f"<p><strong>Na co si dát pozor:</strong></p><ul>{wo}</ul>" if wo else "")
        + (f"<p><strong>Uvolněné hodiny podle předmětu:</strong></p>"
           f"<table>{subj_rows}</table>" if subj_rows else "")
        + f"<p style='color:#888;font-size:12px;'>Report #{rep['id']} "
          f"za {start.isoformat()}–{end.isoformat()}.</p>"
    )
    mail = await send_mail(
        to=coordinator_emails(),
        subject=f"DuklaLabs: měsíční přehled využívání laborky ({start:%m/%Y})",
        body=wrap_html("Měsíční přehled – DuklaLabs", inner),
        source="access-agent-monthly-report",
    )

    return {"agent": NAME, "report_id": rep["id"], "period": start.isoformat(),
            "llm_fallback": is_fallback(llm), "mail": mail}
