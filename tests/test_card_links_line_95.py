"""L-world-class-95: in the Notes list's card view the link row shares the
details line when both fit, and shows two pills before "+N more links".

Measured by `scratchpad/ui-sweeps/foldfit.js` at 1093x614@1.25 on the
showcase: a linked card was 141px (title, preview, a 26px row of pills, the
details line); with two pills 4 of 9 linked cards share one row and are 111px.
These hold the wiring; the sweep holds the numbers.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def _rule(selector_part: str) -> str:
    for selector, body in re.findall(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", CSS):
        if selector.strip().endswith(selector_part):
            return body
    raise AssertionError(f"no rule for {selector_part}")


def test_the_card_wraps_as_rows_only_when_it_has_links_and_no_editor():
    body = _rule("li:not(.list-window-sentinel, :has(textarea)):has(> .entry-links)")
    assert "flex-flow: row wrap" in body


def test_the_details_keep_their_width_so_they_drop_a_row_rather_than_squeeze():
    body = _rule(":has(> .entry-links) > .entry-meta")
    assert "flex: 1 0 auto" in body, "a shrinkable details line would wrap inside itself beside the pills"
    links = _rule("li:not(.list-window-sentinel, :has(textarea)) > .entry-links")
    assert "order: 1" in links and "order: 2" in body, "the pills come first, the details after them"


def test_the_card_view_asks_for_two_pills_and_the_count_replaces_the_rest():
    js = app_js_text()
    assert 'linksShown: notesViewMode === "cards" ? 2 : 0' in js
    assert "const LINKS_SHOWN = options.linksShown || 3;" in js
    assert "connections.length > LINKS_SHOWN + (options.linksShown ? 0 : 1)" in js
