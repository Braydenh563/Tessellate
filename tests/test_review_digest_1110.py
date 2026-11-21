"""The week's and the day's review is one writer (composer audit 2, G4).

"Weekly review", "daily review", "how was my week", "summarise my week",
"summarise my day" and the dashboard's Digest with no model all read
`review_digest`, which wraps `composer_voice.week_review`: what was written by
subject, never a creation log, and reminders made as a count.

Fixed clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import activity, review_digest
from tessellate.api import routes_chat, routes_insights
from tessellate.core import config
from tessellate.core.database import Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 11, 10, 9, 0, 0)
REMINDERS = [
    ("Pay phone bill", 10, False, 7),
    ("Take bins out", 10, False, 7),
    ("Dentist check-up", 11, False, 7),
    ("Email landlord about the leak", 5, True, 6),
    ("Renew passport", 3, False, 2),
]
WEEK_PHRASES = ["weekly review", "give me a weekly review", "how was my week", "how did my week go", "summarise my week", "summarize my week", "week in review"]
DAY_PHRASES = ["daily review", "give me a daily review", "summarise my day", "how was today", "how was my day", "recap my day"]


@pytest.fixture
def book(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_insights, "user_now", lambda _c: NOW)
    notes = [
        ("# Harbor launch plan\n\nShip the mobile app to the public on the 14th of next month.\n\n- [ ] Store listing copy", 9, "Work"),
        ("# Beta feedback\n\n41 testers active. The top complaint is the sign-up flow with nine fields.", 8, "Work"),
        ("Garden shed roof leaks in the north corner after the rain.", 10, "Home"),
        ("# Shopping\n\n- [ ] milk\n- [ ] bread\n- [ ] eggs", 10, "Home"),
    ]
    for text, day, category in notes:
        entry = manager.create_entry(session, text, category)
        entry.created_at = entry.updated_at = dt.datetime(2026, 11, day, 10)
    for text, day, done, made in REMINDERS:
        row = Reminder(text=text, due_at=dt.datetime(2026, 11, day, 9), done=done, created_at=dt.datetime(2026, 11, made))
        session.add(row)
        session.flush()
        row.done_at = dt.datetime(2026, 11, 10, 8) if done else None
    session.commit()
    return session


@pytest.mark.parametrize("phrase", WEEK_PHRASES)
def test_a_week_review_phrase_is_read_as_the_week(phrase):
    assert review_digest.kind(phrase) == "week"


@pytest.mark.parametrize("phrase", DAY_PHRASES)
def test_a_day_review_phrase_is_read_as_the_day(phrase):
    assert review_digest.kind(phrase) == "day"


@pytest.mark.parametrize("phrase", ["what did I do this week", "review my notes about Lisbon", "how was the weekly meeting", "what is a weekly review in agile", "summarise the beta note"])
def test_other_questions_are_not_a_review(phrase):
    assert review_digest.kind(phrase) is None


def test_the_week_is_a_summary_not_a_log(book):
    said = review_digest.week(book, NOW)
    assert said.startswith("You wrote four notes in the last seven days, from 8 November")
    #: Today's notes are named, not hidden as "two more".
    assert "Garden shed roof" in said and "**Shopping**" in said
    assert "two more" not in said
    #: No creation log, no source label, no reminder list of "set the reminder ...".
    for log_line in ("set the reminder", "made the note", "From your notes, no AI"):
        assert log_line not in said
    #: Reminders made are a count; only overdue and next are named.
    assert "Reminders: 4 made, 1 done." in said
    assert "Overdue: Renew passport (due 3 November)." in said
    assert "Next: Pay phone bill (due today); Take bins out (due today); Dentist check-up (due tomorrow)." in said


def test_the_week_names_a_title_less_note_by_its_first_words_once(book):
    said = review_digest.week(book, NOW)
    assert "“Garden shed roof leaks in the…” (today)" in said
    assert "(10 November) (10 November)" not in said and "your note from 10 November" not in said


def test_still_open_is_one_item_a_note_and_not_a_shopping_list(book):
    said = review_digest.week(book, NOW).split("Still open:")[1].split("\n\n")[0]
    assert said.count("- [ ]") == 2
    assert "Milk" in said and "Bread" not in said


def test_an_empty_week_says_so(session):
    assert review_digest.week(session, NOW) == "Nothing was written or finished in the last seven days."


def test_the_day_names_what_was_written_done_and_due(book):
    said = review_digest.day(book, NOW)
    assert said.startswith("You wrote two notes today: ")
    assert "Garden shed roof" in said and "Shopping" in said
    assert "Done today: Email landlord about the leak." in said
    assert "Next: Pay phone bill (due today); Take bins out (due today); Dentist check-up (due tomorrow)." in said
    assert "Harbor launch plan" not in said


def test_the_day_with_nothing_written(session):
    assert review_digest.day(session, NOW) == "You have not written a note today."


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize("phrase", WEEK_PHRASES)
def test_the_week_phrases_reach_the_review_in_ask_and_chat(book, client, phrase, chat):
    kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
    said = _ask(client, phrase, **kw)["text"]
    assert "You wrote four notes in the last seven days" in said, said
    assert "None of these notes say anything" not in said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize("phrase", DAY_PHRASES)
def test_the_day_phrases_reach_the_review_in_ask_and_chat(book, client, phrase, chat):
    kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
    said = _ask(client, phrase, **kw)["text"]
    assert said.startswith("You wrote two notes today"), said


def test_the_digest_with_no_model_is_the_review(book, client):
    said = client.post("/insights/digest").json()["digest"]
    assert said == review_digest.week(book, NOW)
    assert "From your notes, no AI" not in said


def test_the_digest_with_a_model_gets_the_reminders_in_its_prompt(book, ai_client, fake_ollama):
    ai_client.post("/insights/digest")
    prompt = fake_ollama.chat_calls[-1][-1]["content"]
    assert "Renew passport" in prompt and "Take bins out" in prompt


def test_activity_week_is_gone():
    assert not hasattr(activity, "week")
