"""F6 of the composer conversation audit (fable-composer-1110.md): comparing, counting and
sums over what was just shown are computed from the figures the last answer showed (the
frame's notes and days), not refused and not searched. Every row is a turn the audit saw
refused or searched. Clock fixed at Tuesday 10 November 2026, 09:00; the audit's notebook."""

from __future__ import annotations

import pytest

from tessellate.ai import composer_figures
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core import clock
import tests._seed_composer_1110 as seed
from tests.test_composer_frame_1110 import _talk

NOW = seed.NOW


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


def _last(client, session, turns):
    seed.seed(session)
    return _talk(client, turns)[-1]["text"]


def test_which_is_higher_after_comparing_the_budgets(client, session):
    text = _last(client, session, ["compare october and november budget", "which is higher"])
    assert "1,005" in text and "955" in text and "October" in text, text
    assert "general knowledge" not in text


def test_by_how_much_is_the_difference(client, session):
    text = _last(client, session, ["compare october and november budget", "which is higher", "by how much"])
    assert "50" in text and "Your five newest notes" not in text, text


def test_groceries_across_the_budgets(client, session):
    text = _last(client, session, ["how much did I spend on groceries"])
    assert "140" in text and "120" in text and "260" in text and "no amounts" not in text, text


def test_total_for_november_is_the_budget_sum(client, session):
    text = _last(client, session, ["total for november"])
    assert "955" in text and "five notes" not in text, text


def test_total_nights_adds_the_stay(client, session):
    text = _last(client, session, ["what do I know about the japan trip", "how many nights in total"])
    assert "12 nights" in text, text


def test_which_is_longer_is_the_longest_stay(client, session):
    text = _last(client, session, ["what do I know about the japan trip", "which is longer"])
    assert "Tokyo" in text and "5 nights" in text, text


def test_which_was_faster_reads_the_run_times(client, session):
    text = _last(client, session, ["compare my two runs", "which was faster"])
    assert "27:40" in text and "28:55" in text and "2 November" in text, text
    assert "Reading list" not in text


def test_whose_birthday_is_first(client, session):
    text = _last(client, session, ["whose birthday is first"])
    assert "Anna" in text and "3 December" in text and "Mia" in text, text
    assert "Todo" not in text


DATES = ["when is the exam", "when is the dentist", "when is the car service"]


def test_which_comes_first_among_the_dates_shown(client, session):
    text = _last(client, session, [*DATES, "which comes first"])
    assert "Dentist" in text and "21 November" in text, text
    assert "landlord" not in text.lower()


def test_days_between_them(client, session):
    text = _last(client, session, [*DATES[:2], "how many days between them"])
    assert "3 days" in text, text


def test_days_until_then_counts_from_today(client, session):
    text = _last(client, session, [*DATES[:1], "how many days until then"])
    assert "14 days" in text, text


@pytest.mark.parametrize("turns, expect", [
    (["what's 650 plus 140", "times 12"], "9,480"),
    (["what's 650 plus 140", "minus 100"], "690"),
    (["what's 15% of 4500", "split that between 2"], "337.5"),
    (["what's 650 plus 140", "half of that"], "395"),
])
def test_the_calculator_keeps_its_last_result(client, session, turns, expect):
    assert expect in _last(client, session, turns)


def test_how_many_about_harbor_after_a_count(client, session):
    text = _last(client, session, ["how many notes do I have", "how many about harbor"])
    assert "4" in text or "Four" in text, text
    assert "Ship the Harbor" not in text


def test_nothing_to_compare_still_asks(client, session):
    text = _last(client, session, ["hello", "which is higher"])
    assert "general knowledge" not in text


def test_the_figures_are_read_from_the_frames_notes_only(session):
    """Private notes are never read through a client's frame ids."""
    from tessellate.entry import manager

    seed.seed(session)
    hidden = manager.create_entry(session, "# Budget secret\n\nRent 9999. Food 1.", category_name="Money")
    hidden.is_private = True
    session.commit()
    history = [{"question": "q", "answer": "a", "frame": {"note_ids": [hidden.id], "subject": "x", "person": "", "ask": "q", "dates": [], "items": []}}]
    assert composer_figures.answer(session, "total", history, NOW.date()) is None
