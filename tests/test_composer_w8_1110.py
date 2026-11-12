"""W8 (2026-11-10): composer dates, events and footers, rows B11 to B20. One test per row, probed first and fixed
as a class. Clock fixed: the r5 seed is Saturday 7 November 2026, the bt seed Monday 9 November 2026."""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

import tests._seed_bt_1109 as bt
from tessellate.ai import composer_ahead, recognise, source_check
from tessellate.ai import recognise_questions
from tests._r5_1108 import driver


@pytest.fixture
def r5(client, session, monkeypatch):
    return driver(client, session, monkeypatch)


@pytest.fixture
def btask(client, session, monkeypatch):
    bt.seed(session)
    bt.fix_clock(monkeypatch)
    return lambda q: bt.ask(client, q, notes_only=True)["text"]


def _stream(client, question: str, locale: str | None = None) -> list[dict]:
    body = {"question": question, "use_tools": False, **({"locale": locale} if locale else {})}
    with client.stream("POST", "/chat/stream", json=body) as response:
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


# --- B11 the write day is not bolted on a fact that has its own date -----------------------------------

@pytest.mark.parametrize("question", ["when is Sara's birthday", "when is sara's birthday"])
def test_a_fact_with_its_own_date_is_not_dated_by_the_day_it_was_written(r5, question):
    text = r5(question)["text"]
    assert "14 March" in text and "written" not in text, text


def test_how_long_ago_did_i_write_a_note_is_its_own_shape(r5):
    assert r5("how long ago did I write the Sara note")["text"] == "You wrote the Sara note four weeks ago, on Thursday 8 October."


def test_a_when_did_i_write_ask_still_names_the_day(r5):
    assert "written on Thursday 8 October" in r5("when did I write the Sara note")["text"]


def test_a_named_fact_in_a_from_line_keeps_no_write_day(btask):
    text = btask("is the Orchard deadline next week")
    assert "today:" not in text and "16 November" in text, text


# --- B12 footers name no question words the answer did not need ---------------------------------------

@pytest.mark.parametrize("question", ["what's new with uni", "brief me on Lisbon", "is my passport valid", "what is my gym schedule",
                                      "what is the name of my dentist", "is there anything new on Atlas"])
def test_a_footer_does_not_name_a_frame_word(r5, question):
    text = r5(question)["text"]
    assert not any(f"“{w}”" in text for w in ("new", "brief", "valid", "schedule", "name")), text


# --- B13 no sources under an unfound answer ---------------------------------------------------------------

@pytest.mark.parametrize("question", ["how many notes mention Marcus", "do I have an appointment", "what is the capital of France"])
def test_an_unfound_answer_carries_no_source_rows(client, r5, question):
    metas = [e for e in _stream(client, question) if e["type"] == "meta"]
    assert len(metas) == 2 and metas[-1]["raw_results"] == [], metas


def test_a_found_answer_keeps_its_sources(client, r5):
    metas = [e for e in _stream(client, "what is Sara's favourite colour") if e["type"] == "meta"]
    assert len(metas) == 1 and len(metas[0]["raw_results"]) == 1


# --- B14 a habit is on its days, and "anything on Wednesday" is the dated list ----------------------------

@pytest.mark.parametrize("question", ["what's on Wednesday", "do I have anything on Wednesday", "is there anything on Wednesday"])
def test_a_habit_is_placed_on_its_day(btask, question):
    text = btask(question)
    assert "Gym on Monday, Wednesday and Friday at 7am" in text and "Wednesday 11 November" in text, text


def test_a_habit_is_not_a_deadline_in_a_week_list(btask):
    assert "Gym" not in btask("what's due this week")


def test_a_day_with_nothing_says_the_next_one_without_a_stray_stop(btask):
    text = btask("is there anything on Sunday")
    assert "launch. (" not in text and "The next one is Deadline" in text, text


# --- B15 an event question is answered from the notes' own sentences first --------------------------------

@pytest.mark.parametrize("question", ["what happened on 25 October", "what did I do on 25 October"])
def test_an_event_ask_leads_with_the_sentence_that_holds_the_date(r5, question):
    text = r5(question)["text"]
    assert text.startswith("On 25 October, your notes say:\n- Ran 6 km on 25 October.") and "Gym plan" in text, text


# --- B16 a date is not an unbacked figure ------------------------------------------------------------------

def test_the_prompts_own_clock_backs_a_date_in_the_answer():
    prompt = "You are Atlas. Today is Wednesday, and the next seven days are Thu 5 Nov, Fri 6 Nov. The current date and time is 2026-11-04T09:00 (UTC)."
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": "what did I write today"}]
    answer = "Nothing went into your notes today, 4 November."
    assert source_check.unbacked_claims(answer, source_check.sources_from_messages(messages)) == []


def test_a_date_the_clock_does_not_hold_is_still_flagged():
    messages = [{"role": "system", "content": "Today is Wednesday. The current date and time is 2026-11-04T09:00"}, {"role": "user", "content": "hi"}]
    assert source_check.unbacked_claims("It was on 23 November.", source_check.sources_from_messages(messages)) == ["23"]


