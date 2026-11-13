"""A map line is drawn again only when something it reads has changed (wbp2).

`wbRenderMapEdges` computed every line's geometry on every render (15 ms at
200 topics) and only then compared the result with what was on screen. The
cache keys the *inputs*, so an unchanged line costs one string compare. A key
that misses an input is a line that stops following a change, so the proof
here is behavioural: `whiteboard-map.js` is loaded into a node `vm`, every
input is changed in turn and the geometry must move with the key, and a
seeded fuzz changes several at once and checks the one direction that
matters: equal keys never hide different geometry.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAP_JS = ROOT / "frontend" / "js" / "whiteboard-map.js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const ctx = {
  console, Math, Number, Object, Set, Map, JSON, Date, Array, String, RegExp, Promise, Boolean,
  setTimeout: () => 0, clearTimeout() {}, addEventListener() {},
  onSurface() {},  // settings-body.js: the board's load-time wiring waits for its template (row 21); not under test
  MD_RUN_FONTS: { serif: "s", mono: "m", wide: "w" },
  document: { querySelector: () => null, querySelectorAll: () => [], getElementById: () => null, addEventListener() {} },
  wbState: { objects: [] },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx, { filename: "whiteboard-map.js" });
ctx.__out = (value) => process.stdout.write(JSON.stringify(value));
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), ctx);
"""

#: Every input of one line, as a mutation of a fresh scene. `scene()` builds
#: a parent, a child, the map's state and the colour table; each entry changes
#: one thing the geometry is allowed to read.
SCENE = r"""
function scene() {
  const parent = { id: 1, parent_id: null, kind: "topic", x: 0, y: 0, width: 120, height: 40, data: {} };
  const child = { id: 2, parent_id: 1, kind: "topic", x: 260, y: 90, width: 140, height: 44, data: {} };
  window.wbMapState = { type: "map", layout: "tree-right", theme: {} };
  wbMapCache.levelById = new Map([[1, 0], [2, 1]]);
  wbMapCache.looksFor = null;
  wbMapCache.looks = null;
  return { parent, child, colors: new Map([[2, "#336699"]]), layout: "tree-right" };
}
function both(s) {
  const geom = wbMapEdgeGeometry(s.parent, s.child, s.layout, s.colors);
  return { paint: geom.paint, key: wbMapEdgeKey(s.parent, s.child, s.layout, s.colors) };
}
const FISHBONE = (s) => { s.layout = "fishbone"; window.wbMapState.layout = "fishbone"; };
const MUTATIONS = {
  parent_x: (s) => { s.parent.x += 7; },
  parent_y: (s) => { s.parent.y += 7; },
  parent_width: (s) => { s.parent.width += 30; },
  parent_height: (s) => { s.parent.height += 30; },
  child_x: (s) => { s.child.x += 7; },
  child_y: (s) => { s.child.y -= 70; },
  child_width: [(s) => { s.child.x = -300; }, (s) => { s.child.width += 30; }],
  child_height: (s) => { s.child.height += 30; },
  parent_block: (s) => { s.parent._block = { w: 300, h: 200 }; },
  child_block: (s) => { s.child._block = { w: 300, h: 200 }; },
  map_layout: (s) => { s.layout = "tree-down"; window.wbMapState.layout = "tree-down"; },
  map_layout_logic: (s) => { s.layout = "logic-right"; window.wbMapState.layout = "logic-right"; },
  branch_layout: [(s) => { s.child.y = 400; }, (s) => { s.child._bl = "radial"; }],
  branch_top: [FISHBONE, (s) => { s.child._blTop = 99; }],
  parent_is_root: [FISHBONE, (s) => { s.parent.parent_id = 7; }],
  edge_style: (s) => { s.child.data.edge_style = "elbow"; },
  edge_style_straight: (s) => { s.child.data.edge_style = "straight"; },
  edge_dashed: (s) => { s.child.data.edge_dashed = true; },
  edge_width: (s) => { s.child.data.edge_width = "thin"; },
  edge_arrow_on: (s) => { s.child.data.edge_arrow = "on"; },
  edge_arrow_off: [(s) => { s.child.data.edge_dashed = true; }, (s) => { s.child.data.edge_arrow = "off"; }],
  edge_from: (s) => { s.child.data.edge_from = "bottom"; },
  edge_to: (s) => { s.child.data.edge_to = "top"; },
  edge_slide: (s) => { s.child.data.edge_slide = 0.2; },
  edge_bend: (s) => { s.child.data.edge_bend = 0.5; },
  edge_label: (s) => { s.child.data.edge_label = "because"; },
  edge_label_dx: (s) => { s.child.data.edge_label = "x"; s.child.data.edge_label_dx = 31; },
  edge_label_dy: (s) => { s.child.data.edge_label = "x"; s.child.data.edge_label_dy = 17; },
  edge_label_size: (s) => { s.child.data.edge_label = "x"; s.child.data.edge_label_size = 20; },
  edge_label_bold: (s) => { s.child.data.edge_label = "x"; s.child.data.edge_label_bold = true; },
  edge_label_color: (s) => { s.child.data.edge_label = "x"; s.child.data.edge_label_color = "#aa0000"; },
  edge_label_chip: (s) => { s.child.data.edge_label = "x"; s.child.data.edge_label_chip = true; },
  colour: (s) => { s.colors.set(2, "#aa5500"); },
  colour_removed: (s) => { s.colors.delete(2); },
  theme_edge_style: (s) => { window.wbMapState.theme = { edge_style: "elbow" }; },
  theme_edge_dashed: (s) => { window.wbMapState.theme = { edge_dashed: true }; },
  theme_edge_width: [(s) => { wbMapCache.levelById = new Map([[1, 0], [2, 2]]); }, (s) => { window.wbMapState.theme = { edge_width: "thin" }; }],
  theme_edge_arrow: (s) => { window.wbMapState.theme = { edge_arrow: "on" }; },
  theme_level_look: (s) => { window.wbMapState.theme = { hierarchy: "flat" }; },
  theme_level_override: (s) => { window.wbMapState.theme = { levels: { 1: { edge_width: "thin", edge_style: "straight" } } }; },
  child_level: (s) => { wbMapCache.levelById = new Map([[1, 0], [2, 0]]); },
};
"""


