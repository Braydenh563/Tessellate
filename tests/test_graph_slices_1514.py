"""INBOX 1514: the hidden untangle and cleanup no longer block the worker.

A pass was one call of up to 600 ms (the cleanup another), so a drag or new
settings waited for it (a 500-note spread change: one worker turn of 601 ms). They are
generators now, cut into `PENDING_SLICE_MS` slices by `settleUntangled`. These
run the real worker in node: cut into the smallest slices, the layout is the
one the unsliced call makes (the budget is `workNow`, the time spent inside
slices, and an unbounded budget makes both runs end by convergence), a
message heard mid-pass puts the notes back where the screen shows them.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
WORKER = (FRONTEND / "js" / "graph-worker.js").read_text(encoding="utf-8")


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script, str(FRONTEND)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


# Six categories of seven notes, hubs and chains, bridges by a fixed sequence
# (no random source): the seed test_graph_untangle_1400.py uses.
HEAD = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
function world() {
  const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Map, Set,
    setTimeout: () => 1, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {}, postMessage: () => {} };
  sb.self = sb;
  sb.importScripts = (u) => vm.runInContext(fs.readFileSync(path.join(root, u.replace(/^\//, "")), "utf8"), sb);
  vm.createContext(sb);
  vm.runInContext(fs.readFileSync(path.join(root, "js", "graph-worker.js"), "utf8"), sb);
  const groups = ["Work", "Travel", "Cooking", "Reading", "Health", "Ideas"];
  const nodes = [], edges = [];
  groups.forEach((g, gi) => { for (let i = 0; i < 7; i++) nodes.push({ id: gi * 7 + i, group: g, r: i ? 8 : 12 }); });
  groups.forEach((g, gi) => { for (let i = 1; i < 7; i++) edges.push({ source: gi * 7 + (i % 2 ? 0 : i - 1), target: gi * 7 + i, kind: "link" }); });
  for (let gi = 1; gi < 6; gi++) for (const i of [1, 4]) edges.push({ source: gi * 7 + i, target: 0, kind: "link" });
  let seq = 7;
  for (let b = 0; b < 12; b++) { seq = (seq * 31 + 11) % 42; const a = seq; seq = (seq * 17 + 5) % 42; if (Math.floor(a / 7) !== Math.floor(seq / 7)) edges.push({ source: a, target: seq, kind: "link" }); }
  sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
    params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, curved: true, shape: "organic" },
    world: { left: -900, top: -700, right: 900, bottom: 700, aspect: 0.6 } } });
  const run = (code) => vm.runInContext(code, sb);
  run("function untangleBudget() { return 1e9; }");
  for (let t = 0; t < 2000 && run("simulation.alpha() >= simulation.alphaMin()"); t++) run("simulation.tick(); clampToWorld();");
  return run;
}
const positions = (run) => run("nodes.map((n) => [Math.round(n.x * 1e6) / 1e6, Math.round(n.y * 1e6) / 1e6])");
"""

SAME = HEAD + r"""
const a = world();
a("untangleLayout(); landTargets();");
const whole = positions(a);
const b = world();
// The smallest slice there is: every checkpoint yields.
const slices = b(`(() => {
  untangle.done = false;
  const gen = untangleLayoutSteps();
  let n = 0;
  for (;;) { n += 1; const out = sliceRun(gen, Date.now() - 1); if (out) { landTargets(); return n; } }
})()`);
const cut = positions(b);
console.log(JSON.stringify({ same: JSON.stringify(whole) === JSON.stringify(cut), slices }));
"""

SETTLE = HEAD + r"""
const a = world();
a("settleUntangled(Infinity, 0, 0)");
const whole = positions(a);
const b = world();
let calls = 0, answer = false;
while (answer !== true && calls < 100000) { calls += 1; answer = b("settleUntangled(Date.now() + 2, 0, 0)"); }
const cut = positions(b);
console.log(JSON.stringify({ same: JSON.stringify(whole) === JSON.stringify(cut), calls, holding: b("untangle.holding"), cleaned: b("untangle.cleaned") }));
"""

CANCEL = HEAD + r"""
const run = world();
run("pendingStart(false, false, false)");
const start = positions(run);
let calls = 0;
while (!run("untangle.run") && calls < 100000) { calls += 1; run("settleUntangled(Date.now() + 2, 0, 0)"); }
run("settleUntangled(Date.now() + 2, 0, 0)");
const midPass = run("Boolean(untangle.run)");
// Notes standing on trial places: what a cancelled pass must not leave.
run("for (const n of nodes) { n.x += 123; }");
run("onmessage_cancel = pendingCancel(); void onmessage_cancel;");
const back = positions(run);
console.log(JSON.stringify({ midPass, running: run("Boolean(untangle.run) || Boolean(untangle.tidy)"), back: JSON.stringify(back) === JSON.stringify(start) }));
"""


def test_a_pass_cut_into_the_smallest_slices_makes_the_same_layout() -> None:
    out = _node(SAME)
    assert out["same"] is True, out
    # It really was cut: a pass over 42 notes yields at its notes, turns and trials.
    assert out["slices"] > 10, out


def test_settling_in_slices_ends_where_settling_in_one_call_does() -> None:
    out = _node(SETTLE)
    assert out["same"] is True, out
    assert out["calls"] > 10 and out["holding"] is True and out["cleaned"] is True, out


def test_a_message_mid_pass_puts_the_notes_back_and_drops_the_pass() -> None:
    out = _node(CANCEL)
    assert out["midPass"] is True, out
    assert out["running"] is False and out["back"] is True, out


def test_the_slices_are_the_only_way_the_hidden_phase_runs() -> None:
    settle = WORKER[WORKER.index("\nfunction settleUntangled(") :]
    settle = settle[: settle.index("\n}\n")]
    # No whole-pass call is left in the slice path: a pass or cleanup is resumed, not run to its end.
    assert "untangleLayout()" not in settle and "untangleCleanup()" not in settle
    assert "sliceRun(untangle.run, until)" in settle and "sliceRun(untangle.tidy, until)" in settle
    # Budgets run on the work done inside slices, not on the clock the gaps between them move.
    steps = WORKER[WORKER.index("\nfunction* untangleLayoutSteps(") :]
    steps = steps[: steps.index("\n}\n")]
    assert "Date.now()" not in steps and "workNow() + untangleBudget()" in steps
    cleanup = WORKER[WORKER.index("\nfunction* untangleCleanupSteps(") :]
    cleanup = cleanup[: cleanup.index("\n}\n")]
    assert "Date.now()" not in cleanup
