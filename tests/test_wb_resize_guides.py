"""Guides on a resize and on a box drawn out; Show more and Show less only
when they change something (WHITEBOARD_PLAN, INBOX 825 and 826's E4).

The pure parts run in node; the browser half is measured with Playwright
(the wbs-1011 ledger names the numbers).
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _resize(boxes, box, edges, **opts):
    return _node(
        "const WB_ALIGN_SNAP_PX = 6;\n"
        f"const BOXES = {json.dumps(boxes)};\n"
        "function wbGuideBoxes() { return BOXES; }\n"
        + _function("wbResizeGuides")
        + f"console.log(JSON.stringify(wbResizeGuides(null, {json.dumps(box)}, {json.dumps(edges)}, {json.dumps(opts)})));"
    )


def _b(x, y, w=100, h=60):
    return {"minX": x, "minY": y, "maxX": x + w, "maxY": y + h}


def test_a_right_edge_snaps_to_a_neighbours_edge_with_a_guide() -> None:
    out = _resize([_b(0, 200, 204, 60)], {"x": 0, "y": 0, "w": 200, "h": 80}, "e")
    assert out["w"] == 204 and out["x"] == 0
    assert any(g["kind"] == "edge" and g["x1"] == 204 == g["x2"] for g in out["guideLines"])


def test_a_left_edge_moves_x_and_keeps_the_right_edge() -> None:
    out = _resize([_b(53, 300)], {"x": 50, "y": 0, "w": 150, "h": 80}, "w")
    assert out["x"] == 53 and out["x"] + out["w"] == 200


def test_a_height_matches_a_neighbours_height() -> None:
    # The neighbour is 120 tall and far off to the side; a bottom edge dragged
    # to 117 tall takes 120, and both measures are marked.
    out = _resize([_b(900, 900, 100, 120)], {"x": 0, "y": 0, "w": 100, "h": 117}, "s")
    assert out["h"] == 120
    assert sum(1 for g in out["guideLines"] if g["kind"] == "spacing") == 2


def test_the_text_height_is_a_snap_for_the_bottom_edge() -> None:
    out = _resize([], {"x": 0, "y": 0, "w": 100, "h": 143}, "s", fit=140)
    assert out["h"] == 140


def test_the_grid_only_when_nothing_else_is_near() -> None:
    assert _resize([], {"x": 0, "y": 0, "w": 50, "h": 50}, "se", grid=24)["w"] == 48
    out = _resize([_b(0, 300, 51, 20)], {"x": 0, "y": 0, "w": 50, "h": 50}, "e", grid=24)
    assert out["w"] == 51


def test_nothing_near_is_no_snap() -> None:
    out = _resize([_b(500, 500)], {"x": 0, "y": 0, "w": 230, "h": 170}, "se")
    assert (out["w"], out["h"]) == (230, 170) and out["guideLines"] == []


def test_resizes_and_drawing_out_go_through_the_guides() -> None:
    assert SOURCE.count("wbGuidedResize(\"node\"") == 1 and SOURCE.count("wbGuidedResize(\"object\"") == 1
    # Shapes, and the text, sticky and frame boxes, both snap their corner.
    assert SOURCE.count("wbDrawOutSnap(") >= 4
    assert "wbShowSizeReadout(snapped)" in SOURCE


def _more(**kw):
    return _node(_function("wbCardMoreNeeded") + f"console.log(JSON.stringify(wbCardMoreNeeded({json.dumps(kw)})));")


def test_show_less_only_when_collapsing_would_hide_text() -> None:
    # An expanded card sized by hand to 300 that stands 300: nothing to hide.
    assert _more(clamped=False, scrollH=200, clientH=200, cardH=300, floorH=300, capH=0) is False
    # Taller than its stored height: collapsing hides the rest.
    assert _more(clamped=False, scrollH=400, clientH=400, cardH=420, floorH=300, capH=0) is True
    # No stored height: the eight-line cap decides.
    assert _more(clamped=False, scrollH=100, clientH=100, cardH=120, floorH=0, capH=180) is False
    assert _more(clamped=False, scrollH=260, clientH=260, cardH=280, floorH=0, capH=180) is True
    # Collapsed: Show more only when the text overflows.
    assert _more(clamped=True, scrollH=100, clientH=100, cardH=0, floorH=0, capH=0) is False
    assert _more(clamped=True, scrollH=180, clientH=100, cardH=0, floorH=0, capH=0) is True


def test_each_grip_says_what_its_double_click_does() -> None:
    script = _function("wbResizeHandleTitle") + "console.log(JSON.stringify(['frame','image','text','shape'].map(wbResizeHandleTitle)));"
    frame, image, text, shape = _node(script)
    assert "fit this edge" in frame and "fits the picture" in image and "fits the text" in text and text == shape


def test_a_shape_resize_moves_its_grips_and_shows_its_size_live() -> None:
    """The 22-10 bug doc: a shape's box and anchors stayed at the old size until
    release, and its resize showed no "W x H" (scratchpad/ui-sweeps/wb1025-resize.js
    measures both: selection box 164 to 284 wide against a 280 path)."""
    body = _function("wbDrawSketchHandles")
    drag = body[body.index('.attr("class", "wb-sketch-resize-handle")') :]
    assert "placeGrips(live)" in drag
    assert "wbShowSizeReadout(" in drag
    assert "wbClearAlignmentGuides()" in drag


def test_a_sticker_glyph_follows_its_box_during_the_resize() -> None:
    """A sticker's glyph is its box; it stayed 46px in a 214px box after release."""
    start = SOURCE.index("function resizeDrag(handle)")
    drag = SOURCE[start : SOURCE.index("function objectRotateDrag()", start)]
    assert "d.data?.sticker" in drag and "wbStickerSize(d)" in drag
    assert "wbScheduleRender()" in drag[drag.index('.on("end"') :]


