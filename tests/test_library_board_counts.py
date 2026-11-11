"""The Library counts boards one way (INBOX 464 (15)).

Measured on a notebook with one board ("Garden plan", empty): Library,
Everything said "Boards 1" and Boards & maps said "All 2". The cause is
`GET /whiteboard/boards`, which always returns the default scratch board
(`id: null`) whatever is on it, while `/library` lists boards that are notes,
and the default board is not one. The source is now one predicate,
`libraryListsBoard` (note-cards.js, loaded at boot): the default board is a
board the Library lists only when something is on it. The gallery's cards,
its chip counts, its tick sync (`wbVisibleBoards`) and the dashboard's Boards
widget all go through it.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
NOTE_CARDS = (JS / "note-cards.js").read_text(encoding="utf-8")
WHITEBOARD = (JS / "boards-gallery.js").read_text(encoding="utf-8")
DASHBOARD = (JS / "dashboard.js").read_text(encoding="utf-8")
DASH_BOARDS = (JS / "dash-boards.js").read_text(encoding="utf-8")


def _lists(board: dict) -> bool:
    m = re.search(r"^function libraryListsBoard\(board\) \{.*?^\}", NOTE_CARDS, re.S | re.M)
    assert m, "libraryListsBoard is gone from note-cards.js"
    script = m.group(0) + f"\nprocess.stdout.write(String(libraryListsBoard({json.dumps(board)})));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return out == "true"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_an_empty_default_board_is_not_a_board_the_library_lists():
    empty = {"id": None, "node_count": 0, "sketch_count": 0, "object_count": 0}
    assert not _lists(empty)
    assert _lists({**empty, "sketch_count": 2})
    assert _lists({**empty, "object_count": 1})
    # A board you made is listed empty: it is a note, and /library lists it.
    assert _lists({"id": 16, "node_count": 0, "sketch_count": 0, "object_count": 0})
    assert _lists({"id": 16, "node_count": 0, "sketch_count": 0})


def test_every_library_view_of_boards_goes_through_it():
    gallery = WHITEBOARD[WHITEBOARD.index("async function renderLibraryBoardsGallery"):]
    gallery = gallery[: gallery.index("renderBoardTypeFilter(counts)")]
    assert "libraryListsBoard" in gallery, "the gallery counts must use the predicate"
    visible = WHITEBOARD[WHITEBOARD.index("window.wbVisibleBoards = function"):][:600]
    assert "libraryListsBoard" in visible, "the tick sync must see the same list"
    #: The widget moved to dash-boards.js (INBOX 553(d), the boot budget).
    widget = DASH_BOARDS[DASH_BOARDS.index("async function dashRenderBoards"):][:1500]
    assert "libraryListsBoard" in widget
