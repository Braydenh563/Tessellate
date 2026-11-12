"""Gaps in the composer's acts found by the ledger sweep (L47 and kin): each
sentence read, planned and, where it writes, run on a real notebook.
Fixed clock: Thursday 12 November 2026, 10:00."""

from __future__ import annotations

import datetime as dt

from tessellate.ai import acts
from tessellate.entry import manager

NOW = dt.datetime(2026, 11, 12, 10, 0)


def test_rename_with_a_to_in_both_names_picks_the_note_that_exists(session):
    manager.create_entry(session, "# Trip to Spain\n\nFlights booked.")
    manager.create_entry(session, "# Trip\n\nOther.")
    session.commit()
    parsed = acts.parse("rename Trip to Spain to Trip to Portugal", NOW)
    card = acts.preview(session, parsed)["card"]
    assert "Trip to Portugal" in card["label"]
    assert "Trip to Spain" in card["label"]


def _intent(text):
    parsed = acts.parse(text, NOW)
    return parsed and parsed["intent"]


def test_every_stem_with_a_word_after_it_reads_as_its_own_act():
    """L72: the palette's stem is the act's own words, so what a person types after it reads as that act."""
    tails = {"unpin": "dentist", "unlink": "gym from the running note", "set_name": "Sam", "run_skill": "daily review"}
    for intent, tail in tails.items():
        stem = acts.ACTS[intent].stem
        assert stem and _intent(stem + tail) == intent, (intent, stem)


def test_a_note_by_its_number_takes_tags_in_every_wording():
    """L71: 'tag note 12 gym', 'untag note #12 gym', 'pin note number 12', 'pin #12'."""
    got = acts.parse("tag note 12 gym", NOW)
    assert got["intent"] == "tag" and got["note_id"] == 12 and got["tags"] == ["gym"]
    got = acts.parse("untag note #12 gym", NOW)
    assert got["intent"] == "untag" and got["note_id"] == 12 and got["tags"] == ["gym"]
    for text in ("pin note number 12", "pin #12", "pin note 12"):
        got = acts.parse(text, NOW)
        assert got["intent"] == "pin" and got["note_id"] == 12, text


def test_a_reminder_that_is_the_day_before_asks_which_day_not_what_it_is_for(client):
    """L49: 'Remind me about Dentist the day before' keeps 'Dentist' as the thing and asks for the time."""
    from tests.test_composer_route_688 import _ask

    got = acts.parse("Remind me about Dentist the day before", NOW)
    assert got["intent"] == "reminder" and got["text"] == "Dentist" and not got["time_given"]
    text = _ask(client, "Remind me about Dentist the day before", use_tools=True)["text"]
    low = text.lower()
    assert ("when" in low or "time" in low) and "about dentist" in low and "to dentist" not in low
    assert "what is it for" not in low


def test_a_reminder_with_no_time_asks_for_one_and_never_guesses_tomorrow(client, session):
    """L99: the route asks 'when' once (the card is never drawn with tomorrow 9 for 'remind me to call mum')."""
    from tests.test_composer_route_688 import _ask

    events = _ask(client, "remind me to call mum", use_tools=True)
    assert ("when" in events["text"].lower() or "time" in events["text"].lower()) and not events.get("act")


def test_a_name_with_commas_and_with_stays_one_title_and_a_plain_sentence_stays_the_body(session):
    """L50 and L24: 'Christmas with mum, dad and Sara' is the whole name; 'a note that I need to buy milk' is not made a heading."""
    got = acts.parse("new note called Christmas with mum, dad and Sara", NOW)
    assert got["content"] == "Christmas with mum, dad and Sara"
    card = acts.preview(session, got)["card"]
    assert card["label"] == "Make a new note: “Christmas with mum, dad and Sara”"
    sentence = acts.parse("make a note that I need to buy milk and call mum tomorrow", NOW)
    assert sentence["content"] == "I need to buy milk and call mum tomorrow" and not sentence["content"].startswith("#")


def test_remember_to_tonight_and_a_between_window_set_the_start_not_nine(session):
    """L207: 'remember to take the bins out tonight' is a reminder at 20:00; 'between 8 and 10' is for 8 and says so."""
    got = acts.parse("remember to take the bins out tonight", NOW)
    assert got["intent"] == "reminder" and got["due_at"] == dt.datetime(2026, 11, 12, 20, 0)
    got = acts.parse("remind me to call mum tomorrow between 8 and 10", NOW)
    assert got["due_at"] == dt.datetime(2026, 11, 13, 8, 0) and got["text"] == "Call mum between 8 and 10" and got["time_given"]
    got = acts.parse("remind me to ring the bank between 2 and 4pm", NOW)
    assert got["due_at"] == dt.datetime(2026, 11, 12, 14, 0) and got["text"] == "Ring the bank between 2 and 4pm"
    got = acts.parse("remind me to read pages from 3 to 5 tomorrow", NOW)
    assert got["text"] == "Read pages from 3 to 5" and got["due_at"].hour == 9


def test_make_it_simpler_with_no_model_says_a_model_is_needed(client):
    """L45: a rewrite of words already said is not offered as a new note or a category."""
    from tests.test_composer_route_688 import _ask

    for question in ("make it simpler", "rewrite that more formally", "please simplify it", "make this shorter"):
        text = _ask(client, question, use_tools=True)["text"]
        assert text.startswith("Rewording needs a model") and "Heads up" not in text, question
    assert "Rewording needs a model" not in _ask(client, "how do I make it simpler?", use_tools=True)["text"]


def test_a_checklist_note_card_does_not_say_its_empty_checkbox(session):
    """L194: 'make a checklist for my trip' is 'Make a new note “Trip checklist”', not '...: - [ ]'."""
    card = acts.preview(session, acts.parse("make a checklist for my trip", NOW))["card"]
    assert card["label"] == "Make a new note: “Trip checklist”"
    assert card["steps"][0]["arguments"]["content"].startswith("# Trip checklist")
    for text in ("call anna", "call the dentist"):
        got = acts.parse(text, NOW)
        #: L99 and decision 50 (asked once, never guessed) moved this: a reminder with no time now asks for one.
        assert got["intent"] == "reminder" and not got["time_given"] and acts.missing(got) == ["due_at"]


def test_undo_says_the_inverse_of_a_tag_a_link_and_a_reminder_too():
    """L223: 'undo' after any act whose inverse can be said stands for the sentence that does it."""
    from tessellate.ai import reading

    pairs = {
        "pin the gym note": "unpin the gym note",
        "tag the gym note with health and fitness": "remove the tag health, fitness from the gym note",
        "remove the tag urgent from the gym note": "tag the gym note with urgent",
        "tag note 12 with x": "remove the tag x from note 12",
        "link the gym note to the running note": "unlink the gym note from the running note",
        "unlink the gym note from the running note": "link the gym note to the running note",
        "remind me to call mum tomorrow at 3pm": "cancel the call mum reminder",
    }
    for said, inverse in pairs.items():
        got = reading.follow("undo that", [{"text": said}], NOW)
        assert got == (inverse, "undo"), (said, got)
        assert acts.parse(inverse, NOW) is not None, inverse
    assert reading.follow("undo", [{"text": "rename the gym note to Fit"}], NOW) is None
