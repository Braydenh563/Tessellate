"""Several topics picked on a mind map read as a map selection (INBOX 617).

The owner: "on the mind map when selecting a group of nodes, it defaults to
the whiteboard selection and popup menus and right click menus etc".
Measured by `scratchpad/ui-sweeps/bm1005-mapmulti.js` on the base: a marquee
round three topics drew the board's group box (10 handles), the bar showed
four arrange groups and order, the topics' own resize grips stayed out, and
the right-click menu had one map row. After: no group box, the bar's
`mapmulti` group only, Fold and Bold act on all three in one step, the menu
has the map rows. The sweep is the measurement; this pins the shape.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1] / "frontend"


def _body(file: str, name: str) -> str:
    text = frontend_text(file)
    start = re.search(rf"\n(?:async )?function {name}\(", text).start()
    nxt = re.search(r"\n(?:async )?function ", text[start + 10 :])
    return text[start : start + 10 + (nxt.start() if nxt else len(text))]


def test_the_bar_has_a_map_group_for_several_topics():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    group = html[html.index('data-wb-ctx="mapmulti"') :]
    group = group[: group.index("</div>")]
    for name in ("color", "bold", "task", "fold", "summary"):
        assert f'id="wb-mapmulti-{name}"' in group
    js = frontend_text("whiteboard.js")
    assert 'mapmulti: { bar: ["mapmulti"]' in js
    assert '"mapmulti"' in js[js.index("const WB_CONTEXT_GROUPS") :][:300]
    fill = _body("whiteboard.js", "wbFillContextBar")
    assert "wbMapMultiTopics()" in fill and "WB_CONTEXT_CONTROLS.mapmulti" in fill
    assert "wbWireMapMulti();" in _body("whiteboard.js", "initWhiteboard")


def test_no_group_box_and_no_topic_grips_for_a_map_selection():
    handles = _body("whiteboard.js", "wbRenderMultiSelectionHandles")
    assert "if (wbMapMultiTopics()) return;" in handles
    css = (ROOT / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert ".wb-map-node:is(:hover, .wb-selected):not(.wb-in-group) .wb-map-resize-grip" in css


def test_the_right_click_menu_offers_the_same_map_actions():
    menu = _body("whiteboard.js", "wbBuildContextMenu")
    assert "const mapTopics = wbMapMultiTopics();" in menu
    for action in ("fold", "bold", "task", "summary"):
        assert f"WB_MAP_MULTI_ACTIONS.{action}(" in menu
    # Arrange and Order are the board's; a map selection of topics has none.
    assert "if (!wbIsMap())" in menu


def test_one_undo_step_for_the_whole_selection():
    many = _body("whiteboard-map.js", "wbMapStyleMany")
    assert "wbPushDragUndo(entries)" in many
    # The selection is saved in one request since perf 1031 row 20.
    assert many.index("wbPushDragUndo(entries)") < many.index("await wbSaveMany(")
