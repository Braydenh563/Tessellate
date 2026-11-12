"""L365: a map exported as PNG or SVG draws each topic as the canvas does.

Levels (size, weight, slant read off the drawn label), the cut shapes
(diamond, hexagon, chevron as polygons, underline as a bar, plain as words
only), the shadow and glow effect, and the Phosphor icon. The suite cannot
rasterise, so this holds the shape of `wbBuildExportSvg`'s map branch and
runs the pure pieces (`wbSvgText`) under node.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _map_branch() -> str:
    start = WB.index("} else if (WB_MAP_KINDS.has(obj.kind)) {")
    return WB[start : WB.index('} else if (obj.kind === "text" && obj.data.sticker)', start)]


def test_the_cut_shapes_export_as_polygons_with_the_canvas_outline():
    branch = _map_branch()
    for shape in ("diamond", "hexagon", "chevron"):
        assert f'cut === "{shape}"' in branch, shape
        assert f'data-shape="{shape}"]::before' in CSS, shape
    assert '"::after"' in branch and '"::before"' in branch
    assert 'cut === "underline"' in branch and 'cut !== "none"' in branch


def test_effect_and_phosphor_icon_still_travel():
    branch = _map_branch()
    assert "wbExportTopicEffect(" in branch and "wbExportTopicGlyph(" in branch


def test_the_label_takes_its_levels_size_weight_and_slant():
    branch = _map_branch()
    assert 'querySelector(".wb-map-text")' in branch
    assert "fontWeight: textStyle?.fontWeight" in branch and "fontStyle: textStyle?.fontStyle" in branch
    assert "fontSize: 14," not in branch


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_wbsvgtext_writes_weight_and_slant_only_when_they_are_not_the_default():
    text = re.search(r"^function wbSvgText\(.*?^\}", WB, re.S | re.M).group(0)
    script = (
        "const wbSvgEscape = (s) => String(s);\n" + text +
        "\nprocess.stdout.write(JSON.stringify(["
        "wbSvgText(['a'], 1, 2, {}),"
        "wbSvgText(['a'], 1, 2, {fontWeight: '700', fontStyle: 'italic'}),"
        "wbSvgText(['a'], 1, 2, {fontWeight: '400', fontStyle: 'normal'})]));"
    )
    plain, strong, normal = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert "font-weight" not in plain and "font-style" not in plain
    assert 'font-weight="700"' in strong and 'font-style="italic"' in strong
    assert normal == plain
