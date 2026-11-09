"""INBOX 1670, 16:40Z: "the atlas desktop companion when it is idle doesnt really have any animation or subtle
movement to it at all and it randomly jitters up and down. I want it to feel alive like the regular companion and
be more natural and biological". Seven findings, each measured on the engine and its fakes with a fixed clock
(nothing here ran on Windows). Before, on the tree this started from (seed 22, floater, 900 s unless said):

1. the window sat up to 4 px off its place in the air (bob) and 2 px sideways (sway): 4 distinct rows, 905 to 908;
2. the feminine wave drew its box bottom 134 against the stand's 130: a 3 px hop at its entry;
3. the feminine idle bottom stepped 258, 260, 259, 261 source px (3 px) at idle18 and at the wrap;
4. a look held the look picture 1.2 s while the cycle ran on, then snapped to another idle picture;
5. a sit never blinked;
6. blinks came every 3 to 7 s, evenly, never doubled;
7. a sit's tail sway was exactly twice the breath's period: the pair repeated every 9.6 s."""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest
from PIL import Image

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import runner as runner_mod
from tessellate.core.overlay import sprites
from tests.overlay_restlife_1670 import rest_life
from tests.overlay_sim_1670 import skip_flow
from tests.test_overlay_ride_1670 import make

LOOKS = ("masculine", "feminine")
DESK = Path(__file__).resolve().parent.parent / "frontend" / "img" / "desk"


def run_floater(look: str, seed: int, secs: float) -> tuple[float, float, int]:
    """The largest distance the drawn window is from where the engine keeps the figure, in each axis, and the
    distinct rows the window took: stand, drift, act, whatever the hour brings."""
    e, _s = make(look, "float", seed)
    e.big_ready = e.trip_ready = e.climb_ready = math.inf
    t, out, dxs, dys, rows = 0.0, e.update(0.0), 0.0, 0.0, set()
    while t < secs:
        t += min(max(0.016, (out.wake_ms or 1000) / 1000.0), 1.0)
        out = e.update(t)
        if out.clip is not None or e.state in ("peek", "emerge", "hang", "rise", "warp"):
            continue
        dys = max(dys, abs(out.y - (e.y + e._dy(out.frame))))
        dxs = max(dxs, abs(out.x - (e.x + e._flip_dx(out.frame, out.flip))))
        rows.add(out.y)
    return dxs, dys, len(rows)


@pytest.mark.parametrize("look", LOOKS)
def test_1_the_window_is_never_off_its_place_in_the_air(look: str) -> None:
    dx, dy, rows = run_floater(look, 22, 900.0)
    print(look, "offset from the engine's place:", dx, dy, "rows", rows)
    assert dy <= 0.5 and dx <= 0.5, (dx, dy)  # was 4 and 2 px (the bob and the sway)


@pytest.mark.parametrize("look", LOOKS)
def test_1_a_drifting_floater_breathes_in_the_figure(look: str) -> None:
    e, _s = make(look, "float", 5, plain=True)
    e._enter("drift", 0.0)
    e.goal, e.trip, e.state_until = (e.x + 600.0, e.y), True, math.inf
    sy = []
    for i in range(1, 400):
        o = e.update(i / 60.0)
        if o.pose:
            sy.append(o.pose[1])
    assert max(sy) - min(sy) >= 0.008, (min(sy), max(sy))


@pytest.mark.parametrize("look", LOOKS)
def test_2_the_wave_is_drawn_on_the_stands_line(look: str) -> None:
    e, _s = make(look, "float")
    assert e._dy("wave") == e._dy("stand") == e._dy("idle3") == e._dy("walk4")  # was 16 against 19 for the feminine wave


