"""Composer round 3, 2026-11-07 (audit-1107-composer-r3.md): readers that fire
on an everyday word, and frames wrapped round fragments. Every question runs
through `composer.compose` (the digest first, as the route does) over a small
notebook; no model (fake transport), fixed clock."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import composer_property
from tests._seed_r2_1107 import TODAY, _route_answer

assert TODAY == date(2026, 11, 7)


def _pool(*texts: str, ago: int = 0) -> list[dict]:
    day = date.fromordinal(TODAY.toordinal() - ago).isoformat()
    return [{"id": i, "content": t, "category": "Uncategorised", "tags": [], "created_at": f"{day}T10:00:00Z"} for i, t in enumerate(texts, 1)]


def say(question: str, *texts: str, ago: int = 0) -> str:
    return _route_answer(question, _pool(*texts, ago=ago))["text"]


@pytest.mark.parametrize("question", [
    "what is the table number", "what is the seat number", "what is my lucky number", "what is the number",
    "number of notes about Sara", "how many cells", "what number is the bus",
])
def test_r3_2_a_bare_number_is_not_a_phone_number_without_a_person(question):
    assert composer_property.asked(question) == "", question


@pytest.mark.parametrize("question", [
    "what is Sara's number", "what is the number for the dentist", "what's mum's number", "give me Anna's phone number",
    "what is his number",
])
def test_r3_2_a_number_beside_a_person_or_business_is_a_phone_ask(question):
    assert composer_property.asked(question) == "phone", question


def test_r3_2_the_subject_keeps_the_way_it_was_written():
    assert composer_property.subject("what is Sara's number") == "Sara"
    assert composer_property.subject("what is the number for the dentist") == "the dentist"
    assert composer_property.subject("what is his number") == ""


def test_r3_2_a_person_no_note_gives_a_number_for_is_denied_in_the_notebooks_name():
    assert say("what is Sara's number", "Sara likes jazz", "Weekend: call Mum and meet Sara") == "None of your notes give a phone number for Sara."
    assert say("what is the number for the dentist", "Dentist check-up on 11 November") == "None of your notes give a phone number for the dentist."


# --- R3-1: the present tense is the event, not the day the note was written ------------------

UNI = ("# Uni timetable\n\nTuesday and Thursday are uni days. Cloud lab on Thursday afternoon.", "First day of uni is 21 September.")


@pytest.mark.parametrize("question", ["when does uni start", "when do I make the banana bread", "when do I add the flour", "when does the marathon start"])
def test_r3_1_a_present_tense_when_is_never_the_day_a_note_was_written(question):
    said = say(question, *UNI, "# Banana bread\n\n3 ripe bananas, 200 g flour. Bake 50 minutes at 180.", "# Marathon\n\nRace is on 14 March in Brighton.")
    assert "was written" not in said, said


@pytest.mark.parametrize("question", ["when did I write the banana bread", "when was the banana bread written", "when did I start the sourdough", "when did I make the banana bread"])
def test_r3_1_a_past_form_is_still_the_day_the_note_was_written(question):
    said = say(question, "# Banana bread\n\n3 ripe bananas, 200 g flour.", "# Sourdough\n\nFeed twice a day.")
    assert "written" in said or "wrote" in said or "made" in said or "started" in said, said


# --- R3-3: a person's age is not a thing's start -------------------------------------------

SARA = ("# Sara\n\nSara is my sister. Her birthday is on 14 March.", "Sara likes jazz", "# Gift ideas\n\nSara wants a jazz record for her birthday.")


def test_r3_3_how_old_a_person_is_says_the_notes_do_not_and_keeps_the_name_as_written():
    assert say("how old is Sara", *SARA) == "Your notes do not say how old Sara is. Her birthday is on 14 March."


def test_r3_3_a_person_with_no_birthday_has_no_borrowed_one():
    assert say("how old is Tom", "# Tom\n\nTom is my colleague.", *SARA) == "Your notes do not say how old Tom is."


def test_r3_3_an_age_a_note_gives_is_the_answer():
    assert say("how old is Anna", "# Anna\n\nAnna is my cousin. She is 34 years old.") == "She is 34 years old."


def test_r3_3_a_thing_still_counts_days_from_its_start():
    said = say("how old is my sourdough starter", "# Sourdough starter\n\nStarted on 1 October. Feed twice a day.")
    assert said == "Your sourdough starter is 37 days old, started on 1 October.", said


# --- R3-18: "when is" leads with the day still to come -------------------------------------

DENTIST = (
    "# Dentist bill\n\nPaid £85 for the check-up on 3 October.",
    "Dentist said to floss more and use the soft brush",
    "Went to the dentist on 3 October and paid the bill",
    "Dentist check-up on 11 November",
)


@pytest.mark.parametrize("question", ["when is the dentist", "whens the dentist"])
def test_r3_18_a_present_tense_when_leads_with_the_next_date_not_the_last_visit(question):
    said = say(question, *DENTIST)
    assert said.startswith("Dentist check-up on 11 November"), said


def test_r3_18_a_past_when_still_leads_with_the_visit_that_happened():
    assert "3 October" in say("when did I go to the dentist", *DENTIST).split(".")[0]


def test_r3_18_the_day_a_note_was_written_never_stands_before_an_event_with_its_own_date():
    said = say("what time is my dentist appointment", *DENTIST)
    assert "today: Went to the dentist on 3 October" not in said and "today: Paid" not in said, said
    assert "Went to the dentist on 3 October" in said, said


# --- R3-19, R3-29: hedge words are not terms, and a dated answer needs no "not mentioned" tail ---

LONG = (
    "I was wondering whether you could possibly help me find out when exactly the dentist appointment "
    "that I made some weeks ago is happening because I forgot"
)


def test_r3_19_a_hedge_adverb_is_never_called_missing():
    said = say(LONG, *DENTIST, "# Ice breakers\n\nWhat are you reading at the moment?")
    assert "possibly" not in said and "exactly" not in said and "because" not in said, said
    assert "11 November" in said, said


@pytest.mark.parametrize("question", ["when is my next dentist appointment", "what time is my dentist appointment"])
def test_r3_29_a_when_the_note_answers_with_a_date_has_no_not_mentioned_tail(question):
    said = say(question, *DENTIST)
    assert "11 November" in said and "mention" not in said and "regarding" not in said and "“appointment”" not in said, said
