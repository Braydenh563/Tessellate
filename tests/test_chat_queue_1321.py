"""INBOX 1321: "I cant type in the chat bar while it is generating, I want to
be able to queue messages, and edit or delete/bring back queued messages".
Measured with chatqueue1321.js (POSTs held 3s): box enabled mid-answer, two
queued, Edit moved the third back into the box, the second sent after the
first, queue empty at the end.

The queue is the shared composer queue now (CHAT_PLAN B3, `composerQueue` in
palette.js, also the popup agent's and the Guide's; chat.js holds Chat's spec, `chatQueue`); these read Chat's use of it,
the same promises under the component's names."""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_a_send_mid_answer_queues_and_the_end_of_a_turn_sends_the_next():
    text = _read("chat-attach.js")
    send = text[text.index("async function sendChatMessage("):text.index("//: **A bare \"undo\" or \"redo\" typed in chat")]
    assert "if (chatQueue.busy())" in send and "chatQueue.take(" in send
    assert "chatQueue.next()" in send.split("} finally {")[1]
    chat = _read("chat.js")
    queue = _read("palette.js")[_read("palette.js").index("function composerQueue("):]
    assert "!q.held && q.items.length && !q.busy() && q.send(q.items.shift())" in queue
    assert 'composerQueue("chat", chatQueue)' in queue
    assert 'busy: () => !$("chat-stop").classList.contains("hidden")' in chat[chat.index("const chatQueue = {"):]
    turn = _read("chat-turn.js")[:6000]  # moved out of chat-attach.js (boot diet)
    assert "input.disabled = true" not in turn


def test_stop_holds_the_queue_and_the_list_has_edit_and_remove():
    assert _read("wiring.js").count("chatQueue.held = true") == 2
    kit = _read("reply-kit.js")
    paint = kit[kit.index("composerQueue.paint = (q) => {"):]
    assert "Edit: back into the box" in paint and "Remove from the queue" in paint