@pytest.mark.parametrize("look", LOOKS)
def test_3_the_idle_cycle_bottom_stays_within_one_source_pixel(look: str) -> None:
    def bottom(name: str) -> int:
        alpha = Image.open(DESK / look / f"{name}.png").convert("RGBA").getchannel("A").point(lambda v: 255 if v >= 24 else 0)
        return alpha.getbbox()[3]

    rows = [bottom(f"idle{i}") for i in range(sprites.IDLE_COUNT)]
    # the feminine was the finding (258 to 261); the masculine cycle was already within 2 and was not touched
    bound = 1 if look == "feminine" else 2
    assert max(rows) - min(rows) <= bound and abs(max(rows) - bottom("stand")) <= bound, rows


def test_4_a_look_resumes_the_cycle_where_it_paused() -> None:
    e, _s = make("masculine", "float", 3)
    e.big_ready = e.trip_ready = e.climb_ready = math.inf
    e.state_until = math.inf
    t0 = 10.03
    e.update(t0)
    before = e._idle_index(t0)
    e.flash = ("look", t0 + eng.LOOK_FOR)
    e.next_ambient = math.inf
    mid = e.update(t0 + 0.6)
    assert mid.frame == "look"
    end = e.update(t0 + eng.LOOK_FOR + 0.004)
    assert end.frame == f"idle{before}", (end.frame, before)  # was a different picture: the cycle ran on under it


def test_4_the_head_turn_is_a_slow_dissolve_in_and_out() -> None:
    from tests.test_overlay_runner import make as make_runner

    assert "look" in runner_mod.BLENDED and "blink" not in runner_mod.BLENDED
    assert runner_mod.BLEND_LOOK_S >= 2 * runner_mod.BLEND_S
    r, fake, clock, _c, _s = make_runner()
    assert r.start()
    r.show()
    time.sleep(0.2)
    out = r.engine.update(clock.t)
    idle = out._replace(frame="idle3", pose=None, fx=None, clip=None, flip=False, alpha=1.0, wake_ms=None)
    r._apply(idle)
    before = len(fake.layered)
    r._apply(idle._replace(frame="look"))
    for _ in range(25):
        clock.t += 0.0167
        r._apply(idle._replace(frame="look"))
    time.sleep(0.15)
    draws = len(fake.layered) - before
    print("look dissolve draws:", draws)
    assert 6 <= draws <= 10  # BLEND_STEPS steps and the picture, over BLEND_LOOK_S
    r.stop()


def blink_starts(state: str, seed: int, secs: float) -> list[float]:
    e, _s = make("masculine", "float", seed)
    skip_flow(e)  # this reads blink starts, never the flow picture
    e.big_ready = e.trip_ready = e.climb_ready = math.inf
    saved = eng.IDLE_SIT, eng.IDLE_SLEEP
    eng.IDLE_SIT = eng.IDLE_SLEEP = math.inf
    try:
        e.update(0.0)
        if state != "stand":
            e._enter(state, 0.0)
        e.state_until = math.inf
        e.next_ambient = 1.0
        starts, t, was = [], 0.0, False
        while t < secs:
            t += 0.05
            e.update(t)
            on = bool(e.flash) and e.flash[0] == "blink"
            if on and not was:
                starts.append(t)
            was = on
        return starts
    finally:
        eng.IDLE_SIT, eng.IDLE_SLEEP = saved


def test_5_a_sit_blinks_with_its_lids_and_a_sleep_does_not() -> None:
    e, _s = make("masculine", "float", 4)
    e.big_ready = e.trip_ready = e.climb_ready = math.inf
    e._enter("sit", 0.0)
    e.state_until = math.inf
    e.next_ambient = 0.5
    seen = set()
    for i in range(1, 1500):
        seen.add(e.update(i * 0.05).frame)
    assert seen == {"sit", "sitblink"}, seen
    e._enter("sleep", 100.0)
    frames = {e.update(100.0 + i * 0.05).frame for i in range(1, 400)}
    assert frames == {"sleep"}  # its eyes are shut already


