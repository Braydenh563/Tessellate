"""What can happen to a thrown companion on the way (INBOX 1301 D6).

The owner: "If I flick the companion near the top bar or top screen
elements, I want there to be the chance that the compainon an datlas will
land up there or catch the rop elements and/or climb on to them, or maybe
eve splat on the edge of the screen and slide down to land on a platform,
maybe even the chance to go off one side and come back on the other."

`companionThrowStep` (frontend/js/companion-throw.js) wraps the flight's own
step (`nameMarkBuddyFlightStep`, avatars.js) and is pure: platform rects and
a velocity in, an outcome out. These run it in node as written, seeded, over
a few hundred throws each. The same in a browser, measured on the page's own
panels, is scratchpad/ui-sweeps/throwfates.js.
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
CSS = (ROOT / "frontend" / "css" / "companion-throw-lazy.css").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(src: str, name: str) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def _run(body: str):
    consts = re.search(r"^const NMB_THROW = .*;$", AV, re.M).group(0)
    base = "\n".join(_fn(AV, n) for n in ("nameMarkBuddyFlightStep", "nameMarkBuddyThrowFeel"))
    pure = THROW[: THROW.index("//: The throw itself (moved here")]
    harness = (
        "const W = { left: 0, right: 1376, top: 48, floor: 780, ledges: [], w: 64, hang: 43, climb: 84 };"
        "function one(seed, x, y, vx, vy, world = W) {"
        " const rand = companionThrowRng(seed); const k = nameMarkBuddyThrowFeel([rand(), rand(), rand()], Math.hypot(vx, vy));"
        " let s = { x, y, vx, vy, rot: 0, t: 0, on: null, rest: false, tried: {} }; let minX = x, maxX = x, slide = 0, held = 0, steps = 0;"
        " while (!s.rest && steps < 3000) { const was = s; s = companionThrowStep(s, 16, world, k, nameMarkBuddyFlightStep, rand); steps += 1;"
        "  minX = Math.min(minX, s.x); maxX = Math.max(maxX, s.x);"
        "  if (s.splat && was.splat) { slide = Math.max(slide, s.y - was.y); if (s.y === was.y) held += 16; } }"
        " return { kind: s.fate && s.fate.kind, at: s.fate && s.fate.at, x: Math.round(s.x), y: Math.round(s.y), on: s.on === 'floor' ? 'floor' : s.on ? s.on.y : null,"
        "  minX: Math.round(minX), maxX: Math.round(maxX), slide: +(slide / 16).toFixed(3), held, rest: s.rest }; }"
        "function many(n, ...a) { const out = []; for (let i = 1; i <= n; i += 1) out.push(one(i, ...a)); return out; }"
    )
    script = "\n".join([consts, base, pure, harness, f"console.log(JSON.stringify({body}));"])
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def _kinds(runs):
    out: dict[str, int] = {}
    for r in runs:
        out[r["kind"]] = out.get(r["kind"], 0) + 1
    return out


@needs_node
def test_thrown_up_at_the_top_bar_it_sometimes_catches_it_and_hangs() -> None:
    runs = _run("many(200, 600, 400, 0.3, -2.4)")
    kinds = _kinds(runs)
    assert 50 <= kinds.get("hang", 0) <= 110, kinds
    # The rest bounce off it as before (down on the floor, or in the air when
    # the flight's time is up, which the drop then places).
    assert kinds.get("floor", 0) + kinds.get("air", 0) >= 60, kinds
    for r in runs:
        if r["kind"] == "hang":
            assert r["y"] == 43 and r["rest"]
    # A lob that barely reaches the bar is never caught.
    assert "hang" not in _kinds(_run("many(100, 600, 120, 0.1, -0.3)"))


@needs_node
def test_a_panel_edge_passed_going_up_is_sometimes_caught_and_climbed() -> None:
    world = "{ ...W, ledges: [{ left: 300, right: 900, y: 300 }] }"
    runs = _run(f"many(200, 560, 640, 0.2, -1.5, {world})")
    kinds = _kinds(runs)
    assert 60 <= kinds.get("climb", 0) <= 130, kinds
    for r in runs:
        if r["kind"] == "climb":
            # Its hands on the edge (y 300 + 84 is the hanging corner); it
            # climbs on to the top of that edge.
            assert r["y"] == 384 and r["at"][1] == 300 and 300 <= r["at"][0] <= 900
    # Not caught, it may still come down on the panel from above.
    assert kinds.get("ledge", 0) + kinds.get("floor", 0) + kinds.get("air", 0) >= 50, kinds


@needs_node
def test_reaching_for_an_edge_at_the_top_of_the_arc_catches_it() -> None:
    # Thrown so the arc tops out just under the edge's grip: only the reach
    # (26px) catches it there, and some throws do.
    world = "{ ...W, ledges: [{ left: 300, right: 900, y: 300 }] }"
    runs = _run(f"many(120, 560, 420, 0, -0.42, {world})")
    assert _kinds(runs).get("climb", 0) >= 20, _kinds(runs)


@needs_node
def test_thrown_hard_into_a_side_it_splats_and_slides_down_to_a_platform() -> None:
    world = "{ ...W, ledges: [{ left: 1100, right: 1400, y: 560 }] }"
    runs = _run(f"many(200, 1000, 300, 2.6, -0.2, {world})")
    kinds = _kinds(runs)
    assert kinds.get("splat", 0) >= 50, kinds
    for r in runs:
        if r["kind"] == "splat":
            assert r["x"] == 1376 and r["on"] == 560 and r["y"] == 560
            assert r["held"] >= 224 and 0 < r["slide"] <= 0.32
    # No platform under it there: down to the floor.
    floor = [r for r in _run("many(120, 1000, 300, 2.6, -0.2)") if r["kind"] == "splat"]
    assert floor and all(r["on"] == "floor" and r["y"] == 780 for r in floor)


@needs_node
def test_thrown_hard_enough_it_may_go_off_one_side_and_come_back_on_the_other() -> None:
    runs = _run("many(200, 1000, 300, 3.2, -0.6)")
    wraps = [r for r in runs if r["kind"] == "wrap"]
    assert 30 <= len(wraps) <= 90, _kinds(runs)
    for r in wraps:
        # Out past the right edge, in from wholly off the left (its corner
        # 64px out, its width), and down inside the window.
        assert r["maxX"] > 1376 + 64 and r["minX"] <= -64
        assert 0 <= r["x"] <= 1376 and r["rest"]
    left = [r for r in _run("many(200, 300, 300, -3.2, -0.6)") if r["kind"] == "wrap"]
    assert left and all(r["minX"] < -64 and r["maxX"] >= 1376 + 64 for r in left)


@needs_node
def test_a_gentle_throw_into_a_side_only_bounces() -> None:
    kinds = _kinds(_run("many(150, 1200, 300, 0.7, -0.2)"))
    assert "splat" not in kinds and "wrap" not in kinds, kinds


@needs_node
def test_the_same_seed_is_the_same_throw() -> None:
    a, b = _run("[one(7, 1000, 300, 3.2, -0.6), one(7, 1000, 300, 3.2, -0.6)]")
    assert a == b


def test_each_landing_settles_into_a_posture_its_pose_allows() -> None:
    table = re.search(r"const COMPANION_THROW_SETTLE = \{(.*?)\n\};", THROW, re.S).group(1)
    acts = AV[AV.index("const NAME_MARK_BUDDY_ACTS = {") :]
    seen = set()
    for pose, names in re.findall(r"(\w+): \[([^\]]*)\]", table):
        for name in re.findall(r'"(\w+)"', names):
            spec = re.search(rf"\n  {name}: \{{[^}}]*poses: \[([^\]]*)\]", acts)
            assert spec and f'"{pose}"' in spec.group(1), (pose, name)
            seen.add(name)
    # Several ways to sit, to hang and to stand, lying down among them.
    assert {"dangle", "kick", "swing", "onehand", "lie", "stretch"} <= seen


def test_the_throw_is_lazy_and_boot_only_opens_the_door() -> None:
    assert 'companionThrow: ["/css/companion-throw-lazy.css", "/js/companion-throw.js"]' in APP
    assert "companion-throw" not in INDEX
    assert "function nameMarkBuddyThrow(" not in AV and "function nameMarkBuddyThrow(" in THROW
    assert 'ensureModule("companionThrow");' in AV
    assert 'typeof nameMarkBuddyThrow === "function"' in AV, "a let-go before the file arrives is a drop"


def test_reduce_motion_gets_the_plain_flight_and_no_fates() -> None:
    throw = _fn(THROW, "nameMarkBuddyThrow")
    still = throw[throw.index("if (nameMarkBuddyNoTravel()) {") : throw.index("const char =")]
    assert "nameMarkBuddyFlightStep(s, 16, world, feel)" in still and "companionThrowStep" not in still


def test_the_moments_are_transforms_on_the_figure_and_block_nothing() -> None:
    assert "pointer-events" not in CSS
    for rule in re.findall(r"\{([^{}]*)\}", CSS):
        for prop in re.findall(r"([\w-]+):", rule):
            assert prop in {"scale", "transform-origin", "animation", "translate", "rotate"}, prop
    # The climb's wait and the splat's class are outside the frame loop's body.
    frame = _fn(THROW, "nameMarkBuddyThrow")
    frame = frame[frame.index("const frame = (now) =>") : frame.index("const next = () =>")]
    assert "setTimeout" not in frame and "classList.toggle" not in frame
