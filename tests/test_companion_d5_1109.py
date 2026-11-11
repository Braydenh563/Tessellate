"""Companion catalogue D5, the in-app half of the desk's last four acts (atlascat-1108 D5; INBOX 1696 v): a slow pat on
the head (`int.pat`), a fast swipe across it that spins it once (`int.swipe_twirl`), the cloud ride (`move.cloud_ride`)
and the leap and grab when it takes hold of an edge from its feet (`trans.upright>hang`). The decisions are pure
functions run as written in node; the wiring is pinned as text. The desk half is `tests/test_overlay_*`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
TRAVEL = (ROOT / "frontend" / "js" / "companion-travel.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
RECT = {"left": 100, "top": 200, "width": 100, "height": 120}  # the head is the top 42 percent: y 200 to 250


def fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def touch_scope() -> str:
    start = AV.index("nmb.touch = (() => {")
    return AV[start : AV.index("\n})();\n", start) + 7]


def run(body: str):
    script = f"const nmb = {{}};\n{fn('nameMarkBuddyStrokes')}\n{touch_scope()}\nconsole.log(JSON.stringify({body}));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def entries() -> dict:
    return {e["id"]: e for e in json.loads((ROOT / "frontend" / "companion-catalogue.json").read_text(encoding="utf-8"))["entries"]}


def dabs(n: int, depth: int, every: int, x: int = 150, y: int = 215) -> list[list[int]]:
    """`n` dips of `depth` px and back on the head, one sample every `every` ms."""
    return [[x, y + (depth if i % 2 else 0), i * every] for i in range(n)]


def patted(samples: list[list[int]]) -> bool:
    return run(f"nmb.touch.patted({json.dumps(samples)}, {json.dumps(RECT)})")


@needs_node
def test_slow_dabs_on_the_head_are_a_pat() -> None:
    assert patted(dabs(9, 14, 120))


@needs_node
def test_a_flick_a_belly_dab_two_dabs_and_a_wide_sweep_are_not() -> None:
    assert not patted(dabs(9, 14, 20)), "20 ms a dab is a flick: 0.7 px a ms, over the slow limit"
    assert not patted(dabs(9, 14, 120, y=280)), "on the belly"
    assert not patted(dabs(3, 14, 120)), "one turn is a stroke, not a pat"
    assert not patted([[100 + 40 * (i % 5), 215 + (i % 2) * 14, i * 120] for i in range(9)]), "wider than the figure"
    assert not patted(dabs(9, 3, 120)), "a hand's tremor is under a stroke's travel"
    assert not run(f"nmb.touch.patted([], {json.dumps(RECT)})")


def test_the_pat_is_wired_and_has_a_switch() -> None:
    assert "nmb.touch.patted(rub, box)" in AV and "nmb.touch.pat(buddy);" in AV
    row = re.search(r'\["rub", "[^"]*", \[([^\]]*)\]\]', AV)
    assert row and '"pat"' in row.group(1)
    scope = touch_scope()
    pat = scope[scope.index("  function pat(") : scope.index("  return {", scope.index("  function pat("))]
    assert 'ready(buddy, "pat"' in pat
    ready = scope[scope.index("  function ready(") : scope.index("  function pat(")]
    assert "nameMarkBuddyStill()" in ready and "nameMarkBuddyActOff(act)" in ready and "nameMarkBuddyAsleep(buddy)" in ready


def test_the_catalogue_counts_the_pat_as_built_on_both_sides() -> None:
    e = entries()["int.pat"]
    assert e["app"]["s"] == "built" and e["desk"]["s"] == "built"


def swipe(span: int, ms: int, n: int = 5, y: int = 260, back: bool = False) -> list[list[int]]:
    """`n` samples across `span` px in `ms` ms at height `y`, left to right; `back` turns the middle one round."""
    pts = [[100 + span * i // (n - 1), y, ms * i // (n - 1)] for i in range(n)]
    if back:
        pts[n // 2][0] = 90
    return pts


def swiped(samples: list[list[int]]) -> bool:
    return run(f"nmb.touch.swiped({json.dumps(samples)}, {json.dumps(RECT)})")


@needs_node
def test_a_fast_pass_straight_across_is_a_swipe() -> None:
    assert swiped(swipe(100, 60)), "100 px in 60 ms: 1.7 px a ms"
    assert swiped([[200 - x, y, t] for x, y, t in swipe(100, 60)]), "right to left too"


@needs_node
def test_a_slow_pass_a_short_one_a_turn_and_a_climb_are_not() -> None:
    assert not swiped(swipe(100, 400)), "250 ms window: a slow pass is a stroke"
    assert not swiped(swipe(100, 200)), "0.5 px a ms is under the fast limit"
    assert not swiped(swipe(40, 20)), "fast but only 40 percent of its width"
    assert not swiped(swipe(100, 60, back=True)), "it turned round inside the pass"
    assert not swiped([[100 + 25 * i, 200 + 30 * i, 15 * i] for i in range(5)]), "a climb, not a pass across"
    assert not run(f"nmb.touch.swiped([], {json.dumps(RECT)})")


def test_the_swipe_is_wired_and_has_a_switch() -> None:
    assert AV.index("nmb.touch.swiped(rub, box)") < AV.index("nmb.touch.patted(rub, box)"), "a swipe is checked before a pat"
    assert "nmb.touch.twirl(buddy);" in AV
    row = re.search(r'\["flip", "[^"]*", \[([^\]]*)\]\]', AV)
    assert row and '"twirl"' in row.group(1)
    scope = touch_scope()
    twirl = scope[scope.index("  function twirl(") : scope.index("  return {", scope.index("  function twirl("))]
    assert 'ready(buddy, "twirl"' in twirl and "rotate(360deg" in twirl


def test_the_catalogue_counts_the_twirl_as_built_on_both_sides() -> None:
    e = entries()["int.swipe_twirl"]
    assert e["app"]["s"] == "built" and e["desk"]["s"] == "built"


def test_the_cloud_ride_is_a_far_move_the_app_already_plays() -> None:
    """`move.cloud_ride`: the in-app cloud forms under it and carries it over a far way (a walk variant: the chooser
    gives `cloud` where `walk` would be, past three of its widths); `tests/test_companion_travel.py` holds the weights."""
    e = entries()["move.cloud_ride"]
    assert e["app"]["s"] == "built" and e["desk"]["s"] == "built"
    assert "\n  cloud(buddy, dx, dy, ctx) {" in TRAVEL and "cloud: d > s * 3 ? 1.5 : 0" in TRAVEL


def test_upright_to_hang_is_a_leap_and_a_grab() -> None:
    """`trans.upright>hang`: from a stand to a hang the way is always a leap (unless far, which chooses its own), and the
    grab plays at the end of it, on `translate` and `rotate` so the landing squash's `scale` is not fought."""
    go = fn("nameMarkBuddyGo")
    assert 'const grabs = spot.pose === "hang" && poseChanged && nmb.poseWas === "stand" && route !== "fall";' in go
    assert 'if (grabs && route !== "far") route = "leap";' in go
    assert go.index("if (grabs && route") < go.index('if (route === "hop" || route === "leap") {')
    assert "if (grabs) nmb.leapGrab?.(buddy, char, duration + setOff);" in go
    grab = TRAVEL[TRAVEL.index("nmb.leapGrab = function") :]
    assert "nameMarkBuddyStill()" in grab and "translate:" in grab and "rotate:" in grab and "scale" not in grab.split("{", 1)[1]
    e = entries()["trans.upright>hang"]
    assert e["app"]["s"] == "built" and e["desk"]["s"] == "built"
