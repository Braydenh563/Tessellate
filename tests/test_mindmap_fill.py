"""A map topic's fill: one topic, or the topic and everything under it.

The owner's ask: "the option to fill an individual node or have it cascade
to its children as well". The node's colour already paints its edge bar;
the fill is the same colour as a tint across the whole card, so a filled
branch reads as one region.

Stored as `data.fill`, one of three values, and nothing at all by default:

- `self`: this topic is filled; the topics under it are not changed.
- `branch`: this topic and everything under it are filled, including topics
  added to the branch later (the cascade is worked out when the map is
  drawn, the way branch colour is, not written onto every descendant).
- `none`: this one topic stays unfilled inside a filled branch.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WHITEBOARD_JS = ROOT / "frontend" / "js" / "whiteboard.js"
# The map layer is its own file (whiteboard-map.js), loaded before this one.
WHITEBOARD_MAP_JS = ROOT / "frontend" / "js" / "whiteboard-map.js"


def _whiteboard_text() -> str:
    return frontend_text("whiteboard-map.js") + frontend_text("whiteboard.js")
INDEX_HTML = ROOT / "frontend" / "index.html"
MAP_CSS = ROOT / "frontend" / "css" / "07-whiteboard-misc.css"


def _map(client):
    board = client.post(
        "/whiteboard/boards", json={"name": "Fill", "type": "map", "layout": "tree-right"}
    )
    assert board.status_code == 201, board.text
    return board.json()


def _node(client, board_id, text):
    created = client.post(
        f"/whiteboard/boards/{board_id}/nodes",
        json={"kind": "topic", "parent_id": None, "text": text},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_the_fill_is_kept_and_is_a_closed_set(client):
    board = _map(client)
    node = _node(client, board["id"], "A filled topic")

    def put(data):
        return client.put(
            f"/whiteboard/objects/{node['id']}",
            json={
                "kind": node["kind"],
                "board_id": board["id"],
                "data": {**node["data"], **data},
                "x": node["x"],
                "y": node["y"],
                "z": node["z"],
            },
        )

    for value in ("self", "branch", "none"):
        assert put({"fill": value}).status_code == 200
        root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
        assert root["style"]["fill"] == value
    assert put({"fill": None}).status_code == 200
    root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert "fill" not in root["style"]
    assert put({"fill": "tint"}).status_code == 422


def _function_source(name: str) -> str:
    text = _whiteboard_text()
    match = re.search(rf"^function {name}\(.*?^\}}\n", text, re.S | re.M)
    assert match, f"{name} is not in the whiteboard files"
    return match.group(0)


DRIVER = r"""
const node = (id, parent, fill) => ({ id, parent_id: parent, data: fill ? { fill } : {} });
const nodes = [
  node("root", null),
  node("a", "root", "branch"), node("a1", "a"), node("a2", "a", "none"),
  node("a21", "a2"),
  node("b", "root", "self"), node("b1", "b"),
  node("c", "root"), node("c1", "c", "branch"), node("c11", "c1"),
];
const byId = new Map(nodes.map((n) => [n.id, n]));
const childrenOf = new Map();
for (const n of nodes) {
  if (n.parent_id == null) continue;
  if (!childrenOf.has(n.parent_id)) childrenOf.set(n.parent_id, []);
  childrenOf.get(n.parent_id).push(n);
}
const fills = wbMapFills({ byId, childrenOf, roots: [byId.get("root")] });
process.stdout.write(JSON.stringify(Object.fromEntries(fills)));
"""


@pytest.fixture(scope="module")
def fills(tmp_path_factory) -> dict:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("mapfill") / "run.js"
    script.write_text(_function_source("wbMapFills") + DRIVER, encoding="utf-8")
    out = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_a_branch_fill_cascades_and_a_topic_fill_does_not(fills):
    # Nothing set: nothing said (`undefined`, which is where a level's own
    # fill comes in, MINDMAP_PLAN.md decision 39; JSON drops it).
    assert "root" not in fills and "c" not in fills
    # "Fill with its branch": the topic and everything under it, as a tint.
    assert fills["a"] == "tint" and fills["a1"] == "tint"
    # "No fill" inside a filled branch unfills that one topic only; what is
    # under it still belongs to the filled branch.
    assert fills["a2"] is False and fills["a21"] == "tint"
    # "Fill this topic": the topic alone.
    assert fills["b"] == "tint" and "b1" not in fills
    # A cascade can start anywhere down the tree.
    assert fills["c1"] == "tint" and fills["c11"] == "tint"


def test_the_fill_is_offered_in_the_topic_strip_and_drawn_as_a_tint():
    html = INDEX_HTML.read_text(encoding="utf-8")
    select = re.search(r'<select id="wb-map-fill".*?</select>', html, re.S)
    assert select, "the Shape menu has no fill picker"
    values = re.findall(r'<option value="([^"]*)"', select.group(0))
    assert values[:3] == ["", "self", "branch"]

    js = _whiteboard_text()
    keys = re.search(r"const WB_MAP_STYLE_KEYS = \[(.*?)\];", js, re.S).group(1)
    assert '"fill"' in keys, "back to the branch has to drop the fill too"
    assert "wb-map-filled" in js

    css = MAP_CSS.read_text(encoding="utf-8")
    rule = re.search(r"\.wb-map-node\.wb-map-filled \{(.*?)\}", css, re.S)
    assert rule and "var(--wb-branch)" in rule.group(1)
    # A core node's full-colour ground wins over the tint: source order at
    # equal specificity, so the fill rule has to come first.
    assert css.index(".wb-map-node.wb-map-filled {") < css.index(".wb-map-node.wb-map-core {")
