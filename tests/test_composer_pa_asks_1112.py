"""Composer ledger 1112, the ask rows (docs/roadmap/agent-remaining/ledger-1112.md), no model, clock Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import composer_names
from tessellate.api import chat_said, chat_turn, routes_chat
import tests._seed_fc_1110 as seed

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _ask(client, question, history=None):
    body = {"question": question}
    if history:
        body["history"] = history
    parts = []
    with client.stream("POST", "/chat/stream", json=body) as response:
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event.get("type") == "answer":
                    parts.append(event.get("delta", ""))
    return "".join(parts)


@pytest.fixture
def notebook(client, session):
    seed.seed(session)
    return lambda question, **body: _ask(client, question, **body)


# --- F8 ----------------------------------------------------------------------


def test_f8_a_typo_in_my_shopping_list_finds_the_shopping_note(notebook):
    said = notebook("wats on my shoping list")
    assert "**Shopping**" in said and "Milk" in said, said
    assert "Reading list" not in said, said


def test_f8_a_typo_before_a_bare_list_is_read_and_the_reading_is_shown(notebook):
    assert "what is on my shopping list" in notebook("wats on my shoping list")


def test_f8_the_budget_asked_without_a_month_answers_from_the_latest_budget_note(notebook):
    said = notebook("what's in my budget")
    assert "Budget November" in said and "Rent 650" in said, said


def test_f8_a_slip_in_a_title_word_is_repaired_whatever_else_says_the_word():
    notes = [{"content": "# Budget\n\nRent is 650."}, {"content": "My budget this year is tight."}]
    names = composer_names.names_of(notes)
    assert "budget" in names, "a one-word heading is a name even when other notes use the word in lower case"
    assert composer_names.respell("what is on my budgt list", names) == "what is on my budget list"


def test_f8_a_real_word_before_list_is_never_turned_into_a_name():
    names = composer_names.names_of([{"content": "# Shopping\n\n- milk"}])
    assert composer_names.respell("what is on my reading list", names) == "what is on my reading list"


# --- G11 ---------------------------------------------------------------------


def _price_table(session):
    from tessellate.entry import manager

    manager.create_entry(session, "# Shopping prices\n\n| Item | Price |\n|---|---|\n| Milk | £1.20 |\n| Bread | £2.50 |\n| Cheese | £4.00 |", category_name="Life")


def test_g11_how_much_more_cheese_than_milk_is_the_difference_of_the_two_figures(client, session):
    _price_table(session)
    said = _ask(client, "how much more cheese than milk")
    assert said.startswith("2.8 more: Cheese is 4 and Milk is 1.2"), said
    assert "Shopping prices" in said, said


def test_g11_the_other_way_round_says_no(client, session):
    _price_table(session)
    said = _ask(client, "how much more is milk than bread")
    assert said.startswith("No, 1.3 less"), said


def test_g11_a_total_over_a_run_of_sentences_adds_the_figures(notebook):
    said = notebook("total budget for november")
    assert "**955**" in said and "Budget November" in said, said


def test_g11_one_label_in_two_months_is_the_gap_between_them(notebook):
    said = notebook("how much more did I spend eating out in october than november")
    assert said.startswith("70 more in October"), said


def test_g11_two_labels_of_one_months_note(notebook):
    said = notebook("how much more is rent than groceries in november")
    assert said.startswith("510 more: Rent is 650 and Groceries is 140"), said


def test_g11_two_things_that_are_no_labels_are_left_to_the_other_readers(notebook):
    assert "510" not in notebook("how much more is a plane ticket than a train ticket")
