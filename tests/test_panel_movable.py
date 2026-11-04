"""Every popup panel is draggable and resizable (INBOX 1427, owner 2026-10-28).

The clamp and storage maths of frontend/js/panel-movable.js run in node (the
file's top level only wires listeners when a document exists); the rest are
source checks, since the behaviour needs a pointer (measured by hand with
Playwright, numbers in the commit).
"""

from __future__ import annotations

import json
import re
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
vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\n;globalThis.api = { panelClampMove, panelClampSize, panelKeyDelta, panelStoreRead, panelStoreWrite, panelSnapZone, panelZoneRect, panelRestoreOn, panelStoreFits };", ctx);
const a = ctx.api;
const rect = { left: 300, top: 100, width: 500, height: 400 };
const out = {
  farRight: a.panelClampMove(rect, 0, 0, 5000, 0, 1000, 800, 40),
  farLeft: a.panelClampMove(rect, 0, 0, -5000, 0, 1000, 800, 40),
  up: a.panelClampMove(rect, 0, 0, 0, -5000, 1000, 800, 40),
  down: a.panelClampMove(rect, 0, 0, 0, 5000, 1000, 800, 40),
  free: a.panelClampMove(rect, 10, 20, 50, 60, 1000, 800, 40),
  underSidebar: a.panelClampMove(rect, 0, 0, -5000, 0, 1000, 800, 40, { left: 316, top: 0, right: 1000, bottom: 800 }),
  underStatus: a.panelClampMove(rect, 0, 0, 0, 5000, 1000, 800, 40, { left: 0, top: 0, right: 1000, bottom: 760 }),
  beforeDock: a.panelClampMove(rect, 0, 0, 5000, 0, 1000, 800, 40, { left: 0, top: 0, right: 600, bottom: 800 }),
  tooWide: a.panelClampMove({ left: 300, top: 100, width: 900, height: 400 }, 0, 0, -5000, 0, 1000, 800, 40, { left: 316, top: 0, right: 1000, bottom: 800 }),
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
for (const [n, x, y] of [["mid", 500, 400], ["l", 3, 400], ["r", 997, 400], ["t", 500, 2], ["b", 500, 799], ["tl", 5, 5], ["tr", 995, 5], ["bl", 5, 795], ["br", 995, 795], ["edgeIn", 48, 400], ["edgeOut", 49, 400], ["edge0", 0, 400], ["rEdge", 999, 400], ["bEdge", 500, 799], ["rBand", 951, 400], ["rOut", 950, 400], ["cornerSq", 47, 752], ["topThirdL", 200, 2], ["topThirdR", 800, 2], ["topMidEdge", 340, 2]]) out.zones[n] = a.panelSnapZone(x, y, 1000, 800);
out.rects = {};
for (const z of ["left", "right", "max", "bottom", "tl", "tr", "bl", "br"]) out.rects[z] = a.panelZoneRect(z, 1000, 800, 12);
out.noRect = a.panelZoneRect("", 1000, 800, 12);
out.safe = a.panelZoneRect("left", 1000, 800, 12, { left: 60, top: 50, right: 1000, bottom: 770 });
// INBOX 1454: an entry stored before the panel's layout changed, or one that no
// longer fits, is not applied.
a.panelStoreWrite("ocr", { x: 3, y: 4, w: 700, h: 500 }, 2);
out.verSame = a.panelStoreRead("ocr", 2);
out.verOld = a.panelStoreRead("ocr", 3);
out.verNone = a.panelStoreRead("ocr");
a.panelStoreWrite("plain", { x: 3, y: 4, w: null, h: null });
out.plainNow = a.panelStoreRead("plain", 0);
out.plainAfterBump = a.panelStoreRead("plain", 2);
a.panelStoreWrite("dockver", { x: 0, y: 0, w: 500, h: 600, dock: "left" }, 2);
out.dockVer = a.panelStoreRead("dockver", 2);
const nat = { width: 1382, height: 792 };
out.fits = {
  good: a.panelStoreFits({ x: 0, y: 0, w: 900, h: 600 }, nat, 1440, 900),
  position: a.panelStoreFits({ x: -310, y: 200, w: null, h: null }, nat, 1440, 900),
  tiny: a.panelStoreFits({ x: 40, y: 20, w: 120, h: 60 }, nat, 1440, 900),
  squashed: a.panelStoreFits({ x: 0, y: 0, w: 1340, h: 87 }, nat, 1440, 900),
  offscreen: a.panelStoreFits({ x: 5000, y: -4000, w: null, h: null }, nat, 1440, 900),
  tooBig: a.panelStoreFits({ x: 0, y: 0, w: 3000, h: 2000 }, nat, 1440, 900),
  smallNatural: a.panelStoreFits({ x: 0, y: 0, w: 200, h: 100 }, { width: 200, height: 100 }, 1440, 900),
  dockElsewhere: a.panelStoreFits({ x: 0, y: 0, w: 500, h: 700, dock: "right" }, nat, 1440, 900, "left max"),
  dockAllowed: a.panelStoreFits({ x: 0, y: 0, w: 500, h: 700, dock: "left" }, nat, 1440, 900, "left max"),
};
delete store["tessellate.panels"];
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
    # INBOX 1474: the whole panel stays in the free area (it used to park half
    # off the window, which let a panel sit under a sidebar)
    assert maths["farRight"] == {"x": 200, "y": 0}
    assert maths["farLeft"] == {"x": -300, "y": 0}
    assert maths["up"] == {"x": 0, "y": -100}
    assert maths["down"] == {"x": 0, "y": 300}
    assert maths["underSidebar"] == {"x": 16, "y": 0}
    assert maths["underStatus"] == {"x": 0, "y": 260}
    assert maths["beforeDock"] == {"x": -200, "y": 0}
    assert maths["tooWide"] == {"x": 16, "y": 0}
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


@node
def test_an_entry_from_an_older_layout_or_that_no_longer_fits_is_not_applied(maths) -> None:
    """INBOX 1454: the OCR workspace "wasn't normal" because an entry stored for
    the head wrapper (before INBOX 1448 moved the whole card) was applied to the
    card. A layout version per entry and a fit check on open are the class fix."""
    assert maths["verSame"] == {"x": 3, "y": 4, "w": 700, "h": 500}
    assert maths["verOld"] is None and maths["verNone"] is None
    assert maths["plainNow"] == {"x": 3, "y": 4, "w": None, "h": None}
    assert maths["plainAfterBump"] is None
    assert maths["dockVer"] == {"x": 0, "y": 0, "w": 500, "h": 600, "dock": "left"}
    f = maths["fits"]
    assert f["good"] is True and f["position"] is True and f["smallNatural"] is True and f["dockAllowed"] is True
    assert not any([f["tiny"], f["squashed"], f["offscreen"], f["tooBig"], f["dockElsewhere"]])


def test_a_double_click_on_the_grip_puts_the_size_back() -> None:
    js = SRC.read_text(encoding="utf-8")
    assert "function panelResetSize(" in js
    assert 'e.target.closest(".panel-grip")' in js and "panelResetSize(" in js[js.index('addEventListener("dblclick"') :]
    # the grip's own help says so, and so does the head's reset line
    assert "Double-click resets the size" in js


def test_a_press_on_a_head_keeps_the_focus_and_selects_nothing() -> None:
    js = SRC.read_text(encoding="utf-8")
    assert 'addEventListener("mousedown"' in js


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
    # 48px is inside the zone, 49px is not; the very edge (0 and the last pixel)
    # counts on every side, and the band is 48px wide on the right too
    assert z["edgeIn"] == "left" and z["edgeOut"] == ""
    assert (z["edge0"], z["rEdge"], z["bEdge"]) == ("left", "right", "bottom")
    assert (z["rBand"], z["rOut"]) == ("right", "")
    assert z["cornerSq"] == "bl"
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


def test_the_free_area_is_the_window_less_sidebars_the_status_bar_and_docked_panels() -> None:
    js = SRC.read_text(encoding="utf-8")
    body = js[js.index("function panelSafe(") : js.index("//: `data-panel-zones=")]
    assert 'aside.sidebar-panel' in body and "status-bar" in body and ".panel-movable-on" in body
    assert "panelClampMove(" in js[js.index("function panelClamp(") : js.index("function panelClamp(") + 900]


def test_a_side_dock_pushes_the_app_aside_with_one_pref_and_two_controls() -> None:
    js = SRC.read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "panel-movable-lazy.css").read_text(encoding="utf-8")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    rows = (ROOT / "frontend" / "js" / "settings-rows.js").read_text(encoding="utf-8")
    # only a left or right dock, only a panel fixed to the window, one pref
    body = js[js.index("function panelPushSide(") : js.index("function panelPushSync(")]
    assert 'zone === "left" || zone === "right"' in body and "panelPinned(panel)" in body
    assert 'prefs.get("panel-push", "on") !== "off"' in js
    assert "PANEL_PUSH_MIN" in js and "--dock-push-left" in js and "--dock-push-right" in js
    # the pages take the margins, eased with the motion token, none under reduced motion
    assert "#app-main > *" in css and "margin-inline: var(--dock-push-left, 0px) var(--dock-push-right, 0px)" in css
    assert "transition: margin-inline var(--ui-base)" in css and ':where(:root[data-motion="reduced"]) #app-main > *' in css
    # the head button and the Settings row
    assert 'push.className = "icon-only ghost small dialog-head-btn panel-push"' in js
    assert 'push.setAttribute("aria-label", "Move the app aside while docked")' in js
    assert 'id="panel-push-toggle"' in html
    assert '{ key: "panel-push", id: "panel-push-toggle", on: "on", off: "off", base: "on" }' in rows
    assert '["panel-push-toggle", "panel-push"]' in rows
    # a side the app is pushed away from is not an obstacle to the dock itself
    assert 'ignore === (west ? "left" : "right")' in js


