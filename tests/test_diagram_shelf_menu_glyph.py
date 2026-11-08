"""Review finding 5: the shelf's "more" menu put each tile's glyph on its row by index into the rendered rows, so a
`kebabMenu` that regrouped or reordered them would have put a glyph on the wrong row without a sound. The glyph now rides
on its menu item (`lead`, sheets-selects.js `kebabMenu`), read in node over a small fake DOM."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")

HARNESS = r"""
const vm = require("vm"), fs = require("fs");
class El {
  constructor(tag) { this.tag = tag; this.kids = []; this.dataset = {}; this.className = ""; this.owner = null; this.handlers = []; }
  append(...n) { this.kids.push(...n); } prepend(...n) { this.kids.unshift(...n); }
  setAttribute() {} addEventListener(t, f) { this.handlers.push([t, f]); }
  get classList() { return { contains: (c) => this.className.split(" ").includes(c), add: () => {}, remove: () => {} }; }
  cloneNode() { const c = new El(this.tag); c.owner = this.owner; return c; }
  get firstChild() { return this.kids[0]; }
  matches() { return false; } getBoundingClientRect() { return { right: 0, bottom: 0 }; }
}
const doc = { createElement: (t) => new El(t) };
let opened = null;
const ctx = {
  document: doc, diagramModel: {}, console, window: {}, matchMedia: () => ({ matches: false }),
  openMenuAtPoint: (items) => { opened = items; return null; },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv.at(-1) + "/diagram-library.js", "utf8"), ctx);
const names = ["Actor", "Participant", "Message", "Reply", "Note", "Loop", "Alt"];
const glyph = (name) => { const g = new El("svg"); g.owner = name; return g; };
const specs = names.map((name, i) => ({ name, group: i < 3 ? "Parts" : "Steps", hint: name, label: name, data: { tile: name.toLowerCase() }, glyph: glyph(name), press: () => {} }));
const stage = new El("div"); stage.className = "dgm-stage";
stage.querySelector = () => null;
const S = { fig: { parentElement: stage }, k: { name: "sequence" }, specs };
ctx.diagramModel.library.shelf(S, {});
const more = stage.kids.at(-1).kids.at(-1);
more.handlers.find(([t]) => t === "click")[1]();
//: Hand the rows over reversed, as a kebabMenu that regrouped them would; each row's own glyph must still be its own.
const rows = [...opened].reverse().map((item) => ({ label: item.label, glyphOf: item.lead?.().kids[0]?.owner ?? null }));
process.stdout.write(JSON.stringify(rows));
"""


@needs_node
def test_a_reordered_menu_keeps_each_glyph_on_its_own_row() -> None:
    out = subprocess.run(["node", "-e", HARNESS, str(JS)], capture_output=True, text=True, check=True).stdout
    rows = json.loads(out)
    assert len(rows) == 7
    assert all(r["glyphOf"] == r["label"] for r in rows), rows


def test_the_shelf_no_longer_matches_rows_by_position() -> None:
    lib = (JS / "diagram-library.js").read_text(encoding="utf-8")
    assert 'querySelectorAll(":scope > .menu-item")' not in lib and "specs[i]" not in lib
    assert "lead:" in lib
