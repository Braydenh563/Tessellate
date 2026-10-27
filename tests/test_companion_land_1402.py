"""INBOX 1402: a thrown companion settles where it lands.

The owner, 2026-10-27: "ill trow the companions sometimes but then it tll
fly back to some position someitmes across the screen". Measured
(scratchpad/ui-sweeps/throwsettle1402.js, 1280x720): come down on the
window's foot over the bottom bar's buttons, the landing's move took it 224
to 256px along the bar, and from x 1000 it went 320px. `nameMarkBuddyLandNear`
runs here in node as written, against the bar's buttons from that sweep.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def _const(name: str) -> str:
    start = AV.index(f"const {name} = ")
    return AV[start : AV.index("\n", start)]


#: The status bar's buttons at 1280x720 (its top at 683), from the sweep.
BAR = "[[47,688,75,716],[83,688,168,716],[176,688,257,716],[1009,688,1041,716],[1049,688,1077,716],[1201,688,1229,716],[1237,688,1265,716]]"


def _land(calls: str):
    script = "\n".join(
        [
            "const NMB_W = 64, NMB_H = 92, NMB_FEET = 90;",
            "const innerWidth = 1280, innerHeight = 720;",
            f"const OBS = {BAR}.map(([left, top, right, bottom]) => ({{ left, top, right, bottom }}));",
            "let measured = 0;",
            'function nameMarkBuddyTab() { return "dashboard"; }',
            "function nameMarkBuddyObstacles() { measured += 1; return OBS; }",
            "function nameMarkBuddyLedges() { return { top: { bottom: 44 }, bottom: { top: 683 } }; }",
            # The float's hit shape as drawn: head, body to its feet, Atlas's tail.
            "function nameMarkBuddyHits(x, y, pose, obs) { const parts = [[x + 5, y, x + 59, y + 46], [x + 8, y + 43, x + 56, y + 90], [x + 30, y + 50, x + 82, y + 94]]; "
            + "return parts.some(([l, t, r, b]) => obs.some((o) => r > o.left - 4 && l < o.right + 4 && b > o.top - 4 && t < o.bottom + 4)); }",
            _const("NMB_LAND_NEAR"),
            _const("NMB_LAND_STEP"),
            _fn("nameMarkBuddyLandNear"),
            f"const out = {calls}; console.log(JSON.stringify({{ out, measured }}));",
        ]
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_landing_over_the_bars_buttons_settles_beside_where_it_came_down():
    # The drop's own choices from the sweep: 240px and 320px along the bar.
    got = _land(
        "[nameMarkBuddyLandNear(27, 594, { kind: 'yours', pose: 'float', x: 267, y: 594 }),"
        " nameMarkBuddyLandNear(1000, 594, { kind: 'yours', pose: 'float', x: 680, y: 594 })]"
    )
    for (x, y), spot in zip([(27, 594), (1000, 594)], got["out"]):
        moved = ((spot["x"] - x) ** 2 + (spot["y"] - y) ** 2) ** 0.5
        assert moved <= 24, (x, spot)
        assert spot["pose"] == "float" and spot["kind"] == "yours"
        # Clear of every button: its tail's foot above the bar's buttons.
        assert spot["y"] + 94 + 4 <= 688 or spot["x"] + 82 + 4 <= 47, spot


@needs_node
def test_a_near_place_and_a_fall_straight_down_are_kept_and_cost_no_search():
    got = _land(
        "[nameMarkBuddyLandNear(300, 594, { kind: 'yours', pose: 'stand', x: 340, y: 594 }),"
        " nameMarkBuddyLandNear(500, 200, { kind: 'yours', pose: 'stand', x: 520, y: 594, falls: true })]"
    )
    near, fall = got["out"]
    assert (near["x"], near["pose"]) == (340, "stand")
    assert (fall["x"], fall["y"]) == (520, 594)
    assert got["measured"] == 0


@needs_node
def test_with_nothing_nearer_the_drops_choice_stands():
    # A far choice with no free air between: the search stops at its distance.
    got = _land("nameMarkBuddyLandNear(27, 700, { kind: 'bar', pose: 'stand', x: 140, y: 594 })")
    spot = got["out"]
    assert ((spot["x"] - 27) ** 2 + (spot["y"] - 700) ** 2) ** 0.5 <= ((140 - 27) ** 2 + (594 - 700) ** 2) ** 0.5


def test_a_drop_and_a_throw_both_land_near():
    spot = _fn("nameMarkBuddyThrowSpot")
    assert "nameMarkBuddyLandNear(s.x, s.y, spot)" in spot and "innerWidth" not in spot
    assert "nameMarkBuddyLandNear(box.left, box.top, nameMarkBuddyDrop(Math.round(box.left), Math.round(box.top)))" in AV


# --- Part C: a drop at the bottom bar stands on it, never sits over its buttons.
# Measured (/tmp/claude-0/atlasfix/d.js, 1440x900, bar top 863.2): a throw
# down the right side and drops on the bar came to rest as `sit` at y 791,
# its 92px box 20px into the bar and 28x15 over two buttons.
def _drop(calls: str):
    script = "\n".join(
        [
            "const NMB_W = 64, NMB_H = 92, NMB_FEET = 90, NMB_SEAT = 72, NMB_GRIP = 5;",
            "const innerWidth = 1440, innerHeight = 900;",
            "const nmb = { scale: 1 };",
            "const BAR = 863.2;",
            "const OBS = [[1254,868,1282,896],[1286,868,1314,896],[1318,868,1346,896],[936,868,1081,896]]"
            ".map(([left, top, right, bottom]) => ({ left, top, right, bottom }));",
            'function nameMarkBuddyTab() { return "dashboard"; }',
            "function nameMarkBuddyObstacles() { return OBS; }",
            "function nameMarkBuddyLedges() { return { top: { bottom: 44 }, bottom: { top: BAR, bottom: 900 } }; }",
            "function nameMarkBuddyEdges() { return [{ type: 'top', kind: 'bar', y: BAR, left: 0, right: 1440, top: BAR, bottom: 900 }]; }",
            "function nameMarkBuddyChoose() { return null; }",
            # Hit shape as drawn: head, body (to the soles when standing, the seat otherwise), tail.
            "function nameMarkBuddyHits(x, y, pose, obs, legs) { const b = pose === 'stand' ? y + 82 : y + 90; "
            "const parts = [[x + 5, y, x + 59, y + 46], [x + 8, y + 43, x + 56, b], [x + 30, y + 50, x + 82, pose === 'stand' ? y + 90 : y + 94]]; "
            "return parts.some(([l, t, r, bt]) => obs.some((o) => r > o.left - 4 && l < o.right + 4 && bt > o.top - 4 && t < o.bottom + 4)); }",
            _fn("nameMarkBuddyStances"),
            _fn("nameMarkBuddyStepAside"),
            _fn("nameMarkBuddyYoursObstacles"),
            _fn("nameMarkBuddyDrop"),
            f"const out = {calls}; console.log(JSON.stringify({{ out }}));",
        ]
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)["out"]


@needs_node
def test_a_drop_at_the_bar_keeps_its_box_above_the_bars_top():
    pts = [(x, y) for x in (40, 700, 1240, 1300, 1380) for y in (790, 850, 886, 899)]
    spots = _drop("[" + ",".join(f"nameMarkBuddyDrop({x}, {y})" for x, y in pts) + "]")
    for (x, y), spot in zip(pts, spots):
        assert spot["y"] + 92 <= 863.2 + 3, ((x, y), spot)
        assert spot["y"] + 90 <= 863.2 + 1, ((x, y), spot)


def test_escape_with_the_onboarding_overlay_gone_does_not_throw():
    # A page that removed the overlay (a test harness, a sweep) threw on every
    # Escape: "Cannot read properties of null (reading 'classList')".
    text = (ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8")
    assert '$("onboarding-overlay")?.classList.contains("hidden") === false' in text


@needs_node
def test_a_drop_over_the_bars_buttons_floats_just_above_them():
    # Release over the row of buttons (no gap a float fits): up a few px, not
    # the chooser's perch (the stub chooser has none, so it would stay put).
    spots = _drop("[nameMarkBuddyDrop(1300, 850), nameMarkBuddyDrop(1240, 886)]")
    for spot in spots:
        assert spot["y"] + 94 + 4 <= 868 or spot["pose"] == "stand", spot
        assert spot["y"] + 92 <= 863.2 + 3, spot
