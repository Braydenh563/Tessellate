"""Audit 1030 Z26 (no model): a line told in the past was listed as a day
ahead: "Slept badly on Tuesday." in a weekly review came back as "Tuesday 3
November". A sentence whose verb says it happened is not upcoming; one that
arranges a thing ("booked for the 21st", "moved to Friday") or says it is
due still is.

Fixed clock: Friday 30 October 2026, 10:00; notes written Tuesday 27 October."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 30, 10, 0, 0)
WRITTEN = dt.datetime(2026, 10, 27, 9, 0, 0)

PAST = [
    "# Weekly review\nThis week I ran twice and prepared the Atlas beta. Slept badly on Tuesday.",
    "Went to the gym on Monday, legs and core.",
    "Had a migraine on Sunday and stayed in.",
    "Watched the match with Sam on Saturday.",
]
AHEAD = [
    ("Dentist check-up booked for Thursday 5 November.", "5 November"),
    ("The essay is due on Wednesday 4 November.", "4 November"),
    ("Group project meeting moved to Monday 2 November.", "2 November"),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(texts, question: str) -> str:  # noqa: ANN001
        for text in texts:
            entry = manager.create_entry(session, text)
            entry.created_at = entry.updated_at = WRITTEN
        session.commit()
        return _ask(client, question, use_tools=False, notes_only=True, answer_from="notes")["text"]

    return build


@pytest.mark.parametrize("question", ["what's coming up", "what is due soon", "what do I have coming up", "anything due soon"])
def test_a_line_told_in_the_past_is_not_ahead(ask, question):
    said = ask(PAST + [text for text, _ in AHEAD], question)
    for gone in ("Slept badly", "gym on Monday", "migraine", "Watched the match"):
        assert gone not in said, said


@pytest.mark.parametrize("question", ["what's coming up", "what do I have coming up", "what is coming up this week"])
def test_an_arranged_or_due_line_stays_ahead(ask, question):
    said = ask(PAST + [text for text, _ in AHEAD], question)
    for _text, day in AHEAD:
        assert day in said, said
