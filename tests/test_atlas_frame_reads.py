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
  setTimeout: (f) => { frames.push(() => f()); return frames.length; },  // the first look runs in a timer after the frame (`atlasRigWake.afterPaint`)
  atlasTailWake() {}, atlasFix: (n) => +n.toFixed(2), atlasArmPath: () => "M0 0", atlasArmHand: () => "", atlasState: {},
  ATLAS_LOOKS: {}, nameMarkBuddyBehindCover: () => false,  // 1667: the rig holds its reads behind a dialog
};
let clock = 0;
vm.createContext(ctx);
vm.runInContext(process.argv[1] + "\n;globalThis.__wake = atlasRigWake; globalThis.__frame = atlasRigFrame;", ctx);
const classes = new Set(["nmb-walking"]);
const buddy = { id: "nm-buddy", dataset: {}, classList: { contains: (c) => classes.has(c) }, style: { getPropertyValue: () => "" } };
const box = { isConnected: true, dataset: { atlasMood: "calm" }, classList: { contains: (c) => c === "atl-figure-box" }, closest: () => buddy, toggleAttribute() {} };
const arm = (side) => ({ side, sgn: side === "r" ? 1 : -1, probe: { getAnimations: () => [] }, running: { get size() { return probeAnims.length; } }, hold: null, groups: [el()], paths: [el()], hand: el(), geo: {}, j: { sh: { x: 0, v: 0, w: 14, t: null }, el: { x: 0, v: 0, w: 14, t: null }, wr: { x: 0, v: 0, w: 14, t: null }, sy: { x: 1, v: 0, w: 14, t: null } }, hist: [], drawn: [0, 0], shown: "", antic: null });
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
run(60);
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
    # The corner companion's rig draws at 30 a second (every other 60 Hz frame), so 60 frames are 30 drawn ones.
    assert out["anim"]["cs"] >= 3 * 30, "while an animation runs on the arm it reads every drawn frame"
    assert out["after"]["cs"] <= 3 * 20, "and stops once the animation is over and the arm holds"


def test_the_wake_marks_the_figure_for_a_fresh_read() -> None:
    wake = _fn(MOTION, "atlasRigWake")
    assert "rig.dirty = true" in wake
    assert "box.atlasDirtyAt = performance.now()" in wake
    frame = _fn(MOTION, "atlasRigFrame")
    assert "rig.dirty" in frame and frame.index("rig.dirty") < frame.index("atlasRigRead(")


@needs_node
def test_the_breath_reads_the_rise_clock_once_not_each_step() -> None:
    # Intent moved (atlasidle2): the breath is a Web Animation set once, so the
    # rise's clock is read at the start (and a retune), never per step.
    swell = re.search(r"^const ATLAS_BREATH_SWELL = .*;$", LIFE, re.M).group(0)
    out = _node(
        swell
        + "\n"
        + _fn(LIFE, "atlasBreathFrame")
        + r"""
let gets = 0;
const rise = { effect: { getComputedTiming: () => ({ duration: 4600 }) }, startTime: 0 };
Object.defineProperty(rise, "currentTime", { get() { gets += 1; return 0; } });
Object.defineProperty(rise, "playState", { get() { gets += 1; return "running"; } });
const torso = { animate: () => ({ cancel() {} }) };
const box = { dataset: { atlasLook: "masculine" }, querySelectorAll: () => [torso], querySelector: () => ({ getAnimations: () => { gets += 1; return [rise]; } }) };
for (let t = 0; t <= 4600; t += 100) atlasBreathFrame(box, true);
process.stdout.write(JSON.stringify({ gets }));
""",
    )
    assert out["gets"] <= 3, f"{out['gets']} reads of the rise's clock in 46 steps; once, at the start"


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
    assert 'const loops = live && !box.closest("#nm-buddy.nm-buddy-dragging") && !document.documentElement.hasAttribute("data-atlas-lite");' in frame
    assert "loops ? anim.play() : anim.pause()" in frame


def test_lag_1657_tail_path_numbers_are_rounded_with_math_round():
    """INBOX 1657: the tail's paths are rounded ~3,000 times a draw; `toFixed`
    plus a unary plus made `atlasTailPaths` 2.8 to 3.9 ms a draw at 4x CPU,
    `Math.round(v * 100) / 100` 1.7 to 1.8 (same two decimals)."""
    atlas = (JS / "atlas.js").read_text(encoding="utf-8")
    assert "const atlasFix = (v) => Math.round(v * 100) / 100;" in atlas
    assert "toFixed" not in atlas[atlas.index("function atlasStem("):atlas.index("//: **Hands and feet**")]


def test_lag_1657_character_jobs_run_one_task_each():
    """INBOX 1657: the seven jobs the characters' arrival releases were one
    161 ms task at 4x CPU (47 ms forced layout); each is its own task now."""
    atlas = (JS / "atlas.js").read_text(encoding="utf-8")
    body = atlas[atlas.index("function charactersArrived()"):]
    assert "const step = () => {" in body and "setTimeout(step, 0)" in body
    assert "for (const fn of waiting)" not in body


