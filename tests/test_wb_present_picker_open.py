"""The page picker keeps its rows current while its menu is open (INBOX 1563's
sibling bug, found by the agent that built the picker).

`wbPresentCaption` rebuilt the picker's rows through
`wrap.querySelector(".action-menu")`. An open `kebabMenu` is parked on the
body, so that lookup found nothing, the rows were not refreshed and the new
page was not marked `aria-current`. The caption now keeps a reference to the
menu, as the laser menu does. A small fake DOM runs the function itself.
"""

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = frontend_text("whiteboard.js")

FAKE = r"""
class El {
  constructor(tag) { this.tag = tag; this.children = []; this.parent = null; this.cls = new Set(); this.attrs = {}; this.text = ""; this.style = {}; this.disabled = false; }
  get classList() {
    const set = this.cls;
    return { add: (...c) => c.forEach((x) => set.add(x)), remove: (...c) => c.forEach((x) => set.delete(x)), contains: (c) => set.has(c) };
  }
  set className(v) { this.cls = new Set(v.split(/\s+/).filter(Boolean)); }
  set textContent(v) { this.text = v; }
  get textContent() { return this.text; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener() {}
  get scrollWidth() { return 0; }
  get clientWidth() { return 0; }
  replaceChildren(...nodes) { this.children.forEach((c) => (c.parent = null)); this.children = []; this.append(...nodes); }
  append(...nodes) { for (const n of nodes) { if (n.parent) n.parent.children = n.parent.children.filter((c) => c !== n); n.parent = this; this.children.push(n); } }
  matches(sel) { return sel.startsWith(".") ? this.cls.has(sel.slice(1)) : this.tag === sel; }
  walk(sel, direct) {
    const found = [];
    const visit = (node) => { for (const c of node.children) { if (c.matches(sel)) found.push(c); if (!direct) visit(c); } };
    visit(this);
    return found;
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  querySelectorAll(sel) { return sel.startsWith(":scope > ") ? this.walk(sel.slice(9), true) : this.walk(sel, false); }
}
const body = new El("body");
const slot = new El("div"), bar = new El("div"), prev = new El("button"), next = new El("button");
const byId = { "wb-present-count": slot, "wb-present-bar": bar, "wb-present-prev": prev, "wb-present-next": next };
const document = {
  getElementById: (id) => byId[id] || null,
  createElement: (tag) => new El(tag),
  querySelector: () => null,
};
const wbStudy = { on: false };
function wbMapStudySyncBar() {}
function wbPresentShow() {}
function kebabMenu(items) {
  const wrap = new El("span"); wrap.className = "menu-wrap";
  const opener = new El("button"); opener.replaceChildren = function () { this.children = []; };
  const menu = new El("div"); menu.className = "action-menu";
  for (const item of items) { const row = new El("button"); row.className = "menu-item"; row.text = item.label; menu.append(row); }
  wrap.append(opener, menu);
  return wrap;
}
const steps = (names) => names.map((n) => ({ title: () => n }));
"""


def _run(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = SOURCE.index("function wbPresentCaption(")
    fn = SOURCE[start : SOURCE.index("\n}\n", start) + 3]
    out = subprocess.run([node, "-e", FAKE + fn + script], capture_output=True, text=True, check=True, timeout=60)
    return json.loads(out.stdout)


def test_rows_are_refreshed_and_marked_while_the_menu_is_open_on_the_body() -> None:
    out = _run(
        r"""
wbPresentCaption(0, steps(["One", "Two", "Three"]));
const wrap = slot.children[0];
//: What opening a kebab does: the menu leaves its wrap for the body.
const parked = wrap.pickMenu;
body.append(parked);
const inWrap = wrap.querySelector(".action-menu");
wbPresentCaption(1, steps(["One", "Deux", "Three"]));
const rows = parked.querySelectorAll(".menu-item");
console.log(JSON.stringify({
  inWrap: inWrap === null,
  texts: rows.map((r) => r.text),
  current: rows.map((r) => r.attrs["aria-current"] || null),
  caption: wrap.querySelector(":scope > button").attrs["aria-label"],
}));
"""
    )
    assert out["inWrap"] is True  # the lookup the old code used finds nothing
    assert out["texts"] == ["1. One", "2. Deux", "3. Three"]
    assert out["current"] == [None, "step", None]
    assert out["caption"] == "of 3: Deux. Go to a page"


def test_the_picker_keeps_one_reference_to_its_menu() -> None:
    start = SOURCE.index("function wbPresentCaption(")
    body = SOURCE[start : SOURCE.index("\n}\n", start) + 3]
    assert 'wrap.pickMenu = wrap.querySelector(".action-menu");' in body
    assert 'wrap.querySelector(".action-menu")' not in body.replace('wrap.pickMenu = wrap.querySelector(".action-menu");', "")
