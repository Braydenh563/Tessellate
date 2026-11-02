"""Audit 1028 board and mind map UI rows: U12, U14 to U17, U21 to U28, U30, B12."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
WB = (JS / "whiteboard.js").read_text(encoding="utf-8")
MISC = (CSS / "07-whiteboard-misc.css").read_text(encoding="utf-8")
# The boot stylesheets are at their gzip cap (tests/test_boot_budget.py): these rows' rules are lazy.
LAZY = (CSS / "library-lazy.css").read_text(encoding="utf-8")


def _block(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    return source[start : source.index(end_marker, start)]


# U12 ------------------------------------------------------------------------


def _tool_keys() -> dict[str, str]:
    """tool -> the key text the board's own key table binds it to."""
    keys = {}
    table = _block(WB, "const WB_TOOL_KEYS = {", "\n  };")
    for letter, tool in re.findall(r'^\s{4}(\w): "([\w-]+)",', table, re.M):
        keys.setdefault(tool, letter.upper())
    shifted = _block(WB, "const WB_TOOL_SHIFT_KEYS = {", "\n  };")
    for letter, tool in re.findall(r'^\s{4}(\w): "([\w-]+)",', shifted, re.M):
        keys[tool] = "Shift+" + letter.upper()
    keys["image"] = "I"  # WB_ACTION_KEYS: the picture button
    return keys


def test_every_insert_item_with_a_key_shows_that_key_and_none_shows_a_wrong_one():
    menu = _block(HTML, 'id="wb-insert-menu"', 'id="wb-edit-menu"')
    keys = _tool_keys()
    seen = {}
    for item in re.findall(r'<button[^>]*data-wb-insert="([\w-]+)"[^>]*>(.*?)</button>', menu, re.S):
        tool, body = item
        hint = re.search(r"<kbd>(.*?)</kbd>", body)
        seen[tool] = hint.group(1) if hint else None
        assert seen[tool] == keys.get(tool), f"{tool}: menu shows {seen[tool]!r}, keys say {keys.get(tool)!r}"
    # The three the audit named (U12): the sticky said "click", the picture and the connector said nothing.
    assert seen["sticky"] == "N" and seen["image"] == "I" and seen["link-curved"] == "Shift+C"


# U14 ------------------------------------------------------------------------


def test_delete_stands_apart_from_undo_and_redo_in_the_dock_but_not_in_the_side_grid():
    rule = _block(LAZY, '.wb-tool-section-row > [data-tool="delete"] {', "}")
    assert "margin-inline-end: var(--space-3)" in rule  # 2px gap + 8px = 10px, over the 8px the audit asks
    side = _block(LAZY, '[data-dock="side"] .wb-tool-section-row > [data-tool="delete"] {', "}")
    assert "margin-inline-end: 0" in side  # the side dock is a four-cell grid that spaces its own cells


# U24 ------------------------------------------------------------------------

MAP = (JS / "whiteboard-map.js").read_text(encoding="utf-8")


def test_a_topic_inside_the_slide_margin_of_the_edge_is_revealed_not_left_there():
    start = MAP.index("function wbMapRevealTopic(")
    reveal = MAP[start : MAP.index("\n}\n", start)]
    # One margin, declared once, used for both the "is it at the edge" test and the slide to it.
    assert reveal.count("const m = 24;") == 1
    assert reveal.index("const m = 24;") < reveal.index("wbRectEscapes(el.getBoundingClientRect(), inset)")
    assert "right: free.right - m" in reveal and "left: free.left + m" in reveal
    assert "wbRectEscapes(el.getBoundingClientRect(), free)" not in reveal
