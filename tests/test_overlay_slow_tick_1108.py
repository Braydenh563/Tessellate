"""INBOX 1696 (i), the owner on the desktop companion: "I pressed go somewhere else, it just stayed as it was and started
moving to the left and didnt really have any change in animation or body position or motion, but then it got halfway
across my taskbar and it just poofed back to where it was". The same screen drew a fall at about 8 frames a second
(INBOX 1696 a). A tick more than 0.1 s after the last one counted as a fresh start of the pace, so at 8 frames a second
every tick restarted the ease-in: a run crossed the taskbar at 5 px/s (the walk cycle follows the distance, so it did
not change either) and the long, slow trip was open to every timer that ends a stand. A hitch is not a stop.
Seeded engine, fixed clock; the real Windows frame rate is not measured here."""
from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tests.test_overlay_ride_1670 import make  # noqa: E402


def _distance_in(secs: float, tick: float) -> tuple[float, set[str]]:
    e, _s = make("masculine", "walk", 4)
    e.roam = True
    t = 0.0
    while t < 15.0 or e.state != "stand":
        t += 0.033
        e.update(t)
    assert e.command("wander", t)
    start, t0, frames = e.x, t, set()
    while t - t0 < secs:
        t += tick
        out = e.update(t)
        if e.state == "walk":
            frames.add(out.frame)
    return abs(e.x - start), frames


@pytest.mark.parametrize("tick", [0.12, 0.2, 0.3])
def test_a_slow_draw_rate_does_not_restart_the_pace_every_tick(tick: float) -> None:
    fast, _fr = _distance_in(10.0, 0.033)
    slow, frames = _distance_in(10.0, tick)
    assert fast > 300
    # the world step is clamped to 0.1 s a tick, so a slow draw rate is slower, but never a crawl (before: 0.03 of it)
    assert slow > 0.3 * fast, (tick, slow, fast)
    assert len({f for f in frames if f.startswith("walk")}) >= 4  # the walk cycle shows


@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_go_somewhere_else_is_seen_arrives_and_stays_at_ten_frames_a_second(gait: str, seed: int) -> None:
    """Walk frames while it travels on foot, a seen move for a floater, facing the way it goes, arrived and still there a
    minute on (the old spot is not home any more)."""
    e, _s = make("feminine", gait, seed)
    e.roam = True
    t = 0.0
    while t < 15.0 or e.state != "stand":
        t += 0.033
        e.update(t)
    old = e.x
    assert e.command("wander", t)
    new, t0, blank, faced = e.home_x, t, 0, set()
    while t - t0 < 100.0:
        t += 0.1
        out = e.update(t)
        if e.state == "walk" and gait == "walk" and e.goal is not None and abs(e.goal[0] - e.x) > 20:
            faced.add(e.facing * (1 if e.goal[0] > e.x else -1))  # toward where it is going, even to an edge it slips off
            # Intent moved (INBOX 1683 u, hops): a hop-chain leg draws the tucked hop picture while it is in the air.
            blank += not (out.frame.startswith("walk") or (e.hopping and out.frame == "hop"))
        if t - t0 > 60.0:
            assert abs(e.x - new) < 60 * e._scale() and abs(e.x - old) > 100, (t - t0, e.x, new, old)
    assert blank == 0
    assert faced <= {1}, faced  # never walking backwards (a turn may pass through 0)
