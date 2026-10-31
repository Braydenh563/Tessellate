"""Code documents as a code editor, part four: the rest of VS Code's editing.

The owner, 2026-09-23 (INBOX 402): "are there any other vscode features we
can add to the document editor like emmet for other languages or file
types??" And on Ctrl+/, that it should comment the way VS Code does.

These run the vendored CodeMirror bundle itself in node, with the app's own
language table (`docCmLanguageFor`) and the app's own functions lifted out
of documents.js, so a command is held to the exact text it produces in the
language the app really mounts. The keys reaching them are measured in
Chromium by `scratchpad/ui-sweeps/doccodevs.js`.
"""

from __future__ import annotations

import re

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
#: documents.js and the two files split out of it on 2026-09-24, joined:
#: the code side (documents-code.js) and the prose tools (documents-prose.js)
#: moved there verbatim, and the wiring that mounts them stayed in
#: documents.js, so a test that reads "the documents editor" reads all three.
DOCUMENTS_JS = tuple(
    ROOT / "frontend" / "js" / name
    for name in ("documents.js", "documents-code.js", "documents-prose.js")
)


def _documents_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOCUMENTS_JS)
CM_JS = ROOT / "frontend" / "vendor" / "codemirror" / "codemirror.min.js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _source() -> str:
    return _documents_text()


def _function(name: str) -> str:
    text = _source()
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


#: What each call gets: a state in the app's language for `ext`, the text
#: with `|` for the caret or `[` `]` for a selection.
_PRELUDE = r"""
const parse = (marked) => {
  const a = marked.indexOf("["), b = marked.indexOf("]"), c = marked.indexOf("|");
  if (c >= 0) return { doc: marked.slice(0, c) + marked.slice(c + 1), anchor: c, head: c };
  if (a >= 0 && b > a) return { doc: marked.slice(0, a) + marked.slice(a + 1, b) + marked.slice(b + 1), anchor: a, head: b - 1 };
  return { doc: marked, anchor: 0, head: 0 };
};
const stateFor = (ext, marked, extra = []) => {
  const { doc, anchor, head } = parse(marked);
  const state = CM.state.EditorState.create({ doc, selection: { anchor, head }, extensions: [docCmLanguageFor(CM, ext), extra] });
  //: `ensureSyntaxTree` finishes the parse in the language field's context,
  //: but `syntaxTree(state)` reads the field's own tree, which is only as far
  //: as the 20ms first pass got (under load, not far): one empty transaction
  //: moves the finished tree into the field. Flaked under `-n 4` without it.
  CM.language.ensureSyntaxTree(state, state.doc.length, 5000);
  const settled = state.update({}).state;
  if (CM.language.syntaxTree(settled).length !== settled.doc.length) throw new Error("the parse did not finish");
  return settled;
};
const target = (state) => {
  const t = { state, dispatch: (tr) => { t.state = tr.state; } };
  return t;
};
"""


def run(functions: list[str], body: str, calls: list) -> list:
    script = (
        CM_JS.read_text(encoding="utf-8")
        + "\nconst CM = CM6;\n"
        + "\nconst docStrCache = new WeakMap();\n"
        + "\n".join(_function(f) for f in ["docStr", "docCmLanguageFor", *functions])
        + _PRELUDE
        + body
        + f"\nconst calls = {json.dumps(calls)};\n"
        "console.log(JSON.stringify(calls.map(([name, ...args]) => fns[name](...args))));\n"
    )
    #: On stdin: the bundle is 795 KB, past the kernel's limit for one
    #: argument (128 KB), so `node -e` cannot carry it.
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


# --- 1. the comment toggle, by the language at the caret ------------------------

_COMMENT = """
const fns = {
  toggle: (ext, marked, block) => {
    const t = target(stateFor(ext, marked));
    const done = docCodeCommentRun(CM, t, block);
    return done ? t.state.doc.toString() : null;
  },
  twice: (ext, marked) => {
    const t = target(stateFor(ext, marked));
    docCodeCommentRun(CM, t, false);
    docCodeCommentRun(CM, t, false);
    return t.state.doc.toString();
  },
};
"""

_HTML = "<p>x</p>\n<script>\n  let a = 1;|\n</script>\n<style>\n  a { color: red; }\n</style>"


