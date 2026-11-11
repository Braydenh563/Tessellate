"""model-facts-1027 rows 6, 14 and 15 (w34-def1-1111): the three checks the model's words could not yet be held to.

Row 6: "nothing matched" with a model up is the model's to say once a check reads a negative.
Row 14: a yearless date in the facts is read both ways when the year is a guess.
Row 15: "by 10" is a time when the facts state it in any ordinary form, "5.30pm" included.
Every provider here is the fake transport; whether a real model keeps to these is unmeasured
(see docs/roadmap/agent-remaining/w34-def1-1111.md, "Row 7")."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import fact_check, librarian
from tessellate.api import routes_chat
from tessellate.core.database import Document

#: A fixed clock (CLAUDE.md section 8), Wednesday 11 November 2026, 12:00.
NOW = datetime(2026, 11, 11, 12, 0)


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch):
    monkeypatch.setattr(routes_chat, "user_now", lambda _config=None: NOW)


# --- Row 15: the hours the facts state ------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("facts", "hours"),
    [
        ("due at 5pm", {"5", "17"}),
        ("due 5:30 pm", {"5", "17"}),
        # "5.30pm" was read as the hour 30 (and 6 and 18): the minutes are no hour.
        ("due 5.30pm", {"5", "17"}),
        ("due 5 p.m.", {"5", "17"}),
        ("due 17:00", {"5", "17"}),
        ("due at 17h00", {"5", "17"}),
        ("due 17.00", {"5", "17"}),
        ("due at 5 o'clock", {"5"}),
        ("due at noon", {"12"}),
        ("due at midnight", {"12", "0", "24"}),
        ("due half past 5", {"5"}),
        ("due quarter to 6", {"5", "6"}),
        ("10am-11am", {"10", "11"}),
    ],
)
def test_the_hours_the_facts_state_are_known_in_any_ordinary_form(facts, hours):
    assert hours <= fact_check._known(facts, "", NOW)


def test_the_minutes_and_a_decimal_are_no_hour():
    known = fact_check._known("due 5.30pm; it costs 3.14 and 2.50", "", NOW) - {"2025", "2026", "2027"}
    assert not ({"30", "3", "2", "14", "50"} & known), known


@pytest.mark.parametrize(
    ("facts", "prose", "ok"),
    [
        ("Reminder: call mum, due 5.30pm", "Call mum is due by 5.", True),
        ("Reminder: call mum, due 5 p.m.", "Call mum is due by 17.", True),
        ("Reminder: call mum, due at noon", "Call mum is due by 12.", True),
        ("Reminder: call mum, due half past 5", "Call mum is due by 5.", True),
        # Still refused: an hour nothing states (a model's "by 5" about a reminder the engine did not list).
        ("Reminder: call mum, due 5.30pm", "Call mum is due by 6.", False),
        ("Reminder: call mum", "Call mum is due by 5.", False),
    ],
)
def test_a_by_hour_is_kept_only_when_the_facts_state_it(facts, prose, ok):
    assert fact_check.keeps(prose, facts, "what is due", {}, False, NOW) is ok


# --- Row 14: a date with no year ------------------------------------------------------------------------------

def test_a_yearless_date_half_a_year_off_is_read_both_ways():
    """"20 April" is 160 days ahead (2027) or 205 days back (2026) of 11 November: the nearest year is a guess."""
    facts = "Reminder: dentist, 20 April"
    assert fact_check.keeps("The dentist is in 160 days.", facts, "when is the dentist", {}, False, NOW)
    assert fact_check.keeps("The dentist was 205 days ago.", facts, "when is the dentist", {}, False, NOW)
    assert not fact_check.keeps("The dentist is in 300 days.", facts, "when is the dentist", {}, False, NOW)
    assert not fact_check.keeps("The dentist is in 190 days.", facts, "when is the dentist", {}, False, NOW)


def test_a_yearless_date_with_a_clear_year_keeps_one_reading():
    """"5 January" is 55 days ahead or 310 back: only the near one stands, as before."""
    facts = "Reminder: call mum, 5 January"
    assert fact_check.keeps("Call mum is in 55 days.", facts, "when", {}, False, NOW)
    assert not fact_check.keeps("Call mum was 310 days ago.", facts, "when", {}, False, NOW)


def test_the_two_readings_of_one_date_are_not_a_span_between_them():
    """A year apart is not a span the facts carry: the readings are alternatives, not two dates."""
    facts = "Reminder: dentist, 20 April"
    assert not fact_check.keeps("The dentist is 365 days away.", facts, "when is the dentist", {}, False, NOW)
    assert not fact_check.keeps("The dentist is 3 weeks away.", facts, "when is the dentist", {}, False, NOW)


def test_a_second_date_is_spanned_from_each_reading_of_the_first():
    """Two dates, one of them a guess: the days between them are the same under either year when the other is yearless
    and follows it, and the dated one fixes the year."""
    facts = "Reminders: dentist, 20 April; flights, 20 April 2027"
    assert fact_check.keeps("The dentist is the day of the flights.", facts, "when", {}, False, NOW)


def test_the_nearest_unit_rule_is_the_rounding_of_a_span():
    """Row 14's other half, pinned: a span is kept to the nearest of the unit the prose uses (half a unit either way),
    never to a coarser one. By design, since people round; see test_fact_check_1027's tolerance table."""
    facts = "Reminder: pay rent, 14 November 2026"  # 3 days from 11 November 12:00 by the calendar
    assert fact_check.keeps("Pay rent is in 3 days.", facts, "when", {}, False, NOW)
    assert fact_check.keeps("Pay rent is in 2 days and 12 hours.", facts, "when", {}, False, NOW)
    assert not fact_check.keeps("Pay rent is in 4 days.", facts, "when", {}, False, NOW)
    assert not fact_check.keeps("Pay rent is in 1 week.", facts, "when", {}, False, NOW)


