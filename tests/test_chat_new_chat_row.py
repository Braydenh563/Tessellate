"""A new chat is in the list the moment its first message is sent (owner,
2026-10-12: "if I start a new chat then click on a different chat, I cant go
back to the chat I started until the ai response has finished"). Before, the
row was written at the first agent round or at the end, so a plain answer left
the chat out of the list while it streamed."""

from pathlib import Path

JS = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "chat-attach.js").read_text(encoding="utf-8")


def test_a_new_chat_is_checkpointed_when_it_is_sent():
    assert "if (convRef.id === null && !convRef.private) checkpointTurn();" in JS
    assert JS.index("if (convRef.id === null && !convRef.private) checkpointTurn();") > JS.index("async function writeCheckpoint()")
    assert JS.index("if (convRef.id === null && !convRef.private) checkpointTurn();") < JS.index("await streamChat({")


def test_an_empty_first_answer_can_be_saved(client):
    made = client.post("/conversations", json={"question": "hello there", "answer": ""})
    assert made.status_code == 201
    assert any(c["id"] == made.json()["id"] for c in client.get("/conversations").json())