@node
@pytest.mark.parametrize(
    ("ext", "marked", "block", "expected"),
    [
        # The owner's gap: one HTML file, three languages, by the caret.
        ("html", _HTML, False, "<p>x</p>\n<script>\n  // let a = 1;\n</script>\n<style>\n  a { color: red; }\n</style>"),
        (
            "html",
            _HTML.replace("1;|", "1;").replace("red; }", "red; }|"),
            False,
            "<p>x</p>\n<script>\n  let a = 1;\n</script>\n<style>\n  /* a { color: red; } */\n</style>",
        ),
        ("html", "<p>x|</p>", False, "<!-- <p>x</p> -->"),
        # JSX children take braces, the code around them `//`.
        (
            "js",
            "const A = () => (\n  <div>\n    <span>hi</span>|\n  </div>\n);",
            False,
            "const A = () => (\n  <div>\n    {/* <span>hi</span> */}\n  </div>\n);",
        ),
        ("js", "const a = 1;|", False, "// const a = 1;"),
        ("ts", "let a: number = 1;|", False, "// let a: number = 1;"),
        ("css", "a { color: red; }|", False, "/* a { color: red; } */"),
        ("py", "x = 1|", False, "# x = 1"),
        # A grammar from the legacy modes brings its own tokens too.
        ("c", "int x = 1;|", False, "// int x = 1;"),
        ("sql", "select 1;|", False, "-- select 1;"),
        # The marker goes after the indentation, never at column zero.
        ("py", "if x:\n    [y = 1]", False, "if x:\n    # y = 1"),
        # A block keeps its shape: the marker at the block's own indent.
        ("py", "[if x:\n    y = 1]", False, "# if x:\n#     y = 1"),
        # Blank lines are left alone.
        ("py", "[a = 1\n\nb = 2]", False, "# a = 1\n\n# b = 2"),
        # Uncomment only when every line is commented: a real comment inside
        # the selection is not stripped, it is commented with the rest.
        ("py", "[# a\nb = 2]", False, "# # a\n# b = 2"),
        ("py", "[# a\n# b]", False, "a\nb"),
        # Shift+Alt+A: a block comment around the selection.
        ("js", "f([a + b])", True, "f(/* a + b */)"),
        ("css", "a { [color: red;] }", True, "a { /* color: red; */ }"),
        ("html", "<p>[x]</p>", True, "<p><!-- x --></p>"),
    ],
)
def test_the_comment_toggle_follows_the_language_at_the_caret(ext, marked, block, expected):
    assert run(["docCodeCommentRun"], _COMMENT, [["toggle", ext, marked, block]])[0] == expected


@node
@pytest.mark.parametrize(
    ("ext", "marked"),
    [
        ("py", "[if x:\n    y = 1\n\n    z = 2]"),
        ("js", "[function f() {\n  return 1;\n}]"),
        ("html", "<div>\n  <p>x|</p>\n</div>"),
        ("css", "a {\n  color: red;|\n}"),
    ],
)
def test_the_comment_toggle_round_trips_exactly(ext, marked):
    plain = marked.replace("[", "").replace("]", "").replace("|", "")
    assert run(["docCodeCommentRun"], _COMMENT, [["twice", ext, marked]])[0] == plain


def test_ctrl_slash_delegates_for_code_and_keeps_its_rules_for_prose():
    body = _function("toggleDocComment")
    assert body.index("docCodeCommentAtCaret(box)") < body.index("docUndoBreak()"), (
        "a code document is commented by the language at the caret first"
    )
    at = _function("docCodeCommentAtCaret")
    assert "type.previewable" in at and 'docView === "plain"' in at
    #: A grammar with no comment tokens falls back to the file type's marker.
    assert "if (!docCodeCommentRun(CM, target, block)) return false;" in at


