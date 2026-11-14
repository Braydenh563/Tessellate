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
