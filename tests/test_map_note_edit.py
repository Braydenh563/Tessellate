"""A note node edits in place (MINDMAP_PLAN 12.2 item 5, second half): the
notebook's own text opens in the topic note shell, is saved with a PUT to the
note and one Undo step, and the map re-reads its labels."""

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = frontend_text("whiteboard-map.js")
WB = frontend_text("whiteboard.js")


def _body(src, head):
    start = src.index(head)
    return src[start : src.index("\n}", start) + 2]


def test_a_note_node_opens_the_shell_on_the_notebook_note():
    opener = _body(MAP, "function wbMapOpenNote(")
    assert 'node?.kind === "note" && Number.isInteger(node.data?.ref_id)' in opener
    assert "wbMapOpenNote.load(wbMapNoteState, box)" in opener
    load = MAP[MAP.index("wbMapOpenNote.load = ") : MAP.index("wbMapOpenNote.save = ")]
    assert "apiJson(`/entries/${state.entryId}`)" in load  # the whole note, never a clipped row
    assert "box.readOnly = true" in load


def test_closing_saves_the_text_once_with_undo_and_a_label_refresh():
    save = MAP[MAP.index("wbMapOpenNote.save = ") : MAP.index("function wbMapCloseNote(")]
    assert 'method: "PUT"' in save and "wbPushCall(" in save  # the board's history, where Ctrl+Z reads
    assert "wbRefreshMapState()" in save
    close = _body(MAP, "function wbMapCloseNote(")
    assert "state.loaded && value !== state.before" in close  # nothing saved before it loaded or when unchanged


def test_the_topic_menu_offers_it_for_a_note_node_only():
    assert "Edit the note's text…" in WB
    at = WB.index("Edit the note's text…")
    assert 'mapNode.kind === "note"' in WB[at - 200 : at]
