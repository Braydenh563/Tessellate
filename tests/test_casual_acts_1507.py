"""INBOX 1507: "i wanna make a note" with no model got "You previously noted: ..."
over a social skills guide.

Two gaps, each a class: a wish or a request said casually ("i wanna", "can i",
"lemme", "help me") was not taken off the front, so the act under it was never
read; and an act with nothing to write ("make a note", "add a reminder") was
not an act at all, so it fell to a search of the notes. A bare act now asks for
its words, the way a reminder with only a time already did (audit 1028 E26)."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 1, 9, 0)

LEADS = ("i wanna ", "i wana ", "i want to ", "i'd love to ", "can i ", "could i ", "lemme ", "let me ",
         "i need to ", "help me ", "i gotta ", "i'm gonna ", "im gonna ", "wanna ")


@pytest.mark.parametrize("lead", LEADS)
def test_a_casual_lead_comes_off_the_act_under_it(lead):
    found = commands.read(f"{lead}make a note saying buy milk", NOW)
    assert found == {"intent": "new_note", "content": "Buy milk"}, lead


@pytest.mark.parametrize("said", ["make a note", "i wanna make a note", "can i make a note?", "new note",
                                  "take a note please", "write something down", "lemme jot something down"])
def test_a_note_with_nothing_to_say_is_still_a_note(said):
    found = commands.read(said, NOW)
    assert found is not None and found["intent"] == "new_note" and found.get("no_subject"), said


@pytest.mark.parametrize("said", ["set a reminder", "i wanna add a reminder", "make a reminder", "new reminder"])
def test_a_reminder_with_nothing_said_is_still_a_reminder(said):
    found = commands.read(said, NOW)
    assert found is not None and found["intent"] == "reminder" and found.get("no_subject") == "", said


def test_a_lead_does_not_turn_a_question_into_an_act():
    assert commands.read("let me know what I wrote about the gym", NOW) is None
    assert commands.read("can i see what I wrote about the gym", NOW) is None


def test_with_no_model_a_bare_note_asks_what_it_should_say(client):
    client.post("/entries", json={"content": "Ice breakers: if you were a spice, which one would you be?"})
    text = _ask(client, "i wanna make a note", use_tools=True)["text"]
    assert text.startswith("What should the note say"), text
    assert "previously noted" not in text


def test_with_no_model_a_bare_reminder_asks_what_and_when(client):
    text = _ask(client, "i wanna add a reminder", use_tools=True)["text"]
    assert text.startswith("What should I remind you about"), text


def test_with_no_model_a_casual_note_with_words_is_made(client):
    text = _ask(client, "i wanna make a note saying buy oat milk", use_tools=True)["text"]
    assert "Buy oat milk" in text and "previously noted" not in text
