"""Registr agentů pro službu access-agents.

`AGENTS[name]` je coroutine `run(*, trigger: str, ...) -> dict`. Používá ho
plánovač i ruční `POST /run/{name}`. Nové agenty se přidávají sem.
"""
from __future__ import annotations

from app.agents import (
    monthly_lab_report,
    openhours_planner,
    registration_triage,
    subject_release_watch,
)

AGENTS = {
    monthly_lab_report.NAME: monthly_lab_report.run,
    subject_release_watch.NAME: subject_release_watch.run,
    registration_triage.NAME: registration_triage.run,
    openhours_planner.NAME: openhours_planner.run,
}

__all__ = ["AGENTS"]
