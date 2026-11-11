"""INBOX 1716, the owner's lag lines for the OCR viewer and the perch look (static: no browser in pytest).

Measured with a 4x CDP CPU throttle on 320 notes and a stored 60-section page (the numbers are in the
CHANGELOG line): the regions answer's continuation paid 45 to 91ms of forced layout for a scroll of
the reading list, and the dock fit measured three times where one fits a wide row.
"""

from __future__ import annotations

from pathlib import Path
from tests._js_scope import unwrapped

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _body(src: str, head: str) -> str:
    start = src.index(head)
    return src[start : src.index("\n}\n", start) + 2]


def test_the_reading_list_scrolls_in_the_next_frame_not_in_the_answer() -> None:
    src = (JS / "library.js").read_text(encoding="utf-8")
    reveal = _body(src, "function ocrRevealRegionsForPage(")
    assert "scrollIntoView" not in reveal, "a scroll right after the list was rebuilt lays the dialog out in the script"
    assert "ocrUi.revealPending = first;" in reveal
    schedule = _body(src, "function ocrScheduleFitDock(")
    assert "scrollIntoView" in schedule and "ocrUi.revealPending = null;" in schedule


def test_a_wide_dock_is_measured_once() -> None:
    fit = _body((JS / "library.js").read_text(encoding="utf-8"), "function ocrFitDock(")
    assert ".width >= 720 && fits(0)" in fit


def test_the_perch_look_does_not_repeat_on_an_unchanged_page() -> None:
    look = _body(unwrapped((JS / "avatars.js").read_text(encoding="utf-8")), "function nameMarkBuddyCheck(")
    assert "nmb.lastClear" in look
    assert "nmb.pageAt <= clear.at && nmbFollow.scrollAt <= clear.at" in look
