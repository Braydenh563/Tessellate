"""Audit 1031 class 32 (CE1, CE2, CE5, CE6, CE8): the code editor.

CE1: a dot after `console`, `Math`, an object the file declares or a call
offers its members. CE2: the run panel is a sheet over the editor on a phone.
CE5: Shift+Tab with nothing to outdent stays in a code file. CE6: the same
line again is a count. CE8: a code file's card says lines and type."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_a_dot_offers_the_members_of_the_receiver():
    js = _text("frontend", "js", "documents-code.js")
    assert 'console: "log warn error' in js and "Math:" in js and "JSON:" in js
    source = js.split("function docJsMemberSource()", 1)[1].split("\n}\n", 1)[0]
    # A call or an index before the dot has no name to look up, so it takes the
    # shared array, string and promise members (and never builds a RegExp from
    # a bracket).
    assert "[)\\]]" in source
    assert "/^[\\w$]+$/.test(receiver)" in source
    assert "DOC_JS_COMMON_MEMBERS" in source
    # JavaScript and TypeScript are native types, so the source is registered
    # through their language data, not only the generic list.
    native = js.split("docNativeSnippets", 1)[1]
    assert "docJsMemberSource()" in native


def test_the_name_scan_is_cached_per_document_version():
    js = _text("frontend", "js", "documents-code.js")
    scan = js.split("function docNamesIn(doc)", 1)[1].split("\n}\n", 1)[0]
    assert "docNameScans.get(doc)" in scan and "docNameScans.set(doc" in scan
    assert "new WeakMap()" in js


def test_the_run_panel_is_a_sheet_on_a_phone():
    css = _text("frontend", "css", "library-lazy.css")
    block = css.split("The output is a sheet over the editor on a phone", 1)[1].split("/* The panel's head", 1)[0]
    assert "max-width: 599.98px" in block
    assert "position: absolute" in block and "min(24dvh, 220px)" in block
    assert ".cm-scroller" in block and "padding-bottom" in block


def test_shift_tab_stays_in_a_code_file_with_nothing_to_outdent():
    js = _text("frontend", "js", "documents.js")
    body = js.split("A code file keeps Shift+Tab with nothing to outdent", 1)[1].split("},", 1)[0]
    assert "return !docFileType().previewable;" in body


def test_the_same_line_again_is_one_row_with_a_count():
    js = _text("frontend", "js", "documents-code.js")
    fold = js.split("The same line again is a count, not another row", 1)[1].split("const row = document.createElement", 1)[0]
    assert "cm-run-times" in fold and "dataset.times" in fold
    # Input and result rows are never folded: a typed line is its own event.
    assert 'level !== "input" && level !== "result"' in fold


def test_a_code_card_says_lines_and_type():
    docs = _text("frontend", "js", "documents.js")
    # The rule and the type table live in library.js: the Library's list draws
    # before the editors load.
    size = _text("frontend", "js", "library.js").split("function docSizeText(doc, withKind = false)", 1)[1].split("\n}\n", 1)[0]
    assert 'nounCount(doc.lines, "line")' in size and "!kind.previewable" in size and "kind.label" in size
    # The library card and the sidebar row say it by the one rule, and the
    # library waits for the type table (it can open before Documents does).
    card = _text("frontend", "js", "library.js").split("A code file is its lines and its type", 1)[1].split("const when =", 1)[0]
    assert "docSizeText(doc, true)" in card
    assert "await loadDocTypeTable()" in _text("frontend", "js", "library.js")
    assert "docSizeText(doc)" in docs.split("doc-item-type", 1)[1]


def test_a_csv_shows_as_a_read_only_table():
    js = _text("frontend", "js", "documents-code.js")
    assert 'csv: "main"' in js
    html = js.split("function docCsvTableHtml(text, title)", 1)[1].split("\n}\n", 1)[0]
    assert "docSqlCsvRows(text, DOC_RUN_MAX_ROWS + 2" in html and 'esc(cell)' in html
    assert '"\\t"' in html and "<thead>" in html
    # Run sends the table as an HTML page; the panel exists for a CSV too.
    run = _text("frontend", "js", "run-core.js")
    assert 'source: docCsvTableHtml(request.source, request.path)' in run.split("\n  csv: {", 1)[1].split("\n  },", 1)[0]
    assert 'type.ext === "csv" ? docRunExtension(CM) : []' in js
    # A page with nothing printed gives its frame the whole body.
    assert '".cm-run-panel.is-page .cm-run-log:empty": { display: "none" }' in _text("frontend", "js", "documents.js")


def test_a_summary_carries_the_line_count(client):
    code = client.post(
        "/documents", json={"title": "spin.js", "file_type": "js", "content": "a\nb\nc"}
    ).json()
    empty = client.post("/documents", json={"title": "blank", "content": ""}).json()
    rows = {row["id"]: row for row in client.get("/documents").json()}
    assert rows[code["id"]]["lines"] == 3
    assert rows[empty["id"]]["lines"] == 0
