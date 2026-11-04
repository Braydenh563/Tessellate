"""The overlay's behaviour (BACKLOG 16, O3) on a fake clock: no Win32, no real time."""

from __future__ import annotations

import random

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Engine, Monitor

SIZE = (100, 120)
ONE = [Monitor((0, 0, 1920, 1040), 96)]


def make(monitors=None, **kw) -> tuple[Engine, list]:
    kw.setdefault("rng", random.Random(7))
    kw.setdefault("idle_frames", 0)  # these tests are about acts and moves; idle life has its own file
    kw.setdefault("home", (800, 920))
    e = Engine(SIZE, monitors or ONE, **kw)
    return e, []


def run(e: Engine, seconds: float, step: float = 0.033, t0: float = 0.0, pointer=None):
    """Drive the engine at a fixed step; returns the outputs."""
    out = []
    t = t0
    while t < t0 + seconds:
        t += step
        out.append(e.update(t, pointer))
    return out


def wakes(e: Engine, seconds: float, pointer=None) -> tuple[int, list]:
    """Follow the engine's own wake requests for `seconds`: how often it asked to run."""
    t, n, outs = 0.0, 0, []
    out = e.update(t, pointer)
    while out.wake_ms is not None and t < seconds:
        t += out.wake_ms / 1000.0
        out = e.update(t, pointer)
        outs.append(out)
        n += 1
    return n, outs


def test_starts_standing_on_the_floor_of_the_work_area() -> None:
    e, _ = make()
    out = e.update(0.1)
    assert out.frame == "stand" and out.y == 1040 - 120 and not out.click


def test_default_home_is_in_from_the_right_edge_on_the_floor() -> None:
    e = Engine(SIZE, ONE, rng=random.Random(1))
    assert e.home() == (1920 - 100 - 100, 1040 - 120)  # HOME_INSET 100: an edge spot, not the middle (INBOX 1670)
    e2 = Engine(SIZE, [Monitor((0, 0, 1920, 1040), 192)], rng=random.Random(1))
    assert e2.home()[0] == 1920 - 100 - 200  # HOME_INSET 100 at 192 dpi is 200 px (INBOX 1670: an edge spot)


def test_standing_sleeps_to_the_next_blink_or_look_not_a_fixed_tick() -> None:
    e, _ = make(roam=False)
    count, outs = wakes(e, 60)
    assert count <= 20, count
    assert {o.frame for o in outs} <= {"stand", "blink", "look"}
    assert all(o.wake_ms >= eng.MIN_WAKE_MS for o in outs if o.wake_ms)


def test_sixty_seconds_of_standing_is_at_most_twenty_wakes_for_any_seed() -> None:
    for seed in range(60):
        e, _ = make(roam=False, rng=random.Random(seed))
        assert wakes(e, 60)[0] <= 20, seed


def test_blink_and_look_appear_while_standing() -> None:
    e, _ = make(roam=False)
    # Bar moved (INBOX 1670, a settled buddy): a blink or a look comes every 25 to 45 s, so ten minutes, not one.
    _, outs = wakes(e, 600)
    frames = {o.frame for o in outs}
    assert "blink" in frames and "look" in frames


