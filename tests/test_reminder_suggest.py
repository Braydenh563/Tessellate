"""A chat message that reads as a dated intention offers "Make this a reminder"
(the owner, 2026-10-27: "maybe suggest it if something similar appears in the
chat"; CHAT_PLAN decision 79).

Deterministic and model-free (decision 75: with a model up the composer only
hands facts, so the chip is never the model's job). It offers, never creates;
a question, a past-tense statement, an undated intention and a request the
chat already acts on ("remind me to ...") get nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tessellate.ai import reminder_suggest

#: A Monday, 09:00; fixed so "Friday" is the 30th and no test reads the real clock.
NOW = datetime(2026, 10, 26, 9, 0)


@pytest.mark.parametrize(
    "message, words, day",
    [
        ("I need to call the dentist on Friday", "Call the dentist", (2026, 10, 30)),
        ("I have to pay the invoice by 3 November", "Pay the invoice", (2026, 11, 3)),
        ("Don't forget to send the report tomorrow at 9am", "Send the report", (2026, 10, 27)),
        ("I'm going to book the venue next Monday", "Book the venue", (2026, 11, 2)),
        ("I should email Priya tomorrow", "Email Priya", (2026, 10, 27)),
        #: "Remember to ..." at the start is now a request the chat acts on
        #: (composer acts, audit 1029); the nudge to oneself mid-sentence is not.
        ("I need to remember to water the plants on Thursday", "Water the plants", (2026, 10, 29)),
    ],
)
def test_a_dated_intention_is_offered(message, words, day):
    found = reminder_suggest.suggest(message, NOW)
    assert found is not None, message
    assert found["text"] == words
    assert (found["due_at"].year, found["due_at"].month, found["due_at"].day) == day


@pytest.mark.parametrize(
    "message",
    [
        "When do I need to call the dentist on Friday?",
        "Do I have to pay the invoice by 3 November",
        "What is on Friday?",
        "I called the dentist on Friday",
        "I went to the dentist yesterday",
        "I didn't need to call the dentist on Friday",
        "I needed to call the dentist last Friday",
        "I need to call the dentist",
        "Remind me to call the dentist on Friday",
        "Remember to water the plants on Thursday",
        "Set a reminder to pay the invoice tomorrow",
        "Friday",
        "",
    ],
)
def test_questions_past_tense_undated_and_asks_the_chat_acts_on_get_nothing(message):
    assert reminder_suggest.suggest(message, NOW) is None, message


def test_the_sentence_with_the_intention_is_the_one_read():
    found = reminder_suggest.suggest("Thanks, that helps. I need to call the dentist on Friday. Anything else?", NOW)
    assert found is not None and found["text"] == "Call the dentist"


def test_the_route_returns_words_and_a_time(client):
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    response = client.post(
        "/reminders/suggest",
        json={"text": "I need to call the dentist tomorrow at 9am", "tz_offset_minutes": 0},
    )
    assert response.status_code == 200
    body = response.json()["suggestion"]
    assert body["text"] == "Call the dentist"
    due = datetime.fromisoformat(body["due_at"])
    assert due.date() == tomorrow.date()


def test_the_route_is_null_when_there_is_nothing_to_offer(client):
    response = client.post("/reminders/suggest", json={"text": "What is on tomorrow?", "tz_offset_minutes": 0})
    assert response.status_code == 200 and response.json() == {"suggestion": None}


def test_a_suggestion_makes_nothing_until_it_is_pressed(client):
    before = client.get("/reminders").json()
    client.post("/reminders/suggest", json={"text": "I need to call the dentist tomorrow", "tz_offset_minutes": 0})
    assert client.get("/reminders").json() == before
