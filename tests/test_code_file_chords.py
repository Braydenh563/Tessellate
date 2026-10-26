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


def test_a_code_file_has_go_to_line_on_ctrl_g_and_prose_keeps_find_next():
    keymap = _keymap()
    line = next(row for row in keymap.splitlines() if '"Mod-g"' in row)
    assert "docFileType().previewable ? false" in line
    assert "CM.search.gotoLine(view)" in line
    css = (DOCS_JS.parents[1] / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".doc-editor .cm-goto-line {" in css


def test_the_phone_bar_swaps_markdown_buttons_for_code_keys_in_a_code_file():
    root = DOCS_JS.parents[1]
    html = (root / "index.html").read_text(encoding="utf-8")
    bar = html.split('id="doc-phone-bar"')[1].split("</div>")[0]
    keys = re.findall(r'data-code-key="([^"]+)"', bar)
    # Tab and undo first (a phone keyboard has neither), then the brackets.
    assert keys[:4] == ["tab", "outdent", "undo", "redo"]
    assert {"{}", "()", "[]", "&quot;&quot;"} <= set(keys)
    css = (root / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert "#tab-documents.doc-is-code .doc-phone-bar > :not(.doc-code-key)" in css
    assert "#tab-documents .doc-phone-bar > .doc-code-key {\n    display: none;" in css
    code = (root / "js" / "documents-code.js").read_text(encoding="utf-8")
    press = code[code.index("function docCodeKeyPress(") :].split("\n}\n")[0]
    for call in ("docUndo()", "docRedo()", "indentDocSelection(box", "docReplaceRange(box"):
        assert call in press


def test_a_code_files_exports_are_its_source_not_an_empty_page():
    """INBOX 1400 dogfood: Download as .html of a Python file saved a page with
    its title line and nothing else (the preview of a file with no rendered
    form is empty), named `apppy.html`; the bundle and Word rows were offered
    for it too."""
    source = DOCS_JS.read_text(encoding="utf-8")
    html = source[source.index("async function exportDocumentHtml()") :].split("\n}\n")[0]
    head = html.split("withDocPreviewShown")[0]
    assert "!docFileType().previewable" in head
    assert "<pre><code>" in head
    for name in ("function exportDocumentBundle()", "async function exportDocumentDocx()"):
        body = source[source.index(name) :].split("\n}\n")[0]
        assert "docCodeExportRefused(" in body
    sync = source[source.index("function syncDocFileType(") :].split("\n}\n")[0]
    # Print is no longer refused for a code file: it prints a listing
    # (tests/test_code_editor_leftovers.py), so its row stays.
    assert '["doc-export-zip", "doc-export-docx", "doc-map-headings"]' in sync


def test_an_export_name_keeps_a_code_files_extension():
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    source = DOCS_JS.read_text(encoding="utf-8")
    start = source.index("function docExportName")
    fn = source[start : source.index("\n}\n", start) + 3]
    titles = '["app.py", "..hidden", "a..b", "Notes v1.2"]'
    script = fn + f'console.log(JSON.stringify({titles}.map((t) => docExportName(t, "html"))));'
    names = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    assert names == ["app.py.html", "hidden.html", "a.b.html", "Notes-v1.2.html"]


def test_the_word_goal_is_not_offered_in_a_code_file():
    source = DOCS_JS.read_text(encoding="utf-8")
    body = source[source.index("function renderDocStats()") :].split("\n}\n")[0]
    assert 'button.classList.toggle("hidden", docIsCodeFile())' in body
