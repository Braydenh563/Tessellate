"""Audit 1031 HR2, AI6 (ranked row 11): a failed turn names its cause and offers a way on."""

from __future__ import annotations
from tests._app_js import with_pieces


def test_hr2_a_failed_turn_names_its_cause_and_offers_retry_and_settings():
    """HR2 and AI6: a stream that failed shows the server's own sentence, not
    "The model wrote nothing", with Try again and Settings, Models beside it."""

    src = with_pieces("chat-attach.js")
    start = src.index("if (!stopped && !handoff && !asked) {")
    branch = src[start : src.index("chatScrollToEnd();", start)]
    assert "failure ||" in branch, "the note says why the turn failed"
    assert 'openSettingsModal("models")' in branch and "regenerateLastAnswer()" in branch
    assert "failure = said" in src
