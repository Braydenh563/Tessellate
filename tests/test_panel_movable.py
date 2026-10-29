"""Every popup panel is draggable and resizable (INBOX 1427, owner 2026-10-28).

The clamp and storage maths of frontend/js/panel-movable.js run in node (the
file's top level only wires listeners when a document exists); the rest are
source checks, since the behaviour needs a pointer (measured by hand with
Playwright, numbers in the commit).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "js" / "panel-movable.js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")

HARNESS = r"""
const vm = require("node:vm");
const fs = require("node:fs");
const store = {};
const ctx = { localStorage: { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } }, JSON, Math, Number, Array, Object, Element: class {}, WeakMap };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\n;globalThis.api = { panelClampMove, panelClampSize, panelKeyDelta, panelStoreRead, panelStoreWrite };", ctx);
const a = ctx.api;
const rect = { left: 300, top: 100, width: 500, height: 400 };
const out = {
  farRight: a.panelClampMove(rect, 0, 0, 5000, 0, 1000, 800, 40),
  farLeft: a.panelClampMove(rect, 0, 0, -5000, 0, 1000, 800, 40),
  up: a.panelClampMove(rect, 0, 0, 0, -5000, 1000, 800, 40),
  down: a.panelClampMove(rect, 0, 0, 0, 5000, 1000, 800, 40),
  free: a.panelClampMove(rect, 10, 20, 50, 60, 1000, 800, 40),
  tiny: a.panelClampSize(rect, 10, 10, 1000, 800),
  huge: a.panelClampSize(rect, 9999, 9999, 1000, 800),
  narrow: a.panelClampSize({ left: 0, top: 0, width: 200, height: 100 }, 10, 10, 1000, 800),
  keys: [a.panelKeyDelta("ArrowLeft", false), a.panelKeyDelta("ArrowDown", true), a.panelKeyDelta("a", false)],
};
a.panelStoreWrite("settings-modal", { x: 12.4, y: -3, w: 600, h: null });
out.read = a.panelStoreRead("settings-modal");
out.missing = a.panelStoreRead("nope");
a.panelStoreWrite("settings-modal", null);
out.gone = a.panelStoreRead("settings-modal");
store["tessellate.panels"] = "{not json";
out.corrupt = a.panelStoreRead("x");
store["tessellate.panels"] = JSON.stringify({ x: [1, "a", 2, 3] });
out.bad = a.panelStoreRead("x");
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def maths() -> dict:
    out = subprocess.run(["node", "-e", HARNESS, str(SRC)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@node
def test_a_head_never_leaves_the_window(maths) -> None:
    # 500 wide at left 300 in a 1000 window: 64px stays visible either side
    assert maths["farRight"] == {"x": 636, "y": 0}
    assert maths["farLeft"] == {"x": -736, "y": 0}
    assert maths["up"] == {"x": 0, "y": -100}
    assert maths["down"] == {"x": 0, "y": 660}
    assert maths["free"] == {"x": 50, "y": 60}


@node
def test_a_resize_keeps_a_minimum_and_stays_in_the_window(maths) -> None:
    assert maths["tiny"] == {"w": 280, "h": 160}
    assert maths["huge"] == {"w": 700, "h": 700}
    # a panel already smaller than the minimum is never grown past itself
    assert maths["narrow"] == {"w": 200, "h": 100}


@node
def test_keys_move_sixteen_and_shift_resizes(maths) -> None:
    left, down_shift, other = maths["keys"]
    assert left == {"dx": -16, "dy": 0, "dw": 0, "dh": 0}
    assert down_shift == {"dx": 0, "dy": 0, "dw": 0, "dh": 16}
    assert other is None


@node
def test_storage_round_trips_and_survives_garbage(maths) -> None:
    assert maths["read"] == {"x": 12, "y": -3, "w": 600, "h": None}
    assert maths["missing"] is None and maths["gone"] is None
    assert maths["corrupt"] is None and maths["bad"] is None


def test_the_module_is_lazy_and_loads_its_stylesheet() -> None:
    app = (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'panelMovable: ["/css/panel-movable-lazy.css", "/js/panel-movable.js"]' in app
    assert 'ensureModule("panelMovable")' in (ROOT / "frontend" / "js" / "drag-edge.js").read_text(encoding="utf-8")
    assert (ROOT / "frontend" / "css" / "panel-movable-lazy.css").is_file()


def test_the_module_has_no_wake_source_and_uses_the_cssom() -> None:
    js = SRC.read_text(encoding="utf-8")
    for banned in ("requestAnimationFrame", "setInterval", "MutationObserver", "ResizeObserver", 'setAttribute("style"', "innerHTML"):
        assert banned not in js, banned
    assert "setPointerCapture" in js and "style.translate" in js
    assert chr(0x2014) not in js