def test_ctrl_slash_has_one_owner_per_surface():
    """Measured before the fix: Ctrl+/ on a line of prose left a lone "/".
    The editor's keymap commented the line and selected it, then the global
    registry's `editorMenu` wrote "/" over the selection. In a document the
    comment owns the chord; in a note box the blocks menu does."""
    app = app_js_text()
    assert 'if (id === "editorMenu" && e.defaultPrevented) continue;' in app
    notes = _function("noteSurfaceKeymap")
    # A note binds Ctrl+/ itself now, ahead of the engine's defaultKeymap,
    # whose own comment toggle wrote `<!--  -->` into a markdown note. The
    # rule is unchanged: in a note the chord opens the blocks menu and never
    # comments.
    assert "toggleDocComment" not in notes, "a note box's Ctrl+/ is the blocks menu, not a comment"
    if '"Mod-/"' in notes:
        bound = notes[notes.index('"Mod-/"') :][:200]
        assert "editorOpenMenuByShortcut" in bound, bound
    assert '{ key: "Mod-/", run: () => { toggleDocComment(surface()); return true; } }' in _function("docCmKeymap")


def test_sql_mounts_the_mode_not_the_factory():
    """`sql` in the legacy modes is the function that makes a mode; mounting
    it threw from the parser and a .sql document could not be opened."""
    assert 'case "sql": return stream(CM.standardSQL);' in _function("docCmLanguageFor")


def test_block_comment_is_in_the_palette_on_a_free_key():
    source = _source()
    table = source[source.index("// DOC-COMMANDS-BEGIN") : source.index("// DOC-COMMANDS-END")]
    assert 'keys: "Shift+Alt+A",\n    code: true' in table
    app = app_js_text()
    assert '"Shift+Alt+A"' not in app and '"Alt+Shift+A"' not in app, "Shift+Alt+A is taken in the registry"


# --- 6. bracket pair colours and indentation guides -------------------------------

_BRACKETS = """
const fns = {
  depths: (ext, text) => {
    const state = stateFor(ext, text + "|");
    const tree = CM.language.ensureSyntaxTree(state, state.doc.length, 5000);
    return docBracketDepths(text, 0, (i) => !DOC_BRACKET_NOT_CODE.test(tree.resolveInner(i, 1).name))
      .map(([i, d]) => text[i] + d).join(" ");
  },
};
"""


def _const(name: str) -> str:
    text = _source()
    start = text.index(f"const {name} = ")
    return text[start : text.index("\n", start) + 1]


@node
@pytest.mark.parametrize(
    ("ext", "text", "depths"),
    [
        # Nested pairs take the next tone; a closer takes its opener's.
        ("js", "f(a[b{c}])", "(0 [1 {2 }2 ]1 )0"),
        # A bracket in a string, a comment or a regex is not a bracket.
        ("js", 'f("(", /[(]/)\n// (\ng()', "(0 )0 (0 )0"),
        ("py", "x = [f(1), '(']  # (", "[0 (1 )1 ]0"),
        ("css", 'a { b: url("(") }', "{0 (1 )1 }0"),
        # HTML's text is prose; its script is code.
        ("html", "<p>(a)</p>\n<script>f([1])</script>", "(0 [1 ]1 )0"),
        # A stream mode's own string tokens count too.
        ("c", 'int x = f("(", a[0]);', "(0 [1 ]1 )0"),
    ],
)
def test_bracket_depths_skip_what_is_not_code(ext, text, depths):
    body = _const("DOC_BRACKET_NOT_CODE") + _BRACKETS
    assert run(["docBracketDepths"], body, [["depths", ext, text]])[0] == depths


def test_guides_and_brackets_are_mounted_for_code_and_drawn_quietly():
    extras = _function("docCompletionExtras")
    assert 'docIndentGuides(CM, type.indent || "  ")' in extras and "docBracketColours(CM)" in extras
    theme = _source().split("function docCmTheme(CM) {", 1)[1].split("\nfunction ", 1)[0]
    guide = theme.split('".cm-indent-guide"', 1)[1].split("}", 1)[0]
    assert "var(--border)" in guide
    for k in range(3):
        rule = theme.split(f'".cm-bracket-{k}"', 1)[1].split("}", 1)[0]
        assert "color-mix(in srgb, var(--" in rule and "70%, var(--text))" in rule


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("lead", "unit", "steps"),
    [
        ("        ", "    ", [[0, 4], [4, 8]]),
        ("      ", "    ", [[0, 4]]),
        ("\t\t", "\t", [[0, 1], [1, 2]]),
        ("  ", "  ", [[0, 2]]),
        ("", "    ", []),
        # Tabs and spaces mixed: each tab a step, each full run of spaces one.
        ("\t    ", "    ", [[0, 1], [1, 5]]),
    ],
)
def test_indent_steps(lead, unit, steps):
    script = _function("docIndentSteps") + "\nconst a = JSON.parse(process.argv[1]);\nconsole.log(JSON.stringify(docIndentSteps(a[0], a[1])));\n"
    out = subprocess.run(["node", "-e", script, json.dumps([lead, unit])], capture_output=True, text=True, check=True, timeout=60)
    assert json.loads(out.stdout) == steps


