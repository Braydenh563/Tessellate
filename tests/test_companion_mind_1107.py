"""Research B2, B1, B4 (INBOX 1683 l): the mind has more needs that rise and are fed, scores every act through
response curves (need, mood, hour, input, recency) instead of a linear weight, never repeats back to back and
runs short chains. Pure: seeded rng, fixed clock, no Win32."""

from __future__ import annotations

import random

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import props as pr

pr.register()
ONE = [eng.Monitor((0, 0, 1920, 1040), 96)]


def mind(now: float = 0.0) -> bh.Mind:
    return bh.Mind(now)


def test_there_are_more_needs_and_they_rise_with_time() -> None:
    m = mind()
    assert {"rest", "curiosity", "play", "social", "comfort", "hunger", "novelty"} <= set(m.needs)
    before = dict(m.needs)
    m.tick(30.0)
    for k in ("social", "comfort", "hunger", "novelty"):
        assert m.needs[k] > before[k]
    m.needs = {"rest": 0.1, "curiosity": 0.1, "play": 0.1}  # an older, smaller dict still works
    m.tick(60.0)
    assert m.needs["rest"] > 0.1


def test_a_snack_feeds_hunger_and_a_groom_feeds_comfort() -> None:
    m = mind()
    m.needs.update(hunger=0.9, comfort=0.9)
    m.did("snack", 1.0)
    m.did("groom", 2.0)
    assert m.needs["hunger"] < 0.4 and m.needs["comfort"] < 0.6


def test_the_act_that_feeds_the_hungriest_need_is_likelier_and_the_curve_is_not_linear() -> None:
    m = mind()
    m.needs.update(hunger=0.0)
    low = dict(m.weights(100.0, "walk", 12))["snack"]
    m.needs.update(hunger=1.0)
    high = dict(m.weights(100.0, "walk", 12))["snack"]
    m.needs.update(hunger=0.5)
    mid = dict(m.weights(100.0, "walk", 12))["snack"]
    assert high > 2 * low
    assert (mid - low) < (high - low) * 0.6  # the curve is slow at first, not a straight line


def test_quiet_acts_win_when_the_person_is_away_and_attention_acts_when_they_are_here() -> None:
    m = mind()
    m.idle, m.near = 600.0, False
    away = dict(m.weights(100.0, "walk", 12))
    m.idle, m.near = 2.0, True
    here = dict(m.weights(100.0, "walk", 12))
    assert away["doze"] / away["glance_pointer"] > here["doze"] / here["glance_pointer"]
    assert here["peer_at_cursor"] > away["peer_at_cursor"]


def test_nothing_repeats_back_to_back_not_even_a_quiet_one() -> None:
    m, rng = mind(), random.Random(3)
    prev, longest, run, t = "", 0, 0, 0.0
    for _ in range(600):
        t += 5.0
        m.tick(t)
        name = m.pick(rng, t, "walk", 12)
        m.did(name, t)
        run = run + 1 if name == prev else 1
        longest, prev = max(longest, run), name
    assert longest == 1


def test_a_chain_runs_its_steps_in_order_and_is_counted() -> None:
    m, rng = mind(), random.Random(11)
    m.needs.update(rest=0.8)
    seen = []
    t = 0.0
    for _ in range(3000):
        t += 5.0
        m.tick(t)
        name = m.pick(rng, t, "walk", 12)
        m.did(name, t)
        seen.append(name)
        if m.chains_done:
            break
    assert m.chains_done >= 1
    assert any(tuple(seen[i : i + len(c.steps)]) == c.steps for c in bh.CHAINS for i in range(len(seen)))


# --- B5: a higher-priority reaction interrupts a running act ----------------------------------

def _engine():
    from tessellate.core.overlay.engine import Engine, Monitor

    e = Engine((100, 120), [Monitor((0, 0, 1920, 1040), 96)], rng=random.Random(7), idle_frames=0, home=(800, 920))
    e.update(0.1)
    return e


def test_a_high_priority_reaction_breaks_a_running_act_a_low_one_waits() -> None:
    e = _engine()
    e._start_act("read_book", 5.0)
    assert e.state == "act" and e.act == "read_book"
    assert e.react("window_closed", 6.0) is True  # a screen event always could break an act
    e2 = _engine()
    e2._start_act("stretch", 5.0)
    assert e2.react("battery_low", 6.0) is True and e2.act == "shiver"


def test_only_a_higher_priority_breaks_a_reaction_and_a_sitting_figure_is_woken_by_one() -> None:
    e = _engine()
    assert e.react("window_closed", 5.0) is True and e.act == "relief"
    assert e.react("app_switched", 5.5) is False  # equal priority: it never breaks a reaction
    assert e.react("battery_low", 5.6) is True and e.act == "shiver"  # a higher one does
    e3 = _engine()
    e3._enter("sit", 3.0)
    assert e3.react("battery_low", 4.0) is True and e3.state == "act"
    e4 = _engine()
    e4._enter("sit", 3.0)
    assert e4.react("window_opened", 4.0) is False  # a low one does not wake it


