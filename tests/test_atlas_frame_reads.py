"""Atlas reads the page's style only when something may have changed it (B87a, B87c).

The owner, 2026-10-17: "when throwing companions around the physics and
movement was insanely framey and laggy". A carried or thrown Atlas held 30 to
32 fps at 4x CPU (scratchpad/ui-sweeps/throwframes.js) with 10 to 17 ms of
style recalculation a frame; a trace of one carry and flight
(scratchpad/ui-sweeps/atlasrecalc.js) counted 254 forced restyles and
layouts in 1.3 s, every one from Atlas's own loops reading after the
flight's writes: the rig's probe read (`atlasRigRead`, 137), the breath's
rise clock (`atlasBreathFrame`, 81: an animation's `currentTime` and
`playState` bring style up to date) and the props' opacity check
(`atlasPropsFrame`, 22). What they read only changes when a class, a pose or
a mood changes, which is when the rig is woken (`atlasRigWake`, its
MutationObserver), or while an animation runs on the arm. So they read then,
and use what they read until the next wake.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
LIFE = (JS / "atlas-life.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(src: str, name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", src, re.S | re.M)
    assert match, name
    return match.group(0)


def _node(script: str, *args: str):
    run = subprocess.run(["node", "-e", script, *args], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


#: A rig as `atlasRigAttach` makes one, on fakes that count every style read.
RIG = r"""
const vm = require("vm");
const reads = { cs: 0, anim: 0 };
let frames = [];
let probeAnims = [];
let ang = 0;
const el = () => ({ style: { setProperty() {}, rotate: "" }, setAttribute() {}, closest: () => null });
const ctx = {
  console, Math, Number, Object, Set, Map, JSON,
  performance: { now: () => clock },
  document: { documentElement: { dataset: {}, hasAttribute: () => false } },
  matchMedia: () => ({ matches: false }),
  getComputedStyle: () => { reads.cs += 1; return { transform: `matrix(${Math.cos(ang)}, ${Math.sin(ang)}, ${-Math.sin(ang)}, ${Math.cos(ang)}, 0, 0)`, rotate: "none", opacity: "1" }; },
  requestAnimationFrame: (f) => { frames.push(f); return frames.length; },
  atlasTailWake() {}, atlasFix: (n) => +n.toFixed(2), atlasArmPath: () => "M0 0", atlasArmHand: () => "", atlasState: {},
  ATLAS_LOOKS: {},
};
let clock = 0;
vm.createContext(ctx);
vm.runInContext(process.argv[1] + "\n;globalThis.__wake = atlasRigWake; globalThis.__frame = atlasRigFrame;", ctx);
const classes = new Set(["nmb-walking"]);
const buddy = { id: "nm-buddy", dataset: {}, classList: { contains: (c) => classes.has(c) }, style: { getPropertyValue: () => "" } };
const box = { isConnected: true, dataset: { atlasMood: "calm" }, classList: { contains: (c) => c === "atl-figure-box" }, closest: () => buddy, toggleAttribute() {} };
const arm = (side) => ({ side, sgn: side === "r" ? 1 : -1, probe: { getAnimations: () => { reads.anim += 1; return probeAnims; } }, hold: null, groups: [el()], paths: [el()], hand: el(), geo: {}, j: { sh: { x: 0, v: 0, w: 14, t: null }, el: { x: 0, v: 0, w: 14, t: null }, wr: { x: 0, v: 0, w: 14, t: null }, sy: { x: 1, v: 0, w: 14, t: null } }, hist: [], drawn: [0, 0], shown: "", antic: null });
const rig = { box, body: {}, look: "masculine", arms: [arm("l"), arm("r")], raf: 0, at: 0, still: 0, host: buddy, observer: {}, pose: el(), heads: [el()], lag: { x: 0, v: 0, w: 9, t: null }, fresh: false };
box.atlasRig = rig;
const run = (n) => { for (let i = 0; i < n; i += 1) { clock += 16.7; const f = frames; frames = []; for (const g of f) g(clock); } };
const take = () => { const r = { ...reads }; reads.cs = 0; reads.anim = 0; return r; };
"""


@needs_node
def test_a_walking_rig_stops_reading_style_once_its_arms_hold_still() -> None:
    out = _node(
        RIG
        + r"""
