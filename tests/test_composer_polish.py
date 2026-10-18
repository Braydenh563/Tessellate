"""The composer's own words get a deterministic grammar pass (INBOX 1299,
the owner: "small grammar issues like that ... can we use the vendored
grammar repos like harper"): lead capitals, weekday and month names, and the
missing article in a closed list of verb-plus-place phrases. Closed lists, no
model, and never inside words the person wrote (a quoted note keeps its
exact words)."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer_digest
from tessellate.ai.composer_digest import polish

TODAY = date(2026, 10, 12)


@pytest.mark.parametrize(("slip", "fixed"), [
    ("tuesday you go to the gym.", "Tuesday you go to the gym."),
    ("You are free on tuesday and friday.", "You are free on Tuesday and Friday."),
    ("Your exam is in october.", "Your exam is in October."),
    ("you planned a trip. next, tuesday is the day.", "You planned a trip. Next, Tuesday is the day."),
    ("On 14 may you booked it.", "On 14 May you booked it."),
    ("It runs from may 3 to may 9.", "It runs from May 3 to May 9."),
    ("**Plan:** you go to gym on tuesday.", "**Plan:** you go to the gym on Tuesday."),
    ("You go to gym.", "You go to the gym."),
    ("You went to gym on monday and are heading to supermarket after.", "You went to the gym on Monday and are heading to the supermarket after."),
    ("You need to go to dentist tomorrow.", "You need to go to the dentist tomorrow."),
    ("You are going back to library today.", "You are going back to the library today."),
])
def test_the_slips_are_fixed(slip, fixed):
    assert polish(slip) == fixed


@pytest.mark.parametrize("text", [
    "You may go to the gym.",
    "You march to the beat.",
    "You go to the gym.",
    "You go to school and to work, then to bed.",
    "You go to gym class on Tuesday.",
    "You go to church and to hospital.",
    "You head to Gym Shark HQ.",
    "You use a bike, e.g. a red one, etc. and 5 p.m. tomorrow.",
    "It is 3.5 km, then 5 p.m. tomorrow.",
    "Your email is tuesday@example.com and the file is notes-friday.txt.",
    "You like iPhone and eBay.",
])
def test_what_is_already_right_is_not_touched(text):
    assert polish(text) == text


def test_quoted_words_keep_their_exact_spelling():
    said = 'The picture reads “go to gym tuesday” and you wrote "see you in october".'
    assert polish(said) == said
    mixed = 'you read “go to gym tuesday”; tuesday you go to gym.'
    assert polish(mixed) == 'You read “go to gym tuesday”; Tuesday you go to the gym.'


def test_kept_phrases_are_the_notes_own_words():
    """A joke or a quote is said whole: its sentence is passed as kept."""
    line = "**Joke:** why did tuesday go to gym"
    assert polish(line, keep=["why did tuesday go to gym"]) == line


def test_a_block_quote_and_a_link_are_left_alone():
    assert polish("> go to gym on tuesday") == "> go to gym on tuesday"
    link = "See [go to gym tuesday](https://example.com/go-to-gym-tuesday) first."
    assert polish(link) == link


def test_the_pass_is_idempotent():
    once = polish("tuesday you go to gym.")
    assert polish(once) == once


def test_an_answer_goes_through_the_pass():
    notes = [
        {"id": 1, "content": "Gym: I go to gym on tuesday and friday after uni", "created_at": "2026-10-01T10:00:00", "category": "Health", "tags": []},
        {"id": 2, "content": "Gym: went to gym, did legs", "created_at": "2026-10-08T10:00:00", "category": "Health", "tags": []},
    ]
    result = composer_digest.answer("what do I do at the gym?", notes, today=TODAY)
    assert result is not None
    text = result["text"]
    assert "go to gym" not in text and "went to gym" not in text and "tuesday" not in text, text


def test_a_joke_note_is_said_as_the_person_saved_it():
    notes = [
        {"id": 1, "content": "Joke: why did the chicken go to gym on tuesday", "created_at": "2026-10-01T10:00:00", "category": "Jokes", "tags": ["joke"]},
    ]
    result = composer_digest.answer("what jokes have I saved?", notes, today=TODAY)
    assert result is not None
    assert "go to gym on tuesday" in result["text"], result["text"]
