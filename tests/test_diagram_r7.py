"""DOCUMENTS_PLAN 22.4 R7 (1621 D5, D6): the diagram page.

Read for what must hold; the browser numbers (390 and 1440 wide, light and dark) are named in docs/roadmap/HISTORY.md.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
DOCS = (JS / "documents.js").read_text(encoding="utf-8")
MERMAID = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_the_documents_dock_has_a_canvas_blocks_source_well_for_a_diagram():
    seg = HTML[HTML.index('id="doc-diagram-seg"') :]
    seg = seg[: seg.index("</div>")]
    for mode in ("canvas", "blocks", "source"):
        assert f'data-doc-view="{mode}"' in seg, mode
    # A well of three (the recipe's limit), in place of Edit and Read, which mean nothing for a diagram.
    # Hidden by the attribute (the global [hidden] rule), not by boot CSS, which is at its byte budget.
    assert 'id="doc-diagram-seg" hidden' in HTML
    assert '$("doc-diagram-seg").hidden = type.ext !== "mmd"' in DOCS and '$("doc-view-seg").hidden = type.ext === "mmd"' in DOCS


def test_canvas_and_blocks_are_two_layouts_of_the_one_rendered_view():
    allows = DOCS[DOCS.index("allows: (type, mode)") :]
    allows = allows[: allows.index("\n")]
    assert '"canvas"' in allows and '"blocks"' in allows
    setter = DOCS[DOCS.index("function setDocView(") :]
    setter = setter[: setter.index("\n}\n")]
    assert "docViewState.layout" in setter
    preview = DOCS[DOCS.index("function renderDocPreview() {") :]
    preview = preview[: preview.index("\n}\n")]
    assert "dgmLayout" in preview
    assert '[data-dgm-layout="canvas"]' in CSS and '[data-dgm-layout="blocks"]' in CSS


def test_the_dialog_seg_is_canvas_blocks_source_too():
    assert re.search(r'\[\["canvas", "Canvas"\], \["blocks", "Blocks"\], \["source", "Source"\]\]', EMBED)


def test_done_from_the_door_inside_an_editor_makes_a_row_and_inserts_a_link():
    door = MERMAID[MERMAID.index("async function diagramDoor(") :]
    door = door[: door.index("diagramModel.starter =")]
    tail = door[door.index("return openDiagramBuilder({\n      source: diagramModel.starter") :]
    assert 'file_type: "mmd"' in tail and "![[" in tail
    # The slash menu's starter fence is untouched.
    assert "```mermaid" not in tail


def test_the_retraction_of_1546_d9_is_recorded():
    history = (ROOT / "docs" / "roadmap" / "HISTORY.md").read_text(encoding="utf-8")
    assert "DOCUMENTS_PLAN 22, R7" in history and "1546 D9" in history
