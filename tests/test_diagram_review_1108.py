"""Review 1108 of the diagram builder: seven findings, each run in node where the code can be loaded.

Files load into a `vm` context with the globals they read at load time stubbed; what is stubbed is named in each test.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")

HARNESS = r"""
const vm = require("vm"), fs = require("fs");
const JS = process.argv[1];
const ctx = { diagramModel: {}, console, Promise, Math, Number, String, Set, Map, Array, JSON, RegExp, Object };
ctx.window = ctx;
vm.createContext(ctx);
const load = (file) => vm.runInContext(fs.readFileSync(JS + "/" + file, "utf8"), ctx, { filename: file });
const out = (v) => process.stdout.write(JSON.stringify(v));
"""


def run(body: str):
    proc = subprocess.run(["node", "-e", HARNESS + "\n(async () => {\n" + body + "\n})();", str(JS)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2500:]
    return json.loads(proc.stdout)


@needs_node
def test_ctrl_z_in_a_non_flowchart_pane_runs_its_own_undo_without_the_flowchart_toolbar_loaded():
    """HIGH: diagram-kinds.js called diagramModel.bar.historyKey; bar loads for flowcharts only, so a sequence .mmd threw."""
    got = run(
        """
load("diagram-kindbar.js");
const calls = [];
const key = (extra) => ({ key: "z", ctrlKey: true, altKey: false, shiftKey: false, target: { isContentEditable: false, closest: () => null },
  preventDefault: () => calls.push("prevent"), stopPropagation: () => calls.push("stop"), ...extra });
const S = { io: { undo: () => calls.push("undo"), redo: () => calls.push("redo") } };
const h = ctx.diagramModel.kindbar.historyKey;
h(S, key());
h(S, key({ key: "y" }));
h(S, key({ target: { isContentEditable: false, closest: () => ({}) } }));
out({ bar: typeof ctx.diagramModel.bar, calls });
"""
    )
    assert got["bar"] == "undefined"
    assert got["calls"] == ["prevent", "stop", "undo", "prevent", "stop", "redo"]


def test_the_other_kinds_pane_never_reaches_for_the_flowchart_toolbar():
    assert "diagramModel.bar" not in (JS / "diagram-kinds.js").read_text(encoding="utf-8")


def _embed_key(target: str, shift: bool = False) -> list:
    """The real diagram-embed.js `historyKey`, called with Ctrl+Z from `target`: the source box, a button or the title field."""
    return run(
        f"""
load("diagram-embed.js");
const calls = [];
const field = {{ isContentEditable: false, closest: () => ({{}}) }};
const targets = {{ field, button: {{ isContentEditable: false, closest: () => null }}, title: {{ isContentEditable: false, closest: () => ({{}}) }} }};
const event = {{ key: "z", ctrlKey: true, shiftKey: {json.dumps(shift)}, target: targets[{json.dumps(target)}],
  preventDefault: () => calls.push("prevent"), stopPropagation: () => calls.push("stop") }};
ctx.diagramModel.embed.historyKey(event, field, () => calls.push("flush"), {{ undo: () => calls.push("undo"), redo: () => calls.push("redo") }});
out(calls);
"""
    )


@needs_node
def test_ctrl_z_from_a_button_in_the_diagram_window_stops_before_the_apps_undo():
    """MED: Picture, List, Source, Done, Cancel and "?" sit outside the builder pane; the app's undo listens on the document."""
    assert _embed_key("button") == ["prevent", "stop", "undo"]
    assert _embed_key("button", shift=True) == ["prevent", "stop", "redo"]
    assert _embed_key("field") == ["prevent", "stop", "flush", "undo"]


@needs_node
def test_keep_on_the_tall_chart_offer_is_remembered_per_diagram_not_per_shared_preview_host():
    """MED: every diagram document draws into the one #doc-preview, so a host key turned the offer off for all of them."""
    got = run(
        """
const mk = () => { const e = { cls: new Set(), kids: [], classList: { add(c) { e.cls.add(c); }, remove(c) { e.cls.delete(c); }, contains: (c) => e.cls.has(c) },
  append(...n) { e.kids.push(...n); }, set className(v) { e.cls = new Set(v.split(" ")); }, set textContent(v) {} }; return e; };
ctx.document = { createElement: mk };
ctx.smallButton = (label, tip, run) => { const b = mk(); b.run = run; b.label = label; return b; };
load("diagram-outline.js");
const host = mk();
const pane = (key) => ({ host, io: { key }, turn: () => {}, fig: { parentElement: mk() }, note: {} });
const shown = (S) => { ctx.diagramModel.outline.offer(S, true); return Boolean(S.sideways) && !S.sideways.cls.has("hidden"); };
const a1 = pane("doc-a");
const first = shown(a1);
a1.sideways.kids.find((k) => k.label === "Keep").run();
const a2 = pane("doc-a");
const b1 = pane("doc-b");
out({ first, sameDiagramAgain: shown(a2), otherDiagram: shown(b1) });
"""
    )
    assert got == {"first": True, "sameDiagramAgain": False, "otherDiagram": True}
