"""The companion's mind (B87c, B88c, the owner, 2026-10-17: "the companion
needs a lot of improvements in behaviour, actions and lifelike ncp decision
making"; "more movement, more transition and actions").

`NMB_MIND` (companion-menu.js, fetched at the first tick) weighs what you
are doing into the pick, places the wait within the decided 20 to 60
seconds (Brief 34), leads into a big act on a beat, breathes out after one
and sometimes follows it with the act that comes of it, and adds three acts.
The pure parts run here in a node vm with a fixed clock; the boot hooks are
checked in the source.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MENU = (JS / "companion-menu.js").read_text(encoding="utf-8")
AV = (JS / "avatars.js").read_text(encoding="utf-8")
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
MIND = MENU[MENU.index("const NMB_MIND_ACTS") :]

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
const NOW = 1_800_000_000_000;
const calls = [];
const timers = [];
const char = { animate: (...a) => { calls.push(["animate", a[1].duration]); return {}; } };
const classes = new Set();
const buddy = { isConnected: true, dataset: { seed: "x" }, classList: { contains: (c) => classes.has(c) }, querySelector: () => char };
const ctx = {
  Math, Object, Number, JSON, Date: { now: () => NOW },
  nmb: { lastInput: NOW, keyAt: 0, mood: { energy: 0.6 }, pointer: null, x: 500, y: 400, pose: "stand", cool: {}, loudAt: 0, atlasLook: "masculine", act: "" },
  NMB_W: 64, NMB_HEAD: 52, NMB_LOUD_ACTS: ["hop", "wave", "stretch", "shrug", "scratch"], NMB_LOUD_GAP_MS: 75000,
  NAME_MARK_BUDDY_ACTS: { nod: { poses: ["stand", "sit"] }, look: { poses: ["stand"] }, stretch: { poses: ["stand"] }, shrug: { poses: ["stand"] }, ponder: { poses: ["stand"] } },
  NMB_LIMB_MOVES: {},
  still: false, quiet: false, off: new Set(), scrollAgo: Infinity, tab: "notes", actions: "normal",
  nameMarkBuddyStill: () => ctx.still, nameMarkIdleQuiet: () => ctx.quiet, nameMarkBuddyActOff: (a) => ctx.off.has(a),
  nameMarkBuddyScrollAgo: () => ctx.scrollAgo, nameMarkBuddyTab: () => ctx.tab, nameMarkBuddyActions: () => ctx.actions,
  nameMarkBuddyCalmAllows: (now, loudAt, gap, keyAt, s) => now - loudAt >= gap && now - keyAt >= 4000 && !(s < 2000),
  nameMarkBuddyAim: () => calls.push(["aim"]), nameMarkBuddyAct: (a) => calls.push(["act", a]), nameMarkBuddySchedule: () => calls.push(["schedule"]),
  nameMarkBuddyLimbs: (b, k, ms) => calls.push(["limbs", k, ms]), nameMarkBuddyTilt: (v) => calls.push(["tilt", v]),
  nameMarkBuddyExpress: (e, ms, o) => calls.push(["express", e, !!o.drift]), isAtlasSeed: () => false,
  setTimeout: (f, ms) => { timers.push([f, ms]); return timers.length; }, clearTimeout() {},
};
ctx.ctx = ctx;
vm.createContext(ctx);
vm.runInContext(process.argv[1] + "\n;globalThis.MIND = NMB_MIND;", ctx);
const MIND = ctx.MIND;
const out = (v) => process.stdout.write(JSON.stringify(v));
"""


