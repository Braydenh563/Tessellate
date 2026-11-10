"""R9-12 (composer audit round 9): acts. "I've booked X" ticks, an untick says so, a daily reminder repeats,
a list that exists takes the items, a line that is already there is not added twice, "add to X: words" names its
note, a checklist is named for what it is for. Seed: `tests/_seed_r9_1109.py`; Chat mode."""

from __future__ import annotations

import pytest
from sqlalchemy import select

import tests._seed_r9_1109 as sd
from tessellate.core.database import Entry, Reminder


@pytest.fixture
def act(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch, chat=True)
    return lambda q: go(q)[0]


def _note(session, title):
    session.expire_all()
    rows = session.scalars(select(Entry).where(Entry.content.like(f"# {title}%"))).all()
    return rows[-1].content if rows else None


def test_ive_booked_ticks_the_matching_task(act, session):
    assert "ticked off" in act("I've booked the car service")
    assert "[x] book car service" in _note(session, "Todo")


def test_a_past_deed_with_no_task_is_not_an_act(act, session):
    before = _note(session, "Todo")
    act("I've booked the dentist")
    assert _note(session, "Todo") == before


def test_untick_says_unticked(act, session):
    text = act("untick coffee beans")
    assert text == "Unticked “coffee beans” (Shopping list)."
    assert "[ ] coffee beans" in _note(session, "Shopping list")


def test_a_daily_reminder_repeats_and_says_so(act, session):
    text = act("remind me to feed Doug every day at 8am")
    assert "every day" in text
    assert session.scalars(select(Reminder)).all()[-1].recurring == "daily"


def test_a_shopping_list_that_exists_takes_the_items(act, session):
    act("make a shopping list with flour, yeast and salt")
    assert _note(session, "Shoppinglist") is None
    held = _note(session, "Shopping list")
    assert all(w in held.lower() for w in ("flour", "yeast", "salt"))
    assert session.scalars(select(Entry).where(Entry.content.like("# Shopping list%"))).all().__len__() == 1


def test_an_item_already_open_is_not_added_twice(act, session):
    text = act("add oat milk to my shopping list")
    assert text == "Oat milk is already on your Shopping list."
    assert _note(session, "Shopping list").lower().count("oat milk") == 1


@pytest.mark.parametrize("ask", [
    "append to the Q4 report: churn figure checked with finance",
    "add to the Q4 report: churn figure checked with finance",
])
def test_add_to_a_named_note_with_a_colon(act, session, ask):
    text = act(ask)
    assert "could not tell" not in text
    assert "Q4 report" in text


def test_add_to_my_journal_with_a_colon(act):
    assert "could not tell" not in act("add to my journal: started the new Spanish book")


def test_a_checklist_for_a_place_is_named_for_it(act, session):
    act("create a checklist for the kitchen: clear cupboards, move fridge, cover floor")
    held = _note(session, "Kitchen checklist")
    assert held and "- [ ] Clear cupboards" in held and "- [ ] Cover floor" in held

