"""Deleting a message says what the chat now counts (CHAT_PLAN, the owner's 2026-10-10 bugs, L-chat-19).

The owner: "I just asked another question, didnt like the response so I deleted
it, and now somehow the token usage I was at for that chat has lowered??" The
figure is right to fall (it counts the turns that still exist); what was wrong
is that it changed later with nothing saying why. The DELETE answers with the
new total, the header shows it at once, and the undo toast says the change.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def test_the_delete_answers_with_the_tokens_of_the_turns_left(client):
    cid = client.post("/conversations", json={"question": "q1", "answer": "a1", "tokens": 300}).json()["id"]
    client.post(f"/conversations/{cid}/turns", json={"question": "q2", "answer": "a2", "tokens": 200})
    assert client.get(f"/conversations/{cid}").json()["tokens"] == 500
    gone = client.delete(f"/conversations/{cid}/turns/1").json()
    assert gone["tokens"] == 300
    assert sum(int(m.get("tokens") or 0) for m in gone["removed"]) == 200


def _body(name: str) -> str:
    text = app_js_text()
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_the_header_shows_the_new_total_at_once_and_a_stale_meter_goes():
    body = _body("deleteChatTurn")
    assert "renderChatUsage(result.tokens)" in body
    #: The meter reads the last turn's prompt: with that turn gone it described nothing left.
    assert re.search(r"renderChatContextMeter\(null\)", body)


def test_the_undo_toast_says_the_change():
    body = _body("chatTurnUndo")
    assert "tokens" in body and "down from" in body
