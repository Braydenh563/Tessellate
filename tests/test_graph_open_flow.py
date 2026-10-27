"""The graph opens settled and flows to rest (the owner, 2026-10-27).

"ok I just loaded up the graph and it appeard solid then a bunch of nodes
started individually rearranging themselves sliding instantly into position
one after the other and then it juststayed like that and didnt nicely settle
until I slightly adjusted one of them" and "the opening of the graph is very
very not plesant to look at all the adjusting and it is very ridgid and
mechanical. I want tit to be smooth and flowy".

Measured before (`graphopen.js` in the agent's scratchpad, a cold open at
1440x900): 36 notes, a node moved 134 px in one frame and 37 frames moved one
over 20 px, at rest 3.8 s after the first paint; 300 notes, 23 frames over 20
px and 10.6 s to rest, in four bursts (the untangle passes and the cleanup,
each a 12-frame glide whose first frame closed a quarter of the way). The
worker now settles, untangles and cleans out of sight before its first post
(`pending`, `settleUntangled`) and plays one eased motion into the result
(`introInto`); a correction after paint is one glide of every note together
(`settleGlideFrom`). These run the shipped worker in node.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
WORKER = (FRONTEND / "js" / "graph-worker.js").read_text(encoding="utf-8")
CANVAS = (FRONTEND / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _node(script: str, *args: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script, str(FRONTEND), *args], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout.strip().splitlines()[-1])


# Six categories of seven notes, a hub in each and bridges by a fixed sequence
# (the 1400 untangle fixture); every message the worker posts is kept with the
# untangle state at the moment it was posted.
OPEN = r"""
const fs = require("fs"), path = require("path"), vm = require("vm");
const root = process.argv[1];
const mode = process.argv[2];
const sent = [], timers = [];
const sb = { console, Math, Date, Float32Array, Float64Array, Int32Array, Uint8Array, Map, Set,
  setTimeout: (fn) => { timers.push(fn); return timers.length; }, clearTimeout: () => {}, setInterval: () => 1, clearInterval: () => {},
  performance: { now: () => Date.now() } };
sb.self = sb;
sb.postMessage = (m) => sent.push({ m, passes: vm.runInContext("untangle.passes", sb), cleaned: vm.runInContext("untangle.cleaned", sb), after: Boolean(sb.__starts) });
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
const run = (code) => vm.runInContext(code, sb);
let starts = 0, glides = 0;
if (mode === "live") {
  run("pendingStart = ((f) => function (...a) { globalThis.__starts = (globalThis.__starts || 0) + 1; return f.apply(this, a); })(pendingStart)");
  run("settleGlideFrom = ((f) => function (...a) { const n = f.apply(this, a); if (n) globalThis.__glides = (globalThis.__glides || 0) + 1; return n; })(settleGlideFrom)");
}
sb.onmessage({ data: { type: "init", epoch: 1, nodes, edges, alpha: 1,
  warm: mode !== "live", intro: mode === "intro", bloom: mode === "intro",
  params: { gravity: 50, spread: 50, linkForce: 50, lengthByScore: true, groupBy: true, orbit: true, curved: true, shape: "organic" },
  world: { left: -900, top: -700, right: 900, bottom: 700, aspect: 0.6 } } });