def test_a_pinned_panel_minimises_to_a_pill_above_the_composer() -> None:
    js = SRC.read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "css" / "panel-movable-lazy.css").read_text(encoding="utf-8")
    # the button sits before Close, named for the panel
    assert 'min.className = "icon-only ghost small dialog-head-btn panel-min"' in js
    assert "close.parentElement.insertBefore(min, close)" in js
    assert 'st.min.setAttribute("aria-label", `Minimise ${label}`)' in js
    # the pill: glyph, name, a small x that closes; the button restores
    assert 'chip.className = "minimised-pill"' in js and "minimised-pill-open" in js and "minimised-pill-x" in js
    assert 'x.setAttribute("aria-label", `Close ${title}`)' in js
    # state is kept: the host is hidden, never emptied; a dialog is re-opened quietly
    assert 'host.setAttribute("data-panel-min", "")' in js and "innerHTML" not in js
    assert 'window.addEventListener("close", quiet, true)' in js
    assert 'e.key !== "Escape" || !e.shiftKey' in js
    # above the composer, else the status bar
    assert '".chat-dock"' in js and 'getElementById("status-bar")' in js
    # the recipe's look, from tokens
    assert "[data-panel-min] {\n  visibility: hidden;" in css and 'tray.setAttribute("popover", "manual")' in js
    for token in ("--radius-pill", "--card", "--border", "--shadow-md"):
        assert f"var({token})" in css
    assert "min-height: calc(var(--control-h-lg) + var(--space-4))" in css


