"""Composer audit 2026-11-10, F3: an instruction after a list or an act binds to what that answer showed.

"remove milk" after the shopping list is a line of the list (never the bin for the note
"Shopping"); "delete the first one" after the reminders table is that reminder; "add butter",
"make it 6" and "add socks to it" act on the list, reminder and note just shown. A destructive
word that does not single out one item asks which. No model; clock fixed at Tuesday 10 November
2026, 09:00."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.ai import composer_talk, follow_items
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core.database import Entry, Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 10, 9, 0)
LIST = "Your note **Shopping** has none of its three checklist items done:\n\n- [ ] Milk\n- [ ] Eggs\n- [ ] Bread"
TABLE = "You have one reminder waiting.\n\n| Reminder | When |\n| --- | --- |\n| Call anna | Tuesday 10 November at 6pm |\n\n[Open Reminders](#/reminders)"
TABLE_TWO = TABLE.replace("one reminder", "two reminders").replace("\n\n[Open", "\n| Pay rent | Friday 13 November at 9am |\n\n[Open", 1)
MADE = "All set, created “Packing list” in Uncategorised."
SET = "Got it, I will remind you tomorrow at 5pm: call anna."


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _shopping(session):
    return manager.create_entry(session, "# Shopping\n\n- [ ] Milk\n- [ ] Eggs\n- [ ] Bread\n")


def _body(session, entry_id):
    session.expire_all()
    return session.get(Entry, entry_id).content


def _reminder(session, text="Call anna"):
    row = Reminder(text=text, due_at=datetime(2026, 11, 10, 18, 0))
    session.add(row)
    session.commit()
    return row


def _live(session):
    session.expire_all()
    return [r.text for r in session.scalars(select(Reminder).where(Reminder.deleted_at.is_(None))).all()]


def _turn(client, question, answer):
    return _ask(client, question, history=[{"question": "q", "answer": answer}])["text"]


def _waits(client, question, answer):
    """The card an instruction after a list leaves waiting. Intent moved (owner, 2026-11-10,
    HANDOVER "Consent for every act"): these acts used to run at once with Undo; none does now."""
    events = _ask(client, question, history=[{"question": "q", "answer": answer}])
    card = next(e for e in events["act"] if not e.get("done"))
    return card, [{"question": question, "answer": events["text"], "pending_act": card["label"], "pending_steps": card["steps"], "pending_skipped": card["skipped"]}]


# --- the repros, through /chat/stream -----------------------------------------------------------


def test_remove_milk_takes_the_line_off_the_list_and_never_bins_the_note(client, session):
    note = _shopping(session)
    card, history = _waits(client, "remove milk", LIST)
    assert "bin" not in card["label"].lower() and "Milk" in _body(session, note.id), "nothing changes before consent"
    _ask(client, "yes", history=history)
    assert "Milk" not in _body(session, note.id)
    assert "Eggs" in _body(session, note.id) and session.get(Entry, note.id).deleted_at is None


def test_add_butter_adds_a_line_to_the_list_shown(client, session):
    note = _shopping(session)
    said = _turn(client, "add butter", LIST)
    assert "utter" in said and "Shopping" in said and "could not tell" not in said
    assert "utter" not in _body(session, note.id), "an add waits for Confirm"


def test_and_cheese_adds_a_line_too(client, session):
    _shopping(session)
    said = _turn(client, "and cheese", LIST)
    assert "heese" in said and "Shopping" in said and "did not catch" not in said


def test_delete_the_first_one_cancels_that_reminder_and_leaves_the_note(client, session):
    ramen = manager.create_entry(session, "Call with Anna wants to try the new ramen place.")
    _reminder(session)
    card, history = _waits(client, "delete the first one", TABLE)
    assert "bin the note" not in card["label"].lower() and _live(session) == ["Call anna"], "nothing changes before consent"
    _ask(client, "go ahead", history=history)
    assert _live(session) == [] and session.get(Entry, ramen.id).deleted_at is None


def test_make_it_6_moves_the_reminder_just_set(client, session):
    row = _reminder(session)
    card, history = _waits(client, "make it 6", SET)
    session.expire_all()
    assert session.get(Reminder, row.id).due_at.replace(tzinfo=None) == datetime(2026, 11, 10, 18, 0), "nothing changes before consent"
    _ask(client, "sure", history=history)
    session.expire_all()
    assert session.get(Reminder, row.id).due_at.replace(tzinfo=None) == datetime(2026, 11, 11, 18, 0), card["label"]


def test_add_socks_to_it_after_a_new_note(client, session):
    manager.create_entry(session, "# Packing list\n\n- [ ] Passport\n")
    said = _turn(client, "add socks to it", MADE)
    assert "ocks" in said and "Packing list" in said and "Which note" not in said


def test_rename_it_after_a_new_note(client, session):
    manager.create_entry(session, "# Packing list\n\n- [ ] Passport\n")
    said = _turn(client, "rename it to Japan packing", MADE)
    assert "Japan packing" in said and "Which note" not in said


# --- safety: an item that is not singled out asks which, and nothing is binned -------------------


def test_delete_it_over_two_reminders_asks_which(client, session):
    _reminder(session)
    _reminder(session, "Pay rent")
    said = _turn(client, "delete it", TABLE_TWO)
    assert "Which one" in said and "Call anna" in said and "Pay rent" in said
    assert sorted(_live(session)) == ["Call anna", "Pay rent"]


def test_an_item_not_on_the_list_asks_which_and_bins_nothing(client, session):
    note = _shopping(session)
    said = _turn(client, "remove chocolate", LIST)
    assert "Which one" in said and "Milk" in said and "bin" not in said.lower()
    assert session.get(Entry, note.id).deleted_at is None and "Milk" in _body(session, note.id)


def test_an_ordinal_past_the_end_asks_which(client, session):
    _shopping(session)
    assert "Which one" in _turn(client, "delete the seventh one", LIST)


def test_two_reminders_with_one_name_asks_which(client, session):
    _reminder(session)
    _reminder(session)
    said = _turn(client, "delete the first one", TABLE_TWO.replace("Pay rent", "Call anna"))
    assert "Which one" in said and len(_live(session)) == 2


def test_a_note_named_as_a_note_is_still_binned(client, session):
    _shopping(session)
    manager.create_entry(session, "# Boiler\n\nService in March.")
    said = _turn(client, "delete the boiler note", LIST)
    assert "Boiler" in said and "bin" in said.lower()


# --- the reading, unit ---------------------------------------------------------------------------


@pytest.mark.parametrize("question, answer, expect", [
    ("remove milk", LIST, "cancel the list item Milk on the Shopping list"),
    ("delete the second one", LIST, "cancel the list item Eggs on the Shopping list"),
    ("take eggs off the list", LIST, "cancel the list item Eggs on the Shopping list"),
    ("delete the first one", TABLE, "cancel the reminder Call anna"),
    ("delete it", TABLE, "cancel the reminder Call anna"),
    ("add butter", LIST, "add butter to the Shopping note"),
    ("add butter to it", LIST, "add butter to the Shopping note"),
    ("and cheese", LIST, "add cheese to the Shopping note"),
    ("make it 6", SET, "move the reminder call anna to tomorrow at 6pm"),
    ("actually 9am", SET, "move the reminder call anna to tomorrow at 9am"),
    ("add socks to it", MADE, "add socks to the Packing list note"),
])
def test_the_reading(question, answer, expect):
    assert composer_talk.accepted_offer(question, [{"question": "q", "answer": answer}]) == expect


NOTHING = "Nothing in your notes about that."


@pytest.mark.parametrize("question, answer", [
    ("remove the milk note", LIST), ("delete the boiler note", LIST), ("remove all of them", LIST), ("and what about the dentist", LIST),
    ("add butter", NOTHING), ("remove milk", NOTHING), ("add a reminder to call anna", LIST), ("make it 6", LIST), ("and cheese?", LIST),
    ("delete it", NOTHING),
])
def test_left_alone(question, answer):
    assert follow_items.read(question, [{"question": "q", "answer": answer}]) == (None, None)


def test_the_ordinal_counts_against_the_list_shown_some_turns_back():
    history = [{"question": "a", "answer": LIST}, {"question": "which is most urgent", "answer": "Bread, for tonight."}]
    assert follow_items.read("mark the first one done", history)[0] == "tick Milk on the Shopping list"
    assert follow_items.read("mark the first one done", history[:1])[0] is None, "the list is right there: task_acts counts it"
