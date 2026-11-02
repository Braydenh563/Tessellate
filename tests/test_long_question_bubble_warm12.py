"""warm12-1101 leftover: a 20,000-character question took about 450 ms longer to first token than
a short one, all of it the browser laying out the whole question in the user bubble. A long
question shows its first part with a "Show more"; everything that reads the question back reads
the words as sent (`dataset.sent`), never the clipped body."""

import re

from tests._app_js import app_js_text

TEXT = app_js_text()


def _body(name):
    start = TEXT.index(f"function {name}(")
    return TEXT[start : TEXT.index("\n}\n", start)]


def test_a_long_question_is_drawn_clipped_with_show_more():
    body = _body("addBubble")
    assert "BUBBLE_CLIP" in body
    assert "entry-more" in body and "aria-expanded" in body
    assert re.search(r"body\.textContent = .*clip", body)


def test_the_question_is_read_back_as_sent():
    assert "dataset.sent" in _body("questionForBubble")
    assert "dataset.sent" in _body("chatTranscriptText")


def test_a_question_past_ten_lines_folds_with_show_more():
    """The owner, 2026-11-02: "make long chat messages from the user auto collapse with the see more/see
    less at about like 10 lines". The notes' clamp at ten lines, read once a frame after the bubble is
    drawn; a question that fits gets no button."""
    from pathlib import Path

    body = _body("addBubble")
    assert 'body.classList.add("entry-clamped")' in body
    assert "requestAnimationFrame" in body and "body.scrollHeight <= body.clientHeight + 1" in body
    assert 'body.classList.toggle("entry-clamped", !open)' in body
    css = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "03-dashboard-widgets.css").read_text(encoding="utf-8")
    assert re.search(r"\.msg\.user \.msg-body \{\s*--note-preview-lines: 10;", css)
