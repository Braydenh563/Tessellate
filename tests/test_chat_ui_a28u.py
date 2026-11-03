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
    # A deleted exchange (chat-edit.js, lazy) renumbers the user bubbles after it.
    assert "node.dataset.turn -= 1" in js[js.index("async function deleteChatTurn") :][:3000]


def test_e47_the_chat_list_has_a_search_field():
    from tests._app_js import INDEX_HTML

    html = INDEX_HTML.read_text(encoding="utf-8")
    box = re.search(r'<div class="search-field chat-sidebar-search">.*?</div>', html, re.S).group(0)
    assert 'class="ph ph-magnifying-glass search-field-icon"' in box
    assert 'id="chat-sidebar-search" type="search" class="search-field-input"' in box
    assert 'aria-label="Search your saved chats"' in box
    # The server reads titles and message text; the list reads the box on every load.
    assert "/conversations?q=${encodeURIComponent(term)}" in app_js_text()
    assert "loadConversationList.n" in app_js_text()
    assert "Search" not in re.findall(r'placeholder="(Filter[^"]*)"', box)
    from tessellate.ai import help_chat

    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "chat-list")
    assert "search box above it finds a chat" in topic["body"]


def test_e61_plan_and_agent_say_why_in_view_and_stay_reachable():
    js = app_js_text()
    # The visible line names both; Agent is aria-disabled (a Tab stop) with the model-offer popover.
    assert "Plan and Agent need a model." in js
    body = js[js.index("function renderChatModeSeg") :][:2600]
    #: `gated` itself since DX23 (audit 1102): setAttribute writes "true" or "false" either way.
    assert 'agentButton.setAttribute("aria-disabled", gated)' in body
    assert "agentButton.disabled" not in body
    from tests._app_js import INDEX_HTML

    html = INDEX_HTML.read_text(encoding="utf-8")
    button = html[html.index('<button data-chat-mode="agent"') :][:500]
    assert "data-needs-model=" in button and "data-model-offer=" in button


def test_e68_the_transcript_is_busy_while_an_answer_streams():
    turn = (JS_DIR / "chat-turn.js").read_text(encoding="utf-8")
    start = turn.index("chatController = new AbortController();")
    assert 'setAttribute("aria-busy", "true")' in turn[start : start + 600]
    # Cleared where the one controller is let go: end, error and Stop all reach it.
    done = turn.index("chatController = null;")
    assert '$("chat-messages").removeAttribute("aria-busy")' in turn[done - 200 : done + 300]
    assert 'removeAttribute("aria-busy")' in (JS_DIR / "chat-attach.js").read_text(encoding="utf-8")
    assert 'setAttribute("aria-busy", "true")' in (JS_DIR / "answer-kit.js").read_text(encoding="utf-8")


def test_e71_read_aloud_stops_and_has_a_remembered_speed():
    from tests._app_js import INDEX_HTML

    js = app_js_text()
    speak = js[js.index("function speakText") :][:2600]
    assert 'prefs.number("read-aloud-rate", 1, { min: 0.75, max: 1.5 })' in speak
    assert "return utterance;" in speak
    assert "Stop reading" in js and 'querySelectorAll("[data-speak]")' in js
    # Both the icon button and the item in the ⋯ menu are marked.
    assert 'dataset.speak = "1"' in js and "speak: true" in js
    html = INDEX_HTML.read_text(encoding="utf-8")
    box = html[html.index('id="read-aloud-box"') :][:1800]
    for rate in ("0.75", "1", "1.25", "1.5"):
        assert f'<option value="{rate}">' in box
    assert 'data-help-for="read-aloud-help"' in box


def test_e41_the_models_pane_speaks_plainly():
    tools = (JS_DIR / "ai-tools.js").read_text(encoding="utf-8")
    picker = tools[tools.index("function renderChatModelPicker") :][:4200]
    # One installed model, already the one in use: Use this model would do nothing.
    assert 'classList.toggle("hidden", names.length === 1 && names[0] === status.chat_model)' in picker
    # The note says what is installed and when it loads, not where it sits in memory.
    assert "which loads when you ask" in picker
    assert '", not in memory"' not in picker and '", in memory now"' not in picker
    panel = (JS_DIR / "activity-panel.js").read_text(encoding="utf-8")
    assert "loads when you ask" in panel and "not in memory" not in panel
    # The spec list: no "declared", no "in use".
    chat = (JS_DIR / "chat.js").read_text(encoding="utf-8")
    spec = chat[chat.index('["Size", spec.parameters]') :][:1500]
    assert "Thinking mode declared" not in spec and '"Thinking switch"' in spec
    assert "in use`" not in spec and '"Reads at once"' in spec
