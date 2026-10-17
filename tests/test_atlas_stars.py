"""Atlas throws its stars (B88b, the owner, 2026-10-17: "the throwing stars
action for atlas isnt animated").

The juggle (`nmb-act-juggle`) showed three stars on an arc and turned each
about one point over the head, 1.8 s a turn: two of them 21 units out and one
13, so they swept through the face on circles while both arms held still at
64 degrees. Now the rig (`atlasRigFrame`, its own loop: no new frame loop)
throws them: each star goes from the right hand over the head to the left,
is caught and thrown back on a lower arc, three a third of a cycle apart, and
each hand dips as it catches and flicks up as it throws. Thrown across the
screen, Atlas flings its stars out of its hands and they fall away and fade.
Reduced motion keeps the drawn stars where they are.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
CSS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
let frames = [];
let clock = 0;
const el = () => ({ style: { setProperty() {}, rotate: "", transform: "", opacity: "" }, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; }, closest: () => null });
const reduced = process.argv[2] === "reduced";
const ctx = {
  console, Math, Number, Object, Set, Map, JSON,
  performance: { now: () => clock },
  document: { documentElement: { dataset: reduced ? { motion: "reduced" } : {}, hasAttribute: () => false } },
  matchMedia: () => ({ matches: false }),
  getComputedStyle: () => ({ transform: "none", rotate: "none", opacity: "1" }),
  requestAnimationFrame: (f) => { frames.push(f); return frames.length; },
  atlasTailWake() {}, atlasFix: (n) => +n.toFixed(2), atlasArmPath: () => "M0 0", atlasArmHand: () => "", atlasState: {},
  ATLAS_LOOKS: {},
  nmb: { flight: null },
  nameMarkBuddyActOff: () => false,
};
vm.createContext(ctx);
vm.runInContext(process.argv[1] + "\n;globalThis.__wake = atlasRigWake;", ctx);
const classes = new Set();
const buddy = { id: "nm-buddy", dataset: {}, classList: { contains: (c) => classes.has(c) }, style: { getPropertyValue: () => "" } };
const stars = [el(), el(), el()];
const root = el();
const arc = el();
const box = {
  isConnected: true, dataset: { atlasMood: "calm" }, classList: { contains: (c) => c === "atl-figure-box" }, closest: () => buddy, toggleAttribute() {},
  querySelector: (s) => (s.includes("nmp-stars") && s.includes("arc") ? arc : s.includes("nmp-stars") ? root : null),
  querySelectorAll: (s) => (s.includes("atl-juggle") ? stars : []),
};
const arm = (side) => ({ side, sgn: side === "r" ? 1 : -1, probe: { getAnimations: () => [] }, hold: null, groups: [el()], paths: [el()], hand: el(), geo: {}, j: { sh: { x: 0, v: 0, w: 14, t: null }, el: { x: 0, v: 0, w: 14, t: null }, wr: { x: 0, v: 0, w: 14, t: null }, sy: { x: 1, v: 0, w: 14, t: null } }, hist: [], drawn: [0, 0], shown: "", antic: null });
const rig = { box, body: {}, look: "masculine", arms: [arm("l"), arm("r")], raf: 0, at: 0, still: 0, host: buddy, observer: {}, pose: null, heads: [], lag: { x: 0, v: 0, w: 9, t: null }, fresh: false };
box.atlasRig = rig;
const run = (n, each) => { for (let i = 0; i < n; i += 1) { clock += 1000 / 60; const f = frames; frames = []; for (const g of f) g(clock); if (each) each(); } };
const at = (k) => { const m = /translate\(([-0-9.]+)px, ([-0-9.]+)px\)/.exec(stars[k].style.transform); const o = [[10, 17], [31, 4], [52, 17]][k]; return m ? [o[0] + +m[1], o[1] + +m[2]] : null; };
"""


