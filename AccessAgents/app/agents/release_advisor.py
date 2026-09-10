"""Agent #3 – asistent rozhodování o uvolnění.

Pro nadcházející **nerozhodnuté** rezervace (`approved IS NULL`) připraví krátké
doporučení pro učitele/dozora (ne verdikt): „nízké riziko → doporučeno povolit“
× „koliduje s výukou, opakované no-show → zvážit zamítnutí“. Doporučení se uloží
jako `agent.proposals` `kind='release.advice'` `status='info'`; čtvrteční digest
(`run_teacher_digest` v access-request-server) je k rezervacím připojí.

Úroveň kontroly: **navrhuje (jen text).** Nikdy nezapisuje `internal.bookings.approved`.
"""
from __future__ import annotations

import os
from datetime import date

from ailacore import access_metrics as m
from ailacore import dukla
from ailacore.agents import emit_flag, record_agent_run
from ailacore.db import get_pool
from ailacore.llm import decide, is_fallback

NAME = "release_advisor"
MODULE = "access"

DEDUP_DAYS = int(os.getenv("RELEASE_ADVICE_DEDUP_DAYS", "6"))


def _fallback_advice(ctx: dict) -> dict:
    """Bez LLM: jednoduché pravidlo z kontextu."""
    hist = ctx["history"]
    reasons = []
    rec = "povolit"
    if ctx["collides_with_lesson"]:
        reasons.append(f"koliduje s výukou ({ctx['subject'] or 'předmět'})")
        rec = "zvazit"
    if not ctx["release_consent_ok"]:
        reasons.append("nemá schválené uvolňování (třídní + koordinátor)")
        rec = "zvazit"
    if hist.get("no_show", 0) >= 2:
        reasons.append(f"{hist['no_show']}× nepřišel po povolení")
        rec = "zvazit"
    if ctx["subject_streak"] >= 3:
        reasons.append(f"už {ctx['subject_streak']} uvolnění z tohoto předmětu")
        rec = "zvazit"
    if not reasons:
        reasons.append("volná hodina, bez rizikových signálů")
    return {"recommendation": rec, "reason": "; ".join(reasons), "confidence": 0.5}


async def run(*, trigger: str = "scheduler", today: date | None = None) -> dict:
    today = today or date.today()
    upcoming = [b for b in await m.upcoming_bookings(today) if b["approved"] is None]
    if not upcoming:
        return {"agent": NAME, "advice": 0}

    student_ids = sorted({b["student_id"] for b in upcoming})
    history = await m.student_release_history(student_ids)

    pool = await get_pool()
    made = 0
    subj_cache: dict = {}
    async with pool.acquire() as conn:
        # dedup: rezervace, které už čerstvé doporučení mají
        done = {
            int(r["target_id"]) for r in await conn.fetch(
                """
                SELECT target_id FROM agent.proposals
                WHERE module = $1 AND agent = $2 AND kind = 'release.advice'
                  AND created_at >= now() - ($3 || ' days')::interval
                """,
                MODULE, NAME, str(DEDUP_DAYS),
            )
        }
        # aktivní vlajky předmětů (agent #2) pro kontext
        subj_flags = await conn.fetch(
            """
            SELECT target_id, payload FROM agent.proposals
            WHERE module = $1 AND kind = 'student.subject_release_alert'
              AND created_at >= now() - interval '30 days'
            """,
            MODULE,
        )
        streak_by_student: dict[int, int] = {}
        for r in subj_flags:
            payload = r.get("payload") if hasattr(r, "get") else r["payload"]
            if isinstance(payload, str):
                import json as _j
                payload = _j.loads(payload)
            try:
                sid = int(r["target_id"])
            except (TypeError, ValueError):
                continue
            streak_by_student[sid] = max(streak_by_student.get(sid, 0),
                                         int((payload or {}).get("released_count", 0)))

        for b in upcoming:
            if b["id"] in done:
                continue
            key = (b["class_group"], b["date"], b["hour_number"])
            if key not in subj_cache:
                try:
                    subj_cache[key] = await dukla.class_teachers(
                        b["class_group"] or "", b["date"],
                        b["hour_number"] if b["hour_number"] is not None else -1,
                    )
                except Exception:  # noqa: BLE001
                    subj_cache[key] = []
            teachers = subj_cache[key]
            subject = next((t.get("subject") for t in teachers if t.get("subject")), "")
            hist = history.get(b["student_id"], {})
            ctx = {
                "student": f"{b['first_name']} {b['last_name']}",
                "class_group": b["class_group"],
                "date": b["date"].isoformat(),
                "hour_number": b["hour_number"],
                "collides_with_lesson": bool(teachers),
                "subject": subject,
                "release_consent_ok": (b["release_teacher_ok"] is True
                                       and b["release_coord_ok"] is True),
                "occupancy": f"{b.get('booked_count', 0)}/{b['capacity']}",
                "note": b["note"],
                "history": {"approved": hist.get("approved", 0),
                            "denied": hist.get("denied", 0),
                            "came": hist.get("came", 0),
                            "no_show": hist.get("no_show", 0)},
                "subject_streak": streak_by_student.get(b["student_id"], 0),
            }

            llm = decide(
                system=("Jsi asistent učitele. Z kontextu napiš KRÁTKÉ doporučení "
                        "(1 věta) pro učitele, jestli studenta uvolnit – ne verdikt, "
                        "jen doporučení + důvod. recommendation ∈ "
                        "{povolit, zamitnout, zvazit}."),
                user=str(ctx),
                schema={"type": "object", "properties": {
                    "recommendation": {"type": "string",
                                       "enum": ["povolit", "zamitnout", "zvazit"]},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number"}},
                    "required": ["recommendation", "reason"]},
            )
            advice = _fallback_advice(ctx) if is_fallback(llm) else {
                "recommendation": llm.get("recommendation") or "zvazit",
                "reason": llm.get("reason") or "",
                "confidence": float(llm.get("confidence") or 0.5),
            }
            summary = f"{advice['recommendation']}: {advice['reason']}"

            async with conn.transaction():
                flag = await emit_flag(
                    conn, module=MODULE, agent=NAME, kind="release.advice",
                    target_type="booking", target_id=b["id"],
                    payload={**advice, "context": ctx},
                    summary=summary, confidence=advice.get("confidence"),
                )
                await record_agent_run(
                    conn, module=MODULE, agent=NAME, trigger=trigger,
                    detail={"flag_id": flag["id"], "booking_id": b["id"],
                            "recommendation": advice["recommendation"]},
                )
            made += 1

    return {"agent": NAME, "advice": made}
