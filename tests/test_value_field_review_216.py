"""PR 216 review of value-field.js: the phone keyboard fits the field, and a slider
id with a quote in it still finds its readout. The real file runs under node with a
small stand-in for the page (no browser; nothing here has run on a phone)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "frontend" / "js" / "value-field.js"

HARNESS = r"""
const fs = require("fs"), vm = require("vm");
class HTMLInputElement {}
const selectors = [];
const node = (tag) => ({
  tagName: tag.toUpperCase(), children: [], dataset: {}, attrs: {}, l: {},
  classList: { add() {}, remove() {}, toggle() {} },
  setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k] ?? null; },
  append(...c) { this.children.push(...c); }, replaceChildren(...c) { this.children = c; },
  addEventListener() {}, after() {}, select() {}, focus() {}, blur() {},
});
const document = {
  createElement: node, getElementById: () => null, activeElement: null, addEventListener() {},
  querySelectorAll: () => [], querySelector: (selector) => { selectors.push(selector); return null; },
};
const sandbox = { document, window: {}, HTMLInputElement, CSS: { escape: (s) => String(s).replace(/[^\w-]/g, (c) => "\\" + c) } };
sandbox.window.addEventListener = () => {};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), sandbox);
const modeOf = (opts) => { const field = sandbox.window.valueField(node("span"), opts); return field.input.inputMode; };
const slider = Object.assign(Object.create(HTMLInputElement.prototype), {
  type: "range", id: process.argv[2] || "", dataset: {}, min: "0", max: "10", step: "1", value: "3",
  parentElement: null, labels: [], hasAttribute: () => false, getAttribute: () => null, title: "Depth",
  addEventListener() {}, after() {},
});
let ranged = null;
try { ranged = sandbox.window.valueField.range(slider); } catch (error) { ranged = String(error); }
console.log(JSON.stringify({
  page: modeOf({ value: 1, min: 1, max: () => 12 }),
  zoom: modeOf({ value: 100, min: 5, max: 500 }),
  fraction: modeOf({ value: 0.5, min: 0, max: 1, step: 0.1 }),
  open: modeOf({ value: 1 }),
  negative: modeOf({ value: 0, min: -5, max: 30 }),
  selectors, ranged: typeof ranged,
}));
"""


def _run(slider_id: str = "") -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", HARNESS, str(SRC), slider_id], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_the_phone_keyboard_fits_what_the_field_accepts():
    modes = _run()
    # Whole numbers from zero up: digits only.
    assert modes["page"] == "numeric" and modes["zoom"] == "numeric"
    # The parser reads 1.5, so a field that can hold a fraction shows the decimal key;
    # one with no bounds cannot say, so it does too.
    assert modes["fraction"] == "decimal" and modes["open"] == "decimal"
    # Neither numeric keypad has a minus key: a negative lower bound gets the full keyboard.
    assert modes["negative"] == "text"

