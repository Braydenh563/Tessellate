"""K15: a mind map template builds what its picture shows.

The owner: "these templates look great! but what the templates actually give
isnt accurate and doesnt fit what the previews look like" (Career plan's
preview: a root box over four chevron topics, each with two bars). The
picture and the map now read one source: the template's own `payload.root`
and each node's `data.shape`, so this holds them to the file, and the file
to the preview's shape word.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api.routes_whiteboard import BOARD_LAYOUTS, MAP_LEVEL_FIELDS

ROOT = Path(__file__).resolve().parents[1]
MAPS = json.loads((ROOT / "frontend" / "board-library" / "maps.json").read_text(encoding="utf-8"))["items"]
#: What each preview word draws: its centre, its branches, everything under them.
LOOK = {
    "radial": ("ellipse", "pill", "none"),
    "two-sided": ("pill", "pill", "none"),
    "fishbone": ("rounded", "rounded", "none"),
    "fork": ("rounded", "rounded", "none"),
    "phases": ("rounded", "chevron", "underline"),
    "tiers": ("rounded", "rounded", "underline"),
    "tree": ("rounded", "rounded", "underline"),
}


def _walk(nodes, depth=1):
    for n in nodes:
        yield depth, n
        yield from _walk(n["children"], depth + 1)


@pytest.mark.parametrize("entry", MAPS, ids=[m["key"] for m in MAPS])
def test_a_template_stores_its_layout_and_its_topic_shapes(entry):
    root, branch, leaf = LOOK[entry["shape"]]
    assert entry["layout"] in BOARD_LAYOUTS
    assert entry["payload"]["root"] == {"shape": root}
    for depth, node in _walk(entry["payload"]["nodes"]):
        assert node["data"]["shape"] == (branch if depth == 1 else leaf), (entry["key"], node["text"])


def test_chevron_and_underline_are_topic_shapes_a_map_can_hold():
    assert {"chevron", "underline"} <= MAP_LEVEL_FIELDS["shape"]


@pytest.mark.parametrize("key", ["career-map", "brainstorm", "causes", "meeting", "pros-cons"])
def test_a_new_map_from_a_template_builds_the_preview(ai_client, key):
    entry = next(m for m in MAPS if m["key"] == key)
    out = ai_client.post("/board-library/new-board", json={"builtin": f"maps/{key}", "name": "Built"})
    assert out.status_code == 201, out.text
    assert out.json()["layout"] == entry["layout"]
    rows = ai_client.get(f"/whiteboard/?board_id={out.json()['id']}").json()["objects"]
    by_id = {r["id"]: r for r in rows}
    centre = next(r for r in rows if r["parent_id"] is None)
    root, branch, leaf = LOOK[entry["shape"]]
    assert centre["data"]["shape"] == root
    kids: dict[int, list] = {}
    for r in rows:
        kids.setdefault(r["parent_id"], []).append(r)
    branches = sorted(kids[centre["id"]], key=lambda r: r["id"])
    assert [b["data"]["content"] for b in branches] == [n["text"] for n in entry["payload"]["nodes"]]
    for b, node in zip(branches, entry["payload"]["nodes"]):
        assert b["data"]["shape"] == branch
        assert len(kids.get(b["id"], [])) == len(node["children"])
        assert all(c["data"]["shape"] == leaf for c in kids.get(b["id"], []))
    assert len(by_id) == 1 + sum(1 for _ in _walk(entry["payload"]["nodes"]))


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_picture_draws_the_shapes_the_template_stores():
    """Chevron branches are paths with a point, plain leaves are dots, an
    underline is a thin bar: the picture reads the same data the map does."""
    source = (ROOT / "frontend" / "js" / "whiteboard-templates.js").read_text(encoding="utf-8")
    bodies = []
    for name in ["wbThumbRound", "wbThumbLook", "wbThumbShapePart", "wbMapThumbSpec"]:
        match = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert match, name
        bodies.append(match.group(0))
    script = "\n".join(bodies) + f"\nprocess.stdout.write(JSON.stringify({json.dumps(MAPS)}.map((m) => wbMapThumbSpec(m))));"
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    for entry, spec in zip(MAPS, out):
        _, branch, leaf = LOOK[entry["shape"]]
        parts = spec["parts"]
        nodes = [p for p in parts if "wb-thumb-node" in p["cls"].split()]
        if branch == "chevron":
            assert nodes and all(p["tag"] == "path" for p in nodes), entry["key"]
        if leaf == "none" and entry["shape"] != "fishbone":  # a fishbone draws ticks, not dots
            assert any(p["tag"] == "circle" for p in parts), entry["key"]
        if leaf == "underline":
            assert any(p["tag"] == "rect" and p["a"]["height"] == 1.2 for p in parts), entry["key"]


def test_a_new_map_is_not_fitted_again_after_it_is_framed():
    """The New board dialog fitted every board after opening it, which undid
    `wbFrameMapOnOpen`'s fallback for a map too wide to read: Career plan
    opened at 17% on a phone (measured 390x844, 12 topics, words 2px high)
    instead of at 1:1 on its root. A map frames itself; only a board is fitted."""
    text = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    start = text.index('if (board.type === "map") await wbMapTidyFresh();')
    tail = text[start : start + 400]
    fit = tail.index("wbZoomToFit({ animate: false })")
    assert 'board.type !== "map"' in tail[:fit], tail
