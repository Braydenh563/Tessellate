"""CodeQL "polynomial regex on uncontrolled data" (c11): the question readers added in rounds 9 finish a 50,000
character run of whitespace or commas in under 50 ms, and still read a short question as before."""

from __future__ import annotations

import time

import pytest

from tessellate.ai import composer_event_verdict, composer_intent, composer_lists

LONG = 50_000


def _fast(fn, *args):
    start = time.perf_counter()
    fn(*args)
    return time.perf_counter() - start


@pytest.mark.parametrize("junk", [" ", "\t", ",", ", "])
def test_event_window_is_linear(junk):
    assert _fast(composer_intent.without_event_window, "is the plumber" + junk * LONG + "x") < 0.05
    assert _fast(composer_intent.without_event_window, "is the plumber" + junk * LONG) < 0.05


@pytest.mark.parametrize("junk", [" ", "\t", ",", ", ", ",\t"])
def test_courtesy_tail_is_linear(junk):
    assert _fast(composer_lists.clean, "what is due" + junk * LONG + "x") < 0.05
    assert _fast(composer_lists.clean, "what is due" + junk * LONG) < 0.05


def test_verdict_is_linear():
    from datetime import date

    assert _fast(composer_event_verdict.verdict, "is the plumber " + " " * LONG + "x", "Plumber 11 November", date(2026, 11, 9)) < 0.05


def test_distance_reader_is_linear_on_a_digit_run():
    from tessellate.ai import recognise

    assert _fast(recognise.distances, "1" * LONG + " nope") < 0.05  # noqa: SLF001
    assert recognise.distances("Ran 10.5 km today")[0][2] == "10.5"


def test_short_questions_read_as_before():
    assert composer_intent.without_event_window("is the plumber coming this week") == "is the plumber coming"
    assert composer_intent.without_event_window("is the plumber coming tomorrow?") == "is the plumber coming"
    assert composer_lists.clean("what is due pls").rstrip(" ?.!") == "what is due"
