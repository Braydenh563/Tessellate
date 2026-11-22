"""Arrow shape geometry (WHITEBOARD_PLAN section 2, draw.io's `addArrowGeometry`): a block or flex arrow connector takes its
own body width (`arrowBody`) and head width (`arrowHead`). `connectorOutline` is pure and run in node."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LINE = [{"x": 0, "y": 0}, {"x": 200, "y": 0}]


def _outline(shape, geom=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const wbFmtState = {}; const onSurface = () => {};\n" + frontend_text("whiteboard-shape-more.js")
        + f"\nconsole.log(JSON.stringify(wbFmtState.shapeMore.connectorOutline({json.dumps(shape)}, {json.dumps(LINE)}, 3, "
        f"{{start: false, end: true}}, {json.dumps(geom or {})})));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def _ys(d):
    return [float(m) for m in re.findall(r"[-\d.]+ ([-\d.]+)", d.replace("M", "").replace("Z", "")) if m]


def _spread(d):
    ys = _ys(d)
    return max(ys) - min(ys)


@pytest.mark.parametrize("shape", ["block", "flex"])
def test_the_body_width_sets_the_shaft(shape):
    wide = _outline(shape, {"body": 40, "head": 100})
    narrow = _outline(shape, {"body": 10, "head": 100})
    # The head (100 across) is the widest part either way; the shaft is read from the first outline point.
    first_left = lambda out: float(out["d"].split(" L ")[0].split()[2])  # noqa: E731
    assert abs(first_left(wide)) == 20 and abs(first_left(narrow)) == 5


@pytest.mark.parametrize("shape", ["block", "flex"])
def test_the_head_width_sets_the_head(shape):
    assert _spread(_outline(shape, {"head": 60})["d"]) == 60
    assert _spread(_outline(shape, {"head": 120})["d"]) == 120


def test_absent_or_zero_keeps_the_shapes_own_proportion():
    for shape in ("block", "flex"):
        assert _outline(shape)["d"] == _outline(shape, {"body": 0, "head": 0})["d"] == _outline(shape, {"body": "x"})["d"]


def test_other_shapes_ignore_it():
    for shape in ("double", "pipe", "wire", "tapered"):
        assert _outline(shape)["d"] == _outline(shape, {"body": 40, "head": 90})["d"]


def test_the_panel_has_the_two_fields_for_a_connector_only():
    fmt = frontend_text("whiteboard-format.js")
    link = fmt[fmt.index("  link: ["):].split("\n", 1)[0]
    for field in ("arrowbody", "arrowhead"):
        assert f'"{field}"' in link
        assert f'data-fmt="{field}"' in HTML
        assert f'case "{field}":' in fmt
    for ident in ("wb-fmt-arrowbody", "wb-fmt-arrowhead"):
        assert f'id="{ident}"' in HTML
    assert 'on(id, "change"' in fmt and "arrowBody" in fmt
    for kind in ("shape", "line", "arrow", "text"):
        row = fmt[fmt.index(f"  {kind}: ["):].split("\n", 1)[0]
        assert '"arrowbody"' not in row


def test_the_line_reads_it_and_reset_and_copy_style_know_it():
    assert "body: parsed.arrowBody, head: parsed.arrowHead" in frontend_text("whiteboard-shape-more.js")
    wb = frontend_text("whiteboard.js")
    reset = wb[wb.index("const WB_SKETCH_RESET_KEYS"):wb.index("const WB_OBJECT_RESET_KEYS")]
    copy = wb[wb.index("const WB_SKETCH_STYLE_KEYS"):wb.index("const WB_OBJECT_STYLE_KEYS")]
    for key in ("arrowBody", "arrowHead"):
        assert f'"{key}"' in reset and f'"{key}"' in copy, key
