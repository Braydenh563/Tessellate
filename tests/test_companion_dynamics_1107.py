"""Research A2: the pose follows its target by second-order dynamics (frequency, damping, response), not a plain
first-order lag: a squash can overshoot a little and settle, a lean can anticipate, and neither goes unstable on a
long frame. Fixed clock, no Win32."""

from __future__ import annotations

import random

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import engine as eng

ONE = [eng.Monitor((0, 0, 1920, 1040), 96)]


def run(so: bh.SecondOrder, target: float, seconds: float, dt: float = 1 / 60) -> list[float]:
    out = []
    for _ in range(int(seconds / dt)):
        out.append(so.step(dt, target))
    return out


def test_an_underdamped_response_overshoots_and_a_critical_one_does_not() -> None:
    low = run(bh.SecondOrder(2.0, 0.5, 0.0, 0.0), 1.0, 3.0)
    assert 1.10 < max(low) < 1.25 and abs(low[-1] - 1.0) < 0.01  # about 16% for a damping of one half
    crit = run(bh.SecondOrder(2.0, 1.0, 0.0, 0.0), 1.0, 3.0)
    assert max(crit) <= 1.0 + 1e-6 and abs(crit[-1] - 1.0) < 0.01


def test_a_negative_response_starts_by_going_the_other_way() -> None:
    ahead = run(bh.SecondOrder(2.0, 0.8, -0.6, 0.0), 1.0, 0.3)
    assert min(ahead) < -0.005  # anticipation: a small step back before the move
    plain = run(bh.SecondOrder(2.0, 0.8, 0.0, 0.0), 1.0, 0.3)
    assert min(plain) >= 0.0


def test_it_stays_finite_on_a_long_frame_and_does_not_move_on_none() -> None:
    so = bh.SecondOrder(6.0, 0.4, 0.0, 0.0)
    for dt in (1.0, 5.0, 0.0, 1e-4):
        y = so.step(dt, 1.0)
        assert abs(y) < 10.0
    still = bh.SecondOrder(3.0, 0.7, 0.0, 0.25)
    assert still.step(0.0, 9.0) == 0.25


def make() -> eng.Engine:
    e = eng.Engine((100, 120), ONE, rng=random.Random(3), home=(800, 920))
    e.update(0.1)
    return e


def test_the_body_pose_reaches_a_new_target_quickly_overshoots_a_little_and_settles() -> None:
    e = make()
    goal = bh.Pose(0.8, 1.2, 0.05, 0.0)
    e._target_pose = lambda now: goal  # type: ignore[method-assign]
    t, series = 1.0, []
    for _ in range(90):
        e._follow_through(t, 1 / 60)
        series.append(e.cur)
        t += 1 / 60
    assert abs(series[20].sy - 1.2) < 0.04  # within a third of a second, as the first-order lag was
    assert max(p.sy for p in series) < 1.2 * 1.08  # an overshoot, a small one
    assert abs(series[-1].sy - 1.2) < 0.006 and abs(series[-1].lean - 0.05) < 0.006
    assert not e._follow_moving()


def test_a_long_gap_between_draws_is_still_eased_not_jumped() -> None:
    e = make()
    e._target_pose = lambda now: bh.Pose(0.5, 1.5, 0.0, 0.0)  # type: ignore[method-assign]
    e._follow_through(50.0, 5.0)  # a draw after a long rest
    assert abs(e.cur.sy - 1.0) < 0.2
