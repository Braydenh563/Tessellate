"""L-mindmap-17: a branch drag moves one layer, and its move handler reads no layout after it writes.

`scratchpad/ui-sweeps/mapperf.js` measured the map's drag over its CPU budget at every size (median
33/92/247ms a step at 50/200/500 topics against 17), and a profile of a 200-topic branch drag put the
cost in two places: `wbEdgePanTick` read the container's box in the frame after the move had written
every topic's transform, which forced a restyle of the board (1.3s of 2.7s), and every line inside the
branch was rebuilt on every step (`wbMapRibbonD` plus `wbMapSmoothThrough`, 27ms a step) although both
of its ends had moved by the same amount.

So the branch is one layer: its topics are moved into one element that carries the drag's translate,
its inside lines into one SVG group that carries the same translate, and a link with both ends in the
branch is translated rather than re-pathed. Only the lines that cross the branch's edge are drawn
again per step. The structure is held behaviourally where it is cheap to (the layer's own functions,
loaded into a node `vm` over a small fake DOM, and `wbApplyBulkMove` run on its own), and the reads by
source, the way `test_lag_layout_reads_1766.py` holds the rig frame.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
#: whiteboard.js and the files it was split into (whiteboard-items, -stacking, -pointer, -pan, ...).
WB = "\n".join(f.read_text(encoding="utf-8") for f in sorted(JS.glob("whiteboard*.js")) if not f.name.startswith("whiteboard-map"))
MAP = "\n".join(f.read_text(encoding="utf-8") for f in sorted(JS.glob("whiteboard-map*.js")))

#: Everything that makes the browser bring style or layout up to date.
READS = re.compile(
    r"getComputedStyle\(|getBoundingClientRect\(|getClientRects\(|getBBox\(|getComputedTextLength\(|"
    r"\.offset(?:Width|Height|Top|Left)\b|\.client(?:Width|Height|Top|Left)\b|\.scroll(?:Width|Height|Top)\b|"
    r"elementFromPoint\("
)
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(src: str, head: str) -> str:
    start = src.index(head)
    depth = 0
    for i in range(src.index("{", start), len(src)):
        depth += src[i] == "{"
        depth -= src[i] == "}"
        if depth == 0:
            return src[start : i + 1]
    raise AssertionError(head)


def _code(body: str) -> str:
    return "\n".join(line for line in body.splitlines() if not line.strip().startswith("//"))


#: A DOM just big enough for the layer: elements with children, attributes, a style that records its
#: writes, and the two lookups the layer makes. Every write is logged as [element name, what, value].
FAKE_DOM = r"""
var writes = [];
class El {
  constructor(tag, name) { this.tagName = tag; this.name = name || tag; this.children = []; this.parentNode = null; this.attrs = {}; this.dataset = {};
    const self = this;
    this.style = new Proxy({}, { set(o, k, v) { o[k] = v; writes.push([self.name, "style." + String(k), v]); return true; } });
    const cls = new Set();
    this.classList = { add: (c) => cls.add(c), remove: (c) => cls.delete(c), contains: (c) => cls.has(c), toggle: (c, on) => (on ?? !cls.has(c)) ? cls.add(c) : cls.delete(c) };
  }
  get childNodes() { return this.children; }
  get firstChild() { return this.children[0] || null; }
  get nextSibling() { const p = this.parentNode; return p ? p.children[p.children.indexOf(this) + 1] || null : null; }
  get isConnected() { let at = this; while (at.parentNode) at = at.parentNode; return at === root; }
  appendChild(c) { c.remove(); c.parentNode = this; this.children.push(c); return c; }
  insertBefore(c, ref) { if (!ref) return this.appendChild(c); c.remove(); c.parentNode = this; this.children.splice(this.children.indexOf(ref), 0, c); return c; }
  remove() { const p = this.parentNode; if (p) { p.children.splice(p.children.indexOf(this), 1); this.parentNode = null; } }
  setAttribute(k, v) { this.attrs[k] = String(v); writes.push([this.name, k, String(v)]); if (k === "class") for (const c of String(v).split(" ")) this.classList.add(c); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; writes.push([this.name, "-" + k, null]); }
}
var root = new El("root");
var htmlLayer = root.appendChild(new El("div", "html-layer"));
var zoom = root.appendChild(new El("g", "zoom-group"));
var edgeGroup = zoom.appendChild(new El("g", "edge-group"));
edgeGroup.setAttribute("class", "wb-map-edges");
var document = {
  createElement: (tag) => new El(tag, "new-" + tag),
  createElementNS: (ns, tag) => new El(tag, "new-" + tag),
  getElementById: (id) => (id === "wb-html-layer" ? htmlLayer : id === "wb-zoom-group" ? zoom : null),
  querySelector: (sel) => (/wb-map-edges/.test(sel) ? edgeGroup : null),
  querySelectorAll: () => [],
  addEventListener() {},
};
//: The board's own lookups go through the active instance (test_wb_instances), here the fake page.
var wbInstances = { query: (sel) => (sel === "#wb-html-layer" ? htmlLayer : document.querySelector(sel)), queryAll: (sel) => document.querySelectorAll(sel), container: () => root };
"""

#: A trunk (1) outside the drag, the grabbed topic (2), and its branch: 3 and 4 under 2, 5 under 3.
#: Lines: 1:2 crosses the branch's edge, 2:3, 2:4 and 3:5 are inside it. One link joins 4 and 5 (both
#: in the branch), one joins 1 and 5 (across its edge).
SCENE = r"""
const topic = (id, parent_id, x, y) => ({ id, parent_id, kind: "topic", x, y, width: 100, height: 40, data: {} });
const items = new Map([[1, topic(1, null, 0, 0)], [2, topic(2, 1, 200, 0)], [3, topic(3, 2, 400, -60)], [4, topic(4, 2, 400, 60)], [5, topic(5, 3, 600, -60)]]);
const nodeEl = new Map();
for (const [id] of items) { const el = htmlLayer.appendChild(new El("div", "topic-" + id)); el.dataset.id = String(id); el.setAttribute("class", "wb-object wb-object-topic"); nodeEl.set(id, el); }
const edge = (p, c) => {
  const wrap = edgeGroup.appendChild(new El("g", `wrap-${p}:${c}`));
  const el = wrap.appendChild(new El("path", `path-${p}:${c}`));
  return { parent: items.get(p), child: items.get(c), el, layout: "tree-right" };
};
const e12 = edge(1, 2), e23 = edge(2, 3), e24 = edge(2, 4), e35 = edge(3, 5);
const link = (id, a, b) => {
  const el = zoom.appendChild(new El("g", "link-" + id));
  return { sketch: { id }, parsed: { sourceId: a, sourceKind: "object", targetId: b, targetKind: "object" }, el };
};
const l45 = link(9, 4, 5), l15 = link(8, 1, 5);
const d = items.get(2);
d._mapEdges = [e12, e23, e24];
d._linkedSketches = [];
const origin = new Map();
const entry = (id, mapEdges, linked) => origin.set(`object:${id}`, { kind: "object", id, item: items.get(id), x: items.get(id).x, y: items.get(id).y, el: nodeEl.get(id), mapEdges, linked });
entry(3, [e23, e35], []);
entry(4, [e24], [l45]);
entry(5, [], [l45, l15]);
origin.branchOf = 2;
const calls = [];
window.wbUpdateMapEdges = (edges) => { calls.push(["edges", edges.map((e) => `${e.parent.id}:${e.child.id}`)]); for (const e of edges) e.el.setAttribute("d", "M0 0"); };
window.wbUpdateLinkedSketches = (id, pairs) => { calls.push(["links", pairs.map((p) => p.sketch.id)]); };
window.wbItemTransform = (o) => `translate(${o.x}px, ${o.y}px)`;
"""

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const ctx = {
  console, Math, Number, Object, Set, Map, JSON, Date, Array, String, RegExp, Promise, Boolean, Proxy, Error,
  setTimeout: () => 0, clearTimeout() {}, addEventListener() {}, requestAnimationFrame: () => 0,
  onSurface() {},
  MD_RUN_FONTS: { serif: "s", mono: "m", wide: "w" },
  wbState: { objects: [] },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), ctx, { filename: "whiteboard-map.js" });
ctx.__out = (value) => process.stdout.write(JSON.stringify(value));
vm.runInContext(fs.readFileSync(process.argv[4], "utf8"), ctx);
"""


