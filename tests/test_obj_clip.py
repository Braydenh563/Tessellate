"""INBOX 1467 part 3: copy and paste an object (obj-clip.js)."""

from __future__ import annotations

from tests._objmove_node import JS, needs_node, run

FILES = ["obj-ref.js", "obj-clip.js"]
STUBS = """
let selected = "";
window.getSelection = () => ({ toString: () => selected });
const toasts = [];
globalThis.toast = (text) => toasts.push(text);
globalThis.announce = () => {};
// A card for a note, and a field for a place to paste.
const noteCard = (id) => {
  const el = { dataset: { id: String(id) }, querySelector: () => null, matches: (sel) => sel === "#entry-list > li[data-id]" };
  el.closest = (sel) => (sel.includes("#entry-list > li[data-id]") ? el : null);
  return el;
};
const place = (part) => {
  const el = { dataset: {}, matches: () => false };
  el.closest = (sel) => (sel.includes(part) ? el : null);
  return el;
};
const copyEvent = () => { const sent = {}; return { sent, clipboardData: { setData: (t, v) => { sent[t] = v; } }, preventDefault() { this.stopped = true; } }; };
const pasteEvent = (text) => ({ clipboardData: { getData: () => text }, preventDefault() { this.handled = true; }, stopPropagation() {} });
"""


@needs_node
def test_ctrl_c_on_a_focused_card_puts_the_link_on_both_clipboards() -> None:
    out = run(FILES, STUBS + """
    document.activeElement = noteCard(5);
    const event = copyEvent();
    handlers.copy.forEach((fn) => fn(event));
    __out({ clip: objClip.ref, sent: event.sent, prevented: event.stopped, toasts });
    """)
    assert out["clip"] == {"kind": "note", "id": 5, "title": "Five", "url": ""}
    assert out["sent"] == {"text/plain": "[[Five]]"}
    assert out["prevented"] is True
    assert out["toasts"] == ["Copied “Five”."]


@needs_node
def test_words_and_fields_keep_their_own_copy() -> None:
    out = run(FILES, STUBS + """
    const results = [];
    // a selection of words wins over the focused card
    document.activeElement = noteCard(5); selected = "some words";
    let event = copyEvent(); handlers.copy.forEach((fn) => fn(event)); results.push(Boolean(event.stopped));
    // a text field is the field's own copy
    selected = ""; document.activeElement = place("input, textarea");
    event = copyEvent(); handlers.copy.forEach((fn) => fn(event)); results.push(Boolean(event.stopped));
    // nothing focused that is an object
    document.activeElement = place("nothing");
    event = copyEvent(); handlers.copy.forEach((fn) => fn(event)); results.push(Boolean(event.stopped));
    __out({ results, clip: objClip });
    """)
    assert out == {"results": [False, False, False], "clip": None}


@needs_node
def test_paste_in_the_composer_stages_an_attachment_only_for_our_text() -> None:
    out = run(FILES, STUBS + """
    document.activeElement = noteCard(5);
    handlers.copy.forEach((fn) => fn(copyEvent()));
    document.activeElement = place("#chat-input");
    // something else was copied since: an ordinary paste
    const other = pasteEvent("hello"); handlers.paste.forEach((fn) => fn(other));
    const staged = [attachedNoteIds.slice()];
    const mine = pasteEvent("[[Five]]"); handlers.paste.forEach((fn) => fn(mine));
    staged.push(attachedNoteIds.slice());
    __out({ otherHandled: Boolean(other.handled), mineHandled: Boolean(mine.handled), staged });
    """)
    assert out == {"otherHandled": False, "mineHandled": True, "staged": [[], [5]]}


@needs_node
def test_a_text_field_gets_the_link_from_the_browsers_own_paste() -> None:
    out = run(FILES, STUBS + """
    document.activeElement = noteCard(5);
    handlers.copy.forEach((fn) => fn(copyEvent()));
    document.activeElement = place("textarea");
    const event = pasteEvent("[[Five]]"); handlers.paste.forEach((fn) => fn(event));
    __out({ handled: Boolean(event.handled), staged: attachedNoteIds.length });
    """)
    assert out == {"handled": False, "staged": 0}


def test_the_menu_hook_and_the_script_are_wired() -> None:
    menus = (JS / "sheets-selects.js").read_text(encoding="utf-8")
    assert "window.objKebabRows?.(menu);" in menus
    ref = (JS / "obj-ref.js").read_text(encoding="utf-8")
    assert '"/js/obj-clip.js"' in ref
    board = (JS / "whiteboard.js").read_text(encoding="utf-8")
    assert "async function wbPlaceNote(entryId, at)" in board and "wbPlaceNote(entryId, at);" in board
