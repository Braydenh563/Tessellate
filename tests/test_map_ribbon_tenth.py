"""L-mindmap-25: a ribbon prints its numbers from integers, and draws the same outline.

The drop of a linked 500-topic branch draws its 300 cross-links and the lines on screen through
`wbMapRibbonD`, and half of that function's time was printing each rounded double
(`${Math.round(v * 10) / 10}`, about 600 numbers a long ribbon). `wbMapTenth` writes the same text
from integer tenths. Held here: the two agree on every value (NaN, the infinities and -0
included), and `wbMapRibbonD` draws the same outline character for character as the old printing
on a fixed set of branches. `whiteboard-map.js` (with its pieces) runs in a node `vm`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests._app_js import frontend_text

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const ctx = {
  console, setTimeout: () => 0, clearTimeout() {}, addEventListener() {}, queueMicrotask() {}, onSurface() {},
  MD_RUN_FONTS: { serif: "s", mono: "m", wide: "w" },
  document: { querySelector: () => null, querySelectorAll: () => [], getElementById: () => null, addEventListener() {} },
  wbState: { objects: [] },
};
ctx.wbInstances = { container: () => null, layer: () => null, query: () => null, queryAll: () => [] };
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx, { filename: "whiteboard-map.js" });
ctx.__out = (value) => process.stdout.write(JSON.stringify(value));
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), ctx);
"""

BODY = r"""
//: The printing every ribbon used before, to hold the new one to.
const old = (v) => `${Math.round(v * 10) / 10}`;
let seed = 7;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const values = [NaN, Infinity, -Infinity, 0, -0, -0.04, 0.05, -0.05, 0.15, -0.15, -2.25, 1e15 + 0.3, -1e15 - 0.3, 123456789.45];
for (let i = 0; i < 200000; i++) values.push((rnd() - 0.5) * Math.pow(10, rnd() * 12 - 3));
const wrong = values.filter((v) => wbMapTenth(v) !== old(v)).slice(0, 5).map(String);
//: The outline against the old printing: the same samples, joined the same way.
wbMapNodeSize = () => ({ w: 120, h: 36 });
let drawn = 0, differ = 0;
for (let i = 0; i < 60; i++) {
  const parent = { id: i, x: rnd() * 3000 - 1500, y: rnd() * 3000 - 1500, data: {}, parent_id: 1 };
  const child = { id: 1000 + i, x: rnd() * 3000 - 1500, y: rnd() * 3000 - 1500, data: {}, parent_id: i };
  const now = wbMapRibbonD(parent, child, "free");
  const before = now.replace(/-?\d+(?:\.\d+)?/g, (n) => old(Number(n)));
  drawn += now.length > 200;
  differ += before !== now;
}
__out({ wrong, drawn, differ });
"""


@needs_node
def test_the_tenth_prints_what_the_rounded_double_printed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        files = {name: Path(tmp) / name for name in ("h.js", "map.js", "body.js")}
        files["h.js"].write_text(HARNESS, encoding="utf-8")
        #: With its pieces, unwrapped, so the edges file's inner `wbMapTenth` is in scope.
        files["map.js"].write_text(frontend_text("whiteboard-map.js"), encoding="utf-8")
        files["body.js"].write_text(BODY, encoding="utf-8")
        out = subprocess.run(["node", *(str(files[n]) for n in ("h.js", "map.js", "body.js"))], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    got = json.loads(out.stdout)
    assert got["wrong"] == [], got
    assert got["drawn"] == 60 and got["differ"] == 0, got


def test_the_ribbon_prints_through_the_tenth_and_reuses_its_controls() -> None:
    edges = frontend_text("whiteboard-map-edges.js")
    ribbon = edges[edges.index("function wbMapRibbonD(") : edges.index("function wbMapTenth(")]
    assert "const at = (pt) => `${wbMapTenth(pt[0])} ${wbMapTenth(pt[1])}`;" in ribbon
    assert "Math.round(x * 10) / 10" not in ribbon
    smooth = edges[edges.index("function wbMapSmoothThrough(") : edges.index("function wbMapEdgeIsRibbon(")]
    assert "const c1 = [0, 0];" in smooth and "c1[0] = " in smooth
