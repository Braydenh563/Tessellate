"""Edit image (WHITEBOARD_PLAN section 1): turn, flip and filters on a picture, kept as item style."""

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    fns = ""
    for name in ("wbPixel",):
        start = WB.index(f"function {name}(")
        fns += WB[start : WB.index("\n}\n", start) + 3]
    out = subprocess.run([node, "-e", fns + f"console.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_the_filter_lists_only_what_was_changed() -> None:
    assert _node("wbPixel({}, 1, 1).filter") == ""
    assert _node("wbPixel({grey: true, bright: 120, contrast: 100}, 1, 1).filter") == "grayscale(1) brightness(1.2)"
    assert _node("wbPixel({contrast: 80}, 1, 1).filter") == "contrast(0.8)"
    assert _node("wbPixel({bright: 'url(x)', contrast: 9999}, 1, 1).filter") == ""


def test_a_quarter_turn_swaps_the_local_box_and_a_plain_picture_has_no_transform() -> None:
    plain = _node("wbPixel({}, 200, 100)")
    assert (plain["w"], plain["h"], plain["turn"], plain["transform"], plain["svg"]) == (200, 100, 0, "", "")
    box = _node("wbPixel({turn: 90}, 200, 100)")
    assert (box["w"], box["h"], box["turn"]) == (100, 200, 90)
    assert "rotate(90deg)" in box["transform"]
    assert "scale(-1, 1)" in _node("wbPixel({flip_x: true}, 200, 100)")["transform"]
    assert _node("wbPixel({turn: 45}, 200, 100)")["turn"] == 0


def test_the_export_transform_turns_about_the_box_centre() -> None:
    assert _node("wbPixel({turn: 90}, 200, 100)")["svg"] == "translate(100 50) scale(1 1) rotate(90) translate(-50 -100)"


def test_the_panel_offers_edit_image_to_pictures_only() -> None:
    row = re.search(r"^  image: \[(.*)\],$", FMT, re.M).group(1)
    assert '"pixels"' in row
    for kind in ("shape", "text", "frame", "table"):
        assert '"pixels"' not in re.search(rf"^  {kind}: \[(.*)\],$", FMT, re.M).group(1)
    for ident in ("turn", "flipx", "flipy", "grey", "bright", "contrast", "pixreset"):
        assert f'id="wb-fmt-{ident}"' in HTML and f'"wb-fmt-{ident}"' in FMT
    assert 'data-fmt="pixels"' in HTML
    assert "wbPixel(obj.data" in WB

