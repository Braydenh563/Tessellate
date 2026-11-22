"""A branch drop leaves the links it carried whole on their translate (L-mindmap-25, mapperf 500).

Letting go of a 500-topic branch with 300 links inside it redrew every one of them (45 to 80ms of a
110 to 145ms drop frame). Both ends of such a link moved by the drop's one delta, so the drawing it
would get is the one it shows, moved: the drop keeps the translate and the link is drawn from its
data later (idle, the next writer of its path, a render, a press or a key, the export). What is
pinned is that every link shows the geometry a full redraw gives it: a drawn one exactly, a held
one to the printer's own step (a ribbon prints tenths, and a number on a half tenth can round the
other way once moved: 220 of 175,200 numbers over 200 drops, each by 0.1), and once settled,
exactly, string for string. `whiteboard-map.js` (with its pieces, so the real ribbons) and
`whiteboard-drag.js` (the real redraw) are run in a node `vm` against fake elements.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests._app_js import frontend_text

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const ctx = {
  console, Math, Number, Object, Set, Map, JSON, Array, String, RegExp, Promise, Boolean,
  setTimeout: () => 0, clearTimeout() {}, addEventListener() {}, queueMicrotask() {}, onSurface() {},
  MD_RUN_FONTS: { serif: "s", mono: "m", wide: "w" },
  document: { querySelector: () => null, querySelectorAll: () => [], getElementById: () => null, addEventListener() {} },
  wbState: { objects: [], sketches: [] },
};
ctx.wbInstances = { container: () => null, layer: () => null, query: () => null, queryAll: () => [] };
ctx.window = ctx;
vm.createContext(ctx);
for (const [file, name] of [[process.argv[2], "whiteboard-map.js"], [process.argv[3], "whiteboard-drag.js"]]) {
  vm.runInContext(fs.readFileSync(file, "utf8"), ctx, { filename: name });
}
ctx.__out = (value) => process.stdout.write(JSON.stringify(value));
vm.runInContext(fs.readFileSync(process.argv[4], "utf8"), ctx);
"""

