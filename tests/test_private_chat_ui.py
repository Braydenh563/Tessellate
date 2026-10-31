"""A private chat (INBOX 1481), the page's half.

The server half, "nothing is persisted", is `test_private_chat.py`. Here: the
three ways in (the composer's settings, the chat head's menu, the palette),
the mark and the one-line empty state, the three writes the page skips, the
flag it sends, and the one confirm before a private chat with messages goes.
The new code is a lazy file (the boot budget), registered with its stylesheet.
"""

from __future__ import annotations

import re

from tests._app_js import INDEX_HTML, JS_DIR, app_js_text, lazy_modules_source, stand_ins_source

PRIVATE_JS = (JS_DIR / "chat-private.js").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_there_are_three_ways_in():
    js = app_js_text()
    html = INDEX_HTML.read_text(encoding="utf-8")
    # The composer's settings panel
    panel = html[html.index('id="chat-dock-more-panel"') :]
    assert 'id="chat-private-toggle"' in panel[: panel.index('id="persona-peek-panel"')]
    assert '$("chat-private-toggle").addEventListener("click", () => chatPrivateToggle())' in js
    # The chat head's menu
    menu = js[js.index("function mountChatActionsMenu") :]
    assert re.search(r'label: "ph:ghost Private chat",\s+group: "chat",.*?run: \(\) => chatPrivateToggle\(\)', menu[:2500], re.S)
    # The palette
    assert '{ label: "ph:ghost Private chat", reveal: "chat-private"' in js
    assert '"chat-private": { tab: "chat", open: () => chatPrivateStart()' in js


def test_the_head_carries_a_quiet_mark_with_a_title():
    html = INDEX_HTML.read_text(encoding="utf-8")
    mark = re.search(r'<span id="chat-private-mark"[^>]*>.*?</span>', html, re.S).group(0)
    assert "hidden" in mark and "ph-ghost" in mark and "Private" in mark
    assert 'title="Private chat: nothing here is saved or remembered"' in mark
    assert 'class="chat-usage chat-private-mark"' in mark  # the head's own pill, not a new shape


def test_the_empty_state_is_one_line():
    assert 'const PRIVATE_EMPTY_LINE = "Private chat. Nothing here is saved or remembered.";' in PRIVATE_JS
    assert "if (chatConv.private) return chatPrivateEmpty(box);" in app_js_text()
    assert "—" not in PRIVATE_JS and "!" not in PRIVATE_EMPTY_COPY()


def PRIVATE_EMPTY_COPY() -> str:
    return re.search(r'PRIVATE_EMPTY_LINE = "([^"]+)"', PRIVATE_JS).group(1)


def test_a_private_turn_writes_nothing_and_says_so_to_the_server():
    js = app_js_text()
    send = js[js.index("async function chatSendTurn") :]
    # the send-time row, the long turn's checkpoints and the finished turn's save
    assert "if (convRef.id === null && !convRef.private) checkpointTurn();" in send
    assert "if (checkpointInFlight || convRef.private) return checkpointRun;" in send
    assert re.search(r"if \(convRef\.private\) \{\s*//:[^\n]*\n\s*\} else if \(convRef\.id === null\) \{\s*const created = await apiJson\(\"/conversations\"", send)
    # and the flag goes on the wire
    assert "isPrivate: convRef.private," in send
    assert "if (isPrivate) body.private = true;" in js


def test_leaving_a_private_chat_with_messages_asks_once_then_discards():
    js = app_js_text()
    held = _function(js, "chatLeaveHeld")
    assert "!chatConv.private" in held and "chatConv.turns.length" in held and "chatStreaming?.conv === chatConv" in held
    # every way out of the pane goes through it
    assert "if (chatLeaveHeld(newChatConversation)) return;" in js
    assert "if (chatLeaveHeld(() => openConversation(id))) return;" in js
    assert re.search(r"async function deleteCurrentChat\(\) \{\s+if \(chatConv\.private \|\|", js)
    leave = _function(PRIVATE_JS, "chatPrivateLeave")
    assert leave.count("confirmDialog(") == 1
    assert '"Discard this private chat?' in leave and 'confirmLabel: "Discard"' in leave
    assert "chatController?.abort()" in leave and "chatConv = { id: null, turns: [] };" in leave
    assert leave.index("if (!ok) return;") < leave.index("retry();")
    # closing the tab asks too
    assert 'addEventListener("beforeunload"' in PRIVATE_JS


def test_the_switch_ends_an_empty_private_chat_in_place_and_asks_for_a_full_one():
    toggle = _function(PRIVATE_JS, "chatPrivateToggle")
    assert "return newChatConversation();" in toggle  # the guard asks
    assert "chatConv.private = false;" in toggle
    start = _function(PRIVATE_JS, "chatPrivateStart")
    assert "chatConv.private = true;" in start and "newChatConversation()" in start


def test_the_code_is_a_lazy_file_with_its_stylesheet_and_stand_ins():
    modules = lazy_modules_source()
    assert '"/css/chat-private-lazy.css", "/js/chat-private.js"' in modules
    stand_ins = stand_ins_source()
    for name in ("chatPrivateStart", "chatPrivateToggle", "chatPrivateLeave"):
        assert name in stand_ins
    # nothing at boot defines them: the boot scripts only call upward into the stand-ins
    boot_text = (JS_DIR / "chat-attach.js").read_text(encoding="utf-8") + (JS_DIR / "chat.js").read_text(encoding="utf-8")
    assert not re.search(r"function chatPrivate(Start|Toggle|Leave)\(", boot_text)
