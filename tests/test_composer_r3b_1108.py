"""Composer round 3, rows left after the first batch (audit-1107-composer-r3.md):
R3-6, R3-15, R3-8, R3-9, R3-14, R3-22, R3-23, R3-26, R3-27, R3-28. Every question
runs through the digest then the composer, as the route does, with a fixed clock
and no model."""

from __future__ import annotations

import pytest

from tessellate.ai import composer, composer_frame
from tests._seed_r2_1107 import _route_answer
from tests.test_composer_r3_1107 import TODAY, _pool, say

PHONE_NOTE = "# Jose\n\nJose is my landlord. Phone 020 7946 0999. He fixes the boiler."


# --- R3-6: how many <thing> is a count, never a synonym's line -------------------------------


@pytest.mark.parametrize("question", ["how many cells", "how many cells?", "number of cells"])
def test_r3_6_a_counted_thing_no_note_says_is_none_not_a_phone_number(question):
    said = say(question, PHONE_NOTE, "Dentist check-up on 11 November.")
    assert said == "None of your notes mention cells.", said


def test_r3_6_a_counted_thing_a_note_gives_a_figure_for_is_still_counted():
    said = say("how many bananas", "# Banana bread\n\n3 ripe bananas, 200 g flour.")
    assert "3" in said and "bananas" in said, said


# --- R3-15: one name for a title-less note: its first six words, clipped, in quotes -----------

UNTITLED = (
    "Dentist said to floss more and use the soft brush, and to come back in six months.",
    "Cell respiration happens in the mitochondria and makes ATP.",
    "# Lisbon trip\n\nFlights cost $420 return.",
)


def test_r3_15_name_of_is_the_first_six_words_clipped_in_quotes():
    assert composer_frame.name_of({"content": UNTITLED[0]}) == "“Dentist said to floss more and…”"
    assert composer_frame.name_of({"content": "Sara likes jazz"}) == "“Sara likes jazz”"
    assert composer_frame.name_of({"content": UNTITLED[1]}) == "“Cell respiration happens in the mitochondria…”"


def test_r3_15_a_listing_names_an_untitled_note_by_its_words_and_dates_it_after():
    text = composer.compose("what did I write recently", _pool(*UNTITLED), today=TODAY, recent=True)["text"]
    assert "[From today]" not in text, text
    assert "[“Dentist said to floss more and…”](#/notes/1) (today)" in text, text
    assert "[“Cell respiration happens in the mitochondria…”](#/notes/2) (today)" in text, text
    assert "[**Lisbon trip**](#/notes/3) (today)" in text, text


def test_r3_15_a_property_denial_names_an_untitled_note_the_same_way():
    said = say("what is the address of the dentist", UNTITLED[0], "Sara likes jazz")
    assert said == "The note that starts “Dentist said to floss more and…” has no address.", said


# --- R3-8: the same ask gets the same answer ---------------------------------------------------

LISTS = (
    "# Todo\n\n- [ ] Book MOT\n- [x] Pay council tax\n- [ ] Email landlord",
    "# Lisbon packing list\n\n- [x] Passport\n- [ ] Charger\n- [ ] Sunscreen",
    "# Packing for Tokyo\n\n- [ ] Rail pass\n- [ ] Adapter",
)


def _wednesday_pool():
    pool = _pool(*LISTS, "Dentist check-up on Wednesday 11 November at 3pm.", "Standup moved to Wednesday at 10am.")
    for note in pool[3:]:
        note["dated_in_window"] = True
    return pool


@pytest.mark.parametrize("question", ["do I have anything on Wednesday", "have I got anything on Wednesday", "do I have something on Wednesday"])
def test_r3_8_a_day_name_gets_the_same_answer_whichever_way_it_is_asked(question):
    same = _route_answer("what is on Wednesday", _wednesday_pool())["text"]
    assert "Dentist check-up" in same and "Standup" in same, same
    assert _route_answer(question, _wednesday_pool())["text"] == same


def test_r3_8_my_list_with_several_lists_asks_which():
    said = say("what is on my list", *LISTS)
    assert said == "Which list: Todo, Lisbon packing list or Packing for Tokyo?", said


def test_r3_8_my_list_with_one_list_shows_it():
    assert "Passport" in say("what is on my list", LISTS[1], "Dentist check-up on 11 November.")


def test_r3_8_my_todo_is_the_note_called_todo_either_way():
    first, second = say("what's on my todo", *LISTS), say("what is in my todo", *LISTS)
    assert first == second and "Book MOT" in first and "Passport" not in first, first


# --- R3-9: one stem for a word across readers: "shop" finds Shopping and its prices -------------

SHOP = (
    "# Shopping\n\n| Item | Price |\n|---|---|\n| Milk | £1.20 |\n| Bread | £2.50 |\n| Cheese | £4.00 |",
    "My phone is a Pixel 8, bought in March for £549.",
    "Do not buy perfume again.",
    "Went to the corner shop for bread and milk.",
)


@pytest.mark.parametrize("question", ["what do I know about shop", "what do I know about shops", "what do I know about shopping"])
def test_r3_9_a_word_and_its_plural_find_the_same_notes_and_not_a_synonym_beside_a_literal_hit(question):
    said = say(question, *SHOP)
    assert "Shopping" in said and "corner shop" in said, said
    assert "Pixel" not in said and "perfume" not in said, said


@pytest.mark.parametrize("question", ["what did I buy in the shop", "how much did I spend on shopping", "what did I spend on the shop"])
def test_r3_9_the_prices_of_a_shopping_note_answer_a_spending_ask(question):
    said = say(question, *SHOP)
    assert "£1.20" in said and "no amounts" not in said, said


