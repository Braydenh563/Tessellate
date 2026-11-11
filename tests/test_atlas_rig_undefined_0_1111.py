"""INBOX 1111: `Cannot read properties of undefined (reading '0')` in `atlasRigFrame`, intermittent.

The frame takes the very first look itself (`atlasRigWake.look(rig, true)`), and a look returns without reading while
the figure is off screen (`atl-off`, the viewport observer's class), hidden or disconnected. The frame then went on
to `reads[i]` with `reads` undefined: `reads[0]` on the first arm. It happens when a figure is attached below the fold
(the observer marks it `atl-off` before its first frame), so which of two races won decided it. The frame now ends
where it stands with nothing read, and the class change that brings the figure back wakes it (the rig's observer).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOTION = (ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

#: A rig on fakes, as `tests/test_atlas_frame_reads.py` builds one, with the figure's classes set by the test.
SCRIPT = r"""
const vm = require("vm");
let frames = [];
let clock = 0;
const el = () => ({ style: { setProperty() {}, rotate: "" }, setAttribute() {}, closest: () => null });
const ctx = {
  console, Math, Number, Object, Set, Map, JSON,
  performance: { now: () => clock },
  document: { hidden: false, documentElement: { dataset: {}, hasAttribute: () => false } },
  setTimeout: (f, ms, ...a) => 1,
  matchMedia: () => ({ matches: false }),
  getComputedStyle: () => ({ transform: "matrix(1, 0, 0, 1, 0, 0)", rotate: "none", opacity: "1" }),
  requestAnimationFrame: (f) => { frames.push(f); return frames.length; },
  atlasTailWake() {}, atlasFix: (n) => +n.toFixed(2), atlasArmPath: () => "M0 0", atlasArmHand: () => "", atlasState: {},
  ATLAS_LOOKS: {}, nameMarkBuddyBehindCover: () => false,
};
vm.createContext(ctx);
vm.runInContext(process.argv[1] + "\n;globalThis.__frame = atlasRigFrame;", ctx);
const classes = new Set(JSON.parse(process.argv[2]));
const box = { isConnected: true, dataset: { atlasMood: "calm" }, classList: { contains: (c) => classes.has(c) }, closest: () => null, toggleAttribute() {} };
const arm = (side) => ({ side, sgn: side === "r" ? 1 : -1, probe: { getAnimations: () => [] }, running: new Set(), hold: null, groups: [el()], paths: [el()], hand: el(), geo: {}, j: { sh: { x: 0, v: 0, w: 14, t: null }, el: { x: 0, v: 0, w: 14, t: null }, wr: { x: 0, v: 0, w: 14, t: null }, sy: { x: 1, v: 0, w: 14, t: null } }, hist: [], drawn: [0, 0], shown: "", antic: null });
const rig = { box, body: {}, look: "masculine", arms: [arm("l"), arm("r")], raf: 0, at: 0, still: 0, host: box, observer: {}, pose: el(), heads: [el()], lag: { x: 0, v: 0, w: 9, t: null }, fresh: true };
box.atlasRig = rig;
let error = "";
try { clock = 16; ctx.__frame(rig, clock); } catch (e) { error = e.message; }
process.stdout.write(JSON.stringify({ error, reads: !!rig.reads, raf: rig.raf, queued: frames.length, at: rig.at }));
"""


def _run(classes: list[str]) -> dict:
    run = subprocess.run(["node", "-e", SCRIPT, MOTION, json.dumps(classes)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_the_first_frame_of_a_figure_below_the_fold_does_not_read_a_look_it_never_took() -> None:
    out = _run(["atl-figure-box", "atl-off"])
    assert out["error"] == "", out
    assert out["reads"] is False and out["queued"] == 0, "nothing was read, so nothing is drawn or asked for"


@needs_node
def test_a_figure_on_screen_still_takes_its_first_look_and_draws() -> None:
    out = _run(["atl-figure-box"])
    assert out["error"] == "" and out["reads"] is True, out


def test_the_frame_ends_where_it_stands_when_the_look_took_nothing() -> None:
    frame = re.search(r"^function atlasRigFrame\(.*?^\}", MOTION, re.S | re.M).group(0)
    first = frame.index("if (!rig.reads) atlasRigWake.look(rig, true);")
    guard = frame.index("if (!rig.reads)", first + 10)
    assert guard < frame.index("const { reads, turnMatrix } = rig;"), "the guard comes before the arms are indexed"
    assert "rig.dirty = true" in frame[guard : guard + 120], "the next wake looks again"
