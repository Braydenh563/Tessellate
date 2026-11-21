"""L-mindmap-18: picking up a branch that is most of the board moves the few elements outside it.

mapperf.js measured the first step of a 500-topic branch drag at 200 to 350ms of main-thread CPU,
and a trace put it in one place: `UpdateLayoutTree` after `wbMapDragLayer.open` moved every topic of
the branch into the drag layer. Moving an element restyles it and everything in it, about 50us an
element on this app's stylesheet, so the pick-up was linear in the branch with a big constant.

So when the branch is most of the board, it stays where it is: the board layer and the edge group
carry the drag's translate, the topics outside the branch go into a layer carrying the opposite one,
and anything else in the board layer but the mid-line `+` layer is held still by its own `translate`.
This holds the shape with the layer's own functions in a node `vm` over the small fake DOM of
`test_lag_layout_reads_map_drag.py`: a branch of 40 topics on a board of 42 moves two topics and the
lines outside the branch, not 40; a step is a few writes; the drop puts every element back.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_lag_layout_reads_map_drag import FAKE_DOM, HARNESS, JS

#: A trunk (1) and a loose topic (99) outside the drag; the grabbed topic (2) and 39 topics under
#: it, a chain of three levels. Lines: 1:2 crosses the branch's edge, 1:99 is outside it, the rest
#: are inside. One link joins two topics of the branch, one joins the branch to the trunk.
SCENE = r"""
const topic = (id, parent_id, x, y) => ({ id, parent_id, kind: "topic", x, y, width: 100, height: 40, data: {} });
const items = new Map([[1, topic(1, null, 0, 0)], [99, topic(99, 1, 0, 300)], [2, topic(2, 1, 200, 0)]]);
for (let i = 3; i <= 41; i++) items.set(i, topic(i, i <= 8 ? 2 : i - 6, 200 + 100 * Math.ceil((i - 2) / 6), 40 * i));
const nodeEl = new Map();
for (const [id] of items) { const el = htmlLayer.appendChild(new El("div", "topic-" + id)); el.dataset.id = String(id); el.setAttribute("class", "wb-object wb-object-topic"); nodeEl.set(id, el); }
//: What else the board layer holds: a pin layer, which a staying branch holds still, and the
//: mid-line `+` layer, which rides with it (invisible, and placed again by the drop's render).
const plusLayer = htmlLayer.appendChild(new El("div", "plus-layer"));
plusLayer.setAttribute("class", "wb-map-plus-layer");
plusLayer.appendChild(new El("button", "plus-1:2"));
const pins = htmlLayer.appendChild(new El("div", "pin-layer"));
const edgeOf = new Map();
const edge = (p, c) => {
  const wrap = edgeGroup.appendChild(new El("g", `wrap-${p}:${c}`));
  const el = wrap.appendChild(new El("path", `path-${p}:${c}`));
  const e = { parent: items.get(p), child: items.get(c), el, layout: "tree-right" };
  edgeOf.set(`${p}:${c}`, e);
  return e;
};
for (const [id, o] of items) if (o.parent_id != null) edge(o.parent_id, id);
const link = (id, a, b) => {
  const el = zoom.appendChild(new El("g", "link-" + id));
  return { sketch: { id }, parsed: { sourceId: a, sourceKind: "object", targetId: b, targetKind: "object" }, el };
};
const inLink = link(9, 5, 30), outLink = link(8, 1, 30);
//: A link inside the branch whose group the capture has not found yet: found in one pass over the
//: groups, never by a document query per link.
const lostGroup = zoom.appendChild(new El("g", "link-7"));
lostGroup.dataset.id = "7";
const lost = { sketch: { id: 7 }, parsed: { sourceId: 6, sourceKind: "object", targetId: 12, targetKind: "object" }, el: null };
document.querySelectorAll = (sel) => (/sketch-group/.test(sel) ? [lostGroup] : []);
const queried = [];
const query = document.querySelector;
document.querySelector = (sel) => { queried.push(sel); return query(sel); };
const d = items.get(2);
d._mapEdges = [edgeOf.get("1:2"), ...[...edgeOf.values()].filter((e) => e.parent.id === 2)];
d._linkedSketches = [];
const origin = new Map();
for (const [id, o] of items) {
  if (id === 1 || id === 99 || id === 2) continue;
  const mine = [...edgeOf.values()].filter((e) => e.parent.id === id);
  const linked = id === 5 ? [inLink] : id === 30 ? [inLink, outLink] : id === 6 ? [lost] : [];
  origin.set(`object:${id}`, { kind: "object", id, item: o, x: o.x, y: o.y, el: nodeEl.get(id), mapEdges: mine, linked });
}
origin.branchOf = 2;
const calls = [];
//: The sizes the pick-up measured (`wbCaptureBulkMoveOrigin` fills the cache), and what the drop's
//: line drawing can read of them after the pointerup has emptied it.
wbMapNodeSizeCache = new Map([...items.keys()].map((id) => [id, { w: 100 + id, h: 40 }]));
window.wbUpdateMapEdges = (edges) => { calls.push(["edges", edges.length, [2, 41, 1].map((id) => wbMapNodeSizeCache?.get(id)?.w ?? null)]); };
window.wbUpdateLinkedSketches = (id, pairs) => { calls.push(["links", pairs.map((p) => p.sketch.id)]); };
window.wbItemTransform = (o) => `translate(${o.x}px, ${o.y}px)`;
window.d3 = { zoomTransform: () => ({ k: 2 }) };
//: Every element that changes parent, by name.
const moved = [];
for (const name of ["appendChild", "insertBefore"]) {
  const own = El.prototype[name];
  El.prototype[name] = function (c, ref) { if (c.parentNode !== this || name === "insertBefore") moved.push(c.name); return own.call(this, c, ref); };
}
"""

CASE = r"""
const htmlBefore = htmlLayer.children.map((el) => el.name);
const wrapsBefore = edgeGroup.children.map((el) => el.name).sort();
wbMapDragLayer.open(origin, d, nodeEl.get(2));
const layer = origin.layer;
const openMoves = moved.slice();
const membersHome = [2, ...[...origin.values()].map((e) => e.id)].every((id) => nodeEl.get(id).parentNode === htmlLayer);
const outsideCarried = [1, 99].every((id) => nodeEl.get(id).parentNode === layer.el);
const innerWrapsHome = [...edgeOf.values()].filter((e) => e.parent.id !== 1).every((e) => e.el.parentNode.parentNode === edgeGroup);
const plusHome = plusLayer.parentNode === htmlLayer && pins.parentNode === htmlLayer;
const outerWrapsCarried = ["1:2", "1:99"].every((k) => edgeOf.get(k).el.parentNode.parentNode === layer.edges);
writes.length = 0; moved.length = 0;
for (let i = 1; i <= 3; i++) wbMapDragLayer.move(layer, i * 10, i * 5);
const moveWrites = writes.slice();
const stepMoves = moved.length;
for (const [id, o] of items) if (id !== 1 && id !== 99) o.x += 30, o.y += 15;
writes.length = 0; moved.length = 0;
wbClearMapNodeSizeCache();
wbMapDragLayer.close(origin);
__out({ queried, openMoves, plusHome, plusAfter: [plusLayer.style.translate ?? null, pins.style.translate], membersHome, outsideCarried, innerWrapsHome, outerWrapsCarried, moveWrites, stepMoves, calls,
  crossing: { grabbed: d._mapEdges.map((e) => `${e.parent.id}:${e.child.id}`), links: [...origin.values()].flatMap((e) => e.linked.map((p) => p.sketch.id)) },
  htmlBack: htmlLayer.children.map((el) => el.name).join() === htmlBefore.join(),
  wrapsBack: edgeGroup.children.map((el) => el.name).sort().join() === wrapsBefore.join(),
  layerGone: !layer.el.isConnected && !layer.edges.isConnected && origin.layer === null,
  htmlTranslate: htmlLayer.style.translate, edgeTransform: edgeGroup.getAttribute("transform"),
  baked: [2, 3, 41].map((id) => nodeEl.get(id).style.transform), outsideBaked: nodeEl.get(1).style.transform ?? null,
  inLink: inLink.el.getAttribute("transform") });
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_branch_that_is_most_of_the_board_stays_and_the_rest_is_carried(tmp_path: Path) -> None:
    files = {"dom.js": FAKE_DOM, "case.js": SCENE + CASE, "h.js": HARNESS}
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    out = subprocess.run(
        ["node", str(tmp_path / "h.js"), str(tmp_path / "dom.js"), str(JS / "whiteboard-map.js"), str(tmp_path / "case.js")],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert out.returncode == 0, out.stderr[-3000:]
    got = json.loads(out.stdout)
    # The pick-up moves the two topics outside the branch, the two lines outside it and the two
    # layers it makes: six elements, not the forty of the branch and its thirty-nine lines.
    assert not [n for n in got["openMoves"] if n.startswith("topic-") and n not in ("topic-1", "topic-99")], got["openMoves"]
    assert len(got["openMoves"]) <= 6, got["openMoves"]
    assert got["plusHome"] and not {"plus-layer", "pin-layer"} & set(got["openMoves"]), "never moved"
    assert got["membersHome"] and got["outsideCarried"] and got["innerWrapsHome"] and got["outerWrapsCarried"]
    # A step: the still layer and its edge group take the opposite translate, the board layer takes
    # the drag's in screen pixels (zoom 2), the edge group and the inside link take it in board units.
    assert not [q for q in got["queried"] if "sketch-group" in q], got["queried"]
    assert got["stepMoves"] == 0
    assert len(got["moveWrites"]) == 21, got["moveWrites"]
    assert not [w for w in got["moveWrites"] if w[0].startswith("topic-") or w[1] == "d"], got["moveWrites"]
    assert {tuple(w) for w in got["moveWrites"][-7:]} == {
        ("link-7", "transform", "translate(30 15)"),
        ("pin-layer", "style.translate", "-30px -15px"),
        ("new-div", "style.transform", "translate(-30px, -15px)"), ("new-g", "transform", "translate(-30 -15)"),
        ("html-layer", "style.translate", "60px 30px"), ("edge-group", "transform", "translate(30 15)"),
        ("link-9", "transform", "translate(30 15)")}
    # Only what crosses the branch's edge is still drawn per step.
    assert got["crossing"] == {"grabbed": ["1:2"], "links": [8]}, got["crossing"]
    # Let go: every element back in its place and order, the board layer untranslated, each topic
    # of the branch carrying its own transform at its new place, the inside lines drawn once.
    assert got["htmlBack"] and got["wrapsBack"] and got["layerGone"]
    assert got["htmlTranslate"] == "" and got["plusAfter"] == [None, ""] and got["edgeTransform"] is None
    assert got["baked"] == ["translate(230px, 15px)", "translate(330px, 135px)", "translate(930px, 1655px)"]
    assert got["outsideBaked"] is None and got["inLink"] is None
    # The inside lines are drawn from the sizes measured at the pick-up (a move resizes nothing), not
    # by measuring every topic of the branch again after the pointerup emptied the cache.
    assert ["edges", 39, [102, 141, None]] in got["calls"] and ["links", [9, 7]] in got["calls"], got["calls"]
