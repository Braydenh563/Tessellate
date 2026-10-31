"""Code as documents (INBOX 788; DOCUMENTS_PLAN "Placed from INBOX,
2026-10-10 (code as documents)").

The owner: "can you add code templates as document templates as well??",
"maybe even add a code modules library like with the whiteboard and
mindmap??" and "a way to better interact with the ai as a coding asistant
like in vs code??". These hold the templates (each one valid in its own
language, each opening as its own file type), the snippets library and the
assistant panel's contracts. The UI itself is measured by
`scratchpad/ui-sweeps/codedocs.js` at 1440 and 390.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from tessellate.core import filetypes
from tests._app_js import with_pieces

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
NODE = shutil.which("node") or "/opt/node22/bin/node"


def _templates() -> list[dict]:
    """DOC_TEMPLATES, evaluated by node, each filled as the button fills it."""
    source = (JS / "documents.js").read_text(encoding="utf-8")
    start = source.index("const DOC_TEMPLATES = [")
    end = source.index("\n];\n", start) + 4
    fill_start = source.index("function docTemplateFill(")
    fill_end = source.index("\n}\n", fill_start) + 3
    script = (
        "const docNextName = () => 'Untitled document 1';\n"
        + source[start:end]
        + source[fill_start:fill_end]
        + "console.log(JSON.stringify(DOC_TEMPLATES.map((t) => ({...t, filled: docTemplateFill(t)}))));"
    )
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True, timeout=30)
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def templates() -> list[dict]:
    if not Path(NODE).exists():
        pytest.skip("node is not installed")
    return _templates()


def _code(templates: list[dict], template_id: str) -> str:
    return next(t for t in templates if t["id"] == template_id)["filled"]["content"]


def test_every_language_the_brief_names_has_a_code_template(templates):
    code = {t["id"]: t for t in templates if t.get("group") == "code"}
    assert set(code) >= {"py-script", "py-cli", "fastapi", "js-module", "html-page", "sql-schema", "readme", "notebook", "p5"}
    for template in code.values():
        filled = template["filled"]
        assert "{{" not in filled["content"] and "{{" not in filled["title"], template["id"]
        kind = filled.get("file_type", filetypes.DEFAULT_FILE_TYPE)
        #: The type is one the server keeps as given, so the document opens in
        #: the code view of that language rather than falling back to Markdown.
        assert filetypes.normalise(kind) == kind, template["id"]
    #: Writing first, then Code: the gallery's group heads change once.
    groups = [t.get("group") or "writing" for t in templates]
    assert groups == sorted(groups, key=lambda g: g == "code")


@pytest.mark.parametrize("template_id", ["py-script", "py-cli", "fastapi", "notebook"])
def test_the_python_templates_compile(templates, template_id):
    compile(_code(templates, template_id), template_id, "exec")


def test_the_python_script_and_the_cli_run_as_written(templates, capsys):
    script = _code(templates, "py-script")
    namespace: dict = {"__name__": "__main__"}
    exec(compile(script, "py-script", "exec"), namespace)  # noqa: S102 - our own template
    namespace["test_greet"]()
    cli: dict = {"__name__": "__main__"}
    exec(compile(_code(templates, "py-cli"), "py-cli", "exec"), cli)  # noqa: S102
    assert capsys.readouterr().out.count("Hello, Ada") == 2


def test_the_sql_template_runs_in_sqlite(templates):
    db = sqlite3.connect(":memory:")
    db.executescript(_code(templates, "sql-schema"))
    rows = db.execute(
        "SELECT authors.name, books.title FROM books JOIN authors ON authors.id = books.author_id ORDER BY published"
    ).fetchall()
    assert rows == [("Italo Calvino", "Invisible Cities"), ("Ursula K. Le Guin", "The Dispossessed")]


def test_the_javascript_template_passes_its_own_tests(templates):
    if not Path(NODE).exists():
        pytest.skip("node is not installed")
    harness = """
