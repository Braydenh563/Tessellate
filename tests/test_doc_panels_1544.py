"""INBOX 1544: every insert panel has more doors than the "/" menu.

The owner: "are things like the equation and emojis panel only open from typing
in the slash commands?? can there be easier ways and more ways to access them
as their own features and panels??"

The panels are Emoji, Icons and Symbols (one movable picker, three tabs),
Equation and Calculator. Each opens from the document's Insert menu, the
command palette, a chord listed in the document shortcut sheet, and the note
editor's strip where it applies. Symbols is new: a third tab in the picker,
inserted as the character itself.

This pins what the suite can see without a browser: the symbol data (run in
node), the openers and their chords, and that every door names the same panel.
The browser pass (each door, the panel's tab and its place) is in the commit.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests import _js_scope
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
PICKER = _js_scope.unwrapped((JS / "icon-picker.js").read_text(encoding="utf-8"))
EDITOR = (JS / "editor.js").read_text(encoding="utf-8")
DOCS = documents_text()
FEATURES = (JS / "app-features.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")

HARNESS = r"""
const vm = require("node:vm");
const fs = require("node:fs");
const ctx = { JSON, Array, Object, Set, Map, console, prefs: { json: (k, f) => f, set() {} } };
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const groups = vm.runInContext("iconPickerState.symbols()", ctx);
const items = groups.flatMap((g) => g.items);
const text = (c) => vm.runInContext(`iconPickerText(${JSON.stringify(c)})`, ctx);
console.log(JSON.stringify({
  groups: groups.map((g) => [g.key, g.items.length]),
  total: items.length,
  uniqueValues: new Set(items.map((i) => i.value)).size,
  uniqueNames: new Set(items.map((i) => i.name)).size,
  kinds: [...new Set(items.map((i) => i.kind))],
  singleChar: items.every((i) => [...i.value].length === 1),
  pi: items.find((i) => i.name === "pi").value,
  arrowHits: items.filter((i) => i.name.includes("arrow")).length,
  textSymbol: text({ kind: "symbol", value: "π", name: "pi" }),
  textEmoji: text({ kind: "emoji", value: "\u{1F600}", name: "grin" }),
  textIcon: text({ kind: "icon", value: "check", name: "check" }),
}));
"""


def _run() -> dict:
    done = subprocess.run(
        ["node", "-e", HARNESS, str(_js_scope.unwrapped_copy(JS / "icon-picker.js"))], capture_output=True, text=True, check=True
    )
    return json.loads(done.stdout)


@node
def test_the_symbols_are_a_real_set_of_single_characters():
    out = _run()
    assert out["total"] >= 150
    assert out["uniqueValues"] == out["total"], "two names for one character"
    assert out["uniqueNames"] == out["total"]
    assert out["kinds"] == ["symbol"]
    assert out["singleChar"]
    assert out["pi"] == "π"
    assert out["arrowHits"] >= 12
    keys = [k for k, _ in out["groups"]]
    assert {"arrows", "math", "greek", "currency", "writing", "fractions", "marks", "keys"} <= set(keys)


@node
def test_a_symbol_is_inserted_as_itself_an_emoji_as_itself_and_an_icon_as_its_token():
    out = _run()
    assert out["textSymbol"] == "π"
    assert out["textEmoji"] == "\U0001F600"
    assert out["textIcon"] == ":ph-check:"


def test_the_picker_offers_symbols_as_a_third_tab_and_keeps_two_for_everyone_else():
    assert '["symbol", "Symbols"]' in PICKER
    assert 'modes = ["emoji", "icon"]' in PICKER, "the board and the map still get two tabs"
    assert "Search emoji, icons and symbols" in PICKER or "search.placeholder =" in PICKER
    # recents remember a symbol under its own kind
    assert 'r.kind === "symbol"' in PICKER


def test_the_openers_share_one_door_that_takes_the_tab():
    assert "function editorPickGlyph(box, anchor = null, mode = \"emoji\")" in EDITOR
    body = EDITOR[EDITOR.index("function editorPickGlyph(") : EDITOR.index("// Apply one MD_ACTIONS-shaped action")]
    assert 'modes: ["emoji", "icon", "symbol"]' in body
    assert "mode," in body
    # a pick that is not an icon is the text itself
    assert 'choice.kind === "icon"' in body
    # no box (the palette over nothing): copied, not lost
    assert "clipboard" in body


def test_the_slash_menu_has_a_symbol_row_beside_emoji():
    assert 'id: "symbol"' in EDITOR
    row = EDITOR[EDITOR.index('id: "symbol"') :]
    row = row[: row.index("\n")]
    assert 'editorPickGlyph(t, null, "symbol")' in row


def test_each_panel_is_a_markdown_action_the_toolbars_and_menus_press():
    for kind in ("emoji", "icon", "symbol", "equation", "calculator"):
        assert f'{kind}: {{ custom: "{kind}" }}' in DOCS, kind
    apply = DOCS[DOCS.index("function applyMarkdown(") :]
    apply = apply[: apply.index("//: **Undo and redo go through")]
    assert '["emoji", "icon", "symbol"].includes(action.custom)' in apply
    assert 'action.custom === "calculator"' in apply
    assert 'editorPickGlyph(box, anchor, action.custom)' in apply
    assert "POPUP_TOOLS" in apply


def test_the_documents_insert_menu_lists_every_panel():
    # Insert opens the "/" menu (DX6), so every panel is a row of that catalogue.
    rows = (JS / "editor.js").read_text(encoding="utf-8")
    rows = rows[rows.index("function editorBlockRows") : rows.index("function editorBackOverTrail")]
    for row in ('id: "emoji"', 'id: "symbol"', 'id: "equation"', "id: `tool-${tool.id}`"):
        assert row in rows, f"the slash catalogue lacks {row}"
    assert 'data-md="insert"' in INDEX[INDEX.index('id="doc-toolbar-insert"') - 40 :][:200]


def test_the_note_strip_has_symbols_and_equation_beside_the_emoji_button():
    at = INDEX.index('data-md="emoji" title="Emoji or icon" aria-label')
    strip = INDEX[at : at + 1200]
    assert 'data-md="symbol"' in strip
    assert 'data-md="equation"' in strip


def _doc_rows() -> dict[str, str]:
    table = DOCS[DOCS.index("// DOC-COMMANDS-BEGIN") : DOCS.index("// DOC-COMMANDS-END")]
    rows = {}
    for match in re.finditer(r'\{ id: "(insert-[a-z]+)",([^}]*)\}', table):
        rows[match.group(1)] = match.group(2)
    return rows


def test_every_panel_is_a_document_command_with_a_chord_in_the_sheet():
    rows = _doc_rows()
    assert {"insert-emoji", "insert-icon", "insert-symbol", "insert-equation", "insert-calculator"} <= set(rows)
    chords = {}
    for ident, body in rows.items():
        keys = re.search(r'keys: "([^"]*)"', body)
        assert keys, ident
        chords[ident] = keys.group(1)
    # each of the four with a chord, none repeated anywhere in the table
    for ident in ("insert-emoji", "insert-icon", "insert-symbol", "insert-equation", "insert-calculator"):
        assert chords[ident] not in ("", "none"), ident
    table = DOCS[DOCS.index("// DOC-COMMANDS-BEGIN") : DOCS.index("// DOC-COMMANDS-END")]
    all_keys = re.findall(r'keys: "([^"]*)"', table)
    for chord in chords.values():
        assert all_keys.count(chord) == 1, f"{chord} is claimed twice"


def test_the_chords_are_bound_in_the_document_and_in_every_note_box():
    shared = DOCS[DOCS.index("docCmKeymap.insert = ") :]
    shared = shared[: shared.index("\n")]
    for binding, kind in (("Mod-;", "emoji"), ("Mod-Shift-;", "icon"), ("Mod-'", "symbol"), ("Mod-Shift-'", "calculator")):
        assert f'["{binding}", "{kind}"]' in shared, f"{binding} is not {kind}"
    doc = DOCS[DOCS.index("function docCmKeymap(") :]
    doc = doc[: doc.index("\n}\n")]
    note = DOCS[DOCS.index("function noteSurfaceKeymap(") :]
    note = note[: note.index("\n}\n")]
    assert "...docCmKeymap.insert(" in doc, "the document does not bind them"
    assert "...docCmKeymap.insert(" in note, "the note boxes do not bind them"
    # a code file declines the prose ones; the calculator is for any file
    assert "docProseChord" in doc[doc.index("...docCmKeymap.insert(") :][:300]


def test_the_palette_lists_the_three_pickers_and_hands_them_the_box_it_caught():
    for label, mode in (("Emoji", "emoji"), ("Icons", "icon"), ("Symbols", "symbol")):
        row = re.search(rf'label: "ph:[a-z-]+ {label}".*', FEATURES)
        assert row, label
        assert f'popupToolMaths.glyph("{mode}")' in row.group(0)
    glyph = FEATURES[FEATURES.index("popupToolMaths.glyph = ") :]
    glyph = glyph[: glyph.index("\n")]
    assert "popupToolMaths.box(paletteCaughtNow().target)" in glyph
    assert "editorPickGlyph(" in glyph


def test_the_guide_names_every_door():
    from tessellate.ai.help_topics_more import MORE_TOPICS

    body = next(t for t in MORE_TOPICS if t["id"] == "emoji-and-icons")["body"]
    for needle in ("Symbols", "Insert menu", "Ctrl+K", "Ctrl+;", "Ctrl+Shift+;", "Ctrl+'", "Ctrl+Shift+'"):
        assert needle in body, f"the Guide's emoji-and-icons topic does not say {needle}"