#: INBOX 1504: a fake tree stands in for the DOM, so the stacking and clipping
#: decisions of `panelSafe` run in node. A node is `{ name, parent, style, rect,
#: order, modal, shown }`; `style` overrides the defaults below.
STACK_HARNESS = r"""
const vm = require("node:vm");
const fs = require("node:fs");
const ctx = { JSON, Math, Number, Array, Object, Element: class {}, WeakMap, Node: { DOCUMENT_POSITION_FOLLOWING: 4 } };
ctx.localStorage = { getItem: () => null, setItem: () => {} };
ctx.prefs = { get: (k, f = "") => f, setJSON: () => true };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\n;globalThis.PANEL_STATE = PANEL_STATE;", ctx);
const DEFAULTS = { position: "static", zIndex: "auto", opacity: "1", isolation: "auto", overflowX: "visible", overflowY: "visible", display: "block" };
let order = 0;
const all = [];
function node(name, parent, style = {}, rect = [0, 0, 1440, 900], opts = {}) {
  const n = { name, parentElement: parent || null, style: { ...DEFAULTS, ...style }, rect, order: order++, modal: !!opts.modal, tagName: opts.tag || "DIV", dataset: {} };
  n.contains = (o) => { for (let x = o; x; x = x.parentElement) if (x === n) return true; return false; };
  n.compareDocumentPosition = (o) => (o.order > n.order ? 4 : 2);
  n.matches = (q) => q === ":modal" && n.modal;
  n.getBoundingClientRect = () => ({ left: rect[0], top: rect[1], right: rect[2], bottom: rect[3], width: rect[2] - rect[0], height: rect[3] - rect[1] });
  n.getClientRects = () => (opts.hidden ? [] : [1]);
  n.closest = () => null;
  all.push(n);
  return n;
}
ctx.getComputedStyle = (n) => n.style;
function world(build) {
  all.length = 0;
  const root = node("html", null);
  const doc = { documentElement: root, body: node("body", root), getElementById: () => null, querySelectorAll: (q) => (q === "aside.sidebar-panel" ? all.filter((n) => n.tagName === "ASIDE") : []) };
  ctx.document = doc;
  return build(doc.body);
}
ctx.world = world; ctx.node = node;
const out = {};
// a modal dialog in the top layer, a sidebar at the left: the window is the limit
out.modal = world((body) => {
  const side = node("sidebar", body, { position: "sticky" }, [16, 60, 276, 850], { tag: "ASIDE" });
  const dlg = node("dialog", body, { position: "fixed" }, [352, 160, 1088, 730], { modal: true });
  return { safe: ctx.panelSafe(1440, 900, dlg), above: ctx.panelAbove(dlg, side) };
});
// a fixed panel with a higher z-index than the sticky sidebar draws above it
out.higher = world((body) => {
  const side = node("sidebar", body, { position: "sticky" }, [16, 60, 276, 850], { tag: "ASIDE" });
  const panel = node("panel", body, { position: "fixed", zIndex: "50" }, [352, 160, 1088, 730]);
  return { safe: ctx.panelSafe(1440, 900, panel), above: ctx.panelAbove(panel, side) };
});
// a panel under the sidebar's own z-index keeps the free area
out.lower = world((body) => {
  const side = node("sidebar", body, { position: "sticky", zIndex: "60" }, [16, 60, 276, 850], { tag: "ASIDE" });
  const panel = node("panel", body, { position: "fixed", zIndex: "50" }, [352, 160, 1088, 730]);
  return { safe: ctx.panelSafe(1440, 900, panel), above: ctx.panelAbove(panel, side) };
});
// the same z-index: the later in the document is above
out.tie = world((body) => {
  const early = node("early", body, { position: "fixed", zIndex: "5" }, [0, 0, 10, 10]);
  const side = node("sidebar", body, { position: "fixed", zIndex: "5" }, [16, 60, 276, 850], { tag: "ASIDE" });
  const panel = node("panel", body, { position: "fixed", zIndex: "5" }, [352, 160, 1088, 730]);
  return { later: ctx.panelAbove(panel, side), earlier: ctx.panelAbove(early, side) };
});
// the attach panel: absolute, in a z-index 46 dock, under a page that clips on x
// from 332; the sidebar is z-auto beside it. The clip box is the limit, not the sidebar.
out.clipped = world((body) => {
  const side = node("sidebar", body, { position: "sticky" }, [16, 60, 316, 850], { tag: "ASIDE" });
  const main = node("tab-main", body, { overflowX: "clip" }, [332, 60, 1424, 850]);
  const dock = node("dock", main, { position: "relative", zIndex: "46" }, [353, 780, 1403, 840]);
  const picker = node("picker", dock, { position: "relative" }, [362, 780, 398, 840]);
  const panel = node("panel", picker, { position: "absolute", zIndex: "45" }, [362, 300, 906, 780]);
  return { safe: ctx.panelSafe(1440, 900, panel), box: ctx.panelClipBox(panel, 1440, 900) };
});
// a box between an absolute panel and its containing block does not clip it
out.between = world((body) => {
  const cb = node("cb", body, { position: "relative" }, [100, 100, 900, 700]);
  const mid = node("mid", cb, { overflowX: "hidden", overflowY: "hidden" }, [300, 300, 400, 400]);
  const panel = node("panel", mid, { position: "absolute" }, [350, 350, 380, 380]);
  return ctx.panelClipBox(panel, 1440, 900);
});
// an in-flow panel is clipped by every ancestor that clips
out.inflow = world((body) => {
  const mid = node("mid", body, { overflowX: "hidden", overflowY: "auto" }, [300, 100, 800, 500]);
  const panel = node("panel", mid, { position: "relative" }, [350, 350, 380, 380]);
  return ctx.panelClipBox(panel, 1440, 900);
});
// a docked panel stays an obstacle to a panel under it and not to one above it
out.docked = world((body) => {
  const dock = node("dock", body, { position: "fixed", zIndex: "10" }, [0, 0, 600, 900]);
  ctx.PANEL_STATE.set(dock, { dock: "left" });
  dock.classList = { contains: () => true };
  ctx.document.querySelectorAll = (q) => (q === ".panel-movable-on" ? [dock] : []);
  const low = node("low", body, { position: "fixed", zIndex: "5" }, [700, 100, 1100, 500]);
  const high = node("high", body, { position: "fixed", zIndex: "20" }, [700, 100, 1100, 500]);
  return { low: ctx.panelSafe(1440, 900, low).left, high: ctx.panelSafe(1440, 900, high).left };
});
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def stacking() -> dict:
    out = subprocess.run(["node", "-e", STACK_HARNESS, str(SRC)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@node
def test_a_panel_drawn_above_the_sidebar_is_bounded_by_the_window(stacking) -> None:
    """INBOX 1504, "I cant drag the templates popup window to the left past the
    sidebar": a modal dialog (the top layer) and a panel with a higher z-index
    than the sidebar take the whole window; the sidebar is no obstacle."""
    full = {"left": 0, "top": 0, "right": 1440, "bottom": 900}
    assert stacking["modal"] == {"safe": full, "above": True}
    assert stacking["higher"] == {"safe": full, "above": True}


@node
def test_a_panel_that_would_go_under_the_sidebar_keeps_the_free_area(stacking) -> None:
    """INBOX 1474 stays: a panel under the sidebar's own z-index stops at its edge."""
    assert stacking["lower"]["above"] is False
    assert stacking["lower"]["safe"] == {"left": 276, "top": 0, "right": 1440, "bottom": 900}
    # the same z-index is settled by the document order
    assert stacking["tie"] == {"later": True, "earlier": False}


