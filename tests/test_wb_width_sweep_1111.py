"""The whiteboard's width sweep (2026-11-11): what it found, pinned at the cause.

Measured in the running app at 360, 390 touch, 768, 1280, 1920 and 2560, at
125, 150 and 200 percent, light and dark (`/tmp` sweep over `lib.js`).
No width scrolled the page. Four things were wrong:

- a paired Format field (X, Y, W, H) kept the global field's --space-5 side
  padding: a 26px content box in a 62px cell, so "812" read "8(";
- the Format range input's own margin pushed a row 2px past its panel, and
  the command row could not wrap, so its buttons ran 8 to 60px out of it;
- the tools panel published its width while docked along the bottom (758px at
  768) and the side-dock rule read that back as the column's width;
- a 640x400 window left the Library panel 8px tall, its last two tabs
  clipped by the board, and its menu was pushed back below the button after
  `place()` had opened it upward.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"


def _rule(file: str, selector: str) -> str:
    text = (CSS / file).read_text(encoding="utf-8")
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert match, f"{selector} not found in {file}"
    return match.group(1)


def test_a_paired_format_field_gives_back_its_side_padding():
    body = _rule("library-lazy.css", '.wb-format .wb-fmt-cell input[type="number"]')
    assert "padding-inline: var(--space-1)" in body
    assert "text-align: center" in body
    text = (CSS / "library-lazy.css").read_text(encoding="utf-8")
    # After the panel's own field rules, so the cascade (equal specificity
    # would not do: this one is longer) and the source order agree.
    assert text.index('.wb-format .wb-fmt-cell input[type="number"] {') > text.index(
        '.wb-format input[type="number"]:is(:hover, :focus-visible) {'
    )


def test_the_format_range_has_no_margin():
    #: The command row's overflow at 768 is fixed the other way, by test_wrapzoom_docs_1111 (the buttons drop under the name, the row stays nowrap), which landed on the hub first.
    assert "margin: 0" in _rule("library-lazy.css", '.wb-fmt-row input[type="range"]')


def test_the_tools_width_is_published_only_while_docked_at_the_side():
    js = frontend_text("whiteboard.js")
    assert 'name !== "tools" || panel.dataset.dock === "side"' in js
    assert "wbPanelMetricsRoot.style.setProperty(`--wb-w-${name}`" in js


def test_the_sidebar_keeps_a_floor_on_a_short_window():
    body = _rule("07-whiteboard-misc.css", ".wb-sidebar")
    assert "min-height: min(14rem, 60%)" in body


def test_a_short_window_lays_the_sidebar_tabs_in_a_row_and_scrolls_the_panel():
    text = (CSS / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    start = text.index("@media (min-width: 600px) and (max-height: 520px) {")
    block = text[start : text.index("/* The rows' own list gap", start)]
    assert "bottom: var(--space-2)" in block
    assert re.search(r"\.wb-sidebar \.wb-sidebar-rail \{\s*flex-direction: row;", block)
    assert re.search(r"\.wb-sidebar-panel \{[^}]*overflow-y: auto", block)
    assert re.search(r"\.wb-sidebar \.wb-side-section,[^}]*flex: none;", block)


def test_the_boards_filter_row_has_a_phone_gap_that_fits_three_chips():
    text = (CSS / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    match = re.search(
        r"@media \(max-width: 599\.98px\) \{\s*#library-boards-filter \{\s*gap: var\(--space-1\);", text
    )
    assert match, "the boards filter row lost its phone gap (311 of 308 at 360)"


def test_the_library_menu_is_not_forced_back_under_its_button():
    js = frontend_text("whiteboard-library.js")
    assert "got.top < r.top ? r.top - 4 - got.bottom : r.bottom + 4 - got.top" in js
