"""One run protocol for every language (DOCUMENTS_PLAN 23, D1; Brief 69).

The owner: "run and preview and test more than just python". The panel under
the editor sends one request shape, `{kind, source, path, stdin, tests,
lineOffset}`, to the sandbox pages in `api/run_sandbox.py`; a language is a
row of `RUN_LANGS` in `frontend/js/run-core.js`, a lazy bundle. These hold the
contract's two ends together. The runs themselves are measured in Chromium by
`scratchpad/ui-sweeps/code-run.js`. The Python half of the runner is plain
Python, so it is exercised here under CPython rather than only read.
"""

from __future__ import annotations
from tests._app_js import frontend_text

import re
from pathlib import Path

from tessellate.api import run_sandbox

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return frontend_text(name) if name == "documents.js" else (JS / name).read_text(encoding="utf-8")


def _kinds_offered() -> set[str]:
    line = re.search(r"^const DOC_RUN_KINDS = \{([^}]*)\};", _js("documents-code.js"), re.M)
    assert line, "DOC_RUN_KINDS moved: read it from its new home"
    return set(re.findall(r"(\w+): \"", line.group(1)))


def _language_rows() -> set[str]:
    source = _js("run-core.js")
    body = source[source.index("const RUN_LANGS = {") :]
    body = body[: body.index("\n};")]
    return set(re.findall(r"^  (\w+): \{", body, re.M))


def _python_runner() -> dict:
    space: dict = {}
    exec(run_sandbox.PY_RUNNER, space)  # noqa: S102  # the runner is this repo's own text
    return space


def _run_py(code: str, **kwargs) -> list[tuple]:
    rows: list[tuple] = []
    _python_runner()["_mm_run"](code, lambda *row: rows.append(row), **kwargs)
    return rows


def test_every_language_the_toolbar_offers_has_a_row_in_the_protocol():
    offered = _kinds_offered()
    rows = _language_rows()
    assert offered and offered <= rows, f"Run shows for {sorted(offered - rows)} with no language row"


def test_the_protocol_is_a_lazy_bundle_not_boot_code():
    app = _js("app.js")
    assert 'run: ["/js/run-core.js"' in app
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'src="/js/run-core.js' not in index
    assert 'ensureModule("run")' in _js("documents-code.js")


def test_the_sandbox_page_picks_a_runner_by_kind_from_one_table():
    page = run_sandbox.RUN_SANDBOX_HTML
    assert "var RUNNERS = {" in page
    #: An unknown kind cannot name a property of Object.prototype.
    assert "Object.prototype.hasOwnProperty.call(RUNNERS, d.kind)" in page
    assert "d.source != null ? d.source" in page
    #: The line offset is clamped, so a hostile number cannot build a huge string.
    assert "Math.min(100000, Number(d.lineOffset) || 0)" in page


def test_a_python_selection_keeps_the_documents_line_numbers():
    rows = _run_py("print('hi')\nraise ValueError('no')\n", offset=9)
    assert rows[0] == ("log", "hi", 10, False)
    assert rows[-1][0] == "error" and rows[-1][2] == 11 and rows[-1][3] is True


def _node(script: str, *args: str) -> str:
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if node is None:
        pytest.skip("node runs the vendored bundle")
    done = subprocess.run([node, "-e", script, *args], capture_output=True, text=True, check=True, timeout=60)
    return done.stdout


def test_typescript_runs_with_its_types_stripped_and_its_lines_kept():
    """D4: sucrase strips the types and checks nothing; a row's line is the
    document's because the pass keeps every line where it was."""
    assert 'ts: "main"' in _js("documents-code.js")
    assert "TypeScript runs once it is compiled" not in _js("documents-code.js")
    core = _js("run-core.js")
    assert '"/vendor/sucrase/sucrase.min.js", "SUCRASE"' in core
    assert "runs without type checking" in core
    bundle = ROOT / "frontend" / "vendor" / "sucrase" / "sucrase.min.js"
    source = "interface P { x: number }\nconst p: P = { x: 2 };\nfunction id<T>(v: T): T { return v; }\nconsole.log(id<number>(p.x));\nexport const z = 1;\n"
    out = _node(
        "const fs=require('fs');const g={};"
        "new Function('self','window','globalThis',fs.readFileSync(process.argv[1],'utf8')+';self.SUCRASE=SUCRASE')(g,g,g);"
        "process.stdout.write(g.SUCRASE.transform(process.argv[2],{transforms:['typescript','imports'],production:true}).code)",
        str(bundle),
        source,
    )
    assert out.count("\n") == source.count("\n"), out
    assert "interface" not in out and ": number" not in out
    assert out.splitlines()[3] == "console.log(id(p.x));"


