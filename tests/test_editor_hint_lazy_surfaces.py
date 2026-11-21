"""The "/ opens something" placeholder reaches the lazily built editing boxes.

`editorHintAllPlaceholders` ran once at DOM ready, before the chat and
documents surfaces exist (`surfaceBuild`, settings-body.js), so `#chat-input`
and `#doc-content` stayed silent until focused (slashicons.js: doc-content and
chat-input SILENT). A surface that arrives has to be hinted as it arrives.
"""
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_surface_build_hints_the_boxes_it_brings():
    body = (JS / "settings-body.js").read_text()
    build = body[body.index("function surfaceBuild"):body.index("function surfaceFind")]
    assert "editorHintAllPlaceholders" in build


def test_the_hint_function_is_the_editors_own():
    assert "function editorHintAllPlaceholders" in (JS / "editor.js").read_text()
