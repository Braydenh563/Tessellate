"""L48: "hello" and "thanks" end with chips that carry the chat on, with no model (F5), clock fixed."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.entry import manager

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


def _chips(events):
    return [a for e in events if e.get("type") == "offer" and e["offer"].get("kind") == "ask" for a in e["offer"]["asks"]]


@pytest.fixture
def notebook(session):
    manager.create_entry(session, "# Dentist\n\nCheck-up 21 November.")
    session.commit()


#: L48 first gave a bare hello or thanks starter chips. That broke the older pinned intents (small talk with
#: nothing before it has no chips: test_composer_chips_1110, test_parity_1110), so starters follow a prior turn only.
@pytest.mark.parametrize("word", ["hello", "thanks"])
def test_a_greeting_or_thanks_with_nothing_before_has_no_chips(client, notebook, word):
    assert _chips(_events(client, word)) == []


def test_thanks_after_an_answer_still_offers_that_answers_chips(client, notebook):
    first = _events(client, "when is the dentist check-up")
    answer = "".join(e.get("delta", "") for e in first if e.get("type") == "answer")
    after = _events(client, "thanks", history=[{"question": "when is the dentist check-up", "answer": answer}])
    assert _chips(after)



def test_every_starter_chip_gets_an_answer_from_the_notes(client, notebook):
    from tessellate.ai import composer_chips

    for chip in composer_chips.STARTERS:
        said = "".join(e.get("delta", "") for e in _events(client, chip) if e.get("type") == "answer")
        assert said.strip() and "not sure" not in said.lower(), (chip, said)
