"""Code documents as a code editor, part two: indentation, formatting, fixes.

The owner, 2026-09-23: "if I write a \" it automatically does \"\" ... where I
write var_name { and it automatically does {} and then if I press enter it
automatically indents ... also a button to automatically format the whole
document, ot just a selection ... also recommended fixes to apply".

The pairs themselves are CodeMirror's own `closeBrackets` and are measured in
Chromium by `scratchpad/ui-sweeps/doccodeedit.js`. Everything that decides
*what text results* is pure string work in documents.js's `DOC-CODE` region
(the structure scan, the indent a new line gets, the formatter, every quick
fix), so it runs here in node and each case is held to the exact text it
must produce. A formatter that is "about right" is a formatter that corrupts
somebody's file, so nothing here is approximate.
"""

from __future__ import annotations

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

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _region(begin: str, end: str) -> str:
    text = _documents_text()
    start, stop = text.find(begin), text.find(end)
    assert start != -1 and stop > start, f"the {begin} markers are missing from documents-code.js"
    return text[start:stop]


def run(calls: list) -> list:
    """Evaluate `[name, *args]` calls against the regions and return results."""
    script = (
        _region("// DOC-JSON-BEGIN", "// DOC-JSON-END")
        + _region("// DOC-CODE-BEGIN", "// DOC-CODE-END")
        + "\nconst fns = {docCodeScan, docCodeIndentLevel, docFormatCodeText, docFormatJsonText,"
        " docFormatMarkupText, docCodeFixes, docJsonFixes, docJsonErrorAt, docPythonColonFix,"
        " docIndentMixFixes};\n"
        "const apply = (text, edits) => { let out = text;"
        " for (const e of [...edits].sort((a, b) => b.from - a.from))"
        " out = out.slice(0, e.from) + e.insert + out.slice(e.to); return out; };\n"
        "fns.applyFix = (fn, text, ...rest) => {"
        " const diags = fns[fn](text, ...rest);"
        " return diags.map((d) => ({ message: d.message, severity: d.severity || 'error',"
        " fixes: (d.fixes || []).map((f) => [f.name, apply(text, f.edits)]) })); };\n"
        "fns.applyJson = (text, unit) => docJsonFixes(text, docJsonErrorAt(text), unit)"
        ".map((f) => [f.name, apply(text, f.edits)]);\n"
        "fns.applyColon = (text, line) => { const f = docPythonColonFix(text, line);"
        " return f && [f.name, apply(text, f.edits)]; };\n"
        "fns.levels = (text, ext) => docCodeScan(text, ext).lines.map((l) => l.level);\n"
        "fns.problems = (text, ext) => docCodeScan(text, ext).problems.map((p) => [p.kind, p.ch, p.line]);\n"
        "const calls = JSON.parse(process.argv[1]);\n"
        "console.log(JSON.stringify(calls.map(([name, ...args]) => fns[name](...args))));\n"
    )
    out = subprocess.run(
        ["node", "-e", script, json.dumps(calls)], capture_output=True, text=True, check=True, timeout=60
    )
    return json.loads(out.stdout)


def one(name: str, *args):
    return run([[name, *args]])[0]


# --- the indent a new line gets (Enter, and a typed closer) -----------------


@pytest.mark.parametrize(
    ("before", "line", "ext", "level"),
    [
        # The owner's case: `{` then Enter in a C-family file.
        ("int main() {", "", "c", 1),
        ("public class A {\n    void f() {", "", "java", 2),
        ("fn main() {\n    let v = vec![", "", "rs", 2),
        ("func main() {\n\tfoo(a,", "", "go", 2),
        # A typed closer dedents to its opener's line.
        ("int main() {\n    x();\n", "    }", "c", 0),
        ("int main() {\n    if (a) {\n        x();\n", "}", "c", 1),
        # `foo(bar, {` opens two frames on one line and indents its body once.
        ("foo(bar, {", "", "c", 1),
        # Case labels: indented under a C switch, flush under Go's.
        ("switch (x) {\n", "case 1:", "java", 1),
        ("switch (x) {\n    case 1:", "", "java", 2),
        ("func f() {\n\tswitch x {\n", "case 1:", "go", 1),
        # A brace-less if body, and the line after it.
        ("if (x)", "", "c", 1),
        ("if (x)\n    y();", "", "c", 0),
        # A continued expression.
        ("int total = a +", "", "c", 1),
        # Inside a comment or a string the editor keeps the line above's indent.
        ("/* start", "", "c", None),
        ("fn f() {\n    let s = \"multi", "", "rs", None),
        # PHP only indents inside its tags.
        ("<?php\nif ($x) {", "", "php", 1),
    ],
)
def test_the_indent_a_new_line_gets(before, line, ext, level):
    assert one("docCodeIndentLevel", before, line, ext) == level


