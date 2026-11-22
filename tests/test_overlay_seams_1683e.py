"""INBOX 1683 (e), (i), (j): no pose pops in a seeded hour, a loop that closes, a wrap that moves by its own speed.

The wrap itself is in test_overlay_landing_1683k.py; this file measures the hour (`overlay_seams_1683e.py`)."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")
np = pytest.importorskip("numpy")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import sprites as sp  # noqa: E402
from tests.overlay_seams_1683e import hour  # noqa: E402
from tests.test_overlay_ride_1670 import make  # noqa: E402


@pytest.mark.parametrize(("gait", "seed"), [("walk", 1), ("walk", 2), ("float", 2), ("float", 3)])
def test_a_seeded_hour_has_no_pose_pop(gait: str, seed: int) -> None:
    """Before: 262 joint jumps over 4 px in six seeded hours: a landing squash of 15 to 18 px in one draw (the land state
    woke every 170 ms), an act ending in a 15 px snap (the pose ease took all of a long sleep's dt at once), and a dash's
    lean dropping 6 px when one draw moved the figure under a pixel. After: none, in a full hour, for either gait."""
    r = hour(gait, seed, 3600.0)
    assert r["jumps"] == [], r["jumps"]


def test_land_is_drawn_at_the_display_rate() -> None:
    e, _s = make("masculine", "walk", 2)
    e.state = "land"
    e.state_until = 10.0
    e.now = 1.0
    assert e._wake_state(1.0) == eng.TICK_WALK_MS


def _step(a, b) -> float:
    wa, wb = a[..., 3:] / 255, b[..., 3:] / 255
    return float(np.abs(a[..., :3] * wa - b[..., :3] * wb).mean() + np.abs(a[..., 3] - b[..., 3]).mean())


# Intent moved (INBOX 1696 hh, deskframes-1108; L150): the frames are re-shot with the tail held, so both looks wrap like
# any other step (feminine 1.9 times the median step after the L150 re-render, the bar is 3).
@pytest.mark.parametrize("look", ["masculine", "feminine"])
def test_the_idle_cycle_wraps_like_any_other_step(look: str) -> None:
    s = sp.SpriteSet(look)
    frames = [np.asarray(s._load(n)).astype(float) for n in sp.IDLE_FRAMES]
    steps = [_step(frames[i], frames[(i + 1) % len(frames)]) for i in range(len(frames))]
    assert steps[-1] <= 3.0 * float(np.median(steps[:-1])), steps


def test_a_long_sleep_does_not_snap_the_pose() -> None:
    """The class behind the act-to-stand pop: one update after a long wait eases the pose by a bounded slice, not all of it."""
    e, _s = make("masculine", "walk", 2)
    e.update(0.0)
    e.cur = eng.bh.Pose(1.04, 0.9, 0.0, 0.0)
    e.update(1.0)
    assert abs(e.cur.sy - 0.9) < 0.05 and e.cur.sy > 0.9
