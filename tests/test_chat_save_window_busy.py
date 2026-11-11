"""sm-1111 row 25: between the end of a stream and the end of its save the
composer is back (Stop hidden) but the turn has not finished. Measured with the
pacing stand-in model and a 2.5 s delayed `POST /conversations`: a second
message sent in that window made a second conversation (list 2, posts 2).
The composer queue now counts that window as busy for the conversation it
belongs to, so the message waits and is sent when the turn returns."""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend/js"


def _read(name):
    return (JS / name).read_text(encoding="utf-8")


def test_queue_busy_covers_the_save_window_of_the_open_conversation():
    chat = _read("chat.js")
    assert "chatQueue.finishing.has(chatConv)" in chat
    assert "finishing: new Set()" in chat


def test_turn_marks_its_conversation_finishing_and_the_send_unmarks_it_before_draining():
    turn = _read("chat-turn.js")
    assert "chatQueue.finishing.add(convRef)" in turn
    send = _read("chat-attach.js")
    body = send[send.index("async function sendChatMessage") :]
    body = body[: body.index("\n}\n")]
    assert body.index("chatQueue.finishing.delete(") < body.index("chatQueue.next()")