# --- Row 6: a negative claim ----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "prose",
    [
        "I couldn't find any notes about zanzibar.",
        "Nothing in your notes mentions Zanzibar.",
        "You haven't written anything on Zanzibar yet.",
        "There are no notes on Zanzibar.",
        "No luck: none of your notes are about Zanzibar. Want to write one?",
        "I looked, and your notes don't say anything about it.",
    ],
)
def test_a_reply_that_says_nothing_was_found_is_a_negative(prose):
    assert fact_check.says_nothing_found(prose, "what do I know about zanzibar")


@pytest.mark.parametrize(
    "prose",
    [
        "",
        "Here is what I found about Zanzibar.",
        "I found a note about Zanzibar from May.",
        "Your notes say Zanzibar has 3 islands.",
        "I couldn't find that, but your note on Tokyo says the flight is at 9.",
        "According to your notes, Zanzibar is in Tanzania.",
        "Sure!",
        "Zanzibar is an island off Tanzania.",
        "I couldn't find any notes. You have 4 notes about travel.",
        "Nothing matched.\n\n- Tokyo trip\n- Lisbon trip",
        "I couldn't find it. " * 12,
    ],
)
def test_a_reply_that_claims_a_find_or_adds_a_fact_is_not(prose):
    assert not fact_check.says_nothing_found(prose, "what do I know about zanzibar")


def _ask(client, question: str) -> tuple[str, list[dict]]:
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return "".join(e.get("delta", "") for e in events if e["type"] == "answer"), events


def _documents_only(session) -> None:
    """A notebook with a document and no note: retrieval finds no note, so the plain miss is what the engine says."""
    session.add(Document(title="Cooking", content="pasta and oat milk"))
    session.commit()


def test_nothing_matched_is_said_by_the_model_when_its_words_are_a_negative(ai_client, fake_ollama, session):
    _documents_only(session)
    fake_ollama.librarian_reply = "Nothing in your notes mentions Zanzibar, I'm afraid."
    answer, events = _ask(ai_client, "what do I know about zanzibar")
    assert fake_ollama.chat_calls, "the model was never asked"
    assert answer.startswith("Nothing in your notes mentions Zanzibar")
    assert librarian.NO_RESULTS_MESSAGE not in answer
    #: The model is named by the reply's own stats (the badge reads `stats.model` first).
    assert [e for e in events if e["type"] == "stats"][-1].get("model")


@pytest.mark.parametrize(
    "prose",
    ["Here is what I found about Zanzibar: it has 3 islands.", "Your notes say Zanzibar is in Tanzania.", "Hello!", "Nothing here, but your note on Tokyo says the flight is at 9."],
)
def test_nothing_matched_stays_the_engines_when_the_model_claims_a_find(ai_client, fake_ollama, session, prose):
    _documents_only(session)
    fake_ollama.librarian_reply = prose
    answer, events = _ask(ai_client, "what do I know about zanzibar")
    assert fake_ollama.chat_calls
    assert answer.startswith(librarian.NO_RESULTS_MESSAGE)
    assert prose not in answer
    assert not [e for e in events if e["type"] == "stats" and e.get("model")]


def test_the_model_is_asked_with_the_plain_miss_as_its_facts(ai_client, fake_ollama, session):
    _documents_only(session)
    fake_ollama.librarian_reply = "I couldn't find anything on Zanzibar."
    _ask(ai_client, "what do I know about zanzibar")
    asked = fake_ollama.chat_calls[-1]
    assert librarian.NO_RESULTS_MESSAGE in asked[-1]["content"] and "zanzibar" in asked[-1]["content"].lower()


def test_an_empty_notebook_keeps_the_engines_first_steps(ai_client, fake_ollama):
    """No note and no document at all: "You have no notes yet" is the engine's, with no model asked."""
    fake_ollama.librarian_reply = "Nothing in your notes mentions Zanzibar."
    answer, _events = _ask(ai_client, "what do I know about zanzibar")
    assert answer.startswith("You have no notes yet")
    assert not fake_ollama.chat_calls