const res = {};
ctx.__wake(box);
run(60);
res.walk = take();
// A class change (the observer) wakes it: it reads again.
ctx.__wake(box);
run(3);
res.woken = take();
// An animation on the arm (a gesture's) keeps it reading every frame.
probeAnims = [{}];
ctx.__wake(box);
run(30);
res.anim = take();
probeAnims = [];
run(60);
res.after = take();
process.stdout.write(JSON.stringify(res));
""",
        MOTION,
    )
    # Two probes and the pose: 3 reads a frame while it looks.
    assert out["walk"]["cs"] <= 3 * 20, f"60 walking frames read style {out['walk']['cs']} times; it reads only until the arms hold still"
    assert out["walk"]["cs"] >= 3, "it reads at least once after a wake"
    assert out["woken"]["cs"] >= 3, "a wake reads the arms again"
    assert out["anim"]["cs"] >= 3 * 30, "while an animation runs on the arm it reads every frame"
    assert out["after"]["cs"] <= 3 * 20, "and stops once the animation is over and the arm holds"


def test_the_wake_marks_the_figure_for_a_fresh_read() -> None:
    wake = _fn(MOTION, "atlasRigWake")
    assert "rig.dirty = true" in wake
    assert "box.atlasDirtyAt = performance.now()" in wake
    frame = _fn(MOTION, "atlasRigFrame")
    assert "rig.dirty" in frame and frame.index("rig.dirty") < frame.index("atlasRigRead(")


@needs_node
def test_the_breath_reads_the_rise_clock_once_per_refresh_not_each_step() -> None:
    swell = "\n".join(re.search(rf"^const {n} = .*;$", LIFE, re.M).group(0) for n in ("ATLAS_BREATH_SWELL", "ATLAS_BREATH_STEP_MS"))
    out = _node(
        swell
        + "\n"
        + _fn(LIFE, "atlasBreathFrame")
        + r"""
let gets = 0;
let t = 0;
const rise = { effect: { getComputedTiming: () => ({ duration: 4600 }) } };
Object.defineProperty(rise, "currentTime", { get() { gets += 1; return t; } });
Object.defineProperty(rise, "playState", { get() { gets += 1; return "running"; } });
const torsos = [{ style: { scale: "" } }];
const box = { dataset: { atlasLook: "masculine" }, querySelectorAll: () => torsos, querySelector: () => ({ getAnimations: () => [rise] }) };
const seen = [];
for (t = 0; t <= 4600; t += 100) { atlasBreathFrame(box, true, t); seen.push(torsos[0].style.scale); }
process.stdout.write(JSON.stringify({ gets, peak: seen[23], start: seen[0] }));
""",
    )
    assert out["gets"] <= 2 * 2, f"{out['gets']} reads of the rise's clock in 46 steps; once per refresh (5 s)"
    assert out["start"] == "" and out["peak"] == "1.0350 1.0250", "still on the rise's clock, extrapolated by the wall's"


@needs_node
def test_the_props_check_what_shows_only_after_a_wake() -> None:
    out = _node(
        _fn(LIFE, "atlasPropsFrame")
        + r"""
let cs = 0;
let clock = 0;
const performance = { now: () => clock };
const getComputedStyle = () => { cs += 1; return { opacity: "1" }; };
const anim = { play() {}, cancel() {}, currentTime: 0 };
const box = { atlasPropLoops: [{ anim, el: {}, root: {}, lag: 0, on: false }], atlasDirtyAt: 0 };
for (let tick = 1; tick <= 400; tick += 1) { clock += 16.7; atlasPropsFrame(box, true, tick); }
const quiet = cs;
box.atlasDirtyAt = clock;
for (let tick = 401; tick <= 480; tick += 1) { clock += 16.7; atlasPropsFrame(box, true, tick); }
const woken = cs - quiet;
// Hidden, then back: it looks again, so a prop cancelled while hidden plays.
atlasPropsFrame(box, false, 481);
const before = cs;
atlasPropsFrame(box, true, 488);
process.stdout.write(JSON.stringify({ quiet, woken, back: cs - before, on: box.atlasPropLoops[0].on }));
""",
    )
    assert out["quiet"] <= 12, f"{out['quiet']} opacity reads over 400 quiet frames; it looks for 1.5 s after a wake, then stops"
    assert out["woken"] >= 2, "a wake looks again"
    assert out["back"] == 1 and out["on"] is True, "back from hidden it looks again"


def test_carried_or_thrown_the_idle_loops_hold() -> None:
    # Drawn every frame while it is carried or flies, each running loop
    # restyles its element every frame, composited or not: the flight at 1x
    # was 10,169 style invalidations in 1.3 s, 3,000 of them the rings' and
    # planets' loops (scratchpad/ui-sweeps/atlasinval.js); 2,644 with these held.
    css = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")
    rule = re.search(r"#nm-buddy\.nm-buddy-dragging :is\(([^)]*)\) \{ animation-play-state: paused !important; \}", css)
    assert rule, "the carry's pause rule is in the lazy Atlas sheet (boot CSS is at its cap)"
    for part in (".atl-lw", ".atl-lw-breathe", ".atl-orbit-arm", ".atl-orbiter"):
        assert part in rule.group(1).split(", ")
    assert "atl-layer-lower" not in rule.group(1), "the legs' flick while held is the carry's own"
    frame = _fn(LIFE, "atlasTailFrame")
    assert 'const loops = live && !box.closest("#nm-buddy.nm-buddy-dragging");' in frame
    assert "loops ? anim.play() : anim.pause()" in frame
