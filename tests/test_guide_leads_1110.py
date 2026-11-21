"""G5 leftovers (g45-1110): the Guide with no model says what the app is, and a path that is
a sentence is not printed after "It's in"."""

from __future__ import annotations

from tessellate.ai import help_chat
from tests._help_text import after_path


def _said(question: str, tab: str | None = None) -> str:
    return help_chat.offline_answer(question, tab)["content"]


def test_what_is_tessellate_says_what_it_is_not_how_many_tabs():
    lead = after_path(_said("what is tessellate")).split("\n\n")[0]
    assert lead.startswith("Tessellate is a notebook"), lead
    assert "seven tabs" not in lead


def test_where_is_the_bin_does_not_print_a_sentence_after_its_in():
    lead = _said("where is the bin").split("\n\n")[0]
    assert lead.startswith("It's in the bin, reached with"), lead
    assert "Include the bin" in lead and "Ctrl+Z" in lead


def test_an_ordinary_place_is_still_its_in():
    assert _said("where is simple mode").startswith("It's in Settings, General, Simple mode."), _said("where is simple mode")
