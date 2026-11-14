"""L562: a chat hit in Find anything opens the chat at the turn that holds the words."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _search_js() -> str:
    return (ROOT / "frontend" / "js" / "search.js").read_text(encoding="utf-8")


def test_a_chat_hit_scrolls_to_the_first_turn_with_the_query_words():
    source = _search_js()
    opens = source[source.index("const FINDER_OPEN = {") :]
    body = opens[opens.index("chat: (hit)") : opens.index("\n};")]
    # The chat is opened first, then the turn is found by the typed words.
    assert body.index("openConversation(") < body.index("finderState.terms()")
    assert "chat-messages" in body and "flashRevealed(" in body


def test_the_chat_opener_calls_it_for_a_saved_chat_not_an_ask_turn():
    source = _search_js()
    opens = source[source.index("const FINDER_OPEN = {") :]
    opens = opens[: opens.index("\n};")]
    assert 'hit.source === "ask_turns"' in opens
