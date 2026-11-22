"""L-world-class-672: Ctrl+Z in a just-added topic whose text is untouched
takes the topic away (the editor has focus and used to swallow the chord)."""

from __future__ import annotations

import re

from tests._app_js import JS_DIR


def _keydown_block() -> str:
    js = (JS_DIR / "whiteboard-map.js").read_text(encoding="utf-8")
    start = js.index('text.on("keydown", function (event) {')
    return js[start : js.index('text.on("pointerdown"', start)]


def test_untouched_fresh_topic_hands_ctrl_z_to_the_board():
    block = _keydown_block()
    assert re.search(r'event\.key\.toLowerCase\(\) === "z"', block)
    assert "_fresh" in block and "wbUndo" in block


def test_chord_only_when_text_is_untouched_and_not_redo():
    block = _keydown_block()
    z = block[block.index('toLowerCase() === "z"') :]
    assert "!event.shiftKey" in block[block.index('toLowerCase() === "z"') - 200 : block.index('toLowerCase() === "z"') + 200]
    assert "wbEditedText" in z[:600]