@node
def test_a_panel_is_bounded_by_the_box_that_clips_it(stacking) -> None:
    """Measured on the attach panel: it vanished at its page's clip edge (332),
    16px past the sidebar's (316), whatever the z-index."""
    assert stacking["clipped"]["box"] == {"left": 332, "top": 0, "right": 1424, "bottom": 900}
    assert stacking["clipped"]["safe"]["left"] == 332
    # a box between an absolute panel and its containing block never clips it
    assert stacking["between"] == {"left": 0, "top": 0, "right": 1440, "bottom": 900}
    assert stacking["inflow"] == {"left": 300, "top": 100, "right": 800, "bottom": 500}


@node
def test_a_docked_panel_is_an_obstacle_only_to_a_panel_under_it(stacking) -> None:
    assert stacking["docked"] == {"low": 600, "high": 0}


def test_the_free_area_asks_what_the_panel_draws_above() -> None:
    js = SRC.read_text(encoding="utf-8")
    body = js[js.index("function panelSafe(") : js.index("//: **Split screen**")]
    assert "panelClipBox(except" in body and "panelAbove(except, el)" in body
    # decided from the real stacking and clipping, never a list of panel ids
    assert "note-template" not in body and "note-picker" not in body


def test_the_switch_for_remembering_panels_is_findable_from_the_panel_and_the_palette() -> None:
    """INBOX 1505, the owner asked for a switch that already existed: the reset
    button in a panel's head names it, the row carries the words people use for
    it (`data-synonyms`, so "remember panel" and "panel position" find it in
    Find anything), and the Guide topic names it."""
    js = SRC.read_text(encoding="utf-8")
    assert "Settings, Appearance, Panels open where you left them, turns remembering off." in js
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    row = html[html.index('id="panel-restore-row"') : html.index('id="panel-restore-row"') + 400]
    synonyms = re.search(r'data-synonyms="([^"]*)"', row)
    assert synonyms and {"remember", "position", "size"} <= set(synonyms.group(1).split())
    from tessellate.ai import help_topics_more

    topic = next(
        e for v in vars(help_topics_more).values() if isinstance(v, (list, tuple)) for e in v
        if isinstance(e, dict) and e.get("id") == "movable-panels"
    )
    assert "Panels open where you left them" in topic["body"] and "names it" in topic["body"]
    assert {"remember panel position", "panel position"} <= set(topic["keywords"])


