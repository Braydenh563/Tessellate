"""Idle life (INBOX 1656): a standing figure draws the idle cycle at 8 a second, and the
away-from-the-keyboard rule (sits at ten minutes, sleeps at twenty). Fake clock."""

from __future__ import annotations

import random

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import sprites
from tessellate.core.overlay.engine import Engine, Monitor

SIZE = (100, 120)
ONE = [Monitor((0, 0, 1920, 1040), 96)]


def make(**kw) -> Engine:
    kw.setdefault("rng", random.Random(3))
    kw.setdefault("home", (800, 920))
    kw.setdefault("roam", False)
    return Engine(SIZE, ONE, **kw)


def test_the_engine_and_the_frames_agree_on_the_cycle() -> None:
    assert eng.IDLE_FRAMES == sprites.IDLE_COUNT == len(sprites.IDLE_FRAMES)
    assert all(n in sprites.FRAME_NAMES for n in sprites.IDLE_FRAMES)


def test_standing_cycles_through_every_idle_frame_at_about_eight_a_second() -> None:
    e = make()
    seen, t = [], 0.0
    out = e.update(t)
    while t < 1.6:
        seen.append(out.frame)
        assert out.wake_ms is not None and out.wake_ms <= 126
        t += out.wake_ms / 1000.0
        e.flash = None  # blinks have their own test
        out = e.update(t)
    idles = [f for f in seen if f.startswith("idle")]
    assert set(idles) == set(sprites.IDLE_FRAMES)
    assert 11 <= len(idles) <= 14  # one cycle is 1.5 s, so about twelve frames in 1.6 s


def test_a_wake_lands_on_a_new_frame_not_the_same_one_again() -> None:
    e = make()
    out, t = e.update(0.0), 0.0
    for _ in range(40):
        before = out.frame
        t += out.wake_ms / 1000.0
        e.flash = None
        out = e.update(t)
        assert out.frame != before


# "quiet" (typing) left this list 2026-11-04: the owner's "it is also not animated"
# (INBOX 1670); typing keeps the figure in place, its idle frames still play.
@pytest.mark.parametrize("why", ["reduced", "no_frames"])
def test_a_still_figure_is_one_frame_and_costs_no_idle_wake(why: str) -> None:
    kw = {"reduced": True} if why == "reduced" else {"idle_frames": 0} if why == "no_frames" else {}
    e = make(**kw)
    frames, t = set(), 0.0
    for _ in range(30):
        out = e.update(t)
        frames.add(out.frame)
        t += 0.5
    assert frames <= {"stand", "sit", "blink", "look"}
    assert not any(f.startswith("idle") for f in frames)
    assert out.wake_ms is None or out.wake_ms > 130  # a blink or an act, never the idle tick


def test_sitting_sleeping_and_walking_keep_their_own_frames() -> None:
    e = make(roam=True)
    e._enter("sit", 0.0)
    assert e.update(0.1).frame == "sit"
    e._enter("sleep", 1.0)
    assert e.update(1.1).frame == "sleep"
    e._enter("walk", 2.0)
    assert e.update(2.1).frame.startswith("walk")


def test_a_blink_still_overrides_the_cycle() -> None:
    e = make()
    e.flash = ("blink", 10.0)
    assert e.update(1.0).frame == "blink"


def test_untouched_it_sits_at_ten_minutes_and_sleeps_at_twenty() -> None:
    assert (eng.IDLE_SIT, eng.IDLE_SLEEP) == (600.0, 1200.0)
    e = make()
    e.last_active = 0.0
    t, out = 0.0, e.update(0.0)
    first_sit = first_sleep = None
    while t < 1300 and out.wake_ms is not None:
        t += max(out.wake_ms, 500) / 1000.0
        out = e.update(t)
        if out.frame == "sit" and first_sit is None:
            first_sit = t
        if out.frame == "sleep" and first_sleep is None:
            first_sleep = t
    assert first_sit is not None and 600 <= first_sit < 610
    assert first_sleep is not None and 1200 <= first_sleep < 1210


def test_a_roaming_figure_still_does_acts_after_three_minutes_away() -> None:
    e = make(roam=True, home=(100, 920))
    e.last_active = 0.0
    t, frames = 0.0, set()
    while t < 400:
        t += 0.1
        frames.add(e.update(t).frame)
    assert any(f.startswith("walk") for f in frames)
    assert "sit" not in frames


def test_typing_keeps_it_in_place_but_its_idle_frames_still_play() -> None:
    e = make()
    e.quiet = True
    e._enter("stand", 0.0)
    e.state_until = 1e9
    frames, t = set(), 0.0
    for _ in range(40):
        out = e.update(t)
        frames.add(out.frame)
        t += 0.1
    assert any(f.startswith("idle") for f in frames)
