"""Source text: a cursor and a fold are only seen in a running browser; the behaviour is measured by scratchpad/ui-sweeps/wbpresent-cursor.js (CI), so this pins the rules and code that make it.

Presenting a board (the owner, 2026-11-22): over the slide the cursor is the plain
arrow and hides at rest, over the bar it is the normal one; H or the bar's caret
folds the bar to a handle, kept in this browser; the paging keys are in the bar's
tooltips. Measured in the app by scratchpad/ui-sweeps/wbpresent-cursor.js (CI)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend/js/whiteboard-present.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/css/07-whiteboard-misc.css").read_text(encoding="utf-8")
HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")


def _rule(selector_part: str) -> str:
    for match in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", CSS):
        if selector_part in match.group(1) + "{":
            return match.group(1) + "{" + match.group(2) + "}"
    raise AssertionError(selector_part)


def test_the_slide_hides_the_cursor_at_rest_and_never_shows_an_items_hover_cursor():
    plain = _rule(".wb-presenting .whiteboard-container {")
    assert "cursor: default;" in plain
    rest = _rule(".wb-presenting.wb-cursor-rest .whiteboard-container")
    assert "cursor: none;" in rest and ".wb-laser-on" in rest
    # No item's hover cursor: both layers take no pointer events while presenting,
    # so the container is all the pointer is ever over (no universal `*` needed).
    lazy = (ROOT / "frontend/css/library-lazy.css").read_text(encoding="utf-8")
    assert re.search(r"\.wb-presenting #wb-html-layer,\s*#library-view-whiteboard\.wb-presenting #wb-svg-layer \{\s*pointer-events: none;", lazy)
    assert "wb-present-bar" not in plain + rest  # the bar keeps its own cursor
    assert 'container.style.cursor = "";' in JS and "board.style.cursor = cursor" in JS  # the tool's inline one, lifted
    assert 'text.style.cursor = "move"' not in (ROOT / "frontend/js/whiteboard-map.js").read_text(encoding="utf-8")
    assert 'host.addEventListener("pointermove", wbPresentCursorWake)' in JS
    assert 'host?.removeEventListener("pointermove", wbPresentCursorWake)' in JS
    assert "setTimeout(" in JS and "requestAnimationFrame(wbPresentCursorWake" not in JS


def test_the_bar_folds_to_a_handle_by_h_or_its_caret_and_the_choice_is_kept():
    assert 'id="wb-present-fold"' in HTML and 'title="Hide the bar (H)"' in HTML
    assert re.search(r'<button[^>]*id="wb-present-handle"[^>]*class="[^"]*wb-present-bar[^"]*hidden"', HTML)
    assert 'event.key === "h" || event.key === "H") wbPresentFold()' in JS
    assert 'prefs.set(WB_PRESENT_FOLD_KEY, folded ? "1" : "0")' in JS
    assert "wbPresentApplyFold(wbPresentFolded())" in JS.replace("const folded = wbPresentFolded();\n    wbPresentApplyFold(folded)", "wbPresentApplyFold(wbPresentFolded())")


def test_the_paging_keys_are_named_where_a_person_looks():
    for key in ("ArrowRight: 1", "PageDown: 1", '" ": 1', "ArrowLeft: -1", "PageUp: -1"):
        assert key in JS
    assert 'event.key === "Home") wbPresentShow(0)' in JS and 'event.key === "End")' in JS
    assert "Left arrow or Page Up; Home for the first" in HTML
    assert "Right arrow, Space or Page Down; End for the last" in HTML
