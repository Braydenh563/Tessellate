"""A close from a minimised window's pill never shows the window first (CHAT_PLAN B8).

The owner, 2026-11-05: "sometimes when I close a minimised tab for a window,
the window flashes for a split second". The pill's x restored the window
(visible, a modal dialog re-opened modal) and then pressed its Close, so the
exit transition played on screen: 8 frames for the popup agent, 8 for the
Guide, 4 for Settings (measured with Playwright). The close now runs while the
window is still hidden, with no transition, and the hidden mark comes off only
once it is gone. `panelRestore` runs in node over a fake window.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from tests import _js_scope

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = _js_scope.unwrapped_copy(ROOT / "frontend" / "js" / "panel-movable.js")
CSS = ROOT / "frontend" / "css" / "panel-movable-lazy.css"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")

HARNESS = r"""
const vm = require("node:vm");
const fs = require("node:fs");
const ctx = { JSON, Math, Number, Array, Object, Element: class {}, WeakMap, Map, Date, setTimeout, clearTimeout };
ctx.localStorage = { getItem: () => null, setItem: () => {} };
ctx.prefs = { get: (k, f = "") => f, setJSON: () => true };
ctx.window = { addEventListener() {}, removeEventListener() {} };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\n;globalThis.PANEL_MIN = PANEL_MIN;", ctx);
function win(kind, closes) {
  const calls = [];
  const attrs = new Set(["data-panel-min"]);
  const host = {
    tagName: kind === "dialog" ? "DIALOG" : "DIV", open: true, inert: true, isConnected: true,
    hidden: false,
    setAttribute: (k) => attrs.add(k), removeAttribute: (k) => attrs.delete(k), hasAttribute: (k) => attrs.has(k),
    classList: { contains: (c) => c === "hidden" && host.hidden },
    close() { host.open = false; calls.push("close"); },
    showModal() { host.open = true; calls.push("showModal"); },
    show() { host.open = true; calls.push("show"); },
  };
  const btn = {
    focus() { calls.push("focus:" + (attrs.has("data-panel-min") ? "hidden" : "shown")); },
    click() {
      calls.push("click:" + (attrs.has("data-panel-min") ? "hidden" : "shown"));
      if (!closes) return;
      if (kind === "dialog") host.close(); else if (kind === "sheet") host.isConnected = false; else host.hidden = true;
    },
  };
  return { host, btn, calls, attrs };
}
const out = {};
const run = (name, kind, closes) => {
  const w = win(kind, closes);
  ctx.PANEL_MIN.set(w.host, { panel: {}, chip: { remove() {} }, modal: kind === "dialog" });
  ctx.panelCloseBtn = () => w.btn;
  ctx.panelMinTray = () => ({ hidePopover() {} });
  ctx.panelPushSync = () => {};
  ctx.getComputedStyle = () => ({ display: "none" });
  ctx.panelRestore(w.host, true);
  out[name] = { w, atOnce: w.attrs.has("data-panel-min") };
};
run("dialog", "dialog", true);
run("overlay", "overlay", true);
run("sheet", "sheet", true);
run("held", "dialog", false);
setTimeout(() => {
  const res = {};
  for (const [k, v] of Object.entries(out)) res[k] = { calls: v.w.calls, atOnce: v.atOnce, after: v.w.attrs.has("data-panel-min"), open: v.w.host.open };
  console.log(JSON.stringify(res));
}, 1500);
"""


@node
def test_a_close_from_the_pill_never_shows_the_window() -> None:
    proc = subprocess.run(["node", "-e", HARNESS, str(SRC)], capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    res = json.loads(proc.stdout.strip().splitlines()[-1])
    for kind in ("dialog", "overlay", "sheet"):
        calls = res[kind]["calls"]
        # Close is pressed while the window is still hidden, and nothing shows it first.
        assert "click:hidden" in calls, (kind, calls)
        assert not any(c.endswith(":shown") for c in calls), (kind, calls)
        assert "showModal" not in calls and "show" not in calls, (kind, calls)
        # the hidden mark stays on in the same task (no frame with the exit
        # transition on screen) and comes off once the window is gone
        assert res[kind]["atOnce"] is True, kind
        assert res[kind]["after"] is False, kind
    # A close held back (a confirm, a refusal) shows the window again, modal again.
    held = res["held"]
    assert "click:hidden" in held["calls"] and held["calls"][-1] == "showModal", held
    assert held["after"] is False and held["open"] is True


def test_a_minimised_window_has_no_transition_or_animation() -> None:
    css = CSS.read_text(encoding="utf-8")
    start = css.index("[data-panel-min] {")
    rule = css[start : css.index("}", start)]
    assert "visibility: hidden;" in rule
    assert "transition: none;" in rule and "animation: none;" in rule