def run(body: str):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        harness = Path(tmp) / "h.js"
        script = Path(tmp) / "body.js"
        harness.write_text(HARNESS, encoding="utf-8")
        script.write_text(SCENE + body, encoding="utf-8")
        proc = subprocess.run(
            ["node", str(harness), str(MAP_JS), str(script)], capture_output=True, text=True
        )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout)


@needs_node
def test_every_input_of_a_line_moves_its_key_with_its_geometry() -> None:
    """Each input changed alone: the geometry is new, so the key is new. The
    first assertion keeps the test honest (a mutation that does not change
    the line would pass any key), the second is the cache's correctness."""
    out = run(
        """
        const rows = {};
        for (const [name, entry] of Object.entries(MUTATIONS)) {
          const [pre, mutate] = Array.isArray(entry) ? entry : [() => {}, entry];
          const before = scene();
          pre(before);
          const base = both(before);
          const s = scene();
          pre(s);
          mutate(s);
          const after = both(s);
          rows[name] = { geometry: after.paint !== base.paint, key: after.key !== base.key };
        }
        __out(rows);
        """
    )
    unmoved = [name for name, row in out.items() if not row["geometry"]]
    assert not unmoved, f"these mutations do not change the line, so they prove nothing: {unmoved}"
    stale = [name for name, row in out.items() if not row["key"]]
    assert not stale, f"the key misses an input: {stale}"


@needs_node
def test_equal_keys_never_hide_different_geometry() -> None:
    """A seeded fuzz over combinations of every input: whenever two scenes
    draw different lines their keys differ. Equal keys with equal paint is
    the cache hit; equal keys with different paint is the bug this exists
    to catch."""
    out = run(
        """
        let seed = 20261101;
        const rand = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };
        const names = Object.keys(MUTATIONS);
        const seen = new Map();
        let collisions = 0, hits = 0, scenes = 0;
        for (let i = 0; i < 4000; i += 1) {
          const s = scene();
          const picks = 1 + Math.floor(rand() * 4);
          for (let k = 0; k < picks; k += 1) {
            const entry = MUTATIONS[names[Math.floor(rand() * names.length)]];
            if (Array.isArray(entry)) entry.forEach((step) => step(s)); else entry(s);
          }
          // Moves too, so that two scenes agree on the key now and then.
          if (rand() < 0.5) s.child.x += Math.floor(rand() * 3) * 5;
          const { paint, key } = both(s);
          scenes += 1;
          if (seen.has(key)) {
            if (seen.get(key) === paint) hits += 1; else collisions += 1;
          } else seen.set(key, paint);
        }
        __out({ collisions, hits, scenes });
        """
    )
    assert out["collisions"] == 0, out
    assert out["hits"] > 50, f"the fuzz never produced a cache hit, so it proved nothing: {out}"


@needs_node
def test_the_key_is_a_plain_string_compare() -> None:
    out = run(
        """
        const s = scene();
        __out({ type: typeof wbMapEdgeKey(s.parent, s.child, s.layout, s.colors),
                same: wbMapEdgeKey(s.parent, s.child, s.layout, s.colors) === wbMapEdgeKey(s.parent, s.child, s.layout, s.colors) });
        """
    )
    assert out == {"type": "string", "same": True}


