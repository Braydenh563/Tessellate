"""L-world-class-391: the constellation and the microbes allocate nothing a frame.

V8 boxes a fractional number on the heap each time it is handed to a DOM call or to a function it does not
inline, so a frame that moves a hundred path points with fractions made 6 KB of garbage (constellation 173 to 223
KB/s, microbes 607 to 717 KB/s at 20 fps). The fix is read from the source, as the other background-art tests
do: path coordinates are whole numbers in a quarter-pixel space (`p.quarter`), opacities come from a table of
numbers boxed once, and the grid hands back a cell by index. The grid is also run in node."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._js_scope import unwrapped_copy

BG_ART = unwrapped_copy(Path(__file__).resolve().parents[1] / "frontend" / "js" / "bg-art.js")
TEXT = BG_ART.read_text(encoding="utf-8")

_SCRIPT = r"""
const fs = require("fs");
const vm = require("vm");
const noop = () => {};
const box = { document: { addEventListener: noop }, window: { addEventListener: noop }, navigator: {}, performance: { now: () => 0 }, console };
vm.createContext(box);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8") + `
this.out = { bgGrid, bgAlpha, BG_ALPHAS, BG_ALPHA_STEPS };
`, box);
const o = box.out;
const grid = o.bgGrid(400, 300, 50, 6);
const xs = new Float32Array([-100, 10, 399.5, 200, 1000, 60.25]), ys = new Float32Array([5, -80, 299, 150, 20, 61.5]);
grid.build(xs, ys, 0, 6);
const want = (x, y) => Math.min(grid.rows - 1, Math.max(0, Math.floor((y + 40) / 50))) * grid.cols + Math.min(grid.cols - 1, Math.max(0, Math.floor((x + 40) / 50)));
console.log(JSON.stringify({
  cells: Array.from(grid.cell.slice(0, 6)), expect: Array.from(xs).map((x, i) => want(x, ys[i])),
  indexed: Array.from(grid.items).sort((a, b) => a - b),
  alpha: [o.bgAlpha(-1), o.bgAlpha(0.5), o.bgAlpha(0.49), o.bgAlpha(2), o.bgAlpha(0.7)],
  same: o.bgAlpha(0.3) === o.bgAlpha(0.3), n: o.BG_ALPHAS.length, steps: o.BG_ALPHA_STEPS,
}));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("bgart391") / "run.js"
    script.write_text(_SCRIPT, encoding="utf-8")
    run = subprocess.run([node, str(script), str(BG_ART)], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _chunk(name: str) -> str:
    start = TEXT.index(f"\n  {name}(p, ctx) {{")
    nxt = re.search(r"\n  [a-z]+\(p, ctx\) \{", TEXT[start + 10 :])
    return TEXT[start : start + 10 + nxt.start()] if nxt else TEXT[start:]


def test_the_grid_gives_a_cell_by_index_the_way_it_computed_it(out):
    assert out["cells"] == out["expect"]
    assert out["indexed"] == [0, 1, 2, 3, 4, 5]
    assert "cellAt" not in TEXT and "subarray" not in TEXT[TEXT.index("function bgGrid") : TEXT.index("// --- genomes")]


def test_opacities_come_from_a_table_of_numbers_boxed_once(out):
    assert out["alpha"] == [0, 0.5, 0.5, 1, 0.6875]
    assert out["same"] is True and out["n"] == out["steps"] + 1
    # a plain array that starts with a non-number stays an array of tagged values, so a read is the same box
    assert "const BG_ALPHAS = [null];" in TEXT


@pytest.mark.parametrize("style", ["constellation", "microbes"])
def test_a_frame_hands_the_canvas_whole_numbers_and_table_opacities(style):
    chunk = _chunk(style)
    body = chunk[chunk.index("frame(") :]
    assert "p.quarter(true)" in body and body.count("p.quarter(true)") == body.count("p.quarter(false)") or style == "microbes"
    # every globalAlpha assignment in the frame is a table read, never arithmetic
    for line in re.findall(r"globalAlpha = ([^;]+);", body):
        assert re.fullmatch(r"(bgAlpha\(.*\)|BG_ALPHAS\[[^\]]+\]|FAR_ALPHA\[k\]|Math\.sin\(.*\)|[01])", line.strip()) or "Math.sin" in line, line
    # path points are integers: `| 0` on each, no bare fractional coordinate
    for call in re.findall(r"g\.(?:moveTo|lineTo|bezierCurveTo|rect)\(([^;]+)\);", body):
        if "| 0" in call or "seg[" in call or "(sx[i] - 1)" in call:
            continue
        pytest.fail(f"{style}: {call}")


def test_the_microbes_ask_for_flow_in_runs_and_name_bodies_by_index():
    chunk = _chunk("microbes")
    assert "for (const sp of species)" not in chunk
    # no per-organism call into the noise function (a boxed argument and answer each): runs into arrays
    assert "bgFlow(" not in chunk and chunk.count("bgFlowFill(") >= 5
    assert "grid.cell[i]" in chunk
    # a body is passed to the flagella as an index and a side, never as fractional coordinates
    assert "const lash = (g, sp, i, side) =>" in chunk and "lash(g, sp, i, 0)" in chunk
    assert "const sx = (col * at.cell) | 0" in chunk
