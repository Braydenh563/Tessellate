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
    #: Moved 2026-11-09: a table or seat number is a property of its own now (composer-r6), still never a phone.
    assert composer_property.asked(question) != "phone", question
    assert composer_property.asked(question) in ("", "table", "seat"), question


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


# --- R3-17: "abuot lisbn" is not a name called at the end -----------------------------------

@pytest.mark.parametrize("question", ["wat do i know abuot lisbn", "what do i know abot tokio", "tel me abuot lisbn"])
def test_r3_17_a_slipped_head_word_still_has_its_object(question):
    from tessellate.ai import vocative

    assert vocative.split(question).names == [], question


# --- R3-10: "you planned to" only before a verb that is one ---------------------------------

def test_r3_10_a_negated_imperative_is_quoted_never_planned():
    said = say("what do I know about shop", "# Sara birthday ideas\n\nA jazz record, lilies, or tickets to the theatre. Do not buy perfume again.", "# Shopping\n\n- milk\n- bread")
    assert "planned to do not" not in said and "“Do not buy perfume again”" in said, said


def test_r3_10_a_verb_that_is_a_noun_here_is_quoted_never_planned():
    said = say("first order", "Order 4471 from Amazon arrives Tuesday. Cost £34.", "Remember to book a table for dinner in Lisbon on the first night",
               "First day of uni is 21 September", "# Order of the day\n\nStandup, then lunch.")
    assert "planned to order" not in said and "Order 4471 from Amazon arrives Tuesday" in said, said


# --- R3-11, R3-12: a two-sentence or labelled line is quoted as written -------------------------

@pytest.mark.parametrize("i", [0, 1, 2])
def test_r3_11_a_two_sentence_line_is_quoted_not_reported(i):
    from tessellate.ai import composer_digest_lines

    line = "Boiler service due in December. Engineer is Mr Brunetti, phone 020 7946 0555"
    said = composer_digest_lines._said_as_written(line, i)
    assert "mentioned that" not in said and f"“{line}”" in said, said


def test_r3_12_a_label_line_keeps_its_list_and_gets_no_article():
    said = say("what do I know about table 4", "# Table plans\n\nWedding table 4: Anna, Tom and Sara", "# Shopping\n\n- milk",
               "Remember to book a table for dinner in Lisbon on the first night", "First day of uni is 21 September")
    assert "“Wedding table 4: Anna, Tom and Sara”" in said and "a wedding" not in said, said


def test_r3_12_a_title_less_note_is_named_once():
    said = say("what do I know about standup", "Order of the day: standup, lunch with Priya, dentist", "# Shopping\n\n- milk",
               "Weekly standup is every Monday at 9am in the small room", "First day of uni is 21 September")
    assert "your note the order" not in said.lower(), said


# --- R3-20, D1: the note whose title holds the subject leads ----------------------------------

def test_r3_20_a_title_with_the_subject_in_it_leads():
    said = say("who is Priya", "# The order of the day\n\nStandup, then lunch. Priya does the slides, you do the report.", "# Meeting with Priya\n\nPriya leads the design team at Acme",
               "# Project Atlas\n\nPriya owns the launch plan", "# Shopping\n\n- milk")
    assert said.index("design team") < said.index("slides"), said


def test_r3_20_defines_ranks_a_title_with_the_subject_above_a_sentence():
    from tessellate.ai import composer_digest

    class V:
        titled = True
        filed_words = frozenset()

        def __init__(self, title, text):
            from tessellate.ai import composer

            self.title, self.title_words = title, frozenset(composer._stem(w) for w in composer._words(title))
            self.sentences = [type("S", (), {"text": text})()]

    titled = V("Meeting with Priya", "Design review on Friday")
    said = V("Order of the day", "Priya is the one who does the slides")
    exact = V("Priya", "Sister")
    assert composer_digest._defines(exact, ["priya"]) > composer_digest._defines(titled, ["priya"]) > composer_digest._defines(said, ["priya"])


# --- R3-5: "date" in a date ask is not a word to find ---------------------------------------

PASSPORT = ["# Passport\n\nExpires 12 March 2031", "# Test\n\nThe unit test for the parser passes now, the date test still fails.", "# Shopping\n\n- milk",
            "Dentist check-up on 11 November"]


def test_r3_5_a_date_ask_never_finds_the_date_test():
    said = say("what is the date of my passport expiry", *PASSPORT)
    assert "date test" not in said and "12 March 2031" in said, said


@pytest.mark.parametrize("question", ["what dates do I have", "which date is my passport expiry", "what is the date of the exam"])
def test_r3_5_date_is_no_search_term_in_a_date_ask(question):
    from tessellate.ai import composer

    assert "date" not in composer.subject_terms(question) and "dates" not in composer.subject_terms(question), question


# --- R3-21, E3: a place with a note of its own is not "nothing" ---------------------------------

@pytest.mark.parametrize("question", ["have I been to Tokyo", "did I go to Tokyo"])
def test_r3_21_a_place_with_its_own_note_is_named_not_denied(question):
    said = say(question, "# Tokyo trip\n\nFlights leaving 3 April. Staying in Shinjuku for six nights", "# Shopping\n\n- milk", "Went to the dentist on 3 October")
    assert "found nothing in your notes about" not in said and "Tokyo trip" in said and "3 April" in said, said