@pytest.mark.parametrize("look", LOOKS)
def test_5_the_lids_are_drawn_over_the_eyes_and_nothing_else_moves(look: str) -> None:
    s = sprites.SpriteSet(look)
    sit, lid = s.frame("sit", 96), s.frame("sitblink", 96)
    assert (sit.width, sit.height, sit.pad_x, sit.pad_y) == (lid.width, lid.height, lid.pad_x, lid.pad_y)
    changed = [i for i in range(0, len(sit.bgra), 4) if sit.bgra[i:i + 4] != lid.bgra[i:i + 4]]
    rows = {(i // 4) // sit.width for i in changed}
    assert 150 <= len(changed) <= 2500, len(changed)  # the eyes only
    assert max(rows) - min(rows) <= 20, (min(rows), max(rows))
    assert sit.box[3] == lid.box[3]  # the feet stay where they were
    assert ("sitblink", False) in s.metrics(96)


def test_6_blinks_are_irregular_two_to_seven_seconds_with_the_odd_double() -> None:
    starts = [t for seed in (1, 2, 3) for t in [blink_starts("stand", seed, 3000.0)]]
    gaps = [b - a for s in starts for a, b in zip(s, s[1:])]
    doubles = [g for g in gaps if g < 1.0]
    regular = [g for g in gaps if g >= 1.0]
    share = len(doubles) / len(gaps)
    print(f"blinks {len(gaps)}, regular gaps {min(regular):.2f} to {max(regular):.2f}, mean {sum(regular) / len(regular):.2f}, doubles {share:.1%}")
    # a gap longer than 7 s is a look, a wave or a walk between two blinks, so the window is read on the bulk
    inside = [g for g in regular if g <= 7.2]
    assert min(regular) >= 1.9, min(regular)  # was 3 to 7
    assert len(inside) / len(regular) >= 0.7 and max(inside) - min(inside) > 4.0, (len(inside), len(regular))
    assert 0.06 <= share <= 0.22, share  # an occasional double
    assert all(g <= 0.45 for g in doubles)
    spread = {round(g) for g in regular}
    assert len(spread) >= 5, spread  # not one rhythm


def test_6_a_sit_blinks_at_about_the_same_pace() -> None:
    starts = blink_starts("sit", 2, 600.0)
    assert 90 <= len(starts) <= 260, len(starts)


@pytest.mark.parametrize("state", ["sit", "sleep"])
def test_7_the_tail_never_repeats_with_the_breath(state: str) -> None:
    e, _s = make("masculine", "float", 2)
    e._enter(state, 0.0)
    life = eng.REST_LIFE[state]
    breath, _d, sway, sway_s = life
    assert abs(sway_s / breath - 2.0) > 0.1  # no longer exactly twice the breath
    series = [e._rest_tail(i * 0.1, life) for i in range(0, 6000)]  # ten minutes
    amp = max(abs(v) for v in series)
    assert amp <= 1.6 * sway * e._scale() + 1e-9
    # no whole number of breaths brings it back: the best repeat over the first 40 breaths is still a clear miss
    worst = min(
        math.sqrt(sum((series[i] - series[i + int(k * breath * 10)]) ** 2 for i in range(0, 800)) / 800)
        for k in range(1, 40)
    )
    print(state, "best repeat error", round(worst, 3), "of amplitude", round(amp, 3))
    assert worst > 0.08 * amp, worst  # was 0.000 at 2 breaths (9.6 s)
    # it trails the body: the tail's late term is the breath a beat behind
    assert eng.TAIL_LAG > 0 and 0 < eng.TAIL_WANDER < 0.3


@pytest.mark.parametrize("state", ["stand", "sit", "sleep"])
def test_7_rest_stays_alive_in_place_under_the_redraw_cap(state: str) -> None:
    m = rest_life("float", "masculine", state, 2)
    print(state, {k: round(v, 1) if isinstance(v, float) else v for k, v in m.items()})
    assert m["moves"] == 0 and m["max_draws_a_second"] <= 12
    assert m["draws"] >= {"stand": 300, "sit": 100, "sleep": 70}[state], m
