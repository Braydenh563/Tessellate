"""Second composer audit G11: a subject several notes are about is one summary
of them, a note of "Label number" lines is added up and compared line by line,
"next" is a function word, and a bare year is a time window. Fixed clock."""

from __future__ import annotations

import datetime as dt
from datetime import date

import pytest

from tessellate.ai import composer_ask, composer_extra, composer_study, recognise

NOW = dt.datetime(2026, 11, 10, 10, 0, 0)


def _note(i: int, content: str, day: str = "2026-10-20") -> dict:
    return {"id": i, "content": content, "category": "Work", "tags": [], "created_at": f"{day}T10:00:00Z"}


NOTES = [
    _note(1, "Harbor launch plan\nShip the Harbor mobile app to the public on 14 December.\nBeta ends 1 December."),
    _note(2, "Harbor beta feedback\nTesters liked the onboarding. The login screen is slow."),
    _note(3, "Harbor pricing\nFree tier and Plus tier at $5 a month."),
    _note(4, "Budget October\nRent 650\nGroceries 120\nEating out 160"),
    _note(5, "Budget November\nRent 650\nGroceries 140\nEating out 90"),
    _note(6, "Plumber\nCall on Tuesday."),
]


def said(question: str) -> composer_study.Reply:
    reply = composer_extra.answer(composer_study.Ctx(question=question, notes=NOTES, now=NOW, seed="s", asked=question))
    assert reply is not None, question
    return reply


def test_a_subject_several_notes_are_about_is_one_summary_of_them():
    reply = said("summarise harbor")
    assert "3 notes match" in reply.text
    assert reply.text.count("\n- ") == 3
    assert "Other notes that match" not in reply.text
    assert reply.asks == ["What is the latest on Harbor?", "What is still open in Harbor?"]
    #: The title is not said twice in each bullet.
    assert "Harbor pricing Free" not in reply.text


def test_a_short_note_is_said_whole_not_called_too_little():
    text = said("summarise the plumber").text
    assert "too little" not in text and "Call on Tuesday" in text


def test_the_total_of_a_labelled_note_is_added_up():
    text = said("total budget for november").text
    assert "**880**" in text and "Rent 650, Groceries 140, Eating out 90" in text
    assert "**930**" in said("what's my total spending in october").text


@pytest.mark.parametrize("question", ["what's the difference between the two budgets", "compare the october and november budgets"])
def test_two_labelled_notes_show_only_the_lines_that_differ(question):
    text = said(question).text
    assert "Groceries: 120 in Budget October, 140 in Budget November (20 more)" in text
    assert "Eating out: 160 in Budget October, 90 in Budget November (70 less)" in text
    assert "50 less" in text
    assert "The same in both: Rent 650." in text


@pytest.mark.parametrize("word", ["next", "last", "first", "per"])
def test_function_words_are_not_the_search_term(word):
    assert word not in composer_ask.subject_terms(f"whose birthday is {word}")


@pytest.mark.parametrize("phrase", ["2025", "in 2025", "during 2025"])
def test_a_bare_year_is_a_time_window(phrase):
    assert recognise.span(phrase, date(2026, 11, 10), "past") == (date(2025, 1, 1), date(2025, 12, 31), "year")
    assert phrase == "2025" or recognise.find(f"what did I do {phrase}")


def test_forgetting_contradictions_and_patterns_are_answered_from_the_notebook(session):
    from tessellate.api import chat_extra
    from tessellate.repo import reminders as reminder_repo

    reminder_repo.create(session, text="Renew passport", due_at=dt.datetime(2026, 11, 1, 9, 0), priority="normal")
    session.commit()

    def say(question: str) -> str:
        events = chat_extra.notebook_events(session, question, now=NOW)
        assert events and events[0]["type"] == "answer", question
        return events[0]["delta"]

    assert "Renew passport" in say("what am I forgetting")
    assert "change of mind" in say("any contradictions in my notes")
    assert "pattern" in say("any patterns in my notes")
    assert "pattern" in say("what keeps coming up").lower()
    assert chat_extra.notebook_events(session, "summarise harbor", now=NOW) is None


def test_the_model_path_is_handed_the_same_facts(session):
    from tessellate.api import chat_extra

    one = chat_extra.reminder_events(session, "what am I forgetting", now=NOW)
    two = chat_extra.notebook_events(session, "what am I forgetting", now=NOW)
    assert one == two and one


def test_starter_chips_lead_with_what_is_due_and_then_note_searches(session):
    from tessellate.api import chat_extra
    from tessellate.entry import manager
    from tessellate.repo import reminders as reminder_repo

    manager.create_entry(session, "# Harbor launch date\n\nShip on 14 December.")
    reminder_repo.create(session, text="Bins", due_at=dt.datetime(2026, 11, 12, 19, 0), priority="normal")
    session.commit()
    leads = chat_extra.starter_leads(session, NOW)
    assert leads[0] == "What's due this week?"
    assert any("Harbor launch date" in lead for lead in leads[1:])
