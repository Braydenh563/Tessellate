"""Sh1 P32: a Settings pane's title that the phone's jump list repeats is hidden
by the visually-hidden recipe, never `display: none`.

`.jump-echo` (phone-shell.js `echoSettingsPaneTitle`) drops the pane's first h3
because the jump list above it already says the name. `display: none` also took
the heading out of the accessibility tree, so on a phone Memory, Logs and every
other pane whose h3 matches the jump list had no heading for a screen reader's
heading navigation. The recipe is `.visually-hidden` (04-chat-dock-appearance.css):
clipped, 1px, still named. The dock that held only that title goes the same way.

The tour's "455px spill" at 390 was measured too (scratchpad probe, whole tour,
every descendant of the card and the lit target): the one step that reports it is
"One place for everything", whose lit target is `#library-subtabs`, a nine-tab
row that scrolls sideways (scrollWidth 826 in a 364px box, `overflow-x: auto`,
the page itself 390 wide). Scrolled content, not a spill; the test pins that the
row is a scroller so nobody "fixes" it by wrapping.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR

LAZY = "settings-controls-lazy.css"


def _text(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS_DIR / name).read_text(encoding="utf-8"), flags=re.S)


def _rule(text: str, selector_start: str) -> str:
    at = text.index(selector_start)
    return text[text.index("{", at) + 1 : text.index("}", at)]


def _all_css() -> str:
    return "".join(_text(p.name) for p in sorted(CSS_DIR.glob("*.css")))


def test_the_echoed_title_is_clipped_not_removed_from_the_tree():
    css = _text(LAZY)
    body = _rule(css, "#settings-modal h3.jump-echo {")
    assert "display: none" not in body and "display:none" not in body
    for needle in ("position: absolute", "inline-size: 1px", "block-size: 1px", "overflow: hidden", "clip-path: inset(50%)"):
        assert needle in body, needle


def test_the_boot_sheet_no_longer_hides_it_with_display_none():
    boot = _text("07-whiteboard-misc.css")
    assert "h3.jump-echo" not in boot, "the rule moved to the Settings sheet, which loads with the pane"


def test_the_title_rule_is_a_phone_rule():
    css = _text(LAZY)
    at = css.index("#settings-modal h3.jump-echo {")
    head = css[:at]
    last_media = head.rindex("@media")
    assert "(max-width: 819.98px)" in head[last_media:]
    assert head[last_media:].count("{") - head[last_media:].count("}") == 1, "still inside that media block"


def test_a_dock_left_with_only_the_title_is_clipped_too_and_keeps_the_heading():
    css = _text(LAZY)
    body = _rule(css, "#settings-modal .settings-section > .dock:has(> .dock-identity > h3.jump-echo:only-child):not(")
    assert "display: none" not in body
    for needle in ("position: absolute", "inline-size: 1px", "block-size: 1px", "overflow: hidden", "clip-path: inset(50%)", "border: 0"):
        assert needle in body, needle


def test_the_library_tab_row_the_tour_lights_is_a_scroller_not_a_spill():
    css = _all_css()
    assert "overflow-x: auto" in _rule(css, ".notes-subtabs,\n.library-subtabs {")
    assert "flex-wrap: nowrap" in _rule(css, ".tabs-line {")
