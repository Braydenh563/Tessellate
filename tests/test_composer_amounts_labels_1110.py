"""G11 left (g1014-1110): a label looked up across notes of "Label number" lines. "which is cheaper,
free or plus" reads the two labels' figures; "how much more did I spend eating out in october" reads
one label in two notes. Fixed clock, no model."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import composer_extra, composer_study

NOW = dt.datetime(2026, 11, 10, 10, 0, 0)


def _note(i: int, content: str, day: str = "2026-10-20") -> dict:
    return {"id": i, "content": content, "category": "Work", "tags": [], "created_at": f"{day}T10:00:00Z"}


NOTES = [
    _note(1, "Harbor plans\nFree 0\nPlus 5\nPro 12"),
    _note(4, "Budget October\nRent 650\nGroceries 120\nEating out 160"),
    _note(5, "Budget November\nRent 650\nGroceries 140\nEating out 90"),
    _note(6, "Plumber\nCall on Tuesday."),
]


def said(question: str, notes=NOTES) -> str | None:
    reply = composer_extra.answer(composer_study.Ctx(question=question, notes=notes, now=NOW, seed="s", asked=question))
    return reply.text if reply else None


@pytest.mark.parametrize("question", ["which is cheaper, free or plus", "which is cheaper free or plus?", "what's cheaper, plus or free"])
def test_which_is_cheaper_reads_the_two_labels(question):
    text = said(question)
    assert text and text.startswith("Free is cheaper") and "0" in text and "5" in text and "Harbor plans" in text, text


def test_which_costs_more_names_the_dearer_label():
    text = said("which costs more, plus or pro")
    assert text and text.startswith("Pro costs more") and "12" in text, text


def test_a_label_missing_from_the_notes_is_not_guessed():
    assert said("which is cheaper, free or platinum") is None


@pytest.mark.parametrize("question", ["how much more did I spend eating out in october", "how much more did I spend on eating out in october than november"])
def test_how_much_more_compares_one_label_across_two_notes(question):
    text = said(question)
    assert text and "70" in text and "160" in text and "90" in text and "October" in text, text


def test_how_much_less_says_less():
    text = said("how much less did I spend on eating out in november")
    assert text and "70 less" in text, text


def test_one_note_with_the_label_says_there_is_nothing_to_compare():
    text = said("how much more did I spend on eating out in october", NOTES[:2])
    assert text is None or "70" not in text, text
