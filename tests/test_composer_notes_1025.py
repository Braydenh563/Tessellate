"""composer4: what did I write about X this week, outline, compare N-way and
date maths, all with no model. Same fixed clock (Wed 21 Oct 2026) and notes."""

from __future__ import annotations

import re

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask
from tests.test_composer_study_1025 import NOTES, NOW


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, when in NOTES:
        manager.create_entry(session, text, "Uni").created_at = when
    for text, due in (("Hand in the essay", (23, 17)), ("Gym session", (20, 7)), ("Submit essay", (None, 0)), ("Call the landlord", (28, 12))):
        if due[0]:
            session.add(Reminder(text=text, due_at=NOW.replace(day=due[0], hour=due[1], minute=0)))
    session.commit()

    def go(question: str, history: list | None = None, **body) -> str:
        return _ask(client, question, notes_only=True, answer_from="notes", history=history or [], **body)["text"]

    return go



#: (question, must match, must not match)
RECENT = [
    ("what did I write about databases this week", r"Lecture 6: Databases", r"couldn't find"),
    ("What did I write about scheduling this month?", r"Lecture 5: Operating systems", r""),
    ("what did i write about search last week", r"did not write|No note|Nothing", r"^- .*Lecture 3"),
    ("what did I write about search this week", r"COMP2001 Lecture 3", r""),
    ("what have I written about the exam this month", r"Lecture 5", r""),
    ("show me my notes on databases this week", r"Lecture 6: Databases", r""),
    ("what did I jot down about joins yesterday", r"did not write|No note|Nothing", r"^- .*Lecture 6"),
]


@pytest.mark.parametrize("q,must,mustnt", RECENT)
def test_what_did_i_write_about(ask, q, must, mustnt):
    said = ask(q)
    assert re.search(must, said), said
    assert not mustnt or not re.search(mustnt, said, re.M), said


def test_the_list_is_dated_and_quotes_the_note(ask):
    said = ask("what did I write about databases this week")
    assert re.search(r"Mon 19 Oct, \[Lecture 6: Databases\]\(#/notes/2\)", said) and "primary key" in said.lower()


def test_an_empty_window_names_the_latest_note(ask):
    said = ask("what did I write about the dentist last week")
    assert "Dentist" in said and "14 Oct" in said or "did not write" in said


def test_recent_wordings_vary_with_the_question():
    from tessellate.ai import composer_notes, composer_study
    seen = set()
    for i in range(40):
        ctx = composer_study.Ctx(question="what did I write about databases this week", notes=[], now=NOW, seed=f"s{i}")
        seen.add(composer_notes.answer(ctx).text)
    assert len(seen) >= 3


OUTLINE = [
    ("outline lecture 5", r"Scheduling.*\n.*Memory|Scheduling", r"Quiz on"),
    ("outline of lecture 6", r"Joins", r""),
    ("give me an outline of the databases lecture", r"Joins", r""),
    ("what sections does lecture 5 have", r"Scheduling", r""),
    ("table of contents for lecture 5", r"Memory", r""),
    ("outline comp2001 assignment 2", r"Method", r""),
    ("structure of lecture 5", r"Scheduling", r""),
]


@pytest.mark.parametrize("q,must,mustnt", OUTLINE)
def test_outline(ask, q, must, mustnt):
    said = ask(q)
    assert re.search(must, said, re.S), said
    assert not mustnt or not re.search(mustnt, said, re.M), said


def test_outline_nests_by_level_and_counts_words(ask):
    said = ask("outline lecture 5")
    assert "- Lecture 5: Operating systems" in said and "  - Scheduling (" in said and "words)" in said


def test_a_note_without_headings_says_so(ask):
    assert "no headings" in ask("outline dentist").lower()


def test_outline_of_nothing_is_left_to_the_older_readers(ask):
    assert "- Scheduling" not in ask("outline astrophysics")
