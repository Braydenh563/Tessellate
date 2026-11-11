"""E3 (INBOX 1719 b), the desk side: micro-saccades in a held gaze, and a stand's breath that follows the mood and the walk. Fixed clock,
seeded streams, the shipped frames; nothing here reads real time."""

from __future__ import annotations

import math
import random

import pytest

from tessellate.core.overlay import engine_consts as eng
from tessellate.core.overlay import faces, gaze, standing
from tessellate.core.overlay.sprites import SpriteSet
from tests.test_overlay_life_1670 import calm
from tests.test_overlay_ride_1670 import make

pytest.importorskip("PIL")


# --- the scheduler -------------------------------------------------------------------------------------------


def _run(seed: int, seconds: float, attending) -> list[tuple[float, int | None]]:
    s = gaze.Saccade(random.Random(seed))
    out, t = [], 0.0
    while t < seconds:
        t += 0.05
        out.append((round(t, 3), s.tick(t, attending(t))))
    return out


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_a_held_gaze_steps_every_point_six_to_one_point_eight_seconds(seed: int) -> None:
    rows = _run(seed, 120.0, lambda t: True)
    changes = [(t, v) for (t, v), (_t0, v0) in zip(rows[1:], rows) if v != v0]
    gaps = [b[0] - a[0] for a, b in zip(changes, changes[1:])]
    assert 60 <= len(changes) <= 200  # about one every 1.2 s
    assert min(gaps) >= gaze.STEP_EVERY[0] - 0.06 and max(gaps) <= gaze.STEP_EVERY[1] + 0.06  # a tick of slack
    assert changes[0][0] <= gaze.STEP_EVERY[1] + 0.1 and rows[0][1] is None  # the first step is not at once, and is soon
    assert all(v is not None and 0 <= v < len(faces.GAZE) for _t, v in changes)  # always a place of the table, never the one it was on
    assert len({v for _t, v in changes}) == len(faces.GAZE)  # every place is used


def test_the_gaze_is_let_go_when_attention_ends_and_starts_fresh() -> None:
    rows = _run(3, 40.0, lambda t: t < 10.0 or t >= 20.0)
    assert all(v is None for t, v in rows if 10.0 <= t < 20.0)
    assert any(v is not None for t, v in rows if 5.0 <= t < 10.0)
    assert all(v is None for t, v in rows if 20.0 <= t < 20.5)  # no step the moment a gaze begins


def test_a_seed_gives_the_same_steps_and_two_seeds_differ() -> None:
    assert _run(5, 30.0, lambda t: True) == _run(5, 30.0, lambda t: True)
    assert _run(5, 30.0, lambda t: True) != _run(6, 30.0, lambda t: True)


def test_the_attending_acts_are_the_ones_drawn_on_the_look_frame() -> None:
    assert {"look_around", "glance_pointer", "ponder", "scan_horizon", "peer_at_cursor", "peek_down"} <= gaze.ATTEND_ACTS
    assert not {"breathe", "stretch", "yawn", "wave_idle"} & gaze.ATTEND_ACTS
    assert gaze.worn(None, None) is None and gaze.worn(("smile", 2), None) == ("smile", 2)
    assert gaze.worn(None, 3) == ("gaze~3", 3) and gaze.worn(("smile", 2), 3) == ("smile~3", 2)


# --- the drawing ---------------------------------------------------------------------------------------------


def _eye_ink(s: SpriteSet, base, face: tuple[str, int], side: int) -> tuple[float, float, float]:
    """The dark mass of one eye (its centroid in shipped px, and its weight): the iris the art draws."""
    from PIL import Image

    out = faces.draw(s, "stand", base, False, None, face, base)
    cx, cy, k = faces.head_point(s, "stand", base, False, None)
    im = Image.frombytes("RGBA", (out.width, out.height), out.bgra, "raw", "BGRa").convert("L").load()
    ex, n, sx, sy = cx + side * faces.EYE_GAP * k, 0.0, 0.0, 0.0
    for y in range(int(cy - 7 * k), int(cy + 7 * k)):
        for x in range(int(ex - 8 * k), int(ex + 8 * k)):
            w = max(0, 60 - im[x, y])
            n, sx, sy = n + w, sx + w * x, sy + w * y
    return sx / n / k, sy / n / k, n


@pytest.mark.parametrize("look", ["masculine", "feminine"])
def test_a_gaze_step_moves_each_iris_by_its_table_entry_and_nothing_else_of_the_eye(look: str) -> None:
    s = SpriteSet(look)
    base = s.frame("stand", 300, False)
    for side in (-1, 1):
        x0, y0, w0 = _eye_ink(s, base, ("gaze", 3), side)  # the eyes alone, no step: the baseline
        for i, (gx, gy) in enumerate(faces.GAZE):
            x, y, w = _eye_ink(s, base, (f"gaze~{i}", 3), side)
            assert (x - x0, y - y0) == pytest.approx((gx, gy), abs=0.12), (look, side, i)  # measured: within 0.07 px
            assert w == pytest.approx(w0, rel=0.02)  # the same iris, moved: no ghost left behind and none lost


def _mouth_rows(base, k: float, cy: float) -> tuple[int, int]:
    return (int(cy + (faces.MOUTH_DOWN - 4) * k) * base.width * 4, int(cy + (faces.MOUTH_DOWN + 6) * k) * base.width * 4)


def test_a_gaze_step_leaves_the_mouth_and_the_rest_of_the_face_alone() -> None:
    s = SpriteSet("feminine")
    base = s.frame("stand", 300, False)
    a = faces.draw(s, "stand", base, False, None, ("gaze", 3), base).bgra
    b = faces.draw(s, "stand", base, False, None, ("gaze~1", 3), base).bgra
    cx, cy, k = faces.head_point(s, "stand", base, False, None)
    m0, m1 = _mouth_rows(base, k, cy)
    assert a[m0:m1] == b[m0:m1]
    assert a != b