# --- B17 last week is Monday to Sunday everywhere; one head for a list ------------------------------------

@pytest.mark.parametrize("today, back", [(date(2026, 11, 7), 12), (date(2026, 11, 9), 7), (date(2026, 11, 8), 13)])
def test_last_week_counted_in_days_starts_on_the_monday_before(today, back):
    assert recognise_questions.days_since("last week", datetime(today.year, today.month, today.day, 12)) == back


def test_past_week_stays_a_rolling_seven_days():
    assert recognise_questions.days_since("the past week", datetime(2026, 11, 7, 12)) == 7


@pytest.mark.parametrize("question", ["what did I save last week", "what did I write in October", "list the notes I made in October"])
def test_a_window_list_has_one_head_and_a_capital(r5, question):
    text = r5(question)["text"]
    head = text.splitlines()[0]
    assert head[:1].isupper() and "(1 to 31 October)" not in head, head


def test_a_title_less_note_is_named_by_its_first_line_in_a_list(r5):
    text = r5("what did I save last week")["text"]
    assert "[“hi”](#/notes/" in text and "[hi](#/notes/" not in text, text


# --- the owner's naming decision: first line, about six words, an ellipsis -----------------------------------

def test_a_title_less_note_is_cited_by_its_first_words_not_its_day(btask):
    text = btask("compare Priya and Marcus")
    #: D25 took the bracketed name off the quote; the quote is the note's own first line, so it is
    #: not named by its day either.
    assert "Marcus Lee, chair of the garden" in text and "your note" not in text, text


def test_the_bare_marcus_note_is_counted_for_who_is_marcus(btask):
    text = btask("who is Marcus")
    assert "Marcus comes up in four notes" in text and "Marcus Lee, chair of the garden committee" in text, text


# --- B18 a bare day and month follows the locale the request carried ----------------------------------------

@pytest.mark.parametrize("text, locale, said", [
    ("what's due on 12/11", "en-US", "what's due on 11 December"),
    ("what's due on 12/11", "en-GB", "what's due on 12 November"),
    ("what is on 3/4", "en-US", "what is on 4 March 2027"),
    ("what is on 3/4", "en-AU", "what is on 3 April 2027"),
    ("how much is 1/2 of 10", "en-US", "how much is 1/2 of 10"),
    ("add 1/2 cup of milk", "en-US", "add 1/2 cup of milk"),
])
def test_a_numeric_day_is_spelled_by_the_locale(text, locale, said):
    assert recognise.spell_numeric_days(text, date(2026, 11, 9), locale) == said


@pytest.mark.parametrize("locale, day", [("en-GB", "Thursday 12 November"), ("en-US", "Friday 11 December")])
def test_chat_reads_a_numeric_day_in_the_locale_it_carries(client, btask, locale, day):
    events = _stream(client, "what's due on 12/11", locale)
    assert day in "".join(e["delta"] for e in events if e["type"] == "answer")


def test_only_a_question_goes_through_the_numeric_day_reader():
    #: A note typed with "3/4" is saved as typed; a skill's text keeps its characters too.
    today = date(2026, 11, 9)
    assert recognise.spell_asked_days("remember to pay on 3/4", today, "en-US") == "remember to pay on 3/4"
    assert recognise.spell_asked_days("what is due on 3/4", today, "en-US", plain=False) == "what is due on 3/4"
    assert recognise.spell_asked_days("what is due on 3/4", today, "en-US") == "what is due on 4 March 2027"


# --- B19 a month or holiday word is a topic; the bounds of a window are read ---------------------------------

def test_a_month_is_not_a_synonym_of_the_other_months(r5):
    text = r5("what have I written about December")["text"]
    assert "MOT due 15 December" in text and "Rent" not in text and "Flights" not in text, text


def test_before_a_holiday_is_a_window_that_ends_the_day_before(r5):
    text = r5("what is due before Christmas")["text"]
    assert text.startswith("For Sat 7 Nov to Thu 24 Dec you have four dated items") and "christmas" not in text.lower().replace("christmas", "", 0)[40:], text


def test_the_next_two_weeks_and_overdue_read_right(r5):
    assert "next 2 weeks (Sat 7 Nov to Fri 20 Nov)" in r5("what is on in the next two weeks")["text"]
    assert r5("anything overdue")["text"] == "Nothing is overdue."


# --- B20 a verdict writes the day long -----------------------------------------------------------------------

def test_a_verdict_writes_the_date_long(btask):
    text = btask("is the dentist tomorrow")
    assert text.startswith("No, not tomorrow. Thursday 12 November, 9:30, from your Dentist note"), text


def test_a_yes_verdict_keeps_the_weekday_capital(btask):
    assert btask("is the team sync tomorrow").startswith("Yes, Tuesday 10 November at 2pm")


@pytest.mark.parametrize("fact, long", [
    ("Thu 12 Nov 9:30", "Thursday 12 November, 9:30"),
    ("Dentist check-up on 11 November.", "Dentist check-up on Wednesday 11 November."),
    ("Nothing dated.", "Nothing dated."),
])
def test_long_form_writes_the_day_in_full(fact, long):
    assert composer_ahead.long_form(fact, date(2026, 11, 9)) == long
