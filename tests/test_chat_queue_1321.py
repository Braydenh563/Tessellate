"""INBOX 1321: "I cant type in the chat bar while it is generating, I want to
be able to queue messages, and edit or delete/bring back queued messages".
Measured with chatqueue1321.js (POSTs held 3s): box enabled mid-answer, two
queued, Edit moved the third back into the box, the second sent after the
first, queue empty at the end."""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_a_send_mid_answer_queues_and_the_end_of_a_turn_sends_the_next():
    text = _read("chat-attach.js")
    send = text[text.index("async function sendChatMessage("):text.index("function chatQueueShow(")]
    assert 'if (!$("chat-stop").classList.contains("hidden"))' in send and "chatQueue.push(typed)" in send
    assert "sendChatMessage(chatQueue.shift())" in send and "!chatQueueHeld" in send
    turn = text[text.index("async function chatSendTurn("):][:6000]
    assert "input.disabled = true" not in turn


def test_stop_holds_the_queue_and_the_list_has_edit_and_remove():
    assert _read("wiring.js").count("chatQueueHeld = true") == 2
    kit = _read("reply-kit.js")
    paint = kit[kit.index("function chatQueuePaint("):]
    assert "Edit: back into the box" in paint and "Remove from the queue" in paint
