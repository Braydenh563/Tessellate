"""The chat pane keeps its bottom when its height changes without a scroll
event (INBOX 534: "I cant scroll down all the way to the bottom on the chat,
it cuts the scrollbar short").

A picture that loads late grows the pane and a fold the app collapses while
the answer writes shrinks it; neither fires `scroll`, so a pane that was
following the bottom stopped short of it until something else moved it. The
first cause found for the symptom was in the backend (a "streamed" OpenAI
turn arrived whole, `test_streaming_laziness.py`); the rest is hardening,
measured by `scratchpad/ui-sweeps/chatscroll534.js` (a real streamed turn).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import with_pieces

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _between(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin)]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_following_pane_re_pins_on_a_late_image_and_a_fold_toggle():
    source = with_pieces("chat-agent.js")
    code = _between(source, "const SCROLL_STICK_SLACK", "//: **The \"still writing\" pill")
    script = (
        code
        + """
let chatController = null;
globalThis.performance = { now: () => 0 };
function pane() {
  const listeners = {};
  return {
    dataset: {}, scrollHeight: 900, scrollTop: 0, clientHeight: 300,
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    fire(type) { (listeners[type] || []).forEach((fn) => fn({ key: "", touches: [] })); },
  };
}
const out = {};
const a = pane(); keepAtBottom(a);
a.scrollHeight = 1400; a.fire("load");
out.imageWhileStuck = a.scrollTop;
const b = pane(); keepAtBottom(b); b.dataset.stuck = "0";
b.scrollHeight = 1400; b.fire("load");
out.imageWhileAway = b.scrollTop;
const c = pane(); keepAtBottom(c); c.scrollTop = 0;
c.fire("toggle");
out.toggleIdle = c.scrollTop;
chatController = {}; c.fire("toggle");
out.toggleWhileWriting = c.scrollTop;
console.log(JSON.stringify(out));
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == {
        "imageWhileStuck": 1400,
        "imageWhileAway": 900,  # a reader who scrolled away is left where they are
        "toggleIdle": 0,
        "toggleWhileWriting": 900,
    }


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_growth_under_a_following_pane_never_lets_go_only_a_scroll_up_does():
    """The cause found by sampling a real streamed turn every 100ms: a scroll
    event arrives a frame after the pin that made it, and a block that grew
    the pane by more than the 40px slack in between was read as the reader
    leaving. Following stopped at the next heading or code block, and the pane
    fell behind the answer (`data-stuck` "0", the pill up) with no one having
    touched it."""
    source = with_pieces("chat-agent.js")
    code = _between(source, "const SCROLL_STICK_SLACK", "//: **What the notebook gave a message, as one card**")
    script = (
        code
        + """
let chatController = null, chatStreaming = null;
const typingDots = () => ({});
globalThis.performance = { now: () => 1e6 };
const pill = { classList: { toggle() {}, add() {}, remove() {} } };
const pane = {
  id: "chat-messages", dataset: {}, scrollHeight: 400, clientHeight: 400, L: {}, top: 0,
  get scrollTop() { return this.top; },
  set scrollTop(v) { this.top = Math.max(0, Math.min(v, this.scrollHeight - this.clientHeight)); },
  addEventListener(type, fn) { (this.L[type] = this.L[type] || []).push(fn); },
  fire(type, event = {}) { (this.L[type] || []).forEach((fn) => fn(event)); },
  querySelector() { return {}; },
};
const $ = (id) => (id === "chat-messages" ? pane : id === "chat-jump-latest" ? pill : null);
const seen = [];
const note = (label) => seen.push([label, pane.dataset.stuck]);
keepAtBottom(pane);
for (const height of [500, 700, 760, 1100]) {   // growth in blocks of 100px and more
  pane.scrollHeight = height; keepAtBottom(pane); pane.fire("scroll");
}
pane.scrollHeight = 1400; pane.fire("scroll"); note("grew 300 before the pin");
syncChatJumpLatest(); note("sync while growth is pending");
keepAtBottom(pane); pane.fire("scroll"); note("pinned again");
pane.scrollTop = 600; pane.fire("scroll"); note("reader scrolled up");
pane.scrollHeight = 1800; pane.fire("scroll"); note("then it grew");
pane.scrollTop = pane.scrollHeight - pane.clientHeight; pane.fire("scroll"); note("reader back at the bottom");
console.log(JSON.stringify(seen));
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == [
        ["grew 300 before the pin", "1"],
        ["sync while growth is pending", "1"],
        ["pinned again", "1"],
        ["reader scrolled up", "0"],
        ["then it grew", "0"],
        ["reader back at the bottom", "1"],
    ]


def test_a_picture_holds_a_box_before_it_loads_and_the_streaming_bubble_is_not_an_anchor():
    widgets = (CSS / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    figure = _between(widgets, ".answer-figure-open > img {", "}")
    assert "aspect-ratio: auto 4 / 3" in figure
    assert "overflow-anchor: none" in _between(widgets, ".bubble-answer.is-streaming {", "}")
    chat = (CSS / "02-chat-graph.css").read_text(encoding="utf-8")
    assert "aspect-ratio: auto 4 / 3" in _between(chat, ".msg-attachment-image img {", "}")


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_wheel_up_inside_a_nested_scroller_does_not_release_following():
    """A code block, table or fold that can still scroll up takes the wheel
    itself; only a wheel the pane would scroll lets go."""
    source = with_pieces("chat-agent.js")
    code = _between(source, "const SCROLL_STICK_SLACK", "//: **The \"still writing\" pill")
    script = (
        code
        + """
let chatController = null;
globalThis.performance = { now: () => 0 };
globalThis.getComputedStyle = (n) => ({ overflowY: n.overflowY || "visible" });
const node = (props, parent) => Object.assign({ nodeType: 1, scrollTop: 0, scrollHeight: 100, clientHeight: 100, parentElement: parent }, props);
function pane() {
  const L = {};
  return node({ dataset: {}, scrollHeight: 900, scrollTop: 0, clientHeight: 300, parentElement: null,
    addEventListener(t, fn) { (L[t] = L[t] || []).push(fn); },
    wheel(target, deltaY) { (L.wheel || []).forEach((fn) => fn({ target, deltaY })); } });
}
const out = {};
const run = (label, build, deltaY = -100) => {
  const p = pane(); keepAtBottom(p);
  p.wheel(build(p), deltaY);
  out[label] = p.dataset.stuck;
};
run("onPane", (p) => p);
run("codeScrolledDown", (p) => node({ overflowY: "auto", scrollTop: 50, scrollHeight: 400 }, p));
run("codeAtTop", (p) => node({ overflowY: "auto", scrollTop: 0, scrollHeight: 400 }, p));
run("childOfScrolledFold", (p) => node({}, node({ overflowY: "auto", scrollTop: 20, scrollHeight: 400 }, p)));
run("hiddenOverflowIgnored", (p) => node({ overflowY: "hidden", scrollTop: 20, scrollHeight: 400 }, p));
run("wheelDownInCode", (p) => node({ overflowY: "auto", scrollTop: 0, scrollHeight: 400 }, p), 100);
console.log(JSON.stringify(out));
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == {
        "onPane": "0",
        "codeScrolledDown": "1",
        "codeAtTop": "0",
        "childOfScrolledFold": "1",
        "hiddenOverflowIgnored": "0",
        "wheelDownInCode": "1",
    }
