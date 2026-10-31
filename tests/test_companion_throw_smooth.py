"""A throw is planned when it is let go, and its frames only draw.

The owner, 2026-10-27: "throwing the companion is now framey, not clean or
smooth and glitchy"; their lag log had "avatars.js FrameRequestCallback 11ms;
avatars.js nameMarkBuddyDodge 7ms". Measured (throw5.js in the agent's scratch
dir, Atlas on Notes, 1440x900): the landing's obstacle search ran in the
flight's last frame, 11 to 40ms at 1x CPU and 217ms (122 of it forced layout)
at 4x; the popup check (`nameMarkBuddyDodge`), armed by the release's own
click, ran twice mid-flight (9 to 56ms); and one landing measured the
obstacles two to four times. Now the path and the landing are worked out at
the release on one measure, the frames read nothing, and the popup check
waits until it is down.
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
THROW = (ROOT / "frontend" / "js" / "companion-throw.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def _plan(body: str):
    consts = re.search(r"^const NMB_THROW = .*;$", AV, re.M).group(0)
    base = "\n".join(_fn(AV, n) for n in ("nameMarkBuddyFlightStep", "nameMarkBuddyThrowFeel", "nameMarkBuddyMeasureOnce"))
    pure = THROW[: THROW.index("//: The throw itself (moved here")]
    harness = "\n".join(
        [
            "const NMB_W = 64, NMB_GRIP = 8, NMB_FEET = 90; const nmb = {}; let still = false, spots = 0;",
            "function nameMarkBuddyNoTravel() { return still; }",
            "function nameMarkBuddyThrowSpot(s) { spots += 1; return { kind: 'yours', pose: 'stand', x: Math.round(s.x), y: Math.round(s.y) }; }",
            "const W = { left: 0, right: 1376, top: 48, floor: 780, ledges: [{ left: 300, right: 700, y: 420 }] };",
            # Drawn the way the frame draws it: a capped clock, a frame `ms` long (hitches every `hitch`th).
            "function draw(plan, ms, hitch = 0) { const end = plan.path[plan.path.length - 1]; let flown = 0, i = 0, last = null, worst = 0, wraps = 0;"
            + " while (flown < end.t && i < 5000) { i += 1; flown = Math.min(end.t, flown + Math.min(32, hitch && i % hitch === 0 ? 120 : ms));"
            + "  const s = flown >= end.t ? end : companionThrowAtTime(plan.path, flown);"
            + "  if (last) { const d = Math.hypot(s.x - last.x, s.y - last.y); if (d > 300) wraps += 1; else worst = Math.max(worst, d); } last = s; }"
            + " return { worst: +worst.toFixed(1), wraps, x: last.x, y: last.y, endX: end.x, endY: end.y, rest: end.rest }; }",
        ]
    )
    script = "\n".join([consts, base, pure, harness, f"console.log(JSON.stringify({body}));"])
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_the_release_plans_the_path_only_and_the_landing_is_asked_for_later_at_the_paths_end() -> None:
    got = _plan(
        "[[1.6, -0.4], [-1.4, -0.3], [0.1, -2.0], [1.2, -1.2], [0.2, 1.4]].map(([vx, vy], n) => {"
        " companionThrowSeed.seed = n + 3; spots = 0; const p = companionThrowPlan(600, 400, vx, vy, W);"
        " const end = p.path[p.path.length - 1]; const atRelease = spots; p.land(); p.land();"
        " return { atRelease, spots, rest: end.rest, steps: p.path.length, fixed: p.path.every((s, i) => i === 0 || Math.abs(s.t - p.path[i - 1].t - 16) < 1e-9 || s.rest),"
        " landAt: [p.land().x, p.land().y], endAt: [Math.round(end.x), Math.round(end.y)] }; })"
    )
    for r in got:
        # The release measures nothing (the landing is asked for later, once per ask).
        assert r["atRelease"] == 0 and r["spots"] == 2, r
        assert r["rest"] and 2 <= r["steps"] < 400, r
        assert r["fixed"], r
        assert r["landAt"] == r["endAt"], r


@needs_node
def test_the_drawn_flight_moves_under_40px_a_frame_at_any_rate_and_ends_where_the_plan_does() -> None:
    got = _plan(
        "[[1.6, -0.4], [-1.4, -0.3], [0.1, -2.0], [1.2, -1.2], [0.2, 1.4], [2.3, -0.2]].map(([vx, vy], n) => {"
        " companionThrowSeed.seed = n + 11; const p = companionThrowPlan(600, 400, vx, vy, W);"
        " return [draw(p, 1000 / 60), draw(p, 1000 / 144), draw(p, 1000 / 60, 9)]; })"
    )
    for rates in got:
        sixty, fast, hitchy = rates
        # 2.3 px/ms is the fastest it is drawn: 38px in a 60 Hz frame.
        assert sixty["worst"] < 40 and fast["worst"] < 20, rates
        # A hitch is capped at 32ms of flight, never a long step (74px at most).
        assert hitchy["worst"] < 75, rates
        for r in rates:
            assert (r["x"], r["y"]) == (r["endX"], r["endY"]) and r["rest"], r


@needs_node
def test_reduce_motion_plans_the_plain_flight() -> None:
    got = _plan("(() => { still = true; const p = companionThrowPlan(600, 400, 1.6, -0.4, W); return { still: p.still, fates: p.path.some((s) => s.fate && s.fate.kind !== 'floor' && s.fate.kind !== 'ledge') }; })()")
    assert got["still"] is True and got["fates"] is False


def test_the_release_plans_before_it_writes_and_the_frame_reads_nothing() -> None:
    build = AV[AV.index("function nameMarkBuddyBuild(") :]
    release = build[build.index("const release = (event) =>") : build.index('face.addEventListener("pointerup", release)')]
    first_write = release.index('buddy.style.translate = ""')
    assert release.index("nameMarkBuddyWorld(") < release.index("companionThrowPlan(") < first_write
    throw = _fn(THROW, "nameMarkBuddyThrow")
    frame = throw[throw.index("const frame = (now) =>") : throw.index("const next = () =>")]
    for read in ("ThrowSpot", "Drop(", "Obstacles", "LandNear", "World(", "Ledges", "Edges", "getBoundingClientRect", "getComputedStyle", "companionThrowStep"):
        assert read not in frame, read
    # The first frame is one 16ms step: the release's own long task is not flight time.
    assert "let then = 0;" in throw and "(then ? Math.min(32, Math.max(0, now - then)) : 16)" in frame
    # The surfaces the release indexed for the flight's world are the landing's too.
    assert "nameMarkBuddyIndexReset" not in _fn(AV, "nameMarkBuddyThrowSpot")


@needs_node
def test_one_landing_measures_the_obstacles_once() -> None:
    # `nameMarkBuddyObstacles` as written, against a page with nothing on it:
    # the number of measures is the number of popup sweeps it starts.
    script = "\n".join(
        [
            "const nmb = {}; let reads = 0; let nameMarkBuddyTextCache = null; const NAME_MARK_BUDDY_NEVER_COVER = 'button';",
            "const document = { getElementById: () => null, querySelector: () => null, querySelectorAll: () => [] };",
            "function nameMarkBuddyPopups() { reads += 1; return [{ left: 1, right: 2, top: 1, bottom: 2 }]; }",
            "function nameMarkBuddyShown() { return null; }",
            # The tab's kept boxes and the floating roots (INBOX 1465): an empty page.
            "function nameMarkBuddyControlBoxes() { return []; }",
            "function nameMarkBuddyFloaters() { return []; }",
            "function nameMarkBuddyControlsIn() {}",
            _fn(AV, "nameMarkBuddyObstacles"),
            _fn(AV, "nameMarkBuddyMeasureOnce"),
            "const once = nameMarkBuddyMeasureOnce(() => { const a = nameMarkBuddyObstacles('notes'); a.push('x');"
            + " nameMarkBuddyMeasureOnce(() => nameMarkBuddyObstacles('notes')); return nameMarkBuddyObstacles('notes').length; });",
            "const inside = reads; nameMarkBuddyObstacles('notes'); nameMarkBuddyObstacles('notes');",
            "console.log(JSON.stringify({ inside, after: reads - inside, once, held: nmb.obstaclesHeld || null }));",
        ]
    )
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    # Once inside (a caller's push does not reach the next caller), every time outside.
    assert got == {"inside": 1, "after": 2, "once": 1, "held": None}
    assert "nameMarkBuddyMeasureOnce(() => nameMarkBuddyThrowSpot(" in _fn(THROW, "companionThrowPlan")
    assert "nameMarkBuddyMeasureOnce(() => nameMarkBuddyLandNear(box.left, box.top, nameMarkBuddyDrop(" in AV


def test_the_popup_check_waits_until_it_is_down() -> None:
    dodge = _fn(AV, "nameMarkBuddyDodge")
    wait = dodge.index('if (nmb.flight || buddy.classList.contains("nm-buddy-dragging")) {')
    assert wait < dodge.index("getBoundingClientRect") and "setTimeout(nameMarkBuddyDodge, 400)" in dodge[wait:]


def test_the_landing_is_worked_out_after_the_first_frame_or_before_it_when_the_flight_is_one_frame() -> None:
    # The owner, 2026-10-27: "when it calculates the landing, it pauses for a split sec then goes".
    throw = _fn(THROW, "nameMarkBuddyThrow")
    assert "let landing = null;" in throw and "const spotNow = () => (landing ||= plan.land());" in throw
    tail = throw[throw.index("nmb.flight = flight;") :]
    assert tail.index("if (end.t <= 200) spotNow();") < tail.index("next();") < tail.index("requestIdleCallback(spotNow")
    assert "ThrowSpot" not in _fn(THROW, "companionThrowPlan").split("land:")[0]


def test_the_landing_frame_splits_its_restyles_and_reads_no_layout() -> None:
    land = _fn(AV, "nameMarkBuddyThrowLand")
    # The act is the next frame's, not the move's.
    assert land.index("nameMarkBuddyMoveTo(buddy, spot);") < land.index("setTimeout(() => {") < land.index('nameMarkBuddyAct("land")')
    assert 'nameMarkBuddyAct("land");\n  const spots' not in land
    # Nothing to hand over after a throw: the blend (two restyles) is skipped.
    move = _fn(AV, "nameMarkBuddyMoveTo")
    assert 'if (buddy.classList.contains("nmb-poofing") || buddy.classList.contains("nmb-walking")) nameMarkBuddyBlend(buddy, stop);' in move
    # The board's box is read before the move's writes, and not at all off its tab.
    assert move.index("const board = nameMarkBuddyCanvasAt(") < move.index("nameMarkBuddyPut(buddy, x, y);")
    canvas = _fn(AV, "nameMarkBuddyCanvasAt")
    assert canvas.index('board.closest(".hidden")') < canvas.index("nameMarkBuddyShown(board)")
    # The splat's face is a few frames after its class change.
    flat = _fn(THROW, "companionThrowFlat")
    assert 'setTimeout(() => nmb.flight && nameMarkBuddyExpress("surprised"' in flat


def test_letting_go_of_the_companion_does_not_read_layout_for_the_selection_popup() -> None:
    sel = (ROOT / "frontend" / "js" / "selection.js").read_text(encoding="utf-8")
    up = sel[sel.index('document.addEventListener("mouseup", (event) => {') :]
    up = up[: up.index("});")]
    assert up.index('event.target.closest("#nm-buddy")') < up.index("syncSelectionPopup()")


# The owner, 2026-10-27: "I dont want it to always get caught or slide on exactly
# what is above or below it, sometimes i want it to go far, or into the corner,
# ro even off one edge and onto the other, or maybe even to go off the top of
# the screen and fall back down. it needs ot be mroe biological, natural and
# varied." The release's speed and angle choose the flight's aim, planned there.
_MANY = (
    "function many(n, x, y, vx, vy, world = W) { companionThrowMemo.aim = {}; companionThrowMemo.arrive = ''; const out = [];"
    " for (let i = 1; i <= n; i += 1) { companionThrowSeed.seed = 100 + i; const p = companionThrowPlan(x, y, vx, vy, world); const end = p.path[p.path.length - 1];"
    "  out.push({ aim: p.aim, kind: end.fate && end.fate.kind, arrive: end.arrived || '', minY: Math.round(Math.min(...p.path.map((s) => s.y))),"
    "   minX: Math.round(Math.min(...p.path.map((s) => s.x))), maxX: Math.round(Math.max(...p.path.map((s) => s.x))), x: Math.round(end.x), y: Math.round(end.y),"
    "   on: end.on === 'floor' ? 'floor' : end.on ? end.on.y : null, d60: draw(p, 1000 / 60) }); } return out; }"
)


def _many(body: str):
    return _plan(f"(() => {{ {_MANY}; return {body}; }})()")


@needs_node
def test_a_soft_throw_lands_near_and_a_hard_one_is_aimed_by_its_angle() -> None:
    got = _many("{ soft: many(12, 600, 400, 0.5, -0.4), up: many(16, 600, 400, 0.2, -2.3), right: many(16, 600, 400, 2.3, -0.4), left: many(16, 700, 400, -2.3, -0.6) }")
    for r in got["soft"]:
        assert r["aim"] == "near" and abs(r["x"] - 600) < 420, r
    up = {r["aim"] for r in got["up"]}
    assert {"sky", "hang"} <= up, up
    for r in got["up"]:
        if r["aim"] == "sky":
            # Up off the top of the window (its whole height past it) and back down inside.
            assert r["minY"] < -120 and 48 <= r["y"] <= 780 and r["kind"] != "hang", r
    for side in ("right", "left"):
        aims = {r["aim"] for r in got[side]}
        assert {"far", "wrap", "corner"} <= aims, (side, aims)
        for r in got[side]:
            if r["kind"] == "wrap":
                assert r["d60"]["wraps"] >= 1 and r["maxX"] > 1376 and r["minX"] < 0, r
            if r["kind"] == "corner":
                assert r["x"] in (0, 1376), r
        far = [r for r in got[side] if r["aim"] == "far"]
        assert all(abs(r["x"] - (600 if side == "right" else 700)) > 450 for r in far), far
    # Never the same aim twice running for throws alike.
    for runs in got.values():
        aims = [r["aim"] for r in runs if r["aim"] != "near"]
        assert all(a != b for a, b in zip(aims, aims[1:])), aims


@needs_node
def test_a_ledge_catches_a_slow_fall_and_a_fast_one_passes_or_glances_off() -> None:
    got = _many("{ slow: many(20, 500, 380, 0.05, 0.1), fast: many(20, 500, 60, 0.05, 1.8), edge: many(20, 690, 60, 0.05, 1.8) }")
    # A slow fall on to it is caught (the ledge, or a slide or tumble off its end).
    assert sum(r["on"] == 420 or r["kind"] in ("slip", "grab") for r in got["slow"]) >= 16, got["slow"]
    # Falling fast past it, it goes on down.
    assert sum(r["on"] == 420 for r in got["fast"]) <= 2, [r["on"] for r in got["fast"]]
    # Near its end it glances off, out past the end.
    assert sum(r["x"] > 700 for r in got["edge"]) >= 10, [r["x"] for r in got["edge"]]


@needs_node
def test_it_comes_down_in_varied_ways_never_the_same_twice_running() -> None:
    got = _many("many(16, 480, 380, 0.3, -0.5).map((r) => r.arrive)")
    seen = [a for a in got if a]
    assert len(seen) >= 12 and {"catch", "slide", "tumble"} <= set(seen), got
    assert all(a != b for a, b in zip(seen, seen[1:])), seen


@needs_node
def test_the_varied_flights_still_draw_under_40px_a_frame_except_a_wrap() -> None:
    got = _many(
        "[...many(10, 600, 400, 0.2, -2.3), ...many(10, 600, 400, 2.3, -0.4), ...many(10, 480, 380, 0.3, -0.5), ...many(10, 690, 60, 0.05, 1.8)].map((r) => r.d60)"
    )
    for r in got:
        assert r["worst"] < 40 and r["rest"] and (r["x"], r["y"]) == (r["endX"], r["endY"]), r


@needs_node
def test_reduce_motion_has_no_aim() -> None:
    got = _plan("(() => { still = true; return companionThrowPlan(600, 400, 0.2, -2.3, W).aim; })()")
    assert got == ""


@needs_node
def test_a_hard_steep_throw_leaves_the_top_from_mid_screen_and_falls_back_in() -> None:
    # The owner: "or maybe even to go off the top of the screen and fall back
    # down". From y 500 the arc used to top out at about y -78, so it never
    # chose to; now the climb is carried (lighter on the way up) to clear the
    # top by its height. A moderate upward throw still hangs or bounces.
    got = _many("{ mid: many(12, 600, 500, 0.2, -2.3), high: many(12, 600, 300, -0.3, -2.0), low: many(12, 600, 700, 0.1, -2.3), soft: many(12, 600, 500, 0.1, -1.4) }")
    for name in ("mid", "high", "low"):
        sky = [r for r in got[name] if r["aim"] == "sky"]
        assert len(sky) >= 4, (name, [r["aim"] for r in got[name]])
        for r in sky:
            # Wholly off the top (its corner its height and more above 0), then down inside.
            assert r["minY"] < -100 and 48 <= r["y"] <= 780 and 0 <= r["x"] <= 1376, r
        aims = [r["aim"] for r in got[name]]
        assert all(a != b for a, b in zip(aims, aims[1:])), aims
    assert {r["aim"] for r in got["soft"]} <= {"hang", "bounce"}, got["soft"]


@needs_node
def test_a_hand_catch_holds_even_mid_tumble_or_slide() -> None:
    # Landed near a ledge's end tumbling or sliding, then caught by its hands
    # as it went off: it stays hanging there (a tumble once carried it on down).
    got = _many("many(30, 620, 400, 0.15, -0.2)")
    slips = [r for r in got if r["kind"] in ("slip", "grab")]
    assert slips and {r["arrive"] for r in slips} & {"slide", "tumble"}, [(r["kind"], r["arrive"]) for r in got]
    for r in slips:
        assert r["y"] == 420 + 81 and r["x"] in (300, 700), r
