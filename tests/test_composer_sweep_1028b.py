"""Sweep 1028b W1: an act that names its own note never inherits the chat's
follow-on subject ("delete the note about lentil soup" after turns about the
budget searched "budget note about lentil soup"). The class: every act the
pronoun reader serves, with every phrase that names a note."""

from __future__ import annotations

from datetime import datetime

from tessellate.ai import reading

NOW = datetime(2026, 10, 28, 10, 0)
TURNS = [{"text": "find my budget note"}, {"text": "what did I write about travel"}]


def test_an_act_that_names_its_own_note_stands_alone():
    for verb in ("delete", "pin", "unpin", "open", "bin", "summarise", "rename", "move", "tag"):
        for phrase in ("the note about lentil soup", "that note about lentil soup", "the note called Lentil soup"):
            assert reading.follow(f"{verb} {phrase}", TURNS, NOW) is None, (verb, phrase)


def test_the_reading_keeps_only_its_own_subject():
    for text in ("delete the note about lentil soup", "pin the note about lentil soup", "move the note about lentil soup to Work",
                 "rename the note about lentil soup to Soup"):
        got = reading.read(text, now=NOW, context={"turns": TURNS})
        assert got.slots.get("follows") is None, text
        assert "budget" not in str(got.slots).lower(), text


def test_a_bare_pronoun_still_follows_and_what_about_still_swaps():
    assert reading.follow("and delete it", [{"text": "find my budget note"}], NOW) == ("delete the budget note", "pronoun")
    assert reading.follow("delete the note", [{"text": "find my budget note"}], NOW) is not None
    assert reading.follow("what about the gym note", [{"text": "pin the dentist note"}], NOW) is not None
