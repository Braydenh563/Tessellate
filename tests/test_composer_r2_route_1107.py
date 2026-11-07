"""Composer round 2, 2026-11-07, through the chat route (the pool the route
builds is part of the answer): which notes hold a table or a numbered list.
No model (fake transport); fixed clock."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 11, 7, 10, 0, 0)
NOTES = (
    "# Shopping\n\n| Item | Price |\n|---|---|\n| Milk | £1.20 |\n| Bread | £2.50 |",
    "# Packing for Tokyo\n\n1. passport\n2. rail pass\n3. adapter",
    "# Todo\n\n- [ ] Book MOT\n- [x] Pay council tax",
    "# Lisbon dinner\n\nRemember to book a table for dinner in Lisbon on the first night.",
    "# Ideas\n\n- Paint the shed\n- Learn Rust",
    "# Tokyo trip\n\nFlights cost $900 return, leaving 3 April. Staying in Shinjuku for six nights.",
    "# Lisbon trip\n\nFlights cost $420 return, leaving 12 May. Staying at Hotel Alfama near the river.",
)


@pytest.fixture
def go(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text in NOTES:
        entry = manager.create_entry(session, text, "Personal")
        entry.created_at = entry.updated_at = NOW - dt.timedelta(days=3)
    session.commit()
    return lambda q, chat=False: _ask(client, q, **({} if chat else {"notes_only": True, "answer_from": "notes"}))["text"]


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize("question", ["what notes have tables", "which notes have a table"])
def test_e19_a_table_is_a_kind_of_note_not_a_word(go, chat, question):
    said = go(question, chat)
    assert "Shopping" in said and "Lisbon dinner" not in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_e19_a_numbered_list_is_not_every_list(go, chat):
    said = go("which notes have a numbered list", chat)
    assert "Packing for Tokyo" in said and "Ideas" not in said and "Todo" not in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_e2_but_not_names_the_notes_that_keep_one_word_and_leave_the_other(go, chat):
    said = go("notes about Tokyo but not Lisbon", chat)
    assert "Tokyo trip" in said and "Lisbon trip" not in said and "Lisbon dinner" not in said, said
    assert "“not”" not in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_e2_notes_that_leave_a_word_out_are_every_note_without_it(go, chat):
    said = go("which notes are not about Lisbon", chat)
    assert "Tokyo trip" in said and "Shopping" in said, said
    assert "Lisbon trip" not in said and "Lisbon dinner" not in said, said
