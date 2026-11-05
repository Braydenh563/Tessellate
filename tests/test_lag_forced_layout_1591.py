"""INBOX 1591, a31m: the owner's lag lines that are not Atlas's.

Reproduced at 4x CPU on a 1,200-note notebook (reload on the dashboard, `long-animation-frame` scripts):
the `Response.json.then` entry of notes-list.js (the notes' response, whose promise cascade draws the
dashboard) was 363ms with 160ms forced layout (median of five). The dashboard laid the page out three
times for one sizing (`sizeDashWidgets`: the reset to `span 1`, the read, the heatmap's refit after the
writes), once more at once from `watchDashWidgets`, and once more from the loading outline's box reads,
all inside that cascade. Each is pinned by the shape that fixed it, in the style of
tests/test_lag_forced_layout_1575.py.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")


def _body(source: str, head: str) -> str:
    start = source.index(head)
    depth = 0
    for i in range(source.index("{", start), len(source)):
        depth += source[i] == "{"
        depth -= source[i] == "}"
        if depth == 0:
            return source[start : i + 1]
    raise AssertionError(head)


def test_sizing_reads_everything_then_writes_everything() -> None:
    body = _body(DASH, "function sizeDashWidgets(")
    # No release of the spans to measure: the grid is `align-items: start`, so a card's height does not depend on its span.
    assert 'gridRowEnd = "span 1"' not in body
    last_read = max(body.index("getBoundingClientRect"), body.index('dispatchEvent(new Event("dash-refit"))'))
    assert last_read < body.index("style.gridRowEnd = sizeDashWidgetSpan("), "the heatmap refit reads, so it goes before the first write"


def test_the_grid_stays_start_aligned_so_the_reset_is_not_needed() -> None:
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    block = css[css.index("grid-auto-rows: 1px;") :][:900]
    assert "align-items: start;" in block


def test_the_card_observer_is_the_first_sizing_not_a_second_one_beside_it() -> None:
    body = _body(DASH, "function watchDashWidgets(")
    tail = body[body.index("dashResizeObserver.observe(card)") :]
    assert "sizeDashWidgets()" not in tail, "observing fires once per card, a frame on, with the widgets drawn"
    # The no-observer fallback still sizes at once.
    assert body.index("sizeDashWidgets();") < body.index("dashResizeObserver?.disconnect()")


def test_the_loading_outline_is_placed_in_a_frame_not_in_the_notes_cascade() -> None:
    body = DASH.split("async function renderDashboard(", 1)[1].split("\n}\n", 1)[0]
    place = body.index("outline = dashFillingSkeleton(grid, drawing.length)")
    assert "afterFrames(() => {" in body[place - 200 : place], "its box reads wait for the frame"
    assert "}, 1);" in body[place : place + 200]
    assert 'grid.classList.contains("dash-filling")' in body[place - 200 : place], "and it is not placed once the grid has settled"
    assert body.index("let outline = null;") < place < body.index("dashFillingSkeletonDone(outline)")


def test_the_outline_reads_the_grid_once_before_it_appends_anything() -> None:
    # Measured at 4x CPU (1,200 notes): `grid.offsetTop` after `host.appendChild(outline)` laid the page out a
    # second time, 86ms, beside the 173ms of the first read. The outline is absolute, so the grid's offset is
    # the same before the append: one read, used for the placement and for the follow's origin.
    body = _body(DASH, "function dashFillingSkeleton(")
    assert body.count("= grid.offsetTop;") == 1
    assert body.index("= grid.offsetTop;") < body.index("host.appendChild(outline)")
    assert "grid.offsetTop - top0" in body

