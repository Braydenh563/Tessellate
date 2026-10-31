"""Notes audit 1031, the shared-helper rows that live in the client.

N34 the `[[` picker inserts the title without its heading marker; N38 one
preview pass for tables, fences and formulas; N39 a picker row reads as a
phrase; N14 the phone note page does not say its title twice; N30 a link
chip's menu always has a name.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
NODE = shutil.which("node")


def _function(path: str, name: str) -> str:
    text = (JS / path).read_text()
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


@pytest.mark.skipif(NODE is None, reason="node is not available")
@pytest.mark.parametrize(
    "text,expected",
    [
        ("Table note\n| a | b |\n|---|---|\n| 1 | 2 |", "Table note\na · b\n\n1 · 2"),
        ("```js\nconst x = 1;\n```", "const x = 1;"),
        ("$$\\int_0^1 x^2 dx$$ and more", "formula and more"),
        ("one | two is not a table", "one | two is not a table"),
    ],
)
def test_one_preview_pass_for_tables_fences_and_formulas(text, expected):
    script = _function("shell-reminders.js", "previewBlocks") + "\nconsole.log(JSON.stringify(previewBlocks(process.argv[1])));"
    out = subprocess.run([NODE, "-e", script, text], capture_output=True, text=True, timeout=30)
    assert json.loads(out.stdout) == expected


def test_both_preview_helpers_use_that_pass():
    assert "previewBlocks(stripFrontmatter(" in (JS / "shell-reminders.js").read_text()
    assert "return previewBlocks(text)" in (JS / "navigation.js").read_text()


def test_the_picker_inserts_the_title_without_its_hash():
    body = (JS / "editor.js").read_text()
    assert '.replace(/^\\s*#{1,6}\\s+/, "")' in body[body.index("// Link by the note's opening words") :][:900]


def test_a_picker_row_is_named_as_a_phrase():
    row = _function("rich-picker.js", "richPickerRow")
    assert "aria-label" in row and "${title.textContent}, ${about}" in row


def test_the_phone_note_page_drops_the_title_its_head_already_says():
    shell = (JS / "phone-shell.js").read_text()
    assert "function dropRepeatedTitle(" in shell
    assert shell.count("dropRepeatedTitle(") >= 3  # the definition, the open and the refresh


def test_a_link_menu_is_never_nameless():
    assert re.search(r"Actions for the link to \$\{label \|\| ", (JS / "note-cards.js").read_text())


def test_the_capture_card_and_quick_note_are_editor_surfaces():
    """N9, N50: the placeholder's promise (`[[`, `/`) is kept in both boxes."""
    editor = (JS / "editor.js").read_text()
    table = editor[editor.index("const EDITOR_SURFACES = {") :][:3000]
    for box in ("capture-card-body", "quick-note-text"):
        assert f'"{box}": "note"' in table
    card = (JS / "capture-card.js").read_text()
    assert 'id: "capture-card-body"' in card and '"data-autocorrect": ""' in card
    assert 'id="quick-note-text"' in (ROOT / "frontend" / "index.html").read_text()


def test_the_menu_moves_into_the_dialog_that_holds_the_box():
    """A modal dialog is in the top layer: a menu left in body is under it."""
    helper = _function("editor.js", "editorHomeMenu")
    assert 'closest?.("dialog[open]")' in helper and "appendChild($(\"editor-menu\"))" in helper
    close = _function("editor.js", "editorCloseMenu")
    assert "editorHomeMenu(null)" in close


def test_one_focus_contract_after_an_act():
    """N11: a hidden or removed control hands the keyboard to a named target."""
    notes = (JS / "notes-list.js").read_text()
    helper = _function("notes-list.js", "restoreFocusTo")
    assert "checkVisibility" in helper, "a node just hidden still looks focused for one frame"
    assert notes.count("restoreNoteControl(held)") >= 2, "the patch read and the full read both restore"
    assert "restoreFocusTo(() =>" in (JS / "skills.js").read_text(), "leaving Select goes to a control"
    assert (JS / "note-panels.js").read_text().count("focusPanel(row);") == 4
    assert "focusNoteRow(entry.id); // the Save button" in (JS / "note-edit-panels.js").read_text()


