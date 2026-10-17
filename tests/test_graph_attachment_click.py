"""B73 (INBOX 904): a click on a separate attachment node in the graph does
something.

The owner: "Cant select on separate attachment nodes in the graph??"

`scratchpad/ui-sweeps/graph1017-b73.js` (Attachments switched on, three notes
with a file each): a plain click on an attachment node changed nothing, no
popup, no selection, no viewer. `gcClickNode` returned at
`if (!gcIsNote(node)) return`, and a document node fell through the same line.
An entity opened its page and an unresolved link wrote its note; these two
now open what they stand for, and the node's menu offers the same.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start)]


def test_a_click_opens_an_attachment_and_a_document_before_the_notes_only_line() -> None:
    body = _function("gcClickNode")
    assert body.index("gcOpenNodeTarget(node)") < body.index("if (!gcIsNote(node)) return;")
    target = _function("gcOpenNodeTarget")
    assert 'node.type === "attachment"' in target and 'node.type === "document"' in target
    assert "openLightbox(" in target and "openDocument(" in target


def test_the_node_menu_offers_open_for_them_too() -> None:
    body = _function("gcShowNodeMenu")
    assert "gcOpenNodeTarget(" in body, "the menu's Open row must reach non-note nodes"
