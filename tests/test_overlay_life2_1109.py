"""INBOX 1719 (b), second batch of life and biological design. Fixed clock, seeded engines, no real time."""

from __future__ import annotations

import math

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import engine as eng
from tests.test_overlay_life_1670 import calm
from tests.test_overlay_ride_1670 import make


def _gaps(seed: int, n: int = 12) -> list[float]:
    e, _s = make("masculine", "float", seed=seed, plain=True)
    return [round(e._ambient_gap(), 6) for _ in range(n)]


def test_two_seeds_give_different_blink_sequences() -> None:
    # The ambient streams used to be seeded from the Mersenne key's first word, 2147483648 for every seed.
    assert _gaps(1) != _gaps(2) != _gaps(3)
    assert _gaps(1) != _gaps(3)


def test_a_seed_is_still_repeatable() -> None:
    assert _gaps(5) == _gaps(5)


# --- (2) vertical follow-through and a settle -----------------------------------------------------------


def _land(dt: float = 0.016) -> list[tuple[float, float]]:
    """A fall that speeds up to 600 px/s over 0.5 s and stops dead at 1.5 s; (t, tail tip y) for 2.5 s."""
    tr = bh.Trail()
    out = []
    for i in range(160):
        t = i * dt
        tr.step(dt, 0.0, 600.0 * min(1.0, t / 0.5) if t < 1.5 else 0.0)
        out.append((t, tr.lift))
    return out


def test_a_landing_throws_the_tail_down_then_up_and_it_settles() -> None:
    rows = _land()
    pre = [y for t, y in rows if 1.3 < t < 1.45]
    post = [y for t, y in rows if 1.5 <= t <= 1.8]  # the 0.3 s after the landing
    assert max(abs(y) for y in pre) < 1.0  # a steady fall barely throws it
    later = [y for t, y in rows if 1.8 < t <= 2.4]
    assert max(post) > 4.0  # the tip is thrown down within 0.3 s of the landing
    assert min(later) < -1.0  # and swings back over the root
    assert abs(rows[-1][1]) < 0.6


def test_a_floor_walk_does_not_move_the_vertical_chain() -> None:
    tr = bh.Trail()
    for i in range(200):
        tr.step(0.016, 55.0 * min(1.0, i * 0.016), 0.0)
    assert tr.lift == 0.0


def _startled(seed: int):
    e, _s = make("masculine", "float", seed=seed, plain=True)
    calm(e)
    e._enter("startle", 0.0)
    return e


def test_a_startle_is_followed_by_an_exhale_one_to_three_seconds_on() -> None:
    e = _startled(4)
    t, sys_ = 0.0, []
    while t < 6.0:
        t += 0.05
        e.update(t)
        sys_.append((t, e.pose_goal.sy))
    assert 0.5 <= e.settle_at - 0.5 <= 3.0 + 0.1  # begins 1 to 3 s after the startle ends at 0.5 s
    base = e.pose_goal.sy
    inside = [y for t, y in sys_ if e.settle_at <= t <= e.settle_at + eng.EXHALE_FOR]
    outside = [y for t, y in sys_ if t > e.settle_at + eng.EXHALE_FOR + 0.2]
    assert inside and min(inside) < min(outside) - 0.02  # shoulders down by about 3%
    assert abs(outside[-1] - base) < 1e-9


def test_no_exhale_without_a_startle() -> None:
    e, _s = make("masculine", "float", seed=4, plain=True)
    calm(e)
    e._enter("stand", 0.0)
    ys = []
    for i in range(1, 120):
        e.update(i * 0.05)
        ys.append(e.pose_goal.sy)
    assert max(ys) - min(ys) < 0.02


# --- (2) the in-app side: the same vertical chain in atlasTailFollow ---------------------------------------

JS_HARNESS = r"""
const vm = require("vm"); const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const a = src.indexOf("function atlasTailFollow("), b = src.indexOf("//: The tail's centreline bent");
const ctx = { Math, Number, Object, Array };
vm.createContext(ctx);
vm.runInContext(src.slice(a, b).replace(/atlasTailFollow\.strands = [\s\S]*?\n};\n/, ""), ctx);
const tail = {}; const rows = [];
let y = 0, v = 0;
for (let i = 0; i < 160; i += 1) {
  const t = i * 0.016; v = t < 1.5 ? 600 * Math.min(1, t / 0.5) : 0; y += v * 0.016;
  const bend = ctx.atlasTailFollow(tail, 0.016, 100, y);
  rows.push([t, tail.follow.lift[2], bend]);
}
console.log(JSON.stringify(rows));
"""


