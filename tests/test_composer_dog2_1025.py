# ruff: noqa: F811
"""Blind-test round 2, composer findings 1, 2, 3, 4, 10 and 19 (dog2-1025).
Fixed clock Wednesday 21 October 2026; the notes are test_composer_study_1025's."""

from __future__ import annotations

import re

import pytest

from tessellate.core.database import Reminder
from tests.test_composer_four_1025 import NOW, ask  # noqa: F401
from tests.test_composer_route_688 import _ask


def _turn(ask, history, q):
    said = ask(q, history)
    history.append({"question": q, "answer": said})
    return said


# --- 1: the quiz does not capture everything ------------------------------------------------

@pytest.mark.parametrize("off", ["tell me a joke", "what is the weather like today", "open my notes", "thanks, show me what's due this week", "list my reminders"])
def test_an_off_topic_message_ends_the_quiz(ask, off):
    history: list = []
    _turn(ask, history, "quiz me on lecture 5")
    said = _turn(ask, history, off)
    assert "Not quite" not in said and "Correct" not in said and "question 2 of" not in said


def test_an_answer_is_still_graded(ask):
    history: list = []
    _turn(ask, history, "quiz me on lecture 6")
    said = _turn(ask, history, "a column that identifies each row")
    #: composer6 varies the feedback (`composer_study._FEEDBACK`); any of its openers counts as graded.
    assert re.search(r"correct|close|not quite|right|nearly|missed|part of it|matches|that's it|not this time", said, re.I) and "question 2 of" in said


def test_every_quiz_question_offers_a_stop(client, ask):
    out = _ask(client, "quiz me on lecture 5", notes_only=True, answer_from="notes", history=[])
    asks = out["offer"][0]["offer"]["asks"]
    assert "Stop the quiz" in asks and "Hint" in asks and "Skip" in asks


def test_stop_the_quiz_works(ask):
    history: list = []
    _turn(ask, history, "quiz me on lecture 5")
    assert "question 2 of" not in _turn(ask, history, "Stop the quiz")


def test_no_explain_to_do_questions(ask, session):
    from tessellate.entry import manager
    manager.create_entry(session, "# Revision plan\n\n## To do\n\nFinish the second lab sheet before the tutorial on Friday.\n\n## Next steps\n\nBook a slot with the tutor to talk through the essay plan.\n\n## Memory\n\nPaging splits memory into fixed blocks. Segmentation splits memory by purpose.", "Uni")
    session.commit()
    from tessellate.ai import study
    qs = [c.q for c in study.cards("# Revision plan\n\n## To do\n\nFinish the second lab sheet before the tutorial on Friday.\n\n## Next steps\n\nBook a slot with the tutor to talk through the essay plan.\n")]
    assert not any("To do" in q or "Next steps" in q for q in qs)


# --- 2: context does not bleed ---------------------------------------------------------------

def test_what_did_i_write_this_week_after_a_countdown(ask):
    history: list = []
    _turn(ask, history, "how many days until 12 dec")
    said = _turn(ask, history, "what did I write this week")
    assert "No note I found says anything" not in said and "Lecture" in said


def test_the_chat_topic_is_a_word_the_answer_used():
    from tessellate.api import routes_chat
    history = [{"question": "what's left to write", "answer": "That's general knowledge."}]
    assert routes_chat._chat_topic(history) == ""
    history = [{"question": "tell me about scheduling", "answer": "Scheduling decides which process runs next."}]
    assert routes_chat._chat_topic(history) == "scheduling"


# --- 3: what's left to do --------------------------------------------------------------------

@pytest.mark.parametrize("q", ["what's left to do", "what's left", "what do I still have to do", "what's still open", "what have I got left to do", "what's outstanding"])
def test_whats_left_lists_open_items_and_reminders(ask, q):
    said = ask(q)
    assert "general knowledge" not in said
    assert "Read chapter 4" in said and "Book the tram pass" in said and "Hand in the essay" in said
    assert "Pay rent" not in said


def test_whats_left_with_nothing_open(client, session, monkeypatch):
    from tessellate.api import routes_chat
    from tessellate.core import config
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    said = _ask(client, "what's left to do", notes_only=True, answer_from="notes", history=[])["text"]
    assert "general knowledge" not in said and "Nothing" in said


# --- 4: windows and grounding ----------------------------------------------------------------

def test_the_next_7_days_is_the_window(ask):
    said = ask("what's due in the next 7 days")
    assert "Hand in the essay" in said and "Call the landlord" not in said
    assert "You have three reminders" not in said


def test_due_friday_has_no_false_warning(client, ask):
    said = _ask(client, "what's due friday", history=[])["text"]
    assert "Heads up" not in said and "Hand in the essay" in said


def test_a_countdown_has_no_false_warning(client, ask):
    said = _ask(client, "how many days between today and 25 december", history=[])["text"]
    assert "Heads up" not in said


# --- 10: when is my exam, summaries ----------------------------------------------------------

def test_when_is_my_exam_reads_the_reminder(ask, session):
    session.add(Reminder(text="Exam", due_at=NOW.replace(month=12, day=2, hour=9)))
    session.commit()
    said = ask("when is my exam")
    assert "Wed 2 Dec" in said or "Wednesday 2 December" in said
    assert "12 November" in said  # the note still says its own date


def test_a_summary_leaves_code_out_and_has_no_stray_dash():
    from tessellate.ai import study
    note = "# Plan\n\n## To do\n\n```python\nprint('x')\n```\n\n-\n- Finish the lab\n\n## Notes\n\nSomething important here that is long enough to count.\n"
    text = str(study.summary(note, 0))
    assert "print" not in text and "```" not in text
    assert all(p.strip(" -") for _t, picks in study.summary(note, 0) for p in picks)


# --- 19: variety -----------------------------------------------------------------------------

def test_quiz_openings_differ_between_rounds(ask):
    history: list = []
    seen = set()
    for _ in range(4):
        said = _turn(ask, history, "quiz me on lecture 5")
        seen.add(said.split("\n")[0].replace("5 questions", "N questions"))
    assert len(seen) >= 3


def test_an_app_answered_turn_does_not_pay_for_the_note_search(client, ask, monkeypatch):
    from tessellate.api import routes_chat
    calls = []
    real = routes_chat._retrieve_for
    monkeypatch.setattr(routes_chat, "_retrieve_for", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    ask("what's left to do")
    assert calls == []
    ask("tell me about scheduling")
    assert calls == [1]
