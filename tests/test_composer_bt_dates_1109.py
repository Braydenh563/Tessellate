"""bt-compcomp-1109 items 1, 3, 4, 8: a weekday beside its date is one day, a note titled for the subject
answers a yes/no about it, a quote keeps its date and is contiguous, a weekly habit is not due.
Seed: `tests/_seed_bt_1109.py` (clock Monday 9 November 2026)."""

from __future__ import annotations

import time
from datetime import date

import pytest

import tests._seed_bt_1109 as sd
from tessellate.ai import composer_ahead, factgraph, recognise

ORCHARD = "Orchard is the website redesign for the community garden. Deadline: Monday 16 November 2026 for the launch. Budget is 4,500 pounds."


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    return lambda q: sd.ask(client, q, notes_only=True)["text"]


def test_a_weekday_beside_its_date_is_not_a_second_day():
    facts = factgraph.facts({"content": "Deadline: Monday 16 November 2026 for the launch.", "created_at": "2026-11-09T09:00:00"})
    assert [f.attrs["resolved"] for f in facts if f.kind == "date"] == ["2026-11-16"]


def test_a_weekday_alone_is_still_a_day():
    facts = factgraph.facts({"content": "Dinner is on Friday.", "created_at": "2026-11-09T09:00:00"})
    assert [f.attrs["phrase"] for f in facts if f.kind == "date"] == ["on Friday"]


def test_the_deadline_is_the_day_the_note_names_not_today(ask):
    text = ask("what is my Orchard deadline")
    assert "ahead in your notes: 16 November" in text and "9 November" not in text, text


def test_the_dentist_note_answers_tomorrow(ask):
    text = ask("is the dentist tomorrow?")
    assert text.startswith("No, not tomorrow") and "12 Nov" in text and "Dentist note" in text, text
    assert "Weekend todo" not in text.split("\n")[0], text


def test_an_abbreviated_month_is_read_by_the_one_reader():
    assert composer_ahead.date_in("Thu 12 Nov 9:30", date(2026, 11, 9)) == date(2026, 11, 12)
    assert composer_ahead.date_in("nothing dated here", date(2026, 11, 9)) is None


def test_a_quote_keeps_its_date_and_joins_no_gap(ask):
    text = ask("what do I know about the Orchard projcet")
    assert "Monday 2026" not in text and "16 November" in text, text
    for quote in (q.split("”")[0] for q in text.split("“")[1:]):
        assert quote in ORCHARD and "garden. Budget" not in quote, quote


def test_a_weekly_habit_is_not_due(ask):
    text = ask("what's due this week")
    assert "Gym" not in text and "Tuesday 10 November" in text and "Thu 12 Nov" in text, text


@pytest.mark.parametrize("said", ["Gym on Monday, Wednesday and Friday at 7am", "Run every Tuesday", "Mondays are for the gym"])
def test_a_schedule_is_recurring(said):
    assert recognise.recurring_schedule(said)


@pytest.mark.parametrize("said", ["Team sync on Tuesday", "Moved to Friday at 3pm", ""])
def test_a_single_day_is_not_recurring(said):
    assert not recognise.recurring_schedule(said)


def test_a_long_run_is_read_in_bounded_time():
    for text in ("Monday " * 25_000, "every " * 25_000, " " * 50_000 + "Friday"):
        start = time.perf_counter()
        recognise.recurring_schedule(text)
        assert time.perf_counter() - start < 0.5


def test_a_schedule_asked_for_is_not_denied_after_it_is_found(ask):
    text = ask("what is my gym schedule")
    assert "Gym on Monday, Wednesday and Friday at 7am" in text and "do not mention" not in text, text
