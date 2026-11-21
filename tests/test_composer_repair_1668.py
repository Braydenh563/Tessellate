"""INBOX 1668 (b), the owner, 2026-11-04: "not what ai asked" was searched for and
answered "Your notes have this to say: ... These notes do not mention "asked"".
A correction turn is repair, not a search: a short sorry, then the earlier ask
restated and a question about what was meant; never a lookup of the complaint's
words. Read by class (`repair_turn`, INBOX 1357), typos included, model off and
on alike (CHAT_PLAN decision 75)."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import intent, question_noise, repair_turn
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 11, 4, 10, 5)

REPAIRS = [
    "not what ai asked", "not what I asked", "that's wrong", "you misunderstood", "thats not what i asked", "wrong", "not what i meant",
    "no that's not it", "you got me wrong", "nt what i askd", "that is not what I asked for", "no, that's not right", "you misunderstood me",
    "thats wrong", "that's not what I was asking", "I didn't ask that", "no that's wrong", "Not what I asked!", "that's incorrect",
    "you misread that", "you got it wrong", "that is not right", "not what i ment", "thats not wut i asked", "you didn't understand",
    "no, not what I meant", "That's not it", "you've misunderstood", "wrong answer", "that is wrong", "no I meant", "not right",
]
#: Statements and questions that carry their own content are not corrections.
NOT_REPAIRS = [
    "that's wrong, I was in Paris in 2019", "what is wrong with the garden plan", "is it wrong to book the dentist for the 21st",
    "no one called about the dentist", "what did I ask the dentist", "I asked Sam about the boiler", "what was not right in the review",
    "show my notes about golf", "the answer is in my gym note", "who misunderstood the brief", "no", "nope",
]


@pytest.fixture
def notebook(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st.")
    manager.create_entry(session, "# Commitments\n\nYou do not have the 48-hour extension.")
    session.commit()


HISTORY = [{"question": "when is my dentist appointment", "answer": "Your check-up is on the 21st.[1]", "objects": ["Dentist"]}]


@pytest.mark.parametrize("said", REPAIRS)
def test_a_correction_is_read_as_repair(said):
    assert repair_turn.is_repair(said), said
    assert question_noise.social_kind(said) == "repair", said
    assert intent.classify(said) == intent.SMALLTALK, said


@pytest.mark.parametrize("said", NOT_REPAIRS)
def test_a_message_with_its_own_content_is_not_a_correction(said):
    assert not repair_turn.is_repair(said), said
    assert question_noise.social_kind(said) != "repair", said


def _never_a_search(out: dict) -> None:
    text = out["text"]
    assert text.startswith("Sorry"), text
    assert not out.get("grounding"), text
    assert "do not mention" not in text and "have this to say" not in text and "extension" not in text and "Taking that as" not in text, text


@pytest.mark.parametrize("said", REPAIRS)
@pytest.mark.parametrize("kw", [{}, {"notes_only": True, "use_tools": False}])
def test_a_correction_after_a_reply_restates_the_ask_and_asks(client, notebook, said, kw):
    out = _ask(client, said, history=HISTORY, **kw)
    _never_a_search(out)
    assert "“when is my dentist appointment”" in out["text"] and out["text"].rstrip().endswith("?"), out["text"]


@pytest.mark.parametrize("said", REPAIRS)
def test_a_correction_with_nothing_before_asks_what_was_meant(client, notebook, said):
    out = _ask(client, said)
    _never_a_search(out)
    assert out["text"].rstrip().endswith("?"), out["text"]


@pytest.mark.parametrize("said", ["no", "nope", "nah", "No."])
def test_a_bare_no_after_a_reply_is_a_correction(client, notebook, said):
    _never_a_search(_ask(client, said, history=HISTORY))
    _never_a_search(_ask(client, said))


@pytest.mark.parametrize("said", ["no", "nope"])
def test_a_bare_no_to_a_question_is_its_answer(client, notebook, said):
    history = [{"question": "golf", "answer": "I did not find that. Should I look in your notes?"}]
    assert not _ask(client, said, history=history)["text"].startswith("Sorry")


def test_a_second_correction_repairs_the_ask_before_the_first(client, notebook):
    history = HISTORY + [{"question": "not what ai asked", "answer": "Sorry, I took “when is my dentist appointment” for a search of your notes. What were you after?"}]
    out = _ask(client, "no that's wrong", history=history)
    _never_a_search(out)
    assert "“when is my dentist appointment”" in out["text"], out["text"]


@pytest.mark.parametrize("said", ["not what ai asked", "that's wrong", "you misunderstood", "nope"])
def test_the_same_with_a_model_running(ai_client, fake_ollama, notebook, said):
    """With a model running the model words a correction in Chat (decision 75);
    what must hold is that no search is made for the complaint's words: no
    notes are grounded or quoted. The Ask box answers a social turn with its
    hint, again with no search."""
    for kw in ({}, {"notes_only": True, "use_tools": False}):
        out = _ask(ai_client, said, history=HISTORY, **kw)
        assert not out.get("grounding"), (kw, out)
        assert "do not mention" not in out["text"] and "extension" not in out["text"] and "Dentist" not in out["text"], (kw, out["text"])
        assert not out.get("hint") or "Sorry" not in out["text"]
