"""One date-window reader (audit 1029 C24 to C28, C30; INBOX 1357: the class).

A question is read into one window by `composer_plan.window`, and every date
shape (what is on, what is due, the plan) uses it: a past day is a lookback
unless the question looks ahead, unit spans ("the next two weeks") are
windows, "overdue" is the overdue block alone, "before December" is a window
that holds note dates, the day plan counts every open item, and filler verbs
("doing", "did") do not hide a day. Each case runs over several dates and
phrasings, in Ask and in Chat, no model.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import re
import time
from datetime import date

import pytest

from tessellate.ai import composer_plan
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime
TODAY = date(2026, 10, 29)
MODES = pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])


@pytest.fixture
def notebook(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(notes, reminders=()):
        for text, when in notes:
            entry = manager.create_entry(session, text, "Personal")
            entry.created_at = entry.updated_at = when
        for text, due in reminders:
            session.add(Reminder(text=text, due_at=due))
        session.commit()

        def go(question: str, chat: bool = False) -> str:
            kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
            return _ask(client, question, **kw)["text"]

        return go

    return build


# --- the reader itself ------------------------------------------------------------------

@pytest.mark.parametrize(("question", "span"), [
    ("what is on 14 August", (date(2026, 8, 14), date(2026, 8, 14))),
    ("what is on 25 October", (date(2026, 10, 25), date(2026, 10, 25))),
    ("what was I doing on 2 August", (date(2026, 8, 2), date(2026, 8, 2))),
    ("what did I do on 20 October", (date(2026, 10, 20), date(2026, 10, 20))),
    ("what happened on 5 September", (date(2026, 9, 5), date(2026, 9, 5))),
    ("what is on 3 January", (date(2027, 1, 3), date(2027, 1, 3))),
    ("what is on 25 November", (date(2026, 11, 25), date(2026, 11, 25))),
    ("what will be on 14 August", (date(2027, 8, 14), date(2027, 8, 14))),
    ("what is on 14 August coming up", (date(2027, 8, 14), date(2027, 8, 14))),
    ("what is due in the next two weeks", (TODAY, date(2026, 11, 11))),
    ("what is on in the next 2 weeks", (TODAY, date(2026, 11, 11))),
    ("what is on over the next three weeks", (TODAY, date(2026, 11, 18))),
    ("anything in the coming week", (TODAY, date(2026, 11, 4))),
    ("what is due in the next month", (TODAY, date(2026, 11, 28))),
    ("what is due in the next 2 months", (TODAY, date(2026, 12, 28))),
    ("the next 7 days", (TODAY, date(2026, 11, 4))),
    ("what is due before December", (TODAY, date(2026, 11, 30))),
    ("anything due before 1 December", (TODAY, date(2026, 11, 30))),
    ("what is due by 15 November", (TODAY, date(2026, 11, 15))),
    ("what is due until Friday", (TODAY, date(2026, 10, 30))),
])
def test_the_one_reader_reads_every_shape(question, span):
    win = composer_plan.window(question, TODAY)
    assert win is not None and (win[0], win[1]) == span, win


@pytest.mark.parametrize("question", ["what is on", "what is the plan", "what is due before the exam", "what is on in a bit"])
def test_no_window_when_none_is_named(question):
    assert composer_plan.window(question, TODAY) is None


@pytest.mark.parametrize("filler", ["the next " * 4000, "before " * 4000, "a " * 6000 + "weeks", "next 2 " * 4000, "on 1 " * 4000])
def test_the_window_regexes_are_linear(filler):
    t0 = time.perf_counter()
    composer_plan.window("what is due " + filler, TODAY)
    assert time.perf_counter() - t0 < 1.0


# --- the notebook -----------------------------------------------------------------------

def _book():
    notes = [
        ("# Sourdough starter\n\nFed the sourdough starter and it doubled.", D(2026, 8, 2, 9)),
        ("# Garden\n\nPlanted the beans along the fence.", D(2026, 8, 14, 9)),
        ("# Choir\n\nChoir rehearsal ran long, new alto part.", D(2026, 10, 25, 9)),
        ("# Dates\n\nTest day on 3 November. Dentist on 4 November. Car insurance on 20 November.", D(2026, 10, 20, 9)),
    ]
    reminders = [
        ("Renew the library card", D(2026, 10, 27, 9)),
        ("Pay the council tax", D(2026, 10, 28, 9)),
        ("Book the van", D(2026, 11, 2, 9)),
        ("Send the rota", D(2026, 11, 9, 9)),
        ("Order the cake", D(2026, 12, 5, 9)),
    ]
    return notes, reminders


@MODES
@pytest.mark.parametrize(("phrasing", "day", "word"), [
    ("what is on {d}", "14 August", "garden"),
    ("what is on {d}", "2 August", "sourdough"),
    ("what is on {d}", "25 October", "choir"),
    ("what was I doing on {d}", "2 August", "sourdough"),
    ("what did I do on {d}", "14 August", "garden"),
    ("what was I up to on {d}", "25 October", "choir"),
    ("what happened on {d}", "25 October", "choir"),
])
def test_a_past_day_is_a_lookback(notebook, phrasing, day, word, chat):
    said = notebook(*_book())(phrasing.format(d=day), chat)
    assert word in said.lower(), said
    assert "clear of new dates" not in said and "slipped past" not in said, said
    assert not re.search(r"(Saturday|Monday) (14 August|25 October)", said), said


@MODES
@pytest.mark.parametrize(("first", "then", "word"), [
    ("what is on 25 October", "what about the 14th of August", "garden"),
    ("what is on 2 August", "and 25 October", "choir"),
])
def test_a_follow_on_day_is_read_the_same_way(notebook, first, then, word, chat):
    go = notebook(*_book())
    go(first, chat)
    said = go(then, chat)
    assert word in said.lower(), said


@MODES
@pytest.mark.parametrize("phrasing", ["what is on in the next two weeks", "what is due in the next 2 weeks", "anything due over the next two weeks"])
def test_unit_spans_are_windows(notebook, phrasing, chat):
    said = notebook(*_book())(phrasing, chat)
    assert "van" in said.lower() and "rota" in said.lower() and "dentist" in said.lower(), said
    assert "cake" not in said.lower(), said


@MODES
@pytest.mark.parametrize("phrasing", ["what is overdue", "anything overdue", "what is overdue for me", "show me what is overdue"])
def test_overdue_lists_the_overdue_block_only(notebook, phrasing, chat):
    said = notebook(*_book())(phrasing, chat)
    assert "library card" in said.lower() and "council tax" in said.lower(), said
    assert "van" not in said.lower() and "cake" not in said.lower() and "rota" not in said.lower(), said


@MODES
def test_nothing_overdue_says_so(notebook, chat):
    said = notebook([], [("Order the cake", D(2026, 12, 5, 9))])("what is overdue", chat)
    assert "nothing is overdue" in said.lower() and "cake" not in said.lower(), said


@MODES
@pytest.mark.parametrize("phrasing", ["what is due before December", "anything due before December", "what do I have due before December"])
def test_before_a_month_is_a_window_with_note_dates(notebook, phrasing, chat):
    said = notebook(*_book())(phrasing, chat)
    for word in ("test day", "dentist", "car insurance", "van", "rota"):
        assert word in said.lower(), (word, said)
    assert "cake" not in said.lower(), said


@MODES
@pytest.mark.parametrize("phrasing", ["what should I do today", "plan my day", "what should I do this week"])
def test_the_day_plan_counts_and_shows_every_item(notebook, phrasing, chat):
    tasks = ("Finish chapter 3", "Buy a capo", "Email the landlord", "Book the dentist follow-up", "Draft the API spec",
             "Book the review room", "Water the ferns", "Sort the receipts", "Call the plumber", "Clean the oven")
    todo = "# Todo\n\n" + "\n".join(f"- [ ] {t}" for t in tasks)
    said = notebook([(todo, D(2026, 10, 20, 9))])(phrasing, chat)
    counted = re.search(r"Open tasks with no day \((\d+)\)", said)
    assert counted, said
    assert int(counted.group(1)) == len(tasks), said
    assert len(re.findall(r"^- .*\(\[Todo\]", said, re.M)) == len(tasks), said


@MODES
@pytest.mark.parametrize("phrasing", ["what should I do today", "plan my day"])
def test_a_task_dated_outside_the_day_is_still_listed(notebook, phrasing, chat):
    todo = "# Todo\n\n- [ ] Tom to draft the API spec by Friday 6 November\n- [ ] Book the review room"
    said = notebook([(todo, D(2026, 10, 20, 9))])(phrasing, chat)
    assert "draft the API spec" in said and "Book the review room" in said, said


@pytest.mark.parametrize("filler", ["overdue " * 4000, "the " * 6000 + "overdue", "show me " * 3000, "any " * 6000])
def test_the_overdue_reader_is_linear(filler):
    from tessellate.ai.composer_plan import _OVERDUE

    t0 = time.perf_counter()
    _OVERDUE.match(filler)
    assert time.perf_counter() - t0 < 1.0
