"""Composer stress run 2026-10-30, the informal classes: shorthand and a
spoken repair ("whens dentist now no the NEW one"), a total with no verb
("how much desk all up after that money back thing"), a count of ticked
items, and a question whose everyday verb ("meet") outranked its noun."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai.composer_lists import clean
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)
NOTES = [
    ("Tap repair", "2026-09-18", ["home", "plumber"], "Paid $42 for the plumber to fix the kitchen tap. Settled, no reimbursement expected."),
    ("Sam at work", "2026-09-02", ["work"], "Sam Patel is my manager at Northbank Studio. We meet on Thursdays."),
    ("Secondhand desk", "2026-10-10", ["desk", "home"], "Paid AUD $180 for the desk. The listing said $200, but I negotiated."),
    ("Desk partial refund", "2026-10-12", ["desk", "refund"], "Seller refunded AUD $30 because a drawer runner was broken."),
    ("Dentist booking", "2026-10-13", ["dentist"], "Dentist appointment booked for 3 November at 9 am. Routine check-up."),
    ("Dentist rescheduled", "2026-10-27", ["dentist"], "Moved the dentist appointment from 3 November at 9 am to 4 November at 10:30 am. Old slot cancelled."),
    ("", "2026-10-29", ["groceries", "checklist"], "- [x] Milk\n- [ ] Oats\n- [x] Red lentils"),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for title, day, tags, body in NOTES:
        entry = manager.create_entry(session, f"# {title}\n\n{body}" if title else body, tags=tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(day + "T09:00:00")
    session.commit()

    def go(question: str) -> str:
        text = ""
        with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
            for line in response.iter_lines():
                if line.strip() and (event := json.loads(line))["type"] == "answer":
                    text += event["delta"]
        return text

    return go


@pytest.mark.parametrize(("typed", "read"), [
    ("whens dentist now no the NEW one", "when's dentist now"),
    ("wheres the meeting, I mean the moved one?", "where's the meeting now"),
    ("whats on friday", "what's on friday"),
    ("how is it", "how is it"),
])
def test_shorthand_and_a_repair_read_as_the_plain_question(typed, read):
    assert clean(typed) == read


def test_a_repaired_ask_for_the_new_one_leads_with_the_moved_slot(ask):
    said = ask("whens dentist now no the NEW one")
    assert "to 4 November at 10:30 am" in said.split("\n")[0], said


@pytest.mark.parametrize("question", ["how much desk all up after that money back thing", "how much desk altogether"])
def test_a_total_with_no_verb_takes_off_the_refund(ask, question):
    said = ask(question)
    assert "$180" in said and "$150 net" in said, said
    assert "$42" not in said, said


@pytest.mark.parametrize(("question", "lead"), [
    ("how many grocery items are checked off", "Two of three are ticked off on"),
    ("how many things on my grocery list are still open", "One of three is still open on"),
])
def test_a_checklist_count_names_its_items(ask, question, lead):
    said = ask(question)
    assert said.startswith(lead), said
    assert ("Milk and Red lentils" in said) if "Two" in lead else ("Oats" in said), said


def test_the_noun_outranks_an_everyday_verb(ask):
    said = ask("how did we meet the plumber")
    assert "plumber" in said.split("\n")[0], said
    assert "Thursdays" not in said.split("\n")[0], said