# --- 7. symbols: the outline and the breadcrumb of a code file ---------------------

_SYMBOLS = """
const fns = {
  symbols: (ext, text) => docCodeSymbols(CM, stateFor(ext, text + "|"), ext).map((s) => [s.line, s.level, s.text]),
};
"""


@node
@pytest.mark.parametrize(
    ("ext", "text", "symbols"),
    [
        (
            "js",
            "function f(a) {}\nclass A {\n  m() {}\n  static n = 1;\n}\nconst g = () => 1;\nconst v = 3;\n// function nope() {}\nconst s = 'class B {}';",
            [[0, 1, "f()"], [1, 1, "class A"], [2, 2, "m()"], [5, 1, "g()"]],
        ),
        (
            "ts",
            "interface I { a: number }\ntype T = string;\nenum E { A }\nexport function k(): void {}",
            [[0, 1, "interface I"], [1, 1, "type T"], [2, 1, "enum E"], [3, 1, "k()"]],
        ),
        (
            "py",
            "# class Comment:\ndef f(x):\n    pass\nclass A:\n    def m(self):\n        def inner():\n            pass",
            [[1, 1, "f()"], [3, 1, "class A"], [4, 2, "m()"], [5, 3, "inner()"]],
        ),
        (
            "css",
            ".card > p, a:hover { color: red }\n@media (max-width: 600px) {\n  .x { color: red }\n}",
            [[0, 1, ".card > p, a:hover"], [1, 1, "@media (max-width: 600px)"], [2, 2, ".x"]],
        ),
        ("go", "func main() {}", []),
    ],
)
def test_code_symbols(ext, text, symbols):
    assert run(["docCodeSymbols"], _const("DOC_SYMBOL_EXTS") + _SYMBOLS, [["symbols", ext, text]])[0] == symbols


def test_the_outline_reads_symbols_for_code_and_never_moves_them():
    outline = _function("renderDocOutline")
    assert "if (fileType.previewable) headings = docScanHeadings(text);" in outline
    assert "docCodeSymbols(window.CM6, docCmView.state, fileType.ext)" in outline
    assert "if (!needle && !heading.symbol) {" in outline
    assert "if (heading.symbol) return;" in outline
    source = _source()
    table = source[source.index("// DOC-COMMANDS-BEGIN") : source.index("// DOC-COMMANDS-END")]
    assert 'label: "Go to a symbol in this file", keys: "none",\n    code: true, run: () => docOpenSymbols() }' in table
    app = app_js_text()
    assert 'newChat: { keys: "Ctrl+Shift+O"' in app, "if the chord is free again, give it to the symbols"


# --- 8. Alt+Z and shown whitespace ---------------------------------------------------


def test_wrap_and_whitespace_are_code_preferences_in_the_wrap_compartment():
    draw = _function("docCmDrawFor")
    assert 'type.previewable || docToolPref("codeWrap", false)' in draw
    assert '!type.previewable && docToolPref("whitespace", false)' in draw
    assert "CM.view.highlightWhitespace()" in draw
    source = _source()
    assert "docCmParts.wrap.of(docCmDrawFor(CM, type))" in source
    assert "docCmParts.wrap.reconfigure(docCmDrawFor(CM, type))" in source
    assert '{ key: "Alt-z", run: () => { docToggleCodeDraw("codeWrap"); return true; } }' in _function("docCodeEditing")
    app = app_js_text()
    assert '"Alt+Z"' not in app, "Alt+Z is taken in the registry"
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for row in ("doc-code-wrap-row", "doc-whitespace-row"):
        assert f'<label id="{row}" class="menu-item doc-dock-menu-item doc-dock-menu-check checkbox-label hidden"' in html
    assert 'for (const id of ["doc-code-wrap-row", "doc-whitespace-row", "doc-minimap-row"]) $(id)?.classList.toggle("hidden", type.previewable);' in _function("syncDocFileType")
    theme = source.split("function docCmTheme(CM) {", 1)[1].split("\nfunction ", 1)[0]
    assert "var(--muted)" in theme.split('".cm-highlightSpace"', 1)[1].split("}", 1)[0]


