"""INBOX 1590 (c): the Jump to latest pill sits in a strip of its own under the
thread, never over a source card, a Next chip or a message. Measured by a
Playwright sweep over every scroll position at 1280 and 390 wide (CHANGELOG)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import with_pieces



_CSS = Path(__file__).resolve().parent.parent / "frontend" / "css" / "02-chat-graph.css"


def test_the_pill_is_anchored_in_a_strip_under_the_thread():
    css = _CSS.read_text(encoding="utf-8")
    strip = css[css.index(".chat-transcript.has-jump-gap {") :]
    strip = strip[: strip.index("}")]
    assert "padding-bottom: calc(var(--space-9) + var(--space-5))" in strip
    pill = css[css.index(".chat-jump-latest {") :]
    pill = pill[: pill.index("}")]
    assert "bottom: var(--space-1)" in pill and "position: absolute" in pill


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_strip_follows_the_overflow_it_would_have_and_never_flips_itself():
    source = with_pieces("chat-agent.js")
    begin = source.index("const SCROLL_STICK_SLACK")
    code = source[begin : source.index("//: **What the notebook gave a message, as one card**", begin)]
    script = (
        code
        + """
let chatController = null, chatStreaming = null;
const typingDots = () => ({});
globalThis.performance = { now: () => 1e6 };
const GAP = 45, FULL = 600;
const on = new Set(["chat-transcript"]);
const transcript = { classList: { contains: (c) => on.has(c), add: (c) => on.add(c), remove: (c) => on.delete(c), toggle() {} } };
globalThis.getComputedStyle = () => ({ paddingBottom: on.has("has-jump-gap") ? GAP + "px" : "0px" });
const pill = { classList: { toggle() {}, add() {}, remove() {} } };
const pane = {
  id: "chat-messages", dataset: { stuck: "1" }, scrollHeight: 0, top: 0, parentElement: transcript, L: {},
  get clientHeight() { return on.has("has-jump-gap") ? FULL - GAP : FULL; },
  get scrollTop() { return this.top; },
  set scrollTop(v) { this.top = v; },
  addEventListener() {},
  querySelector() { return {}; },
};
const $ = (id) => (id === "chat-messages" ? pane : id === "chat-jump-latest" ? pill : null);
const seen = [];
for (const height of [400, 580, 620, 1000, 620, 580, 400]) {
  pane.scrollHeight = height;
  syncChatJumpLatest(); const first = on.has("has-jump-gap");
  syncChatJumpLatest(); const second = on.has("has-jump-gap");
  seen.push([height, first, second]);
}
console.log(JSON.stringify(seen));
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    # 580 fits the full height (580 < 600 + slack) but not by the strip's 45px: 580 - 600 + 45 = 25 < 40, so no strip;
    # 620 overflows by 20 and by 65 with the strip: on, and stays on at the shorter pane (620 - 555 = 65).
    assert json.loads(out) == [
        [400, False, False], [580, False, False], [620, True, True], [1000, True, True], [620, True, True], [580, False, False], [400, False, False],
    ]
