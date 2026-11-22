"""Indent, dedent and line breaks in every text surface (INBOX 392).

Source-level checks, because the suite cannot drive a browser; the behaviour
was measured with scratchpad sweeps (a board text box: "start", Enter,
"- item" saved as "start- item" before; Tab left the box).
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import app_js_text, frontend_text

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
WB = frontend_text("whiteboard.js")
APP = app_js_text()


def test_board_text_is_edited_as_plain_text_and_read_back_with_its_lines():
    begin = WB[WB.index("function wbBeginTextEdit(") : WB.index("function wbEndTextEdit(")]
    assert '"plaintext-only"' in begin
    # No blur handler may read `textContent`: it drops the <div> line breaks
    # contenteditable inserts where plaintext-only is refused.
    for match in re.finditer(r'\.on\("blur", function \(\) \{(.*?)\n    \}\);', WB, re.S):
        assert "this.textContent" not in match.group(1)
    assert "wbEditedText(this)" in WB


def test_tab_indents_a_board_text_box_being_edited():
    assert "wbIndentEditableLines(this, event.shiftKey)" in WB


def test_a_note_box_indents_before_its_editor_has_loaded():
    bridge = APP[APP.index("**Tab indents from the first keystroke**") :]
    bridge = bridge[: bridge.index("\n});\n")]
    assert "NOTE_SURFACE_IDS.has(box.id)" in bridge
    # Shift+Tab with nothing to take off must stay the browser's, or a
    # flush-left caret is a keyboard trap.
    assert "if (!lines.some(" in bridge
