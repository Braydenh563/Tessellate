"""A board in and out as text (the features audit W5; WHITEBOARD_PLAN Phase E).

Mermaid out and in, a free board's outline, and the board inside its own SVG.
The pure parts run in node against the source; the browser half is
`scratchpad/ui-sweeps/wb1005-interchange.js`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
BOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    pure = SOURCE[: SOURCE.index("//: The rows inside an SVG")]
    out = subprocess.run([node, "-e", pure + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def test_the_flowchart_subset_parses() -> None:
    src = "flowchart LR\nA[Start] --> B{Is it OK?}\nB -->|yes| C((Done))\nB -- no --> D(Fix it) --> B\nstyle A fill:#f9f\nF[\"Quoted\"] -.-> A; G --- A"
    g = _run(f"wbMermaidParse({json.dumps(src)})")
    assert g["dir"] == "LR"
    assert {n["id"]: (n["text"], n["shape"]) for n in g["nodes"]} == {
        "A": ("Start", "rect"), "B": ("Is it OK?", "diamond"), "C": ("Done", "circle"),
        "D": ("Fix it", "rect"), "F": ("Quoted", "rect"), "G": ("G", "rect"),
    }
    edges = {(e["from"], e["to"]): (e["label"], e["arrow"], e["dashed"]) for e in g["edges"]}
    assert edges[("B", "C")] == ("yes", True, False)
    assert edges[("B", "D")] == ("no", True, False)
    assert edges[("D", "B")] == ("", True, False)
    assert edges[("F", "A")] == ("", True, True)
    assert edges[("G", "A")] == ("", False, False)
    assert g["skipped"] == 1


def test_the_layout_puts_each_level_on_its_own_row() -> None:
    at = _run('Object.fromEntries(wbMermaidLayout(wbMermaidParse("graph TD\\nA-->B\\nA-->C\\nB-->D")))')
    assert at["A"]["y"] < at["B"]["y"] == at["C"]["y"] < at["D"]["y"]
    assert at["B"]["x"] != at["C"]["x"]


def test_a_board_round_trips_through_mermaid() -> None:
    state = {
        "nodes": [],
        "objects": [{"id": 1, "kind": "text", "data": {"content": "Hi [x]"}, "x": 0, "y": 0}],
        "sketches": [
            {"id": 5, "data": json.dumps({"d": "M 0 0 L 10 0 Z", "shape": "diamond", "label": "OK?"})},
            {"id": 6, "data": json.dumps({"type": "link-straight", "sourceId": 1, "sourceKind": "object", "targetId": 5, "targetKind": "sketch", "endCap": "arrow", "label": "go"})},
        ],
    }
    text = _run(f"wbBoardToMermaid({json.dumps(state)})")
    assert text.startswith("flowchart TD\n") and '{"OK?"}' in text and "-->|go|" in text
    back = _run(f"wbMermaidParse({json.dumps(text)})")
    assert [n["text"] for n in back["nodes"]] == ["Hi x", "OK?"]
    assert back["edges"][0]["label"] == "go"


def test_a_free_board_outlines_by_frame_then_reading_order() -> None:
    state = {
        "nodes": [],
        "objects": [
            {"id": 1, "kind": "text", "data": {"content": "Second"}, "x": 10, "y": 50},
            {"id": 2, "kind": "text", "data": {"content": "First"}, "x": 10, "y": 10},
            {"id": 3, "kind": "text", "data": {"content": "Outside"}, "x": 900, "y": 900},
        ],
        "sketches": [],
    }
    frames = [{"x": 0, "y": 0, "width": 200, "height": 200, "data": {"content": "Ideas"}}]
    text = _run(f"wbBoardOutline({json.dumps(state)}, {{ frames: {json.dumps(frames)}, title: 'Plan' }})")
    assert text.split("\n")[:7] == ["# Plan", "", "## Ideas", "", "- First", "- Second", ""]
    assert "## Elsewhere on the board" in text and "- Outside" in text


def test_the_svg_carries_the_board_and_the_paths_are_wired() -> None:
    assert "wbBoardSvgMetadata(wbExportRows(scope))" in BOARD
    assert 'value: "mermaid"' in BOARD and 'value: "outline"' in BOARD
    assert "(!f.board || !isMap)" in BOARD
    assert 'data-wb-cmd="import-diagram"' in INDEX and 'id="wb-import-dialog"' in INDEX
    meta = _run('wbBoardSvgMetadata([{kind: "sketch", id: 1, payload: {data: "<x>&"}}])')
    assert meta.startswith('<metadata id="memorymap-board">') and "<x>" not in meta


# --- Subgraphs come in as frames, and frames go out as subgraphs (wb-phase2 step 2)

NESTED = """flowchart TD
A[Start] --> B
subgraph S1 [Build]
  B[Compile] --> C[Test]
  subgraph S2 ["Ship it"]
    D[Deploy]
  end
  C --> D
end
subgraph Plain words here
  E[Lone]
