"""A code file never receives markdown syntax from a chord (INBOX 1400
dogfood: Ctrl+B wrapped a Python line in `**`, Ctrl+U in `<u>`, Ctrl+Shift+8
prefixed `- `).

Every chord in `docCmKeymap` that writes markdown goes through
`docProseChord`, which declines for a file with no rendered form so the
engine's own binding for the key answers."""

from __future__ import annotations

import re
from pathlib import Path

DOCS_JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents.js"
MARKDOWN_CALL = re.compile(r"\b(applyMarkdown|wrapDocSelection)\(")


def _keymap() -> str:
    source = DOCS_JS.read_text(encoding="utf-8")
    start = source.index("function docCmKeymap(CM)")
    return source[start : source.index("\n}\n", start)]


def test_every_markdown_chord_declines_in_a_code_file():
    bare = [
        line.strip()
        for line in _keymap().splitlines()
        if line.strip().startswith("{ key:") and MARKDOWN_CALL.search(line) and "docProseChord" not in line
    ]
    assert bare == []


def test_the_guard_reads_the_file_type():
    source = DOCS_JS.read_text(encoding="utf-8")
    body = source[source.index("function docProseChord(") :].split("\n}\n")[0]
    assert "docFileType().previewable" in body
    assert "return false" in body


def test_slash_and_link_menus_stay_shut_in_a_code_file():
    editor = (DOCS_JS.parent / "editor.js").read_text(encoding="utf-8")
    body = editor[editor.index("function editorHandleInput(") :].split("\n}\n")[0]
    assert "docFileType().previewable" in body
    assert body.index("docFileType().previewable") < body.index('["/", "[["]')
