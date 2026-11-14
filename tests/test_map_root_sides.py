"""The central topic's children go to the side with fewer (bug sweep
2026-10-12): on a Free map 8 of 8 new children went right, and on "Tree, both
sides" 7 of 8, because a new topic sorts first among its siblings and was
dealt against empty sides. Measured in the app by a Playwright probe after the
fix: 4 and 4 on both layouts, "Tree, to the right" still 8 on the right.
`wbMapFreshPlace` runs here in node with the map's helpers stubbed."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

STUBS = """
const WB_MAP_NODE_W = 200;
let NODES = [];
function wbMapNodeSize(n) { return { w: n.width || 200, h: 40 }; }
function wbMapGapDepth() { return 76; }
function wbMapGapBreadth() { return 16; }
function wbMapIndex() {
  const byId = new Map(NODES.map((n) => [n.id, n]));
  const childrenOf = new Map();
  for (const n of NODES) if (n.parent_id != null) {
    if (!childrenOf.has(n.parent_id)) childrenOf.set(n.parent_id, []);
    childrenOf.get(n.parent_id).push(n);
  }
  return { nodes: NODES, byId, childrenOf, roots: NODES.filter((n) => n.parent_id == null) };
}
function wbMapSubtree(index, id) {
  const out = [index.byId.get(id)];
  for (const kid of index.childrenOf.get(id) || []) out.push(...wbMapSubtree(index, kid));
  return out.filter(Boolean);
}
"""


def _run(body: str):
    source = frontend_text("whiteboard-map.js")
    match = re.search(r"^function wbMapFreshPlace\(row, parent\) \{.*?^\}", source, re.S | re.M)
    assert match, "wbMapFreshPlace is gone from whiteboard-map.js"
    out = subprocess.run(["node", "-e", STUBS + match.group(0) + body], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_root_children_alternate_sides():
    got = _run("""
NODES = [{ id: 1, parent_id: null, x: 400, y: 300, width: 200 }];
const add = (parent, id) => { const row = { id, parent_id: parent.id, x: 0, y: 0, width: 200 }; wbMapFreshPlace(row, parent); NODES.push(row); return row; };
for (let i = 0; i < 8; i++) add(NODES[0], 10 + i);
const kids = NODES.filter((n) => n.parent_id === 1);
const left = kids.filter((k) => k.x + 100 < 500);
const overlap = kids.some((a) => kids.some((b) => a !== b && a.x === b.x && Math.abs(a.y - b.y) < 40));
process.stdout.write(JSON.stringify({ left: left.length, right: kids.length - left.length, overlap }));
""")
    assert got == {"left": 4, "right": 4, "overlap": False}


def test_a_left_branchs_child_still_grows_left_and_a_right_ones_right():
    got = _run("""
NODES = [{ id: 1, parent_id: null, x: 400, y: 300, width: 200 },
         { id: 2, parent_id: 1, x: 124, y: 300, width: 200 }, { id: 3, parent_id: 1, x: 676, y: 300, width: 200 }];
const a = { id: 4, parent_id: 2, x: 0, y: 0, width: 200 }; wbMapFreshPlace(a, NODES[1]);
const b = { id: 5, parent_id: 3, x: 0, y: 0, width: 200 }; wbMapFreshPlace(b, NODES[2]);
process.stdout.write(JSON.stringify([a.x < 124, b.x > 676]));
""")
    assert got == [True, True]
