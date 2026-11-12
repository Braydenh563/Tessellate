"""The companion as a house cat (INBOX 1673, the owner: "the companion moves
too much when I relatively quickly move between pages ... it should stay on
other parts or other screens for longer before moving ... like a house cat
that is there but has a mind of its own"; 1670 standing).

The room is a tab; switching tabs hides the cat with it and moves nothing.
It comes over by itself only through `NMB_MIND.move` (companion-menu.js): a
3 minute settle floor, a want (loneliness or boredom) over a per-cat
threshold, a calm moment, a settled user and a dice roll. The pure parts run
in a node vm with a fixed clock; the wiring is checked in the source.
"""

from __future__ import annotations

from tests._help_text import help_more_text
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
// A cat that has settled 10 minutes ago, wants company, in a calm moment, user settled for 2 minutes.
const base = () => ({ now: NOW, settledAt: NOW - 10 * MIN, stay: 1, whim: 0, lonely: 2, bored: 0, calm: true, userSettled: 2 * MIN,
  roomSeen: false, awake: true, blocked: false, idle: 20000, mode: "full", actions: "normal", afieldOn: true, comeOn: true, lastAfield: 0, afield: null });
const out = (v) => process.stdout.write(JSON.stringify(v));
"""


def _run(body: str):
    run = subprocess.run(["node", "-e", HARNESS + body, MIND], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


def test_the_follow_is_gone_from_the_source() -> None:
    for name in ("nameMarkBuddyArrive", "awayTimer", "NMB_DWELL_MS", "NMB_DWELL_JITTER_MS", "nameMarkBuddyUnheld", "sightTimer", "heldTimer"):
        assert name not in AV, name


def test_a_tab_switch_hides_the_cat_and_arms_nothing() -> None:
    body = AV[AV.index("function nameMarkBuddyTabChanged") :]
    body = body[: body.index("\n}\n")]
    assert "nmb-away" in body
    #: The one timer is the look that its perch is still there (a returning page, and a bar or hang
    #: moving to a new page); nothing is armed to follow.
    assert body.count("setTimeout") == 2 and body.count("nmbFollow.recheck = setTimeout(queueNameMarkBuddyCheck, 900)") == 2
    assert "nameMarkBuddyAppear(buddy)" in body and body.count("nameMarkBuddyAppear") == 1
    assert "nmb.absent = true" in body and "nmb.lonelyTouch(true)" in body


def test_a_perch_check_never_queues_a_place_for_another_tab() -> None:
    check = AV[AV.index("function nameMarkBuddyCheck") :]
    check = check[: check.index("\n}\n")]
    assert "if (tab !== nmb.tab) return;" in check
    assert "its perch went" in check and "nameMarkBuddyPerchGone" in check


def test_a_perch_out_of_view_is_not_a_perch_gone() -> None:
    sup = AV[AV.index("function nameMarkBuddySupported") :]
    sup = sup[: sup.index("\n}\n")]
    assert "tested" in sup and "if (!tested) return true;" in sup


def test_perch_gone_falls_then_steps_then_walks_and_never_poofs() -> None:
    body = AV[AV.index("function nameMarkBuddyPerchGone") :]
    body = body[: body.index("\n}\n")]
    assert body.index("nameMarkBuddyDrop") < body.index("nameMarkBuddyChoose")
    assert "poof" not in body.lower()
    assert "outOfSight" in AV[AV.index("function nameMarkBuddyCheck") :][:6000]


def test_a_view_change_does_not_choose_a_new_bar_perch() -> None:
    beat = AV[AV.index("function nameMarkBuddyBeat") :]
    beat = beat[: beat.index("\n}\n")]
    assert '["bar", "hang", "corner"]' not in beat


def test_the_come_in_is_a_walk_of_at_least_1200ms() -> None:
    assert "function nameMarkBuddyWalkEnter" in AV
    body = AV[AV.index("function nameMarkBuddyWalkEnter") :]
    body = body[: body.index("\n}\n")]
    assert "nameMarkBuddyEnter(buddy, spot, true)" in body and "duration: 400" in body
    enter = AV[AV.index("function nameMarkBuddyEnter") :]
    enter = enter[: enter.index("\n}\n")]
    assert "nmb.mind?.walkMs" in enter and "visit ? 1400 : 720" in enter
    assert "if (!visit && !nameMarkBuddyShowy()" in enter


@needs_node
def test_nothing_moves_before_the_settle_floor_whatever_the_want() -> None:
    r = _run("""
