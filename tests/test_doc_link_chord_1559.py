"""INBOX 1559 (audit 1102 DX16): Ctrl+K with a selection makes a link in the
document editor, with none it opens the palette; Ctrl+Alt+1 to 6 set headings.

The suite cannot press keys, so this reads the three places that must agree:
the command table (the `?` sheet and the palette), the CodeMirror keymap and
the fallback textarea, plus the app's own Ctrl+K handler, which has to stand
down when the editor made the link.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_JS = documents_text()
WIRING_JS = (ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8")


def _table() -> str:
    return DOCUMENTS_JS[DOCUMENTS_JS.index("// DOC-COMMANDS-BEGIN"):DOCUMENTS_JS.index("// DOC-COMMANDS-END")]


def _keymap() -> str:
    keymap = DOCUMENTS_JS[DOCUMENTS_JS.index("function docCmKeymap("):]
    return keymap[: keymap.index("\n}\n")]


def test_the_link_row_carries_ctrl_k():
    assert re.search(r'id: "link"[^}]*keys: "Ctrl\+K"', _table())


def test_every_heading_has_a_ctrl_alt_chord_in_the_table_and_the_keymap():
    table, keymap = _table(), _keymap()
    for level in range(1, 7):
        assert f'id: "h{level}"' in table, f"h{level} has no row"
        assert f'"Ctrl+Alt+{level}"' in table, f"Ctrl+Alt+{level} is not listed"
    assert "[1, 2, 3, 4, 5, 6].map((n) => ({ key: `Mod-Alt-${n}`" in keymap


def test_ctrl_k_is_bound_in_the_keymap_and_declines_with_no_selection():
    keymap = _keymap()
    assert 'key: "Mod-k"' in keymap
    body = DOCUMENTS_JS[DOCUMENTS_JS.index("docCmKeymap.link = "):]
    body = body[: body.index("\n")]
    assert "previewable" in body, "a code file keeps Ctrl+K for its own chord"
    assert "selectionStart !== box.selectionEnd" in body, "no selection must fall through to the palette"


def test_the_fallback_textarea_makes_the_same_link():
    handler = DOCUMENTS_JS[DOCUMENTS_JS.index('docBoxEl().addEventListener("keydown"'):]
    handler = handler[: handler.index("$(\"doc-find-toggle\")")]
    assert 'key === "k"' in handler and "docCmKeymap.link" in handler


def test_the_palette_stands_down_when_the_editor_made_the_link():
    assert '(id === "editorMenu" || id === "palette") && e.defaultPrevented' in WIRING_JS
