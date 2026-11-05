"""INBOX 1543: the minimise pill restores every panel that can minimise.

The owner: "I then minimised it and tried to reopen it from the minimised pill
but it didnt reopen" (the emoji panel). Reproduced with a Playwright driver
over eight panels that show `.panel-min` (`scratchpad/ui-sweeps/panelmin.js`):
the emoji picker, the same hung from a caret, and the Guide did not come back
(3 of 8), the calculator, equations, Settings, shortcuts and Appearance did.
The three close on a press outside themselves, and the pill is outside: the
press that was meant to restore them closed them first.

The class, not the panels: a press on the tray is answered at the window,
before any listener a panel keeps (`panelAdopt.trayPress`), so no panel, present or
future, can see the pill as an outside press. This runs that handler in node
with the file's own `panelRestore` replaced by a recorder.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "js" / "panel-movable.js"
SWEEP = ROOT / "scratchpad" / "ui-sweeps" / "panelmin.js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")

HARNESS = r"""
const vm = require("node:vm");
const fs = require("node:fs");
class El { constructor(name) { this.name = name; this.kids = []; } contains(n) { return n === this || this.kids.includes(n); } closest(sel) { return sel === "#panel-min-tray button" && this.tray ? this : null; } }
const ctx = { JSON, Math, Number, Array, Object, Map, Set, WeakMap, Element: El, prefs: { get: (k, f) => f } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\n;globalThis.api = { trayPress: panelAdopt.trayPress };", ctx);
const calls = [];
vm.runInContext("panelRestore = (host, close) => globalThis.__calls.push([host.name, Boolean(close)]);", Object.assign(ctx, { __calls: calls }));
const mk = (name, tray) => { const b = new El(name); b.tray = tray; b.classList = { contains: (c) => c === "minimised-pill-x" && name === "x" }; return b; };
const open = mk("open", true), x = mk("x", true), stray = mk("stray", false);
const chip = new El("chip"); chip.kids = [open, x];
const host = { name: "panel-host" };
vm.runInContext("PANEL_MIN", ctx).set(host, { chip });
const out = {};
const press = (type, target) => { let stopped = false; ctx.api.trayPress({ type, target, stopImmediatePropagation: () => { stopped = true; } }); return stopped; };
out.downStopped = press("pointerdown", open);
out.mouseStopped = press("mousedown", x);
out.afterDown = calls.length;
out.clickOpen = press("click", open);
out.clickX = press("click", x);
out.strayStopped = press("click", stray);
out.calls = calls;
console.log(JSON.stringify(out));
"""


@node
def test_a_press_on_the_pill_never_reaches_a_panel_and_the_click_restores():
    out = subprocess.run(["node", "-e", HARNESS, str(SRC)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got["downStopped"] and got["mouseStopped"], "the press must stop before a panel's outside-press listener"
    assert got["afterDown"] == 0, "only the click restores"
    assert got["clickOpen"] and got["clickX"]
    assert got["calls"] == [["panel-host", False], ["panel-host", True]], "the pill restores, its x restores and closes"
    assert not got["strayStopped"], "a press elsewhere is nobody's business"


def test_the_handler_is_on_the_window_in_the_capture_phase_and_the_chip_has_no_listener_of_its_own():
    js = SRC.read_text(encoding="utf-8")
    assert 'for (const type of ["pointerdown", "mousedown", "click"]) window.addEventListener(type, panelAdopt.trayPress, true);' in js
    chip = js[js.index("function panelChip(") : js.index("function panelMinimise(")]
    assert "addEventListener" not in chip, "a listener on the chip itself is after every document-level outside-press listener"


def test_the_driver_covers_every_kind_of_panel_head():
    sweep = SWEEP.read_text(encoding="utf-8")
    for name in ("emoji", "emoji-anchored", "calculator", "equation", "settings", "shortcuts", "appearance", "guide"):
        assert f'"{name}"' in sweep or f"{name}:" in sweep, name
