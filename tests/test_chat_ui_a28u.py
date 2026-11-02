"""Chat UI audit 1028 rows E47, E49, E61, E68, E71 and E41 (agent a28u, 2026-11-02)."""

from __future__ import annotations

import re

from tests._app_js import JS_DIR
from tests._app_js import app_js_text


def test_e49_edit_reads_the_turn_from_the_bubble():
    edit = (JS_DIR / "chat-edit.js").read_text(encoding="utf-8")
    assert "bubble.dataset.turn" in edit
    assert "indexOf(bubble) / 2" not in edit
    js = app_js_text()
    # Both bubble writers stamp the index this pair will occupy.
    assert "dataset.turn = String(chatConv.turns.length)" in js
    # A deleted exchange renumbers the user bubbles after it.
    assert "dataset.turn" in js[js.index("async function deleteChatTurn") :][:3000]


def test_e47_the_chat_list_has_a_search_field():
    from tests._app_js import INDEX_HTML

    html = INDEX_HTML.read_text(encoding="utf-8")
    box = re.search(r'<div class="search-field chat-sidebar-search">.*?</div>', html, re.S).group(0)
    assert 'class="ph ph-magnifying-glass search-field-icon"' in box
    assert 'id="chat-sidebar-search" type="search" class="search-field-input"' in box
    assert 'aria-label="Search your saved chats"' in box
    # The server reads titles and message text; the list reads the box on every load.
    assert "/conversations?q=${encodeURIComponent(term)}" in app_js_text()
    assert "Search" not in re.findall(r'placeholder="(Filter[^"]*)"', box)
    from tessellate.ai import help_chat

    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "chat-list")
    assert "search box above it finds a chat" in topic["body"]


def test_e61_plan_and_agent_say_why_in_view_and_stay_reachable():
    js = app_js_text()
    # The visible line names both; Agent is aria-disabled (a Tab stop) with the model-offer popover.
    assert "Plan and Agent need a model." in js
    body = js[js.index("function renderChatModeSeg") :][:2600]
    assert 'setAttribute("aria-disabled", "true")' in body
    assert "agentButton.disabled" not in body
    assert "dataset.modelOffer" in body and "dataset.needsModel" in body


def test_e68_the_transcript_is_busy_while_an_answer_streams():
    turn = (JS_DIR / "chat-turn.js").read_text(encoding="utf-8")
    start = turn.index("chatController = new AbortController();")
    assert 'setAttribute("aria-busy", "true")' in turn[start : start + 600]
    # Cleared where the one controller is let go: end, error and Stop all reach it.
    done = turn.index("chatController = null;")
    assert '$("chat-messages").removeAttribute("aria-busy")' in turn[done - 200 : done + 300]
    assert 'removeAttribute("aria-busy")' in (JS_DIR / "chat-attach.js").read_text(encoding="utf-8")
    assert 'setAttribute("aria-busy", "true")' in (JS_DIR / "answer-kit.js").read_text(encoding="utf-8")