let guard = 0;
while (timers.length && guard++ < 20000 && !sent.some((s) => s.m.type === "end")) {
  timers.shift()();
  sb.onmessage({ data: { type: "recycle", buffer: new Float32Array(nodes.length * 2).buffer } });
}
const kinds = sent.map((s) => s.m.type);
const ticks = sent.filter((s) => s.m.type === "tick");
let maxMove = 0, jumps = 0, jumpsAfter = 0;
for (let f = 1; f < ticks.length; f++) {
  const a = ticks[f - 1].m.positions, b = ticks[f].m.positions;
  let m = 0;
  for (let j = 0; j < b.length; j += 2) m = Math.max(m, Math.hypot(b[j] - a[j], b[j + 1] - a[j + 1]));
  maxMove = Math.max(maxMove, m);
  if (m > 20) jumps++;
  if (m > 20 && ticks[f - 1].after) jumpsAfter++;
}
const last = ticks[ticks.length - 1], intros = ticks.filter((s) => s.m.intro);
const lastIntro = intros[intros.length - 1];
const frame = sent.find((s) => s.m.type === "frame");
const final = Array.from(last.m.positions);
console.log(JSON.stringify({
  kinds: kinds.filter((k, i) => k !== kinds[i - 1]),
  ticks: ticks.length, intros: intros.length,
  firstTick: { passes: ticks[0].passes, cleaned: ticks[0].cleaned, intro: Boolean(ticks[0].m.intro), alpha: ticks[0].m.alpha },
  lastRunning: last.m.running, ended: kinds[kinds.length - 1] === "end",
  maxMove, jumps, jumpsAfter,
  landsOnFinal: lastIntro ? Array.from(lastIntro.m.positions).every((v, i) => Math.abs(v - final[i]) < 1e-3) : null,
  frameIsFinal: frame ? Array.from(frame.m.positions).every((v, i) => Math.abs(v - final[i]) < 1e-3) : null,
  startIsFirst: frame && intros.length ? Array.from(frame.m.start).every((v, i) => Math.abs(v - intros[0].m.positions[i]) < 1e-3) : null,
  starts: sb.__starts || 0, glides: sb.__glides || 0,
}));
"""


def test_the_opening_is_untangled_and_cleaned_before_its_first_post_and_flows_into_it() -> None:
    out = _node(OPEN, "intro")
    # The camera's frame first, then the playback, then the map at rest.
    assert out["kinds"] == ["frame", "tick", "end"], out
    first = out["firstTick"]
    assert first["intro"] and first["passes"] > 0 and first["cleaned"], out
    # No note steps more than a few px a frame (it was 134 px), none over 20.
    assert out["jumps"] == 0 and out["maxMove"] <= 12, out
    # The frame is set on the settled map, drawn from the playback's first frame,
    # and the playback lands exactly on it: no snap at the end.
    assert out["frameIsFinal"] and out["startIsFirst"] and out["landsOnFinal"], out
    # At rest in about a second: the hold behind the fade and one eased run.
    assert out["intros"] <= 8 + 61 and out["ticks"] <= out["intros"] + 1, out
    assert out["lastRunning"] is False and out["ended"], out


def test_less_motion_gets_the_settled_map_as_its_one_and_only_frame() -> None:
    out = _node(OPEN, "still")
    assert out["kinds"] == ["tick", "end"] and out["ticks"] == 1, out
    assert out["firstTick"]["passes"] > 0 and out["firstTick"]["cleaned"], out
    assert out["firstTick"]["alpha"] < 0.08 and out["lastRunning"] is False, out
    # A map too big for `WARM_MS` (300 notes in the browser: shown at rest at
    # 1.6 s, then a 13 px-a-frame glide) waits for the settled map instead.
    step = _fn("pendingStep")
    assert "const deadline = pending.open && !still ? pending.from + WARM_MS : 0;" in step
    # No pass is begun that would leave the cleanup no time before the cap.
    settle = _fn("settleUntangled")
    assert "if (cap && Date.now() + 2 * untangleBudget() > cap) {" in settle
    assert settle.index("2 * untangleBudget() > cap") < settle.index("untangleCleanup()")


def test_a_layout_settled_live_is_untangled_out_of_sight_and_glided_to_once() -> None:
    out = _node(OPEN, "live")
    # One settle out of sight and one glide, never a burst per pass. Before it
    # the layout runs live from full heat (no warm-up asked), physics only.
    assert out["starts"] == 1 and out["glides"] <= 1, out
    assert out["jumpsAfter"] == 0, out
    assert out["lastRunning"] is False and out["ended"], out


CANCEL = OPEN.split("let guard = 0;")[0] + r"""
// A drag while the settle out of sight is part way: the notes go back to where
// the screen shows them, and the settle is called off.
const shown = run("nodes.map((n) => [n.x, n.y])");
run("pendingStep()");
sb.onmessage({ data: { type: "drag", id: 3, phase: "start", x: nodes[3].x, y: nodes[3].y } });
const back = run("nodes.map((n) => [n.x, n.y])");
let off = 0;
shown.forEach((p, i) => { if (i !== 3) off = Math.max(off, Math.hypot(p[0] - back[i][0], p[1] - back[i][1])); });
console.log(JSON.stringify({ off, on: run("pending.on"), holding: run("untangle.holding"), decay: run("simulation.alphaDecay()"), live: run("alphaDecayFor(nodes.length)") }));
"""


def test_a_drag_during_the_settle_out_of_sight_starts_from_the_map_on_screen() -> None:
    out = _node(CANCEL, "intro")
    assert out["off"] == 0 and out["on"] is False and out["holding"] is False, out
    assert out["decay"] == out["live"], out


def _fn(name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", WORKER).start() + 1
    return WORKER[start : WORKER.index("\n}\n", start) + 2]


def test_no_pass_glides_on_its_own_and_the_glide_is_one_smoothstep() -> None:
    loop = _fn("loop")
    assert "untangleLayout()" not in loop and "untangleCleanup()" not in loop
    assert "UNTANGLE_GLIDE_STEPS" not in WORKER and "UNTANGLE_CLEAN_STEPS" not in WORKER
    assert "settled && !dragging && untangleOwed()" in loop and "pendingStart(false, false, false);" in loop
    glide = _fn("settleGlideStep")
    assert "smoothstep(1 - settleGlide.left / SETTLE_GLIDE_FRAMES)" in glide
    # The worker's playback frame is where the canvas draws the notes from.
    assert "gcFrameIntro(s, message.positions, message.start);" in CANVAS
    assert "bloom: hidden," in CANVAS
