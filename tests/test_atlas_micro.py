"""Atlas's small behaviours (INBOX 1322b, the owner, 2026-10-19: "atlas needs
to have its animations and expressions improved behaviours, even micro
behaviours and movements, small movement adjustments, more variety").

`atlas-micro.js` (lazy, with the rig) runs one randomised clock: a glance at
the pointer, the focused field or elsewhere, a head tilt, a shift of weight,
an ear flick, a short passing expression. Timing and choice are random and
weighted by context, never the same twice in a row, and none of it runs
under reduced motion, on a hidden tab or while something else has the
companion. It uses Web Animations and timers only: no frame loop.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MICRO = (ROOT / "frontend" / "js" / "atlas-micro.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
let seed = 7;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296);
const timers = [];
const calls = { anim: [], aim: [], mood: [], blink: 0, raf: 0, sparks: [] };
const ends = [];
const animEl = (name) => ({ name, style: {}, classList: { contains: () => false }, animate(frames, opts) { calls.anim.push({ name, frames, opts }); return { cancel() {}, finished: new Promise((done) => ends.push(done)) }; } });
const hand = { name: "hand", children: [], isConnected: true };
const heads = [animEl("head"), animEl("hair")];
const body = animEl("body");
const ears = [animEl("ear-l"), animEl("ear-r")];
const buddy = { id: "nm-buddy", dataset: { pose: "stand" }, classList: { contains: (c) => buddy.on.has(c), [Symbol.iterator]: () => buddy.on[Symbol.iterator]() }, on: new Set() };
const box = {
  isConnected: true, dataset: { atlasMood: "calm", atlasLook: "feminine" }, atlasRig: { heads, arms: [{ side: "r", hand, geo: { segs: [[0, 0, 0, 0, 0, 0, 40, 30], [0, 0, 0, 0, 0, 0, 46, 38]] } }, { side: "l", hand: null, geo: { segs: [[0, 0, 0, 0, 0, 0, 20, 30], [0, 0, 0, 0, 0, 0, 14, 38]] } }] }, classList: { contains: () => false },
  closest: () => buddy,
  querySelector: (s) => (s.includes("atl-lw-body") ? body : null),
  querySelectorAll: (s) => (s.includes("atl-ear") ? ears : []),
};
let ok = true;
const ctx = {
  console, Math: Object.assign(Object.create(Math), { random: rnd }), Number, Object, Set, Map, JSON, Date, Array,
  setTimeout: (f, ms) => { timers.push([f, ms]); return timers.length; }, clearTimeout() {},
  document: { hidden: false, activeElement: null, documentElement: { hasAttribute: () => false, dataset: {} }, querySelectorAll: () => [box], querySelector: () => box },
  innerWidth: 1200, innerHeight: 800,
  requestAnimationFrame: () => { calls.raf += 1; },
  atlasMotionOK: () => ok, atlasBlink: () => { calls.blink += 1; }, nameMarkBuddyActOff: () => false,
  nmb: { pointer: [600, 300], lastInput: 0, keyAt: 0, act: "", visit: null },
  nameMarkBuddyAim: (p) => calls.aim.push(p), nameMarkBuddyMenuOpen: () => false,
  atlasSpark: (parent, x, y, k, cls) => {
    const el = animEl(cls);
    Object.assign(el, { x, y, k, parent, gone: false, remove() { el.gone = true; parent.children = parent.children.filter((c) => c !== el); } });
    parent.children.push(el);
    calls.sparks.push(el);
    return el;
  },
  setAtlasMood: (m, ms) => calls.mood.push([m, ms]), atlasMoodNow: "calm", atlasDriftState: { changedAt: 0 },
};
vm.createContext(ctx);
vm.runInContext(process.argv[1] + "\n;Object.assign(globalThis, { __pick: atlasMicroPick, __gap: atlasMicroGap, __tick: atlasMicroTick, __may: atlasMicroMay, __start: atlasMicroStart, __cast: atlasMicroCast });", ctx);
"""


