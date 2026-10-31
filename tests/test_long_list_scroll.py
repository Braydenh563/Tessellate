"""The Library's and the Timeline's long lists stay smooth while they grow.

Measured on a thousand-note seed (`scratchpad/ui-sweeps/libtlscroll.js`,
libtl-0926): a chunk of Library cards landing mid-scroll took 45 to 88ms
and the Timeline dropped a dozen frames per 120 wheel steps. Four causes,
each pinned here, because each one is a small edit away from coming back and
nothing else in the suite scrolls a thousand rows.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def read(name: str) -> str:
    return (FRONTEND / "js" / name).read_text(encoding="utf-8")


def function_body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    depth = 0
    for index in range(source.index(") {", start) + 2, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"{name} has no end")


def test_the_incremental_renderer_can_build_by_time_and_the_library_asks_it_to():
    # In library.js since the Notes list was windowed (audit 1029 N9).
    source = read("library.js")
    body = function_body(source, "renderIncrementally")
    assert "budgetMs = 0" in body, "opt-in, so a caller that does not ask builds by count"
    assert "performance.now() - started > budgetMs" in body
    # The observer only fires on a *change* of intersection, so a small chunk
    # that leaves the sentinel near must carry on by itself, on frames.
    assert "requestAnimationFrame(pump)" in body
    assert re.search(r"budgetMs:\s*\d+", read("library.js"))


def test_a_new_card_does_not_restyle_the_whole_grid():
    # `:has(.library-card-tick:checked)` on the grid re-matched every card
    # each time a card (with its tick) was inserted: 10 cards restyled 1,270
    # elements. The selection code toggles a class instead.
    css = "\n".join(p.read_text(encoding="utf-8") for p in (FRONTEND / "css").glob("*.css"))
    assert ":has(.library-card-tick:checked)" not in css
    assert ".library-grid.is-choosing .library-card-tick" in css
    library = read("library.js")
    assert 'classList.toggle("is-choosing", chosen.length > 0)' in library
    assert 'classList.toggle("is-choosing", n > 0)' in library


def test_the_timeline_pages_into_the_shared_window_and_counts_from_the_data():
    # Its intent moved (audit 1028 S53): a page used to be built row by row
    # across frames on a 6ms budget (TIMELINE_APPEND_BUDGET_MS) and the DOM
    # grew with every page. It now lands as one-element shells in the same
    # `windowRows` the Notes list uses, and the rows near the reader are built.
    source = read("timeline.js")
    body = function_body(source, "appendTimelineRows")
    assert "TIMELINE_APPEND" not in source
    assert "win.add(list, run.rows)" in body
    assert "timelineRowElement(" not in body, "a page is not built whole"
    # Built rows are fewer than loaded rows, so the count is the data's.
    assert 'querySelectorAll(".timeline-row")' not in body
    assert "visible.size" in body
    assert "windowRows(" in function_body(source, "newTimelineWindow")
    # The Notes list and the Timeline share the one window (S16, S53).
    assert "windowRows(" in function_body(read("notes-list.js"), "renderWindowed")


def test_the_timeline_keyboard_and_focus_reach_rows_that_are_not_built():
    source = read("timeline.js")
    assert "fill(row)" in function_body(source, "timelineRowByKey")
    assert "timelineRowByKey(key)" in function_body(source, "focusTimelineRow")
    assert "timelineRowEls()" in source[source.index('$("timeline-scroll").addEventListener("keydown"') :][:400]
    # Leaving the feed (table, calendar) stops the window's observer.
    assert "timelineWindow.win?.stop()" in function_body(source, "paintTimeline")


def test_the_timeline_scroll_does_its_work_once_a_frame():
    source = read("timeline.js")
    listener = source[source.index('$("timeline-scroll").addEventListener("scroll"') :][:600]
    assert "requestAnimationFrame" in listener
    assert "passive: true" in listener
    span = function_body(source, "timelineDensitySpan")
    assert "timelineSpanCache.density === timelineDensity" in span
    window_ = function_body(source, "drawTimelineWindow")
    assert 'getAttribute("y") !==' in window_


def test_the_strip_window_comes_from_an_observer_not_hit_tests():
    # Up to sixteen `elementFromPoint` probes a frame were half the feed's
    # scripting while scrolling (38 to 20 ms/s measured; the table 39 to 15).
    source = read("timeline.js")
    window_ = function_body(source, "drawTimelineWindow")
    assert "document.elementFromPoint(" not in window_
    assert "timelineOnScreen" in window_
    assert "timelineWatchRow(li);" in function_body(source, "timelineRowElement")
    assert "timelineWatchRow(tr);" in function_body(source, "timelineTableRow")
    assert "timelineForgetRows();" in function_body(source, "paintTimeline")
    watch = function_body(source, "timelineWatchRow")
    assert 'root: $("timeline-scroll")' in watch
    # The scroll listener only asks for the next page now.
    listener = source[source.index('$("timeline-scroll").addEventListener("scroll"') :][:400]
    assert "drawTimelineWindow" not in listener
