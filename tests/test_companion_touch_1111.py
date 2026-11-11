"""The in-app companion's touch on its feet (E6, the same ask as the desk's `tests/test_overlay_touch_1111.py`): soft, a
stumble or a roll by how hard it came down. Seeded node runs of the pure flight over the real JS, a fixed 16 ms clock."""

from __future__ import annotations

import pytest


from tests.test_companion_landing_1683k import needs_node, run as _run

EXTRA = r"""
function touchOne(seed) {
  const rand = companionThrowRng(seed * 7919 + 1);
  const vx = (rand() * 2 - 1) * 3.2, vy = (rand() * 2 - 1) * 3.2;
  const x = 100 + rand() * 1100, y = 150 + rand() * 500;
  const k = nameMarkBuddyThrowFeel([rand(), rand(), rand()], Math.hypot(vx, vy));
  k.ms = 2000;
  let s = { x, y, vx, vy, rot: 0, t: 0, on: null, rest: false, tried: {} };
  let turned = 0, maxStep = 0, steps = 0, x0 = null, rolling = 0, last = 0;
  while (!s.rest && steps < 400) {
    const was = s;
    s = companionThrowStep(s, 16, W, k, nameMarkBuddyFlightStep, rand);
    steps += 1;
    if (s.roll) {
      const d = wrap(s.rot - was.rot);
      if (was.roll) { turned += d; maxStep = Math.max(maxStep, Math.abs(d)); }
      rolling += 16;
    }
    if (s.touch && x0 === null) x0 = s.x;
    last = s.x;
  }
  return { touch: s.touch || "", lie: s.lie || 0, turned: Math.round(turned), maxStep: +maxStep.toFixed(1), rolledMs: rolling,
           rest: s.rest, rot: Math.round(s.rot * 10) / 10, dx: x0 === null ? 0 : Math.round(last - x0), dir: s.dir || 0 };
}
"""


def sweep(n: int = 800):
    return _run(f"(() => {{ {EXTRA}; const o = []; for (let i = 1; i <= {n}; i += 1) o.push(touchOne(i)); return o; }})()")


@needs_node
def test_the_touch_is_set_by_how_hard_it_came_down() -> None:
    out = _run("[0.5, 1.09, 1.11, 1.69, 1.71, 2.3].map((v) => companionThrowLand.touchOf(v))")
    assert out == ["soft", "soft", "stumble", "stumble", "roll", "roll"]


@needs_node
def test_a_seeded_sweep_shows_all_three_and_a_roll_is_one_turn_the_eye_can_follow() -> None:
    rows = sweep()
    on_feet = [r for r in rows if not r["lie"] and r["touch"]]
    kinds = {k: sum(1 for r in on_feet if r["touch"] == k) for k in ("soft", "stumble", "roll")}
    assert min(kinds.values()) >= 8, kinds
    assert all(r["rest"] for r in rows)
    rolls = [r for r in on_feet if r["touch"] == "roll"]
    for r in rolls:
        # one full turn the way it was going (the start lean is under 40 degrees either side), then upright
        assert 320 <= abs(r["turned"]) <= 400, r
        assert r["turned"] * r["dir"] > 0, r
        assert r["maxStep"] <= 0.85 * 16, r  # under the slew limit: the drawn lean follows it frame for frame
        assert abs(r["rot"]) < 1.5, r
    assert max(r["maxStep"] for r in rolls) > 5, "a roll that barely turns is not one"


@needs_node
def test_a_stumble_shuffles_on_and_a_soft_touch_does_not() -> None:
    rows = [r for r in sweep() if not r["lie"] and r["touch"] in ("soft", "stumble") and abs(r["dir"]) == 1]
    soft = [abs(r["dx"]) for r in rows if r["touch"] == "soft"]
    stumble = [abs(r["dx"]) for r in rows if r["touch"] == "stumble"]
    assert sum(stumble) / len(stumble) > sum(soft) / len(soft)


@needs_node
def test_a_roll_starts_from_the_lean_it_landed_with_and_carries_on_forward() -> None:
    out = _run(
        "(() => { const k = nameMarkBuddyThrowFeel([0.5, 0.5, 0.9], 1.0); k.ms = 3000;"
        " let s = { x: 600, y: 700, vx: 0.3, vy: 1.9, rot: 20, t: 0, on: null, rest: false, tried: {}, came: 0 }; const rots = []; let x0 = null;"
        " for (let i = 0; i < 300 && !s.rest; i += 1) { s = nameMarkBuddyFlightStep(s, 16, W, k); if (s.roll) { rots.push(s.rot); x0 ??= s.x; } }"
        " return { rots, dx: s.x - x0, rest: s.rest, touch: s.touch, lie: s.lie || 0 }; })()"
    )
    assert out["touch"] == "roll" or out["lie"], out
    if out["touch"] == "roll":
        assert out["dx"] > 5 and out["rest"]
        assert len(out["rots"]) >= 40


@needs_node
def test_a_soft_bounce_off_a_side_is_pressed_flat_about_that_side() -> None:
    out = _run(
        "(() => { const k = nameMarkBuddyThrowFeel([0.5, 0.5, 0.9], 1.0); k.ms = 3000; const seen = [];"
        " for (const [x, vx] of [[20, -1.2], [1360, 1.2], [700, 0.3]]) {"
        "   let s = { x, y: 300, vx, vy: 0, rot: 0, t: 0, on: null, rest: false, tried: {} }; let bumps = [];"
        "   for (let i = 0; i < 30; i += 1) { s = nameMarkBuddyFlightStep(s, 16, W, k); if (s.bump) bumps.push(s.bump); }"
        "   seen.push(bumps); }"
        " return { seen, left: companionThrowLand.edgeFrames(-1, -1.2), right: companionThrowLand.edgeFrames(1, 1.2), slow: companionThrowLand.edgeFrames(1, 0.07) }; })()"
    )
    left, right, middle = out["seen"]
    assert len(left) == 1 and left[0] < 0 and len(right) == 1 and right[0] > 0 and middle == []
    # about the wall's own edge, narrower and a little taller, back to whole; a faster hit presses harder
    assert [f["transformOrigin"] for f in out["left"]["frames"]] == ["0% 50%"] * 3
    assert [f["transformOrigin"] for f in out["right"]["frames"]] == ["100% 50%"] * 3
    assert out["left"]["frames"][0]["scale"] == out["left"]["frames"][2]["scale"] == "1 1"
    w, h = (float(v) for v in out["left"]["frames"][1]["scale"].split())
    assert w == pytest.approx(0.84) and h == pytest.approx(1.08) and out["left"]["ms"] == 180
    assert float(out["slow"]["frames"][1]["scale"].split()[0]) > w


def test_the_frame_loop_squashes_a_bounce_but_leaves_a_stick_to_its_own_squash() -> None:
    from tests.test_companion_throw_fates import THROW

    assert "if (bump && !s.splat && char && typeof char.animate === \"function\")" in THROW
    assert "companionThrowLand.edgeFrames(bump, bump)" in THROW
