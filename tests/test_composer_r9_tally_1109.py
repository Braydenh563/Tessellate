"""R9-10 and R9-7 reviewer findings (c11): a superlative is taken from one table or list and never from a total,
a distance is the one beside the asked day and the asked verb, a "no" to a yes/no with a window says No and the
real day, and a past window on an "is/are the ..." question stays a filter. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

from datetime import date

import pytest

import tests._seed_r9_1109 as sd
from tessellate.ai import composer_intent
from tessellate.entry import manager


def _add(session, content, ago=1):
    from datetime import datetime

    e = manager.create_entry(session, content, category_name="Uncategorised")
    e.created_at = e.updated_at = datetime.fromordinal(sd.TODAY.toordinal() - ago).replace(hour=10)
    session.commit()


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def test_highest_quote_is_never_the_total_row(session, say):
    _add(session, "# Quote totals\n\n| Builder | Quote |\n|---|---|\n| Marek | £7,200 |\n| BuildRight | £9,100 |\n| Total | £16,300 |")
    text = say("which quote was highest")
    assert "Total" not in text.split("(")[0]
    assert "BuildRight" in text and "9,100" in text


def test_cheapest_builder_is_not_a_line_of_another_list(session, say):
    _add(session, "# Builder costs\n\n- Marek quoted £7,200\n- BuildRight quoted £9,100\n\nPaid so far:\n\n- Deposit paid £500", 2)
    text = say("which builder was cheapest")
    assert "Deposit" not in text.split("(")[0]
    assert "Marek" in text and "7,200" in text


def test_a_distance_is_the_one_beside_the_asked_day(session, say):
    _add(session, "# Run notes\n\nRan 5 km on 5 November and 10 km on 6 November.", 1)
    assert "10 km on 6 November" in say("how far did I run on 6 November")


def test_a_distance_needs_the_asked_verb(say):
    assert say("how far did I walk on 8 November") == "Your notes do not say how far you walk on 8 November."


@pytest.mark.parametrize("ask", ["is the plumber coming tomorrow", "is the plumber coming today"])
def test_a_no_leads_with_no_and_the_real_day(say, ask):
    text = say(ask)
    assert text.startswith("No, not ") and "Wednesday 11 November" in text


def test_the_concert_this_month_is_a_no(say):
    text = say("is the concert this month")
    assert text.startswith("No, not this month") and "5 December" in text


def test_a_past_window_on_an_is_question_is_kept():
    q = "are my notes from yesterday about Raj"
    window, _terms = composer_intent._plan_window(q, ["notes", "raj"], "yesterday", date(2026, 11, 9))
    assert window is not None
