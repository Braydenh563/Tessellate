"""A model turn that claims an act and made no tool call shows the act's Confirm card instead
(L114, a 1.5B run: "Make a board called Launch" answered "I've created a new board" with no call).
The claim text is replaced (`answer_final`), nothing runs before Confirm. Fake transport."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from tessellate.core.database import Entry

from tests.test_engine_routing_1114 import NOW  # noqa: F401  (the fixed clock fixture below)
from tests.test_engine_routing_1114 import _fixed_now  # noqa: F401


def _events(client, question):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line]


CASES = [
    ("Make a board called Launch", "I've created a new board called Launch for you.", "create_mindmap"),
    ("Remember that I prefer short answers", "I have saved your preference for short answers.", "save_user_preference"),
]


@pytest.mark.parametrize(("said", "claim", "tool"), CASES)
def test_a_claimed_act_with_no_call_is_the_act_card(ai_client, fake_ollama, session, said, claim, tool):
    fake_ollama.librarian_reply = claim
    before = {e.id for e in session.scalars(select(Entry))}
    events = _events(ai_client, said)
    cards = [e for e in events if e["type"] == "act" and not e.get("cancel") and not e.get("settle")]
    assert [s["name"] for s in cards[0]["steps"]] == [tool]
    final = [e for e in events if e["type"] == "answer_final"]
    shown = final[-1]["text"] if final else "".join(e["delta"] for e in events if e["type"] == "answer")
    assert "created" not in shown.lower() and "saved" not in shown.lower() and "Heads up" not in shown
    session.expire_all()
    assert {e.id for e in session.scalars(select(Entry))} == before


def test_delete_the_tag_claim_is_the_delete_tag_card(ai_client, fake_ollama, session):
    from tessellate.entry import manager

    manager.create_entry(session, "# Budget\n\nQ4.", category_name="Work", tags=["harbor"])
    session.commit()
    fake_ollama.librarian_reply = "I have deleted the tag harbor."
    events = _events(ai_client, "Delete the tag harbor")
    cards = [e for e in events if e["type"] == "act" and not e.get("cancel") and not e.get("settle")]
    assert cards and cards[0]["steps"][0]["name"] == "delete_tag"
    assert "Heads up" not in "".join(e.get("delta", "") + e.get("text", "") for e in events)


def test_a_claim_with_no_matching_act_keeps_the_heads_up(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "I created a new note titled Jokes."
    events = _events(ai_client, "write me something funny about cats")
    assert not [e for e in events if e["type"] == "act"]
    assert "Heads up" in "".join(e.get("delta", "") for e in events)


def test_a_plain_answer_to_an_act_sentence_is_left_alone(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "Sure, tell me which board you mean."
    events = _events(ai_client, "Make a board called Launch")
    assert "Sure, tell me" in "".join(e.get("delta", "") + e.get("text", "") for e in events)


#: L114 on the 1.5B (2026-11-14): "Make a mind map of Trips" answered with invented XML and "Remember that I prefer short
#: answers" with "Understood. I will keep answers short." Neither claims a write the guard's patterns catch, and neither
#: called a tool, so no card appeared. A sentence the registry reads as a write act, answered with no call, gets its card.
UNCLAIMED = [
    ("Make a mind map of Trips", 'Sure, here is a mind map of "Trips": <Map><root text="Trips"/></Map>', "create_mindmap"),
    ("Remember that I prefer short answers", "Understood. I will keep answers short from here on.", "save_user_preference"),
    ("Make a board called Launch", "Sure thing! How would you like the board to be set up?", "create_mindmap"),
]


@pytest.mark.parametrize(("said", "reply", "tool"), UNCLAIMED)
def test_an_act_sentence_answered_with_no_call_and_no_claim_still_gets_its_card(ai_client, fake_ollama, session, said, reply, tool):
    fake_ollama.librarian_reply = reply
    events = _events(ai_client, said)
    cards = [e for e in events if e["type"] == "act" and not e.get("cancel") and not e.get("settle")]
    assert cards and [s["name"] for s in cards[0]["steps"]] == [tool], [e["type"] for e in events]
    session.expire_all()
    assert not list(session.scalars(select(Entry))), "nothing ran before Confirm"


def test_a_question_that_is_no_act_gets_no_card(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "Boards are canvases for cards."
    events = _events(ai_client, "What is a board?")
    assert not [e for e in events if e["type"] == "act"]


#: L-chat-274: a model that DID call a write, but the wrong one for an act sentence the registry reads exactly
#: ("Make a board called Launch" -> add_board_shape, a frame), parks the registry's card, not its own.
def test_a_wrong_write_call_for_an_exactly_read_act_parks_the_registrys_card(ai_client, fake_ollama, session):
    fake_ollama.tool_script = [[{"name": "add_board_shape", "arguments": {"kind": "frame", "text": "Launch"}}], []]
    events = _events(ai_client, "Make a board called Launch")
    assert not [e for e in events if e["type"] == "confirm" and e["name"] == "add_board_shape"], "the model's own card is not parked"
    cards = [e for e in events if e["type"] == "act" and not e.get("cancel") and not e.get("settle")]
    assert cards and [s["name"] for s in cards[0]["steps"]] == ["create_mindmap"]
    session.expire_all()
    assert not list(session.scalars(select(Entry))), "nothing ran before Confirm"


def test_a_right_write_call_keeps_its_own_card(ai_client, fake_ollama):
    call = {"name": "create_mindmap", "arguments": {"title": "Launch", "kind": "board"}}
    fake_ollama.tool_script = [[call], []]
    events = _events(ai_client, "Make a board called Launch")
    assert [e["name"] for e in events if e["type"] == "confirm"] == ["create_mindmap"]
    assert not [e for e in events if e["type"] == "act" and not e.get("cancel") and not e.get("settle")]
