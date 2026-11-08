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
