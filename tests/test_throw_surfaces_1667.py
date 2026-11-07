"""INBOX 1667, the owner's log 2026-11-07 (Windows, Dashboard): `spotNow` 5956ms,
5774 of it forced layout. The landing read its obstacles (142 controls' boxes
and the bars') after the release's writes, so its first read paid a whole page
layout. They are taken in the release's read phase now, and the landing reads
nothing. Measured (40-note Dashboard, 8,739 elements, 4x CPU, 20 seeded
throws on a dirtied page): landing 13.6ms median / 23.3 max to 0.8 / 3.2; the
spots were identical."""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def app_js_text() -> str:
    return (JS / "avatars.js").read_text(encoding="utf-8") + (JS / "phone-shell.js").read_text(encoding="utf-8")


def frontend_text(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")

READS = ("getBoundingClientRect", "getComputedStyle", "offsetWidth", "offsetHeight", "scrollHeight", "elementFromPoint", "getClientRects")


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def test_the_plan_takes_the_surfaces_before_it_returns_and_the_landing_uses_them():
    body = _body(frontend_text("companion-throw.js"), "function companionThrowPlan(")
    assert "const taken = nameMarkBuddyTakeSurfaces();" in body
    assert "nameMarkBuddyThrowSpot(companionThrowAt(s)), taken)" in body
    assert body.index("nameMarkBuddyTakeSurfaces()") < body.index("land:")


def test_the_landing_answers_from_the_taken_measure():
    js = app_js_text()
    once = _body(js, "function nameMarkBuddyMeasureOnce(")
    assert "taken?.held" in once and "nmb.place.boxes = taken.rects" in once
    # Put back whatever was there, so a later placement reads fresh.
    assert "nmb.place.boxes = boxes;" in once


def test_the_throw_spot_itself_reads_no_layout():
    spot = _body(frontend_text("companion-throw.js"), "function nameMarkBuddyThrowSpot(")
    assert not [r for r in READS if r in spot]


def test_the_surfaces_are_read_before_any_write():
    take = _body(app_js_text(), "function nameMarkBuddyTakeSurfaces(")
    for write in (".style.", "classList.", "setAttribute", ".dataset."):
        assert write not in take


def test_the_header_token_has_no_first_call_of_its_own():
    body = _body(app_js_text(), "function initHeaderHeightToken(")
    assert body.rstrip().endswith("new ResizeObserver(write).observe(bar);")
