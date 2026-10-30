"""Every kind of object can be taken to the other main features (INBOX 393:
"there needs to be more integration between all the main features").

Source-level: each object menu names the shared door, so a menu rebuilt
without it fails here rather than quietly losing the route.
"""

from __future__ import annotations

from pathlib import Path
from tests._app_js import app_js_text

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
APP = app_js_text()
LIBRARY = (FRONTEND / "js" / "library.js").read_text(encoding="utf-8")
BOARDS = (FRONTEND / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _block(source: str, start: str, end: str) -> str:
    i = source.index(start)
    return source[i : source.index(end, i)]


def test_a_note_card_reaches_the_graph_and_the_chat():
    menu = _block(APP, 'label: "ph:hourglass-medium Forgotten notes like this"', "const addItems = [")
    assert "showNoteInGraph(entry.id)" in menu
    assert "askAtlasAboutNote(entry)" in menu


def test_library_notes_and_documents_reach_the_chat():
    document = _block(LIBRARY, 'if (item.kind === "document") {', 'if (item.kind === "archived") {')
    note = _block(LIBRARY, 'if (item.kind === "note") {', "makeMenuItem(\"ph:archive Archive\", \"Keep it, but out of the way, not the bin\"")
    assert 'askAtlasAboutThing("document"' in document
    assert 'askAtlasAboutThing("note"' in note
    assert "showNoteInGraph(item.id)" in note


def test_a_library_document_reaches_the_graph():
    """WORLD_CLASS_PLAN 1.3: the graph draws a document as `document:<id>`
    while its Documents switch is on, so the door turns the switch on and
    looks for that node, not the bare id a note has."""
    document = _block(LIBRARY, 'if (item.kind === "document") {', 'if (item.kind === "archived") {')
    assert "showNoteInGraph(item.id, { document: true })" in document
    assert "ph:graph Show in graph" in document
    #: The finding half moved to graph.js (2026-10-10, the boot budget).
    graph = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
    assert "return graphShowNote(id, options);" in _block(APP, "async function showNoteInGraph(", "\n}")
    door = _block(graph, "async function graphShowNote(", "focusGraphNode(node);")
    assert "document:" in door
    assert '$("graph-documents")' in door


def test_a_board_or_map_card_reaches_the_chat():
    assert "askAtlasAboutThing(board.type === \"map\" ? \"map\" : \"board\", board.title)" in BOARDS


def test_a_file_and_a_reminder_reach_the_chat():
    """The ledger's "left: files, reminders" (OPEN.md, INBOX 393). A reminder
    already had the row; a file card's menu held Download and Delete only."""
    file_menu = _block(LIBRARY, 'if (item.kind === "file") {', "return [];\n}")
    assert 'askAtlasAboutThing("file", item.title)' in file_menu
    assert 'askAtlasAboutThing("reminder", reminder.text)' in APP


def test_the_shared_row_says_the_same_thing_everywhere():
    """One door, one face: the same words and the same glyph on every object's
    menu. The reminder's wore a sparkle where every other wore the chat bubble,
    which reads as a different feature."""
    for source in (APP, LIBRARY, BOARDS):
        for line in source.splitlines():
            if "Ask Atlas about this" in line and ("label" in line or "makeMenuItem(" in line):
                assert "ph:chat-circle Ask Atlas about this" in line, line.strip()


def test_duplicate_sits_with_the_notes_own_actions_not_under_add():
    """Audit 1028 S12: Duplicate lived in the Add flyout, beside "Make a mind
    map" and "Accept the filing", where nobody looks for a copy."""
    menus = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "menus.js").read_text(encoding="utf-8")
    top = menus.index("const topLevel = [")
    add = menus.index("const addItems = [")
    duplicate = menus.index('label: "ph:copy Duplicate"')
    assert top < duplicate < add


def test_board_failures_are_said_on_screen_not_in_the_console():
    """Audit 1028 B22: a failed drawing save, board fetch or connection was a
    `console.error` and nothing else. The remaining `console.warn` lines are
    diagnostics for menus refused at the window's corner, not failures."""
    board = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    assert "console.error(" not in board and "console.log(" not in board
    for what in ("save that drawing", "open that board", "connect those"):
        assert f'voiceLine("failed", {{ what: "{what}"' in board, what
