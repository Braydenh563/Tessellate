"""Wrap and zoom sweep of the mind map and the Dashboard (owner, 2026-11-11):
the rules that fixed what the sweep measured, pinned in the one place they
live (the last section of 10-responsive.css) so a later rewrite of the Widgets
dialog, the quick-link tile or the board sidebar cannot quietly bring a wrap,
an overlap or an unreachable row back."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
SECTION = CSS[CSS.index("Wrap and zoom sweep of the mind map") :]
CLEAN = re.sub(r"/\*.*?\*/", "", SECTION, flags=re.S)


def body(selector: str, text: str = CLEAN) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert match, f"no rule for {selector!r} in the wrap and zoom sweep section"
    return match.group(1)


def test_widgets_dialog_rows_drop_their_controls_under_the_text():
    row = body(".dash-widget-row")
    assert "flex-wrap: wrap" in row and "row-gap: var(--space-2)" in row
    assert "flex: 1 1 10rem" in body(".dash-widget-row-main")
    assert "margin-inline-start: auto" in body(".dash-widget-row-controls")


def test_quick_edit_tile_leaves_room_for_the_touch_sized_menu_button():
    rule = body(".quick-edit-tile > .quick-link")
    assert "var(--target-min)" in rule and "var(--space-9)" in rule


def test_glance_label_is_two_lines_at_most_on_a_phone():
    phone = re.search(
        r"@media \(max-width: 599\.98px\)\s*\{\s*\.dash-glance \.quick-link-label\s*\{([^}]*)\}",
        CLEAN,
    )
    assert phone, "the glance label clamp is not in the phone media query"
    assert "-webkit-line-clamp: 2" in phone.group(1)


def test_map_tab_of_the_board_sidebar_scrolls_inside_the_sheet():
    rule = body('.wb-side-section[data-side-panel="map"]')
    assert "overflow-y: auto" in rule
    assert "padding-block: var(--ring-room)" in rule