# --- R3-14: a connector only before a sentence; a one-sided compare says so once ---------------


def test_r3_14_a_list_in_another_note_is_named_by_its_note_not_joined_in_lower_case_words():
    from tessellate.ai import composer_answer, composer_body
    from tessellate.ai.composer_read import read_note

    pool = _pool("# Reading list\n\n- The Dispossessed\n- Middlemarch\n- A Fire Upon the Deep", "Dune was great.")
    views = [read_note(n, i) for i, n in enumerate(pool)]
    out = composer_answer._Answer({v.id: v for v in views}, TODAY)
    composer_body._other(out, [s for s in views[0].sentences if s.kind == "item"], "separately", set(), [], "x", None)
    assert out.text == "Your note **Reading list** lists The Dispossessed, Middlemarch and A Fire Upon the Deep.", out.text


def test_r3_14_a_compare_with_one_empty_side_says_so_once():
    said = say("compare Lisbon and Tokyo", "# Lisbon trip\n\nFlights leaving 12 May.", "Sara likes jazz")
    assert "Only Lisbon appears in your notes; nothing mentions Tokyo." in said, said
    assert "no mention" not in said and "Nothing focuses solely" not in said, said


# --- R3-22: "what am I reading" is the sentence that says it is going on ---------------------

READING = ("# Reading\n\nThree books to read this year:\n- Piranesi\n- Dune\n- Middlemarch", "# Books\n\nCurrently reading Piranesi. Finished Dune in September.")


@pytest.mark.parametrize("question", ["what am I reading", "what book am I reading"])
def test_r3_22_am_i_doing_leads_with_the_sentence_that_says_it(question):
    said = say(question, *READING)
    assert said.startswith("Currently reading Piranesi"), said
    assert "Three books to read" not in said.split("\n\n")[0], said


# --- R3-23: an amount is named by what it bought, never by when or by a whole clause -----------

BOUGHT = (
    "# Shopping\n\n| Item | Price |\n|---|---|\n| Milk | £1.20 |\n| Bread | £2.50 |\n| Cheese | £4.00 |",
    "My phone is a Pixel 8, bought in March for £549.",
    "Order 4471 from Amazon arrives Tuesday. Cost £34.",
    "# Dentist bill\n\nPaid £85 for the check-up.",
)


@pytest.mark.parametrize("question", ["what did I buy", "what have I bought"])
def test_r3_23_each_amount_is_named_by_the_thing_not_by_a_month_or_a_clause(question):
    said = say(question, *BOUGHT)
    assert said == "Your notes record £675.70 spent: Shopping £7.70, Your phone £549, Order £34 and Dentist bill £85.", said


# --- R3-27: "and the flights" under a Lisbon answer is the Lisbon flights ----------------------


@pytest.mark.parametrize("second", ["and the flights", "and the flights?"])
def test_r3_27_and_a_thing_narrows_to_the_subject_the_turn_before_named(second):
    from tests._seed_r2_1107 import chain

    said = chain(["what is the Lisbon trip", second])[1]
    assert "$420" in said and "$900" not in said, said
    assert "two notes" not in said, said


# --- R3-26: a carried term never rides into an unrelated ask (already answered correctly) -------


def test_r3_26_a_new_property_word_does_not_carry_the_old_unmatched_term():
    from tests._seed_r2_1107 import chain

    said = chain(["what do I know about the Tokyo trip", "when does it start", "how much does it cost"])
    assert all("None of these" not in s and "mention" not in s for s in said[1:]), said
    assert "$900" in said[2], said


# --- R3-28: the sentence holding the asked unit leads; a definition leads with the opening line --


def test_r3_28_how_long_leads_with_the_length_not_the_flights():
    from tests._seed_r2_1107 import ask

    assert ask("how long is the Tokyo trip").startswith("Staying in Shinjuku for six nights"), ask("how long is the Tokyo trip")


def test_r3_28_what_is_a_titled_note_leads_with_its_opening_line():
    from tests._seed_r2_1107 import ask

    assert ask("what is the Lisbon trip").startswith("Flights cost $420 return, leaving 12 May"), ask("what is the Lisbon trip")


@pytest.mark.parametrize("question", ["what does espresso cost", "how much does the espresso machine cost"])
def test_r3_28_a_price_ask_over_unpriced_notes_says_so(question):
    said = say(question, "# Espresso\n\nMachine is a Gaggia Classic. Dial in at 18 g in, 36 g out.", "Dentist on Friday at 3pm.")
    assert said.startswith("None of your espresso") and said.endswith("give a price."), said


# --- how long: "2h50" is a length of time, and the line that says it about the thing asked leads ---

PORTUGAL = (
    "# Portugal trip, overview\n\nTen days in May: four in Lisbon, a day in Sintra, three in Porto, two in the Douro valley. Train between the cities, a car only for the valley.",
    "# Trains\n\nLisbon to Porto on the Alfa Pendular, 2h50. Tickets open 60 days ahead and are half price if booked early.",
    "# Flights\n\nOut to Lisbon, back from Porto, so no day is lost going back. Booked, seats 14A and 14B.",
)


@pytest.mark.parametrize("order", [(0, 1, 2), (1, 0, 2), (2, 0, 1)])
def test_how_long_the_train_is_answered_by_the_line_that_gives_the_journey_time(order):
    said = say("How long is the train from Lisbon to Porto?", *(PORTUGAL[i] for i in order))
    assert said.startswith("Lisbon to Porto on the Alfa Pendular, 2h50"), said
