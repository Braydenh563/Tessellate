"""A live Mermaid diagram on the board (INBOX 1451): an object of kind
`diagram` holding its source in `data.mermaid`, drawn through the same hidden
frame as a note's diagrams, edited by double-click, and turned into shapes
on request. The browser half is `scratchpad/ui-sweeps/wbdiagram.js`."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
WB = (JS / "whiteboard.js").read_text(encoding="utf-8")
INTER = (JS / "whiteboard-interchange.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
SOURCE = "flowchart TD\n  A[Start] --> B[Done]"


def _post(client, data):
    return client.post("/whiteboard/objects", json={"kind": "diagram", "data": data, "x": 0, "y": 0, "width": 320, "height": 200})


def test_a_diagram_keeps_its_source_and_refuses_none(ai_client):
    made = _post(ai_client, {"mermaid": SOURCE})
    assert made.status_code in (200, 201), made.text
    assert made.json()["data"]["mermaid"] == SOURCE
    for bad in ({}, {"mermaid": "   "}, {"mermaid": "x" * 20_001}):
        assert _post(ai_client, bad).status_code == 422, bad
    obj = made.json()
    edited = ai_client.put(f"/whiteboard/objects/{obj['id']}", json={**obj, "data": {**obj["data"], "mermaid": "flowchart LR\n  A --> C"}})
    assert edited.status_code == 200 and edited.json()["data"]["mermaid"].endswith("A --> C")


def _body(src: str, name: str) -> str:
    start = src.index(name)
    return src[start : src.index("\n}\n", start)]


def test_the_diagram_is_built_painted_and_exported():
    assert "wbBuildDiagram(el, d);" in WB and "wbPaintDiagram(this, d);" in WB
    paint = _body(INTER, "function wbPaintDiagram(")
    #: Drawn by the notes' own frame, loaded only when a board has one.
    assert 'ensureModule("mermaid")' in paint and "mermaidRequest(" in paint
    assert "data:image/svg+xml" in INTER
    #: Export and the thumbnail draw what is already drawn, synchronously.
    assert "wbDiagramDataUrl(obj)" in WB


def test_insert_edit_and_convert_are_reachable():
    assert 'data-wb-cmd="insert-diagram"' in HTML and 'id="wb-diagram-dialog"' in HTML
    edit = _body(INTER, "function wbOpenDiagramDialog(")
    assert "wbImportMermaid(" in INTER and "wb-diagram-shapes" in edit
