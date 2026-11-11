"""The desk companion is squashed against a wall it touches (E6, companion-asks N5): a bounce for a moment, a slide held
flat against it. Fixed 60 Hz clock, seeded; the picture is measured in pixels (the narrowing about the wall edge)."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import landing as ld  # noqa: E402
from tessellate.core.overlay import sprites  # noqa: E402
from tests.overlay_tumble_1670 import AREA, STEP, make  # noqa: E402
from tests.test_overlay_landing_1683k import dropped  # noqa: E402


def throw_at_wall(gait: str, side: int, monkeypatch: pytest.MonkeyPatch, verdict: str, secs: float = 1.6):
    """A figure let go toward the `side` wall fast enough to meet it; returns (engine, [(t since, out)])."""
    monkeypatch.setattr(ld, "smack", lambda speed, scale, rng: verdict)
    e, t = dropped(0.0, vx=side * 1400.0, y=400.0)
    if gait == "float":
        e, _s = make("masculine", "float", 3)
        e.update(1.0)
        e.y = 400.0
        e._start_fly(side * 1400.0, 0.0)
        t = 1.0
    e.x = AREA[0] + 300.0 if side < 0 else AREA[2] - 300.0
    rows, t0 = [], None
    for _ in range(int(secs / STEP)):
        t += STEP
        out = e.update(t)
        if t0 is None and (e.bonk_until > t or e.wall):
            t0 = t
        rows.append((None if t0 is None else t - t0, out))
    return e, rows


@pytest.mark.parametrize("gait", ["walk", "float"])
@pytest.mark.parametrize("side", [-1, 1])
def test_a_bounce_squashes_against_the_wall_for_a_moment_and_lets_go(gait: str, side: int, monkeypatch: pytest.MonkeyPatch) -> None:
    _e, rows = throw_at_wall(gait, side, monkeypatch, "bounce")
    during = [o.squash for dt, o in rows if dt is not None and dt <= ld.EDGE_FOR and o.squash]
    assert during, "no squash drawn on the touch"
    assert all(q[1] == side for q in during), (side, during)
    assert max(q[0] for q in during) >= 0.5, during
    assert all(q is None for dt, o in rows if dt is not None and dt > ld.EDGE_FOR + 0.1 for q in [o.squash])


def test_the_amounts_are_on_the_cache_grid_and_never_past_one(monkeypatch: pytest.MonkeyPatch) -> None:
    _e, rows = throw_at_wall("walk", -1, monkeypatch, "bounce")
    amounts = {o.squash[0] for _dt, o in rows if o.squash}
    assert amounts and all(0.0 < a <= 1.0 and a * 8 == round(a * 8) for a in amounts), amounts
    assert len(amounts) <= 8


@pytest.mark.parametrize("side", [-1, 1])
def test_a_slide_holds_the_squash_while_it_is_stuck_to_the_wall(side: int, monkeypatch: pytest.MonkeyPatch) -> None:
    e, rows = throw_at_wall("walk", side, monkeypatch, "slide", secs=1.0)
    stuck = [o.squash for dt, o in rows if dt is not None and dt > 0.3 and e.wall]
    assert stuck and all(q is not None and q[1] == side for q in stuck), stuck
    held = [q[0] for q in stuck]
    assert min(held) == max(held) == ld.EDGE_HOLD, held  # steady, so the picture is one (no strobe)
    assert 1.0 - sprites.EDGE_SQUASH * ld.EDGE_HOLD == pytest.approx(0.86, abs=0.005)


def test_nothing_is_squashed_away_from_a_wall() -> None:
    e, _s = make("masculine", "walk", 3)
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    t = 1.0
    for _ in range(600):
        t += STEP
        assert e.update(t).squash is None


@pytest.mark.parametrize("side", [-1, 1])
def test_the_picture_is_narrower_about_the_wall_edge_and_a_little_taller(side: int) -> None:
    _e, spr = make("masculine", "walk", 3)
    plain = spr.frame("fall", 96, False)
    got = sprites.squashed(plain, (1.0, side))
    pl, pt, pr, pb = plain.box
    gl, gt, gr, gb = got.box
    assert (gl if side < 0 else gr) == (pl if side < 0 else pr), "the wall edge stays where it was"
    width = pr - pl
    assert (gr - gl) == pytest.approx(width * (1.0 - sprites.EDGE_SQUASH), abs=1.5)
    assert gb - gt >= pb - pt and gt >= 0 and gb <= plain.height
    assert (got.width, got.height, got.pad_x, got.pad_y) == (plain.width, plain.height, plain.pad_x, plain.pad_y)
    assert got.bgra != plain.bgra and len(got.bgra) == len(plain.bgra)
    assert sprites.squashed(plain, None) is plain and sprites.squashed(plain, (0.0, side)) is plain
