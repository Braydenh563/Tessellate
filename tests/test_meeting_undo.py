"""Every meeting act undoes (WORLD_CLASS_PLAN 28.5 row 4, decision 53): the
five that had none (create, remind, save into a note, save as a note, save
as a document) each push onto the undo bar. Driven in a browser by
`scratchpad/ui-sweeps/audio80.js` ACT=undo (6/6)."""

from __future__ import annotations

from pathlib import Path
from tests._js_scope import unwrapped

JS = unwrapped((Path(__file__).resolve().parents[1] / "frontend/js/meetings.js").read_text(encoding="utf-8"))


def _block(head: str) -> str:
    return JS.split(head)[1].split("\n}\n")[0]


def test_each_meeting_act_pushes_an_undo():
    assert 'pushUndo("Started a meeting"' in _block("async function openNewMeeting(")
    assert 'pushUndo("Made a reminder from an action item"' in _block("async function meetingRemind(")
    assert 'pushUndo(\n    "Added a transcript to the meeting"' in _block("async function meetingAppendUndoable(")
    assert 'pushUndo("Saved a recording as a meeting"' in _block("async function meetingCreateUndoable(")
    assert 'pushUndo("Saved a transcript as a document"' in _block("async function saveMeetingDocument(")


def test_undo_bins_rather_than_deletes():
    block = _block("function meetingBinPair(")
    assert '{ method: "DELETE" }' in block and '/restore`, { method: "POST" }' in block
