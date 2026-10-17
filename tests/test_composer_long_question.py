"""A question can be as long as a paste: the composer plans over a bounded
prefix, so planning time does not grow with words x text length."""

from __future__ import annotations

import time

from tessellate.ai import composer


def test_planning_a_twenty_thousand_character_question_is_bounded():
    question = "the cat or " * 1800  # ~20,000 characters; 34 s before the cap
    started = time.perf_counter()
    planned = composer.plan(question)
    elapsed = time.perf_counter() - started
    assert planned.terms  # still planned, not refused
    assert elapsed < 5.0, f"planning took {elapsed:.1f}s"


def test_a_long_question_is_not_read_for_a_utility_word_by_word():
    """The route asked `kind_of` seven times a turn and each read 364 words
    against the utility vocabulary: 5 s of a 6 s turn."""
    from tessellate.ai import utilities

    question = "the cat or " * 1800
    started = time.perf_counter()
    assert utilities.kind_of(question[: composer.PLAN_CHARS]) is None
    assert time.perf_counter() - started < 0.15
    started = time.perf_counter()
    for _ in range(7):
        utilities.kind_of(question[: composer.PLAN_CHARS])
    assert time.perf_counter() - started < 0.05


def test_a_short_question_is_planned_over_all_of_it():
    assert composer.plan("what did I write about golf") == composer.plan("what did I write about golf"[: composer.PLAN_CHARS])


def test_a_long_question_streams_an_answer_in_bounded_time(ai_client, session):
    import json

    from tessellate.entry import manager

    manager.create_entry(session, "The cat sat on the mat")
    session.commit()
    started = time.perf_counter()
    with ai_client.stream("POST", "/chat/stream", json={"question": "the cat or " * 1800, "answer_from": "notes"}) as response:
        assert response.status_code == 200
        kinds = [json.loads(line)["type"] for line in response.iter_lines() if line.strip()]
    assert "done" in kinds
    assert time.perf_counter() - started < 30.0  # over 100 s before the cap


def test_the_model_is_given_the_whole_question():
    from types import SimpleNamespace

    from tessellate.api import routes_chat

    short = SimpleNamespace(question="plan this", full_question=None)
    long = SimpleNamespace(question="plan this", full_question="plan this and then some")
    assert routes_chat._in_full(short) == "plan this"
    assert routes_chat._in_full(long) == "plan this and then some"


def test_the_cap_is_a_prefix_not_a_refusal():
    tail = "x" * composer.PLAN_CHARS + " golf"
    assert composer.plan(tail) == composer.plan(tail[: composer.PLAN_CHARS])
