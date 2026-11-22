"""A frame's margins are alignment targets (INBOX 1563).

The owner, 2026-11-03: "in these frames, I cant align objects with a margin
or like the header text or have nice spacing between them which I can easily
do with the alignment guides". Inside a frame the guides also snap to its
inner left, right, top and bottom margin lines and treat them as neighbours
for equal spacing. The pure parts run in node; the margins' distances are read
from the drawn frame (`wbGuideBoxes.insets`) and measured in Chromium.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
SOURCE = frontend_text("whiteboard.js")

FRAME = {"x": 0, "y": 0, "width": 480, "height": 320}
#: A panel's margins: the header text's left, a margin under the subtitle.
INS = {"left": 20, "right": 20, "top": 60, "bottom": 20}


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _static(name: str) -> str:
    start = SOURCE.index(f"wbGuideBoxes.{name} = ")
    return SOURCE[start : SOURCE.index("\n};\n", start) + 4]


def _run(call: str, boxes=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const WB_ALIGN_SNAP_PX = 6;\n"
        f"const BOXES = {json.dumps(boxes or [])};\n"
        "function wbGuideBoxes(excludeKeys, at = null) { return wbGuideBoxes.within(BOXES, at); }\n"
        + _static("within")
        + _static("walls")
        + _function("wbAlignmentGuides")
        + _function("wbSpacingSeries")
        + _function("wbResizeGuides")
        + f"console.log(JSON.stringify({call}));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _walls(frame=FRAME, ins=INS):
    return _run(f"wbGuideBoxes.walls({json.dumps(frame)}, {json.dumps(ins)})")


def _box(x, y, w=100, h=60):
    return {"minX": x, "minY": y, "maxX": x + w, "maxY": y + h}


def _drag(boxes, x, y, w=100, h=60):
    return _run(f"wbAlignmentGuides(null, {x}, {y}, {w}, {h})", boxes)


def test_the_four_margin_lines_sit_at_the_insets() -> None:
    walls = {w["only"]: w for w in _walls()}
    assert (walls["left"]["minX"], walls["left"]["maxX"]) == (20, 20)
    assert (walls["right"]["minX"], walls["right"]["maxX"]) == (460, 460)
    assert (walls["top"]["minY"], walls["top"]["maxY"]) == (60, 60)
    assert (walls["bottom"]["minY"], walls["bottom"]["maxY"]) == (300, 300)
    assert all(w["wall"] == {"minX": 0, "minY": 0, "maxX": 480, "maxY": 320} for w in walls.values())


def test_a_frame_with_no_room_inside_has_no_margins() -> None:
    assert _walls(ins={"left": 300, "right": 300, "top": 10, "bottom": 10}) == []
    assert _run("wbGuideBoxes.walls({x: 0, y: 0, width: 10, height: 10}, null)") == []


@pytest.mark.parametrize(
    ("x", "y", "axis", "delta", "at"),
    [
        (23, 100, "dx", -3, 20),  # left edge near the left margin
        (363, 100, "dx", -3, 460),  # right edge (463) near the right margin
        (100, 63, "dy", -3, 60),  # top edge under the header and subtitle
        (100, 243, "dy", -3, 300),  # bottom edge (303) near the bottom margin
    ],
)
def test_a_card_in_the_frame_lands_on_the_margin(x, y, axis, delta, at) -> None:
    out = _drag(_walls(), x, y)
    assert out[axis] == delta
    line = out["guideLines"][0]
    assert line["kind"] == "edge" and at in (line["x1"], line["y1"])


def test_a_margin_is_for_its_own_edge_only() -> None:
    # A frame at x=200: its left margin is at 220. A wide card whose centre
    # sits on 220, and a narrow one whose right edge is at 222, pass it
    # without snapping; only a left edge lands on it.
    frame = {"x": 200, "y": 0, "width": 480, "height": 320}
    walls = _walls(frame)
    assert _drag(walls, 100, 100, 240, 60)["dx"] == 0
    assert _drag(walls, 182, 100, 40, 60)["dx"] == 0
    assert _drag(walls, 223, 100)["dx"] == -3


def test_a_card_outside_the_frame_does_not_see_its_margins() -> None:
    assert _drag(_walls(), 23, 400)["dx"] == 0
    assert _drag(_walls(), 700, 100)["dx"] == 0


def test_the_margin_is_a_neighbour_for_equal_spacing() -> None:
    # Left margin at 20, a sibling at 180: the card centred between them keeps
    # 50 each side. At x=52 the gaps are 32 and 28; it moves 2 to make them equal.
    out = _drag(_walls() + [_box(180, 100)], 52, 100)
    assert out["dx"] == -2
    spacing = [g for g in out["guideLines"] if g["kind"] == "spacing"]
    assert len(spacing) == 2 and {(g["x1"], g["x2"]) for g in spacing} == {(20, 50), (150, 180)}


def test_the_margin_sets_the_rhythm_for_a_card_beside_a_sibling() -> None:
    # Margin 20, sibling 40..140 (gap 20): the next card keeps that gap from
    # the sibling, so x=163 lands on 160.
    out = _drag(_walls() + [_box(40, 100)], 163, 100)
    assert out["dx"] == -3


def test_a_resize_edge_lands_on_a_margin_but_not_on_its_centre_or_size() -> None:
    # The right edge (463) lands on the right margin (460).
    out = _run('wbResizeGuides(null, {x: 100, y: 100, w: 363, h: 80}, "e")', _walls())
    assert out["x"] + out["w"] == 460
    # A bottom edge at 180, the margins' centre line, does not snap to it.
    assert _run('wbResizeGuides(null, {x: 100, y: 100, w: 100, h: 80}, "s")', _walls())["h"] == 80


def test_the_gathering_adds_the_margins_of_every_visible_unrotated_frame() -> None:
    gather = _function("wbGuideBoxes")
    assert "frame.kind !== \"frame\"" in gather and "wbItemRotation(\"object\", frame)" in gather
    assert "wbGuideBoxes.walls(frame, wbGuideBoxes.insets(frame))" in gather
    insets = _static("insets")
    assert "var(--space-7)" in insets and "wb-frame-panel" in insets and ".wb-frame-hint:not([hidden])" in insets