def _run(tmp_path: Path, body: str) -> dict:
    files = {"dom.js": FAKE_DOM, "case.js": SCENE + body, "h.js": HARNESS}
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    out = subprocess.run(
        ["node", str(tmp_path / "h.js"), str(tmp_path / "dom.js"), str(JS / "whiteboard-map.js"), str(tmp_path / "case.js")],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert out.returncode == 0, out.stderr[-3000:]
    return json.loads(out.stdout)


@needs_node
def test_a_branch_drag_moves_its_topics_and_inside_lines_as_one_layer(tmp_path: Path) -> None:
    got = _run(tmp_path, r"""
      wbMapDragLayer.open(origin, d, nodeEl.get(2));
      const layer = origin.layer;
      const parents = [2, 3, 4, 5].map((id) => nodeEl.get(id).parentNode === layer.el);
      const wrapsIn = [e23, e24, e35].map((e) => e.el.parentNode.parentNode === layer.edges);
      const outsideStays = e12.el.parentNode.parentNode === edgeGroup && nodeEl.get(1).parentNode === htmlLayer;
      writes.length = 0; calls.length = 0;
      for (let i = 1; i <= 3; i++) wbMapDragLayer.move(layer, i * 10, i * 5);
      const moveWrites = writes.slice();
      // What is left for the drag to draw per step: the lines and links that cross the branch's edge.
      const crossing = { grabbed: d._mapEdges.map((e) => `${e.parent.id}:${e.child.id}`),
        members: [...origin.values()].flatMap((e) => e.mapEdges.map((x) => `${x.parent.id}:${x.child.id}`)),
        links: [...origin.values()].flatMap((e) => e.linked.map((p) => p.sketch.id)).concat(d._linkedSketches.map((p) => p.sketch.id)) };
      for (const [id] of items) if (id !== 1) items.get(id).x += 30, items.get(id).y += 15;
      writes.length = 0;
      wbMapDragLayer.close(origin);
      __out({ parents, wrapsIn, outsideStays, moveWrites, crossing, closeCalls: calls,
        back: [2, 3, 4, 5].map((id) => nodeEl.get(id).parentNode === htmlLayer),
        baked: [2, 3, 4, 5].map((id) => nodeEl.get(id).style.transform),
        wrapsBack: [e23, e24, e35].map((e) => e.el.parentNode.parentNode === edgeGroup),
        layerGone: !layer.el.isConnected && !layer.edges.isConnected && origin.layer === null,
        linkTransform: l45.el.getAttribute("transform") });
    """)
    assert all(got["parents"]), "every topic of the branch, the grabbed one included, is in the one layer"
    assert all(got["wrapsIn"]), "every line with both ends in the branch is in the one edge group"
    assert got["outsideStays"], "the line to the trunk and the trunk itself stay where they are"
    # A step is the layer's translate, the edge group's and the inside link's: three writes, no path.
    names = sorted({w[0] for w in got["moveWrites"]})
    assert len(got["moveWrites"]) == 9, got["moveWrites"]
    assert not [w for w in got["moveWrites"] if w[1] == "d"], "a line inside the branch is translated, never re-pathed"
    assert not [w for w in got["moveWrites"] if w[0].startswith("topic-")], "no topic's own transform is written per step"
    assert "link-9" in names and "link-8" not in names
    assert {tuple(w) for w in got["moveWrites"][-3:]} == {
        ("new-div", "style.transform", "translate(30px, 15px)"), ("new-g", "transform", "translate(30 15)"), ("link-9", "transform", "translate(30 15)")}
    # Only what crosses the branch's edge is still drawn per step.
    assert got["crossing"] == {"grabbed": ["1:2"], "members": [], "links": [8]}, got["crossing"]
    # Let go: each topic gets its own transform back at its new place, the lines are drawn once there.
    assert all(got["back"]) and all(got["wrapsBack"]) and got["layerGone"]
    assert got["baked"] == ["translate(230px, 15px)", "translate(430px, -45px)", "translate(430px, 75px)", "translate(630px, -45px)"]
    assert sorted(sorted(c[1]) for c in got["closeCalls"] if c[0] == "edges") == [["2:3", "2:4", "3:5"]]
    assert [c for c in got["closeCalls"] if c[0] == "links"] and got["linkTransform"] is None


@needs_node
def test_the_layer_keeps_the_topics_in_their_order(tmp_path: Path) -> None:
    got = _run(tmp_path, r"""
      const before = htmlLayer.children.map((el) => el.name);
      wbMapDragLayer.open(origin, d, nodeEl.get(2));
      wbMapDragLayer.close(origin);
      __out({ before, after: htmlLayer.children.map((el) => el.name) });
    """)
    assert got["before"] == got["after"]


def test_the_bulk_move_writes_no_member_while_the_layer_carries_them() -> None:
    body = _code(_fn(WB, "function wbApplyBulkMove("))
    # The data still moves (the drop, the cull and the drop target read it); the elements do not.
    assert "entry.item.x = entry.x + dx;" in body
    layer_at = body.index("if (origin.layer)")
    assert layer_at < body.index("el.style.transform = wbItemTransform(entry.item)")
    assert "wbMapDragLayer.move(origin.layer, dx, dy)" in body


def test_the_grabbed_topic_rides_the_layer_and_the_layer_is_closed_before_anything_draws() -> None:
    move = _code(_fn(WB, "function objDragMove("))
    assert "wbMapDragLayer.open(d._bulkOrigin, d, " in move
    assert re.search(r"if \(!d\._bulkOrigin\?\.layer\) d3\.select\(this\.closest\(\"\.wb-object\"\)\)\.style\(\"transform\"", move)
    assert "origin.branchOf = d.id;" in _code(_fn(MAP, "function wbMapBranchDragOrigin("))
    end = _code(_fn(WB, "async function objDragEnd("))
    assert end.index("wbMapDragLayer.close(") < end.index("wbTrashTake(")
    # A render while the layer is open would place every member a second time, on top of the layer's
    # own translate: it closes the layer first.
    head = [line.strip() for line in _code(WB[WB.index("function renderWhiteboard() {") :][:600]).splitlines()]
    assert head[1] == "if (wbMapDragLayer.live) wbMapDragLayer.close();", head[:3]


def test_no_layout_read_follows_a_write_on_the_move_path() -> None:
    move = _code(_fn(WB, "function objDragMove("))
    first_write = move.index('.style("transform"')
    assert not READS.search(move[first_write:]), READS.search(move[first_write:]).group(0)
    for src, head in (
        (WB, "function wbApplyBulkMove("),
        (MAP, "  move(layer, dx, dy) {"),
        (MAP, "function wbUpdateMapEdges("),
        (WB, "function wbTranslateSelectionChrome("),
        (MAP, "function wbMapDropTargetAt("),
        (MAP, "function wbMapSiblingSlotAt("),
        (WB, "function wbScheduleCull("),
        # The edge pan's frame runs after the move's writes: the box it needs is the gesture's own.
        (WB, "function wbEdgePanTick("),
    ):
        body = _code(_fn(src, head))
        assert not READS.search(body), f"{head}: {READS.search(body).group(0)}"
    assert "wbCanvasOriginRect()" in _code(_fn(WB, "function wbEdgePanTick("))
    # The gesture's box, measured at the press, before the first move writes anything.
    assert "wbCanvasOrigin();" in _code(_fn(WB, "function objDragStart("))


def test_a_zoom_step_draws_the_transform_and_settles_once() -> None:
    """L-mindmap-17: a zoom is a transform while it moves and one full redraw when it settles.

    The grips' inverse scale re-styles every grip (70 to 180ms at 500 topics)
    and fired inside a slow pinch whenever two steps were over 120ms apart;
    the cull hid and showed margin edges on steps that drew nothing new.
    """
    frame = _code(_fn(WB, "function wbZoomFrameWork("))
    assert "wbCullNow(t, size, scaling);" in frame
    assert "if (scaling) wbZoomSettle();" in frame
    settle = _code(_fn(WB, "function wbZoomSettle("))
    assert "setTimeout(() => wbCullNow(), wbZoomSettle.ms)" in settle
    sync = _code(_fn(WB, "function wbSyncGridToTransform("))
    assert "wbPublishInvZoom(el, inv, inst), wbZoomSettle.ms)" in sync
    cull = _code(_fn(WB, "function wbCullNow("))
    # The skip comes before any class is toggled, and the ground drawn is kept for the next step.
    assert cull.index("if (unlessDrawn && drawn") < cull.index("classList.toggle")
    assert "wbCullNow.drawn = { x0, x1, y0, y1 };" in cull


def test_the_zoom_number_does_not_resize_its_dock() -> None:
    """L-mindmap-17: "85%" to "100%" resized the zoom dock, whose width is published on the
    board's section (`--wb-w-zoom`), so the zoom step that crossed it restyled the whole board
    (250 to 400ms at 500 topics). The field holds the width of its widest value.
    """
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    rule = css.split(".whiteboard-floating-panel .wb-zoom-level .value-field-input {", 1)[1].split("}", 1)[0]
    assert "min-width: 5ch;" in rule
    assert "wbPanelMetricsRoot.style.setProperty(`--wb-w-${name}`" in WB
