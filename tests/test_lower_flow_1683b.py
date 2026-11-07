"""The in-app lower body, wisps and nebula by pose (INBOX 1683 B1, B2, B3, B5, B6): six or more arrangements a pose,
and a path of their own that never stops. Run in node's vm over the real file; nothing reads a real clock."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

SCRIPT = r"""
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync("frontend/js/atlas-life.js", "utf8");
const ctx = { atlasFix: (v) => Math.round(v * 100) / 100, console, Math, Map, Set, Object, Array, Number, performance, document: {}, window: {}, setTimeout, clearTimeout };
vm.createContext(ctx);
vm.runInContext(src + "\n;this.__x = { L: ATLAS_LOWER_STATES, H: ATLAS_HAIR_STATES, N: ATLAS_NEB_STATES, of: atlasRigLower.blend.of, byState: atlasRigLower.flowByState, parts: atlasRigLower.flowParts, flow: atlasRigLower.flow, at: atlasRigLower.flowAt };", ctx);
const x = ctx.__x, out = { states: {} };
for (const s of Object.keys(x.L)) {
  const lower = x.of(x.L[s].v), hair = x.of(x.H[s]), neb = x.of(x.N[s]);
  const authored = Math.max(...x.L[s].v.map((r) => Math.abs(r[0])));
  out.states[s] = {
    n: [lower.length, hair.length, neb.length], authored: x.L[s].v.length,
    distinct: new Set(lower.map((r) => r.join())).size,
    turn: Math.max(...lower.map((r) => Math.abs(r[0]))), authoredTurn: authored,
    flow: s in x.byState,
  };
}
// A flow on a fake rig: every part gets one path, closed (first key = last), starting at where the last one was.
const mk = () => { const a = []; return { animate: (frames, opt) => { const an = { frames, opt, cancel() { this.gone = true; }, effect: { getComputedTiming: () => ({ progress: 0.5 }) } }; a.push(an); return an; }, a }; };
const els = { boxes: [mk()], wisps: [mk(), mk()], tails: [mk()], hair: [mk()], neb: [mk(), mk()] };
const rig = { box: { isConnected: true, animate() {}, atlasLoops: [] }, lower: { ...els } };
x.flow(rig, "sit", true);
const first = rig.lower.flow.map((a) => [a.keys[0], a.keys[a.keys.length - 1], a.opt.duration, a.opt.composite]);
const n1 = rig.box.atlasLoops.length;
x.flow(rig, "sit", true);
out.paths = rig.lower.flow.length; out.loops = [n1, rig.box.atlasLoops.length];
out.closed = first.every(([a, b]) => a.join() === b.join());
out.durations = [...new Set(first.map((f) => f[2]))].length;
out.composite = [...new Set(first.map((f) => f[3]))];

x.flow(rig, "sit", false);
out.stopped = [rig.lower.flow.length, rig.box.atlasLoops.length];
console.log(JSON.stringify(out));
"""


@needs_node
def test_every_pose_has_six_or_more_arrangements_inside_the_authored_turn() -> None:
    out = subprocess.run(["node", "-e", SCRIPT], capture_output=True, text=True, timeout=30, check=True, cwd=ROOT)
    got = json.loads(out.stdout)
    for state, row in got["states"].items():
        assert row["n"][0] == row["n"][1] == row["n"][2] >= 6, (state, "lower body, hair and stream agree on six or more")
        assert row["distinct"] == row["n"][0], (state, "no two alike")
        assert row["turn"] <= row["authoredTurn"] + 1e-9, (state, "a blend never turns further than the authored rows")
        assert row["flow"], (state, "the continuous path is keyed by the pose too")


@needs_node
def test_each_part_drifts_on_its_own_closed_path_under_the_rest() -> None:
    out = subprocess.run(["node", "-e", SCRIPT], capture_output=True, text=True, timeout=30, check=True, cwd=ROOT)
    got = json.loads(out.stdout)
    assert got["paths"] == 7 and got["loops"] == [7, 7], "one path per element, replaced not stacked"
    assert got["closed"], "a path ends where it began, so it loops without a cut"
    assert got["durations"] >= 5, "the parts keep different periods"
    # Intent moved (2026-11-07, the Atlas idle restyle): the path was added (`composite: "add"`) over the CSS
    # sway's `rotate`, which took the figure off the compositor (tests/test_atlas_composite_1101.py). It is now
    # `translate` alone, which nothing else on these boxes sets, so it replaces and still leaves the sway be.
    assert got["composite"] == [None], "a replacing translate, never added"
    assert got["stopped"] == [0, 0], "reduced motion or away: none run"


TURN_SCRIPT = SCRIPT.split("// A flow on a fake rig")[0].replace("const x = ctx.__x, out = { states: {} };", "const x = ctx.__x, out = { states: {} }; out.max = 0;") + r"""
const mk = () => { const a = []; return { animate: (frames, opt) => { const an = { frames, opt, cancel() {}, effect: { getComputedTiming: () => ({ progress: 0.5 }) } }; a.push(an); return an; }, a }; };
for (const s of Object.keys(x.byState)) {
  for (let i = 0; i < 40; i++) {
    const rig = { box: { isConnected: true, animate() {}, atlasLoops: [] }, lower: { boxes: [mk()], wisps: [mk()], tails: [mk()], hair: [mk()], neb: [mk()] } };
    x.flow(rig, s, true);
    for (const a of rig.lower.flow) for (const f of a.frames) out.max = Math.max(out.max, "rotate" in f ? 99 : 0, ...a.keys.map((k) => k.length - 2));
  }
}
console.log(JSON.stringify(out));
"""


@needs_node
def test_no_part_turns_more_than_four_degrees_in_any_pose() -> None:
    """Review of 1683b: tails reached 1.6 x 2.2 x 1.6 = 5.6 degrees on a startle; the lower body stays within 4 of the torso.
    Intent moved (2026-11-07): the path no longer turns at all (the CSS sway owns `rotate`), so it holds at 0."""
    out = subprocess.run(["node", "-e", TURN_SCRIPT], capture_output=True, text=True, timeout=60, check=True, cwd=ROOT)
    assert json.loads(out.stdout)["max"] <= 4.0
