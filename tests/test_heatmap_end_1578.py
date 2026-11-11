"""The Activity heatmap opens at today (INBOX 1578, the owner: "the activity
heatmap is auto scrolled to the left and not right where the actual data is").

The grid is `content-visibility: auto`, so a `scrollLeft = scrollWidth` write clamped to 0; the
first fix read the last cell's rect and re-took the end on every refit (INBOX 1741: that read was
70ms of forced layout at 4x). The end is now CSS only: the grid is `direction: rtl` (a scroll box
starts at its right edge) and the weeks are appended newest first, which draws them oldest to
newest. Measured in the running app: the newest day's right edge sits on the grid's right edge
(1051 of 1051) with scrollLeft 0, and no script reads it. This file pins the rule.
"""

from __future__ import annotations

from pathlib import Path


def _widget() -> str:
    text = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    return text.split("async function renderHeatmapWidget(", 1)[1].split("\n// --- category breakdown", 1)[0]


ROOT = Path(__file__).resolve().parents[1]


def test_the_end_is_css_only_so_nothing_reads_layout_for_it():
    body = _widget()
    code = "\n".join(line for line in body.splitlines() if not line.strip().startswith("//"))
    for gone in ("toEnd", "atEnd", "getBoundingClientRect", "scrollLeft", "scrollWidth", "dash-refit", "contentvisibilityautostatechange"):
        assert gone not in code, gone
    sized = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8").split("function sizeDashWidgets()", 1)[1].split("\n}\n", 1)[0]
    assert "dash-refit" not in sized


def test_the_grid_is_right_to_left_and_the_weeks_are_appended_newest_first():
    css = (ROOT / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    block = css[css.index("\n.heatmap {") :].split("}", 1)[0]
    assert "direction: rtl;" in block
    assert "for (let w = cells.length - 7; w >= 0; w -= 7) grid.append(...cells.slice(w, w + 7));" in _widget()