def test_brackets_in_strings_comments_and_regexes_are_not_structure():
    cases = [
        ('printf("{");\nint x;', "c"),
        ("/* { */\nint x;", "c"),
        ("// {\nint x;", "c"),
        ("char c = '{';\nint x;", "c"),
        ("let c = '{';\nlet s = r#\"{\"#;\nfn f<'a>() {}", "rs"),
        ("const r = /[{(]/g;\nconst t = `${ {a: 1}.a } {`;\nx = a / b;", "js"),
        ("<p>Don't {</p>\n<?php echo 'x'; ?>", "php"),
        ("cat <<EOF\ndon't {\nEOF\necho hi", "bash"),
        ('s = """ { """\nx = 1', "py"),
        ("x = 1'000'000;\nint y;", "cpp"),
    ]
    results = run([["problems", text, ext] for text, ext in cases])
    for (text, ext), problems in zip(cases, results):
        assert problems == [], f"{ext}: {text!r} reported {problems}"


# --- formatting ----------------------------------------------------------------


MESSY_JS = "function f(a){\nif(a){\n      return 1;   \n}else{\nreturn 2;}\n  }\n\n\n"
TIDY_JS = "function f(a){\n  if(a){\n    return 1;\n  }else{\n    return 2;}\n}\n"

MESSY_C = (
    "#include <stdio.h>\n"
    "int main(void) {\n"
    "        int x = 1;\n"
    "  /* a\n"
    "   * b\n"
    "   */\n"
    "    switch (x) {\n"
    "  case 1:\n"
    '  printf("{   ");\n'
    "   break;\n"
    "    }\n"
    "return 0;\n"
    "}"
)
TIDY_C = (
    "#include <stdio.h>\n"
    "int main(void) {\n"
    "    int x = 1;\n"
    "    /* a\n"
    "     * b\n"
    "     */\n"
    "    switch (x) {\n"
    "        case 1:\n"
    '            printf("{   ");\n'
    "            break;\n"
    "    }\n"
    "    return 0;\n"
    "}\n"
)


def test_format_reindents_by_the_brackets_and_moves_nothing_else():
    got = run([
        ["docFormatCodeText", MESSY_JS, "js", "  "],
        ["docFormatCodeText", MESSY_C, "c", "    "],
        ["docFormatCodeText", "package main\nfunc main() {\nswitch x {\ncase 1:\nfoo()\n}\n}", "go", "\t"],
        ["docFormatCodeText", "a{\ncolor:red;\n@media (x) {\nb { c: d; }\n}\n}", "css", "  "],
        ["docFormatCodeText", "promise\n.then(() => {\ny();\n});\nconst t = a +\nb;", "js", "  "],
    ])
    assert got[0]["text"] == TIDY_JS
    assert got[1]["text"] == TIDY_C
    assert got[2]["text"] == "package main\nfunc main() {\n\tswitch x {\n\tcase 1:\n\t\tfoo()\n\t}\n}\n"
    assert got[3]["text"] == "a{\n  color:red;\n  @media (x) {\n    b { c: d; }\n  }\n}\n"
    assert got[4]["text"] == "promise\n  .then(() => {\n    y();\n  });\nconst t = a +\n  b;\n"


def test_format_never_touches_the_inside_of_a_string():
    template = "const s = `\n    keep   \n  this`;\nif (x) {\n        y();\n}\n"
    python = 'x = 1   \ns = """a   \n  b  """   \n\n\n'
    heredoc = "cat <<EOF\nkeep   \nEOF\necho hi   \n"
    yaml = "a: |\n  keep   \n\n  more  \nb: 2   \n"
    got = run([
        ["docFormatCodeText", template, "js", "  "],
        ["docFormatCodeText", python, "py", "    "],
        ["docFormatCodeText", heredoc, "bash", "  "],
        ["docFormatCodeText", yaml, "yaml", "  "],
    ])
    assert got[0]["text"] == "const s = `\n    keep   \n  this`;\nif (x) {\n  y();\n}\n"
    assert got[1]["text"] == 'x = 1\ns = """a   \n  b  """\n'
    assert got[2]["text"] == "cat <<EOF\nkeep   \nEOF\necho hi\n"
    assert got[3]["text"] == "a: |\n  keep   \n\n  more  \nb: 2\n"


def test_python_and_yaml_indentation_is_never_rewritten():
    """Their indentation is their syntax: only trailing space and the final
    line break move."""
    src = "def f():\n        return 1\nclass A:\n  pass\n"
    assert one("docFormatCodeText", src, "py", "    ")["changed"] is False