def _run(body: str, mode: str = "live"):
    script = HARNESS + body
    run = subprocess.run(["node", "-e", script, MOTION, mode], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


JUGGLE = r"""
classes.add("nmb-act-juggle");
ctx.__wake(box);
const path = [[], [], []];
const sh = { l: [], r: [] };
run(30);
run(108, () => { for (let k = 0; k < 3; k += 1) path[k].push(at(k)); sh.l.push(rig.arms[0].j.sh.x); sh.r.push(rig.arms[1].j.sh.x); });
process.stdout.write(JSON.stringify({ path, sh, busy: rig.raf > 0 }));
"""


@needs_node
def test_juggling_each_star_flies_hand_to_hand_over_the_head() -> None:
    out = _run(JUGGLE)
    for k, pts in enumerate(out["path"]):
        assert all(pts), f"star {k} is placed every frame of the act"
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        assert min(xs) <= 11 and max(xs) >= 51, f"star {k} reaches both hands: x {min(xs)} to {max(xs)}"
        assert min(ys) <= 8, f"star {k} goes up over the head (y {min(ys)})"
        assert max(ys) <= 19.5, f"star {k} never drops into the face (y {max(ys)})"
        # A real flight: no jump between frames of more than a few units.
        steps = [abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(pts, pts[1:])]
        assert max(steps) < 5, f"star {k} jumps {max(steps)} units in a frame"
    # The three stay a third of a cycle apart: never two in one place.
    for i in range(len(out["path"][0])):
        a, b, c = (out["path"][k][i] for k in range(3))
        assert min(abs(a[0] - b[0]) + abs(a[1] - b[1]), abs(b[0] - c[0]) + abs(b[1] - c[1]), abs(a[0] - c[0]) + abs(a[1] - c[1])) > 2
    assert out["busy"], "the rig keeps its loop while it juggles"


@needs_node
def test_juggling_the_hands_dip_and_flick_with_each_throw() -> None:
    out = _run(JUGGLE)
    for side in ("l", "r"):
        swing = max(out["sh"][side]) - min(out["sh"][side])
        assert swing >= 3, f"the {side} arm moves with the throws ({swing:.1f} degrees)"


@needs_node
def test_reduced_motion_keeps_the_drawn_stars() -> None:
    out = _run(JUGGLE, "reduced")
    assert all(p is None for pts in out["path"] for p in pts), "under reduced motion nothing moves the stars"


@needs_node
def test_thrown_it_flings_its_stars_and_they_fall_away_and_fade() -> None:
    out = _run(
        r"""
classes.add("nm-buddy-dragging");
ctx.nmb.flight = {};
ctx.__wake(box);
const seen = [];
run(80, () => seen.push({ p: [at(0), at(1), at(2)], o: stars.map((s) => s.style.opacity), shown: root.style.opacity }));
ctx.nmb.flight = null;
classes.delete("nm-buddy-dragging");
ctx.__wake(box);
run(10);
process.stdout.write(JSON.stringify({ seen, after: { t: stars.map((s) => s.style.transform), o: stars.map((s) => s.style.opacity), shown: root.style.opacity } }));
"""
    )
    first, mid, late = out["seen"][2], out["seen"][25], out["seen"][58]
    assert first["shown"] == "1", "the stars show as they leave its hands"
    for k in range(3):
        assert late["p"][k][1] > mid["p"][k][1], f"star {k} falls"
    assert all(float(o) < 0.5 for o in late["o"]), late["o"]
    assert out["after"]["shown"] == "" and out["after"]["t"] == ["", "", ""] and out["after"]["o"] == ["", "", ""], "landed, the prop is back as drawn"


def test_the_layered_stars_are_the_rigs_not_a_css_turn() -> None:
    assert "#nm-buddy.nmb-act-juggle &.atl-layer .atl-juggle-0" not in CSS, "a CSS turn would fight the rig's throws"
    # The whole drawing (no rig) keeps its CSS loop.
    assert "& .atl-juggle-0 { animation: atl-juggle 1.8s linear infinite; }" in CSS
    frame = MOTION[MOTION.index("function atlasRigFrame(") :]
    frame = frame[: frame.index("\n}\n")]
    assert "atlasTossDraw(" in frame and frame.count("requestAnimationFrame(") == 1