def _tail_kit(src: str) -> str:
    """The tail's path helpers, one closure exporting `paths` and `num`."""
    match = re.search(r"^const atlasTailKit = \(\(\) => \{$.*?^\}\)\(\);$", src, re.S | re.M)
    assert match, "atlasTailKit"
    return match.group(0) + "\nconst { paths: atlasTailPaths, num: atlasTailNum } = atlasTailKit;"
ATLAS_JS = (JS / "atlas.js").read_text(encoding="utf-8")


def _tail_script(body: str) -> str:
    parts = [
        "const atlasFix = (v) => Math.round(v * 100) / 100;",
        *(_fn(ATLAS_JS, n) for n in ("atlasStemSides", "atlasSmooth", "atlasStem")),
        _tail_kit(LIFE),
        body,
    ]
    return "\n".join(parts)


@needs_node
def test_lag_1657_tail_numbers_as_text_match_atlas_fix():
    """INBOX 1657 round 2: `atlasTailNum` writes the tail's ~2,700 numbers a draw
    without the double-to-string conversion (1.3 of 1.6 ms at 4x CPU); the same text."""
    out = _node(_tail_script("""
let bad = 0;
for (let i = 0; i < 400000; i += 1) {
  const v = (Math.sin(i * 12.9898) * 43758.5453 % 1) * (i % 7 ? 400 : 0.02) * (i % 2 ? 1 : -1);
  if (String(atlasFix(v)) !== atlasTailNum(v)) bad += 1;
}
for (const v of [0, -0, 0.004, -0.004, 0.005, 0.5, -0.5, 1, 10, 100, 0.1, 0.01, 1.005, 99.995, -99.995]) if (String(atlasFix(v)) !== atlasTailNum(v)) bad += 1;
process.stdout.write(JSON.stringify({ bad }));
"""))
    assert out["bad"] == 0


@needs_node
def test_lag_1657_tail_paths_share_one_centreline_and_match_atlas_stem():
    """INBOX 1657 round 2: the body, stream, silk and filaments are cut from one
    centreline and memoised widths; at the old two samples a curve their text is
    `atlasStem`'s byte for byte, and the default filaments (always two) are too."""
    out = _node(_tail_script("""
const w = (t) => 3.6 + 4.8 * Math.sin(Math.PI * Math.min(1, 0.22 + 0.86 * t)) - 2.9 * t ** 6;
const spec = { tailWidth: w, tailFilaments: [0.3, -0.4], tailRound: true };
const N = 32;
let bad = 0, n = 0;
for (let k = 0; k < 120; k += 1) {
  const segs = Array.from({ length: N }, (_, i) => {
    const x = i * 3, a = Math.sin(k * 0.7 + i * 0.3) * 2, b = Math.cos(k * 0.4 + i * 0.2) * 2;
    return [x, a, x + 1, a + b, x + 2, b - a, x + 3, Math.sin(k * 0.7 + (i + 1) * 0.3) * 2];
  });
  const s = 2;
  const old = {
    body: atlasStem(segs, w, { samples: s, round: true }),
    stream: atlasStem(segs, (t) => w(t) * 0.26, { samples: s, shift: (t) => w(t) * 0.22 * Math.sin(Math.PI * 2.6 * t) }),
    silk: atlasStem(segs, (t) => w(t) * 0.24, { samples: s, shift: (t) => -w(t) * 0.3 * Math.sin(Math.PI * 2.6 * t + 1.1) }),
    filaments: spec.tailFilaments.map((f) => {
      const pts = atlasStemSides(segs, () => 0, s, (t) => (w(t) / 2) * f).left;
      const run = pts.slice(Math.round(pts.length * 0.18), Math.round(pts.length * 0.92));
      return `M${atlasFix(run[0][0])} ${atlasFix(run[0][1])}${atlasSmooth(run)}`;
    }).join(""),
  };
  const two = atlasTailPaths(spec, segs, 2);
  const one = atlasTailPaths(spec, segs);
  n += 1;
  for (const key of ["body", "stream", "silk", "filaments"]) if (old[key] !== two[key]) bad += 1;
  if (old.filaments !== one.filaments) bad += 1;
  if (one.body.length > old.body.length * 0.6) bad += 1000;
}
process.stdout.write(JSON.stringify({ bad, n }));
"""))
    assert out["bad"] == 0, out


def test_lag_1657_selection_popup_does_not_read_text_of_a_caret():
    """INBOX 1657 round 2: `selection.toString()` lays the page out; a caret
    (every focus change and key on the body) paid that to find nothing selected:
    706 ms of a 22-key run at 4x CPU. Collapsed is asked first."""
    sel = (JS / "selection.js").read_text(encoding="utf-8")
    body = sel[sel.index("function syncSelectionPopup()"):sel.index("function initSelectionPopup()")]
    assert body.index("!selection.isCollapsed ? selection.toString()") > 0
