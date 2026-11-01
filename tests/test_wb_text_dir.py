"""INBOX 1510(a): draw.io's Text tab has a direction (left to right, right to
left, vertical) and the words' own opacity; the board's Format panel had
neither (agent board-1101's gap list). Both are stored only when set, so a
reset box and an untouched one match, and both reach the label inline, so an
export keeps them.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tessellate.api.routes_whiteboard import WhiteboardObjectData
from tests._app_js import frontend_text


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def test_the_panel_has_both_rows_with_help():
    html = frontend_text("index.html")
    assert 'id="wb-fmt-dir"' in html and 'id="wb-fmt-inkalpha"' in html
    assert '<option value="rtl">Right to left</option>' in html
    assert "<b>Direction</b>" in html and "<b>Text opacity</b>" in html
    fmt = frontend_text("whiteboard-format.js")
    assert '["wb-fmt-dir", "dir", "text"]' in fmt and '["wb-fmt-inkalpha", "inkalpha", "text"]' in fmt
    assert '"label_dir", "label_alpha"' in fmt and '"text_dir", "text_alpha"' in fmt


def test_reset_clears_them():
    board = frontend_text("whiteboard.js")
    assert '"label_dir", "label_alpha",\n];' in board
    assert '"text_dir", "text_alpha", "alpha",' in board


def test_the_server_takes_only_the_named_values():
    assert WhiteboardObjectData(text_dir="rtl").text_dir == "rtl"
    assert WhiteboardObjectData(text_alpha=0.5).text_alpha == 0.5
    for bad in ({"text_dir": "upside"}, {"text_alpha": 0}, {"text_alpha": 2}):
        with pytest.raises(ValueError):
            WhiteboardObjectData(**bad)


def test_the_paint_sets_only_known_values():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    board = frontend_text("whiteboard.js")
    code = _function(board, "wbPaintTextDir") + _function(board, "wbLabelBand")
    script = code + r"""
const paint = (dir, alpha) => { const el = { style: {} }; wbPaintTextDir(el, dir, alpha); return el.style; };
const svg = { namespaceURI: "http://www.w3.org/2000/svg", style: {}, dataset: {} };
wbPaintTextDir(svg, "vertical", 1);
const turned = { ...svg.style, dir: svg.dataset.dir, band: wbLabelBand(svg, { cx: 5, cy: 5, w: 160, h: 60 }) };
wbPaintTextDir(svg, undefined, 1);
console.log(JSON.stringify([paint("rtl", 0.5), paint("vertical", 1), paint("upside", undefined), paint(undefined, 0), turned, svg.dataset]));
"""
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert out[0] == {"direction": "rtl", "writingMode": "", "opacity": "0.5"}
    assert out[1] == {"direction": "", "writingMode": "vertical-rl", "opacity": ""}
    assert out[2] == {"direction": "", "writingMode": "", "opacity": ""}
    assert out[3]["opacity"] == ""
    # A shape's SVG label is turned by its layout, never by writing-mode, and
    # wraps to the shape's height.
    assert out[4]["writingMode"] == "" and out[4]["dir"] == "vertical"
    assert out[4]["band"] == {"cx": 5, "cy": 5, "w": 60, "h": 160}
    assert out[5] == {}
    assert 'rotate(-90 ${area.cx} ${area.cy})' in _function(board, "wbLayoutShapeLabel")
