"""1108 P2, P3: the lazy row menu, the SVG label patch and the draw that waits for a typed label, run in node.

The real diagram-library.js, diagram-picture.js and `drawPicture` (cut out of diagram-builder.js) run in a `vm` context
over a small fake DOM. What is stubbed is named in the harness: `kebabMenu` and `openActionMenu` follow menus.js and
sheets-selects.js (the menu leaves `hidden`, the opener says `aria-expanded`, focus goes to the first row), and a
button turns Enter or Space into a click the way a browser does. Real-browser numbers are in the CHANGELOG line.
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
class El {
  constructor(tag) { this.tag = tag; this.children = []; this.parent = null; this.attrs = {}; this.cls = new Set(); this.handlers = []; this.text = ""; }
  get className() { return [...this.cls].join(" "); }
  set className(v) { this.cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
  get classList() { const s = this.cls; return { add: (...c) => c.forEach((x) => s.add(x)), remove: (...c) => c.forEach((x) => s.delete(x)), contains: (c) => s.has(c) }; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  set textContent(v) { this.text = String(v); }
  get textContent() { return this.text + this.children.map((c) => c.textContent).join(""); }
  append(...kids) { for (const k of kids) { k.parent = this; this.children.push(k); } }
  appendChild(k) { this.append(k); return k; }
  replaceWith(n) { const p = this.parent; p.children[p.children.indexOf(this)] = n; n.parent = p; this.parent = null; }
  all() { return this.children.flatMap((c) => [c, ...c.all()]); }
  querySelector(sel) { return this.all().find((e) => sel.split(".").slice(1).every((c) => e.cls.has(c))) || null; }
  querySelectorAll(sel) { return this.all().filter((e) => sel.split(".").slice(1).every((c) => e.cls.has(c))); }
  addEventListener(type, fn, capture) { this.handlers.push({ type, fn, capture: capture === true }); }
  focus() { doc.activeElement = this; }
  getBoundingClientRect() { return { left: 0, right: 0, top: 0, bottom: 0, width: 0, height: 0 }; }
  //: Capture on the way down, the target, then bubbling; stopPropagation ends it.
  click() { dispatch(this, "click"); }
  //: What a browser does with a focused button: Enter or Space is a click.
  press(key) { if (this.tag === "button" && (key === "Enter" || key === " ")) this.click(); }
}
function dispatch(target, type) {
  const path = []; for (let e = target; e; e = e.parent) path.unshift(e);
  const event = { type, target, stopped: false, stopPropagation() { this.stopped = true; } };
  for (const e of path) { for (const h of e.handlers) if (h.type === type && h.capture) h.fn(event); if (event.stopped) return; }
  for (const e of [...path].reverse()) { for (const h of e.handlers) if (h.type === type && !h.capture) h.fn(event); if (event.stopped) return; }
}
const doc = { activeElement: null, createElement: (t) => new El(t) };
// menus.js `openActionMenu` / sheets-selects.js `kebabMenu`, as far as the row menu depends on them.
function kebabMenu(items, label) {
  const wrap = new El("span"); wrap.className = "menu-wrap";
  const menu = new El("div"); menu.className = "action-menu hidden";
  const opener = new El("button"); opener.className = "ghost small icon-only kebab-opener";
  opener.setAttribute("aria-label", label); opener.setAttribute("aria-haspopup", "menu"); opener.setAttribute("aria-expanded", "false");
  opener.addEventListener("click", () => {
    if (menu.cls.has("hidden")) { menu.cls.delete("hidden"); opener.setAttribute("aria-expanded", "true"); menu.querySelector(".menu-item")?.focus(); }
    else { menu.cls.add("hidden"); opener.setAttribute("aria-expanded", "false"); }
  });
  for (const item of items) { const b = new El("button"); b.className = "menu-item"; b.text = item.label; menu.append(b); }
  wrap.append(opener, menu);
  return wrap;
}
const timers = [];
const ctx = {
  document: doc, kebabMenu, diagramModel: {}, console, Promise, Math, Number, String, Set, Array, JSON, RegExp, performance: { now: () => 0 },
  setTimeout: (fn, ms) => timers.push({ fn, ms }) && timers.length, clearTimeout: () => {},
};
ctx.window = ctx;
vm.createContext(ctx);
const load = (file, src) => vm.runInContext(src ?? fs.readFileSync(JS + "/" + file, "utf8"), ctx, { filename: file });
ctx.El = El; ctx.doc = doc;
const out = (v) => process.stdout.write(JSON.stringify(v));
const settle = () => new Promise((r) => setImmediate(r));
//: One round of the timers queued so far (a poll that re-queues itself waits for the next round).
const round = async () => { const now = timers.splice(0); for (const t of now) t.fn(); await settle(); };
"""


