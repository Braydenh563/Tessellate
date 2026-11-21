"""F13 e, f, g, k (g45-1110): empty notes, /week, a study plan without a model,
and "how are you" answered. Fixed clock 2026-11-10 09:00."""

import datetime as dt

import pytest

import tests._seed_r9_1109 as sd
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager

NOW = dt.datetime(2026, 11, 10, 9, 0, 0)

NOTES = [
    ("# Gift ideas for mum", 3),
    ("# Japan trip\n\nFlights out 12 March and back 26 March.", 30),
    ("# Study notes\n\nExam on 20 November. Revise chapters 3 to 5 and do the past paper.\n\n- [ ] past paper", 4),
    ("# Dentist\n\nCheck-up booked for the 21st.", 8),
]


@pytest.fixture
def chat(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, days in NOTES:
        e = manager.create_entry(session, text, "Personal")
        e.created_at = e.updated_at = NOW - dt.timedelta(days=days)
    session.commit()

    def run(*qs):
        history, out = [], []
        for q in qs:
            r = sd.ask(client, q, history=history or None)
            history.append({"question": q, "answer": r["text"]})
            out.append(r["text"])
        return out

    return run


def test_empty_notes_lists_the_title_only_note(chat):
    (a,) = chat("what notes are empty")
    assert "Gift ideas for mum" in a
    assert "Japan trip" not in a
    assert "Your notes don't mention" not in a


def test_slash_week_suggests_the_two_commands(chat):
    (a,) = chat("/week")
    assert "/made week" in a and "/due week" in a
    assert len(a.splitlines()) <= 3


def test_study_plan_without_a_model_answers_from_the_notes(chat):
    (a,) = chat("make a study plan")
    assert "needs a model" not in a
    assert "Exam" in a or "Study notes" in a


def test_how_are_you_reply_is_heard(chat):
    _, a = chat("how are you", "fine thanks")
    assert "pleasure" not in a.lower()
    assert "glad" in a.lower() or "good to hear" in a.lower()
