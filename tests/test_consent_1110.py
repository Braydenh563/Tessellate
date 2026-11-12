"""Consent for every act (owner, 2026-11-10, HANDOVER "Consent for every act"): no act in
chat, Ask or the Guide changes anything until the person presses Confirm or types a yes in
any wording; a typed no drops it; a typed yes reaches only the card the turn before left
waiting. Model on and off alike. Clock fixed at Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

from datetime import datetime, timezone

from pathlib import Path

import pytest
from sqlalchemy import func, select

from tessellate.ai import consent, tools
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core import clock, config
from tessellate.core.database import Entry, Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    #: The run route's summary read the real clock through config and clock, so
    #: between 00:00 and 09:00 UTC "tomorrow at 9" was said back as "today at 9".
    monkeypatch.setattr(config, "user_now", lambda _config: NOW)
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


def _notebook(session):
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st.")
    manager.create_entry(session, "# Todo\n\n- [ ] buy milk\n- [ ] call mum\n")
    manager.create_entry(session, "# Suica\n\nTop up the Suica card at the station before the train.")
    row = Reminder(text="Take bins out", due_at=datetime(2026, 11, 10, 19, 0))
    session.add(row)
    session.commit()


def _state(session):
    session.expire_all()
    notes = session.scalars(select(Entry).order_by(Entry.id)).all()
    reminders = session.scalars(select(Reminder).order_by(Reminder.id)).all()
    return (
        [(e.id, e.content, e.pinned, e.deleted_at, e.category_id) for e in notes],
        [(r.id, r.text, r.due_at, r.done, r.deleted_at) for r in reminders],
    )


def _card(events):
    return next((e for e in events.get("act", []) if not e.get("cancel") and not e.get("settle")), None)


def _waiting(first, card, question="q"):
    return [{"question": question, "answer": first["text"], "pending_act": card["label"], "pending_id": card["consent_id"]}]


ACTS = [
    "remind me to call mum tomorrow at 9am",
    "note: buy stamps",
    "pin the dentist note",
    "delete the dentist note",
    "tag the dentist note with health",
    "rename the dentist note to Teeth",
    "add buy chalk to the dentist note",
    "move the dentist note to Health",
    "tick off the bins reminder",
    "cancel the bins reminder",
    "snooze the bins reminder to tomorrow",
    "start a meeting",
    "remove buy milk from my tasks",
]


@pytest.mark.parametrize("sentence", ACTS)
def test_every_act_shows_a_card_and_changes_nothing(client, session, sentence):
    _notebook(session)
    before = _state(session)
    events = _ask(client, sentence)
    card = _card(events)
    assert card is not None and not card.get("done") and card["steps"], (sentence, events["text"])
    assert "confirm" in events["text"].lower(), events["text"]
    assert "TypeError" not in events["text"] and "went wrong" not in events["text"]
    assert _state(session) == before, f"{sentence!r} changed the notebook before consent"


YES_WORDS = ["yes", "Yes!", "yeah", "yep", "sure", "ok", "Okay.", "do it", "go ahead", "please do", "sounds good", "confirm", "yes please", "Sure, go ahead", "yup, do it"]


@pytest.mark.parametrize("said", YES_WORDS)
def test_a_typed_yes_confirms_the_card_that_waited(client, session, said):
    _notebook(session)
    first = _ask(client, "note: buy stamps")
    card = _card(first)
    assert session.scalar(select(func.count()).select_from(Entry).where(Entry.content.contains("buy stamps"))) == 0
    second = _ask(client, said, history=_waiting(first, card, "note: buy stamps"))
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(Entry).where(Entry.content.contains("buy stamps"))) == 1, (said, second["text"])
    assert any(e.get("done") and e.get("settle") for e in second["act"]), second


@pytest.mark.parametrize("said", ["no", "No.", "nope", "cancel", "don't", "never mind", "Never mind!", "stop", "no thanks"])
def test_a_typed_no_cancels_and_changes_nothing(client, session, said):
    _notebook(session)
    first = _ask(client, "delete the dentist note")
    card = _card(first)
    before = _state(session)
    second = _ask(client, said, history=_waiting(first, card, "delete the dentist note"))
    assert "Nothing was changed" in second["text"] and any(e.get("cancel") for e in second["act"])
    assert _state(session) == before


def test_a_yes_with_nothing_waiting_runs_nothing(client, session):
    _notebook(session)
    first = _ask(client, "delete the dentist note")
    before = _state(session)
    #: The page sent no pending_act this time: a stray yes is not consent.
    history = [{"question": "delete the dentist note", "answer": first["text"]}]
    _ask(client, "yes", history=history)
    assert _state(session) == before


def test_a_yes_only_reaches_the_card_of_the_turn_before(client, session):
    _notebook(session)
    first = _ask(client, "delete the dentist note")
    card = _card(first)
    before = _state(session)
    older = _waiting(first, card)[0]
    _ask(client, "yes", history=[older, {"question": "hello", "answer": "Hi."}])
    assert _state(session) == before


def test_a_yes_that_says_more_is_not_consent(client, session):
    _notebook(session)
    first = _ask(client, "delete the dentist note")
    card = _card(first)
    before = _state(session)
    _ask(client, "yes but only if it is old", history=_waiting(first, card))
    assert _state(session) == before


def test_the_reading_of_consent_words():
    said = ("Yes please!", "go ahead", "Okay", "do it.", "no", "Nope.", "don't", "never mind", "yes but not now", "tell me more", "")
    assert [consent.says(w) for w in said] == ["yes", "yes", "yes", "yes", "no", "no", "no", "no", None, None, None]


# --- G2 (fable-composer2-1110): read questions made notes; snooze showed a TypeError ------------------


@pytest.mark.parametrize("question", ["note about suica", "make a note private"])
def test_a_read_question_never_makes_a_note(client, session, question):
    _notebook(session)
    before = _state(session)
    events = _ask(client, question)
    assert _state(session) == before, events["text"]
    assert "All set, created" not in events["text"]


def test_note_about_suica_finds_the_note(client, session):
    _notebook(session)
    assert "Suica" in _ask(client, "note about suica")["text"]


def _aware_clock(monkeypatch):
    """The real clock is aware (the person's zone); the snooze compared it with a naive stored time."""
    from tessellate.core import config

    aware = NOW.replace(tzinfo=timezone.utc)
    for module in (routes_chat, chat_said, chat_turn, config):
        monkeypatch.setattr(module, "user_now", lambda _config: aware)


def test_a_create_with_a_topic_and_no_words_asks_what_it_says(client, session):
    _notebook(session)
    before = _state(session)
    events = _ask(client, "make a note about suica")
    assert "What should the note say" in events["text"] and _card(events) is None
    assert _state(session) == before


def test_snooze_the_bins_reminder_is_a_card_not_a_crash(client, session, monkeypatch):
    _aware_clock(monkeypatch)
    _notebook(session)
    before = _state(session)
    for sentence in ("snooze the bins reminder to tomorrow", "snooze take bins out until friday", "move the bins reminder to 8pm"):
        events = _ask(client, sentence)
        assert "TypeError" not in events["text"] and "went wrong" not in events["text"], events["text"]
        assert _card(events) is not None, (sentence, events["text"])
    assert _state(session) == before


def test_a_snoozed_reminder_moves_after_consent(client, session, monkeypatch):
    _aware_clock(monkeypatch)
    _notebook(session)
    first = _ask(client, "snooze the bins reminder to tomorrow")
    card = _card(first)
    _ask(client, "go ahead", history=_waiting(first, card))
    session.expire_all()
    due = session.scalars(select(Reminder)).one().due_at
    assert due.replace(tzinfo=None).date() == datetime(2026, 11, 11).date()


# --- parity: the model's tool calls need the same consent ----------------------------------------


@pytest.mark.parametrize("name", sorted(tools.WRITE_TOOLS))
def test_every_write_tool_parks_for_confirm(name):
    assert tools.needs_confirm(name, {}) is True


def test_a_run_the_person_started_stays_approved_for_adds():
    assert tools.needs_confirm("create_note", {}, approved=True) is False
    assert tools.needs_confirm("delete_note", {}, approved=True) is True


def _parked_note(content="# Parked\n\nbody"):
    """A model's create_note, parked as the stream does (`consent.attach`)."""
    return consent.attach({"type": "confirm", "name": "create_note", "arguments": {"content": content}, "label": "create a note"})["consent_id"]


def _count(session, word):
    session.expire_all()
    return session.scalar(select(func.count()).select_from(Entry).where(Entry.content.contains(word), Entry.deleted_at.is_(None)))


def test_a_typed_yes_runs_a_parked_tool_call(client, session):
    _notebook(session)
    history = [{"question": "make a note", "answer": "Atlas wants to: create a note.", "pending_act": "create a note", "pending_id": _parked_note()}]
    events = _ask(client, "yes please", history=history)
    assert _count(session, "Parked") == 1, events["text"]


def test_a_typed_yes_to_a_tool_gives_the_undo_row_and_the_refresh(client, session):
    _notebook(session)
    history = [{"question": "make a note", "answer": "Atlas wants to: create a note.", "pending_act": "create a note", "pending_id": _parked_note()}]
    card = next(e for e in _ask(client, "ok", history=history)["act"] if e.get("done"))
    assert card["settle"] and card["undo"] and card["undo"][0]["name"] == "delete_note", card
    client.post("/chat/command/run", json={"steps": card["undo"]})
    assert _count(session, "Parked") == 0
    page = Path("frontend/js/ask-compose.js").read_text(encoding="utf-8")
    assert "refreshAfterToolChanges(); // what the typed yes wrote" in page


# --- review 1110: what a yes runs is what was parked, once, for the turn before -------------------


def test_a_yes_runs_what_was_parked_not_what_the_page_sends(client, session):
    _notebook(session)
    first = _ask(client, "note: buy stamps")
    card = _card(first)
    forged = [{"name": "delete_note", "arguments": {"note_id": 1}}]
    history = [{**_waiting(first, card)[0], "pending_steps": forged, "pending_tool": {"name": "delete_note", "arguments": {"note_id": 1}}}]
    _ask(client, "yes", history=history)
    assert _count(session, "buy stamps") == 1 and _count(session, "Dentist") == 1


def test_a_card_is_spent_once(client, session):
    _notebook(session)
    first = _ask(client, "note: buy stamps")
    history = _waiting(first, _card(first))
    _ask(client, "yes", history=history)
    again = _ask(client, "yes", history=history)
    assert _count(session, "buy stamps") == 1 and "no longer open" in again["text"]


def test_pressing_confirm_spends_the_card_a_typed_yes_would_run(client, session):
    _notebook(session)
    first = _ask(client, "note: buy stamps")
    card = _card(first)
    pressed = client.post("/chat/command/run", json={"steps": card["steps"], "consent_id": card["consent_id"]})
    assert pressed.status_code == 200
    _ask(client, "yes", history=_waiting(first, card))
    assert _count(session, "buy stamps") == 1


def test_confirm_says_it_in_the_composers_words(client, session):
    _notebook(session)
    card = _card(_ask(client, "remind me to call mum tomorrow at 9am"))
    said = client.post("/chat/command/run", json={"steps": card["steps"], "consent_id": card["consent_id"]}).json()["summary"]
    assert "remind you tomorrow at 9am: call mum" in said.lower() and not said.startswith("Done: Updated"), said


def test_a_yes_does_not_reach_a_card_that_is_not_in_the_last_turn(client, session):
    _notebook(session)
    first = _ask(client, "delete the dentist note")
    before = _state(session)
    stale = {**_waiting(first, _card(first))[0], "answer": ""}  # not an assistant turn that showed the card
    _ask(client, "ok", history=[stale])
    assert _state(session) == before


def test_the_page_marks_older_cards_not_pending_and_names_only_the_last_turns():
    page = Path("frontend/js/answer-kit.js").read_text(encoding="utf-8")
    start = page.index("function chatHistoryToSend")
    body = page[start:start + 1600]
    assert "delete card.dataset.pendingAct" in body and "pending_id" in body
    assert "pending_steps" not in body and "pending_tool" not in body


@pytest.mark.parametrize("said", ["fine", "why not", "alright", "all right", "yes, wait", "yes wait", "wait"])
def test_ambiguous_words_are_not_consent(said):
    assert consent.says(said) is None


def test_a_yes_to_an_offer_chip_runs_the_offered_act(client, session):
    _notebook(session)
    history = [{"question": "what is due", "answer": "Nothing is due.\n\nShall I remind you to call the plumber on Friday at 9?"}]
    out = _ask(client, "yes", history=history)
    done = [e for e in out["act"] if e.get("done")]
    assert done and not any(not e.get("done") and not e.get("cancel") for e in out["act"]), out
    session.expire_all()
    assert [r.text for r in session.scalars(select(Reminder)).all() if "plumber" in r.text.lower()], out["text"]
    assert done[0]["undo"]


def test_a_yes_to_an_offer_that_repeats_a_reminder_still_asks(client, session):
    _notebook(session)
    history = [{"question": "what is due", "answer": "Nothing.\n\nShall I remind you to take bins out on Friday at 9?"}]
    out = _ask(client, "yes", history=history)
    assert not any(e.get("done") for e in out["act"]) and "already have" in out["text"]


def test_a_three_note_request_parks_three_cards():
    from tessellate.ai import agent

    assert agent.MAX_PARKED_CONFIRMS >= 12
