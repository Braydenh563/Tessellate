"""L-world-class-200: Escape puts the Undo notices away, and the bar reads the board's own stack.

Driven at 1440 on :8870 (2026-11-14): a chat rename raised "Renamed to ..." with
Undo; Escape (body focus and chat box focus) set `is-leaving` on it and the
notice left; Ctrl+Z still undid the rename. On a mind map the status bar's pair
read the board's stack: delete a topic (3 to 2 topics, Undo lit), Ctrl+Z (2 to
3, Undo dim, Redo lit), three runs.
"""

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _src(name):
    return (JS / name).read_text(encoding="utf-8")


def test_escape_dismisses_the_newest_undo_notice_after_every_overlay_declined():
    text = _src("settings-wiring.js")
    tail = text[text.index('if (e.key === "Escape" && linkSource !== null) linkCancel();'):]
    tail = tail[: tail.index("\n});")]
    # nothing in front took the key, and only a notice that carries an Undo button goes
    assert 'e.key === "Escape" && !e.defaultPrevented' in tail
    assert 'toastKey?.endsWith(":Undo")' in tail and "dismissToast(n)" in tail


def test_the_bar_walks_the_boards_own_stack_while_a_board_or_map_is_open():
    text = _src("status.js")
    door = text[text.index("function surfaceHistory"):]
    door = door[: door.index("\n}\n")]
    assert "window.wbUndo()" in door and "canUndo: window.wbCanUndo" in door
    assert re.search(r"window\.wbCanUndo = \(\) => \(wbHistoryFor\(\), wbUndoStack\.length > 0\)", _src("whiteboard.js"))
