"""A radial map with more than one top-level topic keeps them apart (boardfix-1108).

Measured in Chromium on a map with four top-level topics (Enter on the central
topic adds another one): in the Radial layout all four sat at radius 0, so
every pair overlapped by a whole box (6 overlapping pairs of 10 boxes, each
187 x 41 to 187 x 52 px); every other layout had 0. Radial puts a single root
at the centre; with several, the virtual root over them takes the centre and
they take the first ring. `wbMapTidyPositions` runs here in node.
"""

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
const WB_MAP_COLUMN_LAYOUTS = new Set(["timeline", "fishbone", "tree-table"]);
function wbMapNodeSize(n) { return { w: 180, h: 40 }; }
function wbMapGapDepth() { return 76; }
function wbMapGapBreadth() { return 16; }
"""


def _functions(source: str) -> str:
    names = [
        "wbTidyFirstWalk", "wbTidyDistance", "wbTidyNextLeft", "wbTidyNextRight", "wbTidyMoveSubtree",
        "wbTidyExecuteShifts", "wbTidyAncestor", "wbTidyApportion", "wbMapTidyPositions", "wbMapLayoutPositions",
    ]
    out = []
    for name in names:
        match = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert match, f"{name} is gone from whiteboard-map.js"
        out.append(match.group(0))
    return "\n".join(out)


def _positions(nodes: list[dict]) -> dict:
    source = frontend_text("whiteboard-map.js")
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
process.stdout.write(JSON.stringify([...pos]));
"""
    run = subprocess.run(["node", "-e", STUBS + _functions(source) + body], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-600:]
    return dict(json.loads(run.stdout))


def _overlaps(pos: dict) -> int:
    boxes = [(p["x"], p["y"], p["x"] + 180, p["y"] + 40) for p in pos.values()]
    count = 0
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            if min(a[2], b[2]) - max(a[0], b[0]) > 2 and min(a[3], b[3]) - max(a[1], b[1]) > 2:
                count += 1
    return count


def test_four_top_level_topics_do_not_stack_on_the_centre():
    nodes = [{"id": i, "parent_id": None, "x": 0, "y": 0} for i in (1, 2, 3, 4)]
    nodes += [{"id": 10, "parent_id": 1, "x": 0, "y": 0}, {"id": 11, "parent_id": 1, "x": 0, "y": 0}, {"id": 12, "parent_id": 3, "x": 0, "y": 0}]
    assert _overlaps(_positions(nodes)) == 0


def test_a_single_root_still_sits_on_the_centre():
    nodes = [{"id": 1, "parent_id": None, "x": 0, "y": 0}, {"id": 2, "parent_id": 1, "x": 0, "y": 0}, {"id": 3, "parent_id": 1, "x": 0, "y": 0}]
    pos = _positions(nodes)
    #: The first root keeps its place, and its children stand on the first ring around it.
    assert (pos[1]["x"], pos[1]["y"]) == (0, 0)
    assert all(abs(pos[i]["x"] - pos[1]["x"]) + abs(pos[i]["y"] - pos[1]["y"]) > 200 for i in (2, 3))
