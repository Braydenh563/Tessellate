"""A number asked for by its noun ("what is the table number") is the sentence that holds
it, or "None of your notes give a table number", never an unrelated line from a note that
merely mentions dinner or a booking (composer-r6, R3-2 residue). Seed: `tests/_seed_1031c.py`."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import composer_property
from tessellate.entry import manager

DINNER = "Dinner at Il Forno on Friday at 7:30pm. Booked for four people under Sara."


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    manager.create_entry(session, DINNER)
    session.commit()
    return seed_c.asker(client, monkeypatch)


@pytest.mark.parametrize("said, key", [
    ("what is the table number", "table"), ("what's the table number for dinner", "table"), ("what is the room number", "room"),
    ("what is my booking number", "booking"), ("what is the flight number", "flight"), ("seat number?", "seat"), ("what is the locker no.", "locker"),
])
def test_a_numbered_thing_is_its_own_property(said, key):
    assert composer_property.asked(said) == key


@pytest.mark.parametrize("said", ["what is the table number", "what's the table number for dinner", "what is the booking number", "what is the room number"])
def test_no_note_with_the_number_says_so_not_an_unrelated_line(go, said):
    text, _ = go(said)
    noun = next(w for w in composer_property.NUMBERED if w in said)
    assert text == f"None of your notes give a {noun} number.", text


def test_the_note_that_holds_it_leads(go, session):
    manager.create_entry(session, "# Wedding\n\nTable 4 for the Jones family.")
    session.commit()
    text, _ = go("what is the table number")
    assert text.startswith("Table 4 for the Jones family"), text


def test_a_phone_number_is_still_a_phone_number(go, session):
    manager.create_entry(session, "# Dentist surgery\n\nPhone 020 7946 0011. Open 9 to 5.")
    session.commit()
    text, _ = go("what is the number for the dentist")
    assert "020 7946 0011" in text, text
