"""Dogfood round 1 (2026-10-25) whiteboard and mind map fixes, fixer B.

Source-level checks the suite can see; the browser numbers are in the
commit messages and `docs/roadmap/agent-remaining/fixb-1025.md`.
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
    assert "While typing a name, Ctrl+Enter adds the sibling." in WB


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "".join(_function(n) for n in ("wbShapeDims", "wbEllipseDrawD"))
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
    left, top, w, h, rx = _bbox(_node("wbEllipseDrawD(100, 100, 200, 160, false)"))
    assert (left, top, w, h) == (100, 100, 100, 60) and rx == 50


def test_ellipse_dragged_up_left_stays_in_the_dragged_box():
    left, top, w, h, _ = _bbox(_node("wbEllipseDrawD(200, 160, 100, 100, false)"))
    assert (left, top, w, h) == (100, 100, 100, 60)


def test_ellipse_with_shift_is_a_circle_away_from_the_press():
    left, top, w, h, _ = _bbox(_node("wbEllipseDrawD(200, 160, 100, 100, true)"))
    assert (left, top, w, h) == (100, 60, 100, 100)


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


def test_only_the_arrow_tool_binds_and_pen_strokes_are_never_targets():
    assert 'window.currentTool === "arrow" ? wbBoundArrowData(' in WB
    assert "!wbSketchIsClosedShape(item)) continue" in _function("wbArrowCandidateAt")


def test_bottom_dock_wraps_between_600_and_819_instead_of_scrolling():
    # 927px of tools in a 683px dock left Undo past the window edge (item 11).
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
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
