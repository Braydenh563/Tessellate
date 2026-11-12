"""Wrap and zoom sweep of the mind map and the Dashboard (owner, 2026-11-11):
the rules that fixed what the sweep measured, pinned so a later rewrite of the
Widgets dialog, the quick-link tile or the board sidebar cannot quietly bring a
wrap, an overlap or an unreachable row back. They were the last section of
10-responsive.css until UI plan 13b (decision 19) moved each beside its
component, so they are found by selector and media query, not by section."""

import re
from pathlib import Path

from tests._css_paths import FORMER_10, sheets

ROOT = Path(__file__).resolve().parent.parent
CSS = sheets(*FORMER_10)
CLEAN = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def body(selector: str, text: str = CLEAN) -> str:
    """The last rule, in load order, whose selector is exactly `selector`: the one that wins."""
    found = re.findall(r"(?:^|(?<=[{}]))\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", text)
    assert found, f"no rule for {selector!r}"
    return found[-1]


def in_query(query: str, selector: str):
    """The last rule for `selector` inside a block whose prelude is exactly `query`, or None."""
    blocks = re.findall(re.escape(query) + r"\s*\{\n(.*?)\n\}\n", CLEAN, flags=re.S)
    found = [b for block in blocks for b in re.findall(r"(?:^|(?<=[{}]))\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", block)]
    return found[-1] if found else None


def test_widgets_dialog_rows_drop_their_controls_under_the_text():
    row = body(".dash-widget-row")
    assert "flex-wrap: wrap" in row and "row-gap: var(--space-2)" in row
    assert "flex: 1 1 10rem" in body(".dash-widget-row-main")
    assert "margin-inline-start: auto" in body(".dash-widget-row-controls")


def test_quick_edit_tile_leaves_room_for_the_touch_sized_menu_button():
    rule = body(".quick-edit-tile > .quick-link")
    assert "var(--target-min)" in rule and "var(--space-9)" in rule


def test_glance_label_is_two_lines_at_most_on_a_phone():
    phone = in_query("@media (max-width: 599.98px)", ".dash-glance .quick-link-label")
    assert phone, "the glance label clamp is not in the phone media query"
    assert "-webkit-line-clamp: 2" in phone


def test_map_tab_of_the_board_sidebar_scrolls_inside_the_sheet():
    rule = body('.wb-side-section[data-side-panel="map"]')
    assert "overflow-y: auto" in rule
    assert "padding-block: var(--ring-room)" in rule


def test_boards_list_count_title_gets_two_lines_on_a_phone():
    phone = in_query("@media (max-width: 599.98px)", '.dock[data-dock-name="library-boards"] .dock-identity > h2')
    assert phone, "the boards list title rule is not in the phone media query"
    assert "-webkit-line-clamp: 2" in phone and "white-space: normal" in phone


def test_reminder_sheet_form_keeps_ring_room_inside_its_scroll_box():
    whole = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    rule = body(".reminder-compose-card > #reminder-compose", whole)
    assert "padding: var(--ring-room)" in rule
    assert "margin: calc(-1 * var(--ring-room))" in rule


def test_outline_row_is_as_tall_as_its_pencil_in_every_band():
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    lazy = re.sub(r"/\*.*?\*/", "", lazy, flags=re.S)
    rule = body("#wb-outline-tree .wb-outline-text", lazy)
    assert "min-height: var(--target-min)" in rule
    assert "min-height: 44px" not in lazy[lazy.index("#wb-outline-tree .wb-outline-edit") :]


def test_last_reminder_scrolls_clear_of_the_floating_new_button():
    rule = in_query("@media (max-width: 599.98px)", "#tab-reminders:has(> .dock-fab)")
    assert rule, "the Reminders page foot rule is not in the phone media query"
    assert "padding-bottom: calc(var(--target-min) + var(--space-5) + var(--space-3))" in rule


def test_map_dock_slides_off_the_zoom_pill_only_as_far_as_it_needs():
    band = in_query("@media (min-width: 820px)", '.whiteboard-floating-panel.bottom-center:not([data-dock="side"])')
    assert band, "the dock's slide is not in the 820 and up band"
    rule = re.sub(r"\s+", " ", band)
    slide = "clamp(0px, calc(2 * (var(--wb-w-zoom) + 1.5rem) + 53rem - 100%), calc(var(--wb-w-zoom) + 1.5rem))"
    assert f"right: {slide}" in rule
    # The old symmetric cap stays, plus what the dock slid: a longer row wraps, never goes under the pill.
    assert f"max-width: calc( 100% + {slide} - 2 * (var(--wb-w-zoom) + 1.5rem) )" in rule
