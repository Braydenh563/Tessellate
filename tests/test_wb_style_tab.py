"""draw.io's Style tab, the cheap half (WHITEBOARD_PLAN, "The draw.io
programme" section 1; whiteboard-1018): corner rounding, a custom dash
pattern and flow animation, on a shape, a line, an arrow and a connector.

All three live in a sketch's data (`round`, `dashPattern`, `flow`), which the
server keeps opaque. The rounding is applied to the drawn line only, as the
hand-drawn look is, so the hit band, ports and label keep the true shape; a
path with a curve in it is left alone. A node test below runs the pure
functions the sweep also measures in the app."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_the_style_tab_has_the_rows():
    style = HTML[HTML.index('data-format-panel="style"'):HTML.index('data-format-panel="text"')]
    assert 'id="wb-fmt-round"' in style and 'data-fmt="round"' in style
    assert 'id="wb-fmt-pattern"' in style and 'data-fmt="pattern"' in style
    assert 'id="wb-fmt-flow"' in style and 'data-fmt="flow"' in style


def test_each_kind_that_draws_a_line_takes_them():
    for kind in ("shape", "line", "arrow", "link"):
        row = FMT[FMT.index(f"  {kind}: ["):].split("\n", 1)[0]
        for field in ("round", "pattern", "flow"):
            assert f'"{field}"' in row, (kind, field)


def test_the_panel_reads_and_writes_them():
    for field in ("round", "pattern", "flow"):
        assert f'case "{field}":' in FMT
    assert 'on("wb-fmt-round", "change"' in FMT
    assert 'on("wb-fmt-pattern", "change"' in FMT
    assert 'on("wb-fmt-flow", "change"' in FMT
    # The corner row only shows when a selected path has corners to round.
    assert "wbFmtCanRound" in FMT


def test_the_renderer_draws_them():
    assert "function wbRoundedPathD" in WB
    assert "function wbDashPatternOf" in WB
    assert "wbRoundedPathD(" in WB[WB.index("sketchUpdate.each(function(d)"):]
    assert 'classed("wb-flow"' in WB
    assert "function wbSetFlowAnimation" in WB
    # A Web Animation on the path: paint only (dash offset), held still under both motion switches.
    flow = WB[WB.index("function wbSetFlowAnimation"):][:900]
    assert "strokeDashoffset" in flow and "prefers-reduced-motion" in flow
    assert 'dataset.motion === "reduced"' in flow and 'dataset.uiMotion === "off"' in flow
    assert "wb-flow-march" not in CSS and "--wb-flow-period" not in CSS


def test_reset_and_copy_style_know_them():
    reset = WB[WB.index("const WB_SKETCH_RESET_KEYS"):WB.index("const WB_OBJECT_RESET_KEYS")]
    copy = WB[WB.index("const WB_SKETCH_STYLE_KEYS"):WB.index("const WB_OBJECT_STYLE_KEYS")]
    for key in ("round", "dashPattern", "flow"):
        assert f'"{key}"' in reset and f'"{key}"' in copy, key


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_pure_functions_round_and_parse():
    """Extracted from whiteboard.js and run in node: the same source the app draws with."""

    def grab(name: str) -> str:
        start = WB.index(f"function {name}(")
        depth, i = 0, WB.index("{", start)
        while True:
            depth += WB[i] == "{"
            depth -= WB[i] == "}"
            i += 1
            if depth == 0:
                return WB[start:i]

    script = "\n".join(
        [grab("wbDashPatternOf"), grab("wbDashArray"), grab("wbRoundedPathD"),
         """
const out = {
  parse: [wbDashPatternOf("8 4"), wbDashPatternOf("8, 4 ,2"), wbDashPatternOf(""), wbDashPatternOf("x"), wbDashPatternOf("0 4"), wbDashPatternOf("1 2 3 4 5 6 7"), wbDashPatternOf("500 4")],
  array: [wbDashArray("solid", 3, [8, 4]), wbDashArray("dashed", 2, null), wbDashArray("solid", 2, null)],
  rect: wbRoundedPathD("M0 0 L100 0 L100 60 L0 60 Z", 10),
  tiny: wbRoundedPathD("M0 0 L10 0 L10 10 L0 10 Z", 40),
  curve: wbRoundedPathD("M0 0 C 10 0 10 10 20 10", 10),
  open: wbRoundedPathD("M0 0 L50 0 L50 50", 8),
  none: wbRoundedPathD("M0 0 L50 0", 0),
};
console.log(JSON.stringify(out));
"""]
    )
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    out = json.loads(run.stdout)
    assert out["parse"] == [[8, 4], [8, 4, 2], None, None, None, None, None]
    assert out["array"] == ["24 12", "6 4", None]
    # Every corner of a rectangle becomes a curve that starts and ends a radius from it.
    assert out["rect"].count("Q") == 4
    assert out["rect"].startswith("M10 0")
    # A radius larger than half the shortest side is held to it.
    assert out["tiny"].startswith("M5 0") and out["tiny"].count("Q") == 4
    assert out["curve"] == "M0 0 C 10 0 10 10 20 10"
    assert out["open"].count("Q") == 1
    assert out["none"] == "M0 0 L50 0"
