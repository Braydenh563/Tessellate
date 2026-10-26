"""The Documents editor's own right-click menu (docs6-1026): Cut, Copy, Paste,
the Paste special modes, Turn into and Select all. Text-level checks, because
the suite cannot see the DOM; the Playwright run is
`scratchpad/ui-sweeps/docpaste.js`."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROSE = (ROOT / "frontend/js/documents-prose.js").read_text(encoding="utf-8")
DOCUMENTS = (ROOT / "frontend/js/documents.js").read_text(encoding="utf-8")


def _fn(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


def test_menu_rows_in_order():
    body = _fn(PROSE, "docEditorMenuItems")
    labels = re.findall(r'label: "([^"]+)"', body)
    assert labels[:3] == ["Cut", "Copy", "Paste"], labels
    assert "Turn into" in labels and labels[-1] == "Select all", labels
    # The Paste special rows are the existing table, not a second list.
    assert "DOC_PASTE_SPECIAL" in body and "docPasteSpecial(" in body
    assert "docTurnIntoMenu(" in body


def test_refused_clipboard_names_ctrl_v():
    body = _fn(PROSE, "docEditorPaste")
    assert "Ctrl+V" in body and '"info"' in body


def test_paste_is_one_undo_step():
    assert "docUndoBreak()" in _fn(PROSE, "docEditorPaste")


def test_shift_bypass_and_scope():
    body = _fn(DOCUMENTS, "docEditorMenuAtPoint")
    assert "shiftKey" in body
    assert "doc-content-code" in body, "code files keep the browser's menu"
    start = DOCUMENTS.index('document.addEventListener("contextmenu", (event) => {\n  const point')
    listener = DOCUMENTS[start : DOCUMENTS.index("\n});\n", start)]
    # Tables and flags keep their own menus, ahead of the editor's.
    order = [listener.index(n) for n in ("docTableMenuAtPoint", "docOpenSuggestAtPoint", "docEditorMenuAtPoint(event")]
    assert order == sorted(order)


def test_escape_returns_focus_to_the_editor():
    menus = (ROOT / "frontend/js/menus.js").read_text(encoding="utf-8")
    assert "view.contentDOM);" in _fn(DOCUMENTS, "docEditorMenuAtPoint")
    assert menus.count("_returnFocusTo") >= 2
