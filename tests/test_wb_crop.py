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
    assert 'style("clip-path", wbCropClip(d.data.crop) || null)' in WB
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

