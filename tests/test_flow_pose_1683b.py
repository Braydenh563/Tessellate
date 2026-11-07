"""Desk companion: the wisps and streams by pose (INBOX 1683 B1, B3: "they dont even ahve different variations or
change based on body position"). Fixed clock: every time here is passed in, nothing reads the real one."""

from __future__ import annotations

from tessellate.core.overlay import behaviour as bh


def series(frame: str, seconds: float = 20.0, step: float = 1 / 25, calm: bool = False):
    flow = bh.Flow()
    out = []
    for k in range(int(seconds / step)):
        out.append(flow.view(100.0 + k * step, calm=calm, frame=frame))
    return out


def test_a_view_without_a_frame_is_the_bare_flow() -> None:
    flow = bh.Flow()
    assert flow.view(10.0) == flow.view(10.0) == bh.Flow().view(10.0)
    assert bh.Flow().view(10.0, frame="") == bh.Flow().view(10.0)


def test_arrangements_differ_by_strand_and_change_over_time() -> None:
    flow = bh.Flow()
    held = {round(flow.arrangement(0, 100.0 + k * 0.5)[0], 2) for k in range(40)}
    assert len(held) >= 4, "several arrangements in twenty seconds, not a loop"
    first = [flow.arrangement(i, 50.0) for i in range(bh.FLOW_BANDS)]
    assert len(set(first)) == bh.FLOW_BANDS, "no two strands hold the same one"
    assert flow.arrangement(2, 77.3) == flow.arrangement(2, 77.3)
    assert all(abs(v) <= 1.0 for i in range(bh.FLOW_BANDS) for t in range(0, 60, 3) for v in flow.arrangement(i, float(t)))


def test_each_pose_shows_at_least_three_arrangements_of_a_strand_in_twenty_seconds() -> None:
    for frame in ("sit", "sleep", "hang", "stand", "idle3", "walk4", "wave"):
        tips = {v[0] // 3 for v in series(frame)}
        assert len(tips) >= 6, (frame, len(tips))


def test_the_pose_changes_the_reach_and_the_speed_not_just_the_arrangement() -> None:
    def spread(frame: str) -> int:
        tips = [v[0] for v in series(frame, 60.0, 0.2)]
        return max(tips) - min(tips)

    assert spread("sleep") < spread("sit") < spread("walk0") + 1
    assert spread("sleep") <= 0.6 * spread("hop")


def test_changing_pose_is_never_a_step() -> None:
    # A step between two reads a frame apart, in px of the shipped frame, no larger than the ordinary steps within a pose.
    step = 1 / 25
    flow = bh.Flow()
    reads = []
    for k in range(500):
        frame = "stand" if k < 250 else "sleep"
        reads.append(flow.view(10.0 + k * step, frame=frame))
    jumps = [max(abs(a - b) for a, b in zip(x, y)) for x, y in zip(reads, reads[1:])]
    ordinary = max(jumps[:240])
    assert max(jumps[240:300]) <= ordinary + 1, (max(jumps[240:300]), ordinary)


def test_the_tip_stays_inside_the_four_degrees_the_join_allows() -> None:
    limit = round((bh.FLOW_TIP * bh.FLOW_ARR_SWAY + bh.FLOW_ARR_TIP) * bh.FLOW_Q) + 1
    for frame in ("sit", "sleep", "hang", "stand", "walk2"):
        assert max(abs(v[k]) for v in series(frame, 120.0, 0.25) for k in range(0, 5 * bh.FLOW_BANDS, 5)) <= limit, frame


def test_reduced_motion_keeps_it_slow_and_small() -> None:
    limit = round((bh.FLOW_TIP * bh.FLOW_CALM_AMP * bh.FLOW_ARR_SWAY + bh.FLOW_ARR_TIP * bh.FLOW_CALM_AMP) * bh.FLOW_Q) + 1
    assert max(abs(v[0]) for v in series("sit", 60.0, 0.25, calm=True)) <= limit
