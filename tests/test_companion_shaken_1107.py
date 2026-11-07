"""INBOX 1683 x and k, ledger N9: the in-app companion's share of the desk fling. A panel it stands on (or a container
scrolled under it) carried fast throws it off with a flail and a worried or miffed face for two to four seconds; it
scrabbles at a wall while it slides and while its hands slip on a panel's edge before the pull-up; it peeks out from
behind a panel's top edge, the phone dock and the bars (already built, pinned here so it is not lost). Node runs the
pure parts on a fixed clock; the real page was not driven here."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests.test_companion_throw_fates import AV, CSS, THROW, _fn

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
SHAKE = re.search(r"^const COMPANION_SHAKE = .*;$", THROW, re.M).group(0)


def shaken(body: str):
    """`nameMarkBuddyShaken` with the page stubbed out; `body` is an expression using `shake(...)` and `calls`."""
    script = f"""
let t = 0;
const performance = {{ now: () => t }};
const calls = [];
const nmb = {{ x: 100, y: 200, pinned: false, visit: null, flight: null, ride: null, shakenAt: 0 }};
const nmbFollow = {{ moving: false }};
let reduced = false, menu = false;
const NMB_THROW = {{ max: 2.3 }};
const nameMarkBuddyNoTravel = () => reduced;
const nameMarkBuddyMenuOpen = () => menu;
const nameMarkBuddyRide = (x) => calls.push(["ride", x]);
const nameMarkBuddyIndexReset = () => calls.push(["reset"]);
const nameMarkBuddyTab = () => "notes";
const nameMarkBuddyWorld = () => ({{ w: 1 }});
const companionThrowPlan = (...a) => (calls.push(["plan", a.slice(0, 4), a[5]]), {{ shaken: a[5] }});
const nameMarkBuddyThrow = (...a) => calls.push(["throw", a[1], a[2], a[4].shaken]);
{SHAKE}
{_fn(THROW, "nameMarkBuddyShaken")}
const g = {{}};
const shake = (sx, sy, at) => {{ t = at; return nameMarkBuddyShaken({{}}, g, sx, sy); }};
console.log(JSON.stringify({body}));
"""
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_two_fast_looks_running_throw_it_the_way_the_panel_went_and_a_little_up() -> None:
    out = shaken("(() => { const a = shake(2, 0, 1000); const b = shake(2, 0, 1016); return [a, b, calls]; })()")
    assert out[0] is False and out[1] is True  # the first fast look only arms it: a one-frame jump is not a shake
    throw = [c for c in out[2] if c[0] == "throw"][0]
    assert throw[1] == pytest.approx(2 * 0.6) and throw[2] == pytest.approx(-0.35) and throw[3] is True


@needs_node
def test_a_throw_is_never_faster_than_the_flight_cap() -> None:
    out = shaken("(() => { shake(40, 30, 1000); shake(40, 30, 1016); return calls.find((c) => c[0] === 'throw'); })()")
    assert (out[1] ** 2 + (out[2] + 0.35) ** 2) ** 0.5 == pytest.approx(2.3 * 0.6)


@needs_node
def test_a_jump_is_not_a_shake_and_neither_is_a_panel_that_animates() -> None:
    assert shaken("(() => { shake(2, 0, 1000); return shake(2, 0, 1300); })()") is False  # looks 300 ms apart
    assert shaken("(() => { nmbFollow.moving = true; shake(2, 0, 1000); return shake(2, 0, 1016); })()") is False


@needs_node
@pytest.mark.parametrize("setup", ["reduced = true", "nmb.pinned = true", "nmb.visit = {}", "nmb.flight = {}", "menu = true"])
def test_reduced_motion_a_pinned_or_visiting_companion_a_flight_or_an_open_menu_never_shake(setup: str) -> None:
    assert shaken(f"(() => {{ {setup}; shake(2, 0, 1000); return shake(2, 0, 1016); }})()") is False


@needs_node
def test_once_in_eight_seconds() -> None:
    out = shaken("(() => { shake(2, 0, 1000); const a = shake(2, 0, 1016); shake(2, 0, 1100); const b = shake(2, 0, 1116); shake(2, 0, 9100); const c = shake(2, 0, 9116); return [a, b, c]; })()")
    assert out == [True, False, True]


@needs_node
def test_a_scrolled_container_lets_go_of_the_ride_first() -> None:
    out = shaken("(() => { nmb.ride = {}; shake(2, 0, 1000); shake(2, 0, 1016); return calls.map((c) => c[0]); })()")
    assert out[:2] == ["ride", "reset"] and "throw" in out


def flail_of(shaken_throw: bool) -> float:
    consts = re.search(r"^const NMB_THROW = .*;$", AV, re.M).group(0)
    base = "\n".join(_fn(AV, n) for n in ("nameMarkBuddyFlightStep", "nameMarkBuddyThrowFeel"))
    pure = THROW[: THROW.index("//: The throw itself (moved here")]
    body = f"""
