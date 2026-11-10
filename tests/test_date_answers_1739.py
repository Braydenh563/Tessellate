"""INBOX 1739: the date answers (composer, with and without a model).

The owner asked "What did I write on 3 November?" and then "any other notes
around that time". Fixed clock: Tuesday 10 November 2026, 09:00. The notebook:
"Uni is done!! :D" written Tuesday 3 November (its text says "on friday",
which the timeline files under Friday 30 October), a golf note on 2 November,
a gym note on 4 November, a mermaid document on 3 November and an older
"Current Commitments" note.
"""

from __future__ import annotations

from datetime import datetime

import re

import pytest

from tessellate.ai import composer_aware
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core.database import Document
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 10, 9, 0)
UNI_BODY = "Just finished my final assignment on friday at 3:30am but it's done haha!"
FIRST = "What did I write on 3 November?"
THEN = "any othjer notes around that time"


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


@pytest.fixture
def notebook(session):
    rows = [
        (f"Uni is done!! :D\n\n{UNI_BODY}", "2026-11-03T10:00"),
        ("Golf\n\nPlayed 18 holes at the club and shot 92.", "2026-11-02T10:00"),
        ("Gym\n\nLeg day with squats and lunges.", "2026-11-04T10:00"),
        ("Current Commitments\n\nWork shifts and uni deadlines this month.", "2026-10-20T10:00"),
    ]
    for content, made in rows:
        entry = manager.create_entry(session, content)
        entry.created_at = entry.updated_at = datetime.fromisoformat(made)
        session.commit()
        #: The timeline's rule reads the day a phrase meant, against the day the note was written.
        manager.record_dates(session, entry, now=entry.created_at)
    session.add(Document(title="Untitled document 2", content="graph TD\n  A --> B", created_at=datetime(2026, 11, 3, 19, 49)))
    session.commit()


def _two_turns(client):
    first = _ask(client, FIRST, history=[])
    second = _ask(client, THEN, history=[{"question": FIRST, "answer": first["text"]}])
    return first["text"], second["text"]


# (e) the closing line never names a month for a day, and is English

def test_a_date_question_leaves_its_day_as_the_chat_topic():
    history = [{"question": FIRST, "answer": "You wrote one note on 3 November: it said so."}]
    assert chat_said._chat_topic(history) == "3 November"  # noqa: SLF001


@pytest.mark.parametrize("question", ["what did I do last week", "what did I write on Friday", "notes from October"])
def test_a_date_word_alone_is_never_the_topic(question):
    history = [{"question": question, "answer": f"{question}: you wrote notes in October, on Friday, last week."}]
    assert chat_said._chat_topic(history) not in {"October", "Friday", "week", "November"}  # noqa: SLF001


@pytest.mark.parametrize("topic", ["3 November", "last week", "golf", "Sara"])
@pytest.mark.parametrize("seed", [str(i) for i in range(12)])
def test_the_resume_line_is_english_and_says_the_topic(topic, seed):
    line = composer_aware.closing(composer_aware.build(topic=topic), seed, asked="and what about them?")
    assert "pull the notes on it up" not in line and not re.search(r"We were on (?!the subject)", line)
    assert topic in line
