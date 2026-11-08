"""CHAT_PLAN T1: the calculator's spoken shorthand, no model, no note.
Fixed clock: Sunday 8 November 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import time

import pytest

from tessellate.ai import composer_extra, composer_study, composer_sums

NOW = dt.datetime(2026, 11, 8, 10, 0, 0)


def ctx(q: str, **extra) -> composer_study.Ctx:
    return composer_study.Ctx(question=q, notes=extra.pop("notes", []), now=NOW, seed="s", asked=q, **extra)


def said(q: str, **extra) -> str:
    reply = composer_extra.answer(ctx(q, **extra))
    return reply.text if reply else ""


TABLE = [
    ("5 factorial", "5 factorial is 120.\n\n_Read as 5 x 4 x 3 x 2 x 1._"),
    ("what is 5!", "5 factorial is 120.\n\n_Read as 5 x 4 x 3 x 2 x 1._"),
    ("factorial of 12", "12 factorial is 479,001,600.\n\n_Read as the product of the whole numbers from 1 to 12._"),
    ("factorial of 0", "0 factorial is 1.\n\n_Read as the product of no numbers, which is 1._"),
    ("half of 90", "Half of 90 is 45.\n\n_Read as 90 divided by 2._"),
    ("What's half of 9?", "Half of 9 is 4.5.\n\n_Read as 9 divided by 2._"),
    ("a third of 10", "A third of 10 is 3.333333.\n\n_Read as 10 divided by 3._"),
    ("a quarter of 8", "A quarter of 8 is 2.\n\n_Read as 8 divided by 4._"),
    ("double 45", "Double 45 is 90.\n\n_Read as 45 times 2._"),
    ("twice 2.5", "Double 2.5 is 5.\n\n_Read as 2.5 times 2._"),
    ("triple 7", "Triple 7 is 21.\n\n_Read as 7 times 3._"),
    ("sqrt 144", "The square root of 144 is 12.\n\n_Read as the square root of 144._"),
    ("what is the sqrt of 2", "The square root of 2 is 1.414214.\n\n_Read as the square root of 2._"),
    ("√9", "The square root of 9 is 3.\n\n_Read as the square root of 9._"),
]


@pytest.mark.parametrize(("q", "text"), TABLE)
def test_exact_sentences(q, text):
    assert said(q) == text


def test_twenty_factorial_is_exact_and_twenty_one_is_left_alone():
    assert said("20 factorial").startswith("20 factorial is 2,432,902,008,176,640,000.")
    assert said("21 factorial") == ""


@pytest.mark.parametrize("q", ["half of my notes", "half of the gym note", "sqrt -4", "double the recipe", "factorial", "sqrt", "5 factorials of work", "half of 9 and 10"])
def test_other_questions_are_left_alone(q):
    assert said(q) == ""


def test_the_answer_ignores_the_model_voice_and_notes():
    private = [{"id": 1, "content": "half of 90 is the secret code", "created_at": "2026-11-01", "private": True}]
    plain = said("half of 90")
    assert said("half of 90", voice="formal", notes=private, history=[{"role": "user", "content": "x"}]) == plain
    assert "secret" not in plain


@pytest.mark.parametrize("text", ["half of" + " " * 20000 + "9", "what is " * 3000, "factorial of " + "9" * 20000, "sqrt " + " " * 20000 + "4", "double" + " 1" * 9000])
def test_a_20k_text_is_linear(text):
    start = time.perf_counter()
    composer_sums.answer(ctx(text))
    assert time.perf_counter() - start < 0.5
