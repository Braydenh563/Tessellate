"""A file staged on an unsent chat message is discarded when the chat is left (the hub, 2026-11-22).

Source text: "confirm that closing the chat (or switching chats) with an unsent staged file discards it
and leaves no document." Measured (scratchpad/ui-sweeps/chatstaged1122.js): a staged .py stayed on the
composer through New chat and through opening a saved chat (1 chip after each), so that chat's first
send imported it as a document. Now 0 chips after either, and 0 document, attachment or media writes.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _body(name: str) -> str:
    js = app_js_text()
    start = js.index(f"function {name}(")
    return js[start : js.index("\n}\n", start)]


def test_every_way_out_of_a_chat_drops_its_staged_files_first():
    body = _body("releaseChatComposer")
    drop = body.find("attachedDocuments.filter((d) => !d.file)")
    guard = body.find("if (!chatController || !chatStreaming) return;")
    assert drop != -1, "leaving a chat no longer drops the files staged on its unsent message"
    assert drop < guard, "the drop sits after the early return, so a chat that is not streaming keeps them"


def test_new_chat_and_opening_a_saved_chat_both_release_the_composer():
    assert "releaseChatComposer();" in _body("newChatConversation")
    assert re.search(r"releaseChatComposer\(\);", _body("openConversation"))


def test_a_staged_file_reaches_the_server_only_on_send():
    """Staging only keeps the File in the browser, so a discard needs no server call to undo it."""
    assert not re.search(r"\b(?:apiJson|apiFetch|fetch|upload\w*)\(", _body("importChatDocuments"))
