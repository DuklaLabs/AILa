"""Agent #4 – triage studentských registrací.

Nové registrace (`auth.users.is_active = FALSE`) projde sadou kontrol a k
těm bez zjevného problému **navrhne schválení** (`agent.proposals`
`kind='registration.approve'`); admin ho odklikne ve frontě → teprve pak se
účet aktivuje (`POST /api/students/{id}/approve` v access-request-server).

Úroveň kontroly: **navrhuje.** Agent nikdy neaktivuje účet sám.
"""
from __future__ import annotations

import os
import re
from datetime import date, timedelta

from ailacore import dukla
from ailacore.agents import emit_proposal, record_agent_run
from ailacore.db import get_pool
from ailacore.llm import decide, is_fallback

NAME = "registration_triage"
MODULE = "access"

_NAME_RE = re.compile(r"^[\wáčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ'’\- ]{2,}$", re.UNICODE)

_PENDING_SQL = """
    SELECT u.id AS user_id, s.student_id, s.first_name, s.last_name,
           s.email, s.class_group, s.release_class_teacher
    FROM internal.students s
    JOIN auth.users u ON u.id = s.user_id
    WHERE u.role = 'student' AND u.is_active = FALSE
      AND NOT EXISTS (
          SELECT 1 FROM agent.proposals p
          WHERE p.module = 'access' AND p.kind = 'registration.approve'
            AND p.target_id = u.id::text
            AND p.status IN ('pending', 'approved')
      )
    ORDER BY s.student_id DESC
"""


def _school_domain() -> str:
    return (os.getenv("SCHOOL_EMAIL_DOMAIN")
            or os.getenv("TEACHER_EMAIL_DOMAIN", "spssecb.cz")).strip().lstrip("@")


async def _checks(conn, r: dict) -> dict:
    email = (r["email"] or "").lower()
    first, last, cls = r["first_name"] or "", r["last_name"] or "", r["class_group"] or ""

    domain_ok = email.endswith("@" + _school_domain().lower())
    name_ok = bool(_NAME_RE.match(first)) and bool(_NAME_RE.match(last))

    try:
        monday = date.today() - timedelta(days=date.today().weekday())
        class_in_timetable = bool(await dukla.class_week(cls, monday))
    except Exception:  # noqa: BLE001
        class_in_timetable = None  # neověřitelné
    try:
        ct = await dukla.class_teacher(cls)
    except Exception:  # noqa: BLE001
        ct = None

    dup = await conn.fetchval(
        """
        SELECT COUNT(*) FROM internal.students
        WHERE lower(first_name) = lower($1) AND lower(last_name) = lower($2)
          AND COALESCE(class_group, '') = COALESCE($3, '')
          AND student_id <> $4
        """,
        first, last, cls, r["student_id"],
    )
    return {
        "domain_ok": domain_ok,
        "name_ok": name_ok,
        "class_in_timetable": class_in_timetable,
        "class_teacher_known": ct is not None,
        "duplicate_in_class": int(dup or 0) > 0,
    }


async def run(*, trigger: str = "scheduler") -> dict:
    pool = await get_pool()
    proposed = []
    async with pool.acquire() as conn:
        pending = await conn.fetch(_PENDING_SQL)

        for row in pending:
            r = dict(row)
            checks = await _checks(conn, r)
            clean = (
                checks["domain_ok"] and checks["name_ok"]
                and checks["class_teacher_known"]
                and checks["class_in_timetable"] is not False
                and not checks["duplicate_in_class"]
            )

            llm = decide(
                system=("Jsi asistent přijímání studentů do DuklaLabs. Z výsledků "
                        "kontrol registrace rozhodni, jestli je zjevně v pořádku "
                        "('ok'), nebo ať ji člověk radši prověří ('review'). Buď "
                        "konzervativní: cokoliv podezřelého → 'review'."),
                user=str({"student": {k: r[k] for k in
                                      ("first_name", "last_name", "email", "class_group")},
                          "checks": checks}),
                schema={
                    "type": "object",
                    "properties": {
                        "suggestion": {"type": "string", "enum": ["ok", "review"]},
                        "reason": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["suggestion", "reason"],
                },
            )
            if is_fallback(llm):
                suggestion = "ok" if clean else "review"
                reason = "automatické vyhodnocení kontrol (LLM nedostupný)"
                confidence = 0.6 if clean else 0.4
            else:
                suggestion = llm.get("suggestion") or ("ok" if clean else "review")
                reason = llm.get("reason") or ""
                confidence = float(llm.get("confidence") or (0.7 if clean else 0.4))

            name = f"{r['first_name']} {r['last_name']}".strip()
            tag = "vypadá v pořádku" if suggestion == "ok" else "k ruční kontrole"
            summary = f"{name} ({r['class_group'] or '?'}) – {tag}: {reason}"

            async with conn.transaction():
                p = await emit_proposal(
                    conn, module=MODULE, agent=NAME, kind="registration.approve",
                    target_type="user", target_id=r["user_id"],
                    payload={"student_id": r["student_id"], "email": r["email"],
                             "class_group": r["class_group"], "checks": checks,
                             "suggestion": suggestion},
                    summary=summary, confidence=confidence,
                )
                await record_agent_run(
                    conn, module=MODULE, agent=NAME, trigger=trigger,
                    detail={"proposal_id": p["id"], "user_id": r["user_id"],
                            "suggestion": suggestion},
                )
            proposed.append({"proposal_id": p["id"], "user_id": r["user_id"],
                             "suggestion": suggestion, "summary": summary})

    return {"agent": NAME, "proposed": len(proposed), "items": proposed}
