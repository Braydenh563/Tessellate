"""CodeQL "polynomial regex on uncontrolled data" (c11): the question readers added in rounds 9 finish a 50,000
character run of whitespace or commas in under 50 ms, and still read a short question as before."""

from __future__ import annotations

import time

import pytest

from tessellate.ai import composer_event_verdict, composer_intent, composer_lists

LONG = 50_000


def _fast(fn, *args):
    """The best of three runs: a polynomial pattern is slow every run, while a
    busy machine (the suite's workers) only slows some (PR 216: 23 ms alone,
    up to 101 ms under load, against the 50 ms bar)."""
    times = []
    for _ in range(3):
        start = time.perf_counter()
        fn(*args)
        times.append(time.perf_counter() - start)
    return min(times)


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
    from tessellate.ai import recognise_questions

    assert _fast(recognise_questions.distances, "1" * LONG + " nope") < 0.05  # noqa: SLF001
    assert recognise_questions.distances("Ran 10.5 km today")[0][2] == "10.5"


def test_short_questions_read_as_before():
    assert composer_intent.without_event_window("is the plumber coming this week") == "is the plumber coming"
    assert composer_intent.without_event_window("is the plumber coming tomorrow?") == "is the plumber coming"
    assert composer_lists.clean("what is due pls").rstrip(" ?.!") == "what is due"


@pytest.mark.parametrize("junk", [" ", "\t", ". "])
def test_brief_sentence_split_is_linear(junk):
    from tessellate.ai import composer_brief

    long_note = "The roof leaks again." + junk * LONG + "x " * 40
    assert _fast(composer_brief.brief, long_note, 5) < 0.05
    assert composer_brief.brief("The roof leaks again.\t\tCall the builder " + "soon " * 30, 5) == "The roof leaks again"


@pytest.mark.parametrize("junk", [", ", "; ", ",", " "])
def test_whole_head_is_linear_on_a_run_of_clause_breaks(junk):
    """`_whole_head` sliced and split the note once per break: 1.6 s on 25,000 commas (PR 216)."""
    from tessellate.ai import composer_brief

    assert _fast(composer_brief._whole_head, "word " + junk * 25_000 + "x", 25) < 0.1
    assert _fast(composer_brief.brief, "word " * 30 + junk * 25_000 + "x") < 0.2


def test_whole_head_still_cuts_at_the_last_clause_that_fits():
    from tessellate.ai import composer_brief

    text = ("Cloud computing is the delivery of computing services over the internet to many users, "
            "which lets a team pay only for what it uses, and grow without buying servers of its own")
    head = composer_brief._whole_head(text, 25)
    assert head == ("Cloud computing is the delivery of computing services over the internet to many users, "
                    "which lets a team pay only for what it uses")
