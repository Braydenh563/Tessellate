"""2026-10-30, the owner: "composer_money seems very specific, what if the
user asks about other things, like distances, measurements". A distance, a
weight or a stretch of time the notes record is added up the way spending
is, by the unit table the converter uses (CHAT_PLAN, placed 2026-10-30)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import composer_money, recognise
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = datetime(2026, 10, 30, 12, 0)
NOTES = [
    "# Running log\n\nRan 5 km on Tuesday along the river. Ran 8.5 km on Saturday with Sam.",
    "# Long run\n\nDid a 12 km run up the hill, slow but steady.",
    "# Deck build\n\nSpent 3 hours on the deck frame. Another 90 minutes sanding the boards.",
    "# Bike commute\n\nCycled 14 km to work and back.",
    "# Q1 goals\n\nRun a 10k. Read 12 books.",
    "# Spending October\n\nGroceries $86 on the 3rd. Rent $1200.",
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


def test_measures_are_read_in_the_dimensions_base_unit():
    assert [(d, v, w) for d, v, w, _ in recognise.measures("Ran 5 km, then 800m, and 2 hours later 10k")] == [
        ("length", 5000.0, "km"), ("length", 800.0, "m"), ("time", 7200.0, "hours"), ("length", 10000.0, "k"),
    ]
    #: "5 in the morning" is no length, and "$10k" is no distance (the
    #: stated intent kept; money is now the "money" dimension of the same
    #: reader, 2026-10-30 quantity engine step 1, so it is read as 10000 dollars).
    assert [(d, v, w) for d, v, w, _ in recognise.measures("$10k for the car at 5 in the morning")] == [("money", 10000.0, "$")]


@pytest.mark.parametrize(("question", "unit"), [("how far did I run", "km"), ("how many km have I run", "km"), ("how many kilometres did I run in total", "kilometres")])
def test_a_distance_is_summed_by_the_verb_asked_in_the_unit_asked(ask, question, unit):
    said = ask(question)
    assert said.startswith(f"Your notes record 25.5 {unit} run: Running log 13.5 {unit} and Long run 12 {unit}."), said
    assert "14 km" not in said, said


def test_a_distance_with_no_verb_counts_every_note(ask):
    assert ask("what's my total distance").startswith("Your notes record 39.5 km: Bike commute 14 km, Running log 13.5 km and Long run 12 km."), ask("what's my total distance")


@pytest.mark.parametrize("question", ["how much time have I spent on the deck", "how many hours did I spend on the deck"])
def test_time_on_a_subject_is_summed_in_one_note(ask, question):
    said = ask(question)
    assert said.startswith("Your notes record 4.5 hours on the deck, going by Deck build: 3 hours and 90 minutes."), said


def test_a_measure_question_is_not_a_money_one():
    assert composer_money.asks("how far did I run this month")
    assert composer_money.asks("how many miles have I walked")
    assert not composer_money.asks("how many recipes have I saved")
    assert not composer_money.asks("how long is the drive to Sam's")
    assert composer_money.records_amounts("Ran 5 km on Tuesday")


@pytest.mark.parametrize(("text", "read"), [
    ("Groceries $86 on the 3rd, rent $1,200.50", [("money", 86.0, "$"), ("money", 1200.5, "$")]),
    ("Flight £320 and a 12 km taxi", [("money", 320.0, "£"), ("length", 12000.0, "km")]),
    ("Saved €1.5k, ran 5 km", [("money", 1500.0, "€"), ("length", 5000.0, "km")]),
])
def test_money_is_one_dimension_of_the_same_reader(text, read):
    got = recognise.measures(text)
    assert [(d, v, w) for d, v, w, _ in got] == read
    assert all(m.end > m.at for m in got)


def test_money_has_no_reader_of_its_own():
    assert not hasattr(recognise, "amounts")
