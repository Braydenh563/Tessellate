"""Audit 1030 Z46, the recast half (no model): "what's in mum's lentil
soup" said one entry of the recipe's list as the answer, then "**Also:**
Carrots; red lentils; cumin." A question about what a list note holds is
answered by the list, whole and counted, however it is asked."""

from __future__ import annotations

import pytest

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

SOUP = "# Mum's recipe for lentil soup\n\n- onions\n- carrots\n- red lentils\n- cumin\n\nSimmer for 40 minutes."
KIT = "# Camping kit\n\n- tent\n- sleeping bag\n- stove\n- head torch\n- water filter"


@pytest.mark.parametrize(("question", "note", "items"), [
    ("what's in mum's lentil soup", SOUP, ["onions", "carrots", "red lentils", "cumin"]),
    ("what is in the lentil soup", SOUP, ["onions", "carrots", "red lentils", "cumin"]),
    ("what goes in the lentil soup", SOUP, ["onions", "carrots", "red lentils", "cumin"]),
    ("what are the ingredients for the lentil soup", SOUP, ["onions", "carrots", "red lentils", "cumin"]),
    ("what's in my camping kit", KIT, ["tent", "sleeping bag", "stove", "head torch", "water filter"]),
    ("what do I need for camping", KIT, ["tent", "sleeping bag", "stove", "head torch", "water filter"]),
])
def test_a_list_note_is_answered_as_its_list(client, session, question, note, items):
    manager.create_entry(session, note)
    manager.create_entry(session, "# Banana bread\n\nThree ripe bananas, flour, butter and an egg.")
    session.commit()
    said = _ask(client, question, use_tools=False, notes_only=True, answer_from="notes")["text"]
    assert "Also:" not in said, said
    first = said.split("\n\n")[0].lower()
    assert all(item in first for item in items), said
