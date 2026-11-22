"""draw.io's line style for polylines: sharp, rounded, curved (WHITEBOARD_PLAN,
"The draw.io programme" section 1, "Line style for polylines").

Rounded was built as `data.round` (the Corners number); curved is `data.curve`,
a smooth line through the same points, drawn on the line only (the hit band,
ports and label keep the true shape). One "Line style" select writes both."""

from tests._app_js import frontend_text
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
WB = frontend_text("whiteboard.js")


def _curved() -> str:
    start = WB.index("wbRoundedPathD.curved = function")
    return WB[start : WB.index("\n};\n", start) + 4]


def _grab(name: str) -> str:
    start = WB.index(f"function {name}(")
    depth, i = 0, WB.index("{", start)
    while True:
        depth += WB[i] == "{"
        depth -= WB[i] == "}"
        i += 1
        if depth == 0:
            return WB[start:i]


def test_curved_path_is_smooth_through_the_points():
    script = "\n".join([
        _grab("wbRoundedPathD"),
        _curved(),
        """
console.log(JSON.stringify({
  open: wbRoundedPathD.curved("M0 0 L50 0 L50 50 L100 50"),
  closed: wbRoundedPathD.curved("M0 0 L100 0 L100 60 L0 60 Z"),
  two: wbRoundedPathD.curved("M0 0 L50 0"),
  arc: wbRoundedPathD.curved("M0 0 C 10 0 10 10 20 10"),
  shaft: wbRoundedPathD.curved("M0 0 L50 0 L50 50 M60 60 L70 70", true),
}));
""",
    ])
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    # Four points, three segments, each a cubic that ends on a real point.
    assert out["open"].startswith("M0 0 C") and out["open"].count("C") == 3
    assert out["open"].endswith("100 50")
    assert out["closed"].count("C") == 4 and out["closed"].endswith("Z")
    # Two points are a straight line; a path with its own curves is left as it came.
    assert out["two"] == "M0 0 L50 0"
    assert out["arc"] == "M0 0 C 10 0 10 10 20 10"
    # A connector's arrowheads are the subpaths after the shaft and keep their shape.
    assert out["shaft"].endswith(" M60 60 L70 70") and "C" in out["shaft"]


def test_the_panel_has_one_line_style_row():
    style = HTML[HTML.index('data-format-panel="style"'):HTML.index('data-format-panel="text"')]
    assert 'id="wb-fmt-linestyle"' in style and 'data-fmt="linestyle"' in style
    for value in ("sharp", "rounded", "curved"):
        assert f'<option value="{value}"' in style


def test_each_kind_that_draws_a_line_takes_it():
    for kind in ("shape", "line", "arrow", "link"):
        row = FMT[FMT.index(f"  {kind}: ["):].split("\n", 1)[0]
        assert '"linestyle"' in row, kind


def test_the_panel_reads_and_writes_it():
    assert 'case "linestyle":' in FMT
    assert 'on("wb-fmt-linestyle", "change"' in FMT
    assert '["wb-fmt-linestyle", "linestyle", "linestyle"]' in FMT


def test_the_renderer_draws_it_and_a_pasted_style_carries_it():
    assert "wbRoundedPathD.curved(pathData" in WB[WB.index("sketchUpdate.each(function(d)"):]
    for name in ("WB_SKETCH_STYLE_KEYS", "WB_SKETCH_RESET_KEYS"):
        block = WB[WB.index(f"const {name}"):].split("];", 1)[0]
        assert re.search(r'"curve"', block), name
