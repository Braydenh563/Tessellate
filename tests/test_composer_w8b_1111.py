"""W8B (2026-11-11): the four composer date rows W8 left unfixed (docs/roadmap/agent-remaining/w8-1110.md, "Found, not fixed").
Each is fixed as a class and has sibling phrasings. Clocks fixed: the bt seed is Monday 9 November 2026, the r5 seed
Saturday 7 November 2026, the calls notebook Thursday 29 October 2026."""

from __future__ import annotations

import datetime as dt
from datetime import date

import pytest

import tests._seed_bt_1109 as bt
from tessellate.ai import composer_ahead, recognise, recognise_windows
from tessellate.ai import recognise_questions
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests._r5_1108 import driver
from tests.test_composer_route_688 import _ask


@pytest.fixture
def btask(client, session, monkeypatch):
    bt.seed(session)
    bt.fix_clock(monkeypatch)
    return lambda q: bt.ask(client, q, notes_only=True)["text"]


@pytest.fixture
def r5(client, session, monkeypatch):
    return driver(client, session, monkeypatch)


# --- 1. a yes/no ask about an appointment is read for its day -------------------------------------------

@pytest.mark.parametrize("question", [
    "is my dentist appointment tomorrow", "is the dentist appointment tomorrow", "is my dentist appointment today",
    "is the dentist tomorrow", "is my dentist appointment on Wednesday", "is my dentist appointment on Friday?",
    "is the dentist on Wednesday",
])
def test_an_appointment_ask_with_the_wrong_day_says_no_and_names_the_day(btask, question):
    said = btask(question)
    assert said.startswith("No, not "), said
    assert "Thursday 12 November, 9:30" in said.split("\n")[0], said


@pytest.mark.parametrize("question", [
    "is my dentist appointment on Thursday", "is the dentist appointment on Thursday?", "is my dentist appointment this Thursday",
    "is the dentist on Thursday",
])
def test_an_appointment_ask_on_its_weekday_says_yes_with_the_long_day(btask, question):
    said = btask(question)
    assert said.startswith("Yes, Thursday 12 November, 9:30, from your Dentist note"), said


def test_the_no_names_the_weekday_asked_with_its_capital(btask):
    assert btask("is my dentist appointment on Wednesday").startswith("No, not on Wednesday. Thursday 12 November, 9:30")


def test_the_appointment_ask_reads_like_the_plain_dentist_ask(btask):
    assert btask("is my dentist appointment tomorrow").split("\n")[0] == btask("is the dentist tomorrow").split("\n")[0]


@pytest.mark.parametrize(("question", "window"), [
    ("is the dentist on Thursday", "on Thursday"), ("is my dentist appointment this Friday?", "this Friday"),
    ("is the plumber coming tomorrow", "tomorrow"), ("will the delivery come next week", "next week"),
    ("is the dentist", ""), ("what is on Thursday", ""),
])
def test_the_window_a_yes_no_ask_ends_with(question, window):
    assert recognise_questions.event_window_asked(question) == window


def test_a_weekday_window_is_cut_from_the_search_words():
    assert recognise_questions.without_event_window_tail("is my dentist appointment on Thursday") == "is my dentist appointment"
    assert recognise_questions.without_event_window_tail("is my dentist appointment this Thursday?") == "is my dentist appointment"


def test_a_weekday_window_tail_is_linear():
    import time

    for run in ("is the plumber" + " on" * 3000, "is the plumber" + " " * 9000 + "on Thursday", "is the " + "this " * 2000):
        t0 = time.perf_counter()
        recognise_questions.event_window_asked(run)
        recognise_questions.without_event_window_tail(run)
        assert time.perf_counter() - t0 < 0.5, run[:30]


# --- 2. a holiday asked by pointer names the year it read -----------------------------------------------

@pytest.mark.parametrize(("phrase", "first"), [
    ("last christmas", date(2025, 12, 25)), ("last christmas eve", date(2025, 12, 24)), ("this christmas", date(2026, 12, 25)),
    ("next christmas", date(2026, 12, 25)), ("last new year", date(2026, 1, 1)),
])
def test_a_pointed_holiday_is_one_day(phrase, first):
    found = recognise.span(phrase, date(2026, 11, 11), "past")
    assert found == (first, first, "day"), found


