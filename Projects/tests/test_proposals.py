"""Čistý test hranice „přímá změna vs. návrh ke schválení“ (bez DB)."""
import pytest

from app.services.proposals import classify_change


@pytest.mark.parametrize(
    "kind",
    ["task.create", "task.delete", "project.update", "finance.update", "project.lifecycle"],
)
def test_risky_kinds_are_proposals(kind):
    assert classify_change(kind) == "proposal"


@pytest.mark.parametrize(
    "kind",
    ["create_task", "set_task_status", "add_time_entry", "update_task_fields", "cokoliv"],
)
def test_safe_kinds_are_direct(kind):
    assert classify_change(kind) == "direct"
