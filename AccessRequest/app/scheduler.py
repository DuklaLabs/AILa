"""Naplánované rozesílání e-mailů.

  * učitelům – rozhodovací digest s požadavky na uvolnění: čtvrtek 13:00
  * dozorům na DuklaLabs – denní seznam uvolněných studentů ke kontrole
    docházky: každý den v 7:00

Běží in-process (APScheduler) v rámci AccessRequest serveru. Časy lze ladit
env proměnnými; `SCHEDULER_ENABLED=false` plánovač vypne.
"""
from __future__ import annotations

import datetime
import os

try:
    from zoneinfo import ZoneInfo
except ImportError:  # < 3.9, nemělo by nastat (base image 3.11)
    ZoneInfo = None  # type: ignore

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.decisions import run_supervisor_roster, run_teacher_digest

_scheduler: AsyncIOScheduler | None = None


def _log(*a) -> None:
    print(*a, flush=True)


def get_jobs() -> list[dict]:
    if _scheduler is None:
        return []
    return [
        {"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
        for j in _scheduler.get_jobs()
    ]


def _tz():
    name = os.getenv("SCHEDULER_TZ", "Europe/Prague")
    return ZoneInfo(name) if ZoneInfo else None


def _enabled() -> bool:
    return os.getenv("SCHEDULER_ENABLED", "true").strip().lower() in {
        "1", "true", "yes", "on", "ano",
    }


async def _teacher_digest_job() -> None:
    try:
        res = await run_teacher_digest()
        _log(f"[scheduler] teacher-digest: sent={len(res['sent'])} "
              f"skipped={len(res['skipped'])} errors={len(res['errors'])}")
        if res["errors"]:
            _log("[scheduler] teacher-digest errors:", res["errors"])
    except Exception as e:  # noqa: BLE001
        _log(f"[scheduler] teacher-digest FAILED: {type(e).__name__}: {e}")


async def _supervisor_roster_job() -> None:
    try:
        res = await run_supervisor_roster(
            only_day=datetime.date.today(), approved_only=True
        )
        _log(f"[scheduler] supervisor-roster: sent={len(res['sent'])} "
              f"skipped={len(res['skipped'])} errors={len(res['errors'])}")
        if res["errors"]:
            _log("[scheduler] supervisor-roster errors:", res["errors"])
    except Exception as e:  # noqa: BLE001
        _log(f"[scheduler] supervisor-roster FAILED: {type(e).__name__}: {e}")


def start_scheduler() -> None:
    global _scheduler
    if not _enabled() or _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone=_tz())

    dow = os.getenv("TEACHER_DIGEST_DOW", "thu")
    th = int(os.getenv("TEACHER_DIGEST_HOUR", "13"))
    tm = int(os.getenv("TEACHER_DIGEST_MINUTE", "0"))
    rh = int(os.getenv("SUPERVISOR_ROSTER_HOUR", "7"))
    rm = int(os.getenv("SUPERVISOR_ROSTER_MINUTE", "0"))

    _scheduler.add_job(
        _teacher_digest_job,
        CronTrigger(day_of_week=dow, hour=th, minute=tm, timezone=_tz()),
        id="teacher-digest", replace_existing=True, misfire_grace_time=3600,
    )
    _scheduler.add_job(
        _supervisor_roster_job,
        CronTrigger(hour=rh, minute=rm, timezone=_tz()),
        id="supervisor-roster", replace_existing=True, misfire_grace_time=3600,
    )
    _scheduler.start()
    _log(f"[scheduler] běží – teacher-digest {dow} {th:02d}:{tm:02d}, "
          f"supervisor-roster denně {rh:02d}:{rm:02d} "
          f"({os.getenv('SCHEDULER_TZ', 'Europe/Prague')})")


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