def _run(body: str):
    run = subprocess.run(["node", "-e", HARNESS + body, MICRO], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_gaps_are_random_and_bounded() -> None:
    out = _run('const g = Array.from({length: 300}, () => ctx.__gap()); process.stdout.write(JSON.stringify({ g }));')
    assert min(out["g"]) >= 1200 and max(out["g"]) <= 11000
    assert len({round(x) for x in out["g"]}) > 250, "no two beats alike"
    assert max(out["g"]) - min(out["g"]) > 5000, "some quick, some long stares"


@needs_node
def test_choice_varies_never_repeats_and_follows_context() -> None:
    out = _run(
        r"""
const base = { typing: false, idle: 0, hour: 14, mood: "calm" };
let last = "";
const seq = [];
for (let i = 0; i < 400; i += 1) { const n = ctx.__pick({ ...base }, last); seq.push(n); last = n; }
const typing = {}, night = {};
for (let i = 0; i < 600; i += 1) { const a = ctx.__pick({ ...base, typing: true }, ""); typing[a] = (typing[a] || 0) + 1; const b = ctx.__pick({ ...base, hour: 1, idle: 90000 }, ""); night[b] = (night[b] || 0) + 1; }
process.stdout.write(JSON.stringify({ seq, typing, night }));
"""
    )
    assert len(set(out["seq"])) >= 6, set(out["seq"])
    assert all(a != b for a, b in zip(out["seq"], out["seq"][1:])), "never the same twice running"
    assert out["typing"].get("focus", 0) > out["typing"].get("sleepy", 0), "typing: a set jaw, not a doze"
    assert out["night"].get("sleepy", 0) > 0 and out["night"].get("sleepy", 0) > out["typing"].get("sleepy", 0)


@needs_node
def test_a_tick_moves_something_small_and_never_uses_a_frame_loop() -> None:
    out = _run(
        r"""
ctx.__start();
for (let i = 0; i < 80; i += 1) { const [f] = timers.shift() || []; if (f) f(); }
const kinds = new Set(calls.anim.map((a) => a.name));
const big = calls.anim.filter((a) => a.frames.some((f) => parseFloat(f.rotate || 0) > 6 || Math.abs(parseFloat(String(f.transform || "").replace("rotate(", "") || 0)) > 6 || Math.abs(parseFloat(f.translate || 0)) > 2));
const added = [...new Set(calls.anim.filter((a) => a.opts.composite === "add").map((a) => a.name))];
const replaced = [...new Set(calls.anim.filter((a) => !a.opts.composite).map((a) => a.name))];
process.stdout.write(JSON.stringify({ kinds: [...kinds], aim: calls.aim.length, mood: calls.mood.length, raf: calls.raf, big: big.length, added, replaced }));
"""
    )
    assert out["raf"] == 0
    assert out["big"] == 0, "micro means a few degrees and a pixel"
    # Audit 1031 row 17: a Web Animation that adds (`composite: "add"`) or shares
    # a property with a running loop cannot be composited, and one such animation
    # puts every loop on the figure back on the main thread (60 style recalcs a
    # second). The seconds-long moves (tilt, shift) replace a property the loops
    # leave alone; only the ear flick (a third of a second) still adds.
    assert out["added"] == ["ear-l", "ear-r"] or set(out["added"]) <= {"ear-l", "ear-r"}, out["added"]
    assert {"head", "hair", "body"} <= set(out["replaced"]), out["replaced"]
    assert {"head", "body"} <= set(out["kinds"]) and out["aim"] > 0


@needs_node
def test_reduced_motion_hidden_tab_and_a_busy_companion_hold_it_still() -> None:
    out = _run(
        r"""
const res = {};
ok = false; res.reduced = ctx.__may(box);
ok = true; res.free = ctx.__may(box);
ctx.document.hidden = true; res.hidden = ctx.__may(box); ctx.document.hidden = false;
buddy.on.add("nmb-act-wave"); res.act = ctx.__may(buddy.on.size && box); buddy.on.clear();
buddy.on.add("nmb-sleep"); res.sleep = ctx.__may(box); buddy.on.clear();
buddy.on.add("nm-buddy-dragging"); res.drag = ctx.__may(box); buddy.on.clear();
ok = false; ctx.__start(); for (let i = 0; i < 10; i += 1) { const [f] = timers.shift() || []; if (f) f(); }
res.moved = calls.anim.length + calls.aim.length + calls.mood.length;
process.stdout.write(JSON.stringify(res));
"""
    )
    assert out == {"reduced": False, "free": True, "hidden": False, "act": False, "sleep": False, "drag": False, "moved": 0}


@needs_node
def test_a_passing_expression_only_from_calm_and_short() -> None:
    out = _run(
        r"""
for (let i = 0; i < 400; i += 1) { ctx.__start(); const [f] = timers.shift() || []; if (f) f(); }
ctx.atlasMoodNow = "happy"; const before = calls.mood.length;
for (let i = 0; i < 200; i += 1) { ctx.__start(); const [f] = timers.shift() || []; if (f) f(); }
process.stdout.write(JSON.stringify({ moods: [...new Set(calls.mood.map((m) => m[0]))], longest: Math.max(...calls.mood.map((m) => m[1])), grew: calls.mood.length - before }));
"""
    )
    assert len(out["moods"]) >= 3
    assert set(out["moods"]) <= {"curious", "happy", "sleepy", "determined", "surprised", "shy", "thinking"}
    assert out["longest"] <= 3600
    assert out["grew"] == 0, "never over a mood something else set"


def test_fetched_once_by_the_blink_clock_that_starts_it() -> None:
    motion = (ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")
    assert 'lazyScript("/js/atlas-micro.js")' in motion and "atlasMicroStart()" in motion


# --- INBOX 1576: the feminine Atlas's stars are a thing she does, not a thing she wears ---------------


@needs_node
def test_only_the_feminine_look_casts_and_not_straight_after_a_cast() -> None:
    out = _run(
        r"""
const base = { typing: false, idle: 0, hour: 14, mood: "calm" };
const tally = (c) => { const t = {}; for (let i = 0; i < 4000; i += 1) { const k = ctx.__pick({ ...base, ...c }, ""); t[k] = (t[k] || 0) + 1; } return t; };
process.stdout.write(JSON.stringify({ fem: tally({ look: "feminine" }), masc: tally({ look: "masculine" }), none: tally({}), soon: tally({ look: "feminine", sinceCast: 5000 }), typing: tally({ look: "feminine", typing: true }) }));
"""
    )
    assert out["fem"].get("cast", 0) > 0, "a beat now and then"
    assert out["fem"]["cast"] / 4000 < 0.12, "now and then, not every few beats"
    assert out["masc"].get("cast", 0) == 0 and out["none"].get("cast", 0) == 0
    assert out["soon"].get("cast", 0) == 0, "a pause between two casts"
    assert out["typing"].get("cast", 0) < out["fem"]["cast"], "she lets you type"


@needs_node
def test_a_cast_throws_stars_from_the_left_hand_that_fade_in_about_a_second_and_go() -> None:
    out = _run(
        r"""
const made = ctx.__cast(box);
const first = calls.sparks.length;
const frames = calls.anim.filter((a) => /atl-cast-star/.test(a.name));
const again = ctx.__cast(box);
const during = calls.sparks.length;
ends.splice(0).forEach((done) => done());
setTimeout(() => process.stdout.write(JSON.stringify({
  made, again, first, during,
  parents: [...new Set(calls.sparks.map((s) => s.parent.name))],
  props: [...new Set(frames.flatMap((a) => a.frames.flatMap((f) => Object.keys(f))))].sort(),
  opts: frames.map((a) => Object.keys(a.opts).sort().join(",")).filter((v, i, all) => all.indexOf(v) === i),
  at: calls.sparks.map((s) => [s.x, s.y]),
  fade: frames.map((a) => { const hit = a.frames.find((f) => f.opacity === 1); return [a.opts.duration, hit.offset, a.opts.delay || 0]; }),
  start: frames.map((a) => a.frames[0].opacity),
  end: frames.map((a) => a.frames[a.frames.length - 1].opacity),
  left: calls.sparks.filter((s) => !s.gone).length, rest: hand.children.length,
  raf: calls.raf,
})), 0);
"""
    )
    assert out["made"] is True and out["first"] >= 3, "a small handful"
    assert out["again"] is False and out["during"] == out["first"], "one cast at a time"
    assert out["parents"] == ["hand"], "from her left hand, riding with it"
    # Her left hand is the rig's arm "r", drawn on the viewer's right, where the
    # owner saw the stars (INBOX 1589; 1576 cast from arm "l", the other hand).
    assert set(out["at"][0]) == {46, 38}, "drawn at the hand's wrist, where the rig puts the hand"
    # Only the compositor's properties: transform and opacity (and the keyframes' offsets).
    assert set(out["props"]) <= {"transform", "opacity", "offset"}, out["props"]
    assert all("composite" not in o for o in out["opts"])
    for duration, offset, delay in out["fade"]:
        assert 800 <= duration * offset <= 1300, "fading in about a second"
        assert delay < 1200, "staggered, not scattered"
    assert set(out["start"]) == {0} and set(out["end"]) == {0}, "never drawn before or after"
    assert out["left"] == 0 and out["rest"] == 0, "at rest she wears none"
    assert out["raf"] == 0


@needs_node
def test_a_cast_does_nothing_under_reduced_motion_or_off_the_feminine_look() -> None:
    out = _run(
        r"""
const res = {};
ok = false; res.reduced = ctx.__cast(box);
ok = true; box.dataset.atlasLook = "masculine"; res.masculine = ctx.__cast(box); box.dataset.atlasLook = "feminine";
box.atlasRig.arms[0].hand = null; res.handless = ctx.__cast(box); box.atlasRig.arms[0].hand = hand;
ok = false; ctx.__start(); for (let i = 0; i < 40; i += 1) { const [f] = timers.shift() || []; if (f) f(); }
res.stars = calls.sparks.length;
process.stdout.write(JSON.stringify(res));
"""
    )
    assert out == {"reduced": False, "masculine": False, "handless": False, "stars": 0}


@needs_node
def test_the_clock_casts_for_a_feminine_figure_on_a_calm_beat() -> None:
    out = _run(
        r"""
for (let i = 0; i < 1500; i += 1) { ctx.__start(); const [f] = timers.shift() || []; if (f) f(); ends.splice(0).forEach((done) => done()); }
process.stdout.write(JSON.stringify({ casts: calls.anim.filter((a) => /atl-cast-star/.test(a.name)).length }));
"""
    )
    assert out["casts"] > 0
