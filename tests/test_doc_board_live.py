"""A board in a document shown live, one window per card (DOCUMENTS_PLAN 26, decision 83, L-documents-11). Each card's Show live
mounts a read-only window of its own: it reads the board, draws it, and zooms through the diagram view's recipe; it never touches
the one whiteboard's state, so two windows and the Library's board cannot cross. Static checks; the behaviour was measured in the
browser (two windows and the main board, state numbers before and after an edit, HISTORY)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests._help_text import help_more_text

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"

pytestmark = pytest.mark.xfail(strict=True, reason="L-documents-11: the live window is not built yet")


def read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def code_of(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def test_each_board_card_offers_show_live_next_to_edit_here() -> None:
    embeds = read("documents-embeds.js")
    assert "Show live" in embeds and '"board-live"' in embeds
    assert 'live.classList.add("doc-embed-board-live")' in embeds
    assert 'live.setAttribute("aria-pressed", "false")' in embeds


def test_a_window_reads_the_board_and_zooms_by_the_diagram_recipe() -> None:
    panel = read("documents-board.js")
    assert "/whiteboard/?board_id=" in panel
    assert "diagramModel.view.wire(" in panel
    assert 'ensureModule("vf")' in panel and 'ensureModule("diagramView")' in panel
    assert 'lazyScript("/css/diagram-lazy.css")' in panel
    # Edit here closing redraws every window on that board; Refresh redraws one.
    assert 'addEventListener("board-live"' in panel and 'addEventListener("board-edited"' in panel
    assert "Refresh" in panel


def test_a_window_never_touches_the_one_whiteboard() -> None:
    code = code_of(read("documents-board.js"))
    live = code[code.index("const windows"):]
    for name in ("wbState", "currentBoardId", "whiteboard-container", "wbSelectedItem", "wbMultiSelection", "wbUndoStack", "openWhiteboardBoard"):
        assert name not in live, name
    # Read-only: the window sends no write.
    assert not re.search(r"method:\s*\"(PUT|POST|PATCH|DELETE)\"", live)


def test_the_window_has_a_height_and_stays_out_of_print() -> None:
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert ".doc-board-live.dgm {" in css
    assert "@media print {\n  .doc-embed-board-live,\n  .doc-board-live {\n    display: none;" in css


def test_the_guide_says_show_live() -> None:
    body = help_more_text()
    start = body.index('"document-board"')
    topic = body[start:start + 2400]
    assert "Show live" in topic and "Refresh" in topic
