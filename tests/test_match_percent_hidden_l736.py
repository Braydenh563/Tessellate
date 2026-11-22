"""L736 (owner, 2026-11-12): match numbers stay out of the found notes while the answer is written; the title keeps them."""

from tests._app_js import frontend_text


def test_percent_held_while_streaming_and_revealed_at_the_end():
    kit = frontend_text("answer-kit.js")
    assert "matchReasonBadge.hold = (root) => {" in kit and "if (!chatController && !askController) return;" in kit
    assert "matchReasonBadge.reveal = () => {" in kit
    assert "matchReasonBadge.reveal();" in frontend_text("chat-turn.js")
    assert "matchReasonBadge.reveal();" in frontend_text("ask-compose.js")
    for name in ("chat-turn.js", "ask-compose.js"):
        assert "matchReasonBadge.hold(" in frontend_text(name)


def test_the_number_stays_in_the_hover_text():
    kit = frontend_text("answer-kit.js")
    assert "% cosine similarity to your question" in kit
