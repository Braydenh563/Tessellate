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


BOOKS = [
    ("Bookshop receipt", "2026-10-05", "Paid $36 for my copy of Piranesi."),
    ("Used book", "2026-10-07", "Paid $20 for a used copy of Earthsea."),
]


@pytest.mark.parametrize("question", [
    "How much book spending is actually recorded?",
    "How much book spending is there?",
    "How much did I really spend on books?",
])
def test_a_subject_does_not_keep_the_questions_verbs(ask, question):
    said = ask(question, BOOKS)
    assert "$56" in said and " is " not in said.split("\n")[0] and "really" not in said.split("\n")[0], said


@pytest.mark.parametrize(("rest", "subject"), [
    ("book  is actually recorded", (["book"], "book")),
    ("fuel is there", (["fuel"], "fuel")),
    ("on the plumber was it", (["plumber"], "the plumber")),
])
def test_the_subject_is_cut_at_the_first_auxiliary(rest, subject):
    assert composer_money._subject(rest) == subject


@pytest.mark.parametrize(("question", "notes", "total"), [
    ("How much have I spent on books?", BOOKS, "$56"),
    ("How much did I spend on bikes?", [("Bikeshop", "2026-10-03", "Paid $120 for a service."), ("Lamp", "2026-10-04", "Paid $30 for the lamp.")], "$120"),
    ("How much have I spent on rent?", [("Rental bond", "2026-10-03", "Paid $500 for the bond."), ("Lamp", "2026-10-04", "Paid $30 for the lamp.")], "$500"),
    ("How much food spending have I recorded?", [("Foodhall", "2026-10-03", "Paid $45 for lunch."), ("Lamp", "2026-10-04", "Paid $30 for the lamp.")], "$45"),
])
def test_a_subject_matches_a_compound_by_its_stem(ask, question, notes, total):
    said = ask(question, notes)
    assert total in said and "found no amounts" not in said and "$30" not in said, said


MIXED = [
    ("Lamp", "2026-10-02", "Paid $100 for the lamp."),
    ("Train", "2026-10-03", "Paid £50 for the train."),
    ("Lunch", "2026-10-04", "Paid €20 for lunch."),
]


def test_two_currencies_are_each_said_not_dropped(ask):
    said = ask("How much have I spent?", MIXED)
    assert "$100" in said and "£50" in said and "€20" in said, said


def test_the_biggest_expense_is_said_for_each_currency(ask):
    said = ask("What is my biggest expense?", MIXED + [("Coat", "2026-10-05", "Paid $140 for the coat.")])
    assert "$140" in said and "£50" in said and "€20" in said and "$100" not in said, said


def test_a_difference_names_the_currency_it_left_out(ask):
    notes = [("Spending September", "2026-09-30", "Groceries $60."), ("Spending October", "2026-10-20", "Groceries $100. Train £50.")]
    said = ask("How much more did I spend in October than September?", notes)
    assert said.startswith("You spent $40 more in October than in September."), said
    assert "£50" in said, said


def _page(notes):
    def page(limit=None, offset=0):
        return notes[offset:offset + limit]
    return page


class _Note:
    def __init__(self, content):
        self.content = content


def test_the_money_scan_reads_past_the_first_page_of_notes():
    notes = [_Note("a note with nothing in it")] * 1000 + [_Note("Paid $40 for the lamp."), _Note("Ran 5 km")]
    found = composer_money.recorded_notes(_page(notes))
    assert [n.content for n in found] == ["Paid $40 for the lamp.", "Ran 5 km"]


def test_the_money_scan_keeps_the_newest_few_hundred_hits():
    notes = [_Note(f"Paid ${i} for the lamp.") for i in range(900)]
    found = composer_money.recorded_notes(_page(notes))
    assert len(found) == composer_money.SCAN_HITS and found[0].content == "Paid $0 for the lamp."


def test_the_route_scans_past_the_page_it_reads(ask, monkeypatch):
    monkeypatch.setattr(composer_money, "SCAN_PAGE", 3)
    old = [("Old lamp", "2026-01-02", "Paid $100 for the lamp.")]
    fillers = [(f"Filler {i}", f"2026-10-{10 + i}", "Nothing to see here.") for i in range(8)]
    said = ask("How much have I spent?", old + fillers)
    assert "$100" in said and "found no amounts" not in said, said