def test_format_refuses_rather_than_scatters_unbalanced_code():
    got = run([
        ["docFormatCodeText", "int main() {\n  foo(;\n", "c", "    "],
        ["docFormatCodeText", 'int main() {\n  printf("hi);\n}\n', "c", "    "],
        ["docFormatJsonText", '{"a": 1,}', "  "],
        ["docFormatMarkupText", "<root>\n<a>\n</root>", "xml", "  "],
    ])
    assert got[0]["error"].startswith("Not formatted: line 1")
    #: The cause is named, not its consequences: the open string, not the
    #: brackets it swallowed.
    assert got[1]["error"] == "Not formatted: line 2, this string is never closed."
    assert got[2]["error"] == "Not formatted: line 1, a comma with nothing after it."
    assert "nothing is open" in got[3]["error"]


def test_format_selection_touches_only_the_selected_lines():
    src = "int f() {\nint a;\nint b;\nint c;\n}"
    got = one("docFormatCodeText", src, "c", "    ", [2, 2])
    assert got["text"] == "int f() {\nint a;\n    int b;\nint c;\n}"


def test_format_is_idempotent():
    sources = [(MESSY_JS, "js", "  "), (MESSY_C, "c", "    "), ("a{\nb:c;\n}", "css", "  ")]
    first = run([["docFormatCodeText", s, e, u] for s, e, u in sources])
    second = run([["docFormatCodeText", f["text"], e, u] for f, (s, e, u) in zip(first, sources)])
    for again in second:
        assert again["changed"] is False


def test_json_is_reprinted_from_its_own_tokens():
    """JSON.parse plus JSON.stringify would change the data: a number past
    2^53 loses digits, `1.0e5` becomes `100000`. Every token is kept."""
    got = one("docFormatJsonText", '{"a":1,"b":[1,2,{"c":12345678901234567890}],"d":{},"e":[], "f": 1.0e5}', "  ")
    assert got["text"] == (
        '{\n  "a": 1,\n  "b": [\n    1,\n    2,\n    {\n      "c": 12345678901234567890\n    }\n  ],\n'
        '  "d": {},\n  "e": [],\n  "f": 1.0e5\n}\n'
    )


def test_a_json_selection_keeps_its_place():
    got = one("docFormatJsonText", '{"x": [1,2]}', "  ", "    ", False)
    assert got["text"] == '{\n      "x": [\n        1,\n        2\n      ]\n    }'


def test_html_and_xml_are_indented_by_their_elements():
    html = (
        "<html>\n<body>\n<ul>\n<li>one\n<li>two</li>\n</ul>\n<pre>\n  keep   \n</pre>\n"
        "<div\n   class=\"a\">\n<p>Don't <b>x</b></p>\n<br>\n</div>\n<script>\n  if (a < b) {}\n</script>\n</body>\n</html>"
    )
    got = run([
        ["docFormatMarkupText", html, "html", "  "],
        ["docFormatMarkupText", "<?xml version=\"1.0\"?>\n<root>\n<a x=\"1\">\n<b/>\n<!-- c\n  d -->\n</a>\n</root>", "xml", "  "],
    ])
    assert got[0]["text"] == (
        "<html>\n  <body>\n    <ul>\n      <li>one\n      <li>two</li>\n    </ul>\n    <pre>\n  keep   \n</pre>\n"
        "    <div\n       class=\"a\">\n      <p>Don't <b>x</b></p>\n      <br>\n    </div>\n    <script>\n"
        "      if (a < b) {}\n    </script>\n  </body>\n</html>\n"
    )
    assert got[1]["text"] == "<?xml version=\"1.0\"?>\n<root>\n  <a x=\"1\">\n    <b/>\n    <!-- c\n      d -->\n  </a>\n</root>\n"


# --- quick fixes --------------------------------------------------------------


def test_a_missing_bracket_is_added_where_it_was_meant():
    got = run([
        ["applyFix", "docCodeFixes", "int main() {\n  foo(a;\n}\n", "c", "    "],
        ["applyFix", "docCodeFixes", "int main() {\n  if (x > 1 {\n    y();\n  }\n}\n", "c", "    "],
        ["applyFix", "docCodeFixes", "int main() {\n    return 0;\n", "c", "    "],
    ])
    assert got[0][0]["message"] == "This \u201c(\u201d is never closed"
    assert got[0][0]["fixes"] == [["Add the missing \u201c)\u201d", "int main() {\n  foo(a);\n}\n"]]
    assert got[1][0]["fixes"] == [["Add the missing \u201c)\u201d", "int main() {\n  if (x > 1) {\n    y();\n  }\n}\n"]]
    assert got[2][0]["fixes"] == [["Add the missing \u201c}\u201d", "int main() {\n    return 0;\n}\n"]]