# --- 9. sticky scroll --------------------------------------------------------------

_STICKY = """
const fns = {
  sticky: (ext, text, line) => {
    const state = stateFor(ext, text + "|");
    const symbols = docCodeSymbols(CM, state, ext);
    const pos = state.doc.line(line).from;
    return docStickyHeaders(symbols, pos, line).map((s) => s.text);
  },
};
"""

_PY = "class A:\n    def m(self):\n        x = 1\n        y = 2\n        z = 3\n    def n(self):\n        pass\n"


@node
@pytest.mark.parametrize(
    ("line", "pinned"),
    [
        # Inside m's body with both headers above: outermost first.
        (4, ["class A", "m()"]),
        # On m's own first line, only the class is above it.
        (2, ["class A"]),
        # Past m, into n: m is no longer pinned.
        (7, ["class A", "n()"]),
        (1, []),
    ],
)
def test_sticky_headers(line, pinned):
    body = _const("DOC_SYMBOL_EXTS") + _STICKY
    assert run(["docCodeSymbols", "docStickyHeaders"], body, [["sticky", "py", _PY, line]])[0] == pinned


def test_sticky_is_an_opaque_overlay_not_a_panel():
    sticky = _function("docStickyScroll")
    assert "view.dom.appendChild(this.dom)" in sticky and "showPanel" not in sticky
    assert 'addEventListener("scroll", this.onScroll, { passive: true })' in sticky
    assert "removeEventListener(\"scroll\", this.onScroll)" in sticky
    assert "DOC_SYMBOL_EXTS.has(type.ext) ? docStickyScroll(CM) : []" in _function("docCompletionExtras")
    theme = _source().split("function docCmTheme(CM) {", 1)[1].split("\nfunction ", 1)[0]
    assert "var(--modal-bg-opaque)" in theme.split('".cm-sticky"', 1)[1].split("}", 1)[0]


# --- INBOX 404 (1): snippets per language ----------------------------------------

_SNIPPETS = """
//: The file types' own indent units (core/filetypes.py), as the app mounts them.
const UNITS = { java: "    ", cs: "    ", c: "    ", cpp: "    ", go: "\t", rs: "    ", kt: "    ", swift: "    ", php: "    ", py: "    ", sql: "    " };
const expandIn = (ext, template) => {
  const t = target(stateFor(ext, "|", CM.language.indentUnit.of(UNITS[ext] || "  ")));
  CM.autocomplete.snippet(template)(t, null, 0, 0);
  return t.state.doc.toString();
};
const fns = {
  every: () => {
    const bad = [];
    for (const [ext, rows] of Object.entries(DOC_CODE_SNIPPETS)) {
      for (const [label, detail, template] of rows) {
        let out = "";
        try { out = expandIn(ext, template); } catch (e) { bad.push(`${ext} ${label}: ${e.message}`); continue; }
        if (/[$#]\\{/.test(out) || !detail || !/^[a-z!]+$/i.test(label)) bad.push(`${ext} ${label}: ${JSON.stringify(out)}`);
      }
    }
    return bad;
  },
  one: (ext, label) => {
    const row = DOC_CODE_SNIPPETS[ext].find((r) => r[0] === label);
    return expandIn(ext, row[2]);
  },
};
"""


def _snippet_table() -> str:
    text = _source()
    start = text.index("const DOC_CODE_SNIPPETS = {")
    end = text.index("DOC_CODE_SNIPPETS.ts = DOC_CODE_SNIPPETS.js;", start)
    return text[start:end] + "DOC_CODE_SNIPPETS.ts = DOC_CODE_SNIPPETS.js;\n"


@node
def test_every_snippet_expands_cleanly_in_its_own_language():
    assert run([], _snippet_table() + _SNIPPETS, [["every"]])[0] == []