def test_the_in_app_tail_is_thrown_down_by_a_landing_like_the_desk_trail() -> None:
    import json
    import shutil
    import subprocess
    from pathlib import Path

    import pytest

    if not shutil.which("node"):
        pytest.skip("needs node")
    js = Path(__file__).resolve().parents[1] / "frontend" / "js" / "atlas-life.js"
    rows = json.loads(subprocess.run(["node", "-e", JS_HARNESS, str(js)], capture_output=True, text=True, timeout=60, check=True).stdout)
    pre = [r[1] for r in rows if 1.3 < r[0] < 1.45]
    post = [r[1] for r in rows if 1.5 <= r[0] <= 1.8]
    assert max(abs(v) for v in pre) < 2.0 and max(post) > 4.0
    assert abs(rows[-1][1]) < 0.6


EXHALE_HARNESS = r"""
const vm = require("vm"); const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const grab = (re) => { const m = src.match(re); if (!m) throw new Error(String(re)); return m[0]; };
const played = [];
const ctx = { Math, atlasMicroMay: (b) => b.ok, atlasMicroPlay: (el, fr, ms) => played.push([el, fr, ms]) };
vm.createContext(ctx);
vm.runInContext("function atlasMicroDo() {}\n" + grab(/^atlasMicroDo\.exhale = [\s\S]*?\n};$/m), ctx);
const body = {}; const box = { ok: true, querySelector: () => body };
ctx.atlasMicroDo.exhale(box); ctx.atlasMicroDo.exhale({ ok: false, querySelector: () => body }); ctx.atlasMicroDo.exhale(null);
console.log(JSON.stringify({ n: played.length, ms: played[0][2], ys: played[0][1].map((f) => f.translate), same: played[0][0] === body }));
"""


def test_the_in_app_exhale_sinks_the_shoulders_and_only_when_nothing_else_moves() -> None:
    import json
    import shutil
    import subprocess
    from pathlib import Path

    import pytest

    if not shutil.which("node"):
        pytest.skip("needs node")
    root = Path(__file__).resolve().parents[1] / "frontend" / "js"
    r = json.loads(subprocess.run(["node", "-e", EXHALE_HARNESS, str(root / "atlas-micro.js")], capture_output=True, text=True, timeout=60, check=True).stdout)
    assert r["n"] == 1 and r["same"] and r["ms"] == 1500  # one play: a busy or missing figure plays none
    assert r["ys"] == ["0px 0px", "0px 2px", "0px 2px", "0px 0px"]
    avatars = (root / "avatars.js").read_text(encoding="utf-8")
    assert 'was === "startle"' in avatars and "atlasMicroDo?.exhale" in avatars  # wired to the startle's end


# --- (4) the stand's fixed 4 s loop and the floater's breath ----------------------------------------------


def _still(seed: int):
    e, _s = make("masculine", "float", seed=seed, plain=True)
    calm(e)
    e._enter("stand", 0.0)
    e.state_until = math.inf
    e.next_ambient = math.inf
    e.last_active = math.inf
    e.mind.needs = {"rest": 0, "curiosity": 0, "play": 0}
    return e


def test_a_calm_stand_never_draws_the_same_cycle_twice() -> None:
    # Measured before the drift: one picture per idle frame in 2 minutes (every cycle the same picture).
    e = _still(3)
    seen, frames, t = set(), set(), 0.0
    while t < 120.0:
        t += 1 / 30
        o = e.update(t)
        if o.frame.startswith("idle"):
            seen.add((o.frame, o.pose))
            frames.add(o.frame)
    assert len(frames) >= 24
    assert len(seen) >= 2 * len(frames)  # each frame is drawn in at least two leans over two minutes


def test_the_stand_drift_is_small_and_moves_within_the_minute() -> None:
    e = _still(3)
    t, leans = 0.0, []
    while t < 120.0:
        t += 1 / 30
        o = e.update(t)
        if o.frame.startswith("idle"):
            leans.append((t, o.pose[2] if o.pose else 0.0))
    assert max(abs(v) for _t, v in leans) <= 0.05  # under 3 degrees
    last, still = leans[0], 0.0
    for t, v in leans:
        if v != last[1]:
            still, last = max(still, t - last[0]), (t, v)
    assert still <= 60.0  # the lean changes cell at least once a minute


def _drift_breaths(mood: str, seconds: float = 60.0) -> float:
    e, _s = make("masculine", "float", seed=5, plain=True)
    calm(e)
    e.mind.mood = lambda now, hour=None: mood  # type: ignore[method-assign]
    e._enter("drift", 0.0)
    e.goal, e.trip, e.state_until = (e.x + 1e9, e.y), True, math.inf
    t = 0.0
    while t < seconds:
        t += 1 / 30
        e.update(t)
    return e.drift_phase


def test_the_floaters_breath_follows_the_mood_instead_of_a_fixed_four_point_four_seconds() -> None:
    calm_n, startled_n, sleepy_n = _drift_breaths("content"), _drift_breaths("startled"), _drift_breaths("sleepy")
    assert startled_n > calm_n * 1.2 > sleepy_n * 1.2  # breaths in a minute: quicker startled, slower sleepy