def test_a_stray_or_wrong_closer_is_changed_or_removed():
    got = one("applyFix", "docCodeFixes", "int f() {\n    return x];\n}\n", "c", "    ")
    assert got == [{
        "message": "Expected \u201c}\u201d here, found \u201c]\u201d",
        "severity": "error",
        "fixes": [
            ["Change it to \u201c}\u201d", "int f() {\n    return x};\n}\n"],
            ["Remove this \u201c]\u201d", "int f() {\n    return x;\n}\n"],
        ],
    }]


def test_a_string_left_open_is_closed_before_the_line_ends():
    got = one("applyFix", "docCodeFixes", 'int main() {\n    printf("hi);\n}\n', "c", "    ")
    assert [d["message"] for d in got] == ["This string is never closed"]
    assert got[0]["fixes"] == [["Close the string", 'int main() {\n    printf("hi");\n}\n']]


def test_an_unclosed_comment_is_closed():
    got = one("applyFix", "docCodeFixes", "int x;\n/* note\n", "c", "    ")
    assert got[0]["fixes"] == [["Close the comment", "int x;\n/* note */\n"]]


def test_json_fixes():
    got = run([
        ["applyJson", '{\n  "a": 1,\n  "b": 2,\n}\n', "  "],
        ["applyJson", '{\n  "a": 1\n  "b": 2\n}\n', "  "],
        ["applyJson", "{\n  a: 1\n}", "  "],
        ["applyJson", "{\n  'a': 1\n}", "  "],
        ["applyJson", '{\n  "a": {\n    "b": 1\n', "  "],
    ])
    assert got[0] == [["Remove the trailing comma", '{\n  "a": 1,\n  "b": 2\n}\n']]
    assert got[1] == [["Add the missing comma", '{\n  "a": 1,\n  "b": 2\n}\n']]
    assert got[2] == [["Put the name in double quotes", '{\n  "a": 1\n}']]
    assert got[3] == [["Use double quotes", '{\n  "a": 1\n}']]
    assert got[4] == [["Close what is still open", '{\n  "a": {\n    "b": 1\n  }\n}\n']]


def test_python_missing_colon():
    got = run([
        ["applyColon", "def f(x)\n    return x  # hi\n", 1],
        ["applyColon", "if ready  # check\n    go()\n", 1],
        ["applyColon", "x = f(1)\n", 1],
        ["applyColon", "def f(x):\n    pass\n", 1],
    ])
    assert got[0] == ["Add the missing colon", "def f(x):\n    return x  # hi\n"]
    assert got[1] == ["Add the missing colon", "if ready:  # check\n    go()\n"]
    #: Not a line that opens a block, or one that already has its colon.
    assert got[2] is None
    assert got[3] is None


def test_mixed_indentation_is_a_note_with_two_fixes():
    got = run([
        ["applyFix", "docIndentMixFixes", "def f():\n    a = 1\n\tb = 2\n\tc = 3\n", "    ", 4, "py"],
        ["applyFix", "docIndentMixFixes", "func f() {\n\ta()\n    b()\n}\n", "\t", 4, "go"],
        #: A file indented wholly with tabs is a choice, not a mistake.
        ["applyFix", "docIndentMixFixes", "int f() {\n\ta();\n}\n", "    ", 4, "c"],
        #: Go's own formatter aligns with spaces after the tabs.
        ["applyFix", "docIndentMixFixes", "func f() {\n\ta := 1\n\t\t  // aligned\n}\n", "\t", 4, "go"],
    ])
    assert got[0][0]["severity"] == "info"
    assert got[0][0]["fixes"] == [
        ["Convert this line to spaces", "def f():\n    a = 1\n    b = 2\n\tc = 3\n"],
        ["Convert every line to spaces", "def f():\n    a = 1\n    b = 2\n    c = 3\n"],
    ]
    assert got[1][0]["fixes"] == [["Convert this line to tabs", "func f() {\n\ta()\n\tb()\n}\n"]]
    assert got[2] == []
    assert got[3] == []


def test_every_message_is_sentence_case_with_no_exclamation():
    texts = [
        "int main() {\n  foo(a;\n}\n",
        "int f() {\n    return x];\n}\n",
        'int main() {\n    printf("hi);\n}\n',
        "int x;\n/* note\n",
    ]
    for diags in run([["applyFix", "docCodeFixes", t, "c", "    "] for t in texts]):
        for d in diags:
            assert d["message"][0].isupper() and "!" not in d["message"]
            for name, _ in d["fixes"]:
                assert name[0].isupper() and "!" not in name


