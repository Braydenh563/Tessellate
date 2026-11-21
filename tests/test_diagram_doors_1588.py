"""The Diagram builder has one name, one icon and one opener at every door (INBOX 1588).

The owner could not find the builder: "make sure the mermaid diagram builder is easily accessible
through all the main features like the notes, whiteboard, mindmap, documents editor, command
palette, quick access, find anything, tools and features, / commands". The `diagram` row of
`POPUP_TOOLS` (settings-panes.js) feeds the palette, Find anything, Quick access, Tools and
features, both "/" menus (so a note's and a document's Insert) and Chat; the board's Insert and
the Library's Create name the same row by hand. All of them end in `diagramDoor`
(documents-mermaid.js), the only opener.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai.help_topics_more import HELP_GROUPS, MORE_TOPICS, TOPIC_META
from tessellate.core.filetypes import FILE_TYPES

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
JS = FRONTEND / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _entry() -> str:
    body = _read("settings-panes.js").split("const POPUP_TOOLS = [", 1)[1].split("\n];", 1)[0]
    return next(b for b in re.split(r"\n  \},?\n", body) if 'id: "diagram"' in b)


def test_the_registry_row_is_named_and_drawn_once_for_every_list():
    entry = _entry()
    assert 'name: "Diagram builder"' in entry and 'icon: "ph:flow-arrow"' in entry
    assert "diagramModel.door({ target: t || null })" in entry
    assert 'guide: "diagram-builder"' in entry
    # The lists read the registry; none holds its own copy of the row.
    assert "...POPUP_TOOLS.map(" in _read("app-features.js") and "of POPUP_TOOLS" in _read("app-features.js")
    assert "for (const tool of POPUP_TOOLS)" in _read("editor.js")
    assert "POPUP_TOOLS.map((tool) =>" in _read("editor.js")


def test_there_is_one_opener_and_every_hand_written_door_calls_it():
    mermaid = _read("documents-mermaid.js")
    assert mermaid.count("async function diagramDoor(") == 1
    assert "diagramModel.door = diagramDoor;" in mermaid and "diagramDoor }" not in mermaid.split("Object.assign(window, {")[1].split("});")[0]
    library = _read("library.js")
    create = library.split("  diagram: {\n    label: \"ph:flow-arrow New diagram\"", 1)[1][:300]
    assert "diagramModel.door({ doc: true })" in create
    assert '"diagram"' in library.split("const LIBRARY_CREATE_ORDER = [", 1)[1].split("]", 1)[0]
    commands = _read("whiteboard-commands.js")
    row = next(line for line in commands.splitlines() if 'id: "insert-diagram"' in line)
    assert 'label: "Diagram builder"' in row and 'icon: "ph:flow-arrow"' in row and 'surface: "both"' in row
    assert "wbEditDiagram()" in row
    # The door's board branch is the board's own opener, not a second dialog.
    assert "return wbEditDiagram();" in mermaid
    interchange = _read("whiteboard-interchange.js")
    #: Intent moved (R12): a new board diagram is an empty builder after the sheet; the starter stays in the door.
    assert "diagramModel.starter" in mermaid and "WB_DIAGRAM_SAMPLE" not in interchange and '|| ""' in interchange


def test_the_chat_box_is_the_target_of_the_chat_row_and_the_board_menu_is_for_maps_too():
    editor = _read("editor.js")
    assert 'tool.id === "diagram" ? document.getElementById("chat-input")' in editor
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    item = next(line for line in html.splitlines() if 'data-wb-cmd="insert-diagram"' in line)
    assert "Diagram builder…" in item and "ph-flow-arrow" in item and "data-wb-surface" not in item


def test_mermaid_is_the_file_format_and_not_the_name():
    ext = next(t for t in FILE_TYPES if t.ext == "mmd")
    assert ext.label == "Diagram"
    for name in ("whiteboard-commands.js", "library.js", "settings-panes.js", "app-features.js"):
        text = _read(name)
        assert "Mermaid diagram, live" not in text and "Mermaid diagram…" not in text, name
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert "<span>Mermaid diagram…</span>" not in html
    assert 'title: d ? "Edit diagram" : "Diagram builder"' in _read("whiteboard-interchange.js")


def test_the_guide_names_every_door():
    topic = next(t for t in MORE_TOPICS if t["id"] == "diagram-builder")
    body = topic["body"]
    for words in ("Ctrl+K, Diagram builder", "Find anything", "Quick access", "Insert", "/ then diagram", "Chat", "board or a mind map",
                  "Library's Create", "Cancel changes nothing", "Mermaid is only its file format"):
        assert words in body, words
    assert "diagram-builder" in TOPIC_META
    assert "diagram-builder" in dict(HELP_GROUPS)["Documents and code"]
