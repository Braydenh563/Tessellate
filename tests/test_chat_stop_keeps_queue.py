"""Owner decision 2026-11-11: in Chat, pressing Stop while messages are queued behind the
answer ends the answer and KEEPS the queue; nothing auto-sends; the person presses Send to
continue. The queued messages stay listed (Edit and Remove) and Send runs them oldest first,
what is typed in the box going last.

The real `composerQueue` (palette.js) and `sendChatMessage` (chat-attach.js) run in node
against stubs for the turn itself; the two Stop handlers are read as text (they need the page).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _fn(text: str, head: str) -> str:
    start = text.index(head)
    return text[start : text.index("\n}\n", start) + 3]


HARNESS = r"""
const [queueSrc, sendSrc] = process.argv.slice(1);
const painted = [];
const ensureModule = () => Promise.resolve(true);
let streaming = false;
const input = { value: "", dispatchEvent() {} };
const $ = (id) => id === "chat-input" ? input : { classList: { contains: () => !streaming } };
const chatConv = { id: 1 };
const sent = [];
let finishTurn = null;
const chatTidyTyped = (t) => t;
const lazyLoadFailed = () => {};
// The turn: Stop shows while it runs; it ends when finishTurn() is called (an answer or a Stop).
const chatSendTurn = (text) => new Promise((resolve) => {
  sent.push(text);
  streaming = true;
  finishTurn = () => { streaming = false; resolve(); };
});
const chatQueue = { input: () => input, finishing: new Set(), busy: () => streaming, send: (t) => sendChatMessage(t, { keepBox: true }), before: () => null };
eval(queueSrc);
eval(sendSrc);
composerQueue.paint = (q) => painted.push(q.items.slice());
composerQueue("chat", chatQueue);
const tick = () => new Promise((r) => setTimeout(r, 5));
(async () => {
  const out = {};
  // an answer is streaming; two messages are queued behind it
  const first = sendChatMessage("first");
  await tick();
  input.value = "second"; await sendChatMessage(); input.value = "third"; await sendChatMessage();
  out.queued = chatQueue.items.slice();
  out.boxAfterQueue = input.value;
  // Stop: the wiring sets the hold, then aborts; the stopped turn ends
  chatQueue.held = true;
  finishTurn();
  await first; await tick();
  out.afterStopSent = sent.slice();
  out.afterStopItems = chatQueue.items.slice();
  out.afterStopHeld = chatQueue.held;
  out.afterStopBusy = chatQueue.busy();
  // what is typed now is held too, behind the queue
  input.value = "fourth";
  const press = sendChatMessage();
  await tick();
  out.afterSend = sent.slice();
  out.boxAfterSend = input.value;
  for (let i = 0; i < 6 && sent.length < 4; i += 1) { finishTurn(); await tick(); }
  finishTurn(); await tick();
  out.order = sent.slice();
  out.left = chatQueue.items.slice();
  out.heldAfter = chatQueue.held;
  // a Send on an empty box with the queue held also resumes it, with no "Type a message" toast
  sent.length = 0;
  streaming = true; chatQueue.items.push("a", "b"); chatQueue.held = true; streaming = false;
  input.value = "";
  await sendChatMessage(); await tick();
  out.emptySend = sent.slice();
  console.log(JSON.stringify(out));
  process.exit(0);
})();
"""


@node
def test_stop_keeps_the_queue_and_send_resumes_it_in_order() -> None:
    queue = _fn(_read("palette.js"), "function composerQueue(")
    chat_attach = _read("chat-attach.js")
    send = chat_attach[
        chat_attach.index("async function sendChatMessage(") : chat_attach.index(
            '//: **A bare "undo" or "redo"'
        )
    ]
    proc = subprocess.run(
        ["node", "-e", HARNESS, queue, send],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["queued"] == ["second", "third"] and out["boxAfterQueue"] == ""
    # Stop ended the answer; nothing was sent; the queue is intact and held
    assert out["afterStopSent"] == ["first"]
    assert out["afterStopItems"] == ["second", "third"]
    assert out["afterStopHeld"] is True and out["afterStopBusy"] is False
    # Send resumes the queue oldest first; the box text goes last and the box is emptied
    assert out["afterSend"] == ["first", "second"] and out["boxAfterSend"] == ""
    assert out["order"] == ["first", "second", "third", "fourth"]
    assert out["left"] == [] and out["heldAfter"] is False
    # an empty Send resumes too
    assert out["emptySend"] == ["a"]


def test_both_stop_handlers_hold_the_queue() -> None:
    wiring = _read("wiring.js")
    handlers = re.findall(r"chatQueue\.held = (true|false);\n\s+chatController", wiring)
    assert handlers == ["true", "true"], "the Stop button and Escape must both hold the queue"


def test_the_list_stays_and_the_guide_says_so() -> None:
    queue = _read("palette.js")[_read("palette.js").index("function composerQueue(") :]
    # the queue is repainted (not cleared) when a held `next()` declines to send
    assert "q.show()" in queue.split("q.next =")[1].split("\n")[0]
    # Stop never empties the list
    wiring = _read("wiring.js")
    assert "chatQueue.items" not in wiring
    topics = (
        Path(__file__).resolve().parent.parent / "src" / "tessellate" / "ai" / "help_topics_more.py"
    )
    body = topics.read_text(encoding="utf-8")
    body = body[body.index('"id": "queued-messages"') :][:1800]
    assert "Stop ends the reply and keeps the list" in body and "press Send" in body