const o = base(); o.lonely = 3; o.settledAt = NOW - 2.9 * MIN;
out([MIND.move(o, 0).kind, MIND.move({ ...o, settledAt: NOW - 3.1 * MIN }, 0).kind]);
""")
    assert r == ["none", "come"]


@needs_node
def test_a_user_who_just_switched_tabs_is_not_followed() -> None:
    r = _run("""
const o = base();
out([MIND.move({ ...o, userSettled: 44000 }, 0).kind, MIND.move({ ...o, userSettled: 46000 }, 0).kind]);
""")
    assert r == ["none", "come"]


@needs_node
def test_come_needs_want_calm_and_the_roll() -> None:
    r = _run("""
const o = base();
out([MIND.move({ ...o, lonely: 0.5 }, 0).kind, MIND.move({ ...o, calm: false }, 0).kind, MIND.move(o, 0.9).kind, MIND.move(o, 0.1).kind,
     MIND.move({ ...o, blocked: true }, 0).kind, MIND.move({ ...o, awake: false }, 0).kind, MIND.move({ ...o, comeOn: false }, 0).kind]);
""")
    assert r == ["none", "none", "none", "come", "none", "none", "none"]


@needs_node
def test_the_threshold_is_the_cats_own() -> None:
    r = _run("""
const o = base(); o.lonely = 1.4;
out([MIND.move({ ...o, whim: 0 }, 0).kind, MIND.move({ ...o, whim: 0.9 }, 0).kind]);
""")
    assert r == ["come", "none"]


@needs_node
def test_lonely_rises_unseen_and_halves_in_three_minutes_seen() -> None:
    r = _run("""
let l = 0;
for (let i = 0; i < 4; i++) l = MIND.lonelyStep(l, 60000, false, 0.7);
const seen = MIND.lonelyStep(2, 180000, true, 0.7);
// flicking 6 tabs for 60 s: seen five sixths of the time
let f = 0;
for (let i = 0; i < 6; i++) { f = MIND.lonelyStep(f, 8000, false, 0.7); f = MIND.lonelyStep(f, 2000, true, 0.7); }
out([l, seen, f, MIND.lonelyStep(2.9, 600000, false, 0.7)]);
""")
    assert 1.1 < r[0] < 1.3
    assert abs(r[1] - 1) < 0.01
    assert r[2] < 0.3
    assert r[3] == 3


@needs_node
def test_a_bored_cat_in_view_strolls_and_an_idle_one_may_go_out() -> None:
    r = _run("""
const o = { ...base(), roomSeen: true, lonely: 0, bored: 2, idle: 20000 };
out([MIND.move(o, 0).kind, MIND.move({ ...o, idle: 4 * MIN }, 0).kind, MIND.move({ ...o, idle: 4 * MIN, actions: "fewer" }, 0).kind,
     MIND.move({ ...o, idle: 4 * MIN, mode: "reduced" }, 0).kind, MIND.move({ ...o, idle: 4 * MIN, afieldOn: false }, 0).kind,
     MIND.move({ ...o, idle: 4 * MIN, lastAfield: NOW - 5 * MIN }, 0).kind]);
""")
    assert r == ["stroll", "afield", "stroll", "stroll", "stroll", "stroll"]


@needs_node
def test_reduced_motion_doubles_the_floor_and_needs_a_quiet_page() -> None:
    r = _run("""
const o = { ...base(), mode: "reduced", settledAt: NOW - 5 * MIN };
out([MIND.move(o, 0).kind, MIND.move({ ...o, settledAt: NOW - 7 * MIN, idle: 4000 }, 0).kind, MIND.move({ ...o, settledAt: NOW - 7 * MIN, idle: 9000 }, 0).kind,
     MIND.floor({ stay: 1, mode: "reduced", actions: "normal" }), MIND.floor({ stay: 1, mode: "full", actions: "fewer" })]);
""")
    assert r == ["none", "none", "come", 360000, 270000]


@needs_node
def test_a_cat_that_is_out_returns_after_its_time_and_stays_out_before() -> None:
    r = _run("""
