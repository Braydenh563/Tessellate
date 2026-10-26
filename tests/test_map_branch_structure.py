"""A structure per branch (INBOX 797, canvasdepth2; MINDMAP_PLAN "canvasdepth,
ranked" row 1, XMind's). A topic's `data.branch_layout` lays the branch under
it out as that layout inside the map's own; stored and exported like a
boundary. The browser half, overlap and lines measured, is
`scratchpad/ui-sweeps/mapdepth2.js mapbranchstructure`."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _body(src: str, name: str) -> str:
    start = src.index(name)
    return src[start : src.index("\n}\n", start)]


def _map(client) -> tuple[int, dict]:
    made = client.post(
        "/whiteboard/boards/import",
        json={"format": "markdown", "content": "# M\n- Root\n  - Branch\n    - Leaf", "name": "Structured"},
    ).json()
    tree = client.get(f"/whiteboard/boards/{made['id']}/tree").json()
    return made["id"], tree


def test_a_branch_layout_is_stored_refused_when_unknown_and_exported(ai_client):
    board_id, _ = _map(ai_client)
    state = ai_client.get("/whiteboard/", params={"board_id": board_id}).json()
    branch = next(o for o in state["objects"] if o["data"].get("content") == "Branch")
    body = {k: branch[k] for k in ("kind", "x", "y", "width", "height", "parent_id", "board_id")}
    ok = ai_client.put(f"/whiteboard/objects/{branch['id']}", json={**body, "data": {**branch["data"], "branch_layout": "tree-down"}})
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["branch_layout"] == "tree-down"
    bad = ai_client.put(f"/whiteboard/objects/{branch['id']}", json={**body, "data": {**branch["data"], "branch_layout": "spiral"}})
    assert bad.status_code == 422
    for fmt in ("opml", "freemind"):
        text = ai_client.get(f"/whiteboard/boards/{board_id}/export", params={"format": fmt}).text
        assert '_branch_layout="tree-down"' in text, fmt
        back = ai_client.post("/whiteboard/boards/import", json={"format": fmt, "content": text, "name": "Back"}).json()
        objs = ai_client.get("/whiteboard/", params={"board_id": back["id"]}).json()["objects"]
        assert any(o["data"].get("branch_layout") == "tree-down" for o in objs), fmt


def test_the_layout_stands_a_structured_branch_in_as_one_block():
    tidy = _body(MAP, "function wbMapTidyPositions(")
    assert "wbMapStructuredPositions(index, layout, tops)" in tidy
    block = _body(MAP, "function wbMapStructuredPositions(")
    assert "_block:" in block and "collapsed: true" in block
    #: The top without its own mark, or both-sides would recurse into it.
    assert "branch_layout: null" in block
    assert "if (d._block) return d._block;" in _body(MAP, "function wbMapNodeSize(")


def test_lines_and_bars_read_the_branchs_own_layout():
    assert "const layout = child._bl || mapLayout;" in _body(MAP, "function wbMapEdgeAnchors(")
    assert "child._bl || wbMapLayout()" in _body(MAP, "function wbMapEdgeStyle(")
    assert "wbMapMarkBranchLayouts(index);" in _body(MAP, "function wbMapIndex(")


def test_the_menu_sets_it_in_one_undo_step():
    setter = _body(MAP, "async function wbMapSetBranchLayout(")
    assert "wbRecordGesture(" in setter and "wbMapTidy(" in setter
    menu = WB[WB.index('subItem("Structure"') :][:700]
    assert "WB_MAP_BRANCH_STRUCTURES" in menu and "Follow the map's layout" in menu
    assert '"branch_layout"' in MAP[MAP.index("const WB_MAP_CONTENT_KEYS") :][:400]


def test_a_topic_beside_its_parent_joins_side_to_side_in_a_downward_map():
    """The owner, 2026-10-26: a topic level with its parent still joined top to bottom."""
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node is not installed")
    helper = _body(MAP, "function wbMapBesideParent(") + "\n}"
    box = {"w": 220, "h": 48}
    cases = [
        ({"x": 0, "y": 0}, {"x": 520, "y": 62}),  # the owner's capture: right, a little lower
        ({"x": 0, "y": 0}, {"x": 0, "y": 124}),  # a tree level below: not beside
        ({"x": 0, "y": 0}, {"x": 300, "y": 124}),  # a wide sibling a level down: not beside
    ]
    script = f"{helper}\nconsole.log(JSON.stringify({json.dumps(cases)}.map(([a, b]) => wbMapBesideParent(a, {json.dumps(box)}, b, {json.dumps(box)}))));"
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    assert json.loads(run.stdout) == [True, False, False]
