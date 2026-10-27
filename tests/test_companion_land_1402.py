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
            "function nameMarkBuddyHits(x, y, pose, obs) { const parts = [[x + 5, y, x + 59, y + 46], [x + 8, y + 43, x + 56, y + 90], [x + 30, y + 50, x + 82, y + 94]];"
            " return parts.some(([l, t, r, b]) => obs.some((o) => r > o.left - 4 && l < o.right + 4 && b > o.top - 4 && t < o.bottom + 4)); }",
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
