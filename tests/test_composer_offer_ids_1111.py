"""A bare typed yes after "Gather them into one note?" or "Track your lifts in a table?" (OPEN O5): the
offer's note holds the notes' words, which the next turn no longer has, so the server keeps it under an id
the page sends back (`consent_store`, never the text). The yes is the consent; it runs with Undo, once."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from tessellate.ai import composer_talk, consent_store
from tessellate.core.database import Entry
from tessellate.entry import manager
from tests import _gold
from tests import _seed_r9_1109 as r9


@pytest.fixture
def chat(client, session, monkeypatch):
    for n in _gold.load()["notes"]:
        made = manager.create_entry(session, n["content"], category_name=n["category"], tags=n["tags"])
        session.flush()
        row = session.get(Entry, made.id)
        row.created_at = row.updated_at = datetime.fromisoformat(n["date"] + "T10:00:00")
    session.commit()
    r9.fix_clock(monkeypatch)
    consent_store.reset_for_tests()
    return client


def _ask(client, question, history=None, **extra):
    """(answer text, offer from the grounding event, all events)."""
    out = r9.ask(client, question, history=history, notes_only=False, **extra)
    offer = next((e["support"]["offer"] for e in out["events"] if e.get("type") == "grounding" and (e.get("support") or {}).get("offer")), None)
    return out["text"], offer, out["events"]


def _notes(session) -> list[str]:
    session.expire_all()
    return [e.content or "" for e in session.scalars(select(Entry)).all()]


GATHER, TRACK = "what jokes have I saved?", "how's the gym going?"


@pytest.mark.parametrize(("question", "label", "kept"), [
    (GATHER, "Gather them into one note?", "Because the student ate his homework"),
    (TRACK, "Track your lifts in a table?", "| 8 September | 80 kg | 60 kg |"),
])
def test_a_note_offer_carries_the_id_of_what_the_server_holds(chat, question, label, kept):
    text, offer, _ = _ask(chat, question)
    assert offer["label"] == label and offer["offer_id"] and text.endswith(label), offer
    #: The page gets an id, and the text only because the button needs it; the yes never reads the page's copy.
    assert consent_store.peek(offer["offer_id"])["offer"]["text"] == offer["text"]


@pytest.mark.parametrize("question", [GATHER, TRACK])
def test_a_typed_yes_makes_the_held_note_once_with_undo(chat, session, question):
    text, offer, _ = _ask(chat, question)
    before = _notes(session)
    turn = [{"question": question, "answer": text, "offer_id": offer["offer_id"]}]
    _reply, _o, events = _ask(chat, "yes", history=turn)
    made = [c for c in _notes(session) if c not in before]
    assert len(made) == 1 and made[0].strip() == offer["text"].strip(), (made, events)
    assert any(e.get("undo") or e.get("type") in ("undo", "done") for e in events), events
    _ask(chat, "yes", history=turn)
    assert len(_notes(session)) == len(before) + 1, "the id was spent by the first yes"


def test_a_yes_without_the_id_or_with_another_answer_in_between_makes_nothing(chat, session):
    text, offer, _ = _ask(chat, GATHER)
    before = _notes(session)
    _ask(chat, "yes", history=[{"question": GATHER, "answer": text}])
    _ask(chat, "yes", history=[{"question": GATHER, "answer": text + "\n\nSomething else was asked.", "offer_id": offer["offer_id"]}])
    _ask(chat, "yes", history=[{"question": GATHER, "answer": text, "offer_id": "made-up-id"}])
    assert _notes(session) == before


def test_the_yes_is_the_consent_only_for_a_yes(chat, session):
    text, offer, _ = _ask(chat, TRACK)
    before = _notes(session)
    _ask(chat, "yes but only the first one", history=[{"question": TRACK, "answer": text, "offer_id": offer["offer_id"]}])
    _ask(chat, "no thanks", history=[{"question": TRACK, "answer": text, "offer_id": offer["offer_id"]}])
    assert _notes(session) == before and consent_store.peek(offer["offer_id"])


def test_the_held_sentence_is_unit_readable_without_a_route():
    key = consent_store.park({"offer": {"line": "Gather them into one note?", "text": "Jokes\n\nOne.\n\nTwo."}})
    turn = [{"question": "q", "answer": "Two jokes.\n\nGather them into one note?", "offer_id": key}]
    assert composer_talk.held_offer("sure", turn) == "Jokes\n\nOne.\n\nTwo."
    assert composer_talk.held_offer("sure", turn) is None


def test_the_page_sends_the_held_id_back_until_the_button_is_pressed():
    from tests._app_js import app_js_text

    js = app_js_text()
    assert 'chatHeldOffer = groundingSupport?.offer?.offer_id || ""' in js
    assert "offer_id: chatHeldOffer" in js
    assert 'chatHeldOffer === offer.offer_id) chatHeldOffer = ""' in js
