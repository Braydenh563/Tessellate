"""Audit 1028 E67: the Next chips on a due answer come from its items (open the
note, set a reminder for the item) and each is an ask the app can act on, not
one fixed "Plan my week". Fixed clock: Monday 2 November 2026."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import acts, composer_plan, composer_study

NOW = datetime(2026, 11, 2, 9, 0)
NOTES = [
    {"id": 7, "content": "# Dentist\n\nCheck-up on Thursday 5 November at 3pm.", "created_at": datetime(2026, 10, 30, 9, 0)},
    {"id": 8, "content": "# Essay\n\nHand in the history essay by Friday 6 November.", "created_at": datetime(2026, 10, 30, 10, 0)},
]
REMINDER = {"text": "Call the bank", "due_at": datetime(2026, 11, 3, 9, 0), "done": False}


def _reply(question, notes=NOTES, reminders=()):
    ctx = composer_study.Ctx(question=question, notes=list(notes), now=NOW, reminders=list(reminders))
    reply = composer_plan.answer(ctx)
    assert reply is not None, question
    return reply


@pytest.mark.parametrize("question", ["what is due this week", "what's due this week", "anything due this week?", "what do I have on this week"])
def test_chips_come_from_the_items(question):
    asks = _reply(question).asks
    assert any(a.lower().startswith("open ") for a in asks), asks
    assert any(a.lower().startswith("remind me") for a in asks), asks
    assert "Plan my week" in asks and len(asks) <= 3, asks


def test_the_open_chip_names_a_note_that_is_in_the_answer():
    reply = _reply("what is due this week")
    opened = next(a for a in reply.asks if a.lower().startswith("open "))
    title = opened.removeprefix("Open the ").removesuffix(" note")
    assert title in ("Dentist", "Essay") and f"[{title}]" in reply.text


@pytest.mark.parametrize("ask_index", [0, 1])
def test_every_chip_is_an_ask_the_app_can_act_on(ask_index):
    asks = [a for a in _reply("what is due this week").asks if a != "Plan my week"]
    chip = asks[ask_index]
    assert acts.parse(chip, NOW) is not None, chip
    assert "\u2014" not in chip and "!" not in chip


def test_a_reminder_item_is_not_offered_a_reminder_again():
    asks = _reply("what is due this week", notes=[], reminders=[REMINDER]).asks
    assert not any(a.lower().startswith("remind me") for a in asks), asks


def test_a_single_day_answer_has_chips_too():
    asks = _reply("what is due on Thursday").asks
    assert asks and all(a.strip() for a in asks)


def test_no_items_no_item_chips():
    reply = composer_plan.answer(composer_study.Ctx(question="what is due this week", notes=[], now=NOW, reminders=[]))
    assert reply is None or not any(a.lower().startswith(("open ", "remind me")) for a in reply.asks)