end
D --> E
A --> S1
"""


def test_subgraphs_parse_with_their_titles_and_members() -> None:
    g = _run(f"wbMermaidParse({json.dumps(NESTED)})")
    assert g["subgraphs"] == [
        {"id": "S1", "title": "Build", "parent": None},
        {"id": "S2", "title": "Ship it", "parent": "S1"},
        {"id": "Plain words here", "title": "Plain words here", "parent": None},
    ]
    groups = {n["id"]: n["group"] for n in g["nodes"]}
    # B is named first outside S1 (A --> B), then given its words inside it:
    # it belongs to the first subgraph that names it, as in Mermaid.
    assert groups == {"A": None, "B": "S1", "C": "S1", "D": "S2", "E": "Plain words here"}
    # The subgraph named in an edge is not a node of its own, and nothing is
    # counted as left out.
    assert "S1" not in groups and g["skipped"] == 0
    assert any(e["from"] == "A" and e["to"] == "S1" for e in g["edges"])


def test_a_frame_holds_its_members_and_nothing_else() -> None:
    out = _run(f"(() => {{ const m = wbMermaidLayout(wbMermaidParse({json.dumps(NESTED)})); return {{ at: Object.fromEntries(m), frames: m.frames }}; }})()")
    at, frames = out["at"], {f["id"]: f for f in out["frames"]}
    assert out["frames"][0]["depth"] == 0 and out["frames"][-1]["depth"] == 1  # outermost first
    assert frames["S2"]["depth"] == 1 and frames["S1"]["depth"] == 0
    members = {"S1": {"B", "C", "D"}, "S2": {"D"}, "Plain words here": {"E"}}
    for fid, f in frames.items():
        for nid, p in at.items():
            box = (p["x"] - 80, p["y"] - 35, p["x"] + 80, p["y"] + 35)
            inside = box[0] >= f["x"] and box[1] >= f["y"] and box[2] <= f["x"] + f["w"] and box[3] <= f["y"] + f["h"]
            overlaps = box[0] < f["x"] + f["w"] and box[2] > f["x"] and box[1] < f["y"] + f["h"] and box[3] > f["y"]
            if nid in members[fid]:
                assert inside, (fid, nid, f, p)
            else:
                assert not overlaps, (fid, nid, f, p)
    # The inner frame sits wholly inside the outer one.
    o, i = frames["S1"], frames["S2"]
    assert o["x"] < i["x"] and o["y"] < i["y"] and i["x"] + i["w"] < o["x"] + o["w"] and i["y"] + i["h"] < o["y"] + o["h"]
    # Two frames side by side never overlap.
    p, q = frames["S1"], frames["Plain words here"]
    assert p["x"] + p["w"] <= q["x"] or q["x"] + q["w"] <= p["x"] or p["y"] + p["h"] <= q["y"] or q["y"] + q["h"] <= p["y"]


def test_a_flat_flowchart_lays_out_as_it_did() -> None:
    at = _run('Object.fromEntries(wbMermaidLayout(wbMermaidParse("graph LR\\nA-->B\\nA-->C")))')
    assert at["B"]["x"] - at["A"]["x"] == 220 and abs(at["B"]["y"] - at["C"]["y"]) == 140


def test_frames_go_out_as_subgraphs_and_come_back() -> None:
    state = {
        "nodes": [],
        "objects": [],
        "sketches": [
            {"id": 5, "data": json.dumps({"d": "M 0 0 L 10 0 Z", "label": "In"})},
            {"id": 7, "data": json.dumps({"d": "M 0 0 L 10 0 Z", "label": "Out"})},
            {"id": 6, "data": json.dumps({"type": "link-straight", "sourceId": 5, "sourceKind": "sketch", "targetId": 7, "targetKind": "sketch"})},
        ],
    }
    frame_of = "(kind, item) => item.id === 5 ? { id: 9, title: 'Team [A]' } : null"
    text = _run(f"wbBoardToMermaid({json.dumps(state)}, undefined, {frame_of})")
    assert '  subgraph f1 ["Team A"]\n    n1["In"]\n  end\n' in text
    back = _run(f"wbMermaidParse({json.dumps(text)})")
    assert back["subgraphs"] == [{"id": "f1", "title": "Team A", "parent": None}]
    assert {n["text"]: n["group"] for n in back["nodes"]} == {"In": "f1", "Out": None}


def test_the_import_makes_the_frames_and_joins_a_subgraph_edge_to_its_frame() -> None:
    body = SOURCE[SOURCE.index("async function wbImportMermaid(") :]
    body = body[: body.index("\n}\n")]
    # The frame's z is the creator's default, the stack's "under the frames
    # already there" (wbz-1026 replaced wbFrameZ with wbStackNewZ).
    assert 'wbCreateObject("frame"' in body and "wbFrameZ" not in body
    assert 'z = wbStackNewZ("object", { kind })' in (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    assert "frameIds.get(e.from)" in body and 'tKind = ids.has(e.to) ? "sketch" : "object"' in body
    assert "wbMermaidFrameOf" in SOURCE[SOURCE.index("async function wbExportMermaid(") :]
