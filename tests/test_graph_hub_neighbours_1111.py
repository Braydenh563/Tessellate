"""A hub's neighbours trade places when that lowers the crossings (graph-1030.md:35, w34-def1-1111).

The hub rings move a well-linked note across its category; nothing moved the
order its lines leave in. `untangleFanSteps` swaps two of a hub's neighbours
when the lines on both cross less afterwards and both stay inside their
category's reach and clear of the rest. Numbers (36-note seed) in
docs/roadmap/agent-remaining/w34-def1-1111.md.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
WORKER = (FRONTEND / "js" / "graph-worker.js").read_text(encoding="utf-8")

# A hub (0) with five neighbours; neighbours 1 and 2 each reach a far note (6, 7)
# on the other side, so their lines cross each other and the hub's other lines
# (5 crossings). Trading 1 and 2 uncrosses all of them.
SCRIPT = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Uint32Array, Map, Set,
  setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
sb.self = sb;
sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
vm.createContext(sb);
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
const where = [[0, 0], [100, 0], [-100, 0], [0, -120], [0, 120], [60, 130], [-300, 100], [300, 100]];
const nodes = where.map((_, id) => ({ id, group: "A", r: 8 }));
const edges = [[0, 1], [0, 2], [0, 3], [0, 4], [0, 5], [1, 6], [2, 7]].map(([source, target]) => ({ source, target, kind: "link" }));
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
  params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, tidy: true, curved: true, shape: "organic" },
  world: { left: -900, top: -700, right: 900, bottom: 700, aspect: 0.6 } } });
const run = (code) => vm.runInContext(code, sb);
run(`nodes.forEach((n, i) => { n.x = ${JSON.stringify(where)}[i][0]; n.y = ${JSON.stringify(where)}[i][1]; n.vx = 0; n.vy = 0; });`);
run("untangleReach()");
const count = () => run("crossingsOn(untangle.edges.map((_, i) => i))");
const before = count();
const gained = run("untangleFanSteps(0, (n) => n.fx != null || n.placed, Infinity).next().value");
const after = count();
const moved = run("nodes.map((n, i) => [i, n.x, n.y])").filter(([i, x, y]) => x !== where[i][0] || y !== where[i][1]).map(([i]) => i);
const pinned = run("(() => { nodes[1].fx = 100; nodes[2].placed = true; return untangleFanSteps(0, (n) => n.fx != null || n.placed, Infinity).next().value; })()");
console.log(JSON.stringify({ before, after, gained, moved, pinned }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_two_neighbours_of_a_hub_trade_places_when_their_far_lines_cross() -> None:
    run = subprocess.run(["node", "-e", SCRIPT, str(FRONTEND)], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr[-2000:]
    out = json.loads(run.stdout.strip().splitlines()[-1])
    assert out["before"] == 5 and out["after"] == 0, out
    assert out["gained"] == out["before"], out
    assert out["moved"] == [1, 2], out
    # With one of the pair pinned the trade is off, and the step reports nothing.
    assert out["pinned"] == 0, out


def test_the_sweep_runs_for_every_hub_inside_the_pass_budget() -> None:
    body = WORKER[WORKER.index("function* untangleLayoutSteps()") :]
    body = body[: body.index("return untangleGlide(startX, startY);")]
    assert "untangle.incident[i].length <= UNTANGLE_MOVE_LINKS) continue;" in body
    assert "gained += yield* untangleFanSteps(i, still, until);" in body
    assert "workNow() < until" in body[body.index("untangleFanSteps") - 200 : body.index("untangleFanSteps")]
    step = WORKER[WORKER.index("function* untangleFanSteps(") :]
    step = step[: step.index("\n}\n")]
    # A trade keeps both notes inside their category and clear of the rest, and is undone otherwise.
    assert "untangleInside(u) && untangleInside(v) && untangleFree(u," in step
    assert "if (workNow() >= until) return gained;" in step
