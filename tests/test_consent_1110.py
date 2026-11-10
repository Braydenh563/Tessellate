"""Consent for every act (owner, 2026-11-10, HANDOVER "Consent for every act"): no act in
chat, Ask or the Guide changes anything until the person presses Confirm or types a yes in
any wording; a typed no drops it; a typed yes reaches only the card the turn before left
waiting. Model on and off alike. Clock fixed at Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from tessellate.ai import consent, tools
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core.database import Entry, Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


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
    return [{"question": question, "answer": first["text"], "pending_act": card["label"], "pending_steps": card["steps"], "pending_skipped": card["skipped"]}]


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


def test_a_typed_yes_runs_a_parked_tool_call(client, session):
    _notebook(session)
    history = [{"question": "make a note", "answer": "Atlas wants to: create a note.", "pending_act": "create a note", "pending_tool": {"name": "create_note", "arguments": {"content": "# Parked\n\nbody"}}}]
    events = _ask(client, "yes please", history=history)
    session.expire_all()
    assert session.scalar(select(func.count()).select_from(Entry).where(Entry.content.contains("Parked"))) == 1, events["text"]
