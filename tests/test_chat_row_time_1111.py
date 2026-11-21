"""OPEN #593: the chat list row reads "3h ago" and its tooltip repeated the same words.

The row stays relative (it is one line by design); the hover now leads with the exact
date and time of the last message, in the viewer's locale, and keeps the turns and
tokens after it.
"""

from tests._app_js import app_js_text


def _row_builder() -> str:
    js = app_js_text()
    start = js.index('meta.className = "conv-meta muted";')
    return js[start : start + 1400]


def test_the_chat_row_hover_leads_with_the_exact_time_of_the_last_message() -> None:
    row = _row_builder()
    assert "meta.title = [parseServerTime(conversation.last_at)?.toLocaleString(undefined, { dateStyle: \"full\", timeStyle: \"short\", ...clockOptions() }), ...bits.slice(1)].filter(Boolean).join(\" · \");" in row


def test_the_chat_row_text_stays_relative() -> None:
    row = _row_builder()
    assert 'meta.textContent = bits.join(" · ");' in row
    assert "const bits = [relativeTime(conversation.last_at)];" in row
