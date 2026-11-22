"""The drop of a big branch does no work for what is off screen (mapperf 500, the drop frame).

Letting go of a 500-topic branch drew every one of its 499 inside lines (131ms of a 182ms frame)
and wrote every topic's transform (a style recalc of each, 75ms), with two topics on screen. A line
or topic the cull hides is read by nothing until the cull shows it, so the drop leaves those for the
cull, which draws or places them as they come on. `whiteboard-map.js` (with its pieces) is run in a
node `vm` against fake elements; the wiring in the cull, the render and the export is read.
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
  wbState: { objects: [] },
};
ctx.wbInstances = { container: () => null, layer: () => null, query: () => null, queryAll: () => [] };
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx, { filename: "whiteboard-map.js" });
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), ctx, { filename: "cull.js" });
ctx.__out = (value) => process.stdout.write(JSON.stringify(value));
vm.runInContext(fs.readFileSync(process.argv[4], "utf8"), ctx);
"""

#: Lines drawn as a straight `M L` between the two topics, so a drawn `d` says which topics it read.
SCENE = r"""
wbMapEdgeIsRibbon = () => false;
wbMapEdgePathD = (p, c) => `M${p.x} ${p.y} L${c.x} ${c.y}`;
wbMapLayout = () => "tree-right";
const topics = new Map([[1, { id: 1, x: 0, y: 0 }], [2, { id: 2, x: 100, y: 0 }], [3, { id: 3, x: 100, y: 900 }]]);
wbMapIndex = () => ({ byId: topics });
function line(parentId, childId, culled) {
  const el = { isConnected: true, setAttribute(k, v) { this[k] = v; } };
  el.parentNode = { classList: { contains: (c) => c === "wb-culled" && el.culled } };
  el.culled = culled;
  return { parent: topics.get(parentId), child: topics.get(childId), el, layout: "tree-right" };
}
"""


