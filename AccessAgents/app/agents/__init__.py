"""Registr agentů pro službu access-agents.

`AGENTS[name]` je coroutine `run(*, trigger: str, ...) -> dict`. Používá ho
plánovač i ruční `POST /run/{name}`. Nové agenty se přidávají sem.
"""
from __future__ import annotations

from app.agents import monthly_lab_report

AGENTS = {
    monthly_lab_report.NAME: monthly_lab_report.run,
}

__all__ = ["AGENTS"]
