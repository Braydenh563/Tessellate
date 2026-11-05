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


@pytest.mark.parametrize("gait", ["walk", "float"])
def test_a_seeded_hour_has_no_landing_pop_and_few_pose_jumps(gait: str) -> None:
    """Before: 262 joint jumps over 4 px in six seeded hours, two of them a landing squash of 15 to 18 px in one draw
    (the land state woke every 170 ms, so the 60 Hz ease became a snap). After: no landing jump, a handful of 4 to 6 px
    steps at a start of travel."""
    r = hour(gait, 1, 1800.0)
    assert not [j for j in r["jumps"] if j[1] == "land" or j[2] == "land"], r["jumps"]
    assert len(r["jumps"]) <= 8, r["jumps"]


def test_land_is_drawn_at_the_display_rate() -> None:
    e, _s = make("masculine", "walk", 2)
    e.state = "land"
    e.state_until = 10.0
    e.now = 1.0
    assert e._wake_state(1.0) == eng.TICK_WALK_MS


def _step(a, b) -> float:
    wa, wb = a[..., 3:] / 255, b[..., 3:] / 255
    return float(np.abs(a[..., :3] * wa - b[..., :3] * wb).mean() + np.abs(a[..., 3] - b[..., 3]).mean())


@pytest.mark.xfail(strict=True, reason="the shipped idle frames were captured with the live tail loop running over the sample; "
                   "scripts/render_desk_frames.js now holds it, but the frames are not re-shot yet (wrap step 8x the median)")
@pytest.mark.parametrize("look", ["masculine", "feminine"])
def test_the_idle_cycle_wraps_like_any_other_step(look: str) -> None:
    s = sp.SpriteSet(look)
    frames = [np.asarray(s._load(n)).astype(float) for n in sp.IDLE_FRAMES]
    steps = [_step(frames[i], frames[(i + 1) % len(frames)]) for i in range(len(frames))]
    assert steps[-1] <= 3.0 * float(np.median(steps[:-1])), steps
