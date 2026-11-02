"""Audit 1030 A13 to A17: the act reader's leads, tails and note links."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tessellate.ai import commands
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 10, 0)

LEADS = ["", "please ", "can you ", "I'd like you to ", "I want you to ", "I need you to ", "go ahead and ", "just ", "kindly ", "ok so ", "also ",
         "if you could ", "when you can, ", "pls ", "plz ", "can u "]
TAILS = ["", " please", " for me", " thanks", " now", " asap", " if you can", " thank you so much"]
BASES = [
    ("remind me to call mum on friday", "reminder"),
    ("mark the passport as done", "complete"),
    ("tick off the charger", "complete"),
    ("delete the old wifi note", "delete"),
    ("pin the dentist note", "pin"),
    ("tag the gym note with fitness", "tag"),
]


@pytest.mark.parametrize("lead", LEADS)
@pytest.mark.parametrize("tail", TAILS)
@pytest.mark.parametrize(("base", "intent"), BASES)
def test_every_lead_and_tail_reads_the_same_act(lead, tail, base, intent):
    found = commands.read_typed(f"{lead}{base}{tail}", NOW)
    assert found is not None and found["intent"] == intent, (lead, base, tail, found)
    if intent == "reminder":
        assert found["text"] == "Call mum"


def test_asap_is_when_never_the_title():
    found = commands.read_typed("remind me to call mum asap", NOW)
    assert found["text"] == "Call mum"
    assert found["time_given"] is True and found["due_at"] == NOW + timedelta(minutes=10)
    again = commands.read_typed("remind me to call mum as soon as possible", NOW)
    assert again["text"] == "Call mum"
    #: A day said wins over asap.
    assert commands.read_typed("remind me to call mum tomorrow asap", NOW)["due_at"].day == 31


def test_one_common_word_in_a_body_is_not_the_source_of_a_reminder(session):
    manager.create_entry(session, "# Lentil soup\n\nMum's recipe: red lentils, stock, cumin.")
    manager.create_entry(session, "# Dentist\n\nCheck-up booked.")
    session.commit()
    plain = commands.plan(session, commands.read_typed("remind me to call mum tomorrow", NOW))
    assert "note_id" not in plain["card"]["steps"][0]["arguments"]
    titled = commands.plan(session, commands.read_typed("remind me to call the dentist tomorrow", NOW))
    assert "note_id" in titled["card"]["steps"][0]["arguments"]


def test_a_title_ending_in_the_assistants_name_is_not_an_address():
    """A17: "tell me about project atlas" keeps its last word when the notes hold the title."""
    from tessellate.ai import vocative

    held = lambda phrase: phrase == "project atlas"  # noqa: E731
    kept = vocative.split("tell me about project atlas", in_notes=held)
    assert kept.question == "tell me about project atlas" and not kept.names
    called = vocative.split("what is the plan for friday atlas", in_notes=held)
    assert called.names == ["atlas"] and called.question == "what is the plan for friday"


def test_looser_reminder_cancel_and_done_forms_a15():
    """A15: ping/alert/schedule/make-me/I-need openers, and the looser cancel and done leads."""
    from datetime import datetime

    from tessellate.ai import commands, task_acts

    now = datetime(2026, 10, 30, 10, 0)
    for question, text in (
        ("ping me about the dentist on 3 november", "The dentist"),
        ("alert me at 6pm to take the bins out", "Take the bins out"),
        ("make me a reminder to book flights on 14 november", "Book flights"),
        ("i need a reminder to renew rego before 3 december", "Renew rego"),
    ):
        found = commands.read(question, now)
        assert found and found["intent"] == "reminder" and found["text"] == text, question
    assert not commands.read("ping me", now)
    for question, about in (
        ("get rid of the reminder about the parcel", "parcel"),
        ("i don't need the reminder to call the bank any more", "call the bank"),
        ("stop reminding me about the dentist", "dentist"),
        ("never mind the reminder to buy milk", "buy milk"),
    ):
        assert task_acts.read_cancel(question)["about"] == about, question
    assert task_acts.read_cancel("clear my cache") is None
    assert task_acts.read_complete("finish the reminder to call mum")["about"] == "call mum"
    assert task_acts.read_complete("i finished the report") is None
