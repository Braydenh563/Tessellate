"""Source text: decision 7, "Metadata rows: one muted line per card or bubble
... the time last and pinned to the card's corner" on chat bubbles (L456).

Measured 2026-11-13 at 1440: a live answer's meta row read "236 ms, Ask" and
never its time, even after a minute. The cost row moves into the answer's
foot bar the moment it lands, and the observer's callback (a microtask, after
the move) looked only for a direct `.msg-meta` child, so it never found one.
It looks where `placeChatTime` does.
"""

from __future__ import annotations

from tests._app_js import frontend_text


def test_the_live_watch_finds_the_cost_row_in_the_foot_bar():
    js = frontend_text("chat-time.js")
    watch = js[js.index("const chatTimeWatch = new MutationObserver(") : js.index("function adoptChatBubble(")]
    assert ":scope > .answer-foot-bar > .msg-meta:not(.msg-meta-solo)" in watch
