"""Digest učitelům umí zobrazit doporučení agenta release_advisor
(blok „🤖 doporučeno …“). Bez advice se chová beze změny (zpětná kompatibilita)."""
from datetime import date

from app.notify import build_digest_email

_ITEMS = [{
    "id": 55, "first_name": "Jan", "last_name": "Novák", "class_group": "4.ER",
    "day": date(2026, 9, 17), "hour_number": 3, "start_time": None,
    "end_time": None, "note": None, "approved": None,
}]


def test_digest_without_advice_has_no_robot_block():
    _subj, body = build_digest_email("Učitel", _ITEMS, link="http://x")
    assert "🤖" not in body


def test_digest_with_advice_renders_recommendation():
    advice = {55: {"recommendation": "povolit", "reason": "volná hodina",
                   "confidence": 0.7}}
    _subj, body = build_digest_email("Učitel", _ITEMS, link="http://x", advice=advice)
    assert "🤖" in body
    assert "doporučeno povolit" in body
    assert "volná hodina" in body


def test_digest_advice_only_for_matching_booking():
    advice = {999: {"recommendation": "zamitnout", "reason": "x"}}
    _subj, body = build_digest_email("Učitel", _ITEMS, link="http://x", advice=advice)
    assert "🤖" not in body
