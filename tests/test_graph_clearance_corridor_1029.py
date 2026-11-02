"""Audit 1029 row 35 (G3): the line-clearance force looks only along each line.

2,000 notes and 3,796 links took 28.7 s to come to rest, and a node profile of
the real worker on that open put 81% of its time in `clearanceForce` (21.4 of
26.3 s): every chord of a long diagonal line scanned every grid cell of its
bounding box, and asked every note in those cells for its nearest point on the
line. The cells now visited are the corridor round the chord (its column's
slice of the line, padded by the reach), and a note is asked only once it is
within its own reach of a chord. These run the real worker in node:
the pushes against a brute-force pass over every (note, line) pair, and the
number of notes asked against the bounding-box scan's.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

SCRIPT = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
const run = (code) => vm.runInContext(code, sb);
// The fixture's shape: 2,000 notes, mostly local links and a long tail.
let seed = 20261029;
const rand = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
const N = 2000, nodes = [], edges = [];
for (let i = 0; i < N; i++) nodes.push({ id: "n" + i, group: "g" + (i % 10), r: 5 + (i % 4) });
while (edges.length < 3800) {
  const a = Math.floor(rand() * N);
  const b = rand() < 0.7 ? (a + 1 + Math.floor(rand() * 20)) % N : Math.floor(rand() * N);
  if (a !== b) edges.push({ source: "n" + a, target: "n" + b, kind: "link" });
}
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
  params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, curved: true, shape: "organic" },
  world: { left: -1700, top: -2000, right: 3100, bottom: 2800, aspect: 0.56 } } });
run("stopLoop()");
// Spread over the world, deterministically, with a few notes held.
const place = nodes.map(() => [-1600 + rand() * 4600, -1900 + rand() * 4600]);
run(`(() => { const p = ${JSON.stringify(place)}; nodes.forEach((n, i) => { n.x = p[i][0]; n.y = p[i][1]; n.vx = 0; n.vy = 0; n.fx = i % 97 === 0 ? n.x : null; n.fy = i % 97 === 0 ? n.y : null; }); })()`);
const pushes = () => run("nodes.map((n) => [n.vx, n.vy])");
run("var asked = 0; var nearestReal = clearNearest; clearNearest = function (n, c) { asked += 1; return nearestReal(n, c); };");
run("clearanceForce()");
const fast = pushes();
const asked = run("asked");
// Brute force: every note against every line, in the same order of lines.
run(`(() => {
  for (const n of nodes) { n.vx = 0; n.vy = 0; }
  for (const link of simulation.force("link").links()) {
    const a = link.source, b = link.target, count = clearCurve(a, b);
    for (const node of nodes) { if (node === a || node === b) continue; nearestReal(node, count); clearPush(node, a, b); }
  }
})()`);
const slow = pushes();
let worst = 0, moved = 0;
fast.forEach((v, i) => { worst = Math.max(worst, Math.abs(v[0] - slow[i][0]), Math.abs(v[1] - slow[i][1])); if (slow[i][0] || slow[i][1]) moved++; });
console.log(JSON.stringify({ asked, worst, moved, links: run("simulation.force('link').links().length") }));
"""


def _run(script: str = SCRIPT) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", script, str(FRONTEND)], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_clearance_pushes_match_every_pair_and_ask_few_notes() -> None:
    out = _run()
    # The pushes are the brute force's (to rounding: the sums run in another order).
    assert out["moved"] > 50, out
    assert out["worst"] < 1e-9, out
    # The bounding-box scan asked 289,939 notes on this map for their nearest
    # point on a line; the corridor with its per-chord check asks 18,202.
    assert out["asked"] < 40_000, out


def test_a_note_flung_far_out_coarsens_the_grid_and_misses_nothing() -> None:
    # The grid is a dense typed array over the notes' extent (2,000 notes,
    # 3,800 links: 42 to 25 ms a call against the Map of lists). One note five
    # million units out would ask for 10^10 cells; the cell doubles instead,
    # and the pushes are still the brute force's.
    far = SCRIPT.replace(
        "const place = nodes.map(() => [-1600 + rand() * 4600, -1900 + rand() * 4600]);",
        "const place = nodes.map(() => [-1600 + rand() * 4600, -1900 + rand() * 4600]); place[3] = [5e6, -5e6];",
    )
    assert far != SCRIPT
    out = _run(far)
    assert out["moved"] > 50, out
    assert out["worst"] < 1e-9, out
