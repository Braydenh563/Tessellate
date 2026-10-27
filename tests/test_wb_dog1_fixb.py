"""Dogfood round 1 (2026-10-25) whiteboard and mind map fixes, fixer B.

Source-level checks the suite can see; the browser numbers are in the
commit messages and `docs/roadmap/archive/agent-remaining/fixb-1025.md`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def test_new_map_toast_says_what_enter_does_while_typing():
    # Enter in a topic's editor is a line break (the owner, 2026-10-10), so the
    # creation toast must name the key that adds a sibling while typing.
    # dog2 item 12: the canvas keys first, then plainly what Enter does while
    # typing (Ctrl+Enter on a selected topic inserts a parent, so it is named
    # only for the editor).
    assert "Tab adds a branch, Enter one beside it. While you type a name, Enter is a new line and Ctrl+Enter adds the one beside it." in WB
    assert "Enter a sibling." not in WB


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "".join(_function(n) for n in ("wbDragBox", "wbEllipseDrawD"))
        + f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(
        subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    )


def _bbox(d: str):
    # M left top+ry, then two arcs of width w: the box is left..left+w, top..top+2ry.
    parts = d.replace("a", " a ").split()
    left, mid = float(parts[1]), float(parts[2])
    rx, ry, w = float(parts[4]), float(parts[5]), float(parts[9])
    return left, mid - ry, w, 2 * ry, rx


def test_ellipse_is_drawn_corner_to_corner_like_the_rectangle():
    # Press at (100, 100), drag to (200, 160): the rectangle's box is x 100..200,
    # y 100..160, and the ellipse must fill the same box (it used to centre on
    # the press and reach 200 wide, 120 tall, 100 left and 40 above it).
    left, top, w, h, rx = _bbox(_node("wbEllipseDrawD(100, 100, 200, 160)"))
    assert (left, top, w, h) == (100, 100, 100, 60) and rx == 50


def test_ellipse_dragged_up_left_stays_in_the_dragged_box():
    left, top, w, h, _ = _bbox(_node("wbEllipseDrawD(200, 160, 100, 100)"))
    assert (left, top, w, h) == (100, 100, 100, 60)


def test_ellipse_with_shift_is_a_circle_away_from_the_press():
    left, top, w, h, _ = _bbox(_node("wbEllipseDrawD(200, 160, 100, 100, { shiftKey: true })"))
    assert (left, top, w, h) == (100, 60, 100, 100)


def test_alt_draws_the_ellipse_from_its_centre():
    """INBOX 1352 gap 2: the default stays corner to corner; Alt is the centre."""
    left, top, w, h, _ = _bbox(_node("wbEllipseDrawD(200, 160, 260, 190, { altKey: true })"))
    assert (left, top, w, h) == (140, 130, 120, 60)


def test_a_shift_square_dragged_up_and_left_ends_at_the_pointer():
    """INBOX 1352 gap 1: it straddled the press (x -60 of a 120 square)."""
    assert _node("wbDragBox(100, 100, 40, 80, { shiftKey: true })") == {"x": 40, "y": 40, "w": 60, "h": 60}


def test_draw_out_snap_has_no_centred_mode():
    assert "centred = false" not in _function("wbDrawOutSnap").split("{")[0]


def _bound(expr: str, hits: dict):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    stubs = (
        f"const HITS = {json.dumps(hits)};"
        "function wbArrowCandidateAt(x, y) { const h = HITS[x > 300 ? 'to' : 'from']; return h ? [h.kind, { id: h.id }] : null; }"
        "function wbNearestAnchor() { return { x: 1, y: 0.5 }; }"
    )
    script = stubs + _function("wbBoundArrowData") + f"console.log(JSON.stringify({expr}));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


BLOB = "{ color: '#123456', width: 3, endCap: 'arrow', startCap: 'none', dash: 'dashed' }"


def test_arrow_ending_on_two_shapes_becomes_a_bound_connector():
    data = _bound(
        f"wbBoundArrowData(100, 100, 400, 100, 10, {BLOB})",
        {"from": {"kind": "sketch", "id": 1}, "to": {"kind": "node", "id": 2}},
    )
    assert data["type"] == "link-straight"
    assert (data["sourceId"], data["sourceKind"]) == (1, "sketch")
    assert data["targetId"] == 2 and "targetKind" not in data
    assert data["endCap"] == "arrow" and data["dash"] == "dashed" and data["color"] == "#123456"


def test_arrow_with_one_free_end_keeps_that_end_as_a_point():
    data = _bound(
        f"wbBoundArrowData(100, 100, 400.4, 100, 10, {BLOB})", {"from": {"kind": "sketch", "id": 1}}
    )
    assert data["sourceId"] == 1 and data["targetPoint"] == {"x": 400, "y": 100}


def test_arrow_on_empty_board_or_within_one_shape_stays_free():
    assert _bound(f"wbBoundArrowData(100, 100, 400, 100, 10, {BLOB})", {}) is None
    same = {"from": {"kind": "sketch", "id": 1}, "to": {"kind": "sketch", "id": 1}}
    assert _bound(f"wbBoundArrowData(100, 100, 400, 100, 10, {BLOB})", same) is None


def test_only_the_arrow_and_line_tools_bind_and_pen_strokes_are_never_targets():
    # The Line tool binds as well since wb2 (2026-10-25): a line between two
    # shapes stayed a loose path that did not follow them.
    assert 'window.currentTool === "arrow" || window.currentTool === "line" ? wbBoundArrowData(' in WB
    assert "!wbSketchIsClosedShape(item)) continue" in _function("wbArrowCandidateAt")


def test_bottom_dock_wraps_between_600_and_819_instead_of_scrolling():
    # 927px of tools in a 683px dock left Undo past the window edge (item 11).
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    start = css.index(
        "@media (min-width: 600px) and (max-width: 819.98px) {\n  .whiteboard-floating-panel.bottom-center:not"
    )
    band = css[start : css.index("\n}\n", css.index(".wb-tool-group {", start)) + 3]
    assert "flex-wrap: wrap;" in band and "overflow: visible;" in band
    assert "min-width: 0;" in band, "the group must be allowed to shrink or it never wraps"


def test_toast_box_clears_the_bottom_dock():
    # Item 22: the toast box's bottom follows the dock's top, and is given back
    # (empty string) when the dock is hidden, at the side, or the window a phone's.
    body = WB[WB.index("const liftToasts = () => {") :]
    body = body[: body.index("    };")]
    assert "toastBox.style.bottom = low ?" in body and ': ""' in body
    assert 'dataset.dock !== "side"' in body and "innerWidth >= 600" in body


def test_a_connection_point_lights_and_grabs_at_the_same_distance():
    # Pressing 9px from a point drew an arrow while the dot lit at 10, so most
    # of a shape's outline was a connector handle. One constant for both.
    assert "const WB_PORT_HIT_PX = 6;" in WB
    assert WB.count("WB_PORT_HIT_PX / zoomK()") == 1
    assert "Math.min(WB_PORT_HIT_PX, side * 0.2) / zoomK()" in WB
    assert "Math.min(9, side * 0.2)" not in WB


MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")


def test_a_new_topic_is_brought_into_view_when_it_is_out_of_it():
    # Item 12: Tab put a child at x~1265 and the view stayed.
    add = MAP[MAP.index("async function wbMapAddChild(") :]
    add = add[: add.index("\n}\n")]
    assert "wbMapRevealTopic(created);" in add
    # The arrow keys use the same helper, not a second copy of the rule.
    nav = MAP[MAP.index("function wbMapNavigate(") :]
    assert "wbMapRevealTopic(target);" in nav[: nav.index("\n}\n")]


def test_rect_escape_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = MAP.index("function wbRectEscapes(")
    fn = MAP[start : MAP.index("\n}\n", start) + 3]
    view = "{ left: 60, top: 100, right: 1260, bottom: 700 }"
    script = fn + (
        f"console.log(JSON.stringify([wbRectEscapes({{ left: 100, top: 200, right: 300, bottom: 240 }}, {view}),"
        f" wbRectEscapes({{ left: 1119, top: 200, right: 1319, bottom: 240 }}, {view}),"
        f" wbRectEscapes({{ left: 100, top: 59, right: 300, bottom: 103 }}, {view})]));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [False, True, True]