#: A fake of the one corner of the DOM `wbRenderMapEdges` touches, so the
#: render itself runs: elements are objects with attributes and children.
FAKE_DOM = r"""
function el(tag) {
  const node = {
    tag, attrs: {}, children: [], parentNode: null, dataset: {}, isConnected: true, style: { setProperty() {}, removeProperty() {} },
    classList: { add() {}, remove() {}, contains: () => false },
    setAttribute(k, v) { this.attrs[k] = String(v); this.writes = (this.writes || 0) + 1; },
    getAttribute(k) { return this.attrs[k] ?? null; },
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    insertBefore(c, ref) {
      const at = this.children.indexOf(c); if (at >= 0) this.children.splice(at, 1);
      const to = ref ? this.children.indexOf(ref) : this.children.length;
      c.parentNode = this; this.children.splice(to < 0 ? this.children.length : to, 0, c); return c;
    },
    remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter((c) => c !== this); this.isConnected = false; },
    addEventListener() {},
    querySelector(sel) {
      const cls = sel.split(".").pop();
      return this.children.find((c) => (c.attrs.class || "").split(" ").includes(cls)) || null;
    },
    querySelectorAll: () => [],
    get firstChild() { return this.children[0] || null; },
    get childNodes() { return this.children; },
    set textContent(v) { this._t = v; },
    get textContent() { return this._t; },
  };
  return node;
}
const zoom = el("g");
document.getElementById = (id) => (id === "wb-zoom-group" ? zoom : null);
document.createElementNS = (ns, tag) => el(tag);
zoom.querySelector = (sel) => zoom.children.find((c) => (c.attrs.class || "") === "wb-map-edges") || null;
"""


@needs_node
def test_an_unchanged_line_is_neither_recomputed_nor_rewritten() -> None:
    """The render itself, on a fake DOM: the second render of an unchanged
    map computes no geometry and writes no attribute; moving one topic
    recomputes exactly its lines; a line the drag moved by hand is redone."""
    out = run(
        FAKE_DOM
        + """
        const objs = [];
        for (let i = 1; i <= 30; i += 1) {
          objs.push({ id: i, kind: "topic", parent_id: i === 1 ? null : Math.ceil(i / 3) , x: i * 20, y: (i % 5) * 60, width: 100, height: 40, data: {} });
        }
        wbState.objects = objs;
        window.wbMapState = { type: "map", layout: "free", theme: {} };
        wbRenderMapEdgePluses = () => {};
        wbSyncMapEdgeHandles = () => {};
        wbWireMapEdgeHandle = () => {};
        wbWireMapEdgeEnd = () => {};
        wbWireMapEdgeGestures = () => {};
        wbMapNodeColors = () => new Map();
        wbMapConcealed = () => new Set();
        let calls = 0;
        const real = wbMapEdgeGeometry;
        wbMapEdgeGeometry = (...args) => { calls += 1; return real(...args); };
        const writes = () => {
          let n = 0;
          const walk = (e) => { n += e.writes || 0; e.children.forEach(walk); };
          walk(zoom);
          return n;
        };
        const edgeCount = objs.length - 1;
        wbRenderMapEdges();
        const first = { calls, writes: writes() };
        calls = 0; const w1 = writes();
        wbRenderMapEdges();
        const second = { calls, writes: writes() - w1 };
        // Move topic 5: its own line up and the lines to its children.
        objs[4].x += 40; calls = 0; const w2 = writes();
        wbRenderMapEdges();
        const kids = objs.filter((o) => o.parent_id === 5).length;
        const moved = { calls, writes: writes() - w2, expected: 1 + kids };
        // A drag frame writes a line by hand; the next render must redo it.
        const group = zoom.children[0];
        const held = group._wbMapEdges.get("1:2");
        held.path._wbMoved = true;
        held.path.attrs.d = "M0 0";
        calls = 0;
        wbRenderMapEdges();
        const handDrawn = { calls, redrawn: held.path.attrs.d !== "M0 0" };
        __out({ edgeCount, first, second, moved, handDrawn });
        """
    )
    assert out["first"]["calls"] == out["edgeCount"]
    assert out["second"] == {"calls": 0, "writes": 0}, out
    assert out["moved"]["calls"] == out["moved"]["expected"], out
    assert 0 < out["moved"]["writes"] <= out["moved"]["expected"] * 12, out
    assert out["handDrawn"] == {"calls": 1, "redrawn": True}, out


def test_the_render_compares_the_key_before_it_works_out_the_geometry() -> None:
    src = MAP_JS.read_text(encoding="utf-8")
    match = re.search(r"^function wbRenderMapEdges\(.*?^}\n", src, re.MULTILINE | re.DOTALL)
    assert match
    body = "\n".join(line for line in match.group(0).splitlines() if not line.lstrip().startswith("//"))
    assert body.index("held.key !== geomKey") < body.index("wbMapEdgeGeometry(")
    assert "wbMapEdgeKey(" in body


def test_a_click_on_the_bend_dot_stays_off_the_canvas() -> None:
    """L-mindmap-15: the first click of a double-click on the dot reached the
    canvas, cleared the selection and stood the mid-line `+` back over the dot,
    so the second click hit the `+` and the line never straightened."""
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    src = MAP_JS.read_text(encoding="utf-8")
    start = src.index("function wbWireMapEdgeHandle(")
    end = src.index("\nfunction ", start + 1)
    script = src[start:end] + r"""
const on = {};
const handle = { addEventListener: (type, fn) => { on[type] = fn; } };
wbWireMapEdgeHandle(handle, "p", "c");
let stopped = false;
on.click?.({ stopPropagation: () => { stopped = true; } });
console.log(JSON.stringify({ wired: typeof on.click === "function", stopped }));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(out.stdout) == {"wired": True, "stopped": True}