def test_each_vendored_run_library_is_credited_and_rebuildable():
    for folder in ("sucrase", "sqljs"):
        base = ROOT / "frontend" / "vendor" / folder
        for name in ("LICENSE", "build.sh", "package.json"):
            assert (base / name).is_file(), f"{folder}/{name}"
        assert f"`{folder}/`" in (ROOT / "docs" / "THIRD_PARTY.md").read_text(encoding="utf-8")


def test_sql_runs_against_an_in_memory_sqlite_in_the_sandbox_never_the_apps():
    """D5: sql.js arrives over postMessage (the page fetches nothing), each
    run opens a fresh in-memory database, results are capped tables."""
    page = run_sandbox.RUN_SANDBOX_HTML
    assert "var RUNNERS = { js: runJs, html: runHtml, sql: runSql" in page
    assert "lib.wasm instanceof ArrayBuffer" in page
    worker = run_sandbox._SQL_WORKER
    assert "new SQL.Database()" in worker and "db.close()" in worker
    assert "initSqlJs({ wasmBinary: d.wasm })" in worker
    assert f"var ROW_CAP = {run_sandbox.SQL_ROW_CAP};" in worker
    #: Still no network for the page that runs it.
    policy = dict(part.strip().split(" ", 1) for part in run_sandbox.RUN_SANDBOX_CSP.split(";") if part.strip())
    assert policy["connect-src"] == "'none'"
    core = _js("run-core.js")
    assert 'runVendorFetch("/vendor/sqljs/sql-wasm.wasm", "bytes")' in core
    #: Cells are text in the panel, never markup.
    table = _js("documents-code.js")
    body = table[table.index("function docRunTable") :]
    body = body[: body.index("\n}\n")]
    assert "textContent" in body and "innerHTML" not in body


def test_previews_are_runs_that_make_a_page():
    """D6: a stylesheet over a sample page, an SVG as an image (its own script
    never runs), a p5 sketch with the vendored p5.min.js handed over."""
    page = run_sandbox.RUN_SANDBOX_HTML
    assert "css: runCss, svg: runSvg, p5: runP5" in page
    assert "var CSS_SAMPLE = " in page and "<h1>" in run_sandbox.CSS_SAMPLE_HTML
    assert "<script" not in run_sandbox.CSS_SAMPLE_HTML
    #: An SVG is shown through <img>, which runs none of its script.
    svg = page[page.index("function runSvg") : page.index("function runP5")]
    assert "<img alt='' src='data:image/svg+xml" in svg and "parsererror" in svg
    #: A sketch or a stylesheet cannot close its own element early.
    assert 'code.replace(/<\\/(script)/gi' in page and 'code.replace(/<\\/(style)/gi' in page
    core = _js("run-core.js")
    assert 'runVendorFetch("/vendor/p5.min.js")' in core
    assert "function runIsP5(source)" in core
    code = _js("documents-code.js")
    assert "const DOC_RUN_LIVE_MS = 400;" in code
    assert "docRunAfterSave();" in _js("documents.js")
    #: INBOX 735: a sketch is a document option, a template of its own type.
    assert 'id: "p5", title: "p5.js sketch"' in _js("documents.js") and 'fileType: "js"' in _js("documents.js")


def test_svg_is_a_document_type_that_edits_as_xml():
    from tessellate.core import filetypes, syntaxcheck

    assert filetypes.normalise("svg") == "svg"
    assert "svg" in syntaxcheck.languages()
    assert syntaxcheck.check("svg", "<svg><circle></svg>")
    assert 'case "svg": return stream(CM.xml);' in _js("documents.js")


