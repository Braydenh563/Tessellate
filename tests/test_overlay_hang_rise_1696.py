"""A floater's way up to a hang is a seen move, and a hang lasts minutes (INBOX 1696 b, owner: the rise to the top
"just slides up" in the standing picture "and stops part way"). Before: a floater's hang trip was any leg mode, most
often a glide or a swoop, which a drift draws in the idle frames (the stand picture sliding up the screen), and a
drift waits under a busy pointer (`_yields`), so it stopped part way when the pointer was near; a hang lasted 30 to
200 s. Now the trip up is a blink or a cloud ride (never waiting on the pointer), and a hang lasts one to eight
minutes by mood. Fixed clock throughout."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import behaviour as bh  # noqa: E402
from tessellate.core.overlay import engine as eng  # noqa: E402
from tests.test_overlay_ride_1670 import make  # noqa: E402

STEP = 0.033


@pytest.mark.parametrize("look", ["feminine", "masculine"])
def test_a_floaters_trip_up_to_a_hang_is_a_blink_or_a_cloud_and_it_gets_there(look: str) -> None:
    kinds = []
    for seed in range(1, 21):
        e, _s = make(look, "float", seed)
        t = 1.0
        e.update(t)
        e._perform("hang", t)
        assert e.state == "warp", (seed, e.state, e.modes[-2:])  # before: a crouch and a drift most seeds
        kinds.append(e.warp["kind"])
        states = set()
        for i in range(int(6 / STEP)):
            t += STEP
            # the pointer busy right where it goes: a drift waited under it, part way up
            e.update(t, (int(e.x + e.size[0] / 2 + (i % 5) * 7), int(e.y + e.size[1] / 2)))
            states.add(e.state)
            if e.state == "hang":
                break
        assert e.state == "hang", (seed, e.state, states)
        assert states <= {"warp", "hang"}, (seed, states)  # never a drift (the slide) on the way
    assert set(kinds) == {"blink", "cloud"}


def test_a_hang_lasts_minutes_and_longer_when_curious_or_bored() -> None:
    for mood, (lo, hi) in bh.HANG_BY_MOOD.items():
        assert lo >= 60.0 and hi >= 2 * lo and hi <= 480.0, mood
    assert bh.HANG_BY_MOOD["sleepy"][1] < bh.HANG_BY_MOOD["bored"][1]
    assert eng.HANG_FOR[0] >= 60.0 and eng.HANG_FOR[1] >= max(hi for _lo, hi in bh.HANG_BY_MOOD.values())
