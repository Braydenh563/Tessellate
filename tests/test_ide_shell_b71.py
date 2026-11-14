"""Brief 71 (DOCUMENTS_PLAN 23, I3): the code editor's IDE shell.

The panel's tabs (D8) as one table, the Problems tab fed by the editor's
diagnostics, the two consoles through the sandbox's `eval` message, the
editor's palette as the app's palette narrowed by ">", the split, and the
keybindings sheet drawn from the command table. The browser half is
`scratchpad/ui-sweeps/code-keys.js`, `ide-shell.js` and `ide-split.js`; these hold what
the source and CPython can show.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api.run_sandbox import PY_RUNNER, RUN_SANDBOX_HTML, RUN_SANDBOX_PY_HTML
from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CODE = (JS / "documents-code.js").read_text(encoding="utf-8")
#: documents-ide.js is one closure now (ranked row 37a); these tests slice or run its private functions, so they read it as it was before it was wrapped (`_js_scope.unwrapped`): same code, same assertions.
IDE = _js_scope.unwrapped((JS / "documents-ide.js").read_text(encoding="utf-8"))
DOCS = (JS / "documents.js").read_text(encoding="utf-8")
PALETTE = _js_scope.unwrapped((JS / "app-palette.js").read_text(encoding="utf-8"))
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


def _table() -> str:
    return DOCS[DOCS.index("// DOC-COMMANDS-BEGIN") : DOCS.index("// DOC-COMMANDS-END")]


# --- the panel (D8) -------------------------------------------------------------


def test_the_tabs_are_one_table_with_vs_codes_chords() -> None:
    table = CODE[CODE.index("const DOC_PANEL_TABS = [") : CODE.index("];", CODE.index("const DOC_PANEL_TABS = ["))]
    rows = re.findall(r'\{ id: "(\w+)", label: "([^"]+)", keys: "([^"]+)" \}', table)
    assert [r[0] for r in rows[:4]] == ["output", "problems", "tests", "console"]
    keys = {r[0]: r[2] for r in rows}
    assert keys["problems"] == "Ctrl+Shift+M" and keys["console"] == "Ctrl+Shift+Y"
    #: The chords are read from the table, so a Debug row (Brief 70) needs
    #: no other change to be toggled.
    chord = _function(CODE, "docPanelChord")
    assert "DOC_PANEL_TABS" in chord and '"Ctrl+J"' in chord


def test_the_head_is_a_dock_with_the_tabs_as_its_identity() -> None:
    panel = _function(CODE, "docRunPanel")
    assert '"cm-run-head dock"' in panel and '"dock-identity cm-run-identity"' in panel
    assert '"tabs-line cm-panel-tabs"' in panel and '"tablist"' in panel and '"tab"' in panel
    assert '"dock-actions cm-run-actions"' in panel
    #: Worded ghosts first, the icon run (help, Close) last. L317 added the worded "Query as SQL" ghost for CSV.
    assert "actions.append(live, stdinButton, tests, query, again, stopButton, clear, help, close)" in panel
    #: A count is the dock's quiet `.dock-chip`, never a pill.
    assert '"dock-chip cm-panel-count"' in panel


def test_each_tab_keeps_its_height_and_output_keeps_one_per_document() -> None:
    save = _function(IDE, "docIdeRunSaveHeight")
    assert "currentDoc.id" in save and "`panel:${tab}`" in save
    assert '"mm-panel-tab"' in _function(IDE, "docIdeRunGrip")
    assert '"mm-panel-tab"' in _function(CODE, "docRunShowTab")
    assert "localStorage" not in IDE


def test_the_editor_stops_the_chords_the_registry_would_also_answer() -> None:
    keydown = _function(IDE, "docIdeKeydown")
    assert "docPanelChord(event)" in keydown and "event.stopPropagation()" in keydown
    slot = _function(IDE, "docIdeSlot")
    assert "Prec.highest(CM.view.EditorView.domEventHandlers({ keydown: (event) => docIdeKeydown(event) }))" in slot
    #: The registry gives these two to other things (settings-wiring.js).
    wiring = (JS / "settings-wiring.js").read_text(encoding="utf-8")
    assert 'attachNote: { keys: "Ctrl+Shift+P"' in wiring and 'toggleCompanion: { keys: "Ctrl+Shift+Y"' in wiring


def test_problems_lists_every_diagnostic_and_follows_the_checks() -> None:
    render = _function(CODE, "docProblemsRender")
    assert "lint.forEachDiagnostic(state" in render and "docRun.problemsLog" in render
    assert "setDiagnosticsEffect" in _function(CODE, "docRunExtension")
    #: Every code file has the panel, not only the kinds that run.
    assert "docRunnable(type) ? docRunExtension(CM) : []" not in CODE


def test_tests_have_their_own_tab() -> None:
    assert "docRun.testsLog" in _function(CODE, "docRunTestRow")
    assert 'docRunShowTab("tests")' in _function(CODE, "docRunCode")


# --- the consoles (D8) ----------------------------------------------------------


def test_the_console_answers_are_routed_by_their_eval_number() -> None:
    assert "docConsoleMessage(data)" in CODE
    send = _function(CODE, "docConsoleEval")
    assert 'type: "eval"' in send and "mmEval: seq" in send
    keys = _function(CODE, "docConsoleKey")
    assert '"ArrowUp"' in keys and '"ArrowDown"' in keys


def test_the_javascript_page_evaluates_in_the_workers_global() -> None:
    assert 'if (d.type === "eval") { evalJs(d); return; }' in RUN_SANDBOX_HTML
    assert "(0,eval)(String(m.source))" in RUN_SANDBOX_HTML
    assert "t:'eval-done'" in RUN_SANDBOX_HTML
    #: A console line's own `console.log` has no document line.
    assert r"if(/\\beval at /.test(s[3]||''))return null;" in RUN_SANDBOX_HTML


def test_the_python_page_evaluates_in_the_last_runs_namespace() -> None:
    assert 'if (d.type === "eval")' in RUN_SANDBOX_PY_HTML
    assert "_mm_eval" in RUN_SANDBOX_PY_HTML


def test_the_python_console_in_cpython() -> None:
    scope: dict = {}
    exec(PY_RUNNER, scope)  # noqa: S102 - the runner's own source, as the worker runs it
    rows: list = []

    def emit(*row):
        rows.append(row)

    scope["_mm_run"]("x = 41\ndef f(n):\n    print('f', n)\n    return n + 1\n", emit)
    scope["_mm_eval"]("f(x)", emit)
    scope["_mm_eval"]("y = 2; print(y * 3)", emit)
    scope["_mm_eval"]("1/0", emit)
    assert rows[0] == ("log", "f 41", 3, False)
    assert rows[1] == ("log", "42", None, False)
    assert rows[2] == ("log", "6", None, False)
    assert rows[3][0] == "error" and "ZeroDivisionError" in rows[3][1]


# --- the palette, the split, the sheet --------------------------------------------


def test_the_editor_palette_is_the_apps_palette_narrowed() -> None:
    assert 'input.value = "> "' in _function(IDE, "docIdeOpenPalette")
    #: The branch holds a fallback row since audit 1028 S62 (Search notes when nothing matches).
    assert re.search(r'if \(lowered\.startsWith\(">"\)\) \{\s+const needle = lowered\.slice\(1\)\.trim\(\);\s+const rows = paletteEditorMatches\(needle\);', PALETTE)
    assert 'c.group === "This document"' in _function(PALETTE, "paletteEditorMatches")


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_fuzzy_match_keeps_order_and_prefers_runs() -> None:
    body = _function(PALETTE, "paletteFuzzyScore") + """