const results = [];
const describe = (name, fn) => fn();
const it = (name, fn) => { fn(); results.push(name); };
const expect = (a) => ({ toBe: (b) => { if (a !== b) throw new Error(`${a} !== ${b}`); } });
"""
    script = harness + _code(templates, "js-module") + "\nconsole.log(results.length);"
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True, timeout=30)
    assert out.stdout.strip() == "2"


def test_the_html_template_is_one_page_with_its_title_filled(templates):
    page = _code(templates, "html-page")
    assert page.startswith("<!doctype html>") and page.count("<title>") == 1
    assert "`Clicked ${clicks} times`" in page


def test_a_code_file_uses_the_panes_width_and_prose_keeps_its_measure():
    css = (ROOT / "frontend" / "css" / "09-editor.css").read_text(encoding="utf-8")
    rule = css[css.index(".doc-editor .cm-editor.doc-content-code {"):]
    rule = rule[: rule.index("}")]
    assert "max-width: min(100%, 100rem)" in rule and "margin-inline: 0" in rule
    #: The prose measure is still the `:not(.doc-content-code)` rule's.
    assert ".doc-editor .cm-editor:not(.doc-content-code) {\n    max-width: calc(var(--doc-measure)" in css


# --- the snippets library (step 2) ---------------------------------------------


def _snippet(client, name="Read a file", language="py", code="with open(path) as f:\n    text = f.read()\n", tags=("io",)):
    response = client.post("/code-snippets", json={"name": name, "language": language, "code": code, "tags": list(tags)})
    assert response.status_code == 201, response.text
    return response.json()


def test_a_snippet_saves_lists_by_language_and_tag_and_searches(client):
    first = _snippet(client)
    _snippet(client, name="Fetch JSON", language="mjs", code="const data = await (await fetch(url)).json();\n", tags=("http", "IO"))
    assert first["kind"] == "snippet" and first["payload"] == {"language": "py", "code": "with open(path) as f:\n    text = f.read()\n"}
    everything = client.get("/code-snippets").json()
    assert [i["name"] for i in everything["items"]] == ["Fetch JSON", "Read a file"]
    #: The language is normalised the way a document's type is.
    assert [i["name"] for i in client.get("/code-snippets", params={"language": "js"}).json()["items"]] == ["Fetch JSON"]
    assert [i["name"] for i in client.get("/code-snippets", params={"q": "io"}).json()["items"]] == ["Fetch JSON", "Read a file"]
    assert [i["name"] for i in client.get("/code-snippets", params={"q": "http fetch"}).json()["items"]] == ["Fetch JSON"]


def test_a_snippet_deletes_into_the_bin_and_its_undo_restores_it(client):
    snippet = _snippet(client)
    deleted = client.delete(f"/board-library/{snippet['id']}")
    assert deleted.status_code == 200
    assert client.get("/code-snippets").json()["items"] == []
    restored = client.post(f"/board-library/{snippet['id']}/restore")
    assert restored.status_code == 200
    assert [i["id"] for i in client.get("/code-snippets").json()["items"]] == [snippet["id"]]


def test_a_snippet_renames_and_retags_and_is_refused_empty(client):
    snippet = _snippet(client)
    renamed = client.put(f"/code-snippets/{snippet['id']}", json={"name": "Read text", "tags": ["Files", "files"]}).json()
    assert renamed["name"] == "Read text" and renamed["tags"] == ["files"] and renamed["payload"]["code"].startswith("with open")
    blank = client.post("/code-snippets", json={"name": "Blank", "code": "   \n"})
    missing = client.put("/code-snippets/999999", json={"name": "x"})
    assert blank.status_code == 422 and missing.status_code == 404


def test_the_boards_library_leaves_snippets_out(client):
    snippet = _snippet(client)
    board = client.get("/board-library").json()
    assert snippet["id"] not in [i["id"] for i in board["items"]]
    assert [i["id"] for i in client.get("/board-library", params={"kind": "snippet"}).json()["items"]] == [snippet["id"]]
    exported = client.get("/board-library/export").json()
    assert all(i["kind"] != "snippet" for i in exported["items"])


def test_the_code_panel_is_lazy_and_its_ways_in_load_it():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    assert 'src="/js/documents-codekit.js' not in index, "lazy: never a boot script"
    assert 'lazyScript("/js/documents-codekit.js")' in docs
    assert 'id="doc-code-snippets-open"' in index and 'data-side="snippets"' in index
    #: The Assistant is a code file's: its button and tab go for prose. The
    #: panel itself no longer does: prose gets the text sections in it
    #: (INBOX 904 B18, tests/test_doc_sections.py), so its intent moved.
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert "#tab-documents:not(.doc-is-code) .doc-code-only" in css
    assert ".doc-code-side)" not in css.split("#tab-documents:not(.doc-is-code)")[1].split("{")[0]
    #: On a phone the panel is the recipe's sheet, never a hand-built one.
    kit = (JS / "documents-codekit.js").read_text(encoding="utf-8")
    assert "openSheet({" in kit and "sidebar-sheet-open" not in kit


def test_every_built_in_library_snippet_is_well_formed():
    if not Path(NODE).exists():
        pytest.skip("node is not installed")
    source = (JS / "documents-codekit.js").read_text(encoding="utf-8")
    start = source.index("const DOC_KIT_LIBRARY = {")
    end = source.index("\n};\n", start) + 4
    out = subprocess.run(
        [NODE, "-e", source[start:end] + "console.log(JSON.stringify(DOC_KIT_LIBRARY));"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    library = json.loads(out.stdout)
    assert {"py", "js", "html", "css", "sql"} <= set(library)
    keys = set()
    for ext, rows in library.items():
        for keyword, name, tags, template in rows:
            assert keyword and name and isinstance(tags, list) and tags, (ext, keyword)
            #: Every `${` opens a stop the engine can close: an unclosed one
            #: would insert the rest of the template as a stop's name.
            depth = 0
            for i, ch in enumerate(template):
                if template.startswith("${", i):
                    depth += 1
                elif ch == "}" and depth:
                    depth -= 1
            assert depth == 0, (ext, keyword)
            assert "${" in template, (ext, keyword)
            keys.add(f"{ext}:{keyword}")
    assert "py:readfile" in keys


# --- the coding assistant (step 3) ---------------------------------------------


def _code_doc(client, content="def add(a, b):\n    return a - b\n"):
    return client.post("/documents", json={"title": "maths.py", "content": content, "file_type": "py"}).json()


def test_a_fix_comes_back_as_code_to_apply_and_the_document_is_untouched(ai_client, fake_ollama):
    doc = _code_doc(ai_client)
    fake_ollama.librarian_reply = "```python\ndef add(a, b):\n    return a + b\n```\nAdd now adds."
    response = ai_client.post(
        f"/documents/{doc['id']}/code-assist",
        json={"action": "fix", "code": "def add(a, b):\n    return a - b\n", "diagnostic": "line 2: test_add failed, 1 != 3"},
    )
    body = response.json()
    assert body["kind"] == "change" and body["code"] == "def add(a, b):\n    return a + b\n"
    assert body["text"] == "Add now adds." and body["answered_by"]
    prompt = fake_ollama.chat_calls[-1][-1]["content"]
    assert "PROBLEM: line 2: test_add failed" in prompt and "return a - b" in prompt
    stored = ai_client.get(f"/documents/{doc['id']}").json()
    assert stored["content"] == "def add(a, b):\n    return a - b\n"


def test_explain_is_prose_and_tests_ask_for_the_run_panels_harness(ai_client, fake_ollama):
    doc = _code_doc(ai_client)
    fake_ollama.librarian_reply = "It subtracts, though its name says add."
    explained = ai_client.post(f"/documents/{doc['id']}/code-assist", json={"action": "explain"}).json()
    assert explained == {**explained, "kind": "answer", "code": None, "text": "It subtracts, though its name says add."}
    #: An empty `code` means the stored file.
    assert "return a - b" in fake_ollama.chat_calls[-1][-1]["content"]
    fake_ollama.librarian_reply = "```python\ndef test_add():\n    assert add(1, 2) == 3\n```"
    tests = ai_client.post(f"/documents/{doc['id']}/code-assist", json={"action": "tests"}).json()
    assert tests["kind"] == "change" and tests["code"].startswith("def test_add")
    assert "unittest.TestCase classes or plain test_ functions" in fake_ollama.chat_calls[-1][-1]["content"]


def test_with_no_model_it_says_what_needs_one(ai_client, fake_ollama, monkeypatch):
    from tessellate.ai import tool_fallback

    doc = _code_doc(ai_client)
    fake_ollama.running = False
    monkeypatch.setattr(tool_fallback, "for_tools", lambda primary: None)
    body = ai_client.post(f"/documents/{doc['id']}/code-assist", json={"action": "refactor"}).json()
    assert body["kind"] == "needs_model" and "need a model" in body["text"] and body["answered_by"] is None


def test_with_needle_a_request_picks_one_of_the_panels_tools(ai_client, fake_ollama, monkeypatch):
    from tessellate.ai import tool_fallback

    class Needle:
        def __init__(self):
            self.offered = None

        def chat_tools(self, model, messages, tools, mode=None):
            self.offered = [t["function"]["name"] for t in tools]
            return {"tool_calls": [{"name": "find_usages", "arguments": {"name": "add"}}]}

    needle = Needle()
    doc = _code_doc(ai_client)
    fake_ollama.running = False
    monkeypatch.setattr(tool_fallback, "for_tools", lambda primary: needle)
    body = ai_client.post(f"/documents/{doc['id']}/code-assist", json={"action": "ask", "question": "where is add used"}).json()
    assert body["kind"] == "tool" and body["tool"] == "find_usages" and body["args"] == {"name": "add"}
    assert body["answered_by"] == "needle (tools only)"
    assert needle.offered == ["format_code", "quick_fix", "run_tests", "run_file", "find_usages"]


def test_the_asks_that_need_a_model_say_so_and_fix_and_the_tools_do_not():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    asks = dict(re.findall(r'<button[^>]*data-assist="(\w+)"([^>]*)>', index))
    assert set(asks) == {"explain", "fix", "tests", "refactor"}
    assert all("data-needs-model" in asks[a] for a in ("explain", "tests", "refactor"))
    #: Fix falls back to the quick fix, so it is never greyed.
    assert "data-needs-model" not in asks["fix"]
    tools = re.findall(r'data-assist-tool="(\w+)"', index)
    assert tools == ["quick_fix", "format_code", "run_tests", "find_usages"]
    #: Every tool the panel offers needle is one the browser can run.
    from tessellate.ai import code_assist

    kit = (JS / "documents-codekit.js").read_text(encoding="utf-8")
    for name in code_assist.TOOL_NAMES:
        assert f"    {name}: () =>" in kit, name


def test_the_assistant_answers_404_for_a_document_that_is_not_there(ai_client):
    """The route by its literal path (tests/test_routes_named.py reads it)."""
    gone = ai_client.post("/documents/999999/code-assist", json={"action": "explain"})
    assert gone.status_code == 404


# Small fixes from the documents batch of the open ledger: one function or one
# rule per row, so each pin sits beside its reason.
def _fn(src: str, name: str) -> str:
    """The text of `function name(...) {...}` at the top level of `src`."""
    start = src.index(f"function {name}(")
    end = src.index("\n}\n", start)
    return src[start : end + 2]


def _node(prelude: str, expr: str, tmp_path: Path | None = None):
    """Run in node; with `tmp_path`, from a file, for source that says "pip"
    (conftest's `_no_test_runs_pip` reads every argument)."""
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = f"{prelude}\nprocess.stdout.write(JSON.stringify({expr}));"
    argv = [node, "-e", script]
    if tmp_path is not None:
        (tmp_path / "run.js").write_text(script, encoding="utf-8")
        argv = [node, str(tmp_path / "run.js")]
    done = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


# Row 1045: a tag-named topic's chip repeated the tag chip beside it.
NOTES_LIST = (JS / "notes-list.js").read_text(encoding="utf-8")


def test_topic_chip_is_left_off_when_a_tag_says_the_same():
    helper = _fn(NOTES_LIST, "topicRepeatsTag")
    cases = [
        ["training", ["training"]],
        ["Training", ["#training"]],
        ["machine learning", ["machine-learning"]],
        ["training", ["work"]],
        ["", ["x"]],
        ["training", None],
    ]
    got = _node(helper, f"{json.dumps(cases)}.map(([n, t]) => topicRepeatsTag(n, t))")
    assert got == [True, True, True, False, False, False]
    chip = _fn(NOTES_LIST, "noteTopicChip")
    assert re.search(r"topicRepeatsTag\(topic\.name, entry\.tags\)\) return null", chip)


# Row 1050: a misspelled place ("westen australia") was not read.
@pytest.mark.parametrize(
    ("place", "zone", "said"),
    [("westen australia", "Australia/Perth", "western australia"),
     ("queensland", "Australia/Brisbane", "queensland"),
     ("new yrok", "America/New_York", "new york"),
     ("my notes", None, None), ("wz", None, None), ("cat", None, None)],
)
def test_a_misspelled_place_is_read_as_its_nearest_name(place, zone, said):
    from tessellate.ai import utilities

    assert utilities.zone_for(place) == zone
    assert utilities.place_name_for(place) == said


def test_the_answer_names_the_place_as_read():
    from datetime import datetime, timezone

    from tessellate.ai import utilities

    out = utilities._clock("what's the time in westen australia", datetime(2026, 10, 11, tzinfo=timezone.utc))
    assert "Perth, Western Australia" in out[0][1]


# Row 1056: the Statistics charts' axis, unchecked at a 0 to 1,240 range.
ASK_CHART = (JS / "ask-chart.js").read_text(encoding="utf-8")


def test_chart_ticks_are_round_and_cover_the_top():
    prelude = _fn(ASK_CHART, "askChartTicks") + _fn(ASK_CHART, "askChartTickLabel")
    got = _node(prelude, "[3, 5, 7, 37, 100, 1240, 86000].map((m) => askChartTicks(m))")
    assert got[0] == [0, 1, 2, 3]
    assert got[5] == [0, 500, 1000, 1500]
    for top, ticks in zip([3, 5, 7, 37, 100, 1240, 86000], got):
        assert ticks[0] == 0 and ticks[-1] >= top and len(ticks) <= 5
        step = ticks[1] - ticks[0]
        assert all(b - a == step for a, b in zip(ticks, ticks[1:]))
        assert re.fullmatch(r"(1|2|5)0*", str(step)) or step == 25 * 10 ** (len(str(step)) - 2), step
    labels = _node(prelude, "[0, 500, 1500, 10000, 85000].map(askChartTickLabel)")
    #: The axis is 36 units wide at 640: four digits fit, five do not.
    assert labels == ["0", "500", "1500", "10k", "85k"]


# Row 1058: a debugger's variable showed one level, never its children.
def test_python_variables_carry_their_children():
    from tessellate.api import run_sandbox

    space: dict = {}
    exec(run_sandbox.PY_RUNNER, space)  # noqa: S102  # the runner is this repo's own text

    class Point:
        def __init__(self):
            self.x, self.y = 1, [2]

    rows = space["_mm_names"]({"xs": [1, "a", [3]], "d": {"k": 2}, "n": 5, "p": Point(), "big": list(range(60)), "e": []})
    by = {row["name"]: row for row in rows}
    assert "children" not in by["n"] and "children" not in by["e"]
    assert by["xs"]["children"] == [
        {"name": "[0]", "value": "1", "type": "int"},
        {"name": "[1]", "value": "'a'", "type": "str"},
        {"name": "[2]", "value": "[3]", "type": "list"},
    ]
    assert by["d"]["children"] == [{"name": "'k'", "value": "2", "type": "int"}]
    assert [c["name"] for c in by["p"]["children"]] == ["x", "y"]
    big = by["big"]["children"]
    assert len(big) == 51 and big[-1] == {"name": "...", "value": "10 more", "type": ""}
    #: One level down only: a child's own children are its repr.
    assert all("children" not in c for c in by["xs"]["children"])


def test_the_panel_draws_a_row_with_children_as_a_disclosure():
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    row = _fn(code, "docDebugValueRow")
    assert 'createElement("details")' in row and "cm-debug-children" in row
    assert code.count("row.children") >= 2
    theme = (JS / "documents.js").read_text(encoding="utf-8")
    assert '".cm-debug-children"' in theme


# Row 1059: breakpoints lived for the tab's life, not across a reload.
def test_breakpoints_are_kept_per_document_across_a_reload():
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    prelude = (
        "const store = {};\n"
        #: Storage goes through prefs (720f66148): its `json` and `set` over the same store.
        "const prefs = { json: (k, d) => { try { return store[k] ? JSON.parse(store[k]) : d; } catch { return d; } }, set: (k, v) => { store[k] = String(v); return true; } };\n"
        "const DOC_DEBUG = { breaks: new Map() };\n"
        + re.search(r"^const DOC_DEBUG_BREAKS_KEY = .*$", code, re.M).group(0) + "\n"
        + re.search(r"^const DOC_DEBUG_BREAKS_DOCS = .*$", code, re.M).group(0) + "\n"
        + _fn(code, "docDebugSavedBreaks") + _fn(code, "docDebugKeepBreaks")
    )
    got = _node(prelude, """(() => {
      docDebugKeepBreaks(7, [{ line: 3, cond: "" }, { line: 9, cond: "i > 2" }]);
      docDebugKeepBreaks(8, []);
      DOC_DEBUG.breaks.clear();
      const back = docDebugSavedBreaks(7);
      const none = docDebugSavedBreaks(8);
      for (let id = 100; id < 100 + DOC_DEBUG_BREAKS_DOCS + 5; id++) docDebugKeepBreaks(id, [{ line: 1, cond: "" }]);
      return { back, none, kept: Object.keys(JSON.parse(store[DOC_DEBUG_BREAKS_KEY])).length };
    })()""")
    assert got["back"] == [{"line": 3, "cond": ""}, {"line": 9, "cond": "i > 2"}]
    assert got["none"] == []
    assert got["kept"] == 100
    assert "DOC_DEBUG.breaks.get(docHistoryOwner)" not in code
    assert code.count("docDebugKeepBreaks(docHistoryOwner") == 1


# Row 1065: a console line that never ended lost the run's namespace.
def test_an_overtime_python_line_is_interrupted_not_its_worker_ended():
    from tessellate.api import run_sandbox

    page = run_sandbox.RUN_SANDBOX_PY_HTML
    assert "new Uint8Array(new SharedArrayBuffer(1))" in page
    assert 'if (d.type === "interrupt") { if (interrupt && busy && worker) interrupt[0] = 2; else stop(); return; }' in page
    assert "p.setInterruptBuffer(new Uint8Array(e.data.interrupt));" in run_sandbox._PY_WORKER
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    over = _fn(code, "docConsoleOvertime")
    assert 'docRunSend({ type: "interrupt"' in over and 'lang !== "python"' in over
    assert 'data.t === "started"' in _fn(code, "docConsoleMessage")


# Row 1066: the split's second half had no completions, lint or snippets.
def test_the_split_carries_completions_lint_and_snippets_but_one_run_panel():
    ide = (JS / "documents-ide.js").read_text(encoding="utf-8")
    tools = _fn(ide, "docIdeSplitTools")
    for part in ("CM.lint.linter(docCodeLintSource(CM)", "CM.lint.lintGutter()", "CM.autocomplete.autocompletion(",
                 "docNativeSnippets(CM, type.ext)", "docCodeEditing(CM, type)"):
        assert part in tools, part
    #: One run panel and one breakpoint lane per document: the first half's.
    assert "docRunExtension" not in tools and "docDebugExtension" not in tools
    assert "...docIdeSplitTools(CM)," in _fn(ide, "docIdeToggleSplit")


# Row 1067: Ctrl+K Ctrl+S flashed the palette open before the sheet.
def test_ctrl_k_waits_for_its_second_chord_before_the_palette():
    ide = (JS / "documents-ide.js").read_text(encoding="utf-8")
    start = ide.index("const DOC_IDE_CHORD_WAIT_MS")
    end = ide.index("}, true);", start) + len("}, true);")
    chord = ide[start:end].replace("window.addEventListener(\"keydown\",", "const onKey =", 1).replace("}, true);", "};", 1)
    prelude = """
const log = [];
const timers = [];
const docIde = { chordAt: 0, chordTimer: 0 };
const input = { value: "", dispatchEvent: () => log.push("input:" + input.value) };
const $ = (id) => (id === "palette-input" ? input : null);
const openPalette = () => { log.push("palette"); };
const docIdeOpenKeys = () => log.push("sheet");
const setTimeout = (fn) => { timers.push(fn); return timers.length; };
const clearTimeout = (n) => { if (n) timers[n - 1] = null; };
const matchesShortcut = (e, k) => (k === "Ctrl+K" ? e.ctrlKey && e.key === "k" : k === "Ctrl+S" ? e.ctrlKey && e.key === "s" : false);
const key = (k, ctrl = false) => ({ key: k, ctrlKey: ctrl, metaKey: false, altKey: false, stopped: false,
  preventDefault() { this.stopped = true; }, stopImmediatePropagation() {} });
""" + chord + """
async function run(second) {
  log.length = 0; timers.length = 0; input.value = "";
  docIdeChordStart();
  const opened = log.length;
  let ev = null;
  if (second === "wait") timers.filter(Boolean).forEach((t) => t());
  else { ev = key(second[0], second[1]); onKey(ev); }
  await new Promise((r) => globalThis.setImmediate(r));
  const left = timers.filter(Boolean).length;
  return { opened, log: [...log], stopped: ev ? ev.stopped : null, armed: docIde.chordAt, left };
}
"""
    script = prelude + (
        "(async () => { const out = { s: await run(['s', true]), esc: await run(['Escape']), "
        "letter: await run(['f']), arrow: await run(['ArrowDown']), wait: await run('wait') }; "
        "process.stdout.write(JSON.stringify(out)); })();"
    )
    done = subprocess.run([shutil.which("node") or "node", "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    got = json.loads(done.stdout)
    #: Ctrl+K alone opens nothing until the second chord or the wait.
    assert all(v["opened"] == 0 for v in got.values())
    assert got["s"]["log"] == ["sheet"] and got["s"]["stopped"] and got["s"]["left"] == 0
    assert got["esc"]["log"] == [] and got["esc"]["stopped"] and got["esc"]["left"] == 0
    assert got["letter"]["log"] == ["palette", "input:f"] and got["letter"]["stopped"]
    assert got["arrow"]["log"] == ["palette"] and not got["arrow"]["stopped"]
    assert got["wait"]["log"] == ["palette"]
    assert all(v["armed"] == 0 for v in got.values())
    assert "matchesShortcut(event, \"Ctrl+K\") && docIdeChordStart()" in _fn(ide, "docIdeKeydown")


# Row 1068: Live Text stayed on the single-page stage, so the scroll layout had none.
def test_live_text_follows_the_page_into_the_scroll_layout():
    lib = (JS / "library.js").read_text(encoding="utf-8")
    mover = _fn(lib, "ocrMoveOverlays")
    prelude = """
const made = {};
const stage = (name) => ({ name, kids: [], appendChild(el) { if (el.parentElement) el.parentElement.kids = el.parentElement.kids.filter((k) => k !== el); el.parentElement = this; this.kids.push(el); } });
const home = stage("home");
for (const id of ["ocr-select", "ocr-boxes", "ocr-live-text"]) { made[id] = { id, parentElement: null }; home.appendChild(made[id]); }
const $ = (id) => made[id] || null;
const page3 = stage("page3");
""" + mover + "\nocrMoveOverlays(page3);"
    got = _node(prelude, "{ moved: page3.kids.map((k) => k.id), left: home.kids.length }")
    #: In paint order: the marquee under the boxes, the words on top.
    assert got == {"moved": ["ocr-select", "ocr-boxes", "ocr-live-text"], "left": 0}


# Row 1069: a SQL run had no way to read a CSV document as a table.
def test_a_csv_document_the_query_names_is_a_table():
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    prelude = "\n".join(
        [
            "const DOC_SQL_CSV_ROWS = 3;",
            _fn(code, "docSqlTableName"),
            _fn(code, "docSqlCsvRows").replace("cap = DOC_SQL_CSV_ROWS + 2", "cap = 5"),
            _fn(code, "docSqlCsvTable"),
        ]
    )
    got = _node(
        prelude,
        """{
        names: ["Sales 2026.csv", "2026 data", "  .csv", "orders"].map(docSqlTableName),
        quoted: docSqlCsvRows('a,b\\r\\n"x, y","say ""hi""\\nthere"\\n\\n1,2'),
        table: docSqlCsvTable("t", "amount,amount,\\n10,9.5,\\n-3,x,\\n1,2,3\\n4,5,6"),
      }""",
    )
    assert got["names"] == ["sales_2026", "t_2026_data", "", "orders"]
    assert got["quoted"] == [["a", "b"], ["x, y", 'say "hi"\nthere'], ["1", "2"]]
    table = got["table"]
    #: Duplicate and blank headers get names; numbers stay numbers; the cap says so.
    assert table["columns"] == ["amount", "amount_2", "column_3"]
    assert table["rows"] == [[10, 9.5, ""], [-3, "x", ""], [1, 2, 3]]
    assert table["cut"] is True
    run = _fn(code, "docRunCode")
    assert 'if (type.ext === "sql")' in run and "request.tables = await docSqlCsvTables(source);" in run
    assert 'apiJson("/documents/contents?file_type=csv")' in code
    core = (JS / "run-core.js").read_text(encoding="utf-8")
    assert 'return { ...runBase(request, "sql"), lib: { js, wasm }, tables };' in core


def test_the_contents_read_narrows_to_one_file_type(client):
    client.post("/documents", json={"title": "sales.csv", "content": "a,b\n1,2", "file_type": "csv"})
    client.post("/documents", json={"title": "notes", "content": "hello", "file_type": "md"})
    rows = client.get("/documents/contents", params={"file_type": "csv"}).json()
    assert [(r["title"], r["file_type"]) for r in rows] == [("sales.csv", "csv")]
    assert len(client.get("/documents/contents").json()) == 2


# Row 1072: JSX in a .js document ran without the JSX pass.
def test_jsx_in_a_js_document_gets_the_jsx_pass_and_nothing_else(tmp_path):
    core = (JS / "run-core.js").read_text(encoding="utf-8")
    start = core.index("const RUN_JSX_MARKUP")
    hint = core[start : core.index("\n", start)]
    sucrase = (ROOT / "frontend/vendor/sucrase/sucrase.min.js").read_text(encoding="utf-8")
    prelude = "\n".join(
        [
            sucrase,
            hint,
            _fn(core, "runIsJsx"),
            "const runVendorScript = async () => SUCRASE;",
            "async " + _fn(core, "runStripTypes"),
            "const runBase = (r, kind) => ({ kind, source: String(r.source || ''), path: String(r.path || '') });",
            "async " + _fn(core, "runJsRequest"),
        ]
    )
    cases = {
        "returned": "function A() { return <div>hi</div>; }",
        "assigned": "const el = <App title='x' />;",
        "fragment": "const f = (\n  <>\n  </>\n);",
        "compare": "if (a < b && c > d) console.log(a<b);",
        "generic": "const n = count <limit ? 1 : 2;",
    }
    script = prelude + (
        "\n(async () => { const cases = " + json.dumps(cases) + "; const out = {};"
        " for (const [k, v] of Object.entries(cases)) out[k] = runIsJsx({ source: v });"
        " out.byName = runIsJsx({ source: 'x', path: 'App.jsx' });"
        " const r = await runJsRequest({ source: 'let x: number = 1;\\nconst el = <b>{x}</b>;', path: 'a.js' }).catch((e) => ({ error: e.message }));"
        " out.typed = r.error || r.source;"
        " out.ran = (await runJsRequest({ source: cases.returned })).source;"
        " process.stdout.write(JSON.stringify(out)); })();"
    )
    #: From a file: the bundle's text holds "pip", which the installer guard
    #: (conftest) refuses to see in an argument.
    path = tmp_path / "jsx.js"
    path.write_text(script, encoding="utf-8")
    done = subprocess.run([shutil.which("node") or "node", str(path)], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    got = json.loads(done.stdout)
    assert got["returned"] and got["assigned"] and got["fragment"] and got["byName"]
    assert not got["compare"] and not got["generic"]
    #: Only the JSX pass: a type annotation in a .js file is still an error.
    assert got["typed"].startswith("Could not read this as JSX")
    assert "React.createElement" in got["ran"] and "<div>" not in got["ran"]


# Row 1070: Python's standard library had no completion after a dot.
def test_the_stdlib_table_answers_after_an_imported_modules_dot():
    table = json.loads((ROOT / "frontend/vendor/python-stdlib/stdlib.json").read_text(encoding="utf-8"))
    modules = table["modules"]
    for name in ("math", "os.path", "json", "datetime", "collections", "re"):
        assert modules[name], name
    sqrt = next(r for r in modules["math"] if r[0] == "sqrt")
    assert sqrt[1] == "function" and sqrt[2].startswith("sqrt(") and sqrt[3]
    #: Small enough to fetch once, lazily (never at boot).
    assert len((ROOT / "frontend/vendor/python-stdlib/stdlib.json").read_bytes()) < 160_000
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    mods = {"math": [["pi"]], "os.path": [["join"]], "json": [["dumps"]]}
    prelude = "\n".join([f"const MODS = {json.dumps(mods)};", _fn(code, "docPyImports"), _fn(code, "docPyStdlibRows")])
    src = "import math, json as j\nfrom os import path\nfrom collections import (Counter as C)\n"
    got = _node(
        prelude,
        "{ imports: [...docPyImports(" + json.dumps(src) + ")],"
        " math: docPyStdlibRows(MODS, docPyImports(" + json.dumps(src) + "), 'math'),"
        " path: docPyStdlibRows(MODS, docPyImports(" + json.dumps(src) + "), 'path'),"
        " j: docPyStdlibRows(MODS, docPyImports(" + json.dumps(src) + "), 'j'),"
        " none: docPyStdlibRows(MODS, docPyImports(" + json.dumps(src) + "), 'random') }",
    )
    assert got["imports"] == [["math", "math"], ["j", "json"], ["path", "os.path"], ["C", "collections.Counter"]]
    assert got["math"] == [["pi"]] and got["path"] == [["join"]] and got["j"] == [["dumps"]]
    #: Not imported, not offered.
    assert got["none"] is None
    assert 'api("/vendor/python-stdlib/stdlib.json", { silent: true })' in code
    assert '["css", "html", "py"].includes(type.ext) ? docHoverDocs(CM) : []' in code


# Row 1088: a word touching a suggestion's marker was never a spelling finding.
def test_a_suggestion_marker_is_a_word_boundary_for_the_spelling_check():
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    prelude = _fn(docs, "docSpellable")
    cases = {
        "inserted": ["{++faque++}", 3, 8],
        "deleted": ["{--faque--}", 3, 8],
        "substituted": ["{~~old~>faque~~}", 8, 13],
        "comment": ["{>>faque<<}", 3, 8],
        "plus": ["a+faque", 2, 7],
        "path": ["dir/faque", 4, 9],
    }
    expr = "Object.fromEntries(Object.entries(" + json.dumps(cases) + ").map(([k, [t, s, e]]) => [k, docSpellable(t, t.slice(s, e), s, e)]))"
    got = _node(prelude, expr)
    assert got == {"inserted": True, "deleted": True, "substituted": True, "comment": True, "plus": False, "path": False}


# Row 1097: a fenced block's language was not written to Word.
def test_a_code_blocks_language_goes_to_word_and_comes_back(tmp_path):
    word = (JS / "documents-word.js").read_text(encoding="utf-8")
    start = word.index('const DOC_WORD_CODE_STYLE = "Code";')
    tables = word[start : word.index("];", word.index("const DOC_WORD_STYLE_MAP")) + 2]
    vendor = ROOT / "frontend/vendor"
    script = f"""
const vm = require("vm"), fs = require("fs");
global.window = global; global.self = global;
vm.runInThisContext(fs.readFileSync({json.dumps(str(vendor / "docx/docx.min.js"))}, "utf8"));
vm.runInThisContext(fs.readFileSync({json.dumps(str(vendor / "mammoth/mammoth.browser.min.js"))}, "utf8"));
{tables}
const D = global.docx;
(async () => {{
  const para = (style, text) => new D.Paragraph({{ style, children: [new D.TextRun({{ text }})] }});
  const doc = new D.Document({{
    styles: {{ paragraphStyles: [{{ id: "Code", name: "Code", basedOn: "Normal" }}, {{ id: "Code-py", name: "Code py", basedOn: "Code" }}] }},
    sections: [{{ children: [para("Code-py", "x = 1"), para("Code-py", "print(x)"), para("Code", "plain")] }}],
  }});
  const buf = await D.Packer.toBuffer(doc);
  const out = await global.mammoth.convertToHtml({{ arrayBuffer: buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) }}, {{ styleMap: DOC_WORD_STYLE_MAP }});
  process.stdout.write(JSON.stringify(out.value));
}})().catch((e) => {{ console.error(e); process.exit(1); }});
"""
    path = tmp_path / "word.js"
    path.write_text(script, encoding="utf-8")
    done = subprocess.run([shutil.which("node") or "node", str(path)], capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    html = json.loads(done.stdout)
    assert '<pre class="language-py">x = 1\nprint(x)</pre>' in html and "<pre>plain</pre>" in html
    assert "const lang = docWordCodeLang(el);" in word and "ctx.langs.add(lang)" in word
    #: The paste converter fences a language-named block with its language.
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    assert 'out.push("```" + lang + "\\n" + code + "\\n```");' in docs


# Row 1096: Mammoth accepted a .docx's tracked changes on the reader's behalf.
def test_a_word_file_with_tracked_changes_is_seen_before_mammoth_reads_it(tmp_path):
    word = (JS / "documents-word.js").read_text(encoding="utf-8")
    vendor = ROOT / "frontend/vendor"
    script = f"""
const vm = require("vm"), fs = require("fs");
global.window = global; global.self = global;
vm.runInThisContext(fs.readFileSync({json.dumps(str(vendor / "docx/docx.min.js"))}, "utf8"));
async {_fn(word, "docWordHasRevisions")}
const D = global.docx;
(async () => {{
  const make = async (run) => {{
    const buf = await D.Packer.toBuffer(new D.Document({{ sections: [{{ children: [new D.Paragraph({{ children: [new D.TextRun("kept "), run] }})] }}] }}));
    return {{ arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) }};
  }};
  const out = {{
    ins: await docWordHasRevisions(await make(new D.InsertedTextRun({{ text: "new", id: 1, author: "A", date: "2026-10-11T00:00:00Z" }}))),
    del: await docWordHasRevisions(await make(new D.DeletedTextRun({{ text: "old", id: 2, author: "A", date: "2026-10-11T00:00:00Z" }}))),
    plain: await docWordHasRevisions(await make(new D.TextRun("plain"))),
    junk: await docWordHasRevisions({{ arrayBuffer: async () => new ArrayBuffer(10) }}),
  }};
  process.stdout.write(JSON.stringify(out));
}})().catch((e) => {{ console.error(e); process.exit(1); }});
"""
    path = tmp_path / "revisions.js"
    path.write_text(script, encoding="utf-8")
    done = subprocess.run([shutil.which("node") or "node", str(path)], capture_output=True, text=True, timeout=120, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout) == {"ins": True, "del": True, "plain": False, "junk": False}
    lib = (JS / "library.js").read_text(encoding="utf-8")
    assert '!(await docWordHasRevisions(file))' in lib


# Row 1073: the Evidence checks switch was stored and shown and gated nothing.
def test_the_evidence_checks_switch_hides_the_answers_evidence_view():
    ask = (JS / "capture-ask.js").read_text(encoding="utf-8")
    prelude = "\n".join(
        [
            "let evidenceSwitchLoad = null; let evidenceChecksKnown = null; let calls = 0; let reply = { evidence_checks: false };",
            "const apiJson = async () => { calls += 1; return reply; };",
            _fn(ask, "evidenceChecksOn"),
            _fn(ask, "evidenceSwitchReset"),
        ]
    )
    script = prelude + (
        "\n(async () => { const off = await evidenceChecksOn(); const known = evidenceChecksKnown; await evidenceChecksOn();"
        " const once = calls; reply = { evidence_checks: true }; evidenceSwitchReset(); const on = await evidenceChecksOn();"
        " process.stdout.write(JSON.stringify({ off, known, once, on, calls })); })();"
    )
    done = subprocess.run([shutil.which("node") or "node", "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {"off": False, "known": False, "once": 1, "on": True, "calls": 2}
    assert 'foot.classList.toggle("hidden", evidenceChecksKnown === false);' in ask
    settings = with_pieces("settings.js")
    assert 'if (typeof evidenceSwitchReset === "function") evidenceSwitchReset();' in settings


# Rows 1130 and 1132: the writing side and the reading grammar decided apart
# what a mark means. One table of marks; each written mark must read back.
def _const_block(src: str, name: str) -> str:
    start = src.index(f"const {name} =")
    end = src.index(";\n", start)
    return src[start : end + 1]


def test_every_written_inline_mark_reads_back_through_inline_md():
    marks = _const_block(NOTES_LIST, "MD_INLINE_MARKS")
    reader = _const_block(NOTES_LIST, "INLINE_MD")
    got = _node(
        marks + "\n" + reader,
        "Object.entries(MD_INLINE_MARKS).map(([k, w]) => {"
        " const text = w + 'word' + w; const m = new RegExp(INLINE_MD.source).exec(text);"
        " return [k, Boolean(m && m[0] === text)]; })",
    )
    assert got and all(ok for _, ok in got), got
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    actions = docs[docs.index("const MD_ACTIONS = {") :]
    for name, _ in got:
        assert re.search(rf"\n  {name}: \{{ wrap: MD_INLINE_MARKS\.{name},", actions), name


# Row 1114: the widget audit found the Dashboard's open-questions line printing
# a question's markdown ("**why**") where the Questions view shows `display`.
def test_the_dashboard_question_line_shows_the_plain_words():
    dash = with_pieces("dashboard.js")
    assert "oldest.display || oldest.text" in dash


# Row 1119: the "/" menu's Flowchart inserts a starter the Live view draws.
def test_the_flowchart_starter_is_one_the_live_view_can_draw(tmp_path):
    editor = (JS / "editor.js").read_text(encoding="utf-8")
    row = re.search(r'add\(\{ id: "flowchart".*?run: \(t\) => editorBlock\(t, "```mermaid\\n(.*?)\\n```"', editor)
    assert row, "the Flowchart row has moved"
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    start = docs.index("const MERMAID_")
    end = docs.index("\n}\n", docs.index("function mermaidFlowParse(")) + 2
    helpers = docs[start:end]
    source = row.group(1).replace("\\n", "\n")
    graph = _node(helpers, f"mermaidFlowParse({json.dumps(source)})", tmp_path)
    assert graph and len(graph["nodes"]) == 2, graph


# Row 1139: p5.js names in a sketch, each one the vendored bundle has.
def test_p5_completions_are_names_the_vendored_p5_has():
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    table = code[code.index("const DOC_P5_NAMES = [") : code.index("];", code.index("const DOC_P5_NAMES = ["))]
    names = re.findall(r'\["(\w+)", "', table)
    assert len(names) > 60
    bundle = (ROOT / "frontend/vendor/p5.min.js").read_text(encoding="utf-8")
    missing = [n for n in names if not re.search(rf"\b{n}\b", bundle)]
    assert not missing, missing
    snippets = _fn(code, "docNativeSnippets")
    assert "docP5Source()" in snippets


# Row 1109: Help puts a group's best match first while searching.
def test_help_search_orders_each_group_by_its_match():
    find = (JS / "settings-find.js").read_text(encoding="utf-8")
    body = _fn(find, "helpApplySearch")
    assert "tiers.get(b) - tiers.get(a)" in body and "a._helpAt - b._helpAt" in body


# Row 1095: a document import and a meeting summary are listed while they run.
def test_long_request_work_registers_with_the_activity_list():
    docs = (ROOT / "src/tessellate/api/routes_documents.py").read_text(encoding="utf-8")
    assert re.search(r'with activity\.track\("import", .*\n\s+viewed = docview\.extract\(', docs)
    meetings = (ROOT / "src/tessellate/api/routes_meetings.py").read_text(encoding="utf-8")
    assert re.search(r'with activity\.track\("generation", "Summarising a meeting".*\n\s+written = meeting_summary', meetings)


# Row 1101: clip.html and capture.html are served with hashed stamps.
@pytest.mark.parametrize("page", ["clip.html", "capture.html"])
def test_the_clipper_and_capture_pages_get_hashed_stamps(client, page):
    got = client.get(f"/{page}")
    assert got.status_code == 200 and got.headers["cache-control"] == "no-cache"
    stamps = re.findall(r'/(?:css|js)/[\w.-]+\?v=([\w.-]+)"', got.text)
    assert stamps and all("-" in stamp for stamp in stamps), stamps


# Row 1108: a sweep can block the service worker so its routes see every request.
def test_the_sweep_boot_passes_service_workers_through():
    lib = (ROOT / "scratchpad/ui-sweeps/lib.js").read_text(encoding="utf-8")
    assert "'serviceWorkers'" in lib[lib.index("const CTX_OPTS") : lib.index("];", lib.index("const CTX_OPTS"))]


def test_a_code_file_spell_checks_comments_and_strings_only():
    """Owner 2026-10-11: identifiers and an f-string's prefix were underlined by
    the browser; the app's own check masks to comment and string nodes."""
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    # A code file takes the masked check (the D7 window applies to prose only).
    assert "if (isCode) docProseFound = docCodeSpellFindings(text);" in docs
    mask = _fn(docs, "docCodeProseMask")
    assert "[rRbBuUfF]{0,3}" in mask and "Interpolation" in mask
    assert "string|template" in mask and "comment" in mask
    spell = _fn(docs, "docCmSpellcheck")
    assert "!docFileType().previewable" in spell
    assert "docOpenSuggestFor(finding, false, point)" in docs[docs.index("DOC_HOVER_SUGGEST_MS =") :]


# Audit 1028 D8: the ASCII word regex split "café" into "caf" and "naïve" into
# "na" and "ve"; a piece next to an accented letter is never checked.
def test_a_piece_of_an_accented_word_is_not_a_spelling_finding():
    docs = (JS / "documents.js").read_text(encoding="utf-8")
    prelude = _fn(docs, "docSpellable")
    cases = {
        "cafe": ["the café was shut", 4, 7],
        "naive_tail": ["a naïve plan", 5, 7],
        "naive_head": ["a naïve plan", 2, 4],
        "plain": ["the cafe was shut", 4, 8],
    }
    expr = "Object.fromEntries(Object.entries(" + json.dumps(cases) + ").map(([k, [t, s, e]]) => [k, docSpellable(t, t.slice(s, e), s, e)]))"
    got = _node(prelude, expr)
    assert got == {"cafe": False, "naive_tail": False, "naive_head": False, "plain": True}
