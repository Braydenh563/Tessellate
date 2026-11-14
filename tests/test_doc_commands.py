"""The documents editor's command table (DOCUMENTS_PLAN Phase 4 item 4).

One table feeds two surfaces: the command palette's "This document" group and
the `?` sheet's editor section. The suite cannot see the DOM, so what it can
check is the thing that actually breaks: a row pointing at a control that is
not in `index.html` any more looks perfectly correct in the table and does
nothing at all when pressed, which is the "a feature that never ran once"
shape CLAUDE.md's review list puts second.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_VIEW_JS = ROOT / "frontend" / "js" / "documents-view.js"
INDEX_HTML = ROOT / "frontend" / "index.html"


@pytest.fixture(scope="module")
def table() -> str:
    source = documents_text()
    start = source.index("// DOC-COMMANDS-BEGIN")
    end = source.index("// DOC-COMMANDS-END")
    return source[start:end]


def test_the_table_exists_and_is_bracketed(table):
    assert "const DOC_COMMANDS = [" in table


def test_every_control_a_command_presses_is_in_the_markup(table):
    """`docRunControl` clicks a control by id rather than copying its handler,
    which is the only way the palette and the dock cannot drift apart. The
    price is that a removed or renamed id is a dead command, so it is checked
    here."""
    markup = INDEX_HTML.read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', markup))
    pressed = set(re.findall(r'docRunControl\("([^"]+)"', table))
    assert pressed, "no command reaches a control: the table has changed shape"
    missing = sorted(pressed - ids)
    assert not missing, f"commands press controls that do not exist: {missing}"


def test_no_two_commands_claim_the_same_chord(table):
    """Two actions on one key means one of them quietly stops working, which
    is the same rule the app's rebinding dialog enforces for its own list."""
    keys = [k for k in re.findall(r'keys: "([^"]*)"', table) if k and k != "none"]
    assert keys, "no command carries a chord"
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    assert not duplicates, f"two commands claim the same chord: {duplicates}"


def test_every_row_says_what_it_is(table):
    """A row with no label is a blank line in the palette."""
    rows = re.findall(r"\{ id: \"([^\"]+)\",([^}]*)\}", table)
    assert len(rows) >= 20, f"only {len(rows)} rows parsed; the table's shape has changed"
    for ident, body in rows:
        assert "label:" in body, f"{ident} has no label"
        assert "icon:" in body, f"{ident} has no icon"
        assert "keys:" in body, f"{ident} does not say whether it has a chord"


def test_the_chords_the_editor_listens_for_are_all_in_the_table(table):
    """The sheet is only honest if it lists what the editor actually binds.
    These are the chords `documents.js`'s own keydown handler reads; a chord
    added there and not here is a shortcut nothing tells anybody about."""
    listed = set(re.findall(r'keys: "([^"]*)"', table))
    for chord in ["Ctrl+S", "Ctrl+B", "Ctrl+I", "Ctrl+Shift+S", "Ctrl+E",
                  "Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+F", "Ctrl+/"]:
        assert chord in listed, f"{chord} is bound in the editor but not in the table"


def test_the_sheet_and_the_palette_read_the_same_table():
    """Both doors by name, so a later pass cannot quietly give one of them a
    list of its own: that is exactly what the plan's "generated from the same
    table so the two cannot disagree" is asking to be prevented."""
    source = documents_text()
    for reader in ["function docPaletteCommands()", "function renderDocShortcutSheet("]:
        assert reader in source
    palette = source[source.index("function docPaletteCommands()"):]
    assert "DOC_COMMANDS" in palette[:800]
    sheet = source[source.index("function renderDocShortcutSheet("):]
    assert "DOC_COMMANDS" in sheet[:800]


def test_every_row_has_a_chord_or_says_none(table):
    """DOCUMENTS_PLAN section 25 row 6: 0 rows without a shortcut or a
    "none" (29 of 52 in a code document had neither, docs42b). The list
    chords are Google Docs' and are bound in `docCmKeymap`."""
    keys = re.findall(r'keys: "([^"]*)"', table)
    assert "" not in keys, f"{keys.count('')} rows have neither a chord nor \"none\""
    source = documents_text()
    keymap = source[source.index("function docCmKeymap("):]
    keymap = keymap[: keymap.index("\n}\n")]
    for chord, binding in (("Ctrl+Shift+8", "Mod-Shift-8"), ("Ctrl+Shift+7", "Mod-Shift-7"), ("Ctrl+Shift+9", "Mod-Shift-9")):
        assert f'keys: "{chord}"' in table and f'key: "{binding}"' in keymap
    assert 'command.keys === "none" ? "" : (command.alt || command.keys)' in source


def test_list_chords_read_the_physical_key():
    """L882: on a layout where Shift+7 types "/" (German, Spanish, Italian, the
    Nordic ones) CodeMirror sees the character "/", drops Shift for it and runs
    Mod-/ (toggle comment) before it ever reaches Mod-Shift-7. Measured with
    hw882.js: Ctrl+Shift+7 wrapped the line in an HTML comment. The list chords
    therefore read `event.code` in a first-in-line DOM handler."""
    source = DOCUMENTS_VIEW_JS.read_text(encoding="utf-8")
    start = source.index("function docRedoChord(")
    body = source[start : source.index("\n}\n", start)]
    for code, kind in (("Digit7", "ol"), ("Digit8", "ul"), ("Digit9", "task")):
        assert f'{code}: "{kind}"' in body
    assert "event.code" in body and "docFileType().previewable" in body
    

def test_autocorrect_waits_for_the_composition_to_end():
    """L883: a pinyin or kana preedit can look like a typo followed by a space
    ("teh "). CodeMirror reports preedit changes as "input.type.compose", which
    `isUserEvent("input.type")` also matches, so autocorrect rewrote the preedit
    and broke the composition (hw883.js: the text became "the tehe " and
    "the 你好"). The pipeline therefore skips an update while the view composes."""
    source = DOCUMENTS_VIEW_JS.read_text(encoding="utf-8")
    start = source.index("function docCmUpdate(")
    body = source[start : source.index("\n}\n", start)]
    line = next(row for row in body.splitlines() if row.strip().startswith("if (") and 'isUserEvent("input.type")' in row)
    assert "update.view.composing" in line
