"""Review fixes for composer round 3 (commit 0d32bfd1): one name for a
title-less note on every surface, name_of's mangles, the shop-and-buy ask,
a list note with an intro line, and a count of notes. Fixed clock, no model."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_frame

UNTITLED = [
    "I just missed the bus to uni and had to walk all the way in the rain.",
    "Sara likes jazz",
    "Dentist said to floss more and use the soft brush.",
    "Had design class today for prototyping",
    "Trip planning: flights to Lisbon",
    "Idea: a bike route along the river to work, about 8 km.",
    "Go to the gym at 9pm",
    "Wrote 4471 words about Amazon arrivals on Tuesday",
]


@pytest.mark.parametrize("content", UNTITLED)
def test_every_surface_names_a_title_less_note_by_name_of(content):
    from tessellate.api import chat_said

    note = {"content": content}
    name = composer_frame.name_of(note)
    assert composer_frame.short_name(note) == name
    assert composer_frame.clipped_words(note) == name.strip("“”")
    if name.startswith("“"):
        assert f"“{chat_said._closing_name(content)}”" == name


def test_a_link_to_a_title_less_note_has_its_name_never_a_date():
    from tessellate.ai import composer_notes

    line = composer_notes._item({"id": 3, "content": "Blockers: none", "created_at": "2026-11-05T10:00:00Z"}, [])
    assert "[“Blockers: none”](#/notes/3)" in line, line


@pytest.mark.parametrize(("content", "name"), [
    ("Dr. Smith said hello to everyone today ok", "“Dr. Smith said hello to everyone…”"),
    ("- [ ] buy milk, then bread", "“buy milk, then bread”"),
    ("1. first item, two", "“first item, two”"),
    ("## Heading words here", "Heading words here"),
    ("", "“An empty note”"),
    ("   \n", "“An empty note”"),
])
def test_name_of_keeps_an_abbreviation_and_drops_a_list_mark(content, name):
    assert composer_frame.name_of({"content": content}) == name


def test_a_sum_names_an_unbought_note_by_the_same_name():
    from tessellate.ai import composer_money

    class V:
        titled = False
        written = None
        note = {"content": "Went running with Sam and then home for tea"}

    assert composer_money._note_name(V) == "“Went running with Sam and then…”"  # quoted as name_of quotes it


def test_a_shop_ask_keeps_the_note_that_only_says_buy():
    from tests.test_composer_r3_1107 import say

    said = say("what do I know about shop", "# Shopping\n\n- milk\n- bread", "Need to buy new shoes for the wedding on Saturday.")
    assert "Shopping" in said and "shoes for the wedding" in said, said


INTRO_TODO = "# Todo\n\nThings I need to do before Friday.\n\n- [ ] Book MOT\n- [ ] Email landlord"
INTRO_PACKING = "# Packing\n\nFor the trip.\n\n- [ ] Passport\n- [ ] Charger"


def test_a_list_with_an_intro_line_is_a_list_to_ask_which_of():
    from tests.test_composer_r3_1107 import say

    said = say("what is on my list", INTRO_TODO, INTRO_PACKING, "Dentist on 11 November")
    assert said == "Which list: Todo or Packing?", said


def test_whats_on_my_todo_shows_a_todo_note_with_an_intro_line():
    from tests.test_composer_r3_1107 import say

    said = say("what's on my todo", INTRO_TODO, INTRO_PACKING)
    assert "Book MOT" in said and "Nothing in the notes" not in said, said


def test_how_many_of_a_thing_no_note_gives_a_figure_for_counts_the_notes_that_mention_it():
    from tests.test_composer_r3_1107 import say

    notes = ("My phone is a Pixel 8, bought in March for £549.", "Old phone: iPhone 6, given to Sam", "Phone bill is £30 a month", "# Shopping\n\n- milk")
    assert say("how many phones", *notes) == "Three of your notes mention phones."
    assert say("how many phones", notes[0], notes[3]) == "One of your notes mentions phones."
