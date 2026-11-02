"""A small drag is a local nudge (INBOX 1517, the owner: "the more I slightly
move nodes on the graph, all of it really starts to bunch up and get closer
together until they are all really close").

Measured on the real worker in node: 200 notes in seven categories settled,
then ten small drags (a note moved 8 units and let go), the layout let rest
after each. The mean link length and the mean distance from the centre are read
after every release; the notes far from the held one are tracked too.
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
const root = process.argv[1], N = +process.argv[2], DIST = +process.argv[3], TIDY = process.argv[4] === "1";
const timers = [], sent = [];
const sandbox = { console, Math, Date, Float32Array, Map, Set,
  setTimeout: (fn) => { timers.push(fn); return timers.length; }, clearTimeout: () => {},
  setInterval: () => 0, clearInterval: () => {}, performance: { now: () => Date.now() },
  postMessage: (m) => sent.push(m) };
sandbox.self = sandbox;
vm.createContext(sandbox);
sandbox.importScripts = (url) => { const f = path.join(root, url.replace(/^\//, "")); vm.runInContext(fs.readFileSync(f, "utf8"), sandbox); };
vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sandbox);
let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const C = 7;
const nodes = Array.from({ length: N }, (_, i) => ({ id: i, r: 7, group: "c" + (i % C) }));
const edges = [], seen = new Set();
for (let m = 0, g = 0; m < N * 1.2 && g < N * 8; g++) {
  const a = Math.floor(rnd() * N), b = rnd() < 0.7 ? (Math.floor(a / C) * C + Math.floor(rnd() * C)) % N : Math.floor(rnd() * N);
  if (a === b || seen.has(a + "-" + b) || seen.has(b + "-" + a)) continue;
  seen.add(a + "-" + b); edges.push({ source: a, target: b, kind: "link" }); m++;
}
const send = (data) => sandbox.onmessage({ data });
let last = null;
const drain = () => { for (const m of sent) if (m.type === "tick") last = Array.from(m.positions); sent.length = 0; sandbox.onmessage({ data: { type: "recycle", buffer: new Float32Array(N * 2).buffer } }); };
const spin = (most) => { for (let i = 0; i < most && timers.length; i++) { timers.shift()(); drain(); } drain(); };
const at = (id) => [last[id * 2], last[id * 2 + 1]];
const stats = () => {
  let cx = 0, cy = 0; for (let i = 0; i < N; i++) { cx += last[i * 2]; cy += last[i * 2 + 1]; } cx /= N; cy /= N;
  let spread = 0; for (let i = 0; i < N; i++) spread += Math.hypot(last[i * 2] - cx, last[i * 2 + 1] - cy);
  let link = 0; for (const e of edges) link += Math.hypot(last[e.source * 2] - last[e.target * 2], last[e.source * 2 + 1] - last[e.target * 2 + 1]);
  return { link: link / edges.length, spread: spread / N };
};
send({ type: "init", epoch: 1, nodes, edges, params: { gravity: 50, spread: 50, lengthByScore: true, groupBy: true, orbit: true, tidy: TIDY }, world: { left: -900, top: -900, right: 900, bottom: 900, aspect: 0.5 }, alpha: 1 });
spin(6000);
const start = stats();
let far = 0, farN = 0;
const rows = [];
for (let d = 1; d <= 10; d++) {
  const id = (d * 17) % N, from = at(id), before = Array.from(last);
  send({ type: "drag", phase: "start", id, x: from[0], y: from[1] });
  for (let s = 1; s <= 4; s++) { send({ type: "drag", phase: "move", id, x: from[0] + DIST * s / 4 * (d % 2 ? 1 : -1), y: from[1] + DIST * s / 8 }); spin(3); }
  send({ type: "drag", phase: "end", id, keep: false });
  spin(800);
  rows.push(stats());
  // notes more than 150 units from the held one: how far did they go in this drag
  for (let i = 0; i < N; i++) if (Math.hypot(before[i * 2] - from[0], before[i * 2 + 1] - from[1]) > 150) { far += Math.hypot(last[i * 2] - before[i * 2], last[i * 2 + 1] - before[i * 2 + 1]); farN++; }
}
const end = rows[rows.length - 1];
console.log(JSON.stringify({ start, end, linkRatio: end.link / start.link, spreadRatio: end.spread / start.spread, farMove: far / farN, rows: rows.map((r) => [+r.link.toFixed(1), +r.spread.toFixed(1)]) }));
"""


def _run(n: int, dist: int, tidy: bool = True) -> dict:
    args = [str(ROOT / "frontend"), str(n), str(dist), "1" if tidy else "0"]
    out = subprocess.run(["node", "-e", SCRIPT, *args], capture_output=True, text=True, check=True, timeout=110)
    return json.loads(out.stdout)


@needs_node
@pytest.mark.parametrize("n", [40, 200])
def test_ten_small_drags_leave_the_layout_where_it_was(n: int) -> None:
    # Measured (1517) with the clearance pass, which ran always until Tidy
    # spacing made it a switch (INBOX 1529); the default is below.
    out = _run(n, 8)
    # The layout is the same size after ten nudges, not smaller and not larger.
    assert 0.97 <= out["linkRatio"] <= 1.03, out
    assert 0.97 <= out["spreadRatio"] <= 1.03, out
    # A note far from the held one stays put (px per drag, the mean over the far notes).
    assert out["farMove"] <= 1.5, out


@needs_node
def test_with_tidy_spacing_off_a_drag_adds_no_drift_of_its_own() -> None:
    """With Tidy spacing off (the default since 1529) ten releases at 40 notes
    shorten the links 3.4% with no movement at all (0.966; 0.964 with 8-unit
    drags): each release re-warms a layout that stopped short of rest. So
    the nudge is held to that control, and the far notes still stay put."""
    moved, still = _run(40, 8, tidy=False), _run(40, 0, tidy=False)
    assert abs(moved["linkRatio"] - still["linkRatio"]) <= 0.01, (moved, still)
    assert abs(moved["spreadRatio"] - still["spreadRatio"]) <= 0.015, (moved, still)
    assert 0.97 <= moved["spreadRatio"] <= 1.03, moved
    assert moved["farMove"] <= 1.5, moved


WORKER = (ROOT / "frontend" / "js" / "graph-worker.js").read_text(encoding="utf-8")


def test_the_hold_is_a_force_and_every_new_layout_clears_it() -> None:
    assert 'force("nudge", nudgeForce)' in WORKER
    for case in ('case "init": {', 'case "params":', 'case "reshuffle":', 'case "stop":'):
        assert "nudgeEnd();" in WORKER[WORKER.index(case) :][:600], case
    settled = WORKER[WORKER.index("  if (settled) {\n    nudgeEnd();") :][:120]
    assert "post(true)" in settled, "a map at rest lets go of the held notes"
    # A real drag is not held back: the share falls to nothing at the full distance.
    assert "1 - t * t * (3 - 2 * t)" in WORKER
