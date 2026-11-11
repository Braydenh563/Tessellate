"""One composer queue for Chat, the popup agent and the Guide (CHAT_PLAN B3).

The owner, 2026-11-05: "I also cant type in the text box while the popup agent
is respondning (check the guide as well) and I cant draft, queue or
edit/delete queued messages like in chat for the popup agent." Chat had the
queue (INBOX 1321) in four names of its own; it is now `composerQueue`, one
component every surface makes its queue from, so the agent and the Guide keep
their box open while a reply runs, Enter queues, the list shows with Edit and
Remove, the next one goes as each reply ends, Stop holds it, and a queued send
never clears what is being typed. Its logic runs in node; the wiring is read
from the source.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _fn(text: str, head: str) -> str:
    start = text.index(head)
    return text[start : text.index("\n}\n", start) + 3]


HARNESS = r"""
const src = process.argv[1];
const painted = [];
const ensureModule = () => Promise.resolve(true);
eval(src);
composerQueue.paint = (q) => painted.push(q.items.slice());
let busy = true;
const sent = [];
const q = composerQueue("agent", { input: () => null, busy: () => busy, send: (t) => sent.push(t), before: () => null });
const out = {};
out.same = composerQueue("agent") === q;
out.takenBusy = [q.take("one"), q.take("two"), q.take("")];
out.items = q.items.slice();
q.next();
out.sentWhileBusy = sent.slice();
busy = false;
q.next();
out.sentAfter = sent.slice();
out.left = q.items.slice();
out.takenIdle = q.take("three");
q.held = true;
q.next();
out.sentHeld = sent.slice();
setTimeout(() => { out.painted = painted.length > 0; console.log(JSON.stringify(out)); }, 20);
"""


@node
def test_the_queue_waits_while_busy_sends_in_order_and_stop_holds_it() -> None:
    src = _fn(_read("palette.js"), "function composerQueue(")
    proc = subprocess.run(["node", "-e", HARNESS, src], capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["same"] is True
    # busy: a send waits (an empty one adds nothing), oldest first
    assert out["takenBusy"] == [True, True, True] and out["items"] == ["one", "two"]
    assert out["sentWhileBusy"] == []
    # the end of a reply sends the next one, one at a time
    assert out["sentAfter"] == ["one"] and out["left"] == ["two"]
    # idle: the surface sends it itself
    assert out["takenIdle"] is False
    # Stop holds the queue
    assert out["sentHeld"] == ["one"]
    assert out["painted"] is True


def test_every_surface_makes_its_queue_from_the_one_component() -> None:
    chat = _read("chat.js")
    palette = _read("palette.js")
    guide = _read("help-chat.js")
    # Chat's spec stays in chat.js; the component is in palette.js, off the capped boot bytes
    assert "const chatQueue = {" in chat and 'composerQueue("chat", chatQueue)' in palette
    assert [p.name for p in JS.glob("*.js") if "function composerQueue(" in p.read_text(encoding="utf-8")] == ["palette.js"]
    assert 'composerQueue("agent", {' in palette
    assert 'composerQueue("guide", {' in guide
    # replaced, not copied: Chat's own names are gone everywhere
    for name in ("chatQueueState", "chatQueuePaint", "chatQueueShow"):
        for path in JS.glob("*.js"):
            assert name not in path.read_text(encoding="utf-8"), (name, path.name)
    painters = [p.name for p in JS.glob("*.js") if "Remove from the queue" in p.read_text(encoding="utf-8")]
    assert painters == ["reply-kit.js"]


def test_the_agent_keeps_its_box_open_and_queues() -> None:
    palette = _read("palette.js")
    busy = _fn(palette, "function cmdPaletteBusy(")
    assert "cmdPaletteInput.disabled" not in busy and "disabled = busy" not in busy
    send = _fn(palette, "function cmdPaletteSend(")
    assert 'composerQueue("agent")' in send and ".take(text)" in send and ".held = false" in send
    ask = palette[palette.index("async function cmdPaletteAsk(") : palette.index("function cmdPaletteGrow(")]
    assert 'composerQueue("agent").next()' in ask.split("} finally {")[-1]
    assert re.search(r'command-palette-stop"\)\?\.addEventListener\("click", \(\) => \{[^}]*held = true', palette)


def test_the_guide_keeps_its_box_open_and_queues() -> None:
    guide = _read("help-chat.js")
    submit = guide[guide.index('$("help-chat-form")?.addEventListener("submit"') :][:600]
    assert 'composerQueue("guide")' in submit and ".take(text)" in submit
    turn = _fn(guide, "async function submitHelpChatQuestion(")
    assert 'composerQueue("guide").next()' in turn.split("} finally {")[-1]
    # a queued send leaves the box to what is being typed
    assert "if (input && !keepBox) input.value = \"\"" in turn
    stop = _fn(guide, "function helpChatStop(")
    assert 'composerQueue("guide").held = true' in stop


def test_a_queued_chat_send_keeps_the_box() -> None:
    turn = _read("chat-turn.js")
    assert "if (!opts.keepBox) {" in turn
    attach = _read("chat-attach.js")
    send = attach[attach.index("async function sendChatMessage(") :][:1200]
    assert "chatQueue.take(" in send and "chatQueue.next()" in send and "chatQueue.held = false" in send
    assert _read("wiring.js").count("chatQueue.held = true") == 0  # Chat's Stop clears the hold (next-queue-1102)
