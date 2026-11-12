"""Saving a note puts Undo on the stack the moment the note exists.

e2e capture-filing "Undo takes a new note back and Redo returns it": Ctrl+Z
pressed while the list was still refreshing found an empty stack and did
nothing. `pushUndo("Created a note", ...)` therefore comes right after the POST
returns and before `await refreshEntries` (the refresh is the slow part).
"""

from __future__ import annotations

from pathlib import Path

CAPTURE_ASK = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "capture-ask.js").read_text(encoding="utf-8")


def test_undo_is_pushed_before_the_list_refresh_is_awaited():
    save = CAPTURE_ASK.index('const saved = await apiJson("/entries", { method: "POST"')
    push = CAPTURE_ASK.index('pushUndo(\n      "Created a note"', save)
    refresh = CAPTURE_ASK.index("await refreshEntries([saved.id]);", save)
    assert save < push < refresh, "Undo must be registered before the first await after the POST"
    assert "await" not in CAPTURE_ASK[save + 60 : push].replace("await commitCaptureImages", ""), "no await between the POST and pushUndo"
