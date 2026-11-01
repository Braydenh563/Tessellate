"""Brief 101b: Undo the run takes the run's writes off the undo stack.

Each write of an agent run goes on the app's Ctrl+Z stack. The run's own
"Undo the run" put everything back at once but left those entries, so a later
Ctrl+Z (or a row's own Undo) ran an inverse that was already applied. The
DOM cannot run here, so this holds the wiring: the run's Undo is handed a
callback, called after a successful undo, that settles every entry and drops
the rows' Undo buttons.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR
from tests._app_js import with_pieces


def test_the_run_undo_settles_the_stack_entries_and_the_rows():
    source = with_pieces("chat-agent.js")
    assert "undoSkillRun(span, all, settleRun)" in source
    settle = re.search(r"const settleRun = \(\) => \{.*?\n          \};", source, re.S)
    assert settle, "settleRun is gone"
    body = settle.group(0)
    assert "agentUndoActions.get(JSON.stringify(change.undo))" in body
    assert "undoStack.includes(action)" in body, "an entry already off the stack must not reach the redo stack twice"
    assert "[data-change-undo]" in body
    assert 'undo.dataset.changeUndo = "1"' in source


def test_undo_skill_run_calls_back_after_it_applied_and_when_already_undone():
    source = (JS_DIR / "note-history.js").read_text(encoding="utf-8")
    func = re.search(r"^async function undoSkillRun\(span, button, onDone\) \{.*?^\}", source, re.S | re.M)
    assert func, "undoSkillRun lost its callback"
    assert func.group(0).count("onDone?.()") == 2
