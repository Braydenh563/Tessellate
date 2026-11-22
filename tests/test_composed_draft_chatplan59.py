"""L-chat-59: the composer's draft (`composed_preview`) is drawn before the model's
first token and replaced by it. The server sent the event; no page read it."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TURN = (ROOT / "frontend" / "js" / "chat-turn.js").read_text(encoding="utf-8")
KIT = (ROOT / "frontend" / "js" / "answer-kit.js").read_text(encoding="utf-8")


def test_the_stream_hands_the_preview_to_the_page():
    assert 'event.type === "composed_preview" && onPreview' in KIT
    assert KIT.count("onPreview") >= 2


def test_the_draft_is_removed_at_the_first_token_and_at_the_end():
    assert 'className = "muted answer-draft"' in TURN
    first = TURN[TURN.index("onAnswer: (delta) => {") :][:200]
    assert "t.draft?.remove()" in first
    assert '.step-pending, .answer-draft' in TURN
