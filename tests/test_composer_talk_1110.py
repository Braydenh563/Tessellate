"""W9 rows B22 to B27, the owner's phrasings, no model, clock fixed at Tuesday 10 November 2026, 09:00:

- B22 a chip never asks about "the Sara" (a name no note puts after an article).
- B23 "yes" after an offer the composer made carries the offer out.
- B24 every confirm line names both buttons; a tag or move names the note; "undo" takes back a pin as well as a tick.
- B25 "call anna" in lower case is a reminder; "make a checklist for my trip" is a checklist note.
- B26 the prose asks "Shall I remind you to X?", the button keeps "Remind you to X?".
- B27 a find searches the topic, not the whole sentence."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import commands, composer_digest, composer_replies, composer_talk, find_topic
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.entry import manager
import tests._seed_1031c as seed_c

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


def _said(events):
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


# --- B22 ---------------------------------------------------------------------


def test_a_chip_never_asks_about_the_sara(client, session, monkeypatch):
    seed_c.seed(session)
    go = seed_c.asker(client, monkeypatch)
    _text, events = go("what else have I saved about the sara")
    asks = [a for e in events if e.get("type") == "offer" for a in (e.get("offer") or {}).get("asks", [])]
    asks += [a for e in events if e.get("type") == "grounding" for a in (e.get("asks") or e.get("next") or [])]
    assert asks and not any("the Sara" in a or "the sara" in a for a in asks), asks


# --- B23 ---------------------------------------------------------------------

OFFER_TURN = [{"question": "what do I know about the boiler", "answer": "Email the landlord about the boiler.\n\nShall I remind you to call the plumber by Friday about the boiler?"}]


@pytest.mark.parametrize("yes", ["yes", "Yes please", "yeah", "sure", "ok do it", "go ahead", "yep!"])
def test_a_yes_takes_up_the_offer(yes):
    assert composer_talk.accepted_offer(yes, OFFER_TURN) == "remind me to call the plumber by Friday about the boiler"


@pytest.mark.parametrize("answer", ["Remind you to call the plumber?", "Set a reminder to call the plumber?", "Want a nudge to call the plumber?"])
def test_the_button_wordings_are_taken_up_too(answer):
    assert composer_talk.accepted_offer("yes", [{"question": "q", "answer": f"Some answer.\n\n{answer}"}]) == "remind me to call the plumber"


@pytest.mark.parametrize("question, history", [
    ("yes", None), ("yes", []), ("yes", [{"question": "q", "answer": "Nothing in your notes about that."}]),
    ("yes", [{"question": "q", "answer": "Save it as a checklist note?"}]), ("no", OFFER_TURN), ("yes and what about the dentist", OFFER_TURN),
])
def test_a_yes_with_no_offer_behind_it_is_left_alone(question, history):
    assert composer_talk.accepted_offer(question, history) is None


def test_yes_after_the_offer_sets_the_reminder(client):
    events = _events(client, "yes", history=OFFER_TURN)
    assert "Good. Anything else?" not in _said(events)
    act = next(e for e in events if e.get("type") == "act" or (e.get("type") == "answer" and False))
    assert any("plumber" in json.dumps(step) for step in act["steps"]), act


def test_yes_with_nothing_offered_is_still_small_talk(client):
    assert "plumber" not in _said(_events(client, "yes", history=[{"question": "hello", "answer": "Hello."}]))


# --- B24 ---------------------------------------------------------------------


@pytest.mark.parametrize("voice", ["natural", "professional"])
def test_every_confirm_wording_names_both_buttons(voice):
    for line in composer_replies.CONFIRM[voice]:
        assert "Confirm" in line.replace("confirm", "Confirm") and "Cancel" in line, line


def test_a_tag_and_a_move_name_the_note(client, session):
    manager.create_entry(session, "# Car\n\nService due in March.")
    session.commit()
    tag = _said(_events(client, "tag the car note #admin"))
    assert "“Car”" in tag and "1 note" not in tag, tag
    move = _said(_events(client, "move the car note to Admin"))
    assert "“Car”" in move and "1 note" not in move, move


def test_undo_takes_back_a_pin():
    from tessellate.ai import reading

    turns = [{"text": "pin the gym note"}]
    assert reading.follow("undo", turns, NOW) == ("unpin the gym note", "undo")
    assert reading.follow("undo that", [{"text": "unpin the gym note"}], NOW) == ("pin the gym note", "undo")
    assert reading.follow("undo", [{"text": "what is on today"}], NOW) is None


def test_undo_alone_still_gives_the_keys(client, session):
    manager.create_entry(session, "# Dentist\n\nCheck-up booked.")
    session.commit()
    assert "Ctrl+Z" in _said(_events(client, "undo"))


# --- B25 ---------------------------------------------------------------------


@pytest.mark.parametrize("said, text", [("call anna", "Call Anna"), ("Call anna", "Call Anna"), ("call the dentist", "Call the dentist"), ("ring mum", "Ring mum"), ("phone my boss", "Phone my boss")])
def test_a_bare_call_is_a_reminder_in_lower_case_too(said, text):
    got = commands.read(said, NOW)
    assert got and got["intent"] == "reminder" and got["text"] == text, got


@pytest.mark.parametrize("said", ["call me", "call back", "call it", "call it a day", "call now", "call tomorrow"])
def test_a_call_that_is_no_person_is_not_a_reminder(said):
    assert (commands.read(said, NOW) or {}).get("intent") != "reminder", said


def test_call_anna_asks_when(client, session):
    manager.create_entry(session, "# Anna\n\nAnna's birthday is 3 March.")
    session.commit()
    said = _said(_events(client, "call anna"))
    assert "These notes do not mention" not in said and "remind you to call Anna" in said, said


@pytest.mark.parametrize("said, title", [
    ("make a checklist for my trip", "# Trip checklist"), ("make a packing list for the beach", "# Beach packing list"),
    ("create a checklist for the garden", "# Garden checklist"),
])
def test_a_checklist_for_a_subject_is_a_checklist_note(said, title):
    got = commands.read(said, NOW)
    assert got and got["intent"] == "new_note" and got["content"].startswith(title + "\n\n- [ ] "), got


def test_a_checklist_with_items_is_unchanged():
    got = commands.read("make a checklist for the kitchen: sponge, soap", NOW)
    assert got["content"] == "# Kitchen checklist\n\n- [ ] Sponge\n- [ ] Soap"


def test_make_a_checklist_for_my_trip_makes_the_note(client):
    events = _events(client, "make a checklist for my trip")
    act = next(e for e in events if e.get("type") == "act")
    assert "Trip checklist" in json.dumps(act["steps"]), act
    assert "checklist" in _said(events).lower() and "not sure I can do that" not in _said(events)


# --- B26 ---------------------------------------------------------------------


def test_the_prose_asks_and_the_button_keeps_its_label():
    offer = composer_digest._asked({"kind": "reminder", "label": "Remind you to ask the tutor?", "text": "Ask the tutor"})
    assert offer["label"] == "Remind you to ask the tutor?" and offer["line"] == "Shall I remind you to ask the tutor?"
    other = {"kind": "reminder", "label": "Want a nudge to ask the tutor?"}
    assert composer_digest._asked(other) == other


# --- B27 ---------------------------------------------------------------------


@pytest.mark.parametrize("said, topic", [
    ("notes similar to my dentist one you know", "dentist"), ("notes like the lisbon one", "lisbon"), ("notes related to my boiler or something", "boiler"),
    ("similar to the sourdough note please", "sourdough"), ("dentist", "dentist"), ("notes about tea", "notes about tea"),
])
def test_a_find_searches_the_topic(said, topic):
    assert find_topic.topic(said) == topic


def test_the_owners_find_searches_dentist(client, session):
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st.")
    session.commit()
    for extra in ({}, {"use_tools": True}):
        events = _events(client, "find notes simlar to my dentist one yk", **extra)
        tool = next(e for e in events if e.get("type") == "tool")
        assert tool["arguments"] == {"query": "dentist"}, tool
        assert "Dentist" in _said(events)