# --- the wiring, which the suite can only read -------------------------------


def _source() -> str:
    return _documents_text()


def _function(name: str) -> str:
    text = _source()
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_pairs_and_the_indent_service_are_mounted_for_code_only():
    """`docCodeEditing` is reached only through `docCodeTools`, which returns
    nothing for prose, plain text, CSV and Plain view: a `"` typed into a
    markdown document is a quotation mark, not the start of a string."""
    tools = _function("docCodeTools")
    assert "docCodeEditing(CM, type)" in tools
    assert "type.previewable" in tools and 'docView === "plain"' in tools
    editing = _function("docCodeEditing")
    for piece in ("closeBrackets()", "closeBracketsKeymap", "indentUnit.of(type.indent",
                  "indentService.of(docCodeIndentAt)"):
        assert piece in editing, piece
    #: Mounted nowhere else, so there is one place pairs are decided.
    assert _source().count("closeBrackets()") == 1


def test_tab_leaves_the_caret_after_the_indent_it_inserts():
    """The engine's `replaceRange` maps a caret at the insertion point to
    before it; the plain-Tab branch has to put it after, or the next key
    lands on the wrong side of the indent (measured 2026-09-23)."""
    body = _function("indentDocSelection")
    branch = body[body.index("if (!multiline && !outdent) {"):]
    branch = branch[: branch.index("return;")]
    assert "setSelectionRange(at + unit.length, at + unit.length)" in branch


def test_format_has_one_command_behind_every_door():
    """The dock button, Shift+Alt+F, the palette row and the Alt+Enter menu
    all reach `docFormatCode`; none carries a copy of it."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    button = html[html.index('id="doc-code-format"') - 20 : html.index('id="doc-code-format"') + 400]
    assert 'class="ghost small hidden"' in button and "Shift+Alt+F" in button
    source = _source()
    assert '$("doc-code-format").addEventListener("click"' in source
    assert '{ key: "Shift-Alt-f", run: () => { docFormatCode("auto"); return true; } }' in _function("docCodeEditing")
    table = source[source.index("// DOC-COMMANDS-BEGIN") : source.index("// DOC-COMMANDS-END")]
    assert 'keys: "Shift+Alt+F",\n    code: true, run: () => docRunControl("doc-code-format"' in table
    assert "!command.code || code" in _function("docPaletteCommands")
    #: The button is for code types only, swapped with the markdown strip.
    assert '$("doc-code-format")?.classList.toggle("hidden", type.previewable' in _function("syncDocFileType")


def test_format_is_one_undo_step_and_refuses_what_does_not_parse():
    body = _function("docFormatCode")
    assert "isolateHistory.of(\"full\")" in body
    assert "docFormatTreeRefusal(CM, state, type.ext)" in body
    assert "docFormatRemoteRefusal(type.ext, text)" in body
    #: The round trip to the server can outlast a keystroke.
    #: Spelled `docStr(...)` since 7add0bf (the text is joined once per
    #: version); the guard is the same, the test named the old spelling.
    assert "docStr(view.state.doc) !== text" in body


def test_quick_fixes_are_recomputed_when_chosen_and_opened_by_the_recipe():
    """A fix carries which check, which problem and which fix, never offsets:
    it is asked for again of the text as it is when chosen. The menu is the
    app's menu-at-a-point recipe, and the chord is not Ctrl+., which the
    shortcut registry gives to stopping an answer."""
    source = _source()
    actions = _function("docCodeActions")
    assert "docApplyCodeFix(view, source, d.key, fix.name, from)" in actions
    assert "d.edits" not in actions and "fix.edits" not in actions
    assert "docCodeFixNow(view, source, key, name, from)" in _function("docApplyCodeFix")
    menu = _function("docOpenCodeFixes")
    assert "openMenuAtPoint(items, \"Quick fixes\"" in menu
    editing = _function("docCodeEditing")
    assert '{ key: "Alt-Enter", run: () => docOpenCodeFixes() }' in editing
    assert "Mod-." not in editing and "Ctrl-." not in editing
    assert 'stopAI: { keys: "Ctrl+."' in app_js_text()
    #: Python's colon fix matches the server's capitalised message.
    assert "/expected ':'/i.test(d.message)" in _function("docCodeLintSource")
    table = source[source.index("// DOC-COMMANDS-BEGIN") : source.index("// DOC-COMMANDS-END")]
    assert 'keys: "Alt+Enter",\n    code: true, run: () => docOpenCodeFixes()' in table
