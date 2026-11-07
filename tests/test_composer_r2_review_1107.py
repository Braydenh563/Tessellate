"""Composer round 2, review of the builder's commits (2026-11-07): the short nth
forms, metadata words, a list named for its open items, the undo copy. Every
question runs through `composer.compose` over `_seed_r2_1107`; no model (fake
transport), fixed clock."""

from __future__ import annotations

import pytest

from tests._seed_r2_1107 import ask


# --- the short nth forms ---

@pytest.mark.parametrize(
    ("question", "said"),
    [
        ("last item in my todo", "The last item is Buy stamps (not done)."),
        ("third item in the Tokyo packing list", "The third item is Adapter."),
        ("the second item on the Tokyo packing list?", "The second item is Rail pass."),
        ("show me the first item in my todo", "The first item is Book MOT (not done)."),
        ("tell me the last item in the Tokyo packing list", "The last item is Umbrella."),
        ("give me the third thing in my todo", "The third item is Email landlord (not done)."),
    ],
)
def test_r2_the_short_nth_forms_name_the_item_without_a_what(question, said):
    assert ask(question) == said


def test_r2_a_bare_ordinal_with_no_note_named_is_left_to_the_search():
    # "first thing in the morning" names no list: it must not become the first item of the one list.
    assert "The first item is" not in ask("first thing in the morning", only=("Todo", "Jokes"))


# --- the undo copy ---

def test_r2_the_undo_copy_names_buttons_that_exist_and_a_key_that_works_outside_a_box():
    for word in ("undo", "redo"):
        got = ask(word)
        assert "status bar" in got and "toast" not in got, got
    assert "Undo on the card" in ask("untick bread"), ask("untick bread")
