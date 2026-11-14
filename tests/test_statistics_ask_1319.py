"""INBOX 1319: "Ask about your statistics", answered from the counts with no
model (ai/stats_ask.py). Exact, like the page: every figure is a count of rows."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from tessellate.ai import stats_ask
from tessellate.core import deps
from tessellate.core.database import Entry, Reminder

#: A Wednesday in the middle of October.
NOW = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)
USAGE = {
    "features": [
        {"name": "tab:notes", "count": 9},
        {"name": "cmd:open-settings", "count": 3},
        {"name": "tab:chat", "count": 2},
    ],
    "unused_days": 90,
}


def _day(month: int, day: int) -> datetime:
    return datetime(2026, month, day, 11, 0, tzinfo=timezone.utc)


@pytest.fixture
def seeded(client):
    with deps.get_db().session() as session:
        rows = [(7, 1, "travel"), (7, 9, "travel"), (7, 20, "travel"), (7, 28, "work")]
        rows += [(9, 3, "work"), (9, 4, "work"), (9, 9, "idea"), (9, 20, "idea"), (9, 25, "idea")]
        rows += [(10, 2, "work"), (10, 5, "work"), (10, 12, "idea"), (10, 13, "idea")]
        for month, day, tag in rows:
            session.add(Entry(content="one two three", tags=json.dumps([tag]), created_at=_day(month, day)))
        session.add(Reminder(text="done one", due_at=NOW, done=True, done_at=_day(10, 13)))
        session.commit()
        yield session


def _ask(session, question):
    return stats_ask.ask(question, session, NOW, USAGE)


def test_a_count_in_a_named_month_is_that_months(seeded):
    answer = _ask(seeded, "how many notes did I write in July")
    assert answer.kind == "month-count" and "4 notes" in answer.text and "July 2026" in answer.text
    assert "5 notes" in _ask(seeded, "how many notes did I make last month").text
    assert "4 notes" in _ask(seeded, "how many notes this month").text


def test_what_you_use_most_comes_from_the_ledger(seeded):
    answer = _ask(seeded, "what do I use most")
    assert answer.kind == "usage"
    assert "Notes tab" in answer.text and "9" in answer.text and "open settings" in answer.text
    assert [fact["count"] for fact in answer.facts] == [9, 3, 2]


def test_writing_more_than_last_month_compares_the_same_days(seeded):
    answer = _ask(seeded, "am I writing more than last month")
    assert answer.kind == "compare"
    #: 4 notes by the 14th of October against 3 by the 14th of September.
    assert "4 notes" in answer.text and "3 by the same date" in answer.text and "more" in answer.text
    assert "5 in all of September" in answer.text
    assert answer.facts[0]["count"] == 4 and answer.facts[1]["count"] == 3


def test_a_month_summary_has_notes_words_top_tag_and_reminders(seeded):
    #: G9 (1110): the top-tag clause needs three notes, so one more "work" note is added here.
    seeded.add(Entry(content="one two three", tags=json.dumps(["work"]), created_at=_day(10, 6)))
    seeded.commit()
    answer = _ask(seeded, "summarise my month")
    assert answer.kind == "summary"
    assert "5 notes" in answer.text and "15 words" in answer.text
    assert "1 reminder done" in answer.text
    assert "Most used tag: work (3 notes)" in answer.text


def test_the_week_can_be_asked_too(seeded):
    answer = _ask(seeded, "summarise my week")
    assert answer.kind == "summary" and "2 notes" in answer.text
    assert "this week" in _ask(seeded, "am I writing more than last week").text.lower()


def test_other_notebook_questions_fall_to_the_chat_composer(seeded):
    assert "13 notes" in _ask(seeded, "how many notes do I have").text
    top = _ask(seeded, "what are my most common tags")
    assert "work" in top.text and "idea" in top.text


def test_a_question_it_cannot_count_says_what_it_can(seeded):
    answer = _ask(seeded, "what is the capital of France")
    assert answer.kind == "none" and "summarise my month" in answer.text.lower()


def test_the_route_answers_in_one_call(client):
    client.post("/entries", json={"content": "hello there"})
    body = client.post("/statistics/ask", json={"question": "how many notes do I have"}).json()
    assert set(body) == {"kind", "text", "facts"} and "1 note" in body["text"]
    blank = client.post("/statistics/ask", json={"question": ""})
    assert blank.status_code == 422


def test_the_page_has_the_box_with_three_starters_and_posts_to_the_route():
    from pathlib import Path

    from tests import _js_scope

    #: statistics.js is one closure now (ranked row 37a); these tests slice or run its private functions, so they read it as it was before it was wrapped (`_js_scope.unwrapped`): same code, same assertions.
    stats = _js_scope.unwrapped(
        (Path(__file__).resolve().parent.parent / "frontend" / "js" / "statistics.js").read_text(encoding="utf-8")
    )
    start = stats.index("function statsAskBox(")
    box = stats[start : stats.index("\n}\n", start)]
    assert "/statistics/ask" in box and 'input.id = "stats-ask-input"' in box and "Ask about your statistics" in box
    assert stats.count('"', stats.index("STATS_ASK_STARTERS"), stats.index("];", stats.index("STATS_ASK_STARTERS"))) >= 6
    assert "statsAskBox()," in stats


def _titled(session):
    session.add(Entry(content="Trip plan. Flights next.", created_at=datetime(2026, 6, 2, 23, 30, tzinfo=timezone.utc)))
    session.add(Entry(content="Binned", deleted_at=datetime(2026, 1, 1), created_at=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)))
    session.add(Entry(content="Private", is_private=True, created_at=datetime(2026, 2, 1, 9, 0, tzinfo=timezone.utc)))
    session.commit()


@pytest.mark.parametrize(
    "question",
    [
        "when did I write my first note ion this notebook?",
        "when was my first note",
        "what is my oldest note",
        "earliest note",
        "when did I start",
    ],
)
def test_first_note_is_answered_with_its_date_and_title(seeded, question):
    _titled(seeded)
    answer = _ask(seeded, question)
    assert answer.kind == "first-note"
    assert "2 June 2026" in answer.text and "Trip plan." in answer.text
    assert "can count" not in answer.text


@pytest.mark.parametrize("question", ["what is my newest note", "latest note", "when did I last write a note", "my most recent note"])
def test_newest_note_is_answered_with_its_date_and_title(seeded, question):
    answer = _ask(seeded, question)
    assert answer.kind == "latest-note"
    assert "13 October 2026" in answer.text and "one two three" in answer.text


def test_first_note_with_no_notes_says_so(client):
    with deps.get_db().session() as session:
        answer = _ask(session, "when did I write my first note")
    assert answer.kind == "first-note" and "no notes yet" in answer.text.lower()


def test_overdue_and_done_reminders_are_counted_as_asked_not_as_the_open_total(seeded, monkeypatch):
    # Audit 1031 Z8: "how many reminders are overdue" was answered "You have 14 open reminders."
    from datetime import timedelta

    from tessellate.ai import notebook_stats

    monkeypatch.setattr(notebook_stats, "utcnow", lambda: NOW)
    for text, due in (("late one", NOW - timedelta(days=2)), ("today", NOW + timedelta(hours=3)), ("later", NOW + timedelta(days=30))):
        seeded.add(Reminder(text=text, due_at=due, done=False))
    seeded.commit()
    overdue = _ask(seeded, "how many reminders are overdue")
    assert overdue.kind == "reminder-count" and overdue.text == "You have 1 overdue reminder."
    assert overdue.facts == [{"label": "overdue reminders", "count": 1}]
    assert _ask(seeded, "how many reminders have I completed").text == "You have 1 reminder marked done."
    assert _ask(seeded, "how many reminders do I have").text.startswith("You have 3 open reminders")
    assert _ask(seeded, "how many reminders are due today").text == "You have 1 reminder due today."


def test_no_overdue_reminders_is_said_so(seeded, monkeypatch):
    from tessellate.ai import notebook_stats

    monkeypatch.setattr(notebook_stats, "utcnow", lambda: NOW)
    assert _ask(seeded, "how many reminders are overdue").text == "You have no overdue reminders."


def test_a_count_over_a_past_window_is_in_the_past_tense(seeded, monkeypatch):
    # Audit 1031 Z8: "You have written no notes last week." A window still running keeps "have written".
    from tessellate.ai import notebook_stats

    monkeypatch.setattr(notebook_stats, "utcnow", lambda: NOW)
    assert notebook_stats.answer("how many notes did I write last week", seeded).text.startswith("You wrote ")
    assert notebook_stats.answer("how many notes did I write today", seeded).text.startswith("You have written ")


# --- Composer audit 2, G9 (1110) ---

_VERDICTS = ("Yes", "Not so far", "About the same")


def test_a_tag_noun_beats_the_usage_verb(seeded):
    answer = _ask(seeded, "what's my most used tag")
    assert answer.kind != "usage"
    assert "Nothing is counted" not in answer.text


@pytest.mark.parametrize(
    "question,needle",
    [
        ("how many links", "link"),
        ("how many orphans", "linked"),
        ("what's my streak", "streak"),
        ("average words per note", "3 words"),
        ("what's my busiest day", "most on"),
        ("did I write yesterday", "yesterday"),
        ("what haven't I used", "chat"),
    ],
)
def test_page_figures_are_answered_not_the_capability_line(seeded, question, needle):
    answer = stats_ask.ask(question, seeded, NOW, {**USAGE, "unused": ["tab:chat", "tab:maps"]})
    assert answer.kind != "none", answer.text
    assert needle in answer.text.lower()


def test_a_comparison_leads_with_yes_or_no_only_when_asked_so(seeded):
    assert not _ask(seeded, "compare this month to last month").text.startswith(_VERDICTS)
    assert not _ask(seeded, "this week vs last week").text.startswith(_VERDICTS)
    assert _ask(seeded, "am I writing more than last month").text.startswith(_VERDICTS)


def test_the_summary_gap_names_notes_and_skips_a_single_use_tag(seeded):
    text = _ask(seeded, "summarise my month").text
    assert "note more than by the same point last month" in text
    assert "(1 note)" not in _ask(seeded, "summarise my week").text


# --- L92 (G9): the week answers use the same point of last week, as the month ones do ---


def test_the_week_comparison_is_through_the_same_day_of_last_week(seeded):
    #: Wed 14 Oct: this week is Mon 12 to Wed 14 (2 notes). Last week already has
    #: Mon 5; with Tue 6, Wed 7 and Fri 9 added it has 3 by Wed 7 and 4 in all.
    for day in (6, 7, 9):
        seeded.add(Entry(content="one two three", tags=json.dumps(["idea"]), created_at=_day(10, day)))
    seeded.commit()
    text = _ask(seeded, "this week vs last week").text
    assert "3 by the same day last week" in text and "4 in all of last week" in text
    assert "1 fewer note" in text


def test_the_week_summary_names_a_tag_used_three_times(seeded):
    for day in (12, 13, 14):
        seeded.add(Entry(content="one two three", tags=json.dumps(["garden"]), created_at=_day(10, day)))
    seeded.commit()
    assert "Most used tag: garden (3 notes)" in _ask(seeded, "summarise my week").text
