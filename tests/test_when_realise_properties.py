"""WORLD_CLASS_PLAN testing gap (L-world-class-19): property tests for the
time reader (`ai/when.py`, which re-exports `ai/recognise.py`) and the
realiser (`ai/realise.py`). Each property runs over a few hundred cases drawn
from a seeded generator and a fixed clock, so a failure names its case and
reruns the same."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

import pytest

from tessellate.ai import realise, when

SEED = 20261112
CASES = 300
#: A Thursday afternoon, the clock every case reads against.
NOW = datetime(2026, 11, 12, 15, 7)
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _cases(n: int = CASES):
    return random.Random(SEED), range(n)


def test_in_n_minutes_and_hours_is_exactly_that_far_ahead():
    rng, runs = _cases()
    for _ in runs:
        n = rng.randint(1, 600)
        unit, step = rng.choice([("minutes", timedelta(minutes=1)), ("hours", timedelta(hours=1))])
        said = f"in {n} {unit}"
        got = when.resolve(said, NOW)
        assert got is not None, said
        assert got.replace(tzinfo=None) - NOW == n * step, said


def test_next_weekday_is_that_weekday_in_next_week():
    monday_next = NOW.date() - timedelta(days=NOW.weekday()) + timedelta(days=7)
    for name in DAYS:
        got = when.resolve(f"next {name}", NOW)
        assert got is not None, name
        assert got.weekday() == DAYS.index(name), name
        assert monday_next <= got.date() <= monday_next + timedelta(days=6), name


def test_tomorrow_at_an_hour_lands_on_tomorrow_at_that_hour():
    rng, runs = _cases(100)
    for _ in runs:
        hour = rng.randint(1, 12)
        half = rng.choice(["am", "pm"])
        got = when.resolve(f"tomorrow at {hour}{half}", NOW)
        assert got is not None
        assert got.date() == NOW.date() + timedelta(days=1)
        assert got.hour == (hour % 12) + (12 if half == "pm" else 0)
        assert got.minute == 0


def test_letters_that_say_no_time_read_as_nothing():
    rng, runs = _cases(100)
    for _ in runs:
        word = "".join(rng.choice("bcdfgjkqvwxz") for _ in range(rng.randint(3, 9)))
        assert when.resolve(word, NOW) is None, word


def test_a_count_takes_the_singular_only_for_one():
    rng, runs = _cases()
    for _ in runs:
        n = rng.randint(0, 40)
        said = realise.counted(n, "note")
        assert said.endswith(" note") == (n == 1), said
        assert said.split()[0] == realise.count_word(n)


def test_a_joined_list_says_every_item_once_and_ends_with_and():
    rng, runs = _cases()
    words = ["bread", "salt", "fish and chips", "tea", "kiln", "rota", "Sam"]
    for _ in runs:
        items = rng.sample(words, rng.randint(2, len(words)))
        said = realise.join_items(items)
        assert said.endswith(f" and {items[-1]}"), said
        for item in items:
            assert item in said


def test_a_cut_title_fits_its_limit_and_never_cuts_a_word():
    rng, runs = _cases()
    vocab = "the kiln rota for pottery studio glaze orders go out on friday budget meeting notes".split()
    for _ in runs:
        title = " ".join(rng.choice(vocab) for _ in range(rng.randint(1, 30)))
        limit = rng.randint(10, 80)
        cut = realise.cut_title(title, limit)
        if len(title) <= limit:
            assert cut == title
            continue
        assert cut.endswith("…") and len(cut) <= limit + 1, (title, limit, cut)
        assert all(word in vocab for word in cut.removesuffix("…").split()), cut


@pytest.mark.parametrize(("delta", "said"), [(0, "today"), (1, "yesterday"), (-1, "tomorrow")])
def test_a_relative_day_names_the_near_days(delta, said):
    today = date(2026, 11, 12)
    assert realise.relative_day(today - timedelta(days=delta), today) == said


def test_a_relative_day_in_the_last_fortnight_is_last_week_and_weeks_round_as_the_card():
    today = date(2026, 11, 12)
    for delta in range(7, 14):
        assert realise.relative_day(today - timedelta(days=delta), today) == "last week"
    for k in range(2, 5):
        assert realise.weeks_gone(7 * k) == k
