"""CHAT_PLAN T10: a pick from options the person typed, no model, no note.
Fixed clock: Sunday 8 November 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import time

import pytest

from tessellate.ai import composer_chance, composer_extra, composer_study

NOW = dt.datetime(2026, 11, 8, 10, 0, 0)


def ctx(q: str, seed: str = "s", **extra) -> composer_study.Ctx:
    return composer_study.Ctx(question=q, notes=extra.pop("notes", []), now=NOW, seed=seed, asked=q, **extra)


def said(q: str, seed: str = "s", **extra) -> str:
    reply = composer_extra.answer(ctx(q, seed, **extra))
    return reply.text if reply else ""


def test_the_exact_sentence():
    text = said("pick one of pizza, sushi, tacos")
    assert text.startswith("I pick ")
    assert text.endswith("\n\n_Read as one pick at random from pizza, sushi and tacos._")
    assert text.split("\n")[0] in ("I pick pizza.", "I pick sushi.", "I pick tacos.")


def test_two_options_read_with_and():
    assert said("choose between tea and coffee").endswith("_Read as one pick at random from tea and coffee._")


def test_an_oxford_or_is_read():
    assert said("choose between tea, coffee, or water").endswith("from tea, coffee and water._")


def test_the_same_chat_gets_the_same_pick_and_other_chats_vary():
    q = "pick one of pizza, sushi, tacos"
    assert said(q, "chat-1") == said(q, "chat-1")
    assert len({said(q, f"chat-{i}").split("\n")[0] for i in range(40)}) == 3


def test_a_duplicate_option_is_counted_once():
    assert said("pick one of tea, Tea and coffee").endswith("from tea and coffee._")


def test_model_on_and_off_read_the_same():
    #: The reader takes nothing from the model's state, voice or history.
    q = "pick one of pizza, sushi, tacos"
    plain = said(q)
    assert said(q, voice="formal") == plain
    assert said(q, history=[{"role": "user", "content": "hello"}]) == plain


@pytest.mark.parametrize("q", ["pick one of my notes", "pick one of a", "choose between my reminders and tasks", "pick a number between 1 and 10", "pick one", "pick a note to read", "choose between " + ", ".join(f"o{i}" for i in range(30))])
def test_what_is_not_a_pick_is_left_alone(q):
    assert composer_chance.answer(ctx(q)) is None


def test_no_note_is_read_or_quoted():
    notes = [{"id": 1, "content": "Tacos are the private plan for the surprise party.", "created_at": "2026-11-01", "private": True}]
    text = said("pick one of pizza, sushi, tacos", notes=notes)
    assert "surprise" not in text and "party" not in text


@pytest.mark.parametrize("text", ["pick one of " + "a, " * 7000, "pick" + " " * 20000 + "x", "pick one of a" + " or" * 7000, "choose between " + " " * 20000 + "or"])
def test_a_20k_text_is_linear(text):
    start = time.perf_counter()
    composer_chance.answer(ctx(text))
    composer_chance._PICK.match(" ".join(text.split()))
    composer_chance.options_in(text[:5000])
    assert time.perf_counter() - start < 0.5
