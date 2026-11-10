"""R9-10 rest (composer audit round 9, c12): the fastest of two runs, the holiday that is best in a month, and
two runs set side by side are worked out from the lines, with dates and units read by `ai/recognise.py`.
Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import time

import pytest

import tests._seed_r9_1109 as sd
from tessellate.ai import composer_tally


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda question: go(question)[0]


def test_the_fastest_run_is_the_quicker_pace(ask):
    text = ask("what was my fastest run")
    assert text.startswith("1 November: 10 km in 58 minutes"), text
    assert "5:48 a km" in text and "None of these notes" not in text


def test_the_longest_run_is_the_longer_distance(ask):
    assert ask("what was my longest run").startswith("8 November: 12 km in 71 minutes")


def test_two_runs_compared_side_by_side(ask):
    text = ask("compare my two runs")
    assert "1 November: 10 km in 58 minutes (5:48 a km)" in text
    assert "8 November: 12 km in 71 minutes (5:55 a km)" in text
    assert "1 November" in text.split("faster")[0].splitlines()[-1] and "longer" in text


def test_the_holiday_that_is_best_in_a_month(ask):
    text = ask("which holiday is better in April")
    assert text.startswith("Japan is best in April"), text
    assert "Holiday options" in text


def test_a_month_no_line_names_says_so(ask):
    assert "no holiday" in ask("which holiday is better in August").lower()


def test_a_long_question_is_read_in_bounded_time():
    out = type("O", (), {"lines": [], "parts": [], "grounding": []})()
    for q in ("which holiday is better in " + "a " * 25_000, "what was my " + " " * 50_000 + "fastest run", "compare my " + " " * 50_000 + "two runs"):
        start = time.perf_counter()
        composer_tally.answer(out, q, [])
        assert time.perf_counter() - start < 0.5
