"""Audit 1028 E25: "create a note called X with Y" is a title (X) and a body (Y),
never the whole phrase as the body. Several phrasings of the same shape."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands

NOW = datetime(2026, 11, 2, 9, 0)


@pytest.mark.parametrize(
    ("ask", "content"),
    [
        ('create a note called "Shopping" with milk, eggs and bread', "Shopping\nMilk, eggs and bread"),
        ("create a note called Shopping with milk, eggs and bread", "Shopping\nMilk, eggs and bread"),
        ("make a note titled 'Trip ideas' saying book flights first", "Trip ideas\nBook flights first"),
        ("new note called Gym that says squats on Monday", "Gym\nSquats on Monday"),
        ("make a note named Garden containing tomatoes and basil", "Garden\nTomatoes and basil"),
        ('add a note called "Passwords": the shed code is 4471', "Passwords\nThe shed code is 4471"),
        ('create a new note called "Reading list" with Dune, Emma', "Reading list\nDune, Emma"),
        ('write a note called “Plan” saying call the bank', "Plan\nCall the bank"),
        ("create a note called Shopping", "Shopping"),
        ('create a note called "Shopping"', "Shopping"),
    ],
)
def test_called_x_with_y_is_a_title_and_a_body(ask, content):
    parsed = commands.parse(ask, NOW)
    assert parsed is not None and parsed.args["intent"] == "new_note", ask
    assert parsed.args["content"] == content


@pytest.mark.parametrize(
    ("ask", "content"),
    [
        ("make a note: buy milk with oat flour", "Buy milk with oat flour"),
        ("note that the boiler code is 4471", "The boiler code is 4471"),
        ("jot down call the bank about the card", "Call the bank about the card"),
    ],
)
def test_a_note_with_no_name_keeps_its_words_whole(ask, content):
    parsed = commands.parse(ask, NOW)
    assert parsed is not None and parsed.args["content"] == content


def test_the_card_says_the_name_and_the_words_on_one_line(session):
    parsed = commands.parse('create a note called "Shopping" with milk, eggs and bread', NOW)
    planned = commands._plan_new_note(session, parsed.args)
    assert planned["line"] == "Make a new note “Shopping”: Milk, eggs and bread."
    assert planned["card"]["steps"][0]["arguments"]["content"] == "Shopping\nMilk, eggs and bread"