const o = { ...base(), roomSeen: true, afield: { until: NOW + MIN } };
out([MIND.move(o, 0).kind, MIND.move({ ...o, afield: { until: NOW - 1 } }, 0).kind, MIND.move({ ...o, afield: { until: NOW - 1 }, calm: false }, 0).kind,
     MIND.awayFor(0.5, 0.5), MIND.awayFor(1, 0), MIND.awayFor(0, 1)]);
""")
    assert r[:3] == ["none", "return", "none"]
    assert all(90000 <= v <= 240000 + 20000 for v in r[3:])


@needs_node
def test_the_walk_in_is_paced_and_clamped() -> None:
    r = _run("""
out([MIND.walkMs(100, 0.5), MIND.walkMs(5000, 0.5), MIND.walkMs(600, 0), MIND.walkMs(600, 1), MIND.walkMs(922, 0.5)]);
""")
    assert r[0] == 1200 and r[1] == 12000
    assert 600 * 6 <= r[2] <= r[3] <= 600 * 11
    #: A 922px walk keeps the 90 to 170 px a second pace (the cap once cut it to 6 s).
    assert 922 * 6 <= r[4] <= 922 * 11


def test_the_two_switches_and_the_guide_say_what_the_cat_does() -> None:
    """Help moves with the UI (standing order 13): the switches exist and the topic no longer says it finds a spot on each page."""
    assert '["come", "Come over to you after a few minutes apart", ["come"]]' in AV
    assert '["afield", "Go out for a while now and then", ["afield"]]' in AV
    topics = help_more_text()
    assert "finds a free spot on each page" not in topics and "Stay here on every page" in topics
    assert "goes out for a while" in topics and "Reduce actions on Normal" in topics
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "Fewer also stops it going out for a while" in html and "stays when you switch pages" in html
    assert not re.search(r"\u2014", topics + html[html.index("Fewer also stops") - 200 : html.index("Fewer also stops") + 200])


SETTINGS = (JS / "companion-settings.js").read_text(encoding="utf-8")


def test_call_back_unhides_a_cat_hidden_with_its_page() -> None:
    #: The reviewer's finding 1: Call back left `nmb-away` on, so the one button for a lost cat did nothing.
    body = SETTINGS[SETTINGS.index("function nameMarkBuddyCallBack") :]
    body = body[: body.index("\n}\n")]
    for part in ("nmb.away = false", "nmb.absent = false", 'classList.remove("nmb-away")', "nmb.afield = null", "nmb.leaving = false", "clearTimeout(nmb.appearTimer)"):
        assert part in body, part
    assert body.index("nmb.away = false") < body.index("placeNameMarkBuddy(")
    assert "!wasAway && " in body


def test_a_still_cat_hidden_with_its_page_still_comes() -> None:
    fn = AV[AV.index("  fadeComes() {") :]
    fn = fn[: fn.index("\n  },")]
    assert '!== "full"' in fn and '=== "fades"' not in fn
    walk = AV[AV.index("function nameMarkBuddyWalkEnter") :]
    walk = walk[: walk.index("\n}\n")]
    assert 'mode === "still"' in walk


def test_the_mind_is_asked_for_where_a_hidden_cat_needs_it() -> None:
    mind = AV[AV.index("function nameMarkBuddyMind") :]
    mind = mind[: mind.index("\n}\n")]
    assert 'ensureModule("companionMenu")' in mind
    tab = AV[AV.index("nmb.cameFrom = nameMarkBuddyTabSide") - 400 : AV.index("nmb.cameFrom = nameMarkBuddyTabSide")]
    assert 'ensureModule("companionMenu")' in tab
    touch = AV[AV.index("  lonelyTouch(unseen) {") :]
    touch = touch[: touch.index("\n  },")]
    assert touch.index("nmb.mind?.lonelyStep") < touch.index("nmb.lonelyAt = now")


def test_a_refused_stroll_is_not_counted() -> None:
    mind = AV[AV.index("function nameMarkBuddyMind") :]
    mind = mind[: mind.index("\n}\n")]
    stroll = mind[mind.index('decided.kind === "stroll"') :]
    assert stroll.index("nameMarkBuddyWander(now, true)") < stroll.index("nmb.moves = ")
