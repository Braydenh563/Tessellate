"""INBOX 1683 k, ledger N7: scrabble, then pull up. When a hanger's hold slips (the window moved under its hands) it may
grip again, scrabble for a moment and pull itself up onto the window's top edge, by its energy and mood; else it drops
as it always did. Fake clock, no Win32; real Windows is unverified."""

from __future__ import annotations

import random
from collections import Counter

import pytest

from tessellate.core.overlay.engine import Engine, Monitor, Perch

SIZE = (100, 120)
FULL = (0, 0, 1920, 1080)
EDGE = Perch(1, 800, 600, 1300)
MOVED = Perch(1, 800, 650, 1300)


def hanging(seed: int = 5, **kw) -> Engine:
    kw.setdefault("hang_top", 0.2)
    e = Engine(SIZE, [Monitor(FULL, 96, FULL, ())], home=(900, 700), rng=random.Random(seed), idle_frames=0, now=0.0, **kw)
    e.update(0.1)
    e.set_windows([EDGE], 0.2)
    e.x = 880.0
    e.hang_on = EDGE
    e._arrive_hang(0.3, e.current_monitor())
    e.update(0.35)
    assert e.state == "hang" and e.hang_on is not None
    return e


def slip(e: Engine, to=MOVED, now: float = 1.0) -> None:
    e.set_windows([to] if to is not None else [], now)


def run(e: Engine, until, limit: float = 20.0) -> float:
    t = e.now
    while not until(e) and t < e.now + limit:
        t += 0.033
        e.update(t)
    return t


def test_a_slipping_hold_with_a_sure_grip_scrabbles_and_pulls_up_onto_the_top_edge() -> None:
    e = hanging()
    e._grip_chance = lambda now: 1.0  # type: ignore[method-assign]
    slip(e)
    assert e.state == "hang" and e.scrabble_until > 1.0 and e.last_slip == "pull"  # still on its hands, scrabbling
    swings = []
    t = 1.0
    while e.state == "hang" and t < 5:
        t += 0.033
        e.update(t)
        swings.append(e._target_pose(t).drag)
    assert max(swings) - min(swings) > 4.0  # the scrabble shakes the hem
    run(e, lambda x: x.state == "stand")
    assert e.state == "stand" and e.perch is not None and e.perch.key == 1
    assert e.y == pytest.approx(MOVED.top - SIZE[1]) and MOVED.left <= e.x <= MOVED.right - SIZE[0]
    assert e.hang_on is None and e.scrabble_until == 0.0 or e.scrabble_until <= e.now


def test_the_scrabble_lasts_long_enough_to_be_seen() -> None:
    e = hanging()
    e._grip_chance = lambda now: 1.0  # type: ignore[method-assign]
    slip(e)
    assert 0.6 <= e.scrabble_until - 1.0 <= 1.5


def test_a_slipping_hold_with_no_grip_drops_as_before() -> None:
    e = hanging()
    e._grip_chance = lambda now: 0.0  # type: ignore[method-assign]
    slip(e)
    assert e.state == "fall" and e.hang_on is None and e.last_slip == "drop"


def test_a_window_that_is_gone_cannot_be_pulled_up_onto() -> None:
    e = hanging()
    e._grip_chance = lambda now: 1.0  # type: ignore[method-assign]
    slip(e, None)
    assert e.state == "fall" and e.last_slip == "drop"


def test_a_window_too_high_to_stand_on_cannot_be_pulled_up_onto() -> None:
    e = hanging()
    e._grip_chance = lambda now: 1.0  # type: ignore[method-assign]
    slip(e, Perch(1, 800, 60, 1300))  # its top is less than a figure below the top of the screen
    assert e.state == "fall"


def test_energy_and_mood_bend_the_grip() -> None:
    e = hanging()
    e.mind.needs["rest"] = 0.0
    fresh = e._grip_chance(1.0)
    e.mind.needs["rest"] = 0.95
    tired = e._grip_chance(1.0)
    assert 0.0 < tired < fresh <= 0.95
    e.mind.needs.update({"rest": 0.0, "curiosity": 0.9, "play": 0.0})
    assert e.mind.mood(1.0, 12) == "curious"
    curious = e._grip_chance(1.0)
    e.mind.needs.update({"rest": 0.7, "curiosity": 0.0})
    assert e.mind.mood(1.0, 12) == "sleepy" and e._grip_chance(1.0) < curious


def test_the_seeded_mix_of_pull_ups_and_drops_follows_the_chance() -> None:
    def mix() -> Counter:
        out: Counter = Counter()
        for seed in range(100):
            e = hanging(seed)
            slip(e)
            out[e.last_slip] += 1
        return out

    first = mix()
    assert sum(first.values()) == 100 and set(first) == {"pull", "drop"}, first
    assert 30 <= first["pull"] <= 85, first
    assert mix() == first


def test_every_seeded_pull_up_ends_standing_on_the_top_edge() -> None:
    ended: Counter = Counter()
    for seed in range(40):
        e = hanging(seed)
        slip(e)
        if e.last_slip != "pull":
            continue
        run(e, lambda x: x.state == "stand")
        ended[(e.state, e.perch.key if e.perch else None, round(e.y))] += 1
    assert ended and set(ended) == {("stand", 1, MOVED.top - SIZE[1])}, ended


def test_a_pick_up_while_it_scrabbles_is_not_pulled_up() -> None:
    e = hanging()
    e._grip_chance = lambda now: 1.0  # type: ignore[method-assign]
    slip(e)
    e._enter("held", e.now)
    assert e.pulling is None and e.scrabble_until <= e.now
