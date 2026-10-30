"""2026-10-30 sweep: amounts, tastes and words a note says by its shape.

"How much have I spent this month" found nothing and "what's my biggest
expense" quoted the spending note whole (`ai/composer_money.py`); "did I
like the ramen place" said no note says so beside "8/10, the broth was
great"; "does Jake owe me money" hedged on "money" beside "$40"; "what do
I need from the shops" found nothing beside the Groceries list."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)
NOTES = [
    "Tried the new ramen place on King St, 8/10, the broth was great but too salty.",
    "# Groceries\n\n- [ ] Oat milk\n- [ ] Eggs\n- [x] Bread\n- [ ] Coffee beans",
    "# Spending October\n\nGroceries $86 on the 3rd, $112 on the 17th. Rent $1200. Concert tickets $90.",
    "# Jake\n\nJake owes me $40 for the concert tickets.",
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for content in NOTES:
        manager.create_entry(session, content)
    session.commit()

    def go(question: str) -> str:
        body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
        text = ""
        with client.stream("POST", "/chat/stream", json=body) as response:
            for line in response.iter_lines():
                if line.strip() and (event := json.loads(line))["type"] == "answer":
                    text += event["delta"]
        return text

    return go


@pytest.mark.parametrize("question", ["how much have I spent this month", "how much did I spend in October"])
def test_spending_is_summed_and_owed_money_is_not(ask, question):
    said = ask(question)
    assert said.startswith("You spent $1,488 in October, going by Spending October: Groceries $198, rent $1,200 and concert tickets $90."), said
    assert "$40" not in said, said


@pytest.mark.parametrize(("question", "lead"), [
    ("what's my biggest expense", "Rent, at $1,200, is the biggest amount in Spending October."),
    ("what was my smallest purchase", "Groceries, at $86, is the smallest amount in Spending October."),
])
def test_the_biggest_and_smallest_amounts(ask, question, lead):
    assert ask(question).startswith(lead), question


def test_a_biggest_that_is_not_money_is_not_summed(ask):
    assert "amount in" not in ask("what's my biggest worry")


@pytest.mark.parametrize("question", ["did I like the ramen place", "did I enjoy the ramen"])
def test_a_taste_is_answered_by_what_the_note_says(ask, question):
    said = ask(question)
    assert said.startswith("Your note of 30 October says: Tried the new ramen place on King St, 8/10"), said
    assert "nothing" not in said, said


@pytest.mark.parametrize(("question", "word"), [("does jake owe me money", "money"), ("what did I rate the ramen", "rate")])
def test_a_word_said_by_its_shape_is_not_missing(ask, question, word):
    said = ask(question)
    assert f"“{word}”" not in said, said
    assert "exact match" not in said, said


def test_the_shops_are_the_grocery_list(ask):
    assert "Groceries" in ask("what do I need from the shops")


@pytest.mark.parametrize("question", [
    "how much money have I recorded Ive spent?",
    "what have I spent so far",
    "whats my total spending",
])
def test_a_spending_total_asked_any_way_is_summed_from_the_notes(ask, client, question):
    """The owner, 2026-10-30 (screenshot): "how much money have I recorded
    Ive spent?" in Agent with Web on and no model answered with a SearXNG
    error and "your notes did not hold an answer"."""
    from tessellate.core import deps

    deps.get_config().set_preference("web_search_enabled", True)
    said = ask(question)
    assert said.startswith("You spent $1,488"), said
    agent = ""
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
        for line in response.iter_lines():
            if line.strip() and (event := json.loads(line))["type"] == "answer":
                agent += event["delta"]
    assert agent.startswith("You spent $1,488"), agent
    said += agent
    assert "search" not in said.lower(), said



@pytest.mark.parametrize("question", ["what's still on my groceries list", "what haven't I bought from the groceries list yet"])
def test_whats_still_on_a_list_is_its_open_items_only(ask, question):
    """2026-10-30 probe: "what's still on my grocery list" listed every item,
    ticked ones too, and a spending line came after it."""
    said = ask(question)
    assert said.startswith("3 still to do on Groceries:"), said
    assert "Bread" not in said and "$" not in said, said
