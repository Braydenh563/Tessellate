"""The owner, 2026-10-11: "can you add more shapes and more arrow options??"
(the Shapes flyout had line, arrow, square, circle, triangle and diamond).

Nine more shape tools sit in the flyout, each drawn in the dragged box and
stored as the library's `custom` shape with its text area, so a hexagon drawn
here and one placed from the library are the same thing. The browser half is
`scratchpad/ui-sweeps/wbcolour-shapes.js`."""

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = frontend_text("whiteboard.js")
COMMANDS = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
WANTED = {"rounded", "ellipse", "hexagon", "parallelogram", "star", "cylinder", "cloud", "callout", "block-arrow"}


def _shapes() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = SOURCE.index("const wbShapeAt")
    table = SOURCE[start : SOURCE.index("const WB_BRUSH_TOOLS", start)]
    script = table + (
        "console.log(JSON.stringify(Object.fromEntries(Object.entries(WB_MORE_SHAPES)"
        ".map(([k, v]) => [k, {label: v.label, area: v.area || null, d: v.d(100, 50, 160, 100)}]))))"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_the_nine_shapes_the_owner_asked_for_are_tools():
    shapes = _shapes()
    assert {k.removeprefix("shape-") for k in shapes} == WANTED
    for key, shape in shapes.items():
        assert f'data-tool="{key}"' in INDEX, key
        assert shape["d"].startswith("M ") and " Z" in shape["d"], key
        # Only the commands the board's path reader knows.
        assert not re.search(r"[^MLCAZ\d\s.\-]", shape["d"]), key
        # The outline fills the box it was dragged in (corners and tips).
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", shape["d"])]
        assert min(nums) >= 0 and max(n for n in nums) <= 260, key


def test_a_drawn_one_is_the_library_s_custom_shape_and_takes_text():
    assert "...Object.keys(WB_MORE_SHAPES)]);" in SOURCE  # a brush tool: drawn by a drag
    assert 'shape: more ? "custom" : window.currentTool' in SOURCE
    assert "if (more?.area) blob.label_area = more.area;" in SOURCE
    assert re.search(r"Object\.keys\(WB_MORE_SHAPES\)\.map\(\(tool\) => \[tool, \[\"size\", \"dash\", \"fill\"\]\]\)", SOURCE)
    assert 'class="wb-shape-menu-group wb-shape-menu-more"' in INDEX


def test_the_palette_and_the_phone_sheet_read_the_same_table():
    assert "Object.entries(WB_MORE_SHAPES).map(([tool, shape])" in COMMANDS
    assert "keys: \"\"" in COMMANDS[COMMANDS.index("Object.entries(WB_MORE_SHAPES)") :][:300]


# The Shapes flyout caret (OPEN row 847).
WB = SOURCE


def _css(name: str) -> str:
    return (ROOT / "frontend" / "css" / name).read_text(encoding="utf-8")


def test_the_shapes_caret_opens_the_list():
    """OPEN row 847: `.wb-shape-caret` had `pointer-events: none`, so the
    toggle's `closest(".wb-shape-caret")` never matched and the caret picked
    the tool. The caret takes the press, and so does the toggle's right 14px."""
    caret = re.search(r"\.wb-shape-caret\s*\{([^}]*)\}", _css("06-timeline-dialogs.css"))
    assert caret and "pointer-events" not in caret.group(1)
    start = WB.index("function wbToggleCaretHit(")
    hit = WB[start : WB.index("\n  }\n", start)]
    assert 'closest(".wb-shape-caret")' in hit and "right - 14" in hit and "e.detail > 0" in hit
    assert "if (wbToggleCaretHit(toggle, e)) {" in WB
