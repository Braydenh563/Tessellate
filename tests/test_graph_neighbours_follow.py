"""A dragged note's neighbours follow it (graph100-1011, "Open": neighbours
barely follow a drag).

Measured on the real worker in node: 200 notes in seven categories, about as
many links as notes, hubs and leaves; six notes of four to six links each
dragged 340 units and held 90 ticks. The notes they link to moved 102 of the
340 units before (30%) and 208 after (61%); once released and settled, 81 and
156. In the app (`scratchpad/ui-sweeps/graphdrag1018.js`, 200 notes, a 308 unit
drag held 1.5 s): 0.28 of the distance before, 0.48 after; 0.28 and 0.40 settled. The category pull and the tether stood between a link and the note it
joined; for the length of a drag the neighbours keep a quarter of the pull home,
are off the tether and are drawn by a soft elastic toward where they stood
relative to the held note (`carryForce`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKER = (ROOT / "frontend" / "js" / "graph-worker.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

SCRIPT = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const timers = [], sent = [];
const sandbox = { console, Math, Date, Float32Array, Map, Set,
  setTimeout: (fn) => { timers.push(fn); return timers.length; }, clearTimeout: () => {},
  setInterval: () => 0, clearInterval: () => {}, performance: { now: () => Date.now() },
  postMessage: (m) => sent.push(m) };
sandbox.self = sandbox;
vm.createContext(sandbox);
sandbox.importScripts = (url) => { const f = path.join(root, url.replace(/^\//, "")); vm.runInContext(fs.readFileSync(f, "utf8"), sandbox); };
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sandbox);
let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const N = 200, C = 7;
const nodes = Array.from({ length: N }, (_, i) => ({ id: i, r: 7, group: "c" + (i % C) }));
const edges = [], seen = new Set();
const core = Array.from({ length: Math.ceil(N * 0.65) }, (_, i) => i);
for (let m = 0, g = 0; m < N && g < N * 6; g++) {
  const a = core[Math.floor(Math.pow(rnd(), 2) * core.length)], b = core[Math.floor(rnd() * core.length)];
  if (a === b || seen.has(a + "-" + b) || seen.has(b + "-" + a)) continue;
  seen.add(a + "-" + b); edges.push({ source: a, target: b, kind: "link" }); m++;
}
const nb = new Map();
for (const e of edges) for (const [x, y] of [[e.source, e.target], [e.target, e.source]]) { if (!nb.has(x)) nb.set(x, []); nb.get(x).push(y); }
const send = (data) => sandbox.onmessage({ data });
let last = null;
const drain = () => { for (const m of sent) if (m.type === "tick") last = Array.from(m.positions); sent.length = 0; sandbox.onmessage({ data: { type: "recycle", buffer: new Float32Array(N * 2).buffer } }); };
const spin = (most) => { for (let i = 0; i < most && timers.length; i++) { timers.shift()(); drain(); } drain(); };
const at = (id) => [last[id * 2], last[id * 2 + 1]];
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
send({ type: "init", epoch: 1, nodes, edges, params: { gravity: 50, spread: 50, lengthByScore: true, groupBy: true, orbit: true }, world: { left: -900, top: -900, right: 900, bottom: 900, aspect: 0.5 }, alpha: 1 });
spin(3000);
const picks = [...nb.entries()].filter(([, l]) => l.length >= 4 && l.length <= 6).map(([id]) => id).slice(0, 6);
const held = [], rest = [];
for (const id of picks) {
  const before = Object.fromEntries([id, ...nb.get(id)].map((i) => [i, at(i)]));
  const from = at(id);
  send({ type: "drag", phase: "start", id, x: from[0], y: from[1] });
  const angle = rnd() * Math.PI * 2;
  const drop = [from[0] + 340 * Math.cos(angle), from[1] + 340 * Math.sin(angle)];
  for (let s = 1; s <= 10; s++) { send({ type: "drag", phase: "move", id, x: from[0] + (drop[0] - from[0]) * s / 10, y: from[1] + (drop[1] - from[1]) * s / 10 }); spin(3); }
  spin(60);
  held.push(nb.get(id).reduce((a, n) => a + dist(at(n), before[n]), 0) / nb.get(id).length / 340);
  send({ type: "drag", phase: "end", id, keep: false });
  spin(600);
  rest.push(nb.get(id).reduce((a, n) => a + dist(at(n), before[n]), 0) / nb.get(id).length / 340);
}
const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
console.log(JSON.stringify({ held: mean(held), rest: mean(rest), picks: picks.length }));
"""


@needs_node
def test_a_dragged_notes_neighbours_follow_it() -> None:
    out = json.loads(subprocess.run(["node", "-e", SCRIPT, str(ROOT / "frontend")], capture_output=True, text=True, check=True, timeout=110).stdout)
    assert out["picks"] >= 4, out
    # 0.30 before the elastic, 0.61 after.
    assert out["held"] >= 0.45, out
    # And it is not a rigid carry: the neighbourhood is not a rigid body.
    assert out["held"] <= 0.85, out
    # Settled after the drop they stay nearer the dropped note than before (0.24).
    assert out["rest"] >= 0.36, out


def test_the_elastic_is_a_force_of_the_layout_and_ends_with_the_drag() -> None:
    assert 'force("carry", carryForce)' in WORKER
    start = WORKER.index("function carryForce(")
    body = WORKER[start : WORKER.index("carryForce.initialize", start)]
    assert "f.node.fx != null" in body, "a pinned neighbour is never moved"
    end = WORKER[WORKER.index('} else {\n        dragging = false;\n        dragOrigin = null;') :][:200]
    assert "markFollowers(node, false)" in end, "the release clears the followers"
    init = WORKER[WORKER.index('case "init": {') :][:300]
    assert "carry.node = null" in init, "a new layout starts with nothing carried"
