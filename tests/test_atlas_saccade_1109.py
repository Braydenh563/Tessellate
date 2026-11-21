"""INBOX 1719 (b): the in-app eyes take small steps during a held gaze (`atlasBlink.saccade`, atlas-motion.js).
Node, a fixed clock and a seeded generator; nothing here uses real time."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

HARNESS = r"""
const vm = require("vm"); const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const grab = (re) => { const m = src.match(re); if (!m) throw new Error(String(re)); return m[0]; };
let clock = 0, queue = [], seed = Number(process.argv[2]);
const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
const writes = [];
const iris = { style: { setProperty: (k, v) => writes.push([clock, k, v]) } };
let attend = true;
const buddy = { classList: { contains: (c) => c === "nmb-attend" && attend }, querySelector: () => ({}), querySelectorAll: () => [iris] };
const ctx = {
  Math: Object.assign(Object.create(Math), { random: rnd }), Number,
  nmb: { ex: 0.4, ey: -0.2 }, document: { hidden: false, getElementById: () => buddy },
  atlasMotionOK: () => true, atlasBlink: () => {},
  setTimeout: (fn, ms) => { queue.push([clock + ms, fn]); return queue.length; },
};
vm.createContext(ctx);
vm.runInContext(grab(/^atlasBlink\.saccade = [\s\S]*?\n};\n/m) + grab(/^atlasBlink\.saccade\.step = [\s\S]*?\n};$/m) + grab(/^atlasBlink\.saccade\.hold = [\s\S]*?\n};$/m), ctx);
ctx.atlasBlink.saccade();
ctx.atlasBlink.saccade();  // armed twice: still one timer
while (queue.length) { queue.sort((a, b) => a[0] - b[0]); const [t, fn] = queue.shift(); clock = t; if (clock > 60000) attend = false; fn(); }
const ts = [...new Set(writes.map((w) => w[0]))];
const gaps = ts.slice(1).map((t, i) => t - ts[i]);
const exs = writes.filter((w) => w[1] === "--nmb-ex").map((w) => Number(w[2]));
console.log(JSON.stringify({ n: ts.length, first: ts[0], maxGap: Math.max(...gaps), minGap: Math.min(...gaps), lo: Math.min(...exs), hi: Math.max(...exs), left: queue.length, last: clock }));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize("seed", [1, 7, 42])
def test_a_held_gaze_has_a_step_of_the_eyes_every_point_six_to_one_point_eight_seconds(seed: int) -> None:
    out = subprocess.run(["node", "-e", HARNESS, str(JS / "atlas-motion.js"), str(seed)], capture_output=True, text=True, timeout=60, check=True).stdout
    r = json.loads(out)
    # 60 s held: a step about every 1.2 s (33 to 100), none more than 1.8 s apart, so no eye is still over 2 s
    assert 33 <= r["n"] <= 100 and r["maxGap"] <= 1800 and r["minGap"] >= 600 and r["first"] <= 1800
    assert 0.4 - 0.26 <= r["lo"] and r["hi"] <= 0.4 + 0.26 and r["hi"] - r["lo"] > 0.3  # small, and never the same place twice
    assert r["left"] == 0 and r["last"] < 62000  # released at 60 s: the loop stops, nothing is left running


def test_the_aim_arms_the_saccade_and_nothing_runs_without_a_look() -> None:
    avatars = (JS / "avatars.js").read_text(encoding="utf-8")
    i = avatars.index('buddy.classList.add("nmb-attend");')
    assert "atlasBlink.saccade?.()" in avatars[i : i + 200]
    motion = (JS / "atlas-motion.js").read_text(encoding="utf-8")
    assert "if (!buddy?.classList.contains(\"nmb-attend\")) return false;" in motion  # released: the loop ends


PACE = r"""
const vm = require("vm"); const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const grab = (re) => { const m = src.match(re); if (!m) throw new Error(String(re)); return m[0]; };
const timeline = { currentTime: 1000 };
// A CSS transition as Chromium runs it: a clock while playing, held while paused, gone once finished or replaced.
const make = (prop) => {
  const a = { transitionProperty: prop, state: "running", t: 0, start: null,
    effect: { getComputedTiming: () => ({ endTime: 180 }) },
    get playState() { return this.state; },
    get currentTime() { return this.state === "running" && this.start !== null ? timeline.currentTime - this.start : this.t; },
    set currentTime(v) { this.t = v; },
    pause() { this.state = "paused"; },
    finish() { this.t = 180; this.state = "finished"; },
    set startTime(v) { this.start = v; this.state = "running"; },
  };
  return a;
};
let anims = [];
const iris = { getAnimations: () => anims };
const ctx = { atlasBlink: () => {}, document: { timeline } };
vm.createContext(ctx);
vm.runInContext(grab(/^atlasBlink\.saccade = [\s\S]*?\n};\n/m) + grab(/^atlasBlink\.saccade\.hold = [\s\S]*?\n};$/m) + grab(/^atlasBlink\.saccade\.pace = [\s\S]*?\n};$/m), ctx);
const s = ctx.atlasBlink.saccade;
s.held = []; s.paced = false;
const out = {};
// Not paced (the morph is not ticking): a step's transition runs free.
anims = [make("translate")];
s.hold([iris]);
out.free = anims[0].playState;
// Paced: held at once, then set to its own time on each tick, and finished at its end.
s.pace(true);
anims = [make("translate"), make("opacity")];
s.hold([iris]);
out.held = anims.map((a) => a.playState);
const tr = anims[0];
timeline.currentTime += 100; s.pace(true); out.at100 = tr.currentTime;
timeline.currentTime += 100; s.pace(true); out.after = tr.playState; out.left = s.held.length;
// A held one when the morph stops: it runs on from its own start, so it ends when it would have.
const b = make("translate"); anims = [b];
s.hold([iris]);
timeline.currentTime += 50; s.pace(false);
out.released = [b.playState, b.currentTime, s.held.length, s.paced];
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_companion_saccade_steps_with_the_dress_tick_not_every_frame() -> None:
    """L-ui-modernisation-201: the iris is an SVG group, so its eased step ran on the main thread at 60 fps (11 frames a
    second idle, traced); on the companion it is held and set to its own time on each 100 ms morph tick instead."""
    out = subprocess.run(["node", "-e", PACE, str(JS / "atlas-motion.js")], capture_output=True, text=True, timeout=60, check=True).stdout
    r = json.loads(out)
    assert r["free"] == "running"  # no tick to step it: the CSS eases it as before
    assert r["held"] == ["paused", "running"]  # only the look's translate, never the fade
    assert r["at100"] == 100 and r["after"] == "finished" and r["left"] == 0
    assert r["released"] == ["running", 50, 0, False]


def test_the_morph_tick_paces_the_saccade_on_the_companion_only() -> None:
    life = (JS / "atlas-life.js").read_text(encoding="utf-8")
    i = life.index("atlasRigLower.morph.run = (rig, buddy) => {")
    body = life[i : life.index("atlasTailCalm.rest.wake.add(m.wake);", i)]
    assert body.count("atlasBlink.saccade.pace") >= 3  # live, not live, at rest
    motion = (JS / "atlas-motion.js").read_text(encoding="utf-8")
    j = motion.index("atlasBlink.saccade.step = ")
    assert "atlasBlink.saccade.hold(irises)" in motion[j : motion.index("\n};", j)]
