"""A resting cat is on the window, not on a tab's own dock (INBOX 1674, from the
1673 blind run: "teleports and appears and disappears").

The 2026-09-27 rule stands: a cat on a tab's own dock is cut in one frame when
you leave that tab. What changes is where a resting cat is: the window's top
edge hang and bottom bar/dock line are on every tab, so a tab change leaves it
in view. A tab's own dock is for a short visit it chose; if you leave during it
its mind walks it back within about a minute. The pure rules run in a node vm
with a fixed clock; the wiring is checked in the source.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MENU = unwrapped((JS / "companion-menu.js").read_text(encoding="utf-8"))
AV = unwrapped((JS / "avatars.js").read_text(encoding="utf-8"))
MIND = MENU[MENU.index("const NMB_MIND_ACTS") :]

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    end = AV.index("\n}\n", start)
    return AV[start : end + 3]


def _order_src() -> str:
    start = AV.index("restOrder: (base, whim = 0) =>")
    end = AV.index("\n  },\n", start)
    return AV[start : end + 5].rstrip(",\n")


def _order(base: list[str], whim: float | None) -> list[str]:
    body = "const o = { " + _order_src().rstrip(",") + " };"
    arg = "undefined" if whim is None else str(whim)
    run = subprocess.run(
        ["node", "-e", body + f"process.stdout.write(JSON.stringify(o.restOrder({json.dumps(base)}, {arg})))"],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr[-1500:]
    return json.loads(run.stdout)


@needs_node
def test_a_resting_cat_takes_the_window_perches_first_on_every_tab() -> None:
    orders = re.findall(r'^  (\w+): \[((?:"\w+"(?:, )?)+)\],$', AV[AV.index("const NAME_MARK_BUDDY_ORDER") : AV.index("const NAME_MARK_BUDDY_ORDER") + 900], re.M)
    assert len(orders) >= 8
    for tab, kinds in orders:
        base = re.findall(r'"(\w+)"', kinds)
        for whim in (0.0, 0.49, 0.5, 0.99):
            got = _order(base, whim)
            assert set(got[:2]) == {"hang", "bar"}, (tab, whim, got)
            assert sorted(got) == sorted(base), (tab, got)
    assert _order(["card", "dock", "bar", "hang"], 0.1)[:2] == ["hang", "bar"]
    assert _order(["card", "dock", "bar", "hang"], 0.9)[:2] == ["bar", "hang"]
    assert _order(["card", "dock"], None)[:2] == ["hang", "bar"]


def test_a_visit_keeps_the_tabs_own_order_and_only_a_visit_does() -> None:
    perches = _fn("nameMarkBuddyPerches")
    assert "nameMarkBuddyPerches(tab, focus = null, visit = false)" in AV
    assert "visit ? own : nmb.restOrder(own, nmb.temper?.whim)" in perches
    choose = _fn("nameMarkBuddyChoose")
    assert "per = 12, visit = false)" in choose
    assert "near && per < 12 ? near[0] : null, visit)" in choose
    assert "nameMarkBuddyChoose(tab, obstacles, near, per, visit)" in choose
    # Two callers ask for the tab's own order: the wander's far branch (a visit it chose) and a toss's landing
    # (where you let go is your choice); nothing else does.
    callers = re.findall(r"nameMarkBuddyChoose\([^;]*, true\)", AV)
    assert len(callers) == 2, callers
    assert any("[nmb.x + off, nmb.y], 4, true" in c for c in callers) and any("[x, y], 4, true" in c for c in callers)


def test_leaving_during_a_visit_keeps_the_one_frame_cut() -> None:
    changed = _fn("nameMarkBuddyTabChanged")
    assert 'buddy.classList.add("nmb-away")' in changed and "nmb.absent = true" in changed
    assert "if (!nmb.absent) nmb.absentAt = Date.now()" in changed
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    assert ".nmb-away" in css and "transition: none" in css[css.index(".nmb-away") : css.index(".nmb-away") + 1500]


def test_a_visit_over_comes_home_and_a_return_ends_it() -> None:
    mind = _fn("nameMarkBuddyMind")
    assert "homeSick: away && !!nmb.absent && !nmb.afield" in mind
    assert "absentMs: now - (nmb.absentAt || now)" in mind
    appear = _fn("nameMarkBuddyAppear")
    assert "nmb.home = null" in appear


HARNESS = r"""
const vm = require("vm");
const NOW = 1_800_000_000_000;
const ctx = {
  Math, Object, Number, JSON, Date: { now: () => NOW },
  nmb: { lastInput: NOW, keyAt: 0, mood: { energy: 0.6 }, pointer: null, cool: {}, loudAt: 0, act: "" },
  NMB_W: 64, NMB_HEAD: 52, NMB_LOUD_ACTS: [], NMB_LOUD_GAP_MS: 75000, NAME_MARK_BUDDY_ACTS: {}, NMB_LIMB_MOVES: {},
  nameMarkBuddyStill: () => false, nameMarkIdleQuiet: () => false, nameMarkBuddyActOff: () => false,
  nameMarkBuddyScrollAgo: () => Infinity, nameMarkBuddyTab: () => "notes", nameMarkBuddyActions: () => "normal",
  nameMarkBuddyCalmAllows: () => true, isAtlasSeed: () => false, setTimeout() {}, clearTimeout() {},
};
vm.createContext(ctx);
vm.runInContext(process.argv[1] + "\n;globalThis.MIND = NMB_MIND;", ctx);
const MIND = ctx.MIND;
const MIN = 60000;
// Left on a dock by a page change during a visit, 40 s ago, no floor passed, no want.
const base = () => ({ now: NOW, settledAt: NOW - 1 * MIN, stay: 1, whim: 0.9, lonely: 0, bored: 0, calm: true, userSettled: 20000,
  roomSeen: false, awake: true, blocked: false, idle: 20000, mode: "full", actions: "normal", afieldOn: true, comeOn: true, lastAfield: 0, afield: null,
  homeSick: true, absentMs: 40000 });