#: Five topics at uneven places, so a ribbon's numbers are not round; 1 to 4 are the dropped branch.
SCENE = r"""
var wbCullNow = { outside: () => false, drawn: null };
const WB_CARD_DEFAULT_SIZE = { w: 250, h: 150 };
const topics = new Map([
  [1, { id: 1, kind: "topic", x: 3.3, y: 7.7, width: 133, height: 41, parent_id: null }],
  [2, { id: 2, kind: "topic", x: 301.13, y: 177.21, width: 97, height: 37, parent_id: 1 }],
  [3, { id: 3, kind: "topic", x: 288.4, y: -140.06, width: 120, height: 40, parent_id: 1 }],
  [4, { id: 4, kind: "topic", x: 611.7, y: 33.35, width: 88, height: 52, parent_id: 2 }],
  [5, { id: 5, kind: "topic", x: -400, y: 300, width: 120, height: 40, parent_id: 1 }],
]);
wbIsMap = () => true;
wbLinkItem = (kind, id) => topics.get(id) || null;
wbMapNodeSize = (o) => ({ w: o.width, h: o.height });
wbMapIndex = () => ({ byId: topics, nodes: [...topics.values()] });
wbMapNodeColors = () => new Map([[1, "#3366ff"]]);
wbMapLayout = () => "tree-right";
wbMapTheme = () => ({ edge_style: "curve" });
currentAccentHex = () => "#123456";
wbResolveLinkEndpoints = (p) => {
  const c = (o) => ({ x: o.x + o.width / 2, y: o.y + o.height / 2 });
  return { source: c(topics.get(p.sourceId)), target: c(topics.get(p.targetId)) };
};
wbLinkPathD = (type, s, t, caps, width, bend) => `M${s.x} ${s.y} Q${(s.x + t.x) / 2 + bend.x} ${(s.y + t.y) / 2 + bend.y} ${t.x} ${t.y}`;
wbFmtState = {};
wbLayoutLinkLabel = () => {};
let writes = [];
function group(id) {
  const part = () => ({ attrs: {}, setAttribute(k, v) { this.attrs[k] = v; writes.push(id); }, getAttribute(k) { return this.attrs[k]; } });
  const path = part();
  const hitbox = part();
  return {
    id, isConnected: true, attrs: {}, path, hitbox,
    setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; },
    querySelector: (sel) => (sel === ".sketch-path" ? path : sel === ".sketch-hitbox" ? hitbox : null),
  };
}
const LINKS = { a: [2, 3, {}], b: [3, 4, { bend: { x: 14, y: -9 } }], c: [1, 4, {}], d: [4, 2, { sourceAnchor: { x: 0.5, y: 1 } }] };
function pairs() {
  return Object.entries(LINKS).map(([id, [s, t, more]]) => {
    const parsed = { type: "link-curved", sourceId: s, targetId: t, sourceKind: "object", targetKind: "object", ...more };
    //: As the branch layer leaves them (`wbMapDragLayer.open`): the group, found in one walk, and not its paths.
    return { sketch: { id, data: JSON.stringify(parsed) }, parsed, el: group(id) };
  });
}
//: The numbers a link shows: its path's, moved by its group's translate.
const nums = (d) => (String(d).match(/-?\d*\.?\d+(?:e-?\d+)?/gi) || []).map(Number);
function shown(el, part) {
  const m = /translate\((-?[\d.e-]+) (-?[\d.e-]+)\)/.exec(el.attrs.transform || "");
  const [tx, ty] = m ? [Number(m[1]), Number(m[2])] : [0, 0];
  return nums(el[part].attrs.d).map((v, i) => v + (i % 2 ? ty : tx));
}
//: A drop of the branch 1 to 4 by `dx, dy`, as the layer leaves it: each link drawn where the
//: branch was and carrying the drag's translate, the topics at their new places.
function drop(dx, dy) {
  for (const t of topics.values()) if (t.id === 5) continue; else { t.x -= dx; t.y -= dy; }
  const list = pairs();
  wbUpdateLinkedSketches(null, list.map((p) => ({ ...p })));  // drawn by earlier passes, which kept their own paths
  for (const t of topics.values()) if (t.id !== 5) { t.x += dx; t.y += dy; }
  for (const p of list) p.el.setAttribute("transform", `translate(${dx} ${dy})`);
  writes = [];
  const layer = {
    stay: null, home: [], el: { parentNode: null, remove() {} }, edges: { parentNode: null, children: [], remove() {} },
    sizes: new Map(), innerEdges: [], links: list, grabbed: { id: 1 }, dx, dy,
  };
  wbMapDragLayer.close({ layer });
  const drawnAtDrop = [...new Set(writes)];
  //: The full redraw, on fresh elements, from the topics' new places.
  const full = pairs();
  wbUpdateLinkedSketches(null, full);
  const want = Object.fromEntries(full.map((p) => [p.sketch.id, { path: p.el.path.attrs.d, hitbox: p.el.hitbox.attrs.d }]));
  const off = (p) => {
    let worst = 0;
    for (const part of ["path", "hitbox"]) {
      const a = shown(p.el, part);
      const b = nums(want[p.sketch.id][part]);
      if (!a.length || a.length !== b.length) return Infinity;
      a.forEach((v, i) => { worst = Math.max(worst, Math.abs(v - b[i])); });
    }
    return worst;
  };
  return { list, want, drawnAtDrop, off };
}
"""


#: One printed tenth, the most a held ribbon's number can differ from a fresh one's.
TENTH = 0.1 + 1e-9


