"""Companion catalogue B5 (`int.tickle`, `int.boop_nose`; INBOX 1696 kk): the desk figure answers a fast small rub on its
belly with a squirm and a giggle, and a tap on its face with a sneeze. Fake clock and pointer, no Win32; real Windows is
unverified. Style of `test_overlay_peek_flip_1108.py`: the engine, a path, what it said."""

from __future__ import annotations

import random

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import engine as eng  # noqa: E402
from tessellate.core.overlay import extras  # noqa: E402
from tests.test_overlay_parity_1683 import box, feed, still  # noqa: E402


def zigzag(x: int, y: int, strokes: int, swing: int, rise: int = 0) -> list[tuple[int, int]]:
    """Back and forth along x by `swing` px about `x`, drifting `rise` px in y over the whole of it."""
    return [(x + (swing if i % 2 else -swing) // 2, y + rise * i // max(1, strokes)) for i in range(strokes + 1)]


def said(e: eng.Engine, path: list[tuple[int, int]], dt: float, t: float) -> list[str]:
    feed(e, t, path, dt)
    return list(e.ex.last)


def belly(e: eng.Engine) -> tuple[int, int]:
    lx, top, r, b = box(e)
    return (lx + r) // 2, top + int(0.72 * (b - top))


def nose(e: eng.Engine) -> tuple[int, int]:
    lx, top, r, b = box(e)
    return (lx + r) // 2, top + int(0.3 * (b - top))


def test_a_fast_small_rub_on_the_body_is_a_tickle() -> None:
    e, _s, t = still()
    x, y = belly(e)
    assert "tickle" in said(e, zigzag(x, y, 10, 10), 0.1, t)
    assert e.state == "act" and e.act == "tickle_squirm"
    assert e.ex.over and e.ex.over[0] == "laughing"


def test_a_long_slow_rub_is_still_a_rub_and_not_a_tickle() -> None:
    e, _s, t = still()
    x, y = belly(e)
    heard = said(e, zigzag(x, y, 8, 50), 0.05, t)
    assert "rub" in heard and "tickle" not in heard


def test_two_strokes_or_a_stroke_on_the_head_are_not_a_tickle() -> None:
    e, _s, t = still()
    x, y = belly(e)
    assert "tickle" not in said(e, zigzag(x, y, 2, 10), 0.1, t)
    e, _s, t = still()
    nx, ny = nose(e)
    assert "tickle" not in said(e, zigzag(nx, ny, 10, 10), 0.1, t)


@pytest.mark.parametrize("seed", [1, 3, 4])
def test_a_tremor_on_the_belly_is_not_a_tickle(seed: int) -> None:
    e, _s, t = still(seed=seed)
    x, y = belly(e)
    rng = random.Random(seed)
    for _ in range(int(40 / 0.016)):
        t += 0.016
        x += rng.uniform(-2, 2)
        y += rng.uniform(-2, 2)
        e.update(t, (int(x), int(y)))
    assert "tickle" not in e.ex.last, e.ex.last


def test_a_tap_on_the_face_is_a_boop() -> None:
    e, _s, t = still()
    lx, top, r, b = box(e)
    nx, ny = nose(e)
    path = [(nx + 400, ny), (nx + 330, ny), (nx + 200, ny), (nx + 60, ny), (nx + 2, ny), (nx + 120, ny), (nx + 300, ny)]
    heard = said(e, path, 0.04, t)
    assert "boop" in heard and not {"poke_giggle", "poke_miffed", "poke_curious"} & set(heard)
    assert e.act == "boop_sneeze" and e.ex.over and e.ex.over[0] == "surprised"


def test_a_tap_on_the_body_or_the_far_side_of_the_face_is_a_poke_not_a_boop() -> None:
    e, _s, t = still()
    lx, top, r, b = box(e)
    bx, by = belly(e)
    path = [(bx + 400, by), (bx + 330, by), (bx + 200, by), (bx + 60, by), (bx + 2, by), (bx + 120, by), (bx + 300, by)]
    heard = said(e, path, 0.04, t)
    assert "boop" not in heard and {"poke_giggle", "poke_miffed", "poke_curious"} & set(heard)
    e, _s, t = still()
    lx, top, r, b = box(e)
    ex_, ey = lx + 3, top + int(0.3 * (b - top))  # the face's far edge, outside the nose
    path = [(ex_ - 400, ey), (ex_ - 330, ey), (ex_ - 200, ey), (ex_ - 60, ey), (ex_ + 2, ey), (ex_ - 120, ey), (ex_ - 300, ey)]
    assert "boop" not in said(e, path, 0.04, t)


def test_they_are_answered_in_the_catalogues_own_lengths() -> None:
    from tessellate.core.overlay import behaviour as bh

    extras.register()
    for act, (lo, hi) in {"tickle_squirm": (1.5, 3.0), "boop_sneeze": (0.8, 1.4)}.items():
        assert bh.ACTIVITIES[act].seconds == (lo, hi)
    assert extras.REACTIONS["tickle"].touch and extras.REACTIONS["boop"].touch
