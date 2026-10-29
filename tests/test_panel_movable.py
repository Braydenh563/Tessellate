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
// The app's storage door (prefs.js), over the same store.
ctx.prefs = { get: (k, f = "") => ctx.localStorage.getItem(k) ?? f, setJSON: (k, v) => { ctx.localStorage.setItem(k, JSON.stringify(v)); return true; } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\n;globalThis.api = { panelClampMove, panelClampSize, panelKeyDelta, panelStoreRead, panelStoreWrite, panelSnapZone, panelZoneRect, panelRestoreOn };", ctx);
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
delete store["tessellate.panels"];
a.panelStoreWrite("dock-me", { x: 1.2, y: 2, w: 500, h: 700, dock: "left" });
out.dockRead = a.panelStoreRead("dock-me");
a.panelStoreWrite("odd", { x: 0, y: 0, w: null, h: null, dock: "sideways" });
out.dockBad = a.panelStoreRead("odd");
out.zones = {};
for (const [n, x, y] of [["mid", 500, 400], ["l", 3, 400], ["r", 997, 400], ["t", 500, 2], ["b", 500, 799], ["tl", 5, 5], ["tr", 995, 5], ["bl", 5, 795], ["br", 995, 795], ["edgeIn", 24, 400], ["edgeOut", 25, 400], ["topThirdL", 200, 2], ["topThirdR", 800, 2], ["topMidEdge", 340, 2]]) out.zones[n] = a.panelSnapZone(x, y, 1000, 800);
out.rects = {};
for (const z of ["left", "right", "max", "bottom", "tl", "tr", "bl", "br"]) out.rects[z] = a.panelZoneRect(z, 1000, 800, 12);
out.noRect = a.panelZoneRect("", 1000, 800, 12);
out.safe = a.panelZoneRect("left", 1000, 800, 12, { left: 60, top: 50, right: 1000, bottom: 770 });
out.restoreDefault = a.panelRestoreOn();
store["panel-pos"] = "off";
out.restoreOff = a.panelRestoreOn();
store["panel-pos"] = "on";
out.restoreOn = a.panelRestoreOn();
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


@node
def test_snap_zones_follow_the_pointer_to_an_edge_or_corner(maths) -> None:
    z = maths["zones"]
    assert z["mid"] == ""
    assert (z["l"], z["r"], z["t"], z["b"]) == ("left", "right", "max", "bottom")
    assert (z["tl"], z["tr"], z["bl"], z["br"]) == ("tl", "tr", "bl", "br")
    # 24px is inside the zone, 25px is not
    assert z["edgeIn"] == "left" and z["edgeOut"] == ""
    # the top band is read by thirds: one gesture, one height
    assert (z["topThirdL"], z["topThirdR"], z["topMidEdge"]) == ("tl", "tr", "max")


@node
def test_zone_rects_tile_the_window_with_an_inset(maths) -> None:
    r = maths["rects"]
    # 1000 x 800, inset 12: a half is (1000 - 36) / 2 = 482 wide, a gap of 12 between
    assert r["left"] == {"left": 12, "top": 12, "width": 482, "height": 776}
    assert r["right"] == {"left": 506, "top": 12, "width": 482, "height": 776}
    assert r["max"] == {"left": 12, "top": 12, "width": 976, "height": 776}
    assert r["bottom"] == {"left": 12, "top": 406, "width": 976, "height": 382}
    assert r["tl"] == {"left": 12, "top": 12, "width": 482, "height": 382}
    assert r["br"] == {"left": 506, "top": 406, "width": 482, "height": 382}
    assert r["tr"]["left"] == 506 and r["bl"]["top"] == 406
    assert maths["noRect"] is None
    # beside a 60px rail, below a 50px bar, above a 30px status bar
    assert maths["safe"] == {"left": 72, "top": 62, "width": 452, "height": 696}


@node
def test_a_dock_is_stored_with_the_panel_and_garbage_is_dropped(maths) -> None:
    assert maths["dockRead"] == {"x": 1, "y": 2, "w": 500, "h": 700, "dock": "left"}
    assert "dock" not in maths["dockBad"]


@node
def test_panels_open_where_left_by_default_and_the_setting_turns_it_off(maths) -> None:
    assert maths["restoreDefault"] is True and maths["restoreOn"] is True
    assert maths["restoreOff"] is False


def test_the_setting_row_is_wired_like_its_neighbours() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="panel-restore-toggle"' in html and "Panels open where you left them" in html
    rows = (ROOT / "frontend" / "js" / "settings-rows.js").read_text(encoding="utf-8")
    assert '{ key: "panel-pos", id: "panel-restore-toggle", on: "on", off: "off", base: "on" }' in rows
    assert '["panel-restore-toggle", "panel-pos"]' in rows


def test_the_reset_button_and_the_snap_preview_are_recipe_shaped() -> None:
    js = SRC.read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "panel-movable-lazy.css").read_text(encoding="utf-8")
    assert 'aria-label", "Put back in the middle"' in js
    assert "dialog-head-btn" in js and "ph-arrow-counter-clockwise" in js
    assert "panel-snap-preview" in js and "pointer-events: none" in css
    assert "backdrop-filter" not in css