def _run(body: str):
    run = subprocess.run(["node", "-e", HARNESS + body, MIND], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_what_you_are_doing_moves_the_pick() -> None:
    out = _run(
        r"""
const d = (setup) => { Object.assign(ctx.nmb, { keyAt: 0, lastInput: NOW, pointer: null }); ctx.scrollAgo = Infinity; ctx.tab = "dashboard"; setup(); return MIND.drive(NOW); };
out({
  typing: d(() => { ctx.nmb.keyAt = NOW - 2000; }),
  scrolling: d(() => { ctx.scrollAgo = 1000; }),
  present: d(() => { ctx.nmb.lastInput = NOW - 60000; }),
  away: d(() => { ctx.nmb.lastInput = NOW - 5 * 60000; }),
  near: d(() => { ctx.nmb.pointer = [540, 420]; ctx.nmb.lastInput = NOW - 1000; }),
  graph: d(() => { ctx.tab = "graph"; }),
  chat: d(() => { ctx.tab = "chat"; }),
});
"""
    )
    t = out["typing"]
    assert t["read"] > 1 and t["ponder"] > 1, "typing, it keeps you company quietly"
    assert t["wave"] < 1 and t["hop"] < 1 and t["juggle"] < 1, "and saves the big gestures"
    assert out["scrolling"]["look"] > 1 and out["scrolling"]["turn"] > 1
    assert out["present"]["juggle"] > 1 and out["present"]["stretch"] > 1 and out["present"]["toss"] > 1, "idle there, it plays"
    assert out["away"]["meditate"] > 1 and out["away"]["juggle"] < 1, "gone a while, it winds down"
    assert out["near"]["glance"] > 1, "the pointer close by, it notices you"
    assert out["graph"]["map"] > 1 and out["chat"]["ponder"] > 1, "each tab leans it to its own thing"


@needs_node
def test_the_wait_stays_in_the_decided_range_and_follows_the_moment() -> None:
    out = _run(
        r"""
const at = (setup, roll) => { Object.assign(ctx.nmb, { keyAt: 0, lastInput: NOW, loudAt: 0, mood: { energy: 0.6 } }); setup(); return MIND.nextIn(NOW, roll); };
const all = [];
for (const roll of [0, 0.25, 0.5, 0.75, 0.999]) for (const e of [0, 0.5, 1]) for (const k of [0, NOW - 1000]) for (const idle of [0, 60000, 600000]) all.push(at(() => { ctx.nmb.mood.energy = e; ctx.nmb.keyAt = k; ctx.nmb.lastInput = NOW - idle; }, roll));
out({
  min: Math.min(...all), max: Math.max(...all),
  typing: at(() => { ctx.nmb.keyAt = NOW - 1000; }, 0.5), idling: at(() => { ctx.nmb.lastInput = NOW - 60000; }, 0.5),
  tired: at(() => { ctx.nmb.mood.energy = 0.1; }, 0.5), lively: at(() => { ctx.nmb.mood.energy = 0.95; }, 0.5),
  spent: at(() => { ctx.nmb.loudAt = NOW - 10000; }, 0.5), plain: at(() => {}, 0.5),
});
"""
    )
    assert out["min"] >= 20000 and out["max"] <= 60000, (out["min"], out["max"])
    assert out["typing"] > out["idling"] + 10000, "it leaves you be while you type, and fidgets while you sit idle"
    assert out["tired"] > out["lively"], "low energy, longer between"
    assert out["spent"] > out["plain"], "a big act just done, a longer rest"


@needs_node
def test_a_big_act_is_led_into_on_a_beat() -> None:
    out = _run(
        r"""
const r = {};
r.quiet = MIND.lead(buddy, "blink");
r.led = MIND.lead(buddy, "wave");
r.callsBefore = calls.map((c) => c[0]);
const [f, ms] = timers.pop();
r.ms = ms;
f();
r.after = calls.slice(-1)[0];
MIND.lead(buddy, "stretch");
classes.add("nm-buddy-dragging");
timers.pop()[0]();
r.grabbed = calls.slice(-1)[0];
classes.clear();
ctx.still = true;
r.still = MIND.lead(buddy, "wave");
ctx.still = false;
ctx.quiet = true;
r.reduced = MIND.lead(buddy, "wave");
out(r);
"""
    )
    assert out["quiet"] is False, "a blink needs no beat"
    assert out["led"] is True and "animate" in out["callsBefore"]
    assert 150 <= out["ms"] <= 350
    assert out["after"] == ["act", "wave"], "the act comes on the beat"
    assert out["grabbed"] == ["schedule"], "picked up in the beat, the act does not start"
    assert out["still"] is False and out["reduced"] is False, "no beat under Still or reduced motion"


@needs_node
def test_after_an_act_it_breathes_out_and_sometimes_follows_on() -> None:
    out = _run(
        r"""
const r = {};
r.nod = MIND.after(buddy, "juggle", 0.1, NOW);
r.none = MIND.after(buddy, "juggle", 0.9, NOW);
r.breath = calls.filter((c) => c[0] === "animate").length;
ctx.off.add("nod");
r.off = MIND.after(buddy, "juggle", 0.1, NOW);
ctx.off.clear();
ctx.nmb.pose = "hang";
r.pose = MIND.after(buddy, "juggle", 0.1, NOW);
ctx.nmb.pose = "stand";
ctx.nmb.keyAt = NOW - 1000;
r.calm = MIND.after(buddy, "ponder", 0.5, NOW);
ctx.nmb.keyAt = 0;
ctx.nmb.visit = {};
r.visit = MIND.after(buddy, "juggle", 0.1, NOW);
ctx.nmb.visit = null;
ctx.still = true;
r.still = MIND.after(buddy, "juggle", 0.1, NOW);
out(r);
"""
    )
    assert out["nod"] == "nod", "a pleased nod after juggling"
    assert out["none"] == ""
    assert out["breath"] >= 2, "a breath out after a big act"
    assert out["off"] == "" and out["pose"] == "", "never a switched-off act or one that does not suit its pose"
    assert out["calm"] == "", "a loud follow-on waits for the calm budget"
    assert out["visit"] == "" and out["still"] == ""


@needs_node
def test_the_new_acts_move_and_wear_a_face() -> None:
    out = _run(
        r"""
MIND.start(buddy, "ponder", 4200);
MIND.start(buddy, "sigh", 1700);
MIND.start(buddy, "wave", 1500);
out({ calls, acts: Object.keys(ctx.NAME_MARK_BUDDY_ACTS), limbs: Object.keys(ctx.NMB_LIMB_MOVES), mind: !!ctx.nmb.mind });
"""
    )
    kinds = [c[0] + ":" + str(c[1]) for c in out["calls"]]
    assert "limbs:ponder" in kinds and ("tilt:-0.45" in kinds or "tilt:0.45" in kinds)
    assert "express:confused" in kinds
    assert "limbs:sigh" in kinds
    assert not any(k.startswith("limbs:wave") for k in kinds), "an act with its own CSS is left to it"
    for act in ("ponder", "sigh", "toss"):
        assert act in out["acts"]
    assert {"ponder", "sigh"} <= set(out["limbs"]) and out["mind"]


def test_every_new_act_has_a_switch_and_the_hooks_are_wired() -> None:
    rows = AV[AV.index("const NMB_ACTIVITIES = [") :]
    rows = rows[: rows.index("];")]
    for act in ("ponder", "sigh", "toss"):
        assert f'"{act}"' in rows, f"{act} has a row in What it does"
    for hook in ("nmb.mind?.drive(", "nmb.mind?.nextIn(", "nmb.mind?.lead(", "nmb.mind?.start(", "nmb.mind?.after(", 'ensureModule("companionMenu")'):
        assert hook in AV, hook
    # Brief 34's envelope: the mind places the wait, it does not move it.
    assert "20000 + 40000 * Math.max(0, Math.min(1, f))" in MIND


@needs_node
def test_atlas_tosses_one_star_from_its_right_hand() -> None:
    harness = (ROOT / "tests" / "test_atlas_stars.py").read_text(encoding="utf-8")
    start = harness.index('HARNESS = r"""') + len('HARNESS = r"""')
    script = harness[start : harness.index('"""', start)] + r"""
classes.add("nmb-act-toss");
ctx.__wake(box);
const ys = [];
run(30);
run(132, () => ys.push(at(1)[1]));
const sh = rig.arms[1].j.sh.x;
process.stdout.write(JSON.stringify({ ys, sh, others: [stars[0].style.opacity, stars[2].style.opacity], shown: root.style.opacity, arc: arc.style.opacity }));
"""
    run = subprocess.run(["node", "-e", script, MOTION, "live"], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    out = json.loads(run.stdout)
    assert min(out["ys"]) <= 4 and max(out["ys"]) >= 16, "up over the head and back to the hand"
    assert out["others"] == ["0", "0"] and out["shown"] == "1" and out["arc"] == "0"
    assert out["sh"] < -40, "the right arm is up to throw"


def test_every_menu_action_answers_with_something_it_does() -> None:
    # The BACKLOG popup-actions audit (owner, 2026-10-12: "some popup icons and
    # actions are not animated"). Each row of the companion's menu, read in
    # companion-1018: Say hello pokes it, Enlarge opens its view, Let it choose
    # and Tuck and Call back walk it, Companion and Atlas look rebuild it, Size
    # eases (`nmb-fitting`), Hide leaves. "Stay here on every page" alone moved
    # nothing (an instant, pinned move to where it already was), so the press
    # showed no sign of having worked. It nods, where a nod fits its pose.
    start = MENU.index("{ group: \"place\", label: \"ph:push-pin Stay here on every page\"")
    pin = MENU[start : MENU.index("} },", start)]
    assert 'nameMarkBuddyAct("nod")' in pin
    assert "NAME_MARK_BUDDY_ACTS.nod.poses.includes(nmb.pose)" in pin and "nameMarkBuddyStill()" in pin
    assert pin.index('nameMarkBuddyMoveTo(buddy, { kind: "pinned"') < pin.index('nameMarkBuddyAct("nod")')