# --- R3-13: "and one more" is never a placeholder for a single item -------------------------------

def test_r3_13_a_fourth_item_is_named_not_counted():
    said = say("what do I know about Tokyo", "# Packing for Tokyo\n\n- passport\n- rail pass\n- adapter\n- umbrella", "# Tokyo trip\n\nFlights leaving 3 April. Staying in Shinjuku for six nights",
               "Tokyo has great ramen", "# Shopping\n\n- milk")
    assert "umbrella" in said and "one more" not in said, said


# --- R3-16: one note is "your newest note" ------------------------------------------------------

def test_r3_16_one_newest_note_is_singular():
    # tests/test_composer_688.py::test_the_newest_notes_for_a_question_with_no_subject, with one note.
    from tests.test_composer_688 import NOTES, ask

    newest = sorted(NOTES, key=lambda n: n["created_at"], reverse=True)[:1]
    text = ask("what did I write recently", newest, recent=True)["text"]
    assert text.startswith("Your newest note, ") and "one newest" not in text, text


# --- R3-4: "the first note about Sara" is not a search for the word first -------------------------

def test_r3_4_first_and_last_note_are_places_in_an_order_not_terms():
    from tessellate.ai import composer

    assert "first" not in composer.subject_terms("what is the first note I wrote about Sara")
    assert "last" not in composer.subject_terms("what is the last note about the dentist")
    assert "first" in composer.subject_terms("first order")


def test_r3_4_the_first_note_about_sara_is_not_the_first_day_of_uni():
    said = say("what is the first note I wrote about Sara", "# Sara\n\nSara is my sister", "First day of uni is 21 September", "Sara likes jazz", "Dinner on Friday")
    assert "First day of uni" not in said, said


# --- R3-24: two trips are not a contradiction --------------------------------------------------

def test_r3_24_notes_titled_for_different_things_never_disagree():
    from types import SimpleNamespace as NS

    from tessellate.ai import composer_body
    from tessellate.ai.composer_read import Sentence

    def sentence(note_id, text):
        return Sentence(note_id=note_id, rank=0, start=0, end=len(text), text=text, words=text.lower().replace(",", "").replace("$", "").split())

    a = sentence(1, "Flights cost $900 return, leaving 3 April")
    b = sentence(2, "Flights cost $420 return, leaving 12 May")
    trips = {1: NS(title_words={"tokyo", "trip"}), 2: NS(title_words={"lisbon", "trip"})}
    same = {1: NS(title_words={"flights"}), 2: NS(title_words={"flights", "booking"})}
    assert composer_body._disagreement([a, b]) == (a, b)
    assert composer_body._disagreement([a, b], trips) is None
    assert composer_body._disagreement([a, b], same) == (a, b)


# --- R3-37: a reading time in a sentence is words, not the footer's abbreviation ----------------

@pytest.mark.parametrize(("compact", "said"), [("under a min", "under a minute"), ("4 min read", "a 4-minute read"), ("1.5h read", "a 1.5-hour read")])
def test_r3_37_a_reading_time_is_said_in_words(compact, said):
    from tessellate.ai import composer_calc

    assert composer_calc._read_said(compact) == said


# --- R3-25: a pronoun lifted out of its note is the note's name ---------------------------------

@pytest.mark.parametrize(("question", "kept"), [("what do I know about Mum", "Mum's birthday is 4 July"), ("when is Mum birthday", "Mum likes gardening")])
def test_r3_25_a_sentence_that_opens_with_she_is_named(question, kept):
    said = say(question, "# Mum\n\nShe likes gardening and crosswords. Her birthday is 4 July", "# Shopping\n\n- milk", "Dentist check-up on 11 November", "Remember to book a table for dinner in Lisbon")
    assert "“She " not in said and "“Her " not in said, said
    assert kept in said, said


# --- R3-34: a hello late at night is not answered "Good night" ----------------------------------

@pytest.mark.parametrize("hour", [22, 23, 0, 3])
def test_r3_34_a_late_hello_is_good_evening_never_good_night(hour):
    from tessellate.ai import composer_compose

    assert composer_compose.greeted_as("hello", hour) == "evening"
    assert composer_compose.time_of_day(23) == "night"  # the clock's word is unchanged; only the greeting differs


# --- review of the round 3 head --------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "what's the number to call", "the number of children", "what is the number of mice in the lab", "how big is the number of days",
])
def test_r3_2_number_to_and_number_of_are_not_a_phone_ask(question):
    assert composer_property.asked(question) == "", question


def test_r3_2_the_number_for_a_business_is_still_a_phone_ask():
    assert composer_property.asked("what is the number for the dentist") == "phone"


@pytest.mark.parametrize("question", ["what date do I have in December", "what dates are in December", "what dates do I have in December"])
def test_r3_5_a_date_ask_with_a_verb_after_it_is_no_date_sum(question):
    from datetime import datetime

    from tessellate.ai import composer_calc

    assert composer_calc._day_question(question, datetime(2026, 11, 7).date()) is None, question  # noqa: SLF001


def test_r3_5_what_day_is_a_date_is_still_a_date_sum():
    from datetime import datetime

    from tessellate.ai import composer_calc

    assert composer_calc._day_question("what day is 3 march", datetime(2026, 11, 7).date()) is not None  # noqa: SLF001
