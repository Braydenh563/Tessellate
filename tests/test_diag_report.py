"""INBOX 1430: the diagnostics report's pure half (frontend/js/diag-report.js) and
the lag watcher's attribution (frontend/js/lag-watch.js), run in node."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const ctx = vm.createContext({ console, navigator: {}, document: { hidden: false, getElementsByTagName: () => [], addEventListener() {} }, window: {}, Error, Map, WeakMap, performance: { now: () => 0 }, setTimeout: () => 1 });
const load = (f) => vm.runInContext(fs.readFileSync(f, "utf8"), ctx);
load(process.argv[1]);
if (process.argv[2]) {
  // lag-watch needs these two; PerformanceObserver is absent so lagStart returns at once.
  vm.runInContext("var LAZY_MODULES = {}; var prefs = { get: (k, d) => d, set() {} }; var recordBrowserLog = () => {}; var api = () => Promise.resolve();", ctx);
  load(process.argv[2]);
}
const input = JSON.parse(fs.readFileSync(0, "utf8"));
console.log(JSON.stringify(vm.runInContext(input.expr, ctx)));
"""


def run(expr: str, files: tuple[str, ...] = ("diag-report.js",)):
    paths = [str(JS / f) for f in files]
    result = subprocess.run(
        ["node", "-e", HARNESS, paths[0], paths[1] if len(paths) > 1 else ""],
        input=json.dumps({"expr": expr}),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def test_the_home_folder_the_address_and_the_stamp_are_removed():
    out = run(
        r"""diagRedact("at f (http://192.168.1.4:8000/js/a.js?v=0.6.2-abc123:1:2) /home/alice/notes C:\\Users\\Bob\\x /Users/carol/y me@example.com")"""
    )
    assert "alice" not in out and "Bob" not in out and "carol" not in out
    assert "192.168" not in out and "?v=" not in out and "example.com" not in out
    assert "/js/a.js:1:2" in out and out.count("~") == 3


def test_lag_lines_with_the_same_wording_group_into_one_counted_range():
    events = [
        {"kind": "frame", "view": "notes", "ms": 220 + i * 20, "cause": f"phone-shell.js tab onclick {100 + i * 40}ms (forced layout {146 + i * 30}ms)", "input": "pointerdown button#tab", "input_ago_ms": 120, "nodes": 3100 + i}
        for i in range(8)
    ] + [{"kind": "frame", "view": "notes", "ms": 900, "cause": "no script attributed", "n": 6}, {"kind": "request", "view": "documents", "ms": 4100, "cause": "/entries/12/links"}]
    lines = run(f"diagGroupLag({json.dumps(events)})")
    joined = "\n".join(lines)
    assert "x8 frame 220-360ms [notes] phone-shell.js tab onclick 100-380ms (forced layout 146-356ms) after pointerdown button#tab" in joined
    assert "x6 frame 900ms [notes] no script attributed" in joined
    assert "x1 request 4100ms [documents] /entries/12/links" in joined
    assert len(lines) == 3


def test_a_frame_with_several_scripts_is_grouped_by_its_worst_one():
    events = [
        {"kind": "frame", "view": "notes", "ms": 600 + i, "cause": f"phone-shell.js onclick {300 + i}ms; graph.js write {50 + i}ms (forced layout 50ms); status.js done 14ms"}
        for i in range(4)
    ]
    (line,) = run(f"diagGroupLag({json.dumps(events)})")
    assert line.startswith("x4 frame 600-603ms [notes] phone-shell.js onclick 300-303ms (also graph.js, status.js)")


def test_a_control_pressed_long_before_is_not_named_as_the_trigger():
    lines = run(
        'diagGroupLag([{kind:"frame",view:"notes",ms:300,cause:"a.js f 300ms",input:"keydown input#q",input_ago_ms:9000}])'
    )
    assert "after" not in lines[0]


def test_errors_are_counted_with_a_few_redacted_frames():
    errors = [
        {"n": 14, "last": 5, "view": "documents", "message": "TypeError: x is undefined", "stack": "TypeError: x is undefined\n at f (http://h:1/js/documents.js?v=1:10:3)\n at g (/home/bob/a.js:2:2)"},
        {"n": 1, "last": 9, "view": "notes", "message": "Boom", "stack": ""},
    ]
    out = run(f"diagErrors({json.dumps(errors)}, 8, 5)")
    assert out[0].startswith("x1 [notes] Boom") and out[1].startswith("x14 [documents] TypeError")
    assert "bob" not in out[1] and "http" not in out[1] and "at f (/js/documents.js:10:3)" in out[1]
    assert len(run(f"diagErrors({json.dumps(errors)}, 1, 5)")) == 1


def _data(lag_count: int = 3, stack_lines: int = 5) -> dict:
    return {
        "now": "2026-10-28T12:00:00Z",
        "header": {"version": "0.6.2", "build": "abc", "device": "Chrome 124 on Linux", "viewport": "1280x720", "dpr": 2, "cores": 8, "memory": 8, "counts": {"notes": 312, "boards": 14, "docs": 20, "links": 1204}, "nodes": 4113, "heap": 84, "platform": "Linux", "python": "3.13", "settings": {"ai_enabled": True}, "sampler": True},
        "lag": [{"kind": "frame", "view": "notes", "ms": 300 + i, "cause": f"file{i}.js fn{i} 300ms"} for i in range(lag_count)],
        "errors": [{"n": 2, "last": i, "view": "notes", "message": f"error {i}", "stack": "\n".join(f"at frame{j} (x.js:{j}:1)" for j in range(stack_lines))} for i in range(20)],
        "server": {"slow_routes": [{"method": "GET", "route": "/entries/:id", "n": 3, "max_ms": 2400, "avg_ms": 1700, "status": 200}], "slow_queries": [{"sql": "SELECT ? FROM t", "n": 2, "max_ms": 900}], "exceptions": [], "job_failures": []},
        "snapshot": {"nodes": 4113, "wide": ["div#list 400 children"], "longest": [{"ms": 812, "kind": "frame", "cause": "documents.js docRender 812ms"}], "raf": [{"owner": "atlas-motion.js tick", "calls": 600, "ms": 1800, "avg": 3, "max": 21.5}], "heap_mb": 84, "sampler": True},
    }


def test_the_report_has_every_section_and_a_routes_table():
    text = run(f"diagBuild({json.dumps(_data())})")
    for title in ("== Tessellate diagnostics ==", "== Lag (", "== Errors in the browser", "== Slow routes", "== Slow database statements", "== Server exceptions", "== Failed jobs", "== Complexity snapshot"):
        assert title in text
    assert "Notebook: 312 notes, 14 boards, 20 documents, 1,204 links | 4,113 page elements" in text
    assert "GET /entries/:id" in text and "atlas-motion.js tick" in text


def test_the_report_fits_the_limit_however_much_there_is():
    big = _data(lag_count=900, stack_lines=40)
    text = run(f"diagBuild({json.dumps(big)})")
    assert len(text) <= 20000
    assert "== Lag" in text and "== Complexity snapshot" in text or "[trimmed" in text


def test_the_report_never_carries_text_a_person_wrote():
    data = _data()
    data["lag"][0]["cause"] = "docs.js render 300ms"
    text = run(f"diagBuild({json.dumps(data)})")
    assert "my private diary" not in text


@pytest.mark.parametrize(
    "stack,owner",
    [
        ("Error\n    at lagRafOwner (http://h/js/lag-watch.js?v=1:5:5)\n    at tick (http://h/js/atlas-motion.js?v=1:30:3)", "atlas-motion.js tick"),
        ("Error\n    at lagRafOwner (http://h/js/lag-watch.js:5:5)\n    at Object.step (http://h/js/whiteboard.js:30:3)", "whiteboard.js step"),
        ("Error\n    at http://h/js/graph.js:9:1", "graph.js"),
        ("Error", "unknown"),
    ],
)
def test_a_frame_loop_is_named_by_the_first_script_that_is_not_the_watcher(stack, owner):
    assert run(f"lagStackOwner({json.dumps(stack)})", ("diag-report.js", "lag-watch.js")) == owner


def test_errors_are_deduped_by_message_and_stack_and_the_table_is_capped():
    out = run(
        """(() => { for (let i = 0; i < 500; i++) lagNoteError("same", "at a (x.js:1:1)"); for (let i = 0; i < 200; i++) lagNoteError("m" + i, ""); return [LAG.errors.size, [...LAG.errors.values()][0].n]; })()""",
        ("diag-report.js", "lag-watch.js"),
    )
    assert out == [60, 500]


def test_a_loop_over_budget_for_three_seconds_is_reported_once():
    out = run(
        """(() => { const seen = []; globalThis.lagNote = (k, ms, c) => seen.push([k, c]);
        for (let s = 0; s < 4; s++) { LAG_RAF.bucket.set("a.js tick", { n: 60, ms: 200 }); LAG_RAF.bucket.set("b.js ok", { n: 60, ms: 2 }); lagRafClose(s * 1000); }
        return seen; })()""",
        ("diag-report.js", "lag-watch.js"),
    )
    assert out == [["raf", "a.js tick 60 calls/s, 3.3ms each (200ms of every second)"]]


def test_bare_stalls_merge_into_one_counted_report():
    out = run(
        """(() => { let t = 1000; Date.now = () => t; globalThis.document.hidden = false;
        globalThis.innerWidth = 1; globalThis.innerHeight = 1; globalThis.navigator = { hardwareConcurrency: 4 };
        for (let i = 0; i < 5; i++) { t += 600; lagNote("frame", 200 + i * 100, ""); }
        return [LAG.queue.length, LAG.queue[0].n, LAG.queue[0].ms, LAG.queue[0].cause]; })()""",
        ("diag-report.js", "lag-watch.js"),
    )
    assert out == [1, 5, 600, "no script attributed"]


API_HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const ctx = vm.createContext({ console, navigator: {}, document: { hidden: false, getElementsByTagName: () => [], addEventListener() {} }, window: {}, Error, Map, WeakMap, Set, Promise, performance: { now: () => 100 }, setTimeout: () => 1 });
vm.runInContext("var LAZY_MODULES = {}; var prefs = { get: (k, d) => d, set() {} }; var recordBrowserLog = () => {}; var api = () => Promise.resolve(); var apiJson = async (p) => ({ p });", ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
new vm.Script("async function loadNotes() { return apiJson('/entries?limit=5'); }", { filename: "http://h/js/notes-list.js?v=1" }).runInContext(ctx);
const script = { duration: 500, sourceFunctionName: "", invoker: "Response.json.then", sourceURL: "http://h/js/app.js?v=1", forcedStyleAndLayoutDuration: 400 };
vm.runInContext("loadNotes()", ctx).then((data) => {
  const hit = vm.runInContext("lagScriptCause", ctx)([script], { startTime: 50, duration: 200 });
  const miss = vm.runInContext("lagScriptCause", ctx)([script], { startTime: 500, duration: 200 });
  console.log(JSON.stringify({ data, hit, miss }));
});
"""


def test_a_long_frame_in_apijsons_continuation_names_the_path_and_the_awaiting_caller():
    """INBOX 1433: `app.js Response.json.then` named nobody. The frame line
    now ends with the paths whose answers landed in it and the first script
    outside the plumbing that asked."""
    result = subprocess.run(
        ["node", "-e", API_HARNESS, str(JS / "lag-watch.js")], capture_output=True, text=True, check=True, timeout=30
    )
    out = json.loads(result.stdout)
    assert out["data"] == {"p": "/entries?limit=5"}, "the answer passes through untouched"
    assert out["hit"].startswith("app.js Response.json.then 500ms (forced layout 400ms)")
    assert "[apiJson /entries from notes-list.js loadNotes]" in out["hit"]
    assert "apiJson" not in out["miss"], "an answer outside the frame is not blamed"
