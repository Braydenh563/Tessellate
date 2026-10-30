"""Audit 1028 E13, E15, E26, E28 and E32: chat questions that reached the wrong answer."""

from __future__ import annotations

import re

import pytest

from tests._app_js import app_js_text
from tests.test_composer_route_688 import _ask
from tessellate.entry import manager


@pytest.fixture
def essay(session):
    manager.create_entry(session, "# History essay\n\nThe history essay is due Friday 7 November, 2000 words.", category_name="Uni")
    manager.create_entry(session, "# Krebs cycle\n\nThe Krebs cycle makes ATP in the mitochondria.", category_name="Uni")
    session.commit()


def _said(client, question):
    return _ask(client, question, use_tools=False)["text"]


def test_a_bare_undo_typed_in_chat_runs_the_apps_undo():
    """E13: sent as a question it got the Help line; the send path now runs undo or redo."""
    js = app_js_text()
    words = re.search(r"const CHAT_UNDO_WORDS = /(.+?)/i;", js).group(1)
    for typed in ("undo", "Undo that", "redo", "undo it.", "undo the last change"):
        assert re.fullmatch(words, typed, re.I), typed
    for typed in ("undo the tag on my essay note", "how do I undo"):
        assert not re.fullmatch(words, typed, re.I), typed
    assert 'return chatWriteRecord("chatHistoryTyped", /^undo/i.test(typed));' in js
    assert "Nothing to undo." in js and "performUndo : performRedo" in js


def test_a_word_question_about_one_note_is_not_the_notebook_count(client, essay):
    """E15."""
    text = _said(client, "when is the history essay due and how many words")
    assert "across 2 notes" not in text and "Friday" in text
    assert "across 2 notes" in _said(client, "how many words have I written")


def test_a_reminder_with_only_a_time_asks_what_for(client):
    """E26."""
    assert _said(client, "set a reminder for 5pm").startswith("What should I remind you about")
    assert "There is no 31 February" in _said(client, "remind me on 31 February to do something")


def test_show_my_reminders_opens_reminders(client):
    """E28."""
    assert "Opening reminders" in _said(client, "show my reminders")


def test_a_hosted_model_question_gets_the_models_help(client):
    """E32."""
    assert "OpenAI" in _said(client, "can I use ChatGPT with this")
