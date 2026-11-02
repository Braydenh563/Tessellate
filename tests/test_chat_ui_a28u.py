"""Chat UI audit 1028 rows E47, E49, E61, E68, E71 and E41 (agent a28u, 2026-11-02)."""

from __future__ import annotations

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