def run(body: str):
    with tempfile.TemporaryDirectory() as tmp:
        files = {name: Path(tmp) / name for name in ("h.js", "map.js", "drag.js", "body.js")}
        files["h.js"].write_text(HARNESS, encoding="utf-8")
        files["map.js"].write_text(frontend_text("whiteboard-map.js"), encoding="utf-8")
        files["drag.js"].write_text(frontend_text("whiteboard-drag.js"), encoding="utf-8")
        files["body.js"].write_text(SCENE + body, encoding="utf-8")
        out = subprocess.run(["node", *(str(files[n]) for n in ("h.js", "map.js", "drag.js", "body.js"))], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


@needs_node
def test_a_whole_tenth_drop_holds_the_plain_links_and_each_shows_the_full_redraw() -> None:
    got = run(
        """
        const r = drop(37, -12.3);
        const atDrop = Object.fromEntries(r.list.map((p) => [p.sketch.id, { off: r.off(p), held: wbMapDragLayer.held.has(p.el), transform: p.el.attrs.transform || null }]));
        wbMapDragLayer.settle();
        const settled = Object.fromEntries(r.list.map((p) => [p.sketch.id, {
          same: p.el.path.attrs.d === r.want[p.sketch.id].path && p.el.hitbox.attrs.d === r.want[p.sketch.id].hitbox,
          transform: p.el.attrs.transform || null,
        }]));
        __out({ drawnAtDrop: r.drawnAtDrop, atDrop, settled, left: wbMapDragLayer.held.size });
        """
    )
    #: The bent link is drawn at the drop; the three plain ones (one with a port) are not.
    assert got["drawnAtDrop"] == ["b"]
    for link, row in got["atDrop"].items():
        assert row["off"] <= (TENTH if row["held"] else 0), (link, row)
    assert {k: v["held"] for k, v in got["atDrop"].items()} == {"a": True, "b": False, "c": True, "d": True}
    assert got["atDrop"]["b"]["transform"] is None
    #: Settled, every path is the full redraw's string and no translate is left.
    assert got["settled"] == {k: {"same": True, "transform": None} for k in "abcd"}
    assert got["left"] == 0


@needs_node
def test_a_drop_off_the_tenth_draws_every_link_now() -> None:
    got = run(
        """
        const r = drop(12.34, 5.5);
        __out({ drawn: r.drawnAtDrop.sort(), off: r.list.map(r.off), transforms: r.list.map((p) => p.el.attrs.transform || null), held: wbMapDragLayer.held.size });
        """
    )
    assert got == {"drawn": ["a", "b", "c", "d"], "off": [0, 0, 0, 0], "transforms": [None] * 4, "held": 0}


@needs_node
def test_a_held_link_redrawn_or_rendered_loses_its_translate() -> None:
    got = run(
        """
        const r = drop(40, 20);
        const [a, , c] = r.list;
        //: Its next writer (a drag of one of its ends) draws it from where the topics are, untranslated.
        wbUpdateLinkedSketches(null, [a]);
        const redrawn = { transform: a.el.attrs.transform || null, same: a.el.path.attrs.d === r.want.a.path, held: wbMapDragLayer.held.has(a.el) };
        //: A render writes every path itself, so it only takes the translates off.
        wbMapDragLayer.release();
        __out({ redrawn, rendered: c.el.attrs.transform || null, held: wbMapDragLayer.held.size });
        """
    )
    assert got == {"redrawn": {"transform": None, "same": True, "held": False}, "rendered": None, "held": 0}


@needs_node
def test_a_link_carrying_a_connectors_end_is_drawn_at_the_drop() -> None:
    got = run(
        """
        wbState.sketches = [{ id: "e", data: JSON.stringify({ type: "link-straight", sourceEdge: { id: "a", t: 0.5 } }) }];
        wbFmtState.linkEdge = { dependents: (id) => (id === "a" ? [{}] : []), follow() {} };
        const r = drop(40, 20);
        __out({ drawn: r.drawnAtDrop.sort(), off: r.list.map(r.off) });
        """
    )
    assert got["drawn"] == ["a", "b"]
    assert got["off"][:2] == [0, 0]
    assert max(got["off"]) <= TENTH


@needs_node
def test_over_many_drops_a_held_link_is_within_a_tenth_and_settles_to_the_full_redraw() -> None:
    got = run(
        """
        let worst = 0, numbers = 0, unequal = 0, held = 0;
        for (let k = 0; k < 200; k++) {
          const r = drop(((k * 37) % 113) - 56 + (k % 3) / 10, ((k * 53) % 97) - 48);
          for (const p of r.list) {
            held += wbMapDragLayer.held.has(p.el) ? 1 : 0;
            worst = Math.max(worst, r.off(p));
            numbers += nums(p.el.path.attrs.d).length;
          }
          wbMapDragLayer.settle();
          for (const p of r.list) {
            if (p.el.path.attrs.d !== r.want[p.sketch.id].path || p.el.hitbox.attrs.d !== r.want[p.sketch.id].hitbox || p.el.attrs.transform) unequal += 1;
          }
        }
        __out({ worst, numbers, unequal, held, left: wbMapDragLayer.held.size });
        """
    )
    assert got["held"] == 600, got
    assert got["numbers"] > 100_000, got
    assert got["worst"] <= TENTH, got
    assert got["unequal"] == 0, got
    assert got["left"] == 0


def test_the_render_the_export_and_a_press_settle_what_the_drop_held() -> None:
    board = frontend_text("whiteboard.js")
    render = board[board.index("function renderWhiteboard() {"):]
    assert re.match(r"function renderWhiteboard\(\) \{\s*if \(wbMapDragLayer\.live\) wbMapDragLayer\.close\(\);\s*wbPruneSelection\(\);\s*wbMapDragLayer\.release\(\);", render)
    exported = frontend_text("whiteboard-export.js")
    assert re.search(r"wbMapDragLayer\.settle\(\);\s*const look = wbExportLook\(\);", exported)
    layer = frontend_text("whiteboard-map.js")
    assert 'for (const type of ["pointerdown", "keydown"]) document.addEventListener(type, () => wbMapDragLayer.settle(), true);' in layer
    drag = frontend_text("whiteboard-drag.js")
    redraw = drag[drag.index("function wbUpdateLinkedSketches("):]
    assert redraw.index('if (entry.el && wbMapDragLayer.held.delete(entry.el)) entry.el.removeAttribute("transform");') < redraw.index('entry.path?.setAttribute("d", pathData);')
