"""A Library chat card shows when the chat was last spoken in, not when its row
last changed (L512): a pin or a rename moves `updated_at`, not the conversation."""

from __future__ import annotations

import json

from tessellate.core.database import Conversation


def _chats(client):
    body = client.get("/library").json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    return [i for i in items if i["kind"] == "chat"]


def test_a_chat_item_carries_the_last_message_time(client, session):
    session.add(
        Conversation(
            title="tomatoes",
            messages=json.dumps(
                [
                    {"role": "user", "content": "why", "at": "2026-01-02T03:04:05+00:00"},
                    {"role": "assistant", "content": "water", "at": "2026-01-02T03:05:00+00:00"},
                ]
            ),
        )
    )
    session.commit()
    chat = _chats(client)[0]
    assert chat["last_at"] == "2026-01-02T03:05:00+00:00"
    assert chat["last_at"] != chat["updated_at"]


def test_a_chat_without_message_stamps_falls_back_to_the_row_time(client, session):
    session.add(Conversation(title="old", messages=json.dumps([{"role": "user", "content": "hi"}])))
    session.commit()
    chat = _chats(client)[0]
    assert chat["last_at"] == chat["updated_at"]
