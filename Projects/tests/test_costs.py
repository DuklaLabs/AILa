"""Čistý test finančního součtu prototypu (bez DB)."""
from app.services.costs import compute_project_costs


def test_material_plus_labor():
    r = compute_project_costs(
        material_czk=1000, minutes=120, hourly_rate_czk=500, planned_budget_czk=4000
    )
    assert r["material_czk"] == 1000
    assert r["labor_hours"] == 2.0
    assert r["labor_czk"] == 1000.0
    assert r["total_czk"] == 2000.0
    assert r["budget_pct"] == 50.0
    assert r["over_budget"] is False


def test_over_budget_flag():
    r = compute_project_costs(
        material_czk=3000, minutes=300, hourly_rate_czk=500, planned_budget_czk=4000
    )
    # 3000 + 5h*500 = 5500 > 4000
    assert r["total_czk"] == 5500.0
    assert r["budget_pct"] == 137.5
    assert r["over_budget"] is True


def test_no_budget_means_no_pct():
    for budget in (None, 0):
        r = compute_project_costs(
            material_czk=10, minutes=60, hourly_rate_czk=500, planned_budget_czk=budget
        )
        assert r["planned_budget_czk"] is None
        assert r["budget_pct"] is None
        assert r["over_budget"] is False


def test_empty_project():
    r = compute_project_costs(
        material_czk=0, minutes=0, hourly_rate_czk=500, planned_budget_czk=1000
    )
    assert r["total_czk"] == 0.0
    assert r["budget_pct"] == 0.0
