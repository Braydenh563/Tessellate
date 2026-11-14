"""L-chat-13: the Activity panel moves by its header and the agent may not act unasked."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai import tools
from tessellate.ai.tools.tool_sets import ADD_TOOLS, CHANGE_TOOLS, WRITE_TOOLS

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

#: Runs activity-drag.js against a stub panel, header and storage, then replays pointer events.
RUNNER = r"""
const fs = require("fs"), vm = require("vm");
const store = {};
const listeners = {};
const style = {};
const box = { left: 20, top: 400, width: 384, height: 300 };
const head = {
  addEventListener: (type, fn) => { listeners[type] = fn; },
  setPointerCapture: () => {},
};
const panel = {
  dataset: {}, style, classList: { add() {}, remove() {} },
  querySelector: () => head,
  getBoundingClientRect: () => ({ ...box, right: box.left + box.width, bottom: box.top + box.height }),
};
const win = { innerWidth: 1000, innerHeight: 800, matchMedia: () => ({ matches: false }), addEventListener: (t, f) => { listeners["win" + t] = f; } };
const ctx = {
  window: win, $: () => panel,
  prefs: {
    json: (k, d) => (k in store ? JSON.parse(store[k]) : d),
    setJSON: (k, v) => { store[k] = JSON.stringify(v); },
    remove: (k) => { delete store[k]; },
  },
};
if (process.argv[3]) store.activityMonitorPos = process.argv[3];
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), ctx);
const target = { closest: () => null };
const out = {};
if (process.argv[2] === "drag") {
  listeners.pointerdown({ button: 0, target, clientX: 40, clientY: 420, pointerId: 1 });
  listeners.pointermove({ clientX: 5000, clientY: -5000 });
  box.left = parseInt(style.left); box.top = parseInt(style.top);
  listeners.pointerup({});
} else if (process.argv[2] === "reset") {
  listeners.dblclick({ target });
}
out.style = { ...style }; out.store = { ...store };
process.stdout.write(JSON.stringify(out));
"""


def _run(mode: str, saved: dict | None = None) -> dict:
    args = ["node", "-e", RUNNER, str(JS / "activity-drag.js"), mode]
    if saved is not None:
        args.append(json.dumps(saved))
    done = subprocess.run(args, capture_output=True, text=True, check=True, timeout=30)
    return json.loads(done.stdout)


@node
def test_drag_clamps_to_the_window_and_persists_the_spot():
    out = _run("drag")
    # Dragged far past the top right: held at the right and top edges (1000 - 384, 0).
    assert out["style"]["left"] == "616px" and out["style"]["top"] == "0px"
    assert json.loads(out["store"]["activityMonitorPos"]) == {"x": 616, "y": 0}


@node
def test_a_saved_spot_comes_back_clamped_to_a_smaller_window():
    out = _run("none", {"x": 900, "y": 790})
    assert out["style"]["left"] == "616px" and out["style"]["top"] == "500px"


@node
def test_double_click_on_the_header_clears_the_spot():
    out = _run("reset", {"x": 100, "y": 100})
    assert "activityMonitorPos" not in out["store"]
    assert out["style"]["left"] == "" and out["style"]["bottom"] == ""


def test_the_panel_loads_the_drag_module_when_it_opens():
    assert 'activityDrag: ["/js/activity-drag.js"]' in (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'ensureModule("activityDrag")' in (JS / "agent-activity.js").read_text(encoding="utf-8")


def test_help_says_how_to_move_it():
    guide = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "Drag its head to move the panel" in guide
    assert "Drag the head to move the panel" in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_agent_never_changes_removes_or_sends_unasked():
    """The owner's rule: moving about is free, anything that edits, deletes or sends waits for a yes."""
    for name in WRITE_TOOLS | CHANGE_TOOLS | ADD_TOOLS:
        assert tools.needs_confirm(name, {}, False), f"{name} must park for a Confirm card"
    for name, spec in tools.TOOLS.items():
        if spec.destructive:
            assert tools.needs_confirm(name, {}, True), f"{name} parks even in an approved run"
    for name in tools.TOOLS:
        if name not in WRITE_TOOLS:
            assert not name.startswith(("delete_", "edit_", "send_", "remove_")), f"{name} reads as a write but is not gated"
