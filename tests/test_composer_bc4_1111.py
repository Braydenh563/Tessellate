"""Batch BC4 (audit 1031 composer rows C11 to C31, rechecked 2026-11-11).
C30 rest: a total-spend ask with one undated priced note and a budget note
says the regular amounts too, never only the one price as money paid."""

from __future__ import annotations

from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


def test_a_total_spend_names_the_regular_amounts_beside_a_single_price(client, session):
    manager.create_entry(session, "# Budget\n\nRent is $1,200 a month. Groceries about $80 a week.")
    manager.create_entry(session, "# Lisbon trip\n\nFlights cost $420 return. Need to book the tram to Sintra.")
    for question in ("what is my total spend", "how much do I spend", "total spend"):
        said = _ask(client, question)["text"]
        assert "rent $1,200 a month" in said.lower() and "groceries about $80 a week" in said, said
