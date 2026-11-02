"""K13: Settings, Models with no model says the composer answers in its place."""

from __future__ import annotations

from tessellate.ai.help_chat import HELP_TOPICS
from tests._app_js import app_js_text


def test_the_models_line_names_the_composer_while_no_model_answers():
    text = app_js_text()
    start = text.index("function renderSettings()")
    body = text[start : text.index("renderBackendPicker(status);", start)]
    assert "if (aiIsOff())" in body
    assert "Until a model is connected, Atlas answers with its built-in composer: from your notes, no AI." in body


def test_the_models_help_topic_says_so():
    topic = next(t for t in HELP_TOPICS if t["id"] == "models")
    assert "built-in composer" in topic["body"]
