"""L-whiteboard-49: one registry for the Undo-recorded map gestures.

`wbRecorded` (whiteboard-map.js) is run in node against a stand-in `wbRecordGesture` that has the real one's depth rule
(whiteboard.js: a gesture inside another runs plain). A recorded function is one binding, so a call from inside its own
wrapped file and a call through `window` both record once; a nested recorded call runs plain; helper properties survive.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

PRELUDE = r"""
let wbRecordDepth = 0;
const recorded = [];
async function wbRecordGesture(run, args = []) {
  if (wbRecordDepth > 0) return run(...args);
  recorded.push(run.name || "anon");
  wbRecordDepth += 1;
  try { return await run(...args); } finally { wbRecordDepth -= 1; }
}
"""


def _source() -> str:
    text = frontend_text("whiteboard-map.js")
    start = text.index("const wbRecordedNames")
    end = text.index("// --- maps:")
    return text[start:end]


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = PRELUDE + _source() + f"\n(async () => {{ {body} }})().then((v) => console.log(JSON.stringify(v)));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_a_call_from_inside_the_file_is_recorded_once():
    # `local` stands for a wrapped file's own call: the binding it names is the recorded one.
    out = _run(
        """
        const add = wbRecorded("add", async function add(n) { return n + 1; });
        const local = async () => add(1);
        const r = await local();
        const g = await add(2);
        return { r, g, recorded, names: [...wbRecordedNames] };
        """
    )
    assert out["r"] == 2 and out["g"] == 3
    assert out["recorded"] == ["add", "add"], "each top-level call is one gesture, local or global"
    assert out["names"] == ["add"]


def test_a_nested_recorded_call_runs_plain():
    out = _run(
        """
        const child = wbRecorded("child", async function child() { return "c"; });
        const parent = wbRecorded("parent", async function parent() { return child(); });
        const r = await parent();
        return { r, recorded };
        """
    )
    assert out == {"r": "c", "recorded": ["parent"]}


def test_helper_properties_survive():
    out = _run(
        """
        function fold() {}
        fold.open = () => "open"; fold.sync = 7;
        const f = wbRecorded("fold", fold);
        return { open: f.open(), sync: f.sync };
        """
    )
    assert out == {"open": "open", "sync": 7}


def test_the_depth_twin_makes_what_it_calls_plain():
    out = _run(
        """
        const inner = wbRecorded("inner", async function inner() { return 1; });
        const drag = wbRecordedDepth(async function drag() { return inner(); });
        const r = await drag();
        return { r, recorded, depth: wbRecordDepth, flag: drag.depthOnly };
        """
    )
    assert out == {"r": 1, "recorded": [], "depth": 0, "flag": True}


def test_whiteboard_js_skips_registered_names_and_keeps_the_depth_guard():
    text = frontend_text("whiteboard.js")
    assert re.search(r"for \(const name of WB_RECORDED\) \{\n\s*if \(wbRecordedNames\.has\(name\)\) continue;", text)
    assert "async function wbRecordGesture(run, args = []) {\n  if (wbRecordDepth > 0 || !wbState) return run(...args);" in text