const s = (l, n) => paletteFuzzyScore(l, n);
console.log(JSON.stringify([s("Run this file", "rtf"), s("Run this file", "xyz"), s("Fold every block", "fold") > s("Fold every block", "fdbl"), s("Split the editor", "")]));
"""
    out = subprocess.run(["node", "-"], input=body, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    first, missing, prefers, empty = __import__("json").loads(out.stdout)
    assert first > 0 and missing == -1 and prefers is True and empty == 0


def test_the_ide_rows_are_in_the_command_table() -> None:
    table = _table()
    for cid, keys in [
        ("panel", "Ctrl+J"),
        ("console", "Ctrl+Shift+Y"),
        ("command-palette", "Ctrl+Shift+P"),
        ("split", "Ctrl+\\\\"),
        ("outline", "none"),
        ("keybindings", "Ctrl+K Ctrl+S"),
    ]:
        row = re.search(r'\{ id: "' + re.escape(cid) + r'".*?keys: "([^"]*)"', table, re.S)
        assert row, cid
        assert row.group(1) == keys, cid


def test_the_split_shares_one_history_and_the_sheet_reads_the_table() -> None:
    split = _function(IDE, "docIdeToggleSplit")
    assert "CM.commands.undo(main)" in split and "docIde.sync.of(true)" in split
    assert "docIde.sync" in _function(IDE, "docIdeSplitFollow")
    render = _function(IDE, "docIdeRenderKeys")
    assert "DOC_COMMANDS" in render and '"wb-help-row"' in render and '"No key"' in render
    assert 'matchesShortcut(event, "Ctrl+S")' in IDE


def test_the_new_styles_are_lazy() -> None:
    boot = (ROOT / "frontend" / "css" / "09-editor.css").read_text(encoding="utf-8")
    for selector in (".cm-console-line", ".cm-panel-count", "doc-split-on"):
        assert selector in LAZY_CSS and selector not in boot, selector


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_html_has_a_check_for_problems() -> None:
    """A stray closing tag and an element never closed, the two HTML mistakes a
    parser that recovers from everything never reports."""
    cm = (ROOT / "frontend" / "vendor" / "codemirror" / "codemirror.min.js").read_text(encoding="utf-8")
    sets = CODE[CODE.index("const DOC_HTML_VOID") : CODE.index("const DOC_HTML_RAW")]
    body = (
        cm + "\n" + sets + _function(CODE, "docDiagnosticRange") + _function(CODE, "docHtmlDiagnostics")
        + """
const CM = CM6;
const st = CM.state.EditorState.create({ doc: "<html><body>\\n<div>\\n  <p>hi</span>\\n</div>\\n<ul><li>x</ul><br>\\n<b>open\\n<section>ok</section>\\n", extensions: [CM.html.html()] });
console.log(JSON.stringify(docHtmlDiagnostics(CM, st).map((d) => [d.severity, st.doc.lineAt(d.from).number])));
"""
    )
    out = subprocess.run(["node", "-"], input=body, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    assert __import__("json").loads(out.stdout) == [["error", 3], ["warning", 6]]
    assert 'ext === "html"' in _function(CODE, "docCodeLintSource")
