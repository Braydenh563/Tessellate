"""Making the mind map's node fill and canvas background colours findable
(coordinator ask): the owner asked for these without knowing they already
exist (`#wb-map-strip-color`, `#wb-bg-color-picker`, both wired and both
already used by PNG/SVG export, `tests/test_export_paint.py`). Nothing that
opens by right-click ever named the colour well, so this adds the one thing
that was actually missing: a words door to it, plus a mention of both wells
in the map's own "Where the map's controls live" help.

No new colour control: both changes point at the picker that was already
there.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHITEBOARD_JS = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _context_menu_body() -> str:
    start = WHITEBOARD_JS.index("function wbBuildContextMenu(kind) {")
    end = WHITEBOARD_JS.index("\n}\n", start)
    return WHITEBOARD_JS[start:end]


def test_the_map_node_menu_has_a_colour_row() -> None:
    body = _context_menu_body()
    assert '"Topic colour…"' in body or "Topic colour…" in body
    assert '"Branch colour…"' in body or "Branch colour…" in body


def test_the_colour_row_opens_the_existing_well_not_a_new_one() -> None:
    body = _context_menu_body()
    row_at = body.index("Topic colour")
    row = body[row_at : row_at + 500]
    assert 'getElementById("wb-map-strip-color")' in row
    # Intent moved (INBOX 1685, 88274b7): the well's click opens the app's own colour popover, so the row
    # clicks it and never asks for the browser's native picker.
    assert "showPicker" not in row
    assert ".click()" in row


def test_no_second_colour_input_was_added() -> None:
    """The fix is a menu row, not a second `<input type=\"color\">`: only the
    strip's own well and the board-background well may exist."""
    ids = re.findall(r'<input type="color" id="([\w-]+)"', INDEX_HTML)
    assert sorted(set(ids)) == sorted(ids), "a duplicated id would hide as a set collapsing a list"
    assert ids.count("wb-map-strip-color") == 1


def test_canvas_background_picker_has_a_clear_tooltip_naming_export() -> None:
    """Renamed from "Board background colour": the same well sits in a mind
    map's own View menu, where "Board" read as if it did not apply."""
    match = re.search(r'<input type="color" id="wb-bg-color-picker"[^>]*>', INDEX_HTML)
    assert match, "wb-bg-color-picker is gone from index.html"
    tag = match.group(0)
    assert 'aria-label="Canvas background colour"' in tag
    assert "export" in tag.lower()
    assert "Board background colour" not in tag


def test_the_maps_own_help_mentions_both_wells() -> None:
    start = INDEX_HTML.index('id="wb-map-places-help"')
    end = INDEX_HTML.index("</div>", start)
    #: Markup wraps this prose across lines for readability; a browser
    #: collapses that to single spaces when it renders the text, so the
    #: check does the same rather than tripping on where the source happens
    #: to break a line.
    help_text = re.sub(r"\s+", " ", INDEX_HTML[start:end])
    assert "Topic colour" in help_text
    assert "background colour" in help_text
    assert "export" in help_text.lower()


def test_palette_names_the_fill_and_background_wells() -> None:
    """INBOX 431(b): a search for fill, colour or background found neither
    well; each now has a palette row that clicks the existing control."""
    js = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    start = js.index("function mapPaletteCommands() {")
    body = js[start : js.index("\n}\n", start)]
    fill = body[body.index("Topic fill colour") - 120 : body.index("Topic fill colour") + 300]
    assert 'getElementById("wb-map-strip-color")' in fill and "color" in fill
    bg = body[body.index("Map background colour") - 120 : body.index("Map background colour") + 300]
    assert 'getElementById("wb-bg-color-picker")' in bg and "fill" in bg
