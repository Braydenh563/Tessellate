"""How the companion travels, and what it does instead of travelling (INBOX 1429).

The owner: "the companion always chooses to jump across the screen and it is
very visually distracting. I need it to choose more things, like summoning a
portal and walking through it, vanishing in a puff of smoke, walking off the
edge of the screen and coming out somewhere else, ducking below the bottom bar
and climbing down from the top and vice versa ... the companion needs to be a
companion, not something that distracts the user from their work."
The duck was withdrawn on INBOX 1463 (it went through the status bar, was cut
by its clip-path on the way and came down from the top bar): see
`tests/test_companion_never_clipped_1463.py`.

`companionTravelChoose` (frontend/js/companion-travel.js, lazy) is pure: the
last move, where it goes and the window in; one of the calm moves out. These
run it in node as written. The source checks pin the other half of the
request: nothing in a per-frame path reads layout (the lag log's L4).
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
TRAVEL = (JS / "companion-travel.js").read_text(encoding="utf-8")
AV = (JS / "avatars.js").read_text(encoding="utf-8")
APP = (JS / "app.js").read_text(encoding="utf-8")
#: The chooser is the top of the file and touches no DOM, so node runs it alone.
PURE = TRAVEL[: TRAVEL.index("//: ---- Playing a move")]

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

WIN = [1440, 900]
BARS = [48, 852]  # the top bar's lower edge, the bottom bar's upper edge (a stale argument the chooser ignores)


def _run(cases: list[dict]) -> list:
    script = PURE + f"\nconsole.log(JSON.stringify({json.dumps(cases)}.map((c) => companionTravelChoose(c.o, c.roll))));"
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def _o(**kw) -> dict:
    base = {"last": "", "dx": 600, "dy": 0, "size": 64, "flies": False, "reduced": False, "win": WIN, "x0": 700, "x1": 100, "y0": 400, "lines": BARS}
    base.update(kw)
    return base


def _all_moves(o: dict) -> set[str]:
    return set(_run([{"o": o, "roll": i / 200} for i in range(200)]))


@needs_node
def test_never_the_same_move_twice_in_a_row() -> None:
    for last in ("walk", "portal", "smoke", "edge"):
        for dx in (-1200, -500, 300, 900):
            for y0 in (60, 400, 800):
                moves = _run([{"o": _o(last=last, dx=dx, y0=y0, x0=700, x1=700 + dx), "roll": i / 100} for i in range(100)])
                assert last not in moves, (last, dx, y0)


@needs_node
def test_a_far_move_is_one_of_the_calm_ones_and_all_of_them_turn_up() -> None:
    seen = _all_moves(_o(y0=800, x0=900, x1=100, dx=800, dy=-300))
    assert {"portal", "smoke", "edge"} <= seen
    assert "leap" not in seen and "arc" not in seen


@needs_node
def test_a_short_move_only_walks() -> None:
    assert _all_moves(_o(dx=90, dy=0, x0=400, x1=310)) == {"walk"}


@needs_node
def test_reduced_motion_is_a_fade_and_nothing_else() -> None:
    for last in ("", "walk", "portal"):
        assert _all_moves(_o(reduced=True, last=last)) == {"fade"}


@needs_node
def test_walking_off_an_edge_needs_a_short_enough_way_to_the_edges() -> None:
    # Both ends mid-window on a wide window: past the walking budget.
    assert "edge" not in _all_moves(_o(win=[2400, 900], x0=1200, x1=300, dx=900))
    assert "edge" in _all_moves(_o(x0=300, x1=1200, dx=-900))


@needs_node
def test_weights_favour_the_quieter_moves_and_walking_is_kept_for_near() -> None:
    script = PURE + "\nconsole.log(JSON.stringify(companionTravelWeights(" + json.dumps(_o(y0=800, x0=900, x1=100, dx=800)) + ")));"
    w = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    # INBOX 1683 u: the puff (smoke) is the rare one now, the owner saw only puffs; it was walk < smoke.
    assert w["smoke"] < w["walk"] < w["portal"]
    assert all(v >= 0 for v in w.values())


@needs_node
def test_every_roll_gives_a_move() -> None:
    for roll in (0, 0.0001, 0.5, 0.9999):
        for last in ("", "walk", "smoke"):
            assert _run([{"o": _o(last=last), "roll": roll}])[0]


def _body(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


LAYOUT_READS = re.compile(r"getBoundingClientRect|offsetWidth|offsetHeight|offsetLeft|offsetTop|clientWidth|clientHeight|getComputedStyle|scrollTop|checkVisibility|getClientRects")


def test_the_per_frame_paths_read_no_layout_directly() -> None:
    # The drag's frame, the follow loop's frame and the pacer's beat (the lag log's L4).
    drag_follow = AV[AV.index("const follow = () => {") : AV.index('face.addEventListener("pointerdown"')]
    assert not LAYOUT_READS.search(drag_follow)
    assert not LAYOUT_READS.search(_body(AV, "nameMarkBuddyFollowFrame"))
    flight = (JS / "companion-throw.js").read_text(encoding="utf-8")
    frame = flight[flight.index("const frame = (now) => {") : flight.index("const next = () => {")]
    assert not LAYOUT_READS.search(frame)


def test_the_release_uses_the_box_it_already_has() -> None:
    release = AV[AV.index("const release = (event) => {") : AV.index('face.addEventListener("pointerup", release)')]
    assert "getBoundingClientRect" not in release
    assert "drag.dx" in release


def test_the_costly_style_reads_of_the_follow_loop_are_throttled() -> None:
    follow = _body(AV, "nameMarkBuddyFollow")
    assert "g.visAt" in follow and "nmb.flight" in follow
    frame = _body(AV, "nameMarkBuddyFollowFrame")
    assert "nmbFollow.movingAt" in frame
    assert "nameMarkBuddyPanelMoving(" in frame and frame.index("movingAt") < frame.index("nameMarkBuddyPanelMoving(")


def test_the_pacer_reads_nothing_while_busy_and_nothing_is_held() -> None:
    tempo = _body(AV, "nameMarkBuddyTempo")
    assert tempo.index("busy && !nmbTempo.held") < tempo.index("anim.playState)")


def test_the_drag_moves_it_by_translate_only() -> None:
    drag_follow = AV[AV.index("const follow = () => {") : AV.index('face.addEventListener("pointerdown"')]
    assert "style.translate" in drag_follow
    assert not re.search(r"style\.(top|left)\b", drag_follow)
    assert "will-change: translate" in (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")


def test_travel_is_a_lazy_module_with_its_own_sheet() -> None:
    menu = (JS / "companion-menu.js").read_text(encoding="utf-8")
    assert 'lazyScript("/css/companion-travel-lazy.css")' in menu and 'lazyScript("/js/companion-travel.js")' in menu
    assert (ROOT / "frontend" / "css" / "companion-travel-lazy.css").is_file()
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "companion-travel" not in index


def test_a_far_move_goes_through_the_chooser_and_a_test_can_force_a_move() -> None:
    go = _body(AV, "nameMarkBuddyGo")
    assert "nmb.travelPlay" in go
    assert "nmb.travelForce" in TRAVEL
    # Never the old always-leap: a far way on foot climbs instead of arcing.
    assert 'route = "climb"' in go


def test_the_idle_acts_are_quiet_and_wait_for_their_sheet() -> None:
    for act in ("shake", "groom", "sniff", "sigh"):
        assert re.search(rf"\b{act}: \{{[^}}]*lazy: true", AV), act
        assert f".nmb-act-{act}" in (ROOT / "frontend" / "css" / "companion-travel-lazy.css").read_text(encoding="utf-8")
        assert f'"{act}"' not in AV[AV.index("const NMB_LOUD_ACTS") : AV.index("const NMB_LOUD_GAP_MS")]


def test_it_wanders_off_less_often() -> None:
    wander = _body(AV, "nameMarkBuddyWander")
    assert "0.35" not in wander


# --- INBOX 1692 (the owner: "transformed sideways off the screen at the top and on the screen at the bottom, there was no
# real animation or life to it at all"; "a portal or like magic ... float on a cloud"). ---------------------------------

NEW_MOVES = {"blink", "cloud", "bubble"}


@needs_node
def test_the_new_ways_turn_up_for_a_far_move_and_never_for_a_near_one() -> None:
    assert NEW_MOVES <= _all_moves(_o(y0=800, x0=900, x1=100, dx=800, dy=-300))
    assert not NEW_MOVES & _all_moves(_o(dx=90, dy=0, x0=400, x1=310))
    assert not NEW_MOVES & _all_moves(_o(reduced=True))


def _play(move: str, was_pose: str, now_pose: str = "stand") -> dict:
    """Run one player in node against stubs; the timers are captured and fired in order, so what a move sets over time is seen."""
    stub = """
