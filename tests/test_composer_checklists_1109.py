"""A kind of note named with no "notes" ("list my checklists", D22) is the kind
question "which notes have checklists", not a search for the word "checklists"
that answered with two unrelated notes. Seed: `tests/_seed_1031c.py`."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import composer_lists


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


@pytest.mark.parametrize("said", [
    "list my checklists", "list checklists", "show my checklists", "what checklists do I have", "which checklists do I have",
    "do I have any checklists", "give me all my checklists", "list my todos",
])
def test_a_bare_kind_is_a_kind_question(said):
    assert composer_lists.holding_ask(said) == ("tasks", False, "which")


@pytest.mark.parametrize("said", ["list my notes", "what dates do I have", "list my work notes", "what is a checklist", "list the Lisbon checklist"])
def test_other_asks_are_not_swallowed(said):
    assert composer_lists.holding_ask(said) is None


def test_the_answer_names_the_notes_that_have_checklists(go):
    text, _ = go("list my checklists")
    assert text.startswith("Two notes have checklists") or "notes have checklists" in text, text
    assert "Lisbon packing list" in text and "Todo" in text, text
    assert "I couldn't find anything" not in text and "Nothing matched" not in text
