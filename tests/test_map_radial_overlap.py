"""A radial map with big stand-in boxes must not overlap (L376).

Measured in the running app (mapdepth2.js mapbranchstructure): a tree-down branch beside a
fishbone one in a radial map left one pair touching by 6 units. The layout now sizes a
stand-in by its longer side and widens the rings until no two boxes touch. Runs the layout in node.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR
from tests.test_map_radial_roots_1108 import _functions

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

STUBS = """
const WB_MAP_NODE_W = 200, WB_MAP_NODE_H = 44;
const WB_MAP_COLUMN_LAYOUTS = new Set(["timeline", "fishbone", "tree-table"]);
function wbMapNodeSize(n) { return n._block || { w: 200, h: 44 }; }
function wbMapGapDepth() { return 76; }
function wbMapGapBreadth() { return 16; }
"""


def _overlaps(nodes: list[dict]) -> int:
    source = (JS_DIR / "whiteboard-map.js").read_text(encoding="utf-8")
    body = f"""
const NODES = {json.dumps(nodes)};
const byId = new Map(NODES.map((n) => [n.id, n]));
const childrenOf = new Map();
for (const n of NODES) if (n.parent_id != null) {{
  if (!childrenOf.has(n.parent_id)) childrenOf.set(n.parent_id, []);
  childrenOf.get(n.parent_id).push(n);
}}
const index = {{ nodes: NODES, byId, childrenOf, roots: NODES.filter((n) => n.parent_id == null) }};
const pos = wbMapTidyPositions(index, "radial");
const boxes = NODES.map((n) => ({{ ...pos.get(n.id), ...wbMapNodeSize(n) }}));
let pairs = 0;
for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {{
  const a = boxes[i], c = boxes[j];
  if (Math.min(a.x + a.w, c.x + c.w) - Math.max(a.x, c.x) > 1 && Math.min(a.y + a.h, c.y + c.h) - Math.max(a.y, c.y) > 1) pairs++;
}}
process.stdout.write(JSON.stringify(pairs));
"""
    run = subprocess.run(["node", "-e", STUBS + _functions(source) + body], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-600:]
    return json.loads(run.stdout)


@pytest.mark.parametrize("sizes", [
    [(412, 164), (200, 44), (200, 44)],
    [(412, 164), (200, 44), (200, 44), (400, 200)],
    [(200, 44), (412, 164), (200, 44), (200, 44), (300, 160)],
    [(300, 520), (200, 44), (412, 164), (200, 44)],
    [(412, 164), (200, 44), (412, 164), (200, 44), (412, 164)],
])
def test_wide_and_tall_stand_ins_beside_plain_topics_do_not_touch(sizes):
    nodes = [{"id": 1, "parent_id": None, "x": 0, "y": 0}]
    for i, (w, h) in enumerate(sizes, start=2):
        node = {"id": i, "parent_id": 1, "x": 0, "y": 0}
        if (w, h) != (200, 44):
            node["_block"] = {"w": w, "h": h}
        nodes.append(node)
    assert _overlaps(nodes) == 0
