"""Agent #5 – plánovač otevřených hodin / dozorů.

Na příští školní týden navrhne, které otevřené hodiny otevřít, s jakou
kapacitou a kterým dozorem – podle:
  - kdy dozoři (`DUKLA_SUPERVISORS`) **neučí** (z duklamaps),
  - historické poptávky podle (den v týdnu, vyučovací hodina),
  - co už je na příští týden otevřené (nenavrhuje duplicity).

Úroveň kontroly: **navrhuje.** Vytvoří **jeden** návrh
`kind='open_hours.week_plan'` se seznamem slotů; koordinátor ho ve frontě
schválí a teprve pak se sloty založí (apply v access-request-server přes
stávající logiku `open_hours.py`). Agent nezakládá nic přímo.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

from ailacore import access_metrics as m
from ailacore import dukla
from ailacore.agents import emit_proposal, record_agent_run
from ailacore.db import get_pool
from ailacore.llm import decide, is_fallback

NAME = "openhours_planner"
MODULE = "access"

MAX_SLOTS = int(os.getenv("OPENHOURS_PLANNER_MAX_SLOTS", "8"))
LOOKBACK_DAYS = int(os.getenv("OPENHOURS_PLANNER_LOOKBACK_DAYS", "90"))
MIN_CAPACITY = int(os.getenv("OPENHOURS_PLANNER_MIN_CAPACITY", "4"))
_CZ_DOW = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]


def _next_week_monday(today: date) -> date:
    this_monday = today - timedelta(days=today.weekday())
    return this_monday + timedelta(days=7)


async def _free_supervisors_by_slot(monday: date) -> dict[tuple, list[str]]:
    """(date_iso, hour_number) -> dozoři, kteří v tu dobu podle rozvrhu NEučí."""
    everyone = dukla.supervisor_names()
    if not everyone:
        return {}
    try:
        busy_rows = await dukla.fetch_supervisions(
            monday, monday + timedelta(days=4), week="next"
        )
    except Exception:  # noqa: BLE001 - best effort
        busy_rows = []
    busy: dict[tuple, set] = {}
    for r in busy_rows:
        busy.setdefault((r["date"], r["hour_number"]), set()).add(r["supervisor"])

    out: dict[tuple, list[str]] = {}
    for d in range(5):
        day_iso = (monday + timedelta(days=d)).isoformat()
        for hour in range(1, 9):  # rozumné vyučovací hodiny
            taken = busy.get((day_iso, hour), set())
            free = [s for s in everyone if s not in taken]
            if free:
                out[(day_iso, hour)] = free
    return out


def _rule_based_plan(monday, demand, free_by_slot, existing) -> list[dict]:
    """Fallback bez LLM: seřaď poptávku, ber sloty s volným dozorem, ne duplicity."""
    used_supervisor_load: dict[str, int] = {}
    taken = {(e["date"].isoformat() if hasattr(e["date"], "isoformat") else e["date"],
              e["hour_number"]) for e in existing}
    plan: list[dict] = []
    for row in demand:
        if len(plan) >= MAX_SLOTS:
            break
        wd, hour = int(row["weekday"]), int(row["hour_number"])
        if wd > 4 or not (1 <= hour <= 8):
            continue
        day = monday + timedelta(days=wd)
        key = (day.isoformat(), hour)
        if key in taken or key not in free_by_slot:
            continue
        free = sorted(free_by_slot[key], key=lambda s: used_supervisor_load.get(s, 0))
        sup = free[0]
        used_supervisor_load[sup] = used_supervisor_load.get(sup, 0) + 1
        cap = max(MIN_CAPACITY, int(round(float(row.get("avg_booked") or 0))) or MIN_CAPACITY)
        plan.append({
            "date": day.isoformat(), "hour_number": hour, "capacity": cap,
            "supervisor": sup,
            "reason": (f"{_CZ_DOW[wd]} {hour}. h – historicky průměr "
                       f"{row.get('avg_booked')} zapsaných, dozor {sup} volný"),
        })
        taken.add(key)
    return plan


async def run(*, trigger: str = "scheduler", today: date | None = None) -> dict:
    today = today or date.today()
    monday = _next_week_monday(today)
    friday = monday + timedelta(days=4)

    demand = await m.demand_by_slot(LOOKBACK_DAYS)
    free_by_slot = await _free_supervisors_by_slot(monday)
    existing = await m.open_slots_between(monday, friday + timedelta(days=1))

    if not free_by_slot:
        return {"agent": NAME, "slots": 0,
                "note": "žádný volný dozor / duklamaps nedostupné"}

    llm = decide(
        system=(
            "Jsi koordinátor otevřených hodin ve školní laboratoři DuklaLabs. "
            "Navrhni sloty na příští týden. Vstup: 'demand' = historická poptávka "
            "podle (weekday 0=po, hour), 'free_by_slot' = kde je jaký dozor volný, "
            "'existing' = co už je otevřené (nenavrhuj to znovu). Vyber max "
            f"{MAX_SLOTS} nejvytíženějších slotů, ke každému přiřaď JEDNOHO dozora "
            "z volných pro daný slot a kapacitu (>= průměr zapsaných, min "
            f"{MIN_CAPACITY}). Datum spočítej: monday + weekday dní."
        ),
        user=str({
            "monday": monday.isoformat(),
            "demand": demand[:20],
            "free_by_slot": {f"{k[0]}|{k[1]}": v for k, v in list(free_by_slot.items())},
            "existing": [{"date": (e["date"].isoformat() if hasattr(e["date"], "isoformat")
                                   else e["date"]), "hour_number": e["hour_number"]}
                         for e in existing],
        }),
        schema={
            "type": "object",
            "properties": {"slots": {"type": "array", "items": {"type": "object",
                "properties": {
                    "date": {"type": "string"}, "hour_number": {"type": "integer"},
                    "capacity": {"type": "integer"}, "supervisor": {"type": "string"},
                    "reason": {"type": "string"}},
                "required": ["date", "hour_number", "capacity", "supervisor"]}}},
            "required": ["slots"],
        },
    )

    if is_fallback(llm):
        slots = _rule_based_plan(monday, demand, free_by_slot, existing)
        method = "rule_based"
    else:
        raw = llm.get("slots") or []
        # sanity: dozor musí být volný pro daný slot, hodina 1..8, ne duplicita
        taken = {((e["date"].isoformat() if hasattr(e["date"], "isoformat")
                   else e["date"]), e["hour_number"]) for e in existing}
        slots = []
        for s in raw[:MAX_SLOTS]:
            try:
                d, h = str(s["date"]), int(s["hour_number"])
            except (KeyError, ValueError, TypeError):
                continue
            key = (d, h)
            free = free_by_slot.get(key, [])
            if key in taken or not (1 <= h <= 10) or s.get("supervisor") not in free:
                continue
            slots.append({
                "date": d, "hour_number": h,
                "capacity": max(MIN_CAPACITY, int(s.get("capacity") or MIN_CAPACITY)),
                "supervisor": s["supervisor"],
                "reason": str(s.get("reason") or ""),
            })
            taken.add(key)
        method = "llm"
        if not slots:  # LLM nic použitelného → fallback
            slots = _rule_based_plan(monday, demand, free_by_slot, existing)
            method = "rule_based_after_llm"

    if not slots:
        return {"agent": NAME, "slots": 0, "note": "nic k navržení"}

    summary = (
        f"Návrh {len(slots)} otevřených hodin na týden od {monday.isoformat()} "
        f"({method}): "
        + "; ".join(f"{s['date']} {s['hour_number']}. h / {s['supervisor']} "
                    f"(kap. {s['capacity']})" for s in slots)
    )
    payload = {
        "week_monday": monday.isoformat(),
        "slots": slots,
        "method": method,
        "basis": {"demand_rows": len(demand),
                  "free_supervisor_slots": len(free_by_slot),
                  "existing_slots": len(existing)},
    }

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            prop = await emit_proposal(
                conn, module=MODULE, agent=NAME, kind="open_hours.week_plan",
                target_type="week", target_id=monday.isoformat(),
                payload=payload, summary=summary, confidence=None,
            )
            await record_agent_run(
                conn, module=MODULE, agent=NAME, trigger=trigger,
                detail={"proposal_id": prop["id"], "slots": len(slots),
                        "method": method},
            )

    return {"agent": NAME, "proposal_id": prop["id"], "slots": len(slots),
            "method": method}
