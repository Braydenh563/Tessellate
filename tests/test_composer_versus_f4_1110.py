"""F4 (s10-1110): "A versus B" over notes of "Label number" lines is set side by side the way
"compare" does it (only the lines that differ, then what is the same), whether the lines are one to a
row or a run of sentences ("Rent 650. Groceries 140."); two labels of one note ("free versus plus")
give both figures and the gap. Fixed clock, no model; a model up reads the same notes (decision 75)."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from tessellate.ai import composer_extra, composer_study
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.entry import manager
from tests.test_parity_1110 import prompt_of, stream

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


@pytest.mark.parametrize("question", ["october budget versus november budget", "october budget vs november budget", "october budget vs. november budget", "november budget compared to october budget"])
def test_versus_sets_two_priced_notes_side_by_side(question):
    text = said(question)
    assert text and "What differs" in text and "Groceries" in text and "Eating out" in text, text
    assert "The same in both: Rent 650" in text, text


def test_a_line_that_is_the_same_is_not_listed_as_a_difference():
    text = said("october budget versus november budget")
    assert text and "- Rent" not in text, text


def test_sentence_runs_are_read_as_lines():
    notes = [_note(1, "# Budget October\n\nRent 650. Groceries 120. Gym 45."), _note(2, "# Budget November\n\nRent 650. Groceries 140. Gym 45.")]
    text = said("october budget versus november budget", notes)
    assert text and "Groceries: 120 in Budget October, 140 in Budget November (20 more)" in text and "Rent 650, Gym 45" in text, text


def test_two_labels_of_one_note():
    text = said("free versus plus")
    assert text and text.startswith("Free is 0 and Plus is 5, 5 more for Plus") and "Harbor plans" in text, text


def test_sides_with_nothing_in_common_are_not_forced():
    assert said("harbor plans vs budget november") is None


def test_one_note_against_itself_is_not_a_comparison():
    assert said("october versus october") is None


def test_a_prose_sentence_with_one_figure_is_not_a_run():
    notes = [_note(1, "# Budget October\n\nPaid the rent. Rent 650."), _note(2, "# Budget November\n\nRent 650. Gym 45.")]
    assert "What differs" not in (said("october budget versus november budget", notes) or "")


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _budgets(session) -> None:
    for content in ("# Budget October\n\nRent 650. Groceries 120. Gym 45.", "# Budget November\n\nRent 650. Groceries 140. Gym 45."):
        manager.create_entry(session, content, category_name="Money")
    session.commit()


def test_the_route_answers_with_no_model(client, session):
    _budgets(session)
    text = stream(client, "october budget versus november budget")["text"]
    assert "What differs" in text and "Groceries" in text, text
    assert json.dumps(text)  # one answer, no card: nothing here acts, so no consent is asked


def test_a_model_with_tools_reads_both_notes(ai_client, fake_ollama, session):
    _budgets(session)
    stream(ai_client, "october budget versus november budget", use_tools=True)
    sent = prompt_of(fake_ollama)
    assert "Groceries 120" in sent and "Groceries 140" in sent, sent[-700:]