@node
@pytest.mark.parametrize(
    ("ext", "label", "text"),
    [
        ("java", "main", "public static void main(String[] args) {\n    \n}"),
        ("java", "sout", "System.out.println();"),
        ("cs", "prop", "public int Name { get; set; }"),
        ("go", "iferr", "if err != nil {\n\treturn err\n}"),
        ("rs", "println", 'println!("");'),
        ("py", "main", 'if __name__ == "__main__":\n    main()'),
        ("sql", "sel", "SELECT * FROM table;"),
        ("bash", "for", "for item in items; do\n  \ndone"),
    ],
)
def test_snippets_write_the_statement_in_the_files_own_indent(ext, label, text):
    assert run([], _snippet_table() + _SNIPPETS, [["one", ext, label]])[0] == text


def test_snippets_reach_the_list():
    source = _function("docCodeCompletionSource")
    assert "docCodeSnippetOptions(CM, ext)" in source and "for (const label of snipped) seen.add(label);" in source
    assert "docNativeSnippets(CM, type.ext)" in _function("docCompletionExtras")
    assert "CM.autocomplete.ifNotIn(quiet" in _function("docNativeSnippets")


# --- INBOX 404 (2): Run and its output -----------------------------------------------


def test_run_goes_through_the_sandbox_and_trusts_only_its_frame():
    source = _source()
    assert 'const DOC_RUN_SANDBOX_URL = "/documents/run-sandbox";' in source
    panel = _function("docRunPanel")
    assert 'frame.setAttribute("sandbox", "allow-scripts")' in panel
    assert "allow-same-origin" not in panel
    listener = source[source.index('window.addEventListener("message", (event) => {\n  if (!docRun') :]
    listener = listener[: listener.index("\n});\n")]
    assert "event.source !== docRun.frame.contentWindow" in listener
    assert "data.mmRun !== docRun.id" in listener
    #: What a program printed is shown as text, never as markup.
    row = _function("docRunRow")
    assert "textContent" in row and "innerHTML" not in row
    #: Stop, the timeout and the line cap all end a run.
    assert "docRunArmTimeout(id)" in _function("docRunCode") and "DOC_RUN_MAX_ROWS" in listener
    assert "DOC_RUN_TIMEOUT_MS" in _function("docRunArmTimeout")


def test_python_runs_in_its_own_runner_once_the_extra_is_installed():
    """The owner, 2026-09-24: "Run Python files: yes, as an opt-in extra"."""
    source = _source()
    #: The types that run and their page; the languages are run-core.js's rows
    #: (tests/test_run_protocol.py).
    assert re.search(r'^const DOC_RUN_KINDS = \{[^}]*\bpy: "python"', source, re.M)
    assert 'const DOC_RUN_SANDBOX_PY_URL = "/documents/run-sandbox/python";' in source
    run = _function("docRunCode")
    #: Not installed: the panel says so and offers the Settings row, rather
    #: than a frame that fails to load a runtime.
    assert "await docRunPythonReady()" in run and "docRunPythonMissing();" in run
    assert "docRunOpenPythonExtra()" in _function("docRunPythonMissing")
    assert 'getElementById("extra-row-pyodide")' in _function("docRunOpenPythonExtra")
    #: The ten seconds count the script, not the runtime's start-up.
    listener = source[source.index('window.addEventListener("message", (event) => {\n  if (!docRun') :]
    listener = listener[: listener.index("\n});\n")]
    assert 'data.t === "started"' in listener and "docRunArmTimeout(docRun.id)" in listener
    #: A late `ready` from the runner the frame just left releases nothing.
    assert "if (data.runner !== wanted) return;" in listener
    #: A panel's own frame loads the JavaScript page; Python's page is the
    #: shared one (Brief 101c, tests/test_python_host.py).
    assert "frame.src = DOC_RUN_SANDBOX_URL;" in _function("docRunPanel")
    assert "own.src = runner;" in _function("docRunSelectFrame")
    #: The row id the button looks for is the one Settings draws.
    app = app_js_text()
    assert 'li.id = `extra-row-${extra.id}`;' in app


def test_run_is_on_a_free_chord_and_in_the_dock_for_code():
    assert '{ key: "Mod-Shift-Enter", run: () => { if (!docRunnable(docFileType())) return false; docRunCode(); return true; } }' in _function("docCodeEditing")
    app = app_js_text()
    assert '"Ctrl+Shift+Enter"' not in app
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<button id="doc-code-run" class="small hidden" type="button"' in html
    assert '$("doc-code-run")?.classList.toggle("hidden", !docRunnable(type));' in _function("syncDocFileType")
    source = _source()
    table = source[source.index("// DOC-COMMANDS-BEGIN") : source.index("// DOC-COMMANDS-END")]
    assert 'keys: "Ctrl+Shift+Enter",\n    code: true, run: () => docRunCode() }' in table


