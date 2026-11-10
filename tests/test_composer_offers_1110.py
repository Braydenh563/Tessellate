"""F12 and F4 leftovers of the 1110 composer audit, no model, clock fixed at Tuesday 10 November 2026, 09:00.

- F12: a reminder is offered only to a question about a date or a task; an offer is taken up by "yes" and dropped by "no thanks", with no second offer behind either.
- F4: bare reactions ("really?", "maybe"), "are you sure", "where did you get that", "more detail", "what was my first question" are read against the answer before, never searched; a "no" after an ack is no repair."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import commands, composer_chat, composer_suggest, composer_talk
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.entry import manager

NOW = datetime(2026, 11, 10, 9, 0)
NOTES = [
    "# Budget\n\nRent $650. Food $300. Savings $200.",
    "# Anna\n\nAnna's birthday is 3 December. Buy Anna a birthday present.",
    "# Passport\n\nRenew passport by 30 November.",
    "# Dentist\n\nCheck-up 21 November.",
    "# Exam\n\nMaths exam on Friday, revise chapters 3 and 4.",
    "# Boiler\n\nCall the plumber by Friday about the boiler.",
    "# Lisbon\n\nLisbon trip in May: the hotel is booked, still to book the flights.",
]
DENTIST = [{"question": "when is the dentist check-up", "answer": "Check-up 21 November, from your Dentist note, in 11 days."}]
LINKED = [{"question": "what do I know about anna", "answer": "Anna's birthday is 3 December. [Anna](#/notes/2)"}]


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


@pytest.fixture
def notebook(session):
    for content in NOTES:
        manager.create_entry(session, content)
    session.commit()


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


def _said(events):
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


def _turns(client, *questions):
    history, out = [], []
    for question in questions:
        text = _said(_events(client, question, history=history[-4:]))
        history.append({"question": question, "answer": text})
        out.append(text)
    return out


# --- F12: unasked reminders --------------------------------------------------------


@pytest.mark.parametrize("ask", ["how much is the budget", "what do I know about anna", "total for november"])
def test_a_question_about_neither_a_date_nor_a_task_offers_no_reminder(client, notebook, ask):
    text = _said(_events(client, ask))
    assert "emind you" not in text, text


def _gold(ask):
    from datetime import date

    from tests import _gold as gold
    from tessellate.ai import composer_digest

    fixture = gold.load()
    notes = [{"id": i + 1, "content": n["content"], "created_at": f"{n['date']}T10:00:00", "category": n["category"], "tags": n["tags"]} for i, n in enumerate(fixture["notes"])]
    return composer_digest.answer(ask, notes, today=date.fromisoformat(fixture["today"]))["text"]


@pytest.mark.parametrize("ask", ["what's the plan for Lisbon?", "what hobbies do I want to try?"])
def test_a_question_about_a_plan_a_date_or_a_wish_still_offers_a_reminder(ask):
    assert "emind you" in _gold(ask), ask


@pytest.mark.parametrize("ask", ["do I like golf?", "how much did I spend on groceries?", "What have I saved about courses & study?"])
def test_a_question_about_neither_offers_no_reminder(ask):
    assert "emind you" not in _gold(ask), ask


def test_the_weekly_spending_offer_is_taken_up():
    offer = [{"question": "q", "answer": "Rent $650.\n\nShall I remind you each week to log your spending?"}]
    sentence = composer_talk.accepted_offer("yes", offer)
    assert sentence and "log my spending" in sentence and "every week" in sentence, sentence
    got = commands.read(sentence, NOW)
    assert got and got["intent"] == "reminder" and "spending" in got["text"].lower(), got


@pytest.mark.parametrize("no", ["no", "no thanks", "nope", "not now", "No thank you", "nah"])
def test_a_no_drops_the_offer_with_one_line(no):
    offer = [{"question": "q", "answer": "Renew passport by 30 November.\n\nShall I remind you to renew passport by 30 November?"}]
    said = composer_chat.reply(no, offer)
    assert said and "hall I remind" not in said and "?" not in said and "misread" not in said, said


def test_a_no_drops_the_offer_in_the_chat(client, notebook):
    first, no = _turns(client, "what do I need to do about the boiler", "no thanks")
    assert "misread" not in no and "In your notebook" not in no and "?" not in no, no


def test_the_drop_lines_vary():
    offer = [{"question": "q", "answer": "Shall I remind you to call the plumber?"}]
    lines = {composer_chat.reply("no thanks", offer, seed=str(i)) for i in range(12)}
    assert len(lines) >= 3, lines


# --- F4: reactions ------------------------------------------------------------------


@pytest.mark.parametrize("ask", ["really?", "maybe", "and then", "hmm", "seriously", "oh really"])
def test_a_bare_reaction_is_a_line_not_a_search(ask):
    said = composer_chat.reply(ask, DENTIST)
    assert said and "newest notes" not in said and "[**" not in said, said


@pytest.mark.parametrize("ask", ["are you sure", "are you sure?", "you sure about that", "is that right"])
def test_are_you_sure_names_the_note_it_came_from(ask):
    assert "Dentist" in (composer_chat.reply(ask, DENTIST) or "")


@pytest.mark.parametrize("ask", ["where did you get that", "where did that come from", "what is your source", "how do you know that"])
def test_where_did_you_get_that_names_the_sources(ask):
    assert "Dentist" in (composer_chat.reply(ask, DENTIST) or "")
    assert "Anna" in (composer_chat.reply(ask, LINKED) or "")


def test_a_source_question_with_no_answer_before_it_says_so():
    said = composer_chat.reply("where did you get that", [])
    assert said and "nothing" in said.lower(), said


def test_more_detail_points_at_the_note_it_came_from():
    said = composer_chat.reply("more detail", LINKED)
    assert said and "#/notes/2" in said, said


def test_what_was_my_first_question():
    history = [{"question": "when is the dentist check-up", "answer": "a"}, {"question": "and the passport", "answer": "b"}]
    assert "dentist check-up" in (composer_chat.reply("what was my first question", history) or "")
    assert composer_chat.reply("what was my first question", []) is not None


def test_the_reactions_in_the_chat_never_reach_search(client, notebook):
    turns = _turns(client, "when is the dentist check-up", "really?", "where did you get that", "are you sure", "what was my first question", "more detail")
    for text in turns[1:]:
        assert "newest notes" not in text and "None of your notes" not in text and "I found no mention" not in text and "Not sure what you mean" not in text, text
    assert "Dentist" in turns[2]


def test_a_no_after_an_ack_is_not_a_repair(client, notebook):
    _hi, _thanks, no = _turns(client, "when is the dentist check-up", "thanks", "no")
    assert "misread" not in no and "read “thanks”" not in no, no


def test_a_no_after_a_notes_answer_is_still_a_repair(client, notebook):
    _answer, no = _turns(client, "when is the dentist check-up", "no")
    assert "Sorry" in no, no


def test_the_stressed_note_chip(client, notebook):
    events = _events(client, "i'm stressed about the exam")
    asks = [a for e in events if e.get("type") == "offer" for a in (e.get("offer") or {}).get("asks", [])]
    assert len(asks) == 1 and asks[0].startswith("What do my notes say about") and "exam" in asks[0], asks


def test_no_chip_when_no_note_has_the_subject(client, notebook):
    events = _events(client, "i'm stressed about the visa")
    asks = [a for e in events if e.get("type") == "offer" for a in (e.get("offer") or {}).get("asks", [])]
    assert not any("visa" in a for a in asks), asks


def test_give_me_the_short_version_with_nothing_to_shorten():
    got = composer_suggest.unknown_action("give me the short version", [])
    assert got and "short" in got["text"].lower() and "not sure how to do that" not in got["text"], got
