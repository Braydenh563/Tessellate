"""INBOX 1668 (c), the owner, 2026-11-04: "the how it went part is kinda innaccurate
as they are completely separate events and time periods". The narrow exception to
INBOX 1441 (no day unless the question asks about time): when one answer tells two
or more separate events of the same activity, each says its own day, relative
("last week", "on Monday"), so they read as separate occasions. Every other answer
keeps 1441. Clock fixed at Wed 4 Nov 2026; model off and on alike (decision 75)."""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 4, 10, 5)
#: Absolute dates never lead in these answers; 1441 says relative or none.
_ABSOLUTE = re.compile(r"\b\d{1,2} (?:Oct|Nov|Sep)\w*|\b(?:Oct|Nov)\w* \d{1,2}\b")

GOLF = [
    ("I had work and hit some golf balls as practice after haha", "2026-10-04T20:00:00"),
    ("Played a game of golf for 18 holes at Windaroo on Monday which was fun but the greens were kinda ass and really dry, I shot like 130", "2026-11-04T18:00:00"),
]
RUNNING = [
    ("Went for a long running session along the river, my knee felt fine", "2026-10-11T07:30:00"),
    ("Did my running at the park, got a new best time over 10k", "2026-11-03T06:45:00"),
]
ACTIVITIES = [
    ("golf", GOLF, ["golf notes", "what have I saved about golf", "tell me about my golf", "what do I have on golf", "golf", "what did I write about golf", "golf?", "my golf notes"]),
    ("running", RUNNING, ["running notes", "what have I saved about running", "tell me about my runs", "what do I have on running"]),
]


def _seed(session, monkeypatch, notes) -> None:
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for content, when in notes:
        entry = manager.create_entry(session, content, "Hobbies", [])
        entry.created_at = entry.updated_at = datetime.fromisoformat(when)
        manager.record_dates(session, entry, now=entry.created_at)
    session.commit()


def _told(text: str) -> list[str]:
    return [p for p in text.split("\n\n") if not p.startswith("You have")]


CASES = [(name, notes, q) for name, notes, qs in ACTIVITIES for q in qs]


@pytest.mark.parametrize(("name", "notes", "question"), CASES)
def test_separate_events_each_say_their_own_day(client, session, monkeypatch, name, notes, question):
    _seed(session, monkeypatch, notes)
    text = _ask(client, question, notes_only=True, use_tools=False)["text"]
    told = _told(text)
    assert len(told) == 2, text
    assert "How it went" not in text and not _ABSOLUTE.search(text), text
    #: The older note carries its distance; the newer says its own (a weekday it
    #: wrote, or the day it was written), never the older one's.
    assert re.search(r"\b(?:weeks?|months?|days?) ago\b|\blast (?:week|month)\b", told[0]), text
    assert re.search(r"\b(?:yesterday|today|on Monday|Tuesday|days? ago|last week|this week)\b", told[1], re.I), text


def test_a_day_the_note_already_names_is_said_once(client, session, monkeypatch):
    _seed(session, monkeypatch, GOLF)
    told = _told(_ask(client, "golf notes", notes_only=True, use_tools=False)["text"])
    assert told[1].count("Monday") == 1 and not told[1].lower().startswith(("today", "on monday, ")), told[1]


def test_the_citations_find_their_words_in_the_text(client, session, monkeypatch):
    _seed(session, monkeypatch, GOLF)
    out = _ask(client, "golf notes", notes_only=True, use_tools=False)
    rows = out["grounding"][0]["sentences"]
    assert len(rows) == 2 and all(row["sentence"] in out["text"] for row in rows), (rows, out["text"])


def test_the_same_with_a_model_running(ai_client, fake_ollama, session, monkeypatch):
    _seed(session, monkeypatch, GOLF)
    before = len(fake_ollama.chat_models)
    text = _ask(ai_client, "golf notes", notes_only=True, use_tools=False, answer_from="notes")["text"]
    assert re.search(r"weeks? ago", _told(text)[0]) and "How it went" not in text, text
    assert len(fake_ollama.chat_models) == before


def test_events_on_one_day_are_one_occasion(client, session, monkeypatch):
    _seed(session, monkeypatch, [("Hit some golf balls at the range before work", "2026-10-20T07:00:00"), ("Played nine holes of golf at the club after work", "2026-10-20T18:00:00")])
    text = _ask(client, "golf notes", notes_only=True, use_tools=False)["text"]
    assert "ago" not in text and "last " not in text, text


def test_a_question_about_time_keeps_its_own_days(client, session, monkeypatch):
    _seed(session, monkeypatch, GOLF)
    text = _ask(client, "when did I last play golf", notes_only=True, use_tools=False)["text"]
    assert "weeks ago, you" not in text, text


@pytest.mark.parametrize("question", ["what do I like to cook", "what have I saved about cooking", "cooking notes"])
def test_what_is_not_an_event_keeps_1441(client, session, monkeypatch, question):
    _seed(session, monkeypatch, [("I like cooking pasta with lots of garlic", "2026-10-04T20:00:00"), ("I love cooking curry on a cold night", "2026-11-02T18:00:00")])
    text = _ask(client, question, notes_only=True, use_tools=False)["text"]
    assert not re.search(r"\b(?:weeks?|months?|days?) ago\b|\bago,", text) and not _ABSOLUTE.search(text), text


def test_one_note_keeps_1441(client, session, monkeypatch):
    _seed(session, monkeypatch, GOLF[:1])
    text = _ask(client, "golf notes", notes_only=True, use_tools=False)["text"]
    assert "ago" not in text and not _ABSOLUTE.search(text), text
