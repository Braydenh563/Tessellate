"""W34 "Incremental crossing count per turned category": `crossingsOn` read every
line of the map for each line it was asked about, 587 ms of a 2.6 s settle at
2,000 notes under node, 96% of the untangle pass. Past `CROSS_GRID_MIN` lines it
now reads only the lines in the grid cells each one's box touches
(`crossingsGridded`). The count must be the brute loop's, pair for pair."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

SCRIPT = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Uint32Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
let seed = 7;
const rnd = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
const N = 600;
const nodes = Array.from({ length: N }, (_, id) => ({ id, group: "g" + (id % 5), r: 7 }));
const pairs = new Set();
const edges = [];
while (edges.length < 1400) {
  const a = Math.floor(rnd() * N);
  const b = rnd() < 0.15 ? Math.floor(rnd() * N) : (a + 1 + Math.floor(rnd() * 20)) % N;
  const key = Math.min(a, b) + ":" + Math.max(a, b);
  if (a === b || pairs.has(key)) continue;
  pairs.add(key);
  edges.push({ source: a, target: b, kind: "link" });
}
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
  params: { gravity: 50, spread: 50, linkForce: 50, groupBy: true, shape: "organic" },
  world: { left: -900, top: -700, right: 900, bottom: 700, aspect: 0.6 } } });
const run = (code) => vm.runInContext(code, sb);
run(`untangleSetup(${JSON.stringify(edges)})`);
const out = [];
for (let trial = 0; trial < 6; trial++) {
  const where = nodes.map((_, i) => [rnd() * 1600 - 800, (i % 5) * 40 + rnd() * 900 - 450]);
  run(`nodes.forEach((n, i) => { n.x = ${JSON.stringify(where)}[i][0]; n.y = ${JSON.stringify(where)}[i][1]; });`);
  for (const size of [16, 60, 400, 1400]) {
    const mine = [];
    const pick = new Set();
    while (mine.length < size) { const k = Math.floor(rnd() * 1400); if (!pick.has(k)) { pick.add(k); mine.push(k); } }
    const grid = run(`crossingsOn(${JSON.stringify(mine)})`);
    // The rule written out once more, every pair read: one line in `mine`, no shared end, a pair inside `mine` once.
    const brute = run(`(() => { const mine = ${JSON.stringify(mine)}; const inMine = new Set(mine); let n = 0;
      const E = untangle.edges;
      for (const i of mine) for (let j = 0; j < E.length; j++) {
        if (j === i || (inMine.has(j) && j < i)) continue;
        const [a, b] = E[i]; const [c, d] = E[j];
        if (c === a || c === b || d === a || d === b) continue;
        if (segmentsCross(nodes[a].x, nodes[a].y, nodes[b].x, nodes[b].y, nodes[c].x, nodes[c].y, nodes[d].x, nodes[d].y)) n += 1;
      }
      return n; })()`);
    out.push([size, grid, brute]);
  }
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_grid_count_is_the_brute_count() -> None:
    run = subprocess.run(["node", "-e", SCRIPT, str(FRONTEND)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-2000:]
    rows = json.loads(run.stdout.strip().splitlines()[-1])
    assert len(rows) == 24
    for size, grid, brute in rows:
        assert grid == brute, (size, grid, brute)
    assert any(brute > 50 for _, _, brute in rows)