def test_an_expression_keeps_its_face_while_the_eyes_step() -> None:
    s = SpriteSet("masculine")
    base = s.frame("stand", 300, False)
    plain = faces.draw(s, "stand", base, False, None, ("smile", 3), base).bgra
    stepped = faces.draw(s, "stand", base, False, None, ("smile~1", 3), base).bgra
    lidded = faces.draw(s, "stand", base, False, None, ("smile~1|2", 3), base).bgra
    assert plain != stepped != lidded
    cx, cy, k = faces.head_point(s, "stand", base, False, None)
    m0, m1 = _mouth_rows(base, k, cy)
    assert plain[m0:m1] == stepped[m0:m1] == lidded[m0:m1]  # the smile is where it was
    assert faces.draw(s, "stand", base, False, None, ("smile~99", 3), base).bgra == plain  # a step off the table is none


# --- the engine ----------------------------------------------------------------------------------------------


def _faces_over(e, seconds: float, t: float = 0.0) -> list[tuple[float, tuple[str, int] | None]]:
    out = []
    end = t + seconds
    while t < end:
        t += 0.05
        out.append((t, e.update(t).face))
    return out


def _still(seed: int):
    e, _s = make("masculine", "float", seed=seed, plain=True)
    calm(e)
    e._enter("stand", 0.0)
    e.state_until = math.inf
    e.next_ambient = math.inf
    e.last_active = math.inf
    e.ex.act_ready = math.inf
    e.mind.needs = {"rest": 0, "curiosity": 0, "play": 0}
    return e


@pytest.mark.parametrize("act", ["ponder", "look_around", "peer_at_cursor"])
def test_an_act_that_looks_takes_small_steps_with_its_eyes(act: str) -> None:
    e = _still(2)
    e._start_act(act, 0.0)
    e.act_len = 12.0
    e.state_until = 12.0
    rows = _faces_over(e, 11.0)
    steps = [f[0].split("|")[0] for _t, f in rows if f and "~" in f[0]]
    assert len(set(steps)) >= 3, (act, steps[:4])  # several places within 11 s
    assert all(s.split("~")[1].isdigit() and int(s.split("~")[1]) < len(faces.GAZE) for s in steps)


def test_a_calm_stand_draws_no_gaze_steps_and_a_held_look_does() -> None:
    e = _still(4)
    assert not [1 for _t, f in _faces_over(e, 60.0) if f and "~" in f[0]]  # nothing looked at: the eyes stay as drawn
    e2 = _still(4)
    e2.flash = ("look", 30.0)
    assert any(f and f[0].startswith("gaze~") for _t, f in _faces_over(e2, 25.0))  # a held look (no expression) is the eyes alone


def test_a_blink_in_a_held_gaze_draws_the_lid_over_the_stepped_eye() -> None:
    e = _still(4)
    assert e._blink_face(0.0, "stand", ("gaze~2", 3)) == ("gaze~2", 3)  # no blink on: unchanged
    e.flash = ("blink", 0.1)
    e.blink_for = 0.28
    f = e._blink_face(0.0, "stand", ("gaze~2", 3))
    assert f is not None and f[0].startswith("gaze~2|")


# --- the stand's breath follows the mood and the walk --------------------------------------------------------


def _cycle_lengths(e, start: float, n: int = 8) -> list[float]:
    out, t = [], start
    for _ in range(n):
        s, length = e._idle_cycle(t + 0.01)
        out.append(length)
        t = s + length
    return out


def test_a_stand_after_a_walk_breathes_quicker_and_eases_back() -> None:
    quiet = _still(3)
    quiet.update(0.0)
    base = sum(_cycle_lengths(quiet, 0.0)) / 8
    tired = _still(3)
    tired.exerted_at = 0.0  # it has just walked
    tired.update(0.0)
    fast = _cycle_lengths(tired, 0.0, 12)
    assert sum(fast[:2]) / 2 <= base * 0.93  # quicker straight after
    assert sum(fast[-2:]) / 2 > sum(fast[:2]) / 2  # and easing back as the exertion fades (half-life 14 s)
    assert min(fast) >= standing.STAND_BREATH[0] * 4.0 / (1.0 + eng.IDLE_SPREAD) - 1e-6  # never faster than the clamp


def test_a_sleepy_stand_breathes_slower_and_the_clamp_holds() -> None:
    e = _still(3)
    e.mind.needs = {"rest": 1.0, "curiosity": 0, "play": 0}
    e.update(0.0)
    lens = _cycle_lengths(e, 0.0)
    assert sum(lens) / len(lens) >= 4.0 * 1.1
    assert max(lens) <= 4.0 * standing.STAND_BREATH[1] / (1.0 - eng.IDLE_SLOWEST) + 1e-6


def test_the_stand_breath_draws_nothing_new_from_the_random_streams() -> None:
    # The breath scale is read, not drawn: two engines that differ only in exertion keep the same idle_rng sequence.
    a, b = _still(5), _still(5)
    b.exerted_at = 0.0
    a.update(0.0)
    b.update(0.0)
    _cycle_lengths(a, 0.0, 6)
    _cycle_lengths(b, 0.0, 6)
    assert a.idle_rng.getstate() == b.idle_rng.getstate()


def test_the_idle_cycle_still_plays_every_picture_when_it_runs_quick() -> None:
    e = _still(3)
    e.exerted_at = 0.0
    seen, t = set(), 0.0
    while t < 20.0:
        t += 1 / 30
        o = e.update(t)
        if o.frame.startswith("idle"):
            seen.add(o.frame)
    assert len(seen) == e.idle_frames