const W = {{ left: 0, right: 1376, top: 48, floor: 780, ledges: [], w: 64, hang: 43, climb: 84 }};
const k = nameMarkBuddyThrowFeel([0.5, 0.5, 0.5], 1.0); k.ms = 2000; k.shaken = {str(shaken_throw).lower()};
let s = {{ x: 600, y: 300, vx: 0.4, vy: -0.5, rot: 0, t: 0, on: null, rest: false, tried: {{}} }};
let first = 0;
for (let i = 0; i < 30; i += 1) {{ s = nameMarkBuddyFlightStep(s, 16, W, k); first = Math.max(first, Math.abs(s.flail || 0)); }}
console.log(first);
"""
    return float(subprocess.run(["node", "-e", "\n".join([consts, base, pure, body])], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_shaken_throw_flails_from_the_first_half_second_a_plain_one_does_not() -> None:
    assert flail_of(False) == 0.0  # 480 ms of rise and the start of the fall: the plain flail waits 450 ms of falling
    assert flail_of(True) > 5.0


def test_the_face_after_is_worried_or_miffed_for_two_to_four_seconds_and_both_faces_exist() -> None:
    faces = re.search(r'faces: \[("[a-z]+"(?:, "[a-z]+")*)\], face: \[(\d+), (\d+)\]', SHAKE)
    names = re.findall(r'"([a-z]+)"', faces.group(1))
    assert names == ["nervous", "angry"] and (int(faces.group(2)), int(faces.group(3))) == (2000, 4000)
    for name in names:
        assert re.search(rf"^  {name}: \{{", AV, re.M), name
    assert re.search(r"angry: \"unimpressed\"", AV)  # angry comes down through the miffed look
    assert "if (nmb.thrown.shaken) companionThrowMiffed();" in THROW


def test_the_follow_loop_asks_for_a_shake_at_twice_the_toss_speed_and_loads_the_module_to_answer() -> None:
    avatars = AV
    follow = avatars[avatars.index("function nameMarkBuddyFollow(") :][:4000]
    assert "Math.hypot(sx, sy) > NMB_TOSS_SPEED * 2" in follow
    assert 'ensureModule("companionThrow")' in follow and "self.nameMarkBuddyShaken?.(buddy, g, sx, sy)" in follow
    assert follow.index("nameMarkBuddyShaken") < follow.index("g.dx = g.fx")  # before the panel's box places it again
    assert "nameMarkBuddyShaken" in avatars and "NMB_TOSS_SPEED = 0.6" in avatars


def test_it_scrabbles_at_a_wall_while_it_slides_and_while_its_hands_slip_before_the_pull_up() -> None:
    assert re.search(r"\.nmb-splat \.nm-buddy-char \{[^}]*animation: nmb-scrabble", CSS)
    def keyframes(name: str) -> str:
        return CSS[CSS.index(f"@keyframes {name}") :].split("\n}\n", 1)[0]

    for name in ("nmb-climb-pull", "nmb-slip-pull"):
        # more than the anticipation's dip: several alternating sideways jolts before the pull
        jolts = re.findall(r"translate: (-?\d+)(?:px)? -?\d+px", keyframes(name))
        assert sum(1 for a, b in zip(jolts, jolts[1:]) if (int(a) < 0) != (int(b) < 0)) >= 3, name


def test_the_hide_behind_is_already_built_for_a_panel_the_dock_and_the_bars() -> None:
    avatars = AV
    assert 'peek: { ms: 14000' in avatars and 'edge: "top"' in avatars  # peek from behind a panel's top edge
    assert 'getElementById("phone-tab-dock")' in avatars and 'legs: "peek"' in avatars  # and the dock and status bar
