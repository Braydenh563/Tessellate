"""Second eye 2026-10-30 (fable-eye-1030 F1, F4, F5, F11, F12): the money
reader asked of a notebook with more than one year, more than one currency,
more than a page of notes, and a subject with a verb or a compound in it.
Every test fixes the clock."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import composer_money
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)


@pytest.fixture
def ask(client, session, monkeypatch):
    def go(question: str, notes: list, now: datetime = NOW) -> str:
        monkeypatch.setattr(config, "user_now", lambda _c: now)
        monkeypatch.setattr(routes_chat, "user_now", lambda _c: now)
        for title, day, body in notes:
            entry = manager.create_entry(session, f"# {title}\n\n{body}" if title else body)
            entry.created_at = entry.updated_at = datetime.fromisoformat(day + "T09:00:00")
        session.commit()
        text = ""
        with client.stream("POST", "/chat/stream", json={"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}) as response:
            for line in response.iter_lines():
                if line.strip() and (event := json.loads(line))["type"] == "answer":
                    text += event["delta"]
        return text

    return go


TWO_YEARS = [
    ("Lamp", "2026-10-02", "Paid $100 for the lamp."),
    ("Boiler repair", "2025-10-11", "Paid $400 for the boiler repair."),
]
TITLED_YEARS = [
    ("Spending October", "2026-10-20", "Groceries $300. Rent $1000."),
    ("Spending October", "2025-10-31", "Groceries $200. Rent $900."),
]


@pytest.mark.parametrize(("question", "paid"), [
    ("How much did I spend in October?", "$100"),
    ("How much have I spent this year?", "$100"),
    ("How much did I spend last year?", "$400"),
    ("How much did I spend in October 2025?", "$400"),
    ("How much did I spend in October last year?", "$400"),
    ("How much did I spend in October of 2026?", "$100"),
])
def test_a_money_window_reads_its_year(ask, question, paid):
    said = ask(question, TWO_YEARS)
    other = "$400" if paid == "$100" else "$100"
    assert paid in said and other not in said and "$500" not in said, said


@pytest.mark.parametrize(("question", "total"), [
    ("How much did I spend in October?", "$1,300"),
    ("How much have I spent this year?", "$1,300"),
    ("How much did I spend last year?", "$1,100"),
])
def test_a_note_titled_with_a_month_belongs_to_the_year_it_was_written(ask, question, total):
    said = ask(question, TITLED_YEARS)
    assert total in said and "$2,400" not in said, said


def test_last_month_in_january_is_december_of_the_year_before(ask):
    notes = [("Gift", "2026-12-10", "Paid $60 for the gift."), ("Old gift", "2025-12-10", "Paid $900 for the gift.")]
    said = ask("How much did I spend last month?", notes, datetime(2027, 1, 15, 12, 0))
    assert "$60" in said and "$900" not in said, said


def test_an_old_month_names_the_latest_year_that_holds_it(ask):
    notes = [("Old lamp", "2025-10-02", "Paid $100 for the lamp."), ("Older lamp", "2024-10-02", "Paid $70 for the lamp.")]
    said = ask("How much did I spend in October?", notes)
    assert "$100" in said and "$70" not in said and "$170" not in said, said
