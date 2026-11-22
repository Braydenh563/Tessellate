"""The first drag of a topic pins it without a render (L-mindmap-26, mapperf 500).

Pinning a dragged topic scheduled a full render, which redrew every line the drop had moved: 93ms
at 500 topics, landing in the first frame of the next gesture (the branch pick-up, 162.6ms). The
pin is one class on the topic, and the only other thing that render placed was the moved topics'
mid-line `+` buttons. `whiteboard-map.js` runs in a node `vm` against fakes.
"""

from __future__ import annotations

import json
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
ctx.__out = (value) => process.stdout.write(JSON.stringify(value));
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), ctx);
"""

SCENE = r"""
const log = { renders: 0, saved: [], pluses: null, classes: [] };
wbIsMap = () => true;
wbSaveObject = async (d) => { log.saved.push([d.id, d.data.pinned]); };
wbScheduleRender = () => { log.renders += 1; };
renderWhiteboard = renderWhiteboardNow = () => { log.renders += 1; };
wbItemElement = (kind, id) => ({ classList: { add: (c) => log.classes.push([kind, id, c]) } });
wbRenderMapEdges = (opts) => { log.pluses = { plusesOnly: opts.plusesOnly, only: opts.only ? [...opts.only].sort() : null }; };
"""


def run(body: str):
    with tempfile.TemporaryDirectory() as tmp:
        files = {name: Path(tmp) / name for name in ("h.js", "map.js", "body.js")}
        files["h.js"].write_text(HARNESS, encoding="utf-8")
        files["map.js"].write_text(frontend_text("whiteboard-map.js"), encoding="utf-8")
        files["body.js"].write_text(SCENE + body, encoding="utf-8")
        out = subprocess.run(["node", *(str(files[n]) for n in ("h.js", "map.js", "body.js"))], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


@needs_node
def test_a_first_drag_pins_the_topic_without_a_render() -> None:
    got = run(
        """
        const d = { id: 1, kind: "topic", data: {} };
        const origin = new Map([["object:2", { kind: "object", item: { id: 2 } }], ["object:3", { kind: "object", item: { id: 3 } }]]);
        wbMapPinOnDrag(d, origin).then(() => __out(log));
        """
    )
    assert got["renders"] == 0, "the pin is one class: a render redraws every moved line (93ms at 500 topics)"
    assert got["saved"] == [[1, True]]
    assert got["classes"] == [["object", 1, "wb-map-pinned"]]
    assert got["pluses"] == {"plusesOnly": True, "only": [1, 2, 3]}


@needs_node
def test_a_solo_drag_places_its_own_pluses_and_a_pinned_topic_does_nothing() -> None:
    got = run(
        """
        const d = { id: 7, kind: "topic", data: {} };
        wbMapPinOnDrag(d).then(async () => {
          const first = { ...log };
          log.pluses = null;
          await wbMapPinOnDrag(d);
          __out({ first, again: { saved: log.saved.length, pluses: log.pluses, renders: log.renders } });
        });
        """
    )
    assert got["first"]["pluses"]["only"] == [7]
    assert got["again"] == {"saved": 1, "pluses": None, "renders": 0}


def test_the_drop_hands_its_branch_to_the_pin() -> None:
    items = frontend_text("whiteboard-items.js")
    assert "if (primary) await wbMapPinOnDrag(d, bulkOrigin);" in items


def test_pluses_only_places_the_buttons_and_draws_no_line() -> None:
    edges = frontend_text("whiteboard-map-edges.js")
    head = edges.index("function wbRenderMapEdges({ only = null, plusesOnly = false } = {})")
    early = edges[head : edges.index("const zoomGroup", head)]
    assert "wbRenderMapEdgePluses(wbMapVisibleEdges(index, wbMapConcealed(index)), wbMapLayout(), only);" in early
    assert "return;" in early