def test_last_christmas_is_the_latest_one_gone_even_just_after_it():
    assert recognise.span("last christmas", date(2026, 12, 30), "past")[0] == date(2026, 12, 25)


@pytest.mark.parametrize("question", [
    "what did I do last Christmas", "what happened last Christmas", "notes from last Christmas", "what did I write last Christmas",
])
def test_the_window_for_last_christmas_carries_its_year(r5, question):
    said = r5(question)["text"]
    assert "last Christmas (2025)" in said, said


@pytest.mark.parametrize(("question", "named"), [
    ("what did I do last Christmas Eve", "last Christmas Eve (2025)"), ("what did I write last New Year", "last New Year (2026)"),
])
def test_the_year_follows_the_holiday_it_read(r5, question, named):
    assert named in r5(question)["text"]


def test_a_holiday_without_a_pointer_and_other_windows_carry_no_year():
    assert recognise_windows.with_holiday_year("at Christmas", date(2025, 12, 25)) == "at Christmas"
    assert recognise_windows.with_holiday_year("last week", date(2026, 11, 2)) == "last week"
    assert recognise_windows.with_holiday_year("last Christmas", None) == "last Christmas"
    assert recognise_windows.with_holiday_year("last Christmas", date(2025, 12, 25)) == "last Christmas (2025)"


# --- 3. one day, one head -----------------------------------------------------------------------------

@pytest.mark.parametrize("question", ["what's on Wednesday", "do I have anything on Wednesday", "is there anything on Wednesday", "what is on Wednesday"])
def test_a_single_day_prints_the_day_once(btask, question):
    said = btask(question)
    assert said.count("Wednesday 11 November") == 1 and "**" not in said, said
    assert "Gym on Monday, Wednesday and Friday at 7am" in said, said


@pytest.mark.parametrize(("question", "head"), [
    ("what's on Thursday", "For Thursday 12 November you have one dated item:"),
    ("what is on Friday", "For Friday 13 November you have one dated item:"),
    ("what's on tomorrow", "For tomorrow, Tuesday 10 November you have one dated item:"),
])
def test_a_single_day_is_a_head_then_its_items(btask, question, head):
    lines = btask(question).split("\n")
    assert lines[0] == head and lines[1] == "" and lines[2].startswith("- "), lines


def test_a_week_still_has_a_heading_for_each_day(btask):
    said = btask("what is on this week")
    assert "**Tomorrow, Tuesday 10 November**" in said and "**Thursday 12 November**" in said, said


# --- 4. getting in touch is one act said five ways ----------------------------------------------------

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)


@pytest.fixture
def calls(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(verb: str):
        for text, when in ((f"# Calls\n\n{verb} mum on 26 October. Long chat about the garden.", dt.datetime(2026, 10, 26, 9)),
                           ("# Todo\n\n- [ ] Call dad", dt.datetime(2026, 10, 27, 9))):
            entry = manager.create_entry(session, text, "Personal")
            entry.created_at = entry.updated_at = when
        session.commit()
        return lambda q: _ask(client, q, notes_only=True, answer_from="notes")["text"]

    return build


ASKS = ["when did I call mum", "when did I phone mum", "when did I ring mum", "when did I text mum", "when did I message mum",
        "when did I last phone mum"]


@pytest.mark.parametrize("verb", ["Called", "Phoned", "Rang", "Texted", "Messaged"])
def test_when_did_i_phone_is_the_day_with_the_notes_own_verb(calls, verb):
    go = calls(verb)
    for question in ASKS:
        assert go(question) == f"On Monday 26 October, you {verb.lower()} mum.", (question, go(question))


def test_a_phone_the_object_is_not_a_call(calls):
    said = calls("Called")("when did I buy my phone")
    assert "you called mum" not in said, said


def test_the_contact_verbs_are_one_synonym_group():
    from tessellate.ai import composer_ask

    for word in ("phone", "ring", "rang", "rung", "text", "message"):
        assert "call" in composer_ask._build_synonyms()[word]  # noqa: SLF001


def test_long_form_still_reads_a_plain_fact():
    assert composer_ahead.long_form("Thu 12 Nov 9:30", date(2026, 11, 9)) == "Thursday 12 November, 9:30"
