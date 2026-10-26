"""K9 and K10 (docs/roadmap/agent-remaining/owner-1026b.md): pins are layout.

Reset to defaults lets go of pinned notes and its toast's Undo puts them back;
a Shift-drag on empty map is a rectangle, not a freehand loop (a straight drag
caught nothing); the selection bar pins and unpins; Unpin all is in the graph's
more menu as well as the Physics fold, and undoable. Static checks; the
browser run that measured them is recorded in CHANGELOG (graph K6 to K10).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
GRAPH = (JS / "graph.js").read_text(encoding="utf-8")
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")


def _body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_reset_releases_pins_and_undo_restores_them():
    body = _body(GRAPH, "graphResetToDefaults")
    assert "graphPinnedRows()" in body and "graphUnpinAllNow" in body
    assert "graphRestorePins(released)" in body  # the server's list: off-screen and document pins too
    assert "already on its default settings" in body and "!pins.length" in body


def test_unpin_all_is_in_the_more_menu_and_undoable():
    menu = re.search(r'id="graph-more-menu".*?</details>', HTML, re.S).group(0)
    assert 'id="graph-unpin-all-menu"' in menu and "doc-dock-menu-item" in menu
    assert '"graph-unpin-all-menu"' in GRAPH and "graphRestorePins(rows)" in GRAPH


def test_the_selection_bar_pins_and_unpins():
    bar = re.search(r'id="graph-selection-dock".*?</div>', HTML, re.S).group(0)
    assert 'id="graph-selection-pin"' in bar and 'id="graph-selection-unpin"' in bar
    assert "gcPinSelection(s, true)" in CANVAS and "gcPinSelection(s, false)" in CANVAS


def test_shift_drag_on_empty_map_is_a_rectangle():
    wire = _body(CANVAS, "gcWireLasso")
    assert "box: true" in wire and "gcBoxPoints" in wire
