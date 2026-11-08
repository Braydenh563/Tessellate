"""Second blind sweep of the diagram builder (1108): what each fix must keep.

The numbers are in agent-remaining/dgmfix2-1108.md; these read the source for what has to stay true.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
KINDBAR = (JS / "diagram-kindbar.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
KINDS = (JS / "diagram-kinds.js").read_text(encoding="utf-8")


def test_the_builder_keeps_ctrl_z_for_itself_wherever_focus_is_inside_it():
    """The app's undo listener is on the document: a press on a tile or the picture also binned the new document."""
    # Moved from diagram-bar.js (flowchart only) to diagram-kindbar.js (every kind); the intent is the same, the home is not.
    assert "function historyKey(" in KINDBAR
    assert "event.stopPropagation()" in KINDBAR.split("function historyKey(")[1].split("\n  }\n")[0]
    assert "diagramModel.kindbar.historyKey(S, event)" in BUILDER
    assert "diagramModel.kindbar.historyKey(S, event)" in KINDS


MERMAID = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")


def test_a_diagram_made_from_insert_is_given_to_the_document_lists_before_its_embed_is_written():
    """Read view resolves `![[Title]]` through `docs`; without the row it said "Nothing called ... yet" until a reload."""
    door = MERMAID.split("draft: \"new-embed\"")[1]
    assert door.index("diagramMadeKnown(made)") < door.index("editorBlock(box")
    body = MERMAID.split("function diagramMadeKnown(")[1].split("\n  }\n")[0]
    assert "docs = other(docs)" in body and "renderDocList()" in body
    assert "diagramModel.madeKnown?.(made)" in EMBED


CANVAS = (JS / "diagram-canvas.js").read_text(encoding="utf-8")


def test_a_tile_dropped_beside_the_diagram_joins_from_the_nearest_box_however_far():
    """The help says "joined from the box nearest the drop"; a 120 px reach joined the selected Start from beside Ship it (136 px)."""
    assert "g.x, g.y, Infinity, ok)" in CANVAS
    assert "g.x, g.y, 120" not in CANVAS


EMBED_JS = (JS / "diagram-embed.js").read_text(encoding="utf-8")
LIBRARY = (JS / "diagram-library.js").read_text(encoding="utf-8")


def test_the_guide_answers_how_to_add_a_block_with_the_keys_the_shelf_and_the_slash():
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    for words in ("Add a block: N, a shelf tile or Add", "/diagram opens the builder in a document", "(Add on a phone)"):
        assert words in body, words
    assert len(body) < 1900


def test_the_builder_help_is_short_lines_not_one_paragraph():
    assert "const helpLines = [" in EMBED_JS and "...helpLines.map((line) => el(\"p\", \"\", line))" in EMBED_JS
    lines = EMBED_JS.split("const helpLines = [")[1].split("];")[0]
    assert lines.count('",\n') + lines.count("\",\n") >= 5


def test_a_phone_is_told_to_tap_add_where_the_shelf_is_hidden():
    """The shelf is `display: none` on a coarse pointer or under 600 px (diagram-lazy.css): no tile can be dragged there."""
    assert "Tap to add it." in LIBRARY and 'matchMedia("(max-width: 599.98px), (pointer: coarse)")' in LIBRARY
    assert "Tap a shape to add it." in LIBRARY
    assert "Tap Add to put a block in" in EMBED_JS


EDGES = (JS / "diagram-edges.js").read_text(encoding="utf-8")


def test_a_handle_stays_inside_the_part_of_the_picture_the_stage_shows():
    """A wide chart scrolls inside the stage, which clips: at 390 the selected block's right handle ended at 354 on a stage ending 344."""
    assert "seen.right - ox0" in EDGES and "fig.clientLeft - fig.scrollLeft" in EDGES
    assert "room(x0, x1, x - size / 2 + ox * out)" in EDGES


OUTLINE = (JS / "diagram-outline.js").read_text(encoding="utf-8")
VIEW = (JS / "diagram-view.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_the_turn_it_sideways_offer_needs_a_shrunk_drawing_lives_in_the_stage_and_is_answered_once_per_diagram():
    """The default three boxes (418 px in a 538 px stage) asked; the line straddled the list and the picture; Keep did not hold after an edit."""
    assert "offer(S, f < 1 && math.sideways(" in VIEW
    # Review 1108: keyed by the diagram (io.key), the host only where there is none; the node test in test_diagram_review_1108.py runs it.
    assert "const answered = new Set();" in OUTLINE and "answered.has(whose(S))" in OUTLINE and "answered.add(whose(S))" in OUTLINE
    assert "S.fig.parentElement" in OUTLINE and "S.note.after(line)" not in OUTLINE
    rule = CSS[CSS.index(".dgm-sideways {") : CSS.index("}", CSS.index(".dgm-sideways {"))]
    assert "12rem" in rule


DOCS_JS = (JS / "documents.js").read_text(encoding="utf-8")
OPS = (JS / "diagram-ops.js").read_text(encoding="utf-8")
KINDBAR = (JS / "diagram-kindbar.js").read_text(encoding="utf-8")
DRAW = (JS / "mermaid-draw.js").read_text(encoding="utf-8")


def test_opening_a_document_closes_the_block_hover_toolbar():
    """Reopening from the embed's link left the pencil/copy/trash bar (1091,161 to 1193,199) over Suggest."""
    start = DOCS_JS.index("const seq = ++docOpenSeq;")
    assert "docBlockBarClose();" in DOCS_JS[start : start + 400]


def test_a_decisions_second_branch_is_labelled_no_when_the_first_is_yes():
    assert '"no"' in OPS and "diamond" in OPS[OPS.index("function dgbJoin") :][:1500]


def test_the_kind_menu_label_differs_from_the_kind_button_label():
    """Two elements shared the aria-label Kind of diagram."""
    assert '"Kinds of diagram"' in KINDBAR


def test_the_embedded_picture_opens_the_diagram_on_a_press():
    assert "diagram-embed-box" in DRAW and "openDocument(doc.id)" in DRAW[DRAW.index("diagram-embed-box") :][:400]
