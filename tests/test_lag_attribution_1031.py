"""The lag reporter names what it can (audit 1031 PF9).

53 of 304 frame rows said "no script attributed", every one over 4 s among
them; 15 input rows said "pointerover on " with no target; the row did not say
whether the page was hidden or the CPU throttled, so an audit run read like a
real lag day. The real file runs in node on stubs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "frontend" / "js" / "lag-watch.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const sent = [];
const el = (tag, id, parent) => ({
  nodeType: 1, tagName: tag, id: id || "", className: "", parentElement: parent || null,
  closest(sel) { let n = this; while (n) { if (n.id) return n; n = n.parentElement; } return null; },
});
const root = el("SECTION", "dash-grid");
const ctx = {
  console, Math, Number, Object, Set, Map, WeakMap, JSON, Date, Error, String, Array, URL,
  LAZY_MODULES: {}, prefs: { get: (k, d) => d, set() {} }, recordBrowserLog() {},
  api: (path, o) => { sent.push(JSON.parse(o.body)); return Promise.resolve(); },
  document: { hidden: false, visibilityState: "visible", getElementsByTagName: () => [], addEventListener() {} },
  window: { devicePixelRatio: 1, lagThrottled: 4 },
  navigator: { hardwareConcurrency: 4 }, innerWidth: 1440, innerHeight: 900,
  setTimeout: () => 1, performance: {},
};
ctx.window.window = ctx.window;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const run = (code) => vm.runInContext(code, ctx);
ctx.el = el; ctx.root = root;
"""


def _node(body: str):
    run = subprocess.run(["node", "-e", HARNESS + body, str(ROOT / "frontend/js/lag-watch.js")], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_a_pointer_target_without_an_id_is_named_by_its_nearest_id():
    out = _node(
        r"""
const inner = el("BUTTON", "", el("DIV", "", root));
console.log(JSON.stringify([run("lagTarget")(inner), run("lagTarget")(null), run("lagTarget")({ nodeType: 3, parentElement: root })]));
"""
    )
    assert out[0] == "button in #dash-grid"
    assert out[1] == "an element that has gone"
    assert out[2] == "section#dash-grid"


@needs_node
def test_a_frame_no_script_owns_still_has_a_cause():
    out = _node(
        r"""
let t = 5_000_000; Date.now = () => (t += 1000);
run("lagFrame")({ duration: 5000, startTime: 100, scripts: [], renderStart: 4100, blockingDuration: 4900 });
run("lagFrame")({ duration: 900, startTime: 7000, scripts: [], renderStart: 7200, blockingDuration: 800 });
run("lagFrame")({ entryType: "longtask", duration: 5000, startTime: 9000, scripts: undefined, attribution: [{ containerType: "iframe", containerName: "preview" }] });
console.log(JSON.stringify(run("LAG.queue").map((e) => e.cause)));
"""
    )
    assert out[0] == "4000ms before rendering with no script over 5ms in it (the page loading: parsing, compiling, style and layout), then 1000ms rendering"
    assert out[1] == "rendering and painting 700ms after the scripts"
    assert out[2].startswith("page task in iframe")
    assert "no script attributed" not in " ".join(out)


@needs_node
def test_a_row_says_whether_the_page_was_throttled_or_hidden():
    out = _node(
        r"""
run("lagNote")("frame", 900, "x.js f 900ms");
const e = run("LAG.queue")[0];
console.log(JSON.stringify({ v: e.visibility, t: e.throttled }));
"""
    )
    assert out == {"v": "visible", "t": 4}


@needs_node
def test_the_same_cause_inside_a_minute_is_one_row_with_a_count():
    out = _node(
        r"""
const now = Date.now;
let t = 1_000_000; Date.now = () => t;
for (let i = 0; i < 4; i++) { run("lagNote")("frame", 300 + i, "docs.js render 300ms"); t += 700; }
const q = run("LAG.queue");
console.log(JSON.stringify([q.length, q[0].n, q[0].ms]));
"""
    )
    assert out == [1, 4, 303]


@needs_node
def test_a_dashboard_input_row_always_has_a_name_and_a_target():
    # 18 dashboard `input` rows carried no target (audit 1031 N17): the grid is rebuilt under the
    # pointer, so the event's target is gone by the time the row is written.
    out = _node(
        r"""
let t = 9_000_000; Date.now = () => (t += 1000);
const card = el("DIV", "", root);
run("lagInput")({ name: "pointerover", duration: 424, target: null, startTime: 0, processingStart: 10, processingEnd: 400 });
run("lagInput")({ name: "", duration: 400, target: card, startTime: 0, processingStart: 10, processingEnd: 300 });
console.log(JSON.stringify(run("LAG.queue").map((e) => e.cause)));
"""
    )
    assert out == ["pointerover on an element that has gone", "input on div in #dash-grid"]


@needs_node
def test_a_frame_with_no_script_over_five_ms_says_what_else_it_was():
    # INBOX 1575: "script with no source file" was never a script. A pointer event in the frame, or
    # the first seconds of the page, name the usual owners of the time; the rest is the browser's.
    out = _node(
        r"""
let t = 5_000_000; Date.now = () => (t += 1000);
run("lagFrame")({ duration: 900, startTime: 20000, scripts: [], renderStart: 20800, firstUIEventTimestamp: 20010 });
t += 600000;
run("lagFrame")({ duration: 900, startTime: 30000, scripts: [], renderStart: 30800, firstUIEventTimestamp: 0 });
console.log(JSON.stringify(run("LAG.queue").map((e) => e.cause)));
"""
    )
    assert "an input event waiting on style and layout" in out[0]
    assert "the browser's own style, layout or garbage collection" in out[1]
    assert "script with no source file" not in " ".join(out)
