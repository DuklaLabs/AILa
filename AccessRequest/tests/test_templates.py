"""Smoke test šablon: každá stránka se vykreslí a má kostru jako v Kroužku
(header.top > .wrap, main > .wrap); stránky pro adminy mají nav.tabs s
aria-current na aktuální záložce, ostatní (student/login/omluvenky) bez záložek."""
import re

import pytest
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["BASE"] = "/ar"

TABBED = {
    "admin.html": "/ar/admin",
    "admin_analytics.html": "/ar/admin/analytics",
    "admin_users.html": "/ar/admin/users",
    "machines.html": "/ar/machines",
}

PLAIN = {
    "index.html": {},
    "login.html": {"error": "x", "next": "/ar/admin"},
    "student_hours.html": {},
    "student_register.html": {"error": None},
    "student_dashboard.html": {"students": [], "my_student_id": None},
    "excuse_confirm.html": {
        "token": "t",
        "request_info": {"status": "pending", "first_name": "A", "last_name": "B",
                         "class_group": "1.EM", "subject_name": "M", "date": "1. 1.",
                         "hour_number": 3},
    },
    "excuse_confirm_batch.html": {"items": [], "action": "approve", "batch_token": "b"},
    "excuse_confirm_done.html": {"message": "ok"},
}


def render(name, ctx):
    return templates.get_template(name).render({"request": None, **ctx})


def _skeleton(html):
    assert re.search(r'<header class="top">\s*<div class="wrap">\s*<div class="brand">', html)
    assert '<div class="logo"' in html and "<h1>" in html
    assert re.search(r'<main>\s*<div class="wrap">', html)
    assert "topbar" not in html and 'class="container"' not in html


@pytest.mark.parametrize("name,href", TABBED.items())
def test_tabbed_pages(name, href):
    html = render(name, {"is_staff": True})
    _skeleton(html)
    assert '<nav class="tabs"' in html and 'class="tabbar" data-ui' in html
    assert '<span class="ind"></span>' in html
    current = re.findall(r'<a href="([^"]+)" aria-current="page"', html)
    assert current == [href]
    assert html.count('<a href="/ar/') >= 4
    assert "AilaUI.auto()" in html and "static/js/ui.js" in html


@pytest.mark.parametrize("name,ctx", PLAIN.items())
def test_plain_pages(name, ctx):
    html = render(name, ctx)
    _skeleton(html)
    assert '<nav class="tabs"' not in html


def test_machines_hides_staff_tabs_for_students():
    html = render("machines.html", {"is_staff": False})
    _skeleton(html)
    assert '<nav class="tabs"' not in html