def test_python_tests_are_unittest_discovery_and_plain_test_functions():
    """D7: every TestCase method and every plain `test*` function, in the
    order written, each with its state, time and the line it failed on; a
    file's own `unittest.main()` guard does not fire."""
    code = (
        "import unittest\n"
        "class TestMath(unittest.TestCase):\n"
        "    def test_add(self):\n"
        "        self.assertEqual(1 + 1, 2)\n"
        "    @unittest.skip('later')\n"
        "    def test_skip(self):\n"
        "        pass\n"
        "    def test_bad(self):\n"
        "        self.assertEqual([1, 2], [1, 3])\n"
        "def test_plain():\n"
        "    assert 2 > 3\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n"
    )
    rows: list[tuple] = []
    tests: list[tuple] = []
    counts = _python_runner()["_mm_tests"](code, lambda *r: rows.append(r), lambda *t: tests.append(t))
    assert counts == {"passed": 1, "failed": 2, "skipped": 1}
    assert [(t[0], t[1]) for t in tests] == [
        ("TestMath.test_add", "pass"),
        ("TestMath.test_skip", "skip"),
        ("TestMath.test_bad", "fail"),
        ("test_plain", "fail"),
    ]
    assert tests[2][4] == 9 and "Lists differ" in tests[2][3]
    assert tests[3][4] == 11 and "assert on this line was false" in tests[3][3]
    assert rows == []


def test_the_javascript_harness_runs_describe_it_expect():
    """D7: the app's own harness, evaluated as the sandbox does, under node."""
    harness = _js("run-tests.js")
    script = (
        "const src=require('fs').readFileSync(process.argv[1],'utf8');"
        "const out=[];globalThis.self=globalThis;globalThis.postMessage=(m)=>out.push(m);"
        "eval(src+';eval(runTestHarnessSource())');"
        "describe('a',()=>{let n=0;beforeEach(()=>{n=1});"
        "it('one',()=>{expect(n).toBe(1);expect({x:[1]}).toEqual({x:[1]});expect(()=>{throw new Error('no')}).toThrow(/no/)});"
        "it('two',()=>{expect([1,2]).not.toContain(2)});it.skip('three',()=>{})});"
        "test('async',async()=>{await new Promise(r=>setTimeout(r,5));expect(0.1+0.2).toBeCloseTo(0.3)});"
        "__mmTests().then(()=>process.stdout.write(JSON.stringify(out)));"
    )
    import json

    out = json.loads(_node(script, str(JS / "run-tests.js")))
    assert [(m.get("name"), m.get("state")) for m in out[:-1]] == [
        ("a > one", "pass"), ("a > two", "fail"), ("a > three", "skip"), ("async", "pass"),
    ]
    assert "expect(received).not.toContain(expected)" in out[1]["text"]
    assert out[-1]["t"] == "tests-done" and (out[-1]["passed"], out[-1]["failed"], out[-1]["skipped"]) == (2, 1, 1)
    assert "function runTestHarness()" in harness


def test_python_input_is_answered_from_the_panels_input_box():
    """D9: `input()` takes the Input box's next line; prompt and answer are
    one row, as in a terminal; running out says where to type more."""
    rows = _run_py("n = input('Name? ')\nprint(n.upper())\ninput('More? ')\n", stdin="ada\n")
    assert rows[0] == ("log", "Name? ada", 1, False)
    assert rows[1] == ("log", "ADA", 2, False)
    assert rows[-1][0] == "error" and "Input box" in rows[-1][1] and rows[-1][2] == 3
    assert 'String(e.data.stdin || "")' in run_sandbox._PY_WORKER
    assert "stdin: String(d.stdin" in run_sandbox.RUN_SANDBOX_PY_HTML


def test_python_input_past_the_box_is_asked_mid_run_and_falls_back_without_the_buffer():
    """L-documents-33: with the page isolated the worker blocks on the panel's
    answer; Escape (None) is EOFError; without the buffer the Input box message stays."""
    asked: list[str] = []

    def ask(prompt):
        asked.append(prompt)
        return "grace"

    rows = _run_py("n = input('Name? ')\nprint(n.upper())\n", ask=ask)
    assert asked == ["Name? "] and rows[0] == ("log", "Name? grace", 1, False) and rows[1][1] == "GRACE"
    gone = _run_py("input('Name? ')\n", ask=lambda prompt: None)
    assert gone[-1][0] == "error" and "Input box" in gone[-1][1]
    none = _run_py("input('Name? ')\n")
    assert none[-1][0] == "error" and "Input box" in none[-1][1]
    assert "shared ? ask : null" in run_sandbox._PY_WORKER
    code = _js("documents-code.js")
    assert 'if (data.t === "input") {' in code and "docRunAsk(String(data.prompt" in code
    assert 'type: "reply", mmRun: id, value: { line }' in code


