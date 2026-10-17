"""A thrown companion flies and lands where it is thrown.

INBOX 882, the owner: "I keep having the issue where I try throwing the
companion across the screen and it just goes back to the same side, the
companion physics just isnt there and needs to be upgraded and fixed."

The flight's two pure pieces, `nameMarkBuddyReleaseVelocity` (the speed it
is let go at) and `nameMarkBuddyFlightStep` (one step of the flight), run
here in node as they are written. The flight in a browser, both ways, on
the desktop and the phone, is `scratchpad/ui-sweeps/throw.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
HELP = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def _run(body: str):
    consts = re.search(r"^const NMB_THROW = .*;$", AV, re.M).group(0)
    src = "\n".join(_fn(n) for n in ("nameMarkBuddyReleaseVelocity", "nameMarkBuddyFlightStep", "nameMarkBuddyThrowFeel"))
    world = "const W = { left: 0, right: 1376, top: 48, floor: 780, ledges: [] };"
    fly = (
        "function fly(vx, vy, x = 200, y = 400, world = W, k = NMB_THROW) {"
        " let s = { x, y, vx, vy, rot: 0, t: 0, on: null, rest: false }; let steps = 0; let peak = 0; let bounces = 0; let walls = 0;"
        " while (!s.rest && steps < 500) { const was = s.vx; s = nameMarkBuddyFlightStep(s, 16, world, k); steps += 1;"
        " peak = Math.max(peak, Math.abs(s.rot)); if (s.hit > 0.35) bounces += 1; if (Math.sign(was) !== Math.sign(s.vx) && was) walls += 1; }"
        " return { x: Math.round(s.x), y: Math.round(s.y), t: s.t, on: s.on === 'floor' ? 'floor' : s.on ? 'ledge' : null, rot: Math.round(s.rot), peak: Math.round(peak), bounces, walls }; }"
    )
    script = "\n".join([consts, src, world, fly, f"console.log(JSON.stringify({body}));"])
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


@needs_node
def test_the_release_speed_is_the_last_80ms_of_the_pull_clamped() -> None:
    got = _run(
        "["
        # A slow start then a quick flick: the flick, not the mean (2 px/ms).
        "nameMarkBuddyReleaseVelocity([[0,0,0],[10,0,100],[20,0,200],[60,0,220],[100,0,240],[140,0,260]], 270),"
        # Let go after the pointer had stopped: no throw.
        "nameMarkBuddyReleaseVelocity([[0,0,0],[100,0,40]], 200),"
        # Faster than the cap: clamped to 4.5 px/ms, in the same direction.
        "nameMarkBuddyReleaseVelocity([[0,0,0],[-500,0,50]], 60),"
        # A slow machine's input, one move inside the window: the one before it too.
        "nameMarkBuddyReleaseVelocity([[0,0,0],[150,-30,100]], 110),"
        # Nothing to measure.
        "nameMarkBuddyReleaseVelocity([], 10), nameMarkBuddyReleaseVelocity([[5,5,10]], 12)"
        "]"
    )
    assert [round(v, 2) for v in got[0]] == [2.0, 0.0]
    assert got[1] is None
    assert [round(v, 2) for v in got[2]] == [-4.5, 0.0]
    assert [round(v, 2) for v in got[3]] == [1.5, -0.3]
    assert got[4] is None and got[5] is None


@needs_node
def test_a_throw_lands_on_the_side_it_was_thrown_to_and_further_the_harder() -> None:
    got = _run("[fly(1, -0.2), fly(2.5, -0.2), fly(-1, -0.2, 1176), fly(-2.5, -0.2, 1176), fly(0.7, 0)]")
    soft_r, hard_r, soft_l, hard_l, gentle = got
    # Thrown right from 200: well to the right, a harder throw further.
    assert soft_r["x"] > 200 + 300 and hard_r["x"] > soft_r["x"] + 300
    # And left from 1176, the same the other way (the owner's "goes back").
    assert soft_l["x"] < 1176 - 300 and hard_l["x"] < soft_l["x"] - 300
    # A gentle one still goes some way, and they all come down on the floor.
    assert gentle["x"] > 200 + 150
    assert all(g["on"] == "floor" and g["y"] == 780 for g in got)
    # Inside the 1.2 s cap, and upright again once it has slid to a stop.
    assert all(g["t"] <= 1200 for g in got)
    assert all(abs(g["rot"]) <= 3 for g in got if g["t"] < 1200)


@needs_node
def test_it_bounces_off_the_walls_and_the_floor_and_leans_into_the_throw() -> None:
    got = _run("[fly(4.5, -0.5, 1000), fly(-4.5, -0.5, 300), fly(1.5, 0.2, 200, 100)]")
    right_wall, left_wall, dropped = got
    # Thrown hard at a wall: it bounces off it, but only a little way back
    # (restitution 0.4, the rebound capped at 0.12 px/ms): it rests within
    # 200px of the wall it was thrown at, never back where it started.
    assert right_wall["walls"] >= 1 and 1376 - 200 <= right_wall["x"] < 1376
    assert left_wall["walls"] >= 1 and 0 < left_wall["x"] <= 200
    # Falling from high up it bounces on the floor before it settles.
    assert dropped["bounces"] >= 1
    # It leans the way it flies, by its speed, never past 40 degrees.
    assert all(10 <= g["peak"] <= 40 for g in got)


@needs_node
def test_it_comes_down_on_a_ledge_under_its_path_and_never_through_one() -> None:
    got = _run(
        "[fly(1.5, -0.3, 200, 300, { ...W, ledges: [{ left: 300, right: 1300, y: 500 }] }),"
        # Starting on a ledge and thrown along it, it does not catch on its own.
        " fly(1.5, 0, 200, 500, { ...W, ledges: [{ left: 100, right: 400, y: 500 }] }),"
        # A ledge it flies over (out of its x range) is not landed on.
        " fly(1.5, -0.3, 200, 300, { ...W, ledges: [{ left: 1300, right: 1376, y: 500 }] })]"
    )
    assert got[0]["on"] == "ledge" and got[0]["y"] == 500
    assert got[1]["on"] == "floor"
    assert got[2]["on"] == "floor"


def test_the_flight_is_one_frame_loop_on_transforms_and_lands_as_a_drop() -> None:
    build = AV[AV.index("function nameMarkBuddyBuild(") :]
    assert "nameMarkBuddyReleaseVelocity(drag.samples || [], event?.timeStamp ?? performance.now())" in build
    assert "nameMarkBuddyThrow(buddy, v[0], v[1]);" in build
    throw = _fn("nameMarkBuddyThrow")
    # One requestAnimationFrame, its step capped so a hidden tab resumes in
    # place, drawn by `nameMarkBuddyPut` (a transform) and a rotate.
    assert throw.count("requestAnimationFrame(") == 1
    assert "Math.min(32, Math.max(0, now - then))" in throw
    assert "nameMarkBuddyPut(buddy, Math.round(s.x), Math.round(s.y));" in throw
    assert ".style.left" not in throw and ".style.top" not in throw
    # Reduce motion: the same flight worked out at once, then a crossfade.
    assert "if (nameMarkBuddyNoTravel()) {" in throw
    # A grab or any other move ends the flight where it is.
    assert "nmb.flight?.stop();" in _fn("nameMarkBuddyMoveTo")
    land = _fn("nameMarkBuddyThrowLand")
    # The nearest place to where it stopped, searched round that point, not
    # round the old spot, and kept as the tab's spot.
    assert "nameMarkBuddyDrop(s.x, s.y)" in land and "nameMarkBuddyChoose" not in land
    assert "spots[tab] = nameMarkBuddySpotFor(spot);" in land
    assert "nameMarkBuddyToss" not in AV


def test_the_guide_says_it_can_be_thrown() -> None:
    assert "throw it" in HELP.lower()


@needs_node
def test_every_throw_feels_a_little_different_and_a_hard_one_tumbles() -> None:
    # Brief 88 (b): the owner wants the bounce "but vary how much it does
    # that". Same fling, two draws: two landings; a hard fling tumbles and
    # comes down upright.
    got = _run(
        "[nameMarkBuddyThrowFeel([0, 0, 0], 1), nameMarkBuddyThrowFeel([1, 1, 1], 3),"
        " fly(1.5, 0.3, 200, 100, W, nameMarkBuddyThrowFeel([0, 0, 0], 1.5)),"
        " fly(1.5, 0.3, 200, 100, W, nameMarkBuddyThrowFeel([1, 1, 1], 1.5)),"
        " fly(3.2, -0.5, 200, 400, W, nameMarkBuddyThrowFeel([0.5, 0.5, 0.5], 3.2))]"
    )
    soft, hard, a, b, tumble = got
    assert 0.27 < soft["bounce"] < 0.53 and 0.27 < hard["bounce"] < 0.53 and soft["bounce"] != hard["bounce"]
    assert soft["spin"] == 0 and hard["spin"] > 0
    assert abs(a["x"] - b["x"]) > 20
    # A tumble turns past a full turn in the air and lands within 3 degrees of upright.
    assert tumble["peak"] > 180
    # Upright at rest, or at the 1.2 s cap eased upright by the stop.
    assert abs(tumble["rot"]) <= 1 or (tumble["t"] >= 1200 and "char.animate([{ rotate: `${r}deg` }, { rotate: \"0deg\" }]" in _fn("nameMarkBuddyThrow"))


def _drop(obstacles: str):
    # `nameMarkBuddyDrop` as written, against a page with no panels (no edges)
    # and the given controls; `nameMarkBuddyChoose` stands in as the tab's nearest
    # good perch, a dock.
    script = "\n".join(
        [
            "const NMB_W = 64, NMB_H = 130, NMB_SEAT = 60, NMB_FEET = 90, NMB_GRIP = 8;",
            "const innerWidth = 1440, innerHeight = 900; const nmb = {};",
            f"const OBS = {obstacles};",
            'function nameMarkBuddyTab() { return "chat"; }',
            "function nameMarkBuddyObstacles() { return OBS; }",
            "function nameMarkBuddyEdges() { return []; }",
            "function nameMarkBuddyYoursObstacles(o) { return o; }",
            "function nameMarkBuddyStepAside(spot) { return spot; }",
            "function nameMarkBuddyHits(x, y, pose, obs) { return obs.some((b) => x < b.right && x + NMB_W > b.left && y < b.bottom && y + NMB_H > b.top); }",
            'function nameMarkBuddyChoose() { return { kind: "dock", pose: "stand", legs: "", x: 40, y: 600, edge: {} }; }',
            _fn("nameMarkBuddyDrop"),
            "console.log(JSON.stringify([nameMarkBuddyDrop(1350, 774), nameMarkBuddyDrop(300, 300)]));",
        ]
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_throw_that_comes_down_over_controls_is_never_left_floating_over_them() -> None:
    # The owner, 2026-10-17: the companion "sometimes loses its perch and is
    # left stuck floating and not anchored to something". Measured (chat,
    # 1440x900): a throw that came down on the window's foot at the right had
    # the composer's controls in the way of every stance within 48px, so it
    # floated over the mode switch at (1350, 774) and stayed. Open air with
    # nothing under it is still a place of your own; open air over a control
    # is not, and the nearest good perch is where it comes down.
    over, clear = _drop("[{ left: 1300, top: 789, right: 1400, bottom: 821 }]")
    assert over["pose"] == "stand" and over["kind"] == "dock", over
    assert clear["pose"] == "float" and clear["kind"] == "yours", clear
    free, _ = _drop("[]")
    assert free["pose"] == "float", "open air with no control under it still floats where it was let go"
