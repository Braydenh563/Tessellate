"""The diagram builder wherever Mermaid draws (1546 P5; DOCUMENTS_PLAN "1546 design" D6 and D7).

Node runs the one pure piece, `diagramModel.fence` (the lines between a ```mermaid fence's marks,
so a replace keeps the marks and everything around them byte for byte). The rest is read for what
it must and must not hold: the Live figure's button and its exact-range replace, the board's
double-click opening the builder and nothing else (the textarea dialog and its ids are gone), one
undo step per save, a reply's "Open as a diagram", a diagram document drawn by `![[name]]`, and the
exports. The browser numbers (the PNG's pixels and size, a board source byte-equal after an open
and a Done) are in scratchpad/ui-sweeps/wbdiagram.js.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MERMAID = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")
DRAW = (JS / "mermaid-draw.js").read_text(encoding="utf-8")
INTER = (JS / "whiteboard-interchange.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _fence(text: str, source: str, near: int = 0):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    region = MERMAID[MERMAID.index("// DIAGRAM-MODEL-BEGIN") : MERMAID.index("// DIAGRAM-MODEL-END")]
    code = region + f"\nconsole.log(JSON.stringify(diagramModel.fence({json.dumps(text)}, {json.dumps(source)}, {near})));"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(code)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=60, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return json.loads(out.stdout)


TEXT = "Intro\n\n```mermaid\nflowchart TD\n  A --> B\n```\n\nMiddle\n\n```mermaid\nflowchart TD\n  A --> B\n```\n\nEnd\n"
SRC = "flowchart TD\n  A --> B"


def test_the_fence_range_is_exactly_the_lines_between_the_marks():
    at = _fence(TEXT, SRC)
    assert TEXT[at["from"] : at["to"]] == SRC
    swapped = TEXT[: at["from"]] + "flowchart LR\n  X --> Y" + TEXT[at["to"] :]
    assert swapped.startswith("Intro\n\n```mermaid\nflowchart LR\n  X --> Y\n```\n\nMiddle\n")
    assert swapped.endswith("\n\nEnd\n") and swapped.count("```mermaid") == 2


def test_of_two_identical_fences_the_one_nearest_the_figure_is_replaced():
    first, second = _fence(TEXT, SRC, 0), _fence(TEXT, SRC, TEXT.rindex("```mermaid"))
    assert first["from"] < second["from"] and TEXT[second["from"] : second["to"]] == SRC


def test_a_fence_that_changed_is_not_replaced():
    assert _fence(TEXT, "flowchart TD\n  A --> C") is None
    assert _fence("no fence here", SRC) is None


def test_the_live_figure_has_edit_as_blocks_and_replaces_only_its_range():
    assert 'smallButton("ph:squares-four", "Edit as blocks"' in MERMAID
    live = MERMAID[MERMAID.index("//: Edit as blocks (1546 D6)") : MERMAID.index("class DocMermaidReason")]
    assert "openDiagramBuilder({" in live and "diagramModel.fence(docStr(view.state.doc), this.source, near)" in live
    #: A Done with no change touches nothing; the figure's own press (the caret) is not the button's.
    assert "if (!changed) return;" in live and 'addEventListener("mousedown", (event) => event.stopPropagation())' in live
    #: The tool is outside the figure, which a redraw empties.
    assert "wrap.append(figure, edit, keep)" in live


def test_the_builder_opens_in_a_dialog_with_the_dialog_head_and_hands_back_the_source():
    assert 'diagramEmbed: ["/js/diagram-embed.js"]' in MERMAID and "async function openDiagramBuilder(options)" in MERMAID
    assert "openDiagramBuilder" in MERMAID.split("Object.assign(window,")[1]
    assert "dialogHead(title, () => finish(false))" in EMBED and 'el("div", "card modal-card space-dialog dgm-dialog")' in EMBED
    #: The overlay recipe, not a native <dialog>: a modal <dialog> sits above the sheets and menus it opens.
    assert "showModal" not in EMBED and 'el("dialog"' not in EMBED and "wireBackdropClose(overlay" in EMBED
    # Intent unchanged: Done hands over the source and whether it changed; the New diagram window adds its title as a third argument (DD-12, 1107).
    assert "onDone(history[at], history[at] !== first," in EMBED
    #: Closing with changes asks first; Escape is that same close.
    assert "confirmDialog(" in EMBED and "activeOverlay() !== overlay" in EMBED
    assert "diagramModel.builder.show(host, io, history[at])" in EMBED


def test_the_board_object_opens_the_builder_and_the_textarea_dialog_is_gone():
    dbl = INTER[INTER.index("function wbBuildDiagram(") : INTER.index("//: Draws the source once per source")]
    assert "wbEditDiagram(d)" in dbl and "wbOpenDiagramDialog" not in INTER
    edit = INTER[INTER.index("function wbEditDiagram(") : INTER.index("async function wbSaveDiagram(")]
    assert "openDiagramBuilder({" in edit and "wbDiagramToShapes(d, source)" in edit
    for gone in ("wb-diagram-dialog", "wb-diagram-text", "wb-diagram-preview", "wb-diagram-shapes", "wb-diagram-save"):
        assert gone not in HTML and gone not in INTER, gone
    #: One undo step, then the one save; an unchanged Done saves nothing, so the source stays byte for byte.
    save = INTER[INTER.index("async function wbSaveDiagram(") : INTER.index("//: Editable shapes where the diagram stood")]
    assert save.count("wbPushUndo(") == 1 and save.count("await wbSaveObject(d)") == 1
    assert "if (d && !changed) return;" in save
    assert "wbEditDiagram()" in (JS / "whiteboard-commands.js").read_text(encoding="utf-8")


def test_a_reply_offers_open_as_a_diagram_only_in_chat_and_ask():
    assert 'figure.closest(".step-answer, .answer")' in DRAW and "mermaidFill.asDiagram(figure, code.textContent)" in DRAW
    made = DRAW[DRAW.index("mermaidFill.asDiagram =") : DRAW.index("mermaidFill.embed =")]
    assert '"Open as a diagram"' in made and 'file_type: "mmd"' in made and "offerCreateUndo(doc)" in made


def test_a_diagram_document_embedded_with_wiki_brackets_draws_through_mermaid_draw_in():
    card = (JS / "markdown.js").read_text(encoding="utf-8")
    assert 'doc?.file_type === "mmd" && !plain' in card and "mermaidFill.embed(figure, doc, name)" in card
    embed = DRAW[DRAW.index("mermaidFill.embed =") : DRAW.index("//: A saved HTML file outlives")]
    assert "await mermaidDrawIn(box)" in embed and "mdDocumentCard(doc, name, true)" in embed


def test_export_is_svg_png_at_twice_the_viewbox_and_the_two_copies_in_the_builders_menu():
    assert "Math.ceil(box[2]) * 2" in EMBED and "Math.ceil(box[3]) * 2" in EMBED and '"image/png"' in EMBED
    #: The board's rasteriser and its bundle are not pulled in.
    assert "wbRasterizeSvg" not in EMBED
    for row in ("Save as SVG", "Save as PNG", "Copy as Mermaid", "Copy as SVG"):
        assert '"ph:' in BUILDER and row in BUILDER, row
    assert 'ensureModule("diagramEmbed")' in BUILDER and "S.io.menu" in BUILDER


def test_a_press_on_the_picture_finds_a_node_even_though_mermaid_12_prefixes_the_ids():
    """The reader looked for `flowchart-<id>-<n>` and Mermaid 12 draws `<svg id>-flowchart-<id>-<n>`, so a press on the
    picture never selected its block (measured in the frame: no id began with `flowchart`). It left the builder for
    diagram-picture.js, which the builder loads with the drag code, to keep the builder under its size cap. Node runs it."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    picture = (JS / "diagram-picture.js").read_text(encoding="utf-8")
    assert "/js/diagram-picture.js" in BUILDER and "diagramModel.picture.pick(S, event)" in BUILDER and "function boxesOf" not in BUILDER
    svg = (
        '<svg id="mmd2" viewBox="4 4 168 228"><g class="nodes">'
        '<g class="node" id="mmd2-flowchart-A-0" transform="translate(88, 34)"><rect width="152" height="44"></rect></g>'
        '<g class="node" id="flowchart-B-1" transform="translate(88, 118)"><rect width="152" height="44"></rect></g>'
        "</g></svg>"
    )
    code = "globalThis.diagramModel = {};\n" + picture + f"\nconsole.log(JSON.stringify(diagramModel.picture.boxes({json.dumps(svg)})));"
    found = json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)
    assert [b["id"] for b in found["boxes"]] == ["A", "B"] and found["boxes"][0]["w"] == 152 and found["vb"] == [4, 4, 168, 228]


def test_opening_an_existing_diagram_asks_before_it_drops_changes_like_cancel_does():
    """1679 slice 9 review: the button left the dialog with no confirm, so edits were lost; it shares Cancel's `mayDiscard`."""
    assert "const mayDiscard = async" in EMBED and "!(await mayDiscard())" in EMBED
    open_btn = EMBED[EMBED.index("const known = existing") :][:700]
    assert "mayDiscard()" in open_btn and open_btn.index("mayDiscard()") < open_btn.index("leave();")