def run(body: str):
    with tempfile.TemporaryDirectory() as tmp:
        files = {name: Path(tmp) / name for name in ("h.js", "map.js", "cull.js", "body.js")}
        files["h.js"].write_text(HARNESS, encoding="utf-8")
        files["map.js"].write_text(frontend_text("whiteboard-map.js"), encoding="utf-8")
        board = frontend_text("whiteboard.js")
        cull = re.search(r"^wbCullNow\.outside = .*?^\};", board, re.S | re.M)
        assert cull, "wbCullNow.outside is the one box test the cull and the drop share"
        files["cull.js"].write_text("var wbCullNow = {};\n" + cull.group(0) + "\nconst WB_CARD_DEFAULT_SIZE = { w: 250, h: 150 };\n", encoding="utf-8")
        files["body.js"].write_text(SCENE + body, encoding="utf-8")
        out = subprocess.run(["node", *(str(files[n]) for n in ("h.js", "map.js", "cull.js", "body.js"))], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


@needs_node
def test_the_drop_draws_the_lines_on_screen_and_holds_the_rest() -> None:
    got = run(
        """
        const shown = line(1, 2, false);
        const hidden = line(2, 3, true);
        wbUpdateMapEdges([shown, hidden], { onScreen: true });
        const before = { shown: shown.el.d, hidden: hidden.el.d || null, moved: hidden.el._wbMoved, held: wbMapStaleEdges.size };
        //: A render can replace the topics between the drop and the cull: the held line reads the current ones.
        topics.set(3, { id: 3, x: 140, y: 960 });
        wbMapDrawStaleEdges([hidden.el]);
        const after = { hidden: hidden.el.d, held: wbMapStaleEdges.size };
        wbMapDrawStaleEdges([hidden.el]);
        __out({ before, after, again: hidden.el.d });
        """
    )
    assert got["before"] == {"shown": "M0 0 L100 0", "hidden": None, "moved": True, "held": 1}
    assert got["after"] == {"hidden": "M100 0 L140 960", "held": 0}
    assert got["again"] == "M100 0 L140 960"


@needs_node
def test_a_held_line_drawn_any_other_way_is_let_go_and_a_gone_one_is_skipped() -> None:
    got = run(
        """
        const a = line(1, 2, true);
        const b = line(2, 3, true);
        wbUpdateMapEdges([a, b], { onScreen: true });
        a.el.culled = false;
        wbUpdateMapEdges([a]);
        const afterDraw = wbMapStaleEdges.size;
        b.el.isConnected = false;
        wbMapDrawStaleEdges();
        __out({ afterDraw, left: wbMapStaleEdges.size, gone: b.el.d || null });
        """
    )
    assert got == {"afterDraw": 1, "left": 0, "gone": None}


@needs_node
def test_a_staying_drop_places_only_the_topics_on_screen_either_side() -> None:
    """The board stayed and moved by `dx, dy`; a culled topic that is off the cull's ground where it
    was and where it lands is left for the cull, any other topic is placed now."""
    got = run(
        """
        wbItemTransform = (d) => `translate(${d.x}px, ${d.y}px)`;
        wbCullNow.drawn = { x0: -500, x1: 500, y0: -500, y1: 500 };
        const el = (culled) => ({ style: {}, classList: { contains: (c) => c === "wb-culled" && culled } });
        const far = [el(true), { x: 3000, y: 3000, width: 100, height: 40 }];
        const comesFrom = [el(true), { x: 3000, y: 100, width: 100, height: 40 }];
        const onScreen = [el(false), { x: 10, y: 10, width: 100, height: 40 }];
        const layer = {
          stay: { html: { style: {} }, edgeGroup: { removeAttribute() {} }, fixed: [], members: [far, comesFrom, onScreen] },
          home: [], el: { parentNode: null, remove() {} }, edges: { parentNode: null, children: [], remove() {} },
          sizes: new Map(), innerEdges: [], links: [], grabbed: { id: 1 },
        };
        layer.dx = 2950;
        layer.dy = 0;
        wbMapDragLayer.close({ layer });
        const row = ([m]) => ({ transform: m.style.transform || null, later: Boolean(m._wbPlaceLater) });
        __out([far, comesFrom, onScreen].map(row));
        """
    )
    assert got == [
        {"transform": None, "later": True},
        {"transform": "translate(3000px, 100px)", "later": False},
        {"transform": "translate(10px, 10px)", "later": False},
    ]


def test_the_cull_the_render_and_the_export_draw_what_the_drop_left() -> None:
    board = frontend_text("whiteboard.js")
    cull = board[board.index("function wbCullNow("):board.index('window.addEventListener("resize", wbScheduleCull)')]
    assert re.search(r"if \(!cull && el\._wbPlaceLater\) \{\s*el\._wbPlaceLater = false;\s*el\.style\.transform = wbItemTransform\(d\);", cull)
    assert "if (!cull && held.path._wbMoved) wbUpdateMapEdges.drawHeld([held.path]);" in cull
    #: Placed and drawn before the class comes off, so nothing is shown where it was.
    assert cull.index("wbUpdateMapEdges.drawHeld([held.path])") < cull.index('held.wrap.classList.toggle("wb-culled", cull)')
    edges = frontend_text("whiteboard-map-edges.js")
    render = edges[edges.index("function wbRenderMapEdges("):edges.index("function wbMapEdgeKey(")]
    assert "wbMapStaleEdges.delete(held.path);" in render
    move = frontend_text("whiteboard-map.js")
    assert "if (layer.innerEdges.length) wbUpdateMapEdges(layer.innerEdges, { onScreen: true });" in move
    exported = frontend_text("whiteboard-export.js")
    edges_export = exported[exported.index("mapEdges() {"):]
    assert edges_export.index("wbUpdateMapEdges.drawHeld();") < edges_export.index('queryAll(".wb-map-edges .wb-map-edge")')
