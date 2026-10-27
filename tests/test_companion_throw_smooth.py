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
            " while (flown < end.t && i < 5000) { i += 1; flown = Math.min(end.t, flown + Math.min(32, hitch && i % hitch === 0 ? 120 : ms));"
            "  const s = flown >= end.t ? end : companionThrowAtTime(plan.path, flown);"
            "  if (last) { const d = Math.hypot(s.x - last.x, s.y - last.y); if (d > 300) wraps += 1; else worst = Math.max(worst, d); } last = s; }"
            " return { worst: +worst.toFixed(1), wraps, x: last.x, y: last.y, endX: end.x, endY: end.y, rest: end.rest }; }",
        ]
    )
    script = "\n".join([consts, base, pure, harness, f"console.log(JSON.stringify({body}));"])
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_the_landing_is_worked_out_once_at_the_release_and_the_path_ends_there() -> None:
    got = _plan(
        "[[1.6, -0.4], [-1.4, -0.3], [0.1, -2.0], [1.2, -1.2], [0.2, 1.4]].map(([vx, vy], n) => {"
        " companionThrowSeed.seed = n + 3; spots = 0; const p = companionThrowPlan(600, 400, vx, vy, W);"
        " const end = p.path[p.path.length - 1];"
        " return { spots, rest: end.rest, steps: p.path.length, fixed: p.path.every((s, i) => i === 0 || Math.abs(s.t - p.path[i - 1].t - 16) < 1e-9 || s.rest),"
        " landAt: [p.spot.x, p.spot.y], endAt: [Math.round(end.x), Math.round(end.y)] }; })"
    )
    for r in got:
        assert r["spots"] == 1, r
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
            _fn(AV, "nameMarkBuddyObstacles"),
            _fn(AV, "nameMarkBuddyMeasureOnce"),
            "const once = nameMarkBuddyMeasureOnce(() => { const a = nameMarkBuddyObstacles('notes'); a.push('x');"
            " nameMarkBuddyMeasureOnce(() => nameMarkBuddyObstacles('notes')); return nameMarkBuddyObstacles('notes').length; });",
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
