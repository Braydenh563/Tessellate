"""Board-wide style presets (WHITEBOARD_PLAN, "The draw.io programme" section 1,
"Board-wide style presets"): with nothing selected the Format panel's Style tab
offers twelve colour schemes; one press writes fill, line and text colour across
the board in one undo step. The scheme is a pure function of the preset and the
item, run in node here and in the app by the sweep that drives the button."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")


def _block(start_marker: str, end_marker: str) -> str:
    start = FMT.index(start_marker)
    return FMT[start : FMT.index(end_marker, start)]


def test_the_presets_and_the_patch_rule():
    kit = _block("//: **Board style presets**", "//: --- end board style")
    script = "const wbFmtState = {};\n" + kit + """
const kit = wbFmtState.board;
const shape = (extra) => ({ kind: "sketch", fmt: "shape", filled: true, data: { color: "#000000", fill: "#ffffff", ...extra } });
const out = {
  count: kit.PRESETS.length,
  names: new Set(kit.PRESETS.map((p) => p.name)).size,
  hex: kit.PRESETS.every((p) => [p.fill, p.stroke, p.ink].every((c) => /^#[0-9a-f]{6}$/.test(c))),
  filled: kit.patchFor(kit.PRESETS[0], shape({})),
  unfilled: kit.patchFor(kit.PRESETS[0], { kind: "sketch", fmt: "shape", filled: false, data: { color: "#000000" } }),
  line: kit.patchFor(kit.PRESETS[0], { kind: "sketch", fmt: "line", data: {} }),
  link: kit.patchFor(kit.PRESETS[0], { kind: "sketch", fmt: "link", data: {} }),
  sticky: kit.patchFor(kit.PRESETS[0], { kind: "object", fmt: "text", data: { bg: "#ffee88", border_color: "#000000" } }),
  plainText: kit.patchFor(kit.PRESETS[0], { kind: "object", fmt: "text", data: {} }),
  image: kit.patchFor(kit.PRESETS[0], { kind: "object", fmt: "image", data: {} }),
};
console.log(JSON.stringify(out));
"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert out["count"] == 12 and out["names"] == 12 and out["hex"]
    blue = {"fill": "#dae8fc", "stroke": "#6c8ebf"}
    assert out["filled"]["color"] == blue["stroke"] and out["filled"]["fill"] == blue["fill"] and out["filled"]["fillOpacity"] == 1
    # A shape with no fill stays unfilled: the scheme must not paint what was left clear.
    assert out["unfilled"]["color"] == blue["stroke"] and "fill" not in out["unfilled"]
    assert out["line"] == {"color": blue["stroke"]} and out["link"] == {"color": blue["stroke"]}
    assert out["sticky"]["bg"] == blue["fill"] and out["sticky"]["border_color"] == blue["stroke"]
    assert list(out["plainText"]) == ["color"]
    assert out["image"] is None


def test_the_panel_offers_them_only_with_nothing_selected():
    assert 'id="wb-board-style"' in HTML and 'id="wb-board-style-list"' in HTML
    assert 'data-help-for="wb-fmt-help-boardstyle"' in HTML
    sync = FMT[FMT.index("function wbFormatSync() {"):]
    assert 'getElementById("wb-board-style")' in sync[:3000]
    assert "wbFmtState.board.show(" in sync[:3000]


def test_applying_is_one_undo_step_and_skips_locked_items():
    kit = _block("//: **Board style presets**", "//: --- end board style")
    assert "wbRecordGesture(" in kit and "wbIsLocked(" in kit and "wbSaveMany(" in kit