def test_a_focus_brought_by_a_press_adopts_after_the_press_ends():
    """The Guide E2E flake: adopting adds the grip's row, so a bottom-anchored
    sheet rose 20px between pointerdown and pointerup and the send click landed
    on the card (reproduced 6 of 6 at a 6x CPU throttle)."""
    text = (ROOT / "frontend" / "js" / "panel-movable.js").read_text(encoding="utf-8")
    focus = text.split('document.addEventListener("focusin"', 1)[1].split("}, true);", 1)[0]
    assert "if (p && press.down) press.wait.add(p);" in focus
    assert 'window.addEventListener("pointerup", adoptWaiting, true);' in text
    assert "setTimeout(() => panels.forEach(panelAdopt), 0);" in text


def test_a_dock_zone_keeps_clear_of_both_bars_whatever_the_panel_draws_above():
    # INBOX 1648: a modal panel docked left filled over the top and status bars
    # (measured 8 to 892 against bars at 44 and 863; now 52 to 855).
    src = (Path(__file__).resolve().parents[1] / "frontend/js/panel-movable.js").read_text(encoding="utf-8")
    assert 'function panelSafe(vw, vh, except, ignore = "", bars = false)' in src
    assert 'const bar = bars ? barBox("top-bar") : seen("top-bar");' in src
    assert 'const foot = bars ? barBox("status-bar") : seen("status-bar");' in src
    assert 'panelPushSide(panel, st.dock) : "", true));' in src  # panelFit
    assert "sideSafe[z] || dockSafe" in src  # the zone shown while dragging
