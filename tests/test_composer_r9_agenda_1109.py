"""R9-8 (composer audit round 9): the everyday phrasings for the agenda and the open tasks
get the dated list, never the newest notes or "you wrote nothing down". Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


@pytest.mark.parametrize("question", ["what have I got on", "what's coming up"])
def test_the_agenda_with_no_day_is_the_dated_list(say, question):
    text = say(question)
    assert "Wednesday 11 November" in text and "Friday 13 November" in text and "newest notes" not in text


@pytest.mark.parametrize("question", ["whats on tmrw", "what's on tomorrow"])
def test_a_day_ahead_is_planned_not_written(say, question):
    text = say(question)
    assert text == "Nothing is planned for tomorrow." and "wrote" not in text


def test_anything_important_this_week_is_the_week(say):
    assert "Thursday 12 November" in say("anything important this week?")


def test_a_kind_of_date_narrows_the_list(say):
    assert "Mum's birthday is 2 December" in say("any birthdays coming up")
    text = say("any appointments coming up")
    assert "GP appointment" in text and "hospital appointment" in text


@pytest.mark.parametrize("question", ["what tasks do I have", "what needs doing"])
def test_tasks_are_the_open_checklist_items(say, question):
    text = say(question)
    assert "email Raj the draft" in text and "no reminders" not in text