def run(body: str):
    proc = subprocess.run(["node", "-e", HARNESS + "\n(async () => {\n" + body + "\n})();", str(JS)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2500:]
    return json.loads(proc.stdout)


SVG = (
    '<svg viewBox="0 0 100 100"><g class="node default" id="mmd1-flowchart-A-0" transform="translate(10, 10)"><rect/>'
    '<text><tspan class="text-outer-tspan row" x="0"><tspan class="text-inner-tspan">Old</tspan><tspan class="text-inner-tspan"> name</tspan></tspan></text></g>'
    '<g class="node default" id="mmd1-flowchart-B-1" transform="translate(30, 30)"><rect/>'
    '<text><tspan class="text-outer-tspan row" x="0"><tspan class="text-inner-tspan">Other</tspan></tspan></text></g></svg>'
)


def _patch(was: str, text: str, key: str = "n:A"):
    return run(
        f"""
load("diagram-picture.js");
ctx.diagramModel.ops = {{ split: (k) => k.split(":") }};
let shown = null, painted = 0;
ctx.mermaidShow = (fig, result) => {{ shown = result.svg; }};
const img = {{ mermaidSvg: {json.dumps(SVG)} }};
const S = {{ source: "x", fig: {{ mermaidKey: "k", onpaint: [() => painted++], querySelector: () => img }} }};
ctx.diagramModel.picture.patch(S, {json.dumps(key)}, {json.dumps(was)}, {json.dumps(text)});
out({{ shown, painted }});
"""
    )


@needs_node
def test_a_relabel_is_swapped_into_the_drawn_node_and_only_that_node():
    got = _patch("Old name", "New name")
    assert got["painted"] == 1
    assert "New name</tspan></tspan>" in got["shown"] and "Old" not in got["shown"] and ">Other<" in got["shown"]


@needs_node
def test_the_swapped_words_are_escaped_so_a_label_cannot_add_markup():
    got = _patch("Old name", 'a<b>&"c"')
    assert "a&lt;b&gt;&amp;" in got["shown"] and "<b>" not in got["shown"]
    # A double quote is text content here, not an attribute, so it may stay; it must not break out of the tspan.
    assert got["shown"].count("<tspan") == _patch("Old name", "plain")["shown"].count("<tspan")


@needs_node
@pytest.mark.parametrize("was,key", [("Not the words", "n:A"), ("Old name", "n:Missing")])
def test_a_patch_leaves_the_picture_alone_when_the_old_words_or_the_node_do_not_match(was, key):
    got = _patch(was, "New name", key)
    assert got["shown"] is None and got["painted"] == 0


def _builder_draw() -> str:
    code = (JS / "diagram-builder.js").read_text(encoding="utf-8")
    body = code[code.index("function drawPicture(S) {") :]
    return body[: body.index("\n  // --- the tree")]


@needs_node
def test_a_draw_waits_while_a_label_is_typed_and_a_second_relabel_ends_in_one_redraw_with_the_latest_label():
    got = run(
        f"""
load("diagram-picture.js");
load("drawPicture", {json.dumps(_builder_draw())});
ctx.diagramModel.front = (s) => ({{ rest: s }});
ctx.diagramModel.picture.boxes = () => null;
ctx.diagramModel.picture.failure = () => {{}};
ctx.ensureModule = () => Promise.resolve(true);
ctx.smallButton = () => null;
ctx.el = () => new El("p");
const drawn = [];
ctx.mermaidFill = (fig, source, done) => {{ drawn.push(source); done({{ svg: null }}); }};
let editing = true;
const cls = {{ toggle() {{}}, remove() {{}} }};
const S = {{ source: "flowchart TD\\n A[One]", drawn: 0, m: {{ nodes: [1] }}, plain: false,
  tree: {{ querySelector: () => (editing ? {{}} : null) }},
  fig: {{ classList: cls, closest: () => null, querySelector: () => null, replaceChildren() {{}}, onpaint: [] }} }};
ctx.drawPicture(S);
for (let i = 0; i < 4; i++) await round();
const whileTyping = drawn.length;
S.source = "flowchart TD\\n A[Two]";
ctx.drawPicture(S);
for (let i = 0; i < 4; i++) await round();
const stillTyping = drawn.length;
editing = false;
for (let i = 0; i < 6; i++) await round();
out({{ whileTyping, stillTyping, drawn }});
"""
    )
    assert got["whileTyping"] == 0 and got["stillTyping"] == 0
    assert got["drawn"] == ["flowchart TD\n A[Two]"]


def _lazy(items_js: str, label: str):
    return (
        'load("diagram-library.js");\n'
        f"const items = () => {items_js};\n"
        f"const stub = ctx.diagramModel.library.lazyKebab(items, {json.dumps(label)});\n"
        "const row = new El('div'); row.append(stub);\n"
        "const opener = () => row.querySelector('.kebab-opener');\n"
        "const menu = () => row.querySelector('.action-menu');\n"
        "const itemsIn = () => row.querySelectorAll('.menu-item').length;\n"
    )


FLOW_ITEMS = "[{label: 'Rename'}, {label: 'Connect to'}, {label: 'Colour'}, {label: 'Shape', items: []}, {label: 'Move up'}, {label: 'Delete'}]"
KIND_ITEMS = "[{label: 'Rename'}, {label: 'Add child'}, {label: 'Delete'}]"


@needs_node
@pytest.mark.parametrize("items_js,count", [(FLOW_ITEMS, 6), (KIND_ITEMS, 3)])
@pytest.mark.parametrize("how", ["click", "Enter", " "])
def test_a_row_menu_opens_with_all_its_items_on_the_first_press_by_click_or_key(items_js, count, how):
    got = run(
        _lazy(items_js, "Menu for Step")
        + f"""
const before = itemsIn();
const first = opener();
let built = 0;
first.focus();
{"first.click();" if how == "click" else f"first.press({json.dumps(how)});"}
out({{ before, after: itemsIn(), expanded: opener().getAttribute("aria-expanded"), hidden: menu().cls.has("hidden"),
  swapped: opener() !== first, focusInMenu: doc.activeElement && doc.activeElement.cls.has("menu-item"),
  label: opener().getAttribute("aria-label"), isStub: row.children[0] === stub }});
"""
    )
    assert got["before"] == 0 and got["after"] == count
    assert got["expanded"] == "true" and got["hidden"] is False and got["swapped"] and got["focusInMenu"]
    assert got["label"] == "Menu for Step" and got["isStub"] is False


@needs_node
def test_a_second_press_closes_the_built_menu_and_does_not_build_it_again():
    got = run(
        _lazy(KIND_ITEMS, "Menu for Step")
        + """
opener().click();
const built = row.children[0];
opener().click();
out({ same: row.children[0] === built, expanded: opener().getAttribute("aria-expanded"), count: itemsIn() });
"""
    )
    assert got == {"same": True, "expanded": "false", "count": 3}


def test_both_panes_build_their_row_menu_lazily():
    # The call sites cannot be run without the whole pane; this keeps both on the lazy path.
    assert "diagramModel.library.lazyKebab(() => blockItems(S, key)" in (JS / "diagram-builder.js").read_text(encoding="utf-8")
    assert "diagramModel.library.lazyKebab(() => itemsFor(S, key)" in (JS / "diagram-kinds.js").read_text(encoding="utf-8")