@pytest.mark.skipif(NODE is None, reason="node is not available")
def test_a_held_edit_keeps_the_first_base_hash_and_the_newest_words():
    """N47: one held edit per note; a change made elsewhere meanwhile is still refused."""
    script = "\n".join(
        [
            "const store = {};",
            "const prefs = { json: (k, d) => (k in store ? JSON.parse(store[k]) : d), set: (k, v) => ((store[k] = v), true), remove: (k) => delete store[k] };",
            "const renderNoteOutbox = () => {}, renderPendingNoteRows = () => {}, scheduleNoteOutboxFlush = () => {};",
            "const NOTE_OUTBOX_KEY = 'noteOutbox';",
            "let n = 0; const newNoteClientKey = () => 'k' + ++n;",
            _function("quick-note.js", "noteOutbox"),
            _function("quick-note.js", "writeNoteOutbox"),
            _function("quick-note.js", "noteEditOutboxAdd"),
            "noteEditOutboxAdd(7, { content: 'one', base_hash: 'AAA' });",
            "noteEditOutboxAdd(7, { content: 'two', base_hash: 'BBB' });",
            "noteEditOutboxAdd(8, { content: 'other', base_hash: 'CCC' });",
            "console.log(JSON.stringify(noteOutbox().map((i) => [i.edit_id, i.content, i.base_hash])));",
        ]
    )
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert json.loads(out.stdout) == [[7, "two", "AAA"], [8, "other", "CCC"]], out.stderr


def test_the_flush_sends_edits_as_puts_and_the_form_holds_on_a_dead_server():
    quick = (JS / "quick-note.js").read_text()
    assert '`/entries/${editId}`, { method: "PUT"' in quick
    assert "!item.edit_id" in quick, "a held edit must not draw as a new note"
    assert "holdNoteEdit(entry.id" in (JS / "note-edit-panels.js").read_text()
    assert '"noteEditOutboxAdd"' in (JS / "app.js").read_text(), "the stand-in for the lazy module"


def test_a_missing_note_puts_the_address_back_and_clears_the_live_line():
    """N48."""
    body = (JS / "capture-ask.js").read_text()
    branch = body[body.index('if (!card) {') :][:500]
    assert 'recordTabVisit("notes", "browse", "", { refine: true })' in branch
    assert 'announce("")' in branch and 'toast("No such note.")' in branch


def test_the_bin_has_an_address_and_the_palette_opens_the_bin_itself():
    """N49: `#/library/bin`, the Bin kind chosen, and an Unlock command."""
    assert 'bin: "library-bin"' in (JS / "router.js").read_text()
    reveal = (JS / "reveal-targets.js").read_text()
    block = reveal[reveal.index('"library-bin": {') :][:700]
    assert 'libraryKind = "archived"' in block and 'recordTabVisit("library", "library-bin")' in block
    assert 'revealFeature("library-bin")' in (JS / "navigation.js").read_text() or 'await revealFeature("library-bin")' in (JS / "navigation.js").read_text()
    assert "Unlock private notes" in (JS / "settings-panes.js").read_text()


def test_a_template_date_is_written_in_words():
    """N24: "Oct 31, 2026", not the numeric locale date, in a template and the "/" menu."""
    ask = (JS / "capture-ask.js").read_text()
    assert "stampDate(now)" in ask and 'month: "short", day: "numeric", year: "numeric"' in ask
    assert "stampDate(now)" in (JS / "editor.js").read_text()
    assert "now.toLocaleDateString()" not in ask


@pytest.mark.skipif(NODE is None, reason="node is not available")
@pytest.mark.parametrize(
    "box,engine,unknown",
    [
        ("is:archived", ["is:archived"], None),
        ("is:done has:image", ["is:done", "has:image"], None),
        ("is:pinned is:draft", [], None),
        ("is:starred", [], None),
        ("is:wibble", [], "wibble"),
        ("is:attachment", [], "attachment"),
    ],
)
def test_unknown_is_flags_are_named_and_engine_ones_go_to_the_engine(box, engine, unknown):
    """N18: `is:archived` is the engine's (the finder's grammar), `is:wibble`
    is nobody's and an empty list says so."""
    text = (JS / "notes-list.js").read_text()
    regex = re.search(r"^const ENGINE_QUERY_RE = (.+);$", text, re.M).group(1)
    flags = re.search(r"^const NOTE_FLAGS = (.+);$", text, re.M).group(1)
    script = f"""
const ENGINE_QUERY_RE = {regex}; const NOTE_FLAGS = {flags};
const box = process.argv[1], found = [];
box.replace(ENGINE_QUERY_RE, (_, lead, term) => found.push(term));
const rest = box.replace(ENGINE_QUERY_RE, " ");
const bad = rest.split(/\\s+/).filter((t) => t.startsWith("is:")).map((t) => t.slice(3)).find((f) => !NOTE_FLAGS.includes(f));
console.log(JSON.stringify([found, bad || null]));
"""
    out = subprocess.run([NODE, "-e", script, box], capture_output=True, text=True, timeout=30)
    assert json.loads(out.stdout) == [engine, unknown]


def test_the_empty_list_names_an_unknown_filter():
    text = (JS / "notes-list.js").read_text()
    assert "noMatchHint(noMatch);" in text
    #: The hint's own text moved to notes-lazy.js (a stand-in loads it; gzip budget), the call did not.
    assert "No filter named is:${bad}." in (JS / "notes-lazy.js").read_text()
