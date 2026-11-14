"""CHAT_PLAN Answering rows A1 to A23 (LEDGER L-chat-78 to 99): each plan line's own phrasing asked of the
audit-1031 notebook (clock fixed at Saturday 31 October 2026, 11:30) with no model. A probe that stays a gap
names it in the LEDGER row, not here."""

from __future__ import annotations

import pytest

from tessellate.ai import composer
from tests import _seed_1031c as seed
from tests.test_composer_688 import TODAY as TODAY688, _note


@pytest.fixture
def ask(client, session, monkeypatch):
    seed.seed(session)
    go = seed.asker(client, monkeypatch)
    return lambda question, history=None: go(question, history=history)[0]


def test_a1_a_person_is_found_with_no_model(ask):
    said = ask("who is Priya")
    assert "Priya to send mockups" in said and "only note that names Priya" in said


def test_a10_a_person_is_recalled_from_the_sentences_that_name_them(ask):
    assert "Coffee with Anna on Saturday 31 October at Brunetti" in ask("what do I know about Anna")


def test_a2_a_past_date_is_said_in_words_with_the_exact_day(ask):
    said = ask("when did I last go to the gym")
    assert "On 28 September, about five weeks ago" in said


def test_a3_days_until_a_named_holiday_are_counted_with_both_dates(ask):
    said = ask("how many days until Christmas")
    assert said.startswith("55 days") and "25 December 2026" in said


def test_a3_days_since_a_note_are_counted_from_the_note_date(ask):
    assert "4 November" in ask("how long since my last dentist visit")


def test_a21_how_often_and_last_time_come_from_the_dated_notes(ask):
    assert "once, on 28 September" in ask("how often do I go to the gym")


def test_a9_a_past_window_lists_its_notes_newest_first_with_a_count(ask):
    said = ask("what did I write last week")
    assert "eleven notes" in said.lower() and "last week" in said.lower()
    assert said.index("Sun 25 Oct") < said.index("Sat 24 Oct") < said.index("Fri 23 Oct")


def test_a9_what_changed_this_week_groups_by_day(ask):
    said = ask("what changed this week")
    assert "you made ten notes" in said and "**Thu 29 Oct:**" in said


def test_a12_what_is_due_reads_the_dated_notes_with_no_model(ask):
    said = ask("what is due this week")
    assert "three dated items" in said.lower() and "**Tomorrow, Sunday 1 November**" in said


def test_a13_what_is_open_lists_unticked_items_with_their_notes(ask):
    said = ask("what is open")
    assert "Eight unticked checklist items are still open" in said and "Renew passport" in said


def test_a14_what_contradicts_names_the_dropped_plan(ask):
    assert "no later note picks up your plan to see Kyoto and Nara" in ask("what contradicts")


def test_a15_patterns_state_recurrence_with_dates(ask):
    assert "has come up eight times since 14 July" in ask("what patterns do you see in my notes")


def test_a16_a_measured_line_states_its_count_and_unit(ask):
    assert "about 833 words across 54 notes" in ask("how many words have I written")


def test_a20_a_summary_has_a_lead_and_offers_more(ask):
    said = ask("summarise the Tokyo trip")
    assert "Tokyo trip" in said and "Say “more” for the rest." in said


def test_a19_a_definition_is_the_sentence_that_says_is_a():
    notes = [_note(1, "Sprint\n\nA sprint is a two week block of work.", 3), _note(2, "Lunch with Sam on Friday.", 5)]
    said = composer.compose("what is a sprint", notes, today=TODAY688)["text"]
    assert "A sprint is a two week block of work." in said
