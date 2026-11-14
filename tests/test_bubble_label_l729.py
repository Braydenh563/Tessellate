"""L729 (owner, 2026-11-12): the answer bubble's label is Atlas's assistant with no model and Atlas, <model> with one;
the Why trail says the same name."""

from tests._app_js import frontend_text
from pathlib import Path


def test_chat_and_ask_labels_name_atlas():
    js = frontend_text("reply-kit.js") + frontend_text("ask-compose.js")
    assert "Atlas's assistant, from your notes" in js
    assert "`Atlas, ${model}`" in js and "`Atlas, ${meta.answered_by}`" in js
    assert '"From your notes", "Answered from your notes with no model' not in js


def test_why_trail_uses_the_same_name():
    from tessellate.ai import why

    source = Path(why.__file__).read_text(encoding="utf-8")
    assert "Atlas's assistant wrote it from your notes" in source
