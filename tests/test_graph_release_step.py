"""Releasing a dragged note does not kick its neighbours (LEDGER L8: a single tick
step of 7 px after a drag release).

During a drag the notes a held note links to are off the tether (`following`).
On release the tether came back at full strength in one tick; it is not scaled
by alpha, so a neighbour stretched past its leash went from standing still to
a step of tens of pixels in a single tick. Measured on the real worker in node
(200 notes, seven categories, six notes of four to six links dragged 340 units
and held 60 ticks): the largest rise in a note's per-tick step after release
was 46.7 world units after a 340 unit drag and 6.3 after a 60 unit one; with the tether eased back in over
`TETHER_EASE_TICKS` (30) and a held note let go standing still (`nudgeLetGo`), 5.8 and 2.0. In the app (a scripted drag,
screen px, the largest rise in a note's per-tick step at the release): 7.2 to 0.65 at 60 px, 28.6 to 2.6 at 100.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

SCRIPT = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const timers = [], sent = [];
// A counter clock (as tests/_graph_worker_harness.js's clockStep): the worker's
// time budgets buy the same work on a loaded machine (it failed once under -n 4).
let fakeNow = 1e12;
const clock = class extends Date { static now() { return (fakeNow += 0.05); } };
const sandbox = { console, Math, Date: clock, Float32Array, Map, Set,
  setTimeout: (fn) => { timers.push(fn); return timers.length; }, clearTimeout: () => {},
  setInterval: () => 0, clearInterval: () => {}, performance: { now: () => clock.now() },
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
const DIST = Number(process.argv[2]);
const picks = [...nb.entries()].filter(([, l]) => l.length >= 4 && l.length <= 6).map(([id]) => id).slice(0, 6);
const all = () => last.slice();
let worst = 0, worstFirst = 0;
for (const id of picks) {
  const from = at(id);
  send({ type: "drag", phase: "start", id, x: from[0], y: from[1] });
  const angle = rnd() * Math.PI * 2;
  const drop = [from[0] + DIST * Math.cos(angle), from[1] + DIST * Math.sin(angle)];
  for (let s = 1; s <= 10; s++) { send({ type: "drag", phase: "move", id, x: from[0] + (drop[0] - from[0]) * s / 10, y: from[1] + (drop[1] - from[1]) * s / 10 }); spin(3); }
  spin(60);
  const frames = [all()];
  const step = () => { timers.length && timers.shift()(); drain(); frames.push(all()); };
  for (let i = 0; i < 2; i++) step();
  const mark = frames.length - 1;
  send({ type: "drag", phase: "end", id, keep: false });
  for (let i = 0; i < 14; i++) step();
  // The largest rise in any note's per-tick step from one tick to the next, from the release on.
  for (let t = mark + 1; t < frames.length; t++) {
    const a = frames[t - 2], b = frames[t - 1], c = frames[t];
    for (const n of [id, ...nb.get(id)]) {
      const s1 = Math.hypot(b[n * 2] - a[n * 2], b[n * 2 + 1] - a[n * 2 + 1]);
      const s2 = Math.hypot(c[n * 2] - b[n * 2], c[n * 2 + 1] - b[n * 2 + 1]);
      worst = Math.max(worst, s2 - s1);
    }
  }
}
console.log(JSON.stringify({ worst }));
"""


@needs_node
@pytest.mark.parametrize(("distance", "limit"), [(340, 10), (60, 4)])
def test_a_release_does_not_jump_its_neighbours_in_one_tick(distance: int, limit: int) -> None:
    out = json.loads(
        subprocess.run(
            ["node", "-e", SCRIPT, str(ROOT / "frontend"), str(distance)],
            capture_output=True,
            text=True,
            check=True,
            timeout=110,
        ).stdout
    )
    assert out["worst"] < limit, out
