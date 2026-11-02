"""Audit 1031 GR1, second try (ranked row 19, 2026-11-02): the clearance force's share of a cold settle.

The line-clearance force (Tidy spacing on) was 5.2 s of a 9.9 s init to end on
the 2,000-note fixture (126 calls, 41 ms each, `wb.js` in the agent's scratch
dir). The first 60 ticks only shape the layout while it is hot, so the force
runs on every second one of them; every tick after runs it, and so does a
drag. These run the real worker in node.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
WORKER = (FRONTEND / "js" / "graph-worker.js").read_text(encoding="utf-8")

SCRIPT = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
const N = 60, nodes = [], edges = [];
for (let i = 0; i < N; i++) nodes.push({ id: i, group: "g" + (i % 4), r: 8 });
for (let i = 1; i < N; i++) edges.push({ source: i, target: (i * 7) % i, kind: "link" });
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
  params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, tidy: process.argv[2] === "1", curved: true, shape: "organic" },
  world: { left: -600, top: -600, right: 600, bottom: 600, aspect: 1 } } });
const run = (code) => vm.runInContext(code, sb);
const links = run("simulation.force('link').links().length");
const stamps = [], gains = [];
for (let t = 1; t <= 70; t++) { run("simulation.tick()"); stamps.push(run("clear.stamp")); gains.push(run("clear.gain")); }
console.log(JSON.stringify({ links, stamps, gains, lean: run("CLEAR_LEAN_TICKS") }));
"""


def _run(tidy: bool) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", SCRIPT, str(FRONTEND), "1" if tidy else "0"], capture_output=True, text=True, timeout=100)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


def test_the_clearance_force_runs_on_every_second_tick_of_the_first_sixty_only():
    out = _run(True)
    links, stamps = out["links"], out["stamps"]
    assert out["lean"] == 60
    # One stamp per link per run: 30 runs by tick 60, then one every tick.
    assert stamps[59] == 30 * links
    assert stamps[69] == (30 + 10) * links
    # The schedule alternates (run, skip) from the first tick.
    assert [stamps[t] - stamps[t - 1] for t in range(1, 6)] == [0, links, 0, links, 0]
    assert stamps[0] == links
    # A tick that runs in the lean stretch pushes twice as hard (the skipped
    # tick's share: with the plain skip the clusters fixture of
    # test_graph_layout.py ended with two lines through notes); after it, once.
    assert out["gains"][:4] == [2, 1, 2, 1]
    assert set(out["gains"][60:]) == {1}


def test_the_lean_schedule_is_counted_from_each_init_not_from_the_worker_start():
    assert "clear.lean = CLEAR_LEAN_TICKS;" in WORKER
    init = WORKER[WORKER.index('case "init": {') :]
    assert init.index("clear.lean = CLEAR_LEAN_TICKS;") < init.index("simulation = d3")


def test_a_map_with_tidy_off_never_calls_the_force():
    out = _run(False)
    assert out["stamps"][-1] == 0


PUSHES = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1], longCells = process.argv[2];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
const text = fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8");
const patched = text.replace("const CLEAR_LONG_CELLS = 4;", "const CLEAR_LONG_CELLS = " + longCells + ";");
if (patched === text && longCells !== "4") throw new Error("constant not found");
vm.runInContext(patched, sb);
let seed = 20261102;
const rand = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
const N = 600, nodes = [], edges = [];
for (let i = 0; i < N; i++) nodes.push({ id: "n" + i, group: "g" + (i % 6), r: 5 + (i % 4) });
while (edges.length < 1000) {
  const a = Math.floor(rand() * N), b = Math.floor(rand() * N);
  if (a !== b) edges.push({ source: "n" + a, target: "n" + b, kind: "link" });
}
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
  params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, tidy: true, curved: true, shape: "organic" },
  world: { left: -1500, top: -1500, right: 1500, bottom: 1500, aspect: 1 } } });
const run = (code) => vm.runInContext(code, sb);
run("stopLoop()");
const place = nodes.map(() => [-1400 + rand() * 2800, -1400 + rand() * 2800]);
run(`(() => { const p = ${JSON.stringify(place)}; nodes.forEach((n, i) => { n.x = p[i][0]; n.y = p[i][1]; n.vx = 0; n.vy = 0; }); clear.lean = 0; })()`);
run("clearanceForce()");
console.log(JSON.stringify({ v: run("nodes.map((n) => [n.vx, n.vy])") }));
"""


def _pushes(long_cells: str) -> list:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", PUSHES, str(FRONTEND), long_cells], capture_output=True, text=True, timeout=100)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])["v"]


def test_a_long_chord_read_as_one_run_per_column_pushes_exactly_as_cell_by_cell_does():
    # 1e9 cells: no chord is long, so every column is read cell by cell, as before.
    # Measured: 183 against 205 ms a call on the 2,000-note spread map (the
    # pushes' checksum identical to the last digit).
    runs = _pushes("4")
    cells = _pushes("1e9")
    assert any(v != [0, 0] for v in runs)
    assert runs == cells


def test_the_long_chord_run_is_in_the_source():
    assert "const CLEAR_LONG_CELLS = 4;" in WORKER
    assert "gy += long ? y1 - y0 + 1 : 1" in WORKER
