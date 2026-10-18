"""draw.io's connector spacing (WHITEBOARD_PLAN, "The draw.io programme"
section 4; whiteboard-1018 step 6): the size of a line jump, a gap between a
connector's end and the shape it joins, and a command that clears a
connector's bends.

The jump size and the gaps are connector data the server keeps opaque
(`jumpSize`, `gapStart`, `gapEnd`); the pure parts run in node here and the
app measures the drawn line."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")


def test_the_style_tab_has_the_rows():
    style = HTML[HTML.index('data-format-panel="style"'):HTML.index('data-format-panel="text"')]
    for ident in ("wb-fmt-jumpsize", "wb-fmt-gapstart", "wb-fmt-gapend"):
        assert f'id="{ident}"' in style, ident
    for row in ("jumpsize", "gapstart", "gapend"):
        assert f'data-fmt="{row}"' in style, row


def test_only_a_connector_takes_them():
    link = FMT[FMT.index("  link: ["):].split("\n", 1)[0]
    for field in ("jumpsize", "gapstart", "gapend"):
        assert f'"{field}"' in link, field
    for kind in ("shape", "line", "arrow", "text"):
        row = FMT[FMT.index(f"  {kind}: ["):].split("\n", 1)[0]
        for field in ("jumpsize", "gapstart", "gapend"):
            assert f'"{field}"' not in row, (kind, field)


def test_the_panel_reads_and_writes_them():
    for field in ("jumpsize", "gapstart", "gapend"):
        assert f'case "{field}":' in FMT
    for ident in ("wb-fmt-jumpsize", "wb-fmt-gapstart", "wb-fmt-gapend"):
        assert f'on("{ident}", "change"' in FMT, ident


def test_the_line_reads_them():
    assert "wbJumpSize(parsed)" in WB[WB.index("function wbApplyLineJumps"):][:2500]
    assert "gap" in WB[WB.index("function wbLinkShape"):][:600]
    assert "wbGapEnds(" in WB[WB.index("function wbLinkPathD"):][:1500]


def test_reset_and_copy_style_know_them():
    reset = WB[WB.index("const WB_SKETCH_RESET_KEYS"):WB.index("const WB_OBJECT_RESET_KEYS")]
    copy = WB[WB.index("const WB_SKETCH_STYLE_KEYS"):WB.index("const WB_OBJECT_STYLE_KEYS")]
    for key in ("jumpSize", "gapStart", "gapEnd"):
        assert f'"{key}"' in reset and f'"{key}"' in copy, key


def test_clear_waypoints_is_a_command():
    row = next((line for line in CMD.splitlines() if '{ id: "clear-waypoints"' in line), None)
    assert row and 'group: "Item"' in row and 'needs: "bent"' in row and "wbClearWaypoints(" in row
    assert "  bent: " in CMD
    body = FMT[FMT.index("function wbClearWaypoints"):][:900]
    assert "wbFmtApply(" in body


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_pure_functions():
    def grab(src: str, name: str) -> str:
        start = src.index(f"function {name}(")
        # The body's brace, past any destructured parameter.
        depth, i = 0, src.index(") {", start) + 2
        while True:
            depth += src[i] == "{"
            depth -= src[i] == "}"
            i += 1
            if depth == 0:
                return src[start:i]

    script = "\n".join([grab(WB, "wbJumpSize"), grab(WB, "wbLinkGap"), grab(WB, "wbGapEnd"), grab(WB, "wbGapEnds"),
        """
const box = { minX: 0, minY: 0, maxX: 100, maxY: 50 };
const s = { x: 100, y: 25, dir: { x: 1, y: 0 }, box };
const t = { x: 300, y: 25, dir: { x: -1, y: 0 }, box };
const free = { x: 300, y: 25 };
const out = {
  jump: [{}, { width: 5 }, { jumpSize: 12 }, { jumpSize: 1 }, { jumpSize: 99 }, { jumpSize: "x", width: 2 }].map(wbJumpSize),
  gap: [{}, { gapStart: 8 }, { gapEnd: -3 }, { gapStart: 500, gapEnd: 4 }, { gapStart: "x" }].map(wbLinkGap),
  straight: wbGapEnds(s, t, { start: 10, end: 20 }, { chord: true }),
  curved: wbGapEnds(s, { ...t, y: 125 }, { start: 10, end: 0 }, { chord: false }),
  free: wbGapEnds(s, free, { start: 10, end: 10 }, { chord: true }),
  tiny: wbGapEnds({ ...s, x: 100 }, { ...t, x: 110 }, { start: 60, end: 60 }, { chord: true }),
};
console.log(JSON.stringify(out));
"""])
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    # Automatic is four more than the line's width, as the jump was before it had a size.
    assert out["jump"] == [7, 9, 12, 2, 40, 6]
    assert out["gap"] == [None, {"start": 8, "end": 0}, None, {"start": 60, "end": 4}, None]
    # A straight line shortens along the chord from both ends; a free point has no perimeter to keep off.
    assert (out["straight"]["source"]["x"], out["straight"]["target"]["x"]) == (110, 280)
    assert out["straight"]["source"]["y"] == 25 and out["straight"]["target"]["y"] == 25
    # A curve leaves along its end's own direction.
    assert (out["curved"]["source"]["x"], out["curved"]["source"]["y"]) == (110, 25)
    assert out["curved"]["target"]["y"] == 125
    assert out["free"]["target"]["x"] == 300 and out["free"]["source"]["x"] == 110
    # Two big gaps on a short line never cross over each other.
    assert out["tiny"]["source"]["x"] < out["tiny"]["target"]["x"]
