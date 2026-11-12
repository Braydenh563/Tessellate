"""Answers that quoted a note stop quoting it once it is private (SEC-14).

The 2026-10-05 audit: `set_private` encrypted the note, its history, its
dates and its search rows, but a stored Ask answer or a saved chat reply that
had quoted it before kept the words in the clear, readable in Ask history,
in the conversation and in the database file. Now each one that cited the
note (by id) or repeats a sentence of it is redacted, and says so.
"""

from __future__ import annotations

import json

import pytest

from tessellate.core import deps, vault
from tessellate.core.database import AskTurn, Conversation
from tessellate.entry import manager_private

SECRET = "# Zebrasecret plan\n\nMy bank PIN is 4417, the spare key is at Quokkatown station."
QUOTE = "the spare key is at Quokkatown station"


@pytest.fixture(autouse=True)
def open_vault(session):
    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    yield
    vault.close()


def _seed(client):
    note = client.post("/entries", json={"content": SECRET}).json()["id"]
    other = client.post("/entries", json={"content": "Bread wants a long proof."}).json()["id"]
    with deps.get_db().session() as s:
        cited = AskTurn(question="where is the key", answer=f"It is at Quokkatown station [{note}].",
                        raw_result_ids=json.dumps([note, other]))
        quoted = AskTurn(question="key?", answer=f"Your note says {QUOTE}.", raw_result_ids="[]")
        clean = AskTurn(question="bread?", answer="A long proof.", raw_result_ids=json.dumps([other]))
        chat = Conversation(title="keys", messages=json.dumps([
            {"role": "user", "content": "where is my key"},
            {"role": "assistant", "content": "At Quokkatown station.", "raw_results": [{"id": note}],
             "steps": [{"tool": "get_note", "result": SECRET}], "thinking": "PIN is 4417"},
            {"role": "user", "content": "and the bread"},
            {"role": "assistant", "content": "A long proof.", "raw_results": [{"id": other}]},
        ]))
        attached = Conversation(title="attached", messages=json.dumps([
            {"role": "user", "content": "summarise this", "note_ids": [note]},
            {"role": "assistant", "content": "A plan about a spare key."},
        ]))
        untouched = Conversation(title="bread", messages=json.dumps([
            {"role": "user", "content": "bread"},
            {"role": "assistant", "content": "A long proof."},
        ]))
        s.add_all([cited, quoted, clean, chat, attached, untouched])
        s.commit()
        ids = (cited.id, quoted.id, clean.id, chat.id, attached.id, untouched.id)
    return note, ids


def test_making_a_note_private_redacts_the_answers_that_quoted_it(client):
    note, (cited, quoted, clean, chat, attached, untouched) = _seed(client)
    assert client.post(f"/entries/{note}/privacy", json={"private": True}).status_code == 200
    with deps.get_db().session() as s:
        for turn_id in (cited, quoted):
            turn = s.get(AskTurn, turn_id)
            assert "Quokkatown" not in turn.answer
            assert turn.answer == manager_private.PRIVATE_ANSWER_REDACTED
        assert s.get(AskTurn, clean).answer == "A long proof."

        messages = json.loads(s.get(Conversation, chat).messages)
        assert messages[0]["content"] == "where is my key"  # the person's own words stay
        assert messages[1]["content"] == manager_private.PRIVATE_ANSWER_REDACTED
        assert messages[1].get("redacted") is True
        assert "Quokkatown" not in json.dumps(messages) and "4417" not in json.dumps(messages)
        assert messages[3]["content"] == "A long proof."

        attached_messages = json.loads(s.get(Conversation, attached).messages)
        assert attached_messages[1]["content"] == manager_private.PRIVATE_ANSWER_REDACTED
        assert json.loads(s.get(Conversation, untouched).messages)[1]["content"] == "A long proof."


def test_none_of_its_words_stay_in_the_file(client):
    note, _ = _seed(client)
    client.post(f"/entries/{note}/privacy", json={"private": True})
    data_dir = deps.get_config().data_dir
    raw = b"".join(
        (data_dir / name).read_bytes()
        for name in ("tessellate.db", "tessellate.db-wal")
        if (data_dir / name).exists()
    ).lower()
    assert b"quokkatown" not in raw


def test_ask_history_shows_the_redaction(client):
    note, (cited, *_rest) = _seed(client)
    client.post(f"/entries/{note}/privacy", json={"private": True})
    body = client.get(f"/ask-history/{cited}").json()
    assert body["answer"] == manager_private.PRIVATE_ANSWER_REDACTED
