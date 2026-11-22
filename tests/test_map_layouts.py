"""XMind's structures beyond the tree, as map layouts (MINDMAP_PLAN 15, row 6).

The logic chart, the timeline, the fishbone and the tree table are layout
rows: the picker offers them, the palette names them in the picker's words,
and the server stores them. `scratchpad/ui-sweeps/maplayouts.js` lays each out
at 12 and 200 topics and counts overlapping boxes.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import re
from pathlib import Path

from tessellate.api.routes_whiteboard import BOARD_LAYOUTS

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
MAP_JS = frontend_text("whiteboard-map.js")
NEW = ("logic-right", "timeline", "fishbone", "tree-table")


def _picker() -> list[tuple[str, str]]:
    body = INDEX[INDEX.index('<select id="wb-map-layout"') :]
    body = body[: body.index("</select>")]
    #: An option may carry its icon (`data-icon`) since the picker became an icon menu.
    return re.findall(r'<option value="([a-z-]+)"[^>]*>([^<]+)</option>', body)


def _names() -> list[tuple[str, str]]:
    body = MAP_JS[MAP_JS.index("const WB_MAP_LAYOUT_NAMES") :]
    body = body[: body.index("]);")]
    return re.findall(r'\["([a-z-]+)", "([^"]+)"\]', body)


def test_the_picker_and_the_palette_name_the_same_layouts_in_the_same_words():
    assert _picker() == _names()
    assert {value for value, _ in _picker()} == BOARD_LAYOUTS


def test_the_four_structures_are_offered_and_stored(client):
    assert set(NEW) <= BOARD_LAYOUTS
    for layout in NEW:
        board = client.post(
            "/whiteboard/boards", json={"name": f"Map {layout}", "type": "map", "layout": layout}
        ).json()
        assert (board["type"], board["layout"]) == ("map", layout)
        listed = {b["id"]: b for b in client.get("/whiteboard/boards").json()}
        assert listed[board["id"]]["layout"] == layout


def test_a_column_layout_tidies_the_whole_map_on_an_add():
    """A new topic in one column moves the columns beside it, so the add's
    branch tidy is the whole map there."""
    scope = MAP_JS[MAP_JS.index("function wbMapTidyBranchScope(parentId) {") :][:200]
    assert "WB_MAP_COLUMN_LAYOUTS.has(wbMapLayout())" in scope
