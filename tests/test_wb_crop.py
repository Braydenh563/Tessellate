"""Crop a picture to a shape (INBOX 1313, plan row 13): `data.crop` on an image
clips it on the board and in an export, set from the Format panel."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    table = WB[WB.index("const WB_CROPS") : WB.index("\n};\n", WB.index("const WB_CROPS")) + 4]
    fns = ""
    for name in ("wbCropClip", "wbCropPath"):
        start = WB.index(f"function {name}(")
        fns += WB[start : WB.index("\n}\n", start) + 3]
    out = subprocess.run([node, "-e", table + fns + f"console.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_the_board_clip_is_a_css_shape() -> None:
    assert _node('wbCropClip("ellipse")') == "ellipse(50% 50% at 50% 50%)"
    assert _node('wbCropClip("diamond")') == "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)"
    assert _node('wbCropClip("hexagon")').startswith("polygon(25% 0%, 75% 0%, 100% 50%")
    assert _node('wbCropClip("triangle")') == "polygon(50% 0%, 100% 100%, 0% 100%)"


def test_an_unknown_or_absent_crop_clips_nothing() -> None:
    assert _node("[wbCropClip(undefined), wbCropClip('star'), wbCropClip('__proto__'), wbCropPath('star', 10, 10)]") == ["", "", "", ""]


def test_the_export_path_matches_the_shape_at_the_pictures_size() -> None:
    assert _node('wbCropPath("diamond", 200, 100)') == "M 100 0 L 200 50 L 100 100 L 0 50 Z"
    assert _node('wbCropPath("triangle", 80, 60)') == "M 40 0 L 80 60 L 0 60 Z"
    ellipse = _node('wbCropPath("ellipse", 200, 100)')
    assert ellipse.startswith("M 0 50 A 100 50") and ellipse.endswith("Z")


def test_the_board_and_the_export_both_read_it() -> None:
    assert 'style("clip-path", wbCropClip(d.data.crop, d.data.trim) || null)' in WB
    export = WB[WB.index('if (obj.kind === "image" && obj.data.url)') :][:1600]
    assert "wbCropPath(" in export


def test_the_format_panel_offers_it_to_pictures_only() -> None:
    row = re.search(r"^  image: \[(.*)\],$", FMT, re.M).group(1)
    assert '"crop"' in row
    for kind in ("shape", "text", "frame", "table"):
        assert '"crop"' not in re.search(rf"^  {kind}: \[(.*)\],$", FMT, re.M).group(1)
    assert 'id="wb-fmt-crop"' in HTML and 'data-fmt="crop"' in HTML
    assert 'on("wb-fmt-crop"' in FMT and 'case "crop"' in FMT


def test_the_choices_are_the_servers() -> None:
    for name in ("ellipse", "diamond", "hexagon", "triangle"):
        assert f'<option value="{name}">' in HTML



def test_a_rectangle_trim_shares_the_clip_with_the_shape() -> None:
    # A plain trim is a rectangle inside the box; the export path is the same box at the picture's size.
    assert _node("wbCropClip(undefined, [10, 20, 30, 40])") == "polygon(40% 10%, 80% 10%, 80% 70%, 40% 70%)"
    assert _node("wbCropPath(undefined, 200, 100, [10, 20, 30, 40])") == "M 80 10 L 160 10 L 160 70 L 80 70 Z"
    # A shape fits inside what the trim leaves: a diamond on half the box.
    assert _node('wbCropClip("diamond", [0, 50, 0, 0])') == "polygon(25% 0%, 50% 50%, 25% 100%, 0% 50%)"
    assert _node('wbCropClip("ellipse", [0, 50, 0, 0])') == "ellipse(25% 50% at 25% 50%)"
    assert _node('wbCropPath("ellipse", 200, 100, [0, 50, 0, 0])').startswith("M 0 50 A 50 50")
    # No trim, an empty one, or one that leaves nothing, changes nothing.
    assert _node("[wbCropClip(undefined, [0, 0, 0, 0]), wbCropClip(undefined, [60, 0, 40, 0]), wbCropClip(undefined, 'x')]") == ["", "", ""]
    assert _node('wbCropClip("diamond", [0, 0, 0, 0])') == _node('wbCropClip("diamond")')


def test_the_panel_offers_the_trim_to_pictures_only() -> None:
    row = re.search(r"^  image: \[(.*)\],$", FMT, re.M).group(1)
    assert '"trim"' in row
    for kind in ("shape", "text", "frame", "table"):
        assert '"trim"' not in re.search(rf"^  {kind}: \[(.*)\],$", FMT, re.M).group(1)
    for edge in range(4):
        assert f'id="wb-fmt-trim{edge}"' in HTML and f'"wb-fmt-trim{edge}"' in FMT
    assert 'data-fmt="trim"' in HTML and "trim: set ? trim : undefined" in FMT
    assert "obj.data.trim" in WB[WB.index('if (obj.kind === "image" && obj.data.url)') :][:1600]


def test_replace_picture_is_a_pictures_only_row_that_uploads_then_swaps_the_address() -> None:
    row = re.search(r"^  image: \[(.*)\],$", FMT, re.M).group(1)
    assert '"replace"' in row
    for kind in ("shape", "text", "frame", "table"):
        assert '"replace"' not in re.search(rf"^  {kind}: \[(.*)\],$", FMT, re.M).group(1)
    assert 'data-fmt="replace"' in HTML and 'id="wb-fmt-replace"' in HTML and 'id="wb-fmt-replace-file"' in HTML
    handler = FMT[FMT.index('on("wb-fmt-replace-file"') :][:900]
    assert '"/media/upload"' in handler and 'wbFmtApply("replace", () => ({ url: uploaded.url })' in handler


def test_a_picture_has_a_draggable_crop_box_that_writes_the_same_trim() -> None:
    row = re.search(r"^  image: \[(.*)\],$", FMT, re.M).group(1)
    assert '"cropbox"' in row
    for kind in ("shape", "text", "frame", "table"):
        assert '"cropbox"' not in re.search(rf"^  {kind}: \[(.*)\],$", FMT, re.M).group(1)
    assert 'data-fmt="cropbox"' in HTML and 'id="wb-fmt-cropbox"' in HTML and '"wb-fmt-cropbox"' in FMT
    box = FMT[FMT.index("const cropBox = ") : FMT.index('on("wb-fmt-cropbox"')]
    # Eight grips, the numbers' own write path, a keyboard way, and Escape to end it.
    assert '["nw", "n", "ne", "e", "se", "s", "sw", "w"]' in box
    assert 'wbFmtApply("trim"' in box and "ArrowLeft" in box and "Escape" in box
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8") + (
        ROOT / "frontend" / "css" / "library-lazy.css"
    ).read_text(encoding="utf-8")  # L-ui-modernisation-31: Library-only rules live in library-lazy.css
    assert ".wb-crop-grip" in css and ".wb-crop-rect" in css