def test_run_selection_and_run_cell_keep_the_documents_lines():
    """D9: "Run selection" and "Run cell" over `# %%` markers send part of
    the file with its line offset; both are palette commands."""
    code = _js("documents-code.js")
    assert "function docRunSelection()" in code and "function docRunCell()" in code
    assert r"const marker = /^\s*(?:#|\/\/|--)\s*%%/;" in code
    assert "lineOffset: range ? doc.lineAt(range.from).number - 1 : 0," in code
    table = _js("documents.js")
    for command in ('id: "run-selection"', 'id: "run-cell"', 'id: "run-tests"'):
        assert command in table


def test_a_long_run_is_a_job_in_activity_and_stops_from_it(client):
    """DOCUMENTS_PLAN 25 row 9 (decision 70): the panel lists a run still
    going, `/activity` shows it with Stop, Stop reaches the tab on its next
    renewal, and the end of the run takes the row away."""
    from tessellate.core import activity

    activity.clear()
    started = client.post("/documents/run-jobs", json={"label": "Running sketch.js"}).json()
    job = started["id"]
    rows = client.get("/activity").json()["jobs"]
    row = next(r for r in rows if r["id"] == job)
    assert row["label"] == "Running sketch.js" and row["stoppable"] is True and row["kind"] == "code-run"
    first = client.post(f"/documents/run-jobs/{job}/beat").json()
    stop = client.post(f"/activity/{job}/stop").json()
    second = client.post(f"/documents/run-jobs/{job}/beat").json()
    assert first == {"stopped": False} and stop["stopped"] is True and second == {"stopped": True}
    ended = client.delete(f"/documents/run-jobs/{job}")
    after = client.get("/activity").json()["jobs"]
    gone = client.post(f"/documents/run-jobs/{job}/beat")
    assert ended.status_code == 200 and all(r["id"] != job for r in after) and gone.status_code == 404


def test_run_jobs_are_bounded_and_leased(client):
    from tessellate.api import run_sandbox as rs
    from tessellate.core import activity

    activity.clear()
    codes = [client.post("/documents/run-jobs", json={}).status_code for _ in range(rs.RUN_JOB_MAX + 1)]
    assert codes == [200] * rs.RUN_JOB_MAX + [429]
    #: A tab that went away stops renewing; its rows go when the lease runs out.
    for job in list(activity._jobs.values()):
        job.beat -= rs.RUN_JOB_LEASE_S + 1
    assert activity.count(rs.RUN_JOB_KIND) == 0
    too_long = client.post("/documents/run-jobs", json={"label": "x" * 500})
    assert too_long.status_code == 422
    activity.clear()


def test_python_without_the_runtime_shows_run_disabled_with_one_line():
    """DOCUMENTS_PLAN 25 row 2: Run stays on the toolbar for a .py document,
    disabled, and the one line beside it opens Settings, Packages."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<button id="doc-code-run-why" class="linklike small hidden" type="button"' in html
    assert ">Install Python in Settings, Packages</button>" in html
    docs = _js("documents.js")
    assert '$("doc-code-run-why")?.addEventListener("click", () => docRunOpenPythonExtra());' in docs
    assert "docRunSyncAvailability(type);" in docs
    code = _js("documents-code.js")
    body = code[code.index("async function docRunSyncAvailability") :]
    body = body[: body.index("\n}\n")]
    assert "run.disabled = !ready;" in body and 'why.classList.toggle("hidden", ready || !docRunnable(type));' in body


def test_debug_is_a_mode_of_the_protocol_for_three_languages():
    """Brief 70: Debug is a third mode beside run and test, for the rows
    that implement it, and the lowering pass is in the same lazy bundle."""
    source = _js("run-core.js")
    body = source[source.index("const RUN_LANGS = {") :]
    body = body[: body.index("\n};")]
    rows = re.split(r"^  (\w+): \{", body, flags=re.M)
    debuggable = {rows[i] for i in range(1, len(rows), 2) if "debug:" in rows[i + 1]}
    assert debuggable == {"js", "ts", "py"}
    assert 'mode === "debug" ? lang.debug' in source
    app = _js("app.js")
    assert '"/js/run-debug.js"]' in app
