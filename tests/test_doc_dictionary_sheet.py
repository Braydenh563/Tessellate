"""The writing dictionary as a settings sheet (INBOX 410).

The owner, 2026-09-24: "redesign the dictionary panel as it is ugly and needs
a proper professional modern redesign." The screenshot: a title with a boxed
"1 word" chip, a select and a boxed "+ Add a word" crammed on one row, the
grammar switch in a full-width accent-bordered pill, every word in its own
bordered box with a boxed x. The layout is measured in Chromium by
`scratchpad/ui-sweeps/dictsheet.js`; this holds the shape in the markup and
the wiring.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
#: The sheet's code is documents-dictionary.js (DOCUMENTS_PLAN L327), fetched on the first press.
DOCS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8") + (ROOT / "frontend" / "js" / "documents-dictionary.js").read_text(encoding="utf-8")
CSS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))


def _dialog() -> str:
    match = re.search(r'<dialog id="doc-dictionary-dialog".*?</dialog>', HTML, re.S)
    assert match, "the dictionary dialog is missing"
    return match.group(0)


def _body(name: str) -> str:
    start = DOCS.index(f"function {name}(")
    return DOCS[start : DOCS.index("\n  }\n", start)]


def test_the_count_is_muted_text_not_a_chip() -> None:
    count = re.search(r'<span id="doc-dictionary-count"[^>]*>', _dialog()).group(0)
    assert "chip" not in count and "muted" in count


def test_one_field_finds_and_adds() -> None:
    dialog = _dialog()
    assert re.search(r'<input id="doc-dictionary-search" type="search"', dialog)
    assert "promptDialog(" not in DOCS[DOCS.index('$("doc-dictionary-add")') :][:400], (
        "Add is the field's own, never a second prompt"
    )
    render = _body("renderDocDictionary")
    assert "doc-dictionary-search" in render and "empty-state" in render
    assert "Press Enter to add it" in render


def test_the_checks_are_settings_rows_not_a_pill() -> None:
    dialog = _dialog()
    assert re.search(r'<label class="setting-check[^"]*">\s*<input type="checkbox" id="doc-grammar-check"', dialog)
    assert re.search(r'<label class="setting-check[^"]*">\s*<input type="checkbox" id="doc-smart-punctuation"', dialog)
    assert 'class="doc-dictionary-setting"' in dialog and 'id="doc-spelling-variant"' in dialog
    assert "checkbox-label doc-grammar-row" not in dialog


def test_rows_are_quiet_and_remove_waits_for_hover_or_focus() -> None:
    row = re.search(r"\n\.doc-dictionary-row \{(.*?)\n\}", CSS, re.S).group(1)
    assert "border:" not in row
    assert re.search(r"\.doc-dictionary-remove \{[^}]*opacity: 0", CSS)
    assert re.search(r"\.doc-dictionary-row:focus-within \.doc-dictionary-remove", CSS)
    assert re.search(r"@media \(hover: none\) \{\s*\.doc-dictionary-remove \{\s*opacity: 1", CSS)


def test_the_list_goes_in_and_out_as_text() -> None:
    dialog = _dialog()
    assert 'id="doc-dictionary-import"' in dialog and 'id="doc-dictionary-export"' in dialog
    assert re.search(r'<input id="doc-dictionary-file" type="file" accept="\.txt,text/plain" hidden>', dialog)
    imported = _body("docDictionaryImport")
    assert "[...have, ...fresh]" in imported, "import adds and never removes"
    assert "writing-dictionary.txt" in _body("docDictionaryExport")
