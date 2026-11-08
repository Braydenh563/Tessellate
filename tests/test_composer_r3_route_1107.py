"""Composer round 3, 2026-11-07 (audit-1107-composer-r3.md), through the chat
route (the pool the route builds is part of the answer). No model (fake
transport); fixed clock."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 11, 7, 10, 0, 0)
NOTES = (
    "# Dentist\n\nDr Patel at Kings Road practice. Phone 020 7946 0011. Next check-up Wednesday 11 November at 3pm.",
    "Dentist check-up on 11 November",
    "Number of the day: 7",
    "my number is in the safe",
    "# Passport\n\nExpires 12 March 2031. Number is in the safe.",
    "# Sara\n\nSara likes jazz.",
    "# Weekend plans\n\nSunday: call Mum and meet Sara for lunch at 1pm.",
    "# Uni timetable\n\nTuesday and Thursday are uni days. Cloud lab on Thursday afternoon.",
    "# Marathon\n\nRace is on 14 March in Brighton. Start is at 9am.",
    "# Tokyo trip\n\nFlights cost $900 return, leaving 3 April. Staying in Shinjuku for six nights.",
    "# Lisbon trip\n\nFlights cost $420 return, leaving 12 May. Staying at Hotel Alfama near the river.",
    "# What I know about espresso\n\nGrind fine, 18 g in, 36 g out, 28 seconds.",
    "# Biology\n\nCell respiration: glucose plus oxygen gives carbon dioxide, water and ATP. Exam on 8 December.",
)


@pytest.fixture
def go(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text in NOTES:
        entry = manager.create_entry(session, text, "Personal")
        entry.created_at = entry.updated_at = NOW - dt.timedelta(days=3)
    session.commit()
    return lambda q, chat=False: _ask(client, q, **({} if chat else {"notes_only": True, "answer_from": "notes"}))["text"]


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_r3_2_the_number_for_a_business_finds_the_note_that_holds_it(go, chat):
    said = go("what is the number for the dentist", chat)
    assert "020 7946 0011" in said and "no phone number" not in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_r3_2_a_person_with_no_number_is_denied_in_the_notebooks_name(go, chat):
    said = go("what is Sara's number", chat)
    assert said.startswith("None of your notes give a phone number for Sara."), said
    assert "likes jazz has no" not in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_r3_17_a_slip_in_the_asking_words_does_not_swallow_the_subject(go, chat):
    said = go("wat do i know abuot lisbn", chat)
    assert "Lisbon" in said and "espresso" not in said and "I read that as “what do i know about”" not in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_r3_17_a_misspelt_place_is_searched_as_the_place(go, chat):
    said = go("wat do i know about tokio", chat)
    assert "Tokyo" in said and "None of your notes mention" not in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_r3_17_a_misspelt_when_is_read_as_when(go, chat):
    said = go("wen is the exam", chat)
    assert "8 December" in said and "You have two notes" not in said, said


# --- R3-30: an empty notebook says so -----------------------------------------------------------

@pytest.mark.parametrize("question", ["what do I know about Lisbon", "what is my phone number", "who is Sara"])
def test_r3_30_an_empty_notebook_says_it_has_no_notes(client, question):
    text = _ask(client, question, use_tools=False)["text"]
    assert text.startswith("You have no notes yet."), text
    assert "couldn't find" not in text, text


def test_r3_30_a_notebook_with_notes_keeps_the_plain_miss(go):  # noqa: D103
    assert "You have no notes yet" not in go("what do I know about Reykjavik")


# --- review of the round 3 head -------------------------------------------------------------------
@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_r3_2_a_number_to_call_is_not_a_phone_number_for_the_word_call(go, chat):
    said = go("what's the number to call", chat)
    assert "phone number for call" not in said, said