def test_walks_along_the_floor_and_cycles_twelve_frames() -> None:
    e, _ = make(rng=random.Random(3))
    e._enter("walk", 0.0)
    e.facing = 1
    outs = run(e, 3.0)
    assert {o.frame for o in outs} == {f"walk{i}" for i in range(12)}
    assert all(o.y == 1040 - 120 for o in outs)
    assert outs[-1].x > outs[0].x
    assert outs[0].wake_ms == eng.TICK_WALK_MS
    # Intent kept, measure moved (INBOX 1670: eased in, "no sudden darts"): the pace is read after
    # the ease-in, from the second half of the walk.
    half = outs[len(outs) // 2 :]
    speed = (half[-1].x - half[0].x) / (len(half) * 0.033)
    assert 50 <= speed <= 60


def test_walking_left_mirrors_the_frame_and_moves_left() -> None:
    e, _ = make()
    e._enter("walk", 0.0)
    e.facing = -1
    outs = run(e, 2.0)
    assert outs[0].flip and outs[-1].x < outs[0].x


def test_turns_around_at_the_edge_of_the_work_area_and_stays_on_screen() -> None:
    e, _ = make(home=(1800, 920))
    e._enter("walk", 0.0)
    e.state_until = 1e9
    e.facing = 1
    outs = run(e, 12.0)
    assert max(o.x for o in outs) <= 1920 - 100
    assert outs[-1].x < max(o.x for o in outs) - 20  # it came back
    assert any(o.flip for o in outs) and not all(o.flip for o in outs)
    e2, _ = make(home=(10, 920))
    e2._enter("walk", 0.0)
    e2.state_until = 1e9
    e2.facing = -1
    assert min(o.x for o in run(e2, 6.0)) >= 0


def test_dt_is_clamped_so_a_stall_never_teleports() -> None:
    e, _ = make()
    e._enter("walk", 0.0)
    e.state_until = 1e9
    e.facing = 1
    x0 = e.update(0.033).x
    x1 = e.update(600.0).x  # ten minutes later (a resume)
    assert x1 - x0 <= eng.WALK_SPEED * eng.MAX_DT + 1


def test_pointer_near_makes_it_look_and_very_near_startles() -> None:
    e, _ = make(roam=False)
    near = e.update(5.0, (e.x + 50 + 100, e.y + 60))
    assert near.frame == "look" and not near.flip  # pointer on the right: not mirrored
    e2, _ = make(roam=False)
    very = e2.update(5.0, (int(e2.x + 50 + 20), int(e2.y + 60)))
    assert very.frame == "hop"
    far = make(roam=False)[0].update(5.0, (0, 0))
    assert far.frame == "stand"


def test_it_faces_the_pointer_and_does_not_repeat_within_the_cooldown() -> None:
    e, _ = make(roam=False)
    out = e.update(5.0, (int(e.x - 40), int(e.y + 60)))
    assert out.frame == "look" and out.flip  # pointer on the left: mirrored
    e.update(7.0, (int(e.x - 40), int(e.y + 60)))  # notice over
    again = e.update(8.0, (int(e.x - 40), int(e.y + 60)))
    assert again.frame != "look" or e.notice_ready > 8.0
    assert e.notice_ready >= 5.0 + eng.NOTICE_COOLDOWN


def test_sits_then_sleeps_when_nobody_touches_it() -> None:
    e, _ = make(roam=False)
    frames = []
    t = 0.0
    out = e.update(t)
    while out.wake_ms is not None and t < 1500:
        t += out.wake_ms / 1000.0
        out = e.update(t)
        frames.append((t, out.frame))
    names = [f for _, f in frames]
    assert "sit" in names and names[-1] == "sleep"
    assert names.index("sit") < names.index("sleep")
    first_sit = next(t for t, f in frames if f == "sit")
    assert eng.IDLE_SIT <= first_sit < eng.IDLE_SIT + 5
    assert out.wake_ms in (None, eng.POLL_QUIET_MS)


def test_sleeping_costs_at_most_a_wake_every_two_seconds() -> None:
    e, _ = make()
    e._enter("sleep", 0.0)
    e.last_active = -1000.0
    count, outs = wakes(e, 60)
    assert count <= 31 and all(o.frame == "sleep" for o in outs)


def test_hovering_the_pet_wakes_it() -> None:
    e, _ = make()
    e._enter("sleep", 0.0)
    e.last_active = -1000.0
    out = e.update(1.0, event=("move", 850, 950))
    assert out.frame == "stand"


def test_click_waves_and_reports_a_left_click_then_stands() -> None:
    e, _ = make()
    e.update(1.0, event=("down", 850, 950))
    out = e.update(1.05, event=("up", 851, 951))
    assert out.click == "left" and out.frame == "wave"
    assert e.update(1.06).click is None
    assert e.update(1.05 + eng.WAVE_FOR + 0.1).frame in ("stand", "blink", "look", "walk0", "walk1", "sit")


def test_right_click_is_reported() -> None:
    e, _ = make()
    assert e.update(1.0, event=("right", 850, 950)).click == "right"


def test_press_and_move_under_four_pixels_is_still_a_click() -> None:
    e, _ = make()
    e.update(1.0, event=("down", 850, 950))
    e.update(1.01, event=("move", 853, 950))
    out = e.update(1.02, event=("up", 853, 950))
    assert out.click == "left" and out.x == 800


def test_past_four_pixels_it_is_a_drag_and_follows_the_pointer() -> None:
    e, _ = make()
    e.update(1.0, event=("down", 850, 950))
    out = e.update(1.01, event=("move", 856, 950))
    assert out.frame == "held" and out.click is None
    out = e.update(1.02, event=("move", 1000, 500))
    assert (out.x, out.y) == (1000 - 50, 500 - 30)  # kept the grab offset (50, 30)
    assert out.wake_ms == eng.TICK_WALK_MS
    up = e.update(1.03, event=("up", 1000, 500))
    assert up.click is None  # a drag is never a click


def test_let_go_in_the_air_it_falls_to_the_floor_then_lands_and_settles() -> None:
    e, _ = make()
    e.update(1.0, event=("down", 850, 950))
    e.update(1.01, event=("move", 1010, 300))
    # The pointer rests before it lets go: a slow release is a plain drop, not a
    # throw (a quick one is, since the owner's report on 2026-11-04).
    out = e.update(1.5, event=("up", 1010, 300))
    assert out.frame == "fall"
    t, ys, settled = 1.5, [], None
    while t < 4 and out.frame == "fall":
        t += 0.016
        out = e.update(t)
        ys.append(out.y)
        settled = out.settled or settled
    assert ys == sorted(ys) and out.y == 1040 - 120
    assert out.frame == "land" and out.settled
    assert out.x == 1010 - 50
    assert e.update(t + eng.LAND_FOR + 0.2).frame != "land"
    assert e.home() == (960, 920)


def test_let_go_on_the_floor_lands_without_a_fall() -> None:
    e, _ = make()
    e.update(1.0, event=("down", 850, 950))
    e.update(1.01, event=("move", 900, 950))
    out = e.update(1.02, event=("up", 900, 950))
    assert out.frame == "land" and out.settled and out.y == 1040 - 120


def test_a_drop_on_a_lower_monitor_lands_on_that_floor() -> None:
    mons = [Monitor((0, 0, 1920, 1040), 96), Monitor((1920, 100, 3840, 1180), 96)]
    e, _ = make(mons)
    e.update(1.0, event=("down", 850, 950))
    e.update(1.01, event=("move", 3000, 400))
    e.update(1.02, event=("up", 3000, 400))
    out = run(e, 3.0, step=0.016, t0=1.02)[-1]
    assert out.y == 1180 - 120 and out.x >= 1920


def test_walking_onto_a_lower_monitor_falls_and_onto_a_higher_one_hops() -> None:
    low = [Monitor((0, 0, 1920, 1040), 96), Monitor((1920, 0, 3840, 1200), 96)]
    e, _ = make(low, home=(1800, 920))
    e._enter("walk", 0.0)
    e.state_until, e.facing = 1e9, 1
    frames = {o.frame for o in run(e, 6.0, step=0.016)}
    assert "fall" in frames
    assert e.y == 1200 - 120 or e.facing == -1
    high = [Monitor((0, 0, 1920, 1040), 96), Monitor((1920, 0, 3840, 900), 96)]
    h, _ = make(high, home=(1800, 920))
    h._enter("walk", 0.0)
    h.state_until, h.facing = 1e9, 1
    outs = run(h, 6.0, step=0.016)
    assert "hop" in {o.frame for o in outs}
    assert 900 - 120 in {o.y for o in outs}


def test_walking_stops_at_the_last_monitor_not_in_the_gap_between_non_overlapping_ones() -> None:
    stacked = [Monitor((0, 0, 1920, 1040), 96), Monitor((1920, 2000, 3840, 3040), 96)]
    e, _ = make(stacked, home=(1800, 920))
    e._enter("walk", 0.0)
    e.state_until, e.facing = 1e9, 1
    assert max(o.x for o in run(e, 8.0)) <= 1920 - 100 + 60  # never crossed to the unreachable one


def test_reduced_motion_never_moves_blinks_or_asks_to_be_woken() -> None:
    e, _ = make(reduced=True)
    first = e.update(0.0)
    assert first.frame == "sit" and first.wake_ms is None
    outs = run(e, 60.0, step=1.0)
    assert {(o.x, o.y) for o in outs} == {(first.x, first.y)}
    assert {o.frame for o in outs} == {"sit"} and all(o.wake_ms is None for o in outs)
    assert e.update(61.0, pointer=(e.x + 50, e.y + 60)).frame == "sit"  # does not notice


def test_reduced_motion_still_clicks_and_carries_and_a_drop_lands_on_the_floor_at_once() -> None:
    e, _ = make(reduced=True)
    assert e.update(1.0, event=("down", 850, 950)) and e.update(1.1, event=("up", 850, 950)).click == "left"
    e.update(2.0, event=("down", 850, 950))
    e.update(2.01, event=("move", 1000, 400))
    out = e.update(2.02, event=("up", 1000, 400))
    # Owner report 2026-11-04 (b): a drop used to stay where it was let go, in mid-air.
    assert out.frame == "sit" and out.settled and out.y == e.floor_y() and out.wake_ms is None
    assert run(e, 5.0, t0=2.02)[-1].y == out.y


def test_roam_off_never_walks() -> None:
    e, _ = make(roam=False)
    assert {o.frame for o in run(e, 120.0, step=0.5)} <= {"stand", "blink", "look", "sit"}
    assert len({o.x for o in run(e, 30.0, t0=120.0, step=0.5)}) == 1


def test_a_roaming_pet_actually_moves_around_over_two_minutes(monkeypatch) -> None:
    monkeypatch.setattr(eng, "IDLE_SIT", float("inf"))  # the person is about; it would sleep after 20 minutes
    monkeypatch.setattr(eng, "IDLE_SLEEP", float("inf"))
    e, _ = make(rng=random.Random(11))
    # Intent kept, bar moved (INBOX 1670: a buddy that mostly stays by its home spot): it still
    # moves, over ten minutes now (a stroll is about one decision in seventy), not across the screen.
    outs = run(e, 21600.0, step=0.5)  # six hours: a stroll is about one decision in a hundred now
    xs = {o.x for o in outs}
    assert len(xs) > 40, len(xs)
    assert {"walk0", "stand"} <= {o.frame for o in outs}


def test_a_dpi_change_rescales_and_keeps_it_on_a_monitor() -> None:
    e, _ = make(home=(1800, 920))
    e.set_monitors([Monitor((0, 0, 1280, 720), 96)], (150, 180))
    out = e.update(1.0)
    assert out.x <= 1280 - 150 and out.y == 720 - 180


def test_resume_resets_the_clock_without_a_jump() -> None:
    e, _ = make()
    e._enter("walk", 0.0)
    e.state_until, e.facing = 1e9, 1
    x0 = e.update(1.0).x
    e.resume(5000.0)
    x1 = e.update(5000.033).x
    assert abs(x1 - x0) < 5


def test_walking_speed_scales_with_the_monitors_dpi() -> None:
    e, _ = make([Monitor((0, 0, 3840, 2080), 192)], home=(1000, 2080 - 120))
    e._enter("walk", 0.0)
    e.state_until, e.facing = 1e9, 1
    outs = run(e, 3.0)
    half = outs[len(outs) // 2 :]  # after the ease-in
    speed = (half[-1].x - half[0].x) / (len(half) * 0.033)
    assert 105 <= speed <= 120
