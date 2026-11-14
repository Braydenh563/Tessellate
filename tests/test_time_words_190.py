"""L-chat-190 (the owner: "the composer should note timewords so it can be like, last Friday you did this"):
the time word of the question comes back in the answer's first sentence, and each note says the date it
resolves to (the fixed clock is Monday 9 November 2026, so last Friday is 6 November)."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture()
def ask(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    return lambda q: sd.ask(client, q, notes_only=True)["text"]


@pytest.mark.parametrize("question", ["what did I write last Friday", "what did I do last Friday"])
def test_last_friday_is_said_back_as_the_friday_it_is(ask, question):
    text = ask(question)
    assert text.startswith("Last Friday"), text
    assert "notes" in text.splitlines()[0]


def test_each_note_carries_the_date_the_time_word_resolved_to(ask):
    lines = [ln for ln in ask("what did I write last Friday").splitlines() if ln.startswith("- ")]
    assert lines and all(ln.startswith("- Fri 6 Nov,") for ln in lines), lines


def test_yesterday_and_a_weekday_resolve_too(ask):
    assert "yesterday" in ask("what did I write yesterday").lower().splitlines()[0]
    assert "Tuesday" in ask("what did I write on Tuesday").splitlines()[0]
