"""Audit 1029 row 35 (G3): a big map is drawn once a tick, and the worker does not idle half its time.

Measured on a cold open of 2,000 notes and 3,796 links (session scratch
`r35/draws.js`, `r35/timeline.js`): 472 full draws for 141 ticks, 417 of them
glide frames between two ticks at about 13 ms each (6.3 s of main thread), and
a worker that slept as long as each 90 ms tick took, so the layout ran at half
a core and came to rest in 28.7 s.

- The canvas keeps a smoothed cost of its full draws (`gcNoteDrawCost`); once
  a draw costs more than `GC_GLIDE_COST_MS`, a tick is drawn where it lands
  (`gcTickSnaps`), with no frames between.
- The worker yields a short turn after a costly tick (`loopYield`), except
  during a drag and in performance mode (on by itself at two cores or fewer),
  which keep the duty cycle.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
FRONTEND = ROOT / "frontend"

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(script: str, *args: str):
    run = subprocess.run([shutil.which("node"), "-e", script, *args], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


@needs_node
def test_a_costly_draw_draws_each_tick_once_and_a_cheap_one_glides() -> None:
    cost = re.search(r"\nconst GC_GLIDE_COST_MS = [^;]+;", CANVAS).group(0)
    script = (
        cost
        + _function(CANVAS, "gcNoteDrawCost")
        + _function(CANVAS, "gcTickSnaps")
        + r"""
const s = {};
const out = { fresh: gcTickSnaps(s) };
for (let i = 0; i < 10; i++) gcNoteDrawCost(s, 3);
out.cheap = gcTickSnaps(s);
for (let i = 0; i < 10; i++) gcNoteDrawCost(s, 13);
out.costly = gcTickSnaps(s);
for (let i = 0; i < 10; i++) gcNoteDrawCost(s, 2);
out.cheapAgain = gcTickSnaps(s);
console.log(JSON.stringify(out));
"""
    )
    out = _run(script)
    assert out == {"fresh": False, "cheap": False, "costly": True, "cheapAgain": False}


def test_the_tick_handler_snaps_and_the_frame_measures_full_draws() -> None:
    handler = CANVAS[CANVAS.index('if (message.type === "tick")') : CANVAS.index('} else if (message.type === "frame")')]
    assert re.search(r"s\.gliding = true;\s*\n(?:\s*//.*\n)*\s*if \(gcTickSnaps\(s\)\) gcGlideFinish\(s\);", handler)
    assert "s.layoutRunning = message.running !== false;" in handler
    assert "const costly = s.layoutRunning && gcTickSnaps(s);" in CANVAS
    assert "s.dragNode || costly || s.alpha > 0.03 ? null : gcLineGrid(" in CANVAS
    assert re.search(r'message\.type === "end"\) \{\n\s*s\.layoutRunning = false;', CANVAS)
    request = _function(CANVAS, "gcRequestDraw")
    assert "const full = s.sceneStale;" in request and "gcNoteDrawCost(s, performance.now() - drawn)" in request


WORKER = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
const run = (code) => vm.runInContext(code, sb);
const at = (p, d, cost) => run(`perf = ${p}; dragging = ${d}; loopYield(${cost})`);
console.log(JSON.stringify({
  big: at(false, false, 90), bigDrag: at(false, true, 90), bigPerf: at(true, false, 90),
  small: at(false, false, 5), smallPerf: at(true, false, 5), huge: at(false, true, 200),
}));
"""


@needs_node
def test_the_worker_yields_a_short_turn_after_a_costly_tick_unless_held_back() -> None:
    out = _run(WORKER, str(FRONTEND))
    assert out["big"] <= 8, out
    # A drag and performance mode keep the duty cycle (as long as the tick, capped).
    assert out["bigDrag"] == 120 and out["huge"] == 120, out
    assert out["bigPerf"] == 180, out
    # A cheap tick still fills a 16 ms frame.
    assert out["small"] == 11 and out["smallPerf"] == 22, out


UNTANGLE = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
// A stepped clock: every reading is 100 ms after the last.
let now = 1000;
class FakeDate extends Date { static now() { return (now += 100); } }
const sb = { console, Math, Date: FakeDate, Float32Array, Float64Array, Int32Array, Uint8Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
const run = (code) => vm.runInContext(code, sb);
let seed = 1029;
const rand = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
const N = 600, nodes = [], edges = [];
for (let i = 0; i < N; i++) nodes.push({ id: "n" + i, group: "g" + (i % 6), r: 6 });
while (edges.length < 1100) {
  const a = Math.floor(rand() * N), b = Math.floor(rand() * N);
  if (a !== b) edges.push({ source: "n" + a, target: "n" + b, kind: "link" });
}
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
  params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, curved: true, shape: "organic" },
  world: { left: -1500, top: -1500, right: 1500, bottom: 1500, aspect: 1 } } });
run("stopLoop()");
const place = nodes.map(() => [-1400 + rand() * 2800, -1400 + rand() * 2800]);
run(`(() => { const p = ${JSON.stringify(place)}; nodes.forEach((n, i) => { n.x = p[i][0]; n.y = p[i][1]; n.fx = null; n.fy = null; n.placed = false; }); untangle.done = false; })()`);
run("var counted = 0; var crossingsReal = crossingsOn; crossingsOn = function (m) { counted += 1; return crossingsReal(m); };");
const budget = run("untangleBudget()");
run("untangleLayout()");
console.log(JSON.stringify({ budget, counted: run("counted"), groups: 6 }));
"""


@needs_node
def test_a_pass_keeps_to_its_budget_through_the_category_turns() -> None:
    # Measured in Chromium on the 2,000-note open: one `untangleGroups` call
    # took 7.2 s (161 crossing counts, each over every line) against a pass
    # budget of 0.6 s. With a clock that reads 100 ms later each time, the
    # 600 ms budget allows a handful of counts, not 6 categories x 16 turns.
    out = _run(UNTANGLE, str(FRONTEND))
    assert out["budget"] == 600, out
    assert out["counted"] <= 12, out
