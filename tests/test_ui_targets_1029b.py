"""Audit 1029 rank 46 (N11, X8, G13, G20, X22): targets under the floor.

Measured with `elementFromPoint` probes (the target a press reaches, not the
painted box) at 390 on a touch context and at 1440 on a mouse, on the 77-note
showcase notebook:

- a link pill's menu button was 21 by 21 with a mouse (under the 24 floor of
  WCAG 2.2 2.5.8) and 24 high on a finger;
- a link pill's chip was clipped to 19 high by its own `overflow: hidden`,
  which also cut off the hit overhang every interactive chip carries;
- "Show more" under a clamped note was 69 by 14 with a mouse;
- every `.search-field` input was 20 high inside a 32 high well (the press
  outside the line of text landed on the well);
- `.panel-grip` was 16 by 16 on every movable dialog (axe target-size);
- the graph's hit slop was 6 screen px for a finger too, a 19 to 23 px target
  on a phone.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend" / "css"
JS = ROOT / "frontend" / "js"


def _rule(text: str, selector: str) -> str:
    """The body of the rule whose selector list contains `selector`."""
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", text, flags=re.S)):
        if selector in [part.strip() for part in match.group(1).split(",")]:
            return match.group(2)
    raise AssertionError(f"no rule for {selector}")


def test_one_overhang_rule_serves_chips_the_link_menu_and_show_more():
    text = (CSS / "01-forms-settings.css").read_text(encoding="utf-8")
    for selector in (
        ".chip-interactive::after",
        ".entry-more::after",
        "#entry-list .menu-wrap > button::after",
    ):
        body = _rule(text, selector)
        assert "position: absolute" in body, selector
        assert "inset-block: min(0px, calc(50% - var(--target-min) / 2))" in body, selector
        assert "inset-inline: min(0px, calc(50% - var(--target-min) / 2))" in body, selector


def test_wrapped_link_pills_keep_a_fingers_room_apart():
    text = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    at = text.index("@media (pointer: coarse) {\n  #entry-list .entry-links {")
    assert "row-gap: calc(var(--target-min) - 1.5rem)" in text[at : at + 160]


def test_show_more_is_the_positioned_box_its_overhang_hangs_from():
    text = (CSS / "06-timeline-dialogs.css").read_text(encoding="utf-8")
    assert "position: relative" in _rule(text, ".entry-more")


def test_a_connection_chip_is_clipped_across_only():
    """Its words are cut with an ellipsis across; above and below stay open so
    the hit overhang is not cut with them (the entry meta's chips, FE-14)."""
    text = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    body = _rule(text, "#entry-list .link-connection > .chip.link")
    assert "overflow: clip visible" in body and "overflow: hidden" not in body
    assert "white-space: nowrap" in body


def test_a_search_field_input_fills_its_well():
    text = (CSS / "04-chat-dock-appearance.css").read_text(encoding="utf-8")
    assert "align-self: stretch" in _rule(text, ".search-field > .search-field-input")


def test_the_panel_grip_is_the_floor_not_a_space_step():
    text = (CSS / "panel-movable-lazy.css").read_text(encoding="utf-8")
    body = _rule(text, ".panel-movable-on > .panel-grip")
    assert "width: var(--target-min)" in body and "height: var(--target-min)" in body
    # Zero net height, shifted into the right padding so it does not cover a
    # foot's last button (the margin moved; the floor size it pins did not).
    assert "margin: calc(-1 * var(--target-min)) calc(-1 * var(--space-5)) 0 auto" in body
    assert "--space-6" not in body


def test_a_finger_gets_a_wider_graph_hit_slop():
    text = (JS / "graph-canvas.js").read_text(encoding="utf-8")
    assert re.search(r'const GC_SLOP_PX = window\.matchMedia\?\.\("\(pointer: coarse\)"\)\?\.matches \? \d+ : 6;', text)
    body = text[text.index("function gcNodeAtWorld(") :]
    body = body[: body.index("\n}\n")]
    assert "GC_SLOP_PX /" in body and "6 /" not in body
    # The reach is a finger's: a dot of the smallest radius still clears 44 px.
    reach = int(re.search(r"\? (\d+) : 6;", text).group(1))
    assert 2 * (reach + 2) >= 44


def test_the_graph_legend_is_one_tab_stop():
    text = (JS / "graph-canvas.js").read_text(encoding="utf-8")
    assert "function graphLegendRove(" in text
    body = text[text.index("function graphLegendRove(") :]
    body = body[: body.index("\n}\n")]
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert key in body, key
    assert 'tabIndex = ' in body
    assert 'graphLegendRove(document.getElementById("graph-legend"))' in text


def test_a_space_menu_row_and_its_actions_are_the_floor():
    """The switcher's rows were 33 high with the space's own button 20 high and
    its rename and delete 16 by 20 (audit 1029 X22, measured at 390)."""
    text = (CSS / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    main = re.findall(r"\n\.space-option-main \{([^}]*)\}", text)[-1]
    assert "align-self: stretch" in main and "min-height: var(--target-min)" in main
    actions = _rule(text, ".space-option-actions>button")
    assert "min-width: var(--target-min)" in actions and "min-height: var(--target-min)" in actions
    row = re.search(r"\n\.space-option \{([^}]*)\}", text).group(1)
    assert "padding: 0 var(--space-2) 0 var(--space-3)" in row
