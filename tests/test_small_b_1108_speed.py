"""The patterns of batch B stay linear on hostile input (CodeQL: polynomial regex on uncontrolled data)."""

from __future__ import annotations

import time

import pytest

from tessellate.ai import composer_numbers, composer_small

BUDGET = 0.05

HOSTILE = [
    "what if" + "\t" * 20000 + "x",
    "what if " + "\t" * 20000,
    "where did I write" + " \t" * 20000,
    "where did I write down" + "\t" * 20000 + "!",
    "show me" + "\t" * 20000 + "something",
    "show me something" + " " * 20000 + "x",
    "show me" + " " * 20000,
    "what if I " + "?!. " * 5000,
    "where did I write about " + "the " * 8000,
]


@pytest.mark.parametrize("text", HOSTILE)
def test_the_small_patterns_stay_fast_on_long_runs(text):
    composer_small.what_if("what if I move to Lisbon", [])  # the first call loads the word tables; the budget is for the pattern
    composer_small.where_asked("where did I write about squats")
    for run in (composer_small.what_if, composer_small.where_written):
        start = time.perf_counter()
        run(text, [])
        assert time.perf_counter() - start < BUDGET
    start = time.perf_counter()
    composer_small.asks_old(text)
    composer_small.where_asked(text)
    assert time.perf_counter() - start < BUDGET


@pytest.mark.parametrize("text", ["“" * 20000, "“a" * 10000, "five notes " + "“" * 20000, '"' * 20000, "`" * 20000])
def test_quoted_text_is_found_in_linear_time(text):
    start = time.perf_counter()
    composer_numbers.normalise(text)
    assert time.perf_counter() - start < BUDGET
