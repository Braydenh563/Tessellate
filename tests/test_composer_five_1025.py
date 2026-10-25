"""composer5: a realistic uni notebook (Biology 101, WW1, Maths problem sets,
reminders) asked with no model. Fixed clock, fixed notes."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 21, 10, 0, 0)
BIO = (
    "# Biology 101: Cell respiration\n\n"
    "Cell respiration releases energy from glucose. The **Krebs cycle** happens in the mitochondrial matrix and makes NADH and FADH2.\n\n"
    "## Glycolysis\n\nGlycolysis splits glucose into two pyruvate and makes 2 ATP.\n\n"
    "## Electron transport\n\nThe electron transport chain makes about 32 ATP.\n\n"
    "```python\natp = 2 + 2 + 32\nprint(atp)\n```\n\n- [ ] Read chapter 4\n- [ ] Revise the Krebs cycle diagram\n"
)
WW1 = (
    "# History: Causes of WW1\n\n"
    "The main causes were militarism, alliances, imperialism and nationalism.\n\n"
    "## Alliances\n\nThe Triple Entente and the Triple Alliance split Europe in two.\n\n"
    "## The spark\n\nThe assassination of Franz Ferdinand in Sarajevo on 28 June 1914 started the crisis.\n"
)
MATHS = (
    "# Maths: Problem set 5\n\nProblem set 5 covers integration by parts.\n\n"
    "- [ ] Finish problem set 5\n\nExam on 12 November, hall B.\n"
)
NOTES = [(BIO, dt.datetime(2026, 10, 20, 9), "Lecture notes"), (WW1, dt.datetime(2026, 10, 19, 9), "Lecture notes"), (MATHS, dt.datetime(2026, 10, 18, 9), "Maths")]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, when, cat in NOTES:
        manager.create_entry(session, text, cat).created_at = when
    session.add(Reminder(text="Exam", due_at=dt.datetime(2026, 11, 12, 9, 0)))
    session.add(Reminder(text="Call the landlord", due_at=dt.datetime(2026, 10, 28, 17, 0)))
    session.commit()

    def go(question: str, notes_only: bool = True, **body) -> str:
        extra = {"answer_from": "notes"} if notes_only else {}
        return _ask(client, question, notes_only=notes_only, history=[], **extra, **body)["text"]

    return go


@pytest.mark.parametrize("q", ["what is the Krebs cycle", "what caused ww1", "when was the assassination"])
def test_item1_no_unrelated_reminder_offer(ask, q):
    said = ask(q)
    assert "Remind you" not in said, said
    #: Nor a closer about a note the answer never used.
    if q == "what caused ww1":
        assert "Biology" not in said, said


@pytest.mark.parametrize("asked,on", [
    ("what is the Krebs cycle", False),
    ("explain glycolysis", False),
    ("what do I still need to do", True),
    ("when is problem set 5 due", True),
    ("when do I read chapter 4", True),
    ("when was the assassination", False),
])
def test_item1_a_reminder_is_offered_only_for_a_question_about_the_task(asked, on):
    from tessellate.ai import composer_digest
    assert composer_digest._on_topic("read chapter 4", asked) is on


@pytest.mark.parametrize("q", ["when is my exam", "what date is my exam", "when do I have my exam", "when's the exam"])
def test_item2_when_is_my_exam_names_the_reminder_and_the_note(ask, q):
    said = ask(q)
    assert "Exam" in said and "12 November" in said and "09:00" in said, said
    assert "hall B" in said and "Problem set 5" in said, said


@pytest.mark.parametrize("q", ["how long ago was 1 september", "when is my exam", "what's due this week", "what are my reminders"])
def test_item3_no_false_grounding_warning(ask, q):
    assert "Heads up" not in ask(q, notes_only=False), q


def test_item4_summary_covers_all_and_sorts_code(ask):
    said = ask("summarise my lecture notes")
    print(said)
    assert "print(atp)" not in said and "atp = 2" not in said, said
    assert "\n-\n" not in said and not said.rstrip().endswith("-"), said
    assert "WW1" in said or "Alliances" in said, said