# --- INBOX 404 (4): go to definition, references ------------------------------------

_DEFS = """
const at = (marked) => marked.indexOf("|");
const fns = {
  def: (ext, marked) => {
    const state = stateFor(ext, marked);
    const pos = state.selection.main.head;
    const word = docWordAt(state, pos);
    const d = docPickDefinition(docDefinitionsOf(CM, state, word.name, ext), pos);
    return d ? state.doc.lineAt(d.from).number : null;
  },
  refs: (ext, marked) => {
    const state = stateFor(ext, marked);
    const word = docWordAt(state, state.selection.main.head);
    return docReferencesOf(CM, state, word.name).map((r) => state.doc.lineAt(r.from).number);
  },
};
"""

_FUNCS = ["docWordAt", "docReferencesOf", "docPythonDefines", "docDefinitionsOf", "docPickDefinition"]


def _defs_body() -> str:
    return "".join(_const(n) for n in ("DOC_CHECK_MAX_CHARS", "DOC_BRACKET_NOT_CODE", "DOC_DEFINING", "DOC_SCOPES")) + _DEFS


@node
@pytest.mark.parametrize(
    ("ext", "marked", "line"),
    [
        # A function, used below its definition.
        ("js", "function total(a) {\n  return a;\n}\nconst x = tot|al(1);", 1),
        # A parameter shadows the outer name inside its function.
        ("js", "const a = 1;\nfunction f(a) {\n  return a| + 1;\n}", 2),
        # And outside it, the outer one.
        ("js", "const a = 1;\nfunction f(a) {\n  return a;\n}\nconsole.log(a|);", 1),
        # A method, by its name.
        ("ts", "class A {\n  run(): void {}\n}\nnew A().ru|n();", 2),
        # Python: a def, a parameter, an assignment.
        ("py", "def area(r):\n    return r * r\n\nx = are|a(2)", 1),
        ("py", "n = 1\ndef f(n):\n    return n| + 1", 2),
        ("py", "total = 0\nfor i in range(3):\n    total += i\nprint(tot|al)", 1),
        # A grammar with no tree: the name after a defining word.
        ("go", "func add(a int) int {\n\treturn a\n}\n\nfunc main() {\n\tad|d(1)\n}", 1),
        ("c", "int square(int x) {\n    return x * x;\n}\nint y = squ|are(3);", 1),
        # A name only in a string has no definition.
        ("js", 'const s = "total";\nto|tal;', None),
    ],
)
def test_go_to_definition(ext, marked, line):
    assert run(_FUNCS, _defs_body(), [["def", ext, marked]])[0] == line


@node
@pytest.mark.parametrize(
    ("ext", "marked", "lines"),
    [
        # Every use in code; the string and the comment are not uses.
        ("js", 'const total = 1;\n// total\nconst s = "total";\nf(tot|al, total);', [1, 4, 4]),
        ("py", "x = 1\n# x\nprint(x|)", [1, 3]),
        # A longer name that contains it is not it.
        ("js", "let item = 1;\nlet items = [ite|m];", [1, 2]),
    ],
)
def test_references(ext, marked, lines):
    assert run(_FUNCS, _defs_body(), [["refs", ext, marked]])[0] == lines


def test_definition_keys_and_find_in_documents():
    editing = _function("docCodeEditing")
    assert '{ key: "F12", run: () => docGoToDefinition() }' in editing
    assert '{ key: "Shift-F12", run: () => docShowReferences() }' in editing
    assert '{ key: "Mod-Shift-f", run: () => docFindInDocuments() }' in _function("docCmKeymap")
    find = _function("docFindInDocuments")
    assert 'openFinder(query, { kind: "document" })' in find
    app = app_js_text()
    for chord in ('"F12"', '"Shift+F12"', '"Ctrl+Shift+F"'):
        assert f"keys: {chord}" not in app, f"{chord} is taken in the registry"
    assert '{ key: "document", icon: "ph:file-text"' in app