const out = (v) => process.stdout.write(JSON.stringify(v));
"""


def _run(body: str):
    run = subprocess.run(["node", "-e", HARNESS + body, MIND], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_a_cat_left_on_a_visit_walks_back_after_half_a_minute_and_not_before() -> None:
    got = _run(
        """
const at = (patch) => MIND.move({ ...base(), ...patch }, 0.99).kind;
out({
  late: at({}),
  early: at({ absentMs: 20000 }),
  noFloorNoWant: at({ settledAt: NOW - 1000, lonely: 0, bored: 0 }),
  diceFree: MIND.move(base(), 0.999).kind,
  notCalm: at({ calm: false }),
  flicking: at({ userSettled: 3000 }),  // flipping tabs: still comes home (it is the moment it should)
  blocked: at({ blocked: true }),
  asleep: at({ awake: false }),
  off: at({ actions: "off" }),
  notSick: at({ homeSick: false }),
});
"""
    )
    assert got["late"] == "come" and got["noFloorNoWant"] == "come" and got["diceFree"] == "come"
    assert got["flicking"] == "come", "a person flipping tabs does not hold the walk home back"
    assert got["early"] == got["notCalm"] == got["blocked"] == got["asleep"] == got["off"] == "none"
    # Without a visit the 3 minute floor and the want still rule (1673 unchanged).
    assert got["notSick"] == "none"


@needs_node
def test_a_visit_return_is_inside_about_a_minute_of_the_tick() -> None:
    got = _run("out({ k: MIND.K })")
    assert got["k"]["homeAfter"] <= 30000
    assert got["k"]["homeAfter"] + 12000 <= 60000, "30 s plus the tick's 4 to 12 s beat stays inside a minute"


def test_a_stream_pulls_the_cat_only_when_it_is_already_in_view() -> None:
    errand = _fn("nameMarkBuddyChatErrand")
    gate = errand.index("nmb.away || nmb.absent || nmb.afield || nmb.outOfSight")
    assert gate < errand.index("nameMarkBuddyErrand(")
    # The bell stays the window's own (the Reminders button is on every tab).
    assert "nmb.away" not in _fn("nameMarkBuddyBellErrand")


def test_the_crossfade_is_the_reduced_motion_entrance_only() -> None:
    walk = _fn("nameMarkBuddyWalkEnter")
    assert "if (nameMarkBuddyNoTravel())" in walk and "duration: 400" in walk
    assert walk.index("duration: 400") < walk.index("return nameMarkBuddyEnter(buddy, spot, true)")


PERCHES_HARNESS = r"""
const vm = require("vm");
const edge = (kind) => ({ kind, left: 0, right: 1440, el: null });
const ctx = {
  JSON, Math, innerWidth: 1440, NMB_GUTTER: 12, NMB_W: 64,
  NAME_MARK_BUDDY_ORDER: { notes: ["dock", "card", "under", "hang", "bar"] },
  nameMarkBuddyLedges: () => ({ top: null, bottom: null }),
  nameMarkBuddyEdges: () => ["hang", "bar", "dock", "card"].map(edge),
  nameMarkBuddyStances: (e, x) => [{ x, y: 100, pose: "sit" }],
  nmb: { temper: { whim: 0.2 } },
};
vm.createContext(ctx);
vm.runInContext(process.argv[1] + "\nnmb.restOrder = " + process.argv[2] + ";\n" + process.argv[3] + "\nglobalThis.P = nameMarkBuddyPerches;", ctx);
const first = (visit) => ctx.P("notes", null, visit)[0].kind;
process.stdout.write(JSON.stringify({ rest: first(false), visit: first(true) }));
"""


@needs_node
def test_the_perch_list_leads_with_the_tabs_own_only_for_a_visit() -> None:
    # Behaviour, not text: the real nameMarkBuddyPerches on a tab whose own order starts with its dock.
    run = subprocess.run(["node", "-e", PERCHES_HARNESS, "", _order_src().split("restOrder: ", 1)[1].rstrip(","), _fn("nameMarkBuddyPerches")], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    got = json.loads(run.stdout)
    assert got["rest"] in ("hang", "bar") and got["visit"] == "dock", got


def test_a_resting_choice_never_settles_on_a_tab_own_perch() -> None:
    choose = _fn("nameMarkBuddyChoose")
    assert 'const settling = !!best && !visit && !nmb.fitting && ["dock", "card", "under"].includes(best.kind);' in choose
    assert choose.index("if (best && !settling) return best;") < choose.index("if (settling) {")
    window = choose[choose.index("if (settling) {") :]
    window = window[: window.index("const corner")]
    assert 'spot.legs === "peek"' in window and "nmb.windowFit(tab, obstacles)" in window and "|| best" in window
    # The fitted search stays on the window's own kinds and puts the scale back.
    fit = AV[AV.index("windowFit: (tab, obstacles) =>") :]
    fit = fit[: fit.index("\n  },\n")]
    assert 'perch.kind !== "hang" && perch.kind !== "bar"' in fit and "nmb.fitting = false" in fit and "nmb.scale = saved" in fit


def test_every_place_that_marks_it_absent_stamps_when() -> None:
    for text, name in ((AV, "avatars.js"), (MENU, "companion-menu.js")):
        for hit in re.finditer(r"nmb\.absent = true;", text):
            assert "nmb.absentAt = Date.now()" in text[max(0, hit.start() - 160) : hit.start()], (name, text.count("\n", 0, hit.start()) + 1)
