"""L-chat-245: a contradiction ask that names a subject lists that subject's changes only.

Measured before: over the L-chat-8 notebook plus a passport pair, "do my notes
contradict each other about the passport" listed the passport pair, the address
change and the uni days change (three lines for one subject asked).
"""

from __future__ import annotations

import datetime as dt

import pytest

NOW = dt.datetime(2026, 11, 10, 10, 0, 0)
NOTES = [
    ("My address is 12 Oak Street", "2025-03-01"),
    ("My address is now 4 Birch Road", "2026-06-01"),
    ("Uni days this semester: Tuesday and Thursday", "2026-02-20"),
    ("Uni days this semester are Monday and Wednesday", "2026-07-01"),
    ("Passport expiry: 3 March 2027", "2026-01-10"),
    ("Passport expiry: 3 March 2031", "2026-09-30"),
]


@pytest.fixture()
def seeded(session):
    from tessellate.core.database import Entry

    for content, day in NOTES:
        session.add(Entry(content=content, created_at=dt.datetime.fromisoformat(day + "T09:00:00")))
    session.commit()
    return session


def _say(session, question: str) -> str:
    from tessellate.api import chat_extra

    events = chat_extra.notebook_events(session, question, now=NOW)
    assert events and events[0]["type"] == "answer", question
    return events[0]["delta"]


def _bullets(said: str) -> list[str]:
    return [line for line in said.splitlines() if line.startswith("- ")]


def test_the_unscoped_ask_still_lists_every_change(seeded):
    said = _say(seeded, "do my notes contradict each other")
    assert len(_bullets(said)) == 3 and "Birch" in said and "2031" in said, said


@pytest.mark.parametrize("question", [
    "do my notes contradict each other about the passport",
    "what is the passport contradiction",
    "are there any contradictions about my passport",
    "any inconsistencies on the passport",
    "show me the passport contradictions",
])
def test_a_named_subject_lists_only_that_subjects_change(seeded, question):
    said = _say(seeded, question)
    bullets = _bullets(said)
    assert len(bullets) == 1 and "2031" in bullets[0] and "2027" in bullets[0], said
    assert "Birch" not in said and "Thursday" not in said, said


def test_a_named_subject_with_no_change_says_so_for_that_subject(seeded):
    said = _say(seeded, "do my notes contradict each other about the dentist")
    assert "dentist" in said and not _bullets(said) and "Birch" not in said, said


@pytest.mark.parametrize("question", ["do my notes contradict each other", "check my notes for contradictions", "find contradictions in my notes"])
def test_notes_and_each_other_are_not_subjects(seeded, question):
    assert len(_bullets(_say(seeded, question))) == 3