# K19 / K17 / K16 (owner-1026b)

CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_only_the_moving_edges_measure_carries_a_badge_and_it_sits_outside_the_handle() -> None:
    out = _resize([_b(900, 900, 100, 120)], {"x": 0, "y": 0, "w": 100, "h": 117}, "s")
    marks = [g for g in out["guideLines"] if g["kind"] == "spacing"]
    assert len(marks) == 2
    assert sum(1 for g in marks if g.get("label") is False) == 1
    assert sum(1 for g in marks if g.get("out") is True) == 1


def test_the_badge_is_pushed_off_its_line_by_a_screen_distance() -> None:
    body = _function("wbShowAlignmentGuides")
    assert "line.label === false" in body
    assert "line.out" in body and "WB_BADGE_CLEAR_PX" in SOURCE


def test_a_picture_fills_its_box_without_stretching() -> None:
    i = CSS.index(".wb-object-image > img")
    block = CSS[i : CSS.index("}", i)]
    for rule in ("width: 100%", "height: 100%", "object-fit: contain", "display: block"):
        assert rule in block


def test_fit_height_follows_the_natural_aspect_at_the_current_width() -> None:
    out = _node(
        "const WB_OBJECT_MIN_SIZE = 24;\n"
        + _function("wbImageFitHeight")
        + "console.log(JSON.stringify([wbImageFitHeight(3000, 2000, 300), wbImageFitHeight(0, 0, 300), wbImageFitHeight(1000, 10, 100)]));"
    )
    assert out == [200, 300, 24]


def test_double_clicking_a_picture_grip_fits_it_in_one_undo_step() -> None:
    assert "wbFitImage(" in SOURCE
    assert 'owner?.classList.contains("wb-object-image")) return;' not in SOURCE
    assert _function("wbFitImage").count("wbPushUndo(") == 1
    assert "double-click fits the picture" in _function("wbResizeHandleTitle")
    assert _function("wbFitToText").count("wbPushUndo(") >= 2
