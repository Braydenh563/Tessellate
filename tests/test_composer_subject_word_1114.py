"""The four SUBJECT_WORD phrasings (CHAT_PLAN item 3, L-timeline-9 and L-timeline-11): a word the notes share is
not the thing asked for, so the answer says what is missing or lists the schedule, never the nearest note."""
from __future__ import annotations

import pytest

from tests.test_phrasing_real_1111 import _ask, _fixed_now, notebook  # noqa: F401 (fixtures)

pytestmark = pytest.mark.usefixtures("notebook")


def test_a_meeting_with_my_boss_is_not_the_meeting_with_priya(client):
    for asked in ("when is the meeting with my boss scheduled for", "when is that meeting with my boss"):
        text = _ask(client, asked)["text"]
        assert "boss" in text and "Priya" not in text, text


def test_the_meeting_schedule_is_the_dated_items_ahead(client):
    for asked in ("share my meeting schedule with me", "go over my meeting schedule with me please", "what meetings are coming up"):
        text = _ask(client, asked)["text"]
        assert text.startswith("No meeting is dated ahead in your notes. For the next two weeks"), (asked, text)
        assert "Plumber is coming Thursday" in text and "referral" not in text, text


def test_my_calendar_is_the_dated_items_ahead(client):
    assert _ask(client, "show me my calendar")["text"].startswith("For the next two weeks")


def test_book_as_reserve_is_not_the_book_a_note_is_about(client):
    text = _ask(client, "i want to book tickets for an event.")["text"]
    assert "tickets" in text and "Piranesi" not in text and "Dentist" not in text, text
    #: The noun still finds its note, and a person the notes name still does.
    assert "Piranesi" in _ask(client, "the book Piranesi")["text"]
    assert "plumber" in _ask(client, "when is my landlord's plumber coming")["text"].lower()


def test_birthdays_and_trips_ahead_still_list_their_dates(client):
    assert _ask(client, "any birthdays coming up")["text"].startswith("2 birthdays ahead")
    assert "12 March" in _ask(client, "any trips coming up")["text"]
