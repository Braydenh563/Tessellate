"""2026-10-30, one quantity engine (CHAT_PLAN, placed 2026-10-30): the status
words money had (still due, refunded, a budget or a goal) read of any
quantity where they read naturally, and the difference between two sets of
notes is two sums and a subtraction, citing both. Every test fixes the
clock; none reads the real one."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import composer_money
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)
WALKS = [
    ("Walking log", "2026-10-25", "Walked 18 km on Sunday. Walked 12 km on Wednesday."),
    ("Walking target", "2026-10-01", "My target is 50 km walked a month."),
]
RUNS = [
    ("Running log", "2026-10-27", "Ran 5 km on Tuesday. Ran 3.5 km on Saturday."),
    ("Q1 goals", "2026-09-01", "Run a 10k. Read 12 books."),
]
DECK = [("Deck build", "2026-10-20", "Spent 3 hours on the frame. Another 5 hours still to go on the boards.")]
FOOD = [
    ("Food budget", "2026-10-01", "Food budget for October is $400."),
    ("Spending October", "2026-10-20", "Groceries $86. Dinner out $60."),
]
STUDY = [("Study log", "2026-10-26", "Studied 12 hours on Monday. Studied 6 hours on Thursday."), ("Exam plan", "2026-10-01", "Goal: 40 hours of revision before the exam.")]
AGENCY = [("Agency hours", "2026-10-20", "Booked 10 hours with the agency. The agency refunded 2 hours.")]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def go(question: str, notes: list) -> str:
        for title, day, body in notes:
            entry = manager.create_entry(session, f"# {title}\n\n{body}")
            entry.created_at = entry.updated_at = datetime.fromisoformat(day + "T09:00:00")
        session.commit()
        text = ""
        with client.stream("POST", "/chat/stream", json={"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}) as response:
            for line in response.iter_lines():
                if line.strip() and (event := json.loads(line))["type"] == "answer":
                    text += event["delta"]
        return text

    return go


@pytest.mark.parametrize(("question", "lead"), [
    ("how far short of my 50 km goal am I", "You are 20 km short of your 50 km goal."),
    ("how many km left to my 50 km target", "You are 20 km short of your 50 km target."),
    ("how close am I to my 50 km goal", "You are 20 km short of your 50 km goal."),
    ("how much further to my 50 km target", "You are 20 km short of your 50 km target."),
    ("how far am I from my walking target", "You are 20 km short of your 50 km target."),
])
def test_a_goal_in_a_distance_is_what_is_left_of_it(ask, question, lead):
    said = ask(question, WALKS)
    assert said.startswith(lead), said
    assert "Walking log" in said and "30 km" in said, said


@pytest.mark.parametrize("question", ["how far short of my 10k goal am I", "how many km left to my 10 km target", "how far off my 10k target am I"])
def test_a_ten_k_goal_is_read_as_ten_kilometres(ask, question):
    said = ask(question, RUNS)
    assert said.startswith("You are 1.5 km short of your 10 km"), said


def test_a_goal_that_is_met_says_how_far_past_it(ask):
    said = ask("how far short of my 5 km goal am I", RUNS)
    assert said.startswith("You are 3.5 km past your 5 km goal."), said


@pytest.mark.parametrize("question", [
    "how many hours are left on the deck",
    "how many hours do I have left on the deck",
    "how much time is still to go on the deck",
    "how many hours remain on the deck",
])
def test_a_stretch_still_to_go_is_found_like_a_balance_still_due(ask, question):
    said = ask(question, DECK)
    assert said.startswith("5 hours is still to go, going by Deck build."), said


def test_a_stretch_still_to_go_is_not_counted_as_done(ask):
    said = ask("how many hours did I spend on the deck", DECK)
    assert said.startswith("Your notes record 3 hours on the deck, going by Deck build: 3 hours."), said
    assert "Another 5 hours is still to go (Deck build), so 8 hours all up." in said, said


@pytest.mark.parametrize("question", ["how much of my $400 budget is left", "how much is left of my $400 budget", "how much of my food budget have I got left", "how much have I used of my $400 budget"])
def test_a_budget_is_what_is_left_of_it(ask, question):
    said = ask(question, FOOD)
    assert said.startswith("You have $254 left of your $400 budget."), said
    assert "$146" in said, said


def test_a_budget_that_is_passed_says_by_how_much(ask):
    said = ask("how much of my $100 budget is left", FOOD)
    assert said.startswith("You are $46 over your $100 budget."), said


def test_a_refund_is_taken_off_hours_as_it_is_off_money(ask):
    said = ask("how many hours did I book", AGENCY)
    assert said.startswith("Your notes record 10 hours booked"), said
    assert "Less 2 hours refunded (Agency hours), that is 8 hours net." in said, said


@pytest.mark.parametrize("question", ["how many days are left until Christmas", "how many hours until Friday", "how much is left on my hotel bill"])
def test_a_date_or_a_bill_is_not_a_stretch_to_go(question):
    assert composer_money._left_asked(question) is None


@pytest.mark.parametrize("question", [
    "how many hours short of my 40 hour goal am I",
    "how many hours do I still need to hit my 40 hour target",
    "how much further until I reach my 40 hour goal",
    "how many hours have I studied toward my goal",
])
def test_a_goal_in_hours_is_read_the_same_way(ask, question):
    said = ask(question, STUDY)
    assert said.startswith("You are 22 hours short of your 40-hour"), said


@pytest.mark.parametrize("question", [
    "how much is my budget", "how far is the station", "how many books are left", "what is my goal for the year",
    "how much did the hotel cost altogether", "how many days are left until Christmas",
])
def test_a_question_that_is_no_goal_is_not_read_as_one(question):
    assert composer_money._target_asked(question) is None
