"""Second blind sweep of the diagram builder (1108): what each fix must keep.

The numbers are in agent-remaining/dgmfix2-1108.md; these read the source for what has to stay true.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
BAR = (JS / "diagram-bar.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
KINDS = (JS / "diagram-kinds.js").read_text(encoding="utf-8")


def test_the_builder_keeps_ctrl_z_for_itself_wherever_focus_is_inside_it():
    """The app's undo listener is on the document: a press on a tile or the picture also binned the new document."""
    assert "function historyKey(" in BAR
    assert "event.stopPropagation()" in BAR.split("function historyKey(")[1].split("\n  }\n")[0]
    assert "diagramModel.bar.historyKey(S, event)" in BUILDER
    assert "diagramModel.bar.historyKey(S, event)" in KINDS


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