# --- the rare long walk and an hour of life, seeded, fixed clock -------------------------------

def hour_of_life(seed: int, hour: int = 14):
    from tessellate.core.overlay import engine as eng

    e = eng.Engine((100, 120), [eng.Monitor((0, 0, 1920, 1040), 96)], rng=random.Random(seed), idle_frames=0, home=(800, 920))
    e.hour = hour
    # Intent moved (INBOX 1692, 00:50Z): with presence on, the hour is mostly a few minutes-long spells (a typing spell
    # goes on in place, so its act runs twice in a row on purpose); this hour measures the mind's own picks, and
    # spells have their variety tests in test_overlay_presence_1692.py.
    e.presence = False
    names: list[str] = []
    real = e._start_act
    e._start_act = lambda name, now: (names.append(name), real(name, now))[1]  # type: ignore[method-assign]
    t = 0.0
    while t < 3600.0:
        t += 0.25
        if int(t) % 45 == 0:
            e.last_active = t  # the person is at the desk, working: not typing at this very moment
        e.update(t)
    return e, names


def longest_run(names: list[str]) -> int:
    best = run = 0
    prev = None
    for n in names:
        run = run + 1 if n == prev else 1
        best, prev = max(best, run), n
    return best


def test_an_hour_has_variety_no_repeat_and_at_most_a_couple_of_long_walks() -> None:
    walks, distinct = [], []
    for seed in (1, 2, 3):
        e, names = hour_of_life(seed)
        walks.append(e.long_walks)
        distinct.append(len(set(names)))
        assert longest_run(names) == 1, (seed, names[:40])
    assert all(w <= 2 for w in walks) and all(d >= 12 for d in distinct), (walks, distinct)


def test_a_long_walk_is_never_twice_within_an_hour_and_needs_a_good_mood() -> None:
    e, _ = hour_of_life(5)
    e.last_long_walk = e.now
    e.mind.feel("curious", e.now)
    assert e._long_walk_ok(e.now + 100.0) is False
    assert e._long_walk_ok(e.now + 3700.0) in (True, False)
    e.last_long_walk = -1e9
    e.mind.feel("sleepy", e.now)
    assert e._long_walk_ok(e.now) is False
    e.mind.feel("happy", e.now)
    e.mind.needs["rest"] = 0.2
    assert e._long_walk_ok(e.now) is True


def test_a_long_walk_crosses_most_of_the_screen_on_foot_then_looks_about() -> None:
    from tessellate.core.overlay import engine as eng

    e = eng.Engine((100, 120), [eng.Monitor((0, 0, 1920, 1040), 96)], rng=random.Random(4), idle_frames=0, home=(300, 920))
    e.hour = 14
    t = 0.0
    while t < 3.0:
        t += 0.25
        e.update(t)
    x0 = e.x
    e._long_walk(t)
    assert e.long_walks == 1 and e.mode and e.state in ("walk", "crouch")
    states = set()
    for _ in range(4000):
        t += 0.1
        e.last_active = t
        e.update(t)
        states.add(e.state)
        if e.act in ("ponder", "look_around"):
            break
    assert abs(e.x - x0) >= 0.45 * (1920 - 100) and "warp" not in states and e.act in ("ponder", "look_around")


def test_the_hour_summary_numbers() -> None:
    # Intent moved (INBOX 1692, 00:50Z): travel is now seen (blink, cloud and bubble rides of 1.5 to 3.4 s), which takes a
    # little of the hour and moves the seeded draws; four seeds swung 24 to 37 acts each, so the bar reads eight seeds
    # (the base had 17 chains and 271 acts over them, this 11 and 264): 30 acts and more than one chain a seed-hour.
    # Intent moved (atlascat 1108 A3): acts built on both sides take the catalogue's longer lengths (a nap 20 to 240 s, a read 25 to 55 s),
    # so the hour holds fewer, longer acts: 15 chains and 222 acts over the eight seeds, 28 an hour; the bar reads 200.
    chains = acts = 0
    for seed in range(1, 9):
        e, names = hour_of_life(seed)
        chains += e.mind.chains_done
        acts += len(names)
    assert chains >= 10 and acts >= 200


def test_an_overdue_trip_is_chosen_more_often() -> None:
    e = eng.Engine((100, 120), ONE, rng=random.Random(5), home=(800, 920))
    e.roam = True
    e.update(0.1)
    e.trip_ready = 100.0
    weight = lambda t: dict(e._act_table(t, 0.0))["trip"]  # noqa: E731
    assert weight(100.0) < weight(700.0) < weight(100.0 + 99999.0)
    assert weight(100.0 + 99999.0) <= weight(100.0) * (1 + eng.TRIP_OVERDUE_MAX) + 1e-9
