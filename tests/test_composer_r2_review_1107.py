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


# --- a metadata word is not a word a note leaves out ---

@pytest.mark.parametrize("question", ["do I have notes without tags", "show me notes without a title", "which notes have no category", "notes without links"])
def test_r2_a_metadata_word_is_never_a_word_the_notes_leave_out(question):
    got = ask(question)
    assert "do not mention" not in got and "mention tags" not in got and "mention a title" not in got, got


# --- the open items of the list named ---

@pytest.mark.parametrize("question", ["what is not done in Todo", "what's not done in my todo", "what is unticked on the Todo list"])
def test_r2_open_items_of_the_list_named(question):
    got = ask(question)
    assert got.startswith("3 still to do on Todo:"), got
    assert "Book MOT" in got and "Pay council tax" not in got and "coriander" not in got, got


def test_r2_open_items_of_another_list_named():
    got = ask("what is not done in the Lisbon packing list")
    assert got.startswith("3 still to do on Lisbon packing list:") and "Book MOT" not in got, got
