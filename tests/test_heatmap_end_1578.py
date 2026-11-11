"""The Activity heatmap opens at today (INBOX 1578, the owner: "the activity
heatmap is auto scrolled to the left and not right where the actual data is").

The grid is `content-visibility: auto`, so in the frame after it was built its
`scrollWidth` read its box (304 of 701 at 1440) and `scrollLeft = scrollWidth`
clamped to 0. The end is now read from the last cell's rect and re-taken when
the grid is laid out, when it stops being skipped and on a resize, for as long
as the reader has not scrolled away. Measured in the running app (INBOX 1578:
scrollLeft 0 of 397 before, 397 of 397 after); this file pins the rule.
"""

from __future__ import annotations

from pathlib import Path


def _widget() -> str:
    text = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    return text.split("async function renderHeatmapWidget(", 1)[1].split("\n// --- category breakdown", 1)[0]


def test_the_end_is_read_from_the_last_cell_not_from_a_scroll_width_that_may_be_stale():
    body = _widget()
    assert "grid.scrollLeft = grid.scrollWidth" not in body
    assert "last.getBoundingClientRect().right - grid.getBoundingClientRect().right" in body


def test_it_is_taken_again_when_the_grid_is_laid_out_unskipped_or_resized():
    body = _widget()
    assert 'grid.addEventListener("dash-refit", toEnd)' in body
    assert "ResizeObserver" not in body  # the file's wake sources only fall (test_frontend_wake_sources)
    sized = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert 'heat.dispatchEvent(new Event("dash-refit"))' in sized.split("function sizeDashWidgets()", 1)[1].split("\n}\n", 1)[0]
    assert '"contentvisibilityautostatechange"' in body
    assert "requestAnimationFrame(toEnd)" in body


def test_a_reader_who_scrolled_away_is_left_where_they_are():
    body = _widget()
    assert "if (!atEnd || !last) return;" in body
    assert "atEnd = grid.scrollWidth - grid.clientWidth - grid.scrollLeft < 2;" in body


def test_it_writes_only_when_off_the_end_and_reads_the_scroll_two_frames_on():
    """Lag rest (INBOX 1741): an unconditional write fired a scroll event whose handler read scrollWidth in the event (132 to 187ms forced at 4x)."""
    body = _widget()
    assert "if (Math.abs(off) >= 1) grid.scrollLeft += off;" in body
    scroll = body.split('grid.addEventListener("scroll"', 1)[1].split("}, { passive: true });", 1)[0]
    assert "afterFrames(" in scroll
