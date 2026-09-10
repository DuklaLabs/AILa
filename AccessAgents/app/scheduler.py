"""Plánovač agentů (in-process APScheduler).

Bezpečná brzda: `ACCESS_AGENT_ENABLED` musí být pravdivé, jinak se
nezaregistruje žádný job (agenti jdou pořád spustit ručně přes `POST /run/{name}`).
Časy jednotlivých agentů se ladí env proměnnými.
"""
from __future__ import annotations

import os

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agents import AGENTS

_scheduler: AsyncIOScheduler | None = None


def _log(*a) -> None:
    print("[access-agents]", *a, flush=True)


def enabled() -> bool:
    return os.getenv("ACCESS_AGENT_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on", "ano",
    }


def _tz():
    name = os.getenv("SCHEDULER_TZ", "Europe/Prague")
    return ZoneInfo(name) if ZoneInfo else None


def get_jobs() -> list[dict]:
    if _scheduler is None:
        return []
    return [
        {"id": j.id,
         "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
        for j in _scheduler.get_jobs()
    ]


async def _run_agent(name: str) -> None:
    try:
        res = await AGENTS[name](trigger="scheduler")
        _log(f"{name}: {res}")
    except Exception as e:  # noqa: BLE001 - job nesmí shodit scheduler
        _log(f"{name} SELHAL: {type(e).__name__}: {e}")


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    if not enabled():
        _log("plánovač vypnutý (ACCESS_AGENT_ENABLED). Agenti jdou spustit ručně.")
        return

    _scheduler = AsyncIOScheduler(timezone=_tz())

    # #1 měsíční report – 1. den v měsíci
    _scheduler.add_job(
        lambda: _run_agent("monthly_lab_report"),
        CronTrigger(
            day=int(os.getenv("MONTHLY_REPORT_DAY", "1")),
            hour=int(os.getenv("MONTHLY_REPORT_HOUR", "6")),
            minute=0, timezone=_tz(),
        ),
        id="monthly_lab_report", replace_existing=True, misfire_grace_time=3600,
    )

    # #2 hlídač uvolněných hodin podle předmětu – denně večer
    _scheduler.add_job(
        lambda: _run_agent("subject_release_watch"),
        CronTrigger(
            hour=int(os.getenv("SUBJECT_WATCH_HOUR", "18")),
            minute=0, timezone=_tz(),
        ),
        id="subject_release_watch", replace_existing=True, misfire_grace_time=3600,
    )

    # #4 triage registrací – pravidelný poll
    _scheduler.add_job(
        lambda: _run_agent("registration_triage"),
        CronTrigger(
            minute=f"*/{int(os.getenv('REG_TRIAGE_EVERY_MIN', '15'))}",
            timezone=_tz(),
        ),
        id="registration_triage", replace_existing=True, misfire_grace_time=600,
    )

    # #5 plánovač otevřených hodin – týdně (dopoledne, před plánováním týdne)
    _scheduler.add_job(
        lambda: _run_agent("openhours_planner"),
        CronTrigger(
            day_of_week=os.getenv("OPENHOURS_PLANNER_DOW", "thu"),
            hour=int(os.getenv("OPENHOURS_PLANNER_HOUR", "9")),
            minute=0, timezone=_tz(),
        ),
        id="openhours_planner", replace_existing=True, misfire_grace_time=3600,
    )

    _scheduler.start()
    _log("plánovač běží:", ", ".join(j["id"] for j in get_jobs()))


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
