"""Agent #2 – hlídač uvolněných hodin podle předmětu.

Sleduje, z kolika hodin jednotlivého předmětu už byl student uvolněn. Když
součet dosáhne prahu `SUBJECT_RELEASE_STREAK` (default 3) a student si zapisuje
další rezervaci kolidující se stejným předmětem, agent **upozorní koordinátora
a založí vlajku** (`agent.proposals` `status='info'`). Nic neblokuje ani nemění –
rozhodnutí (povolit / zamítnout to další uvolnění) dělá koordinátor ručně přes
`/rozhodovani/{token}` nebo `POST /api/students/{id}/release-coord`.

Úroveň kontroly: **pouze informuje + označí.**
"""
from __future__ import annotations

import os
from datetime import date, timedelta

from ailacore import access_metrics as m
from ailacore import dukla
from ailacore.agents import emit_flag, record_agent_run
from ailacore.db import get_pool
from ailacore.llm import decide, is_fallback

from app.mail import coordinator_emails, esc, send_mail, wrap_html

NAME = "subject_release_watch"
MODULE = "access"

LOOKBACK_DAYS = int(os.getenv("SUBJECT_RELEASE_LOOKBACK_DAYS", "90"))
DEDUP_DAYS = int(os.getenv("SUBJECT_RELEASE_DEDUP_DAYS", "7"))


def _threshold() -> int:
    try:
        return max(1, int(os.getenv("SUBJECT_RELEASE_STREAK", "3")))
    except ValueError:
        return 3


async def _subjects_for(cache: dict, class_group: str | None, day, hour) -> set[str]:
    key = (class_group, day, hour)
    if key not in cache:
        try:
            cache[key] = await dukla.class_teachers(
                class_group or "", day, hour if hour is not None else -1
            )
        except Exception:  # noqa: BLE001 - best effort
            cache[key] = []
    return {t.get("subject") for t in cache[key] if t.get("subject")}


async def run(*, trigger: str = "scheduler", today: date | None = None) -> dict:
    today = today or date.today()
    threshold = _threshold()
    cache: dict = {}

    # 1) minulá uvolnění → součet uvolněných hodin per student+předmět
    past = await m.released_bookings(today - timedelta(days=LOOKBACK_DAYS), today)
    tally: dict[tuple, int] = {}
    names: dict[int, tuple] = {}
    for r in past:
        names[r["student_id"]] = (r["first_name"], r["last_name"], r["class_group"])
        for subj in await _subjects_for(cache, r["class_group"], r["date"], r["hour_number"]):
            tally[(r["student_id"], subj)] = tally.get((r["student_id"], subj), 0) + 1

    # 2) nadcházející nerozhodnuté rezervace kolidující se stejným předmětem
    upcoming = await m.upcoming_bookings(today)
    hits: dict[tuple, dict] = {}
    for r in upcoming:
        if r["approved"] is not None:
            continue
        for subj in await _subjects_for(cache, r["class_group"], r["date"], r["hour_number"]):
            count = tally.get((r["student_id"], subj), 0)
            if count < threshold:
                continue
            k = (r["student_id"], subj)
            names.setdefault(r["student_id"],
                             (r["first_name"], r["last_name"], r["class_group"]))
            h = hits.setdefault(k, {
                "student_id": r["student_id"], "subject": subj,
                "released_count": count, "threshold": threshold,
                "pending": [],
            })
            h["pending"].append({"booking_id": r["id"], "date": r["date"].isoformat(),
                                 "hour_number": r["hour_number"]})

    if not hits:
        return {"agent": NAME, "alerts": 0}

    # 3) dedup proti čerstvým vlajkám + zápis
    pool = await get_pool()
    created = []
    async with pool.acquire() as conn:
        recent = await conn.fetch(
            """
            SELECT target_id, payload FROM agent.proposals
            WHERE module = $1 AND agent = $2
              AND kind = 'student.subject_release_alert'
              AND created_at >= now() - ($3 || ' days')::interval
            """,
            MODULE, NAME, str(DEDUP_DAYS),
        )
        seen = set()
        for row in recent:
            payload = row["payload"]
            if isinstance(payload, str):
                import json as _j
                payload = _j.loads(payload)
            seen.add((row["target_id"], (payload or {}).get("subject")))

        for (student_id, subj), h in sorted(hits.items()):
            if (str(student_id), subj) in seen:
                continue
            first, last, cls = names.get(student_id, ("", "", None))
            student_name = f"{first} {last}".strip()
            summary = (
                f"{student_name} byl uvolněn z {h['released_count']} hodin předmětu "
                f"{subj} (práh {threshold}) a zapisuje si další "
                f"({', '.join(p['date'] for p in h['pending'])})."
            )
            payload = {**h, "student_name": student_name, "class_group": cls}
            async with conn.transaction():
                flag = await emit_flag(
                    conn, module=MODULE, agent=NAME,
                    kind="student.subject_release_alert",
                    target_type="student", target_id=student_id,
                    payload=payload, summary=summary,
                )
                await record_agent_run(
                    conn, module=MODULE, agent=NAME, trigger=trigger,
                    detail={"flag_id": flag["id"], "student_id": student_id,
                            "subject": subj},
                )
            created.append({**payload, "flag_id": flag["id"], "summary": summary})

    if not created:
        return {"agent": NAME, "alerts": 0, "note": "vše už nahlášeno (dedup)"}

    # 4) souhrnný e-mail koordinátorovi
    llm = decide(
        system=("Jsi koordinátor uvolňování z výuky na DuklaLabs. Ze seznamu "
                "upozornění napiš 2–4 věty pro kolegy koordinátory – koho a proč "
                "je třeba prověřit. Neradíš rozhodnutí, jen shrnuješ."),
        user=str([c["summary"] for c in created]),
        schema={"type": "object", "properties": {"summary": {"type": "string"}},
                "required": ["summary"]},
    )
    intro = "" if is_fallback(llm) else f"<p>{esc(llm.get('summary'))}</p>"
    rows = "".join(
        f"<li>{esc(c['summary'])}</li>" for c in created
    )
    mail = await send_mail(
        to=coordinator_emails(),
        subject=f"DuklaLabs: {len(created)} upozornění – opakované uvolnění z předmětu",
        body=wrap_html("Hlídač uvolněných hodin podle předmětu",
                       intro + f"<ul>{rows}</ul>"),
        source="access-agent-subject-watch",
    )
    return {"agent": NAME, "alerts": len(created), "mail": mail}
