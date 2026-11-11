"""F2 gap row 6: a frame's Padding is the room `wbFrameFit` leaves round what it holds (32 when empty).

`wbFrameFit` runs in node with the board's lookups stubbed: one held item at (100, 100) to (200, 160).
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text


def _fit(frame_data: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    src = frontend_text("whiteboard.js")
    start = src.index("async function wbFrameFit(")
    fit = src[start : src.index("\n}\n", start) + 3]
    script = f"""
const WB_FRAME_FIT_MARGIN = 32;
const wbFrameContents = () => ["object:7"];
const wbFindItem = () => ({{ id: 7 }});
const wbItemBBox = () => ({{ minX: 100, minY: 100, maxX: 200, maxY: 160 }});
const wbLinkedSketchesFor = () => [];
const toast = () => {{}};
const WB_KIND_INFO = {{ object: {{ payload: (f) => ({{ x: f.x }}) }} }};
const reducedMotionWanted = () => true;
const wbScheduleRender = () => {{}};
const wbSaveObject = async () => {{}};
const wbPushUndo = () => {{}};
const wbUpdateSelectionBar = () => {{}};
const document = {{ querySelector: () => null }};
{fit}
(async () => {{
  const frame = {{ kind: "frame", id: 1, x: 0, y: 0, width: 400, height: 400, data: {frame_data} }};
  await wbFrameFit(frame);
  console.log(JSON.stringify({{ x: frame.x, y: frame.y, w: frame.width, h: frame.height }}));
}})();
"""
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_no_padding_keeps_the_32_unit_margin():
    assert _fit("{}") == {"x": 68, "y": 68, "w": 164, "h": 124}
    assert _fit("undefined") == {"x": 68, "y": 68, "w": 164, "h": 124}


def test_a_set_padding_replaces_it_and_zero_is_snug():
    assert _fit("{ pad: 10 }") == {"x": 90, "y": 90, "w": 120, "h": 80}
    assert _fit("{ pad: 0 }") == {"x": 100, "y": 100, "w": 100, "h": 60}


def test_a_frame_shows_the_padding_row():
    fmt = frontend_text("whiteboard-format.js")
    row = fmt[fmt.index("  frame: [") : fmt.index("\n", fmt.index("  frame: ["))]
    assert '"pad"' in row
    assert "frame.data?.pad ?? WB_FRAME_FIT_MARGIN" in frontend_text("whiteboard.js")
    assert "a frame's edge and what it holds" in frontend_text("index.html")
