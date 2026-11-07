"""Composer round 2, 2026-11-07 (audit-1107-composer-r2.md): table rows, negation,
pronoun follow-ons, undo, ordinals, accents. Every question runs through
`composer.compose` over `_seed_r2_1107`; no model (fake transport), fixed clock."""

from __future__ import annotations

import pytest

from tests._seed_r2_1107 import ask


@pytest.mark.parametrize("question", ["how much is bread", "how much is the bread"])
def test_e1_a_table_row_answers_the_price_it_holds(question):
    said = ask(question)
    assert "2.50" in said and "only a title" not in said, said


def test_e1_a_note_with_a_table_is_never_called_only_a_title():
    for question in ("shopping", "what is in the Shopping note", "milk"):
        assert "only a title" not in ask(question, only=("Shopping",)), question

