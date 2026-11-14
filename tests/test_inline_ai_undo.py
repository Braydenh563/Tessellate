"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

L288/L755: the inline AI edit is one entry on the app's undo stack (rule 1.8)."""

from __future__ import annotations

import re
from pathlib import Path

EDITOR = Path(__file__).resolve().parents[1] / "frontend" / "js" / "editor.js"


def _body(name: str) -> str:
    text = EDITOR.read_text(encoding="utf-8")
    start = re.search(rf"^(?:async\s+)?function\s+{name}\(", text, re.M).start()
    nxt = re.search(r"^(?:async\s+)?function\s", text[start + 10:], re.M)
    return text[start : start + 10 + nxt.start()] if nxt else text[start:]


def test_submit_pushes_one_undo_entry_with_redo():
    body = _body("inlineAiSubmit")
    assert re.search(r"inlineAiState\.action\s*=\s*pushUndo\(\s*\"AI edit\"", body)
    assert body.count("editorSplice(") >= 3  # the write, the undo, the redo


def test_bar_undo_goes_through_the_stack_not_a_value_write():
    body = _body("inlineAiUndo")
    assert "performUndo()" in body and "settleUndoFromToast(" in body
    assert ".value =" not in body


def test_retry_drops_the_stale_entry():
    body = _body("inlineAiRetry")
    assert "undoStack.splice(" in body and "inlineAiState.action = null" in body
