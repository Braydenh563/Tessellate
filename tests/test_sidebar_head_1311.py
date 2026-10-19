"""INBOX 1311: the Notes sidebar's collapse toggle scrolled away with the
category list and sat 8px above the head's row (measured at 1440x900: toggle
y9, heading y17; scrolled 200px, toggle y-191). Now it is first in flow and
sticky: y17 level with the heading, scrolled or not (scratchpad side2.js)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")


def test_the_notes_toggle_is_first_in_flow():
    assert 'if (aside.id === "sidebar") aside.prepend(collapseBtn);' in JS


def test_it_sticks_level_with_the_sticky_head():
    rule = CSS[CSS.index("#sidebar:not(.sidebar-collapsed) > .sidebar-collapse-toggle {") :].split("}")[0]
    assert "position: sticky;" in rule and "top: 0;" in rule
    #: Sibling margins collapse to the most negative, so this carries the head's pull-up.
    assert "calc(-1 * (var(--sidebar-toggle-size) + var(--card-pad-y)))" in rule
    head = CSS[CSS.index("  #sidebar > .sidebar-head {\n    position: sticky;") :].split("}")[0]
    assert "margin-top: calc(-1 * var(--card-pad-y));" in head
