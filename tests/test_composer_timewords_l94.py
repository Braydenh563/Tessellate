"""L94 (INBOX 899): a time word in a note is said as the day it meant on the day it was written, with its
clock time, never as a bare "tomorrow at 3pm" that was true only then. Fixed clock: 31 October 2026."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer_digest_sentences as sentences

TODAY = date(2026, 10, 31)
WRITTEN = date(2026, 10, 5)


@pytest.fixture(autouse=True)
def _clock():
    token = sentences._TODAY.set(TODAY)
    yield
    sentences._TODAY.reset(token)


@pytest.mark.parametrize("text, day, gone", [
    ("Dentist appointment tomorrow at 3pm", "6 October at 3pm", "tomorrow"),
    ("Call Sam tomorrow at noon.", "6 October at noon", "tomorrow"),
    ("Car service in 3 days", "8 October", "in 3 days"),
    ("Exam in two weeks", "19 October", "in two weeks"),
    ("Met Jo two days ago", "3 October", "two days ago"),
])
def test_a_relative_time_word_is_the_day_it_meant(text, day, gone):
    pinned = sentences._pin(text, WRITTEN)
    assert f"on {day}" in pinned and gone not in pinned.lower(), pinned


def test_a_note_of_today_keeps_its_own_words():
    assert sentences._pin("Dentist appointment tomorrow at 3pm", TODAY) == "Dentist appointment tomorrow at 3pm"
    assert sentences._pin("Car service in 3 days", TODAY) == "Car service in 3 days"


def test_the_answer_says_the_day_a_note_meant(client, session, monkeypatch):
    """Through the chat: the dentist note of 5 October is the 6th, not "tomorrow", asked on 31 October."""
    import json

    from tests import _seed_1031c as seed
    from tessellate.core.database import Entry

    from datetime import datetime

    session.add(Entry(content="Dentist appointment tomorrow at 3pm", tags=json.dumps(["health"]), created_at=datetime(2026, 10, 5, 9)))
    session.commit()
    said, _ = seed.asker(client, monkeypatch)("what do I know about the dentist")
    assert "tomorrow" not in said.lower() and "6 October at 3pm" in said, said
