"""draw.io's Fill section, the other half (WHITEBOARD_PLAN, "The draw.io
programme" section 1; whiteboard-1018): a gradient (a second colour and a
direction, or radial) and a fill style (hatch, cross-hatch, dots, dashes,
zigzag) on a closed shape.

Both live in the sketch's data (`gradient {to, dir}`, `fillStyle`), which the
server keeps opaque, and both are drawn through a `<defs>` kept inside the
shape's own group, so the board's export, which clones each group, carries
them with it and the picture keeps what the board shows. Pure functions run
in node here; the app measures the rest."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def test_the_style_tab_has_the_rows():
    style = HTML[HTML.index('data-format-panel="style"'):HTML.index('data-format-panel="text"')]
    for ident in ("wb-fmt-fillstyle", "wb-fmt-gradient-dir", "wb-fmt-gradient"):
        assert f'id="{ident}"' in style, ident
    for value in ("hatch", "cross", "dots", "dashed", "zigzag"):
        assert f'value="{value}"' in style, value
    for value in ("none", "s", "n", "e", "w", "radial"):
        assert f'<option value="{value}">' in style[style.index('id="wb-fmt-gradient-dir"'):], value


def test_only_a_closed_shape_takes_them():
    row = FMT[FMT.index("  shape: ["):].split("\n", 1)[0]
    assert '"fillstyle"' in row and '"gradient"' in row
    for kind in ("line", "arrow", "link", "text"):
        row = FMT[FMT.index(f"  {kind}: ["):].split("\n", 1)[0]
        assert '"fillstyle"' not in row and '"gradient"' not in row, kind


def test_the_panel_reads_and_writes_them():
    for field in ("fillstyle", "gradient", "gradient-dir"):
        assert f'case "{field}":' in FMT
    for ident in ("wb-fmt-fillstyle", "wb-fmt-gradient-dir", "wb-fmt-gradient"):
        assert f'on("{ident}", "change"' in FMT, ident


def test_the_renderer_draws_them_inside_the_group():
    assert "function wbSyncFillDefs" in WB
    body = WB[WB.index("function wbSyncFillDefs"):][:3000]
    assert '":scope > defs.wb-fill-defs"' in body
    assert "createElementNS" in body
    assert "innerHTML" not in body
    paint = WB[WB.index("sketchUpdate.each(function(d)"):]
    assert "wbSyncFillDefs(this" in paint
    # A patterned fill is mostly board, so the label keeps the theme's ink.
    assert 'parsed.fillStyle' in WB[WB.index("function wbShapeLabelInk"):][:500]


def test_reset_and_copy_style_know_them():
    reset = WB[WB.index("const WB_SKETCH_RESET_KEYS"):WB.index("const WB_OBJECT_RESET_KEYS")]
    copy = WB[WB.index("const WB_SKETCH_STYLE_KEYS"):WB.index("const WB_OBJECT_STYLE_KEYS")]
    for key in ("gradient", "fillStyle"):
        assert f'"{key}"' in reset and f'"{key}"' in copy, key


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_pure_functions():
    def grab(name: str) -> str:
        start = WB.index(f"function {name}(")
        depth, i = 0, WB.index("{", start)
        while True:
            depth += WB[i] == "{"
            depth -= WB[i] == "}"
            i += 1
            if depth == 0:
                return WB[start:i]

    consts = WB[WB.index("const WB_FILL_STYLES"):].split("\n", 1)[0]
    script = "\n".join([consts, grab("wbGradientVector"), grab("wbFillPatternSpec"), grab("wbHexColour"),
        """
const out = {
  vec: ["s", "n", "e", "w", "radial", "x"].map((d) => wbGradientVector(d)),
  solid: wbFillPatternSpec("solid", "#336699"),
  bogus: wbFillPatternSpec("bogus", "#336699"),
  hatch: wbFillPatternSpec("hatch", "#336699"),
  cross: wbFillPatternSpec("cross", "#336699"),
  dots: wbFillPatternSpec("dots", "#336699"),
  dashed: wbFillPatternSpec("dashed", "#336699"),
  zigzag: wbFillPatternSpec("zigzag", "#336699"),
  hex: ["#abc", "#aabbcc", "#aabbccdd", "red", "url(#x)", "#12", "", null].map(wbHexColour),
};
console.log(JSON.stringify(out));
"""])
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    out = json.loads(run.stdout)
    assert out["vec"][0] == {"x1": 0, "y1": 0, "x2": 0, "y2": 1}
    assert out["vec"][1] == {"x1": 0, "y1": 1, "x2": 0, "y2": 0}
    assert out["vec"][2] == {"x1": 0, "y1": 0, "x2": 1, "y2": 0}
    assert out["vec"][3] == {"x1": 1, "y1": 0, "x2": 0, "y2": 0}
    assert out["vec"][4] is None and out["vec"][5] is None
    assert out["solid"] is None and out["bogus"] is None
    for name in ("hatch", "cross", "dots", "dashed", "zigzag"):
        spec = out[name]
        assert spec["size"] > 0 and spec["els"], name
        # The colour comes through, and only as a plain hex.
        assert any(el["attrs"].get("stroke") == "#336699" or el["attrs"].get("fill") == "#336699" for el in spec["els"]), name
    assert out["hatch"]["rotate"] == 45 and out["cross"]["rotate"] == 45 and out["dots"]["rotate"] == 0
    assert out["hex"] == ["#abc", "#aabbcc", "#aabbccdd", None, None, None, None, None]