const NMB_W = 64, NMB_H = 92, NMB_BLEND_IN_MS = 120;
var innerWidth = 1440, innerHeight = 900;
const timers = [];
const setTimeout = (fn, ms) => { timers.push([ms, fn]); return timers.length; };
const clearTimeout = () => {};
const nmbTempo = { seen: 0, timer: 0 };
function nameMarkBuddyTempo() {}
function nameMarkBuddyBlend(b, fn) { fn(); }
const made = [];
const document = { createElement: () => ({ style: { setProperty() {} }, setAttribute() {}, appendChild() {}, animate() {}, remove() {}, className: "" }) };
const nmb = { x: 100, y: 700, lx: 0, ly: 0, pose: %s, travelFx: [], travelTimers: [], afterClean: (fn) => fn(), anim: null };
const buddy = { dataset: { pose: %s }, classList: { add() {}, remove() {}, contains: () => false }, parentElement: null };
""" % (json.dumps(now_pose), json.dumps(was_pose))
    run = f"""
const ctx = {{ was: {{ x: 1200, y: 100, pose: {json.dumps(was_pose)} }}, frames: [], body: null, ms: 0, turn: "" }};
COMPANION_TRAVEL_PLAYERS[{json.dumps(move)}](buddy, 1100, -600, ctx);
const poseAtStart = buddy.dataset.pose;
const log = [poseAtStart];
for (const [ms, fn] of timers.sort((a, b) => a[0] - b[0])) {{ fn(); log.push(buddy.dataset.pose); }}
console.log(JSON.stringify({{ ctx, poseAtStart, log }}));
"""
    done = subprocess.run(["node", "-e", stub + TRAVEL.replace("nmb.travelPlay = companionTravelPlay;", "") + run], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


@needs_node
def test_an_edge_move_from_a_hang_keeps_the_hang_until_it_is_out_of_sight() -> None:
    r = _play("edge", "hang")
    assert r["poseAtStart"] == "hang"  # it did not stand up on the spot
    assert r["log"][-1] == "stand"  # and has the new pose once it is gone
    assert any(f["opacity"] == 0 for f in r["ctx"]["frames"]) and any(f["opacity"] == 1 for f in r["ctx"]["frames"])


@needs_node
def test_the_edge_move_has_a_body_that_thins_through_the_edge_and_eased_runs() -> None:
    r = _play("edge", "stand")
    body, frames = r["ctx"]["body"], r["ctx"]["frames"]
    assert body and any(b["scale"].startswith("0.2 ") for b in body)  # squeezed thin through the edge, both ways
    assert sum(b["scale"].startswith("0.2 ") for b in body) >= 3
    assert any(f.get("easing") in ("ease-in", "ease-out") for f in frames)  # not one linear slide
    assert r["ctx"]["ms"] >= 1600


@needs_node
@pytest.mark.parametrize("move", sorted(NEW_MOVES))
def test_the_new_moves_play_with_a_body_and_end_in_place(move: str) -> None:
    r = _play(move, "stand")
    ctx = r["ctx"]
    assert ctx["body"] and ctx["frames"] and ctx["ms"] >= 1500
    last = ctx["frames"][-1]
    assert last["translate"] == "0px 0px" and last["opacity"] == 1
    assert ctx["frames"][0]["translate"] == "1100px -600px"


def test_the_wisp_the_spark_the_cloud_and_the_bubble_have_their_styles() -> None:
    css = (ROOT / "frontend" / "css" / "companion-travel-lazy.css").read_text(encoding="utf-8")
    for cls in ("nmb-wisp", "nmb-spark", "nmb-cloud", "nmb-bubble"):
        assert f".{cls}" in css, cls
    assert "nmb-wisp" in TRAVEL and "nmb-spark" in TRAVEL


def test_a_new_views_far_move_blinks_instead_of_crossfading_when_the_file_is_here() -> None:
    go = _body(AV, "nameMarkBuddyGo")
    assert '"blink")) return;' in go and go.index('"blink")') < go.index("nameMarkBuddyCrossfade(buddy, dx, dy, 420)")


def test_the_travel_file_stays_small() -> None:
    import gzip

    assert len(gzip.compress((JS / "companion-travel.js").read_bytes())) <= 6000
