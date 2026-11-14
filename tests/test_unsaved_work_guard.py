"""The unsaved-work guard (WORLD_CLASS_PLAN 22.1 item 4, navigation.js).

"No `beforeunload` guard anywhere; the drafts cover the capture box, but a
document mid-save, a board mid-drag and a chat mid-stream are not checked."
This covers the three surfaces named in the brief whose "has this been
saved yet" is a plain flag already read by their own Save button rather
than something that needs asking a server: the note edit form
(`noteFormDirty`, notes-list.js), the Capture box (`#entry-content`'s own
value) and a document mid-autosave (`docDirty`, documents.js). One reader
of each flag (`hasUnsavedWork`), never a second writer, and one
`beforeunload` listener for all three rather than the old `docDirty`-only
one that used to live in documents.js.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_has_unsaved_work_reads_the_three_existing_flags() -> None:
    """No parallel dirty state: the guard reads the flags each surface's own
    Save button already reads, through a `typeof` guard for the ones that
    belong to a lazily-loaded tab."""
    app = app_js_text()
    body = _function(app, "hasUnsavedWork")
    assert "docDirty" in body
    assert "noteFormDirty" in body
    assert 'appState.get("note") !== null' in body
    # The capture box is deliberately not asked about: its text survives a
    # tab switch and a reload (its localStorage draft), so leaving loses
    # nothing (decided 2026-09-27, after a prompt on every switch).
    assert '$("entry-content")' not in body
    # The document flag belongs to a lazy tab (documents.js), so it must be
    # read through a typeof guard, the same pattern switchTab's own
    # graphSimulation check already uses for a lazy module that may not
    # have loaded: a bare reference would throw ReferenceError on a session
    # that never opened Documents.
    assert 'typeof docDirty !== "undefined"' in body


def test_one_beforeunload_listener_covers_every_surface() -> None:
    """The old documents.js-only listener is gone; there is exactly one
    `beforeunload` guard left in the app's code, and it is built on
    `hasUnsavedWork`."""
    app = app_js_text()
    listeners = re.findall(r'addEventListener\("beforeunload"', app)
    assert len(listeners) == 1, f"expected one beforeunload listener, found {len(listeners)}"
    start = app.index('addEventListener("beforeunload"')
    block = app[start : app.index("});", start) + 3]
    assert "hasUnsavedWork()" in block
    assert "event.preventDefault()" in block


def test_documents_js_no_longer_has_its_own_docdirty_only_guard() -> None:
    """The narrower listener this replaces must actually be gone from
    documents.js, not just duplicated alongside the new one."""
    from tests._app_js import FRONTEND_DIR

    documents_js = (FRONTEND_DIR / "js" / "documents.js").read_text(encoding="utf-8")
    assert 'addEventListener("beforeunload"' not in documents_js


def test_switch_tab_asks_before_leaving_unsaved_work() -> None:
    """`switchTab` is the one function every in-app navigation (a tab
    press, a deep link, the back/forward restore) goes through, so the
    guard sits at its very top, before anything is revealed or torn
    down."""
    app = app_js_text()
    guard = _function(app, "confirmLeavingUnsavedWork")
    assert 'prefs.get("activeTab", null) === name' in guard, (
        "re-pressing the tab already on screen is not a departure"
    )
    # INBOX 711: an open note form stays open with its words kept, so only a
    # document can lose words on a switch, and it is saved before asking.
    assert "docDirty" in guard and "saveDocument({ silent: true })" in guard
    assert guard.index("saveDocument(") < guard.index("confirmDialog(")
    assert "noteFormDirty" not in guard

    switch_tab = _function(app, "switchTab")
    first_statement = switch_tab.split("\n")[1].strip()
    assert first_statement == "if (!(await confirmLeavingUnsavedWork(name))) return;", (
        "the guard must run before switchTab touches the DOM, not after"
    )


def test_confirm_dialog_is_the_recipe_used_not_window_confirm() -> None:
    """DESIGN.md's recipe index: a decision the person has to make is
    `confirmDialog`, never the browser's own `window.confirm`."""
    app = app_js_text()
    guard = _function(app, "confirmLeavingUnsavedWork")
    assert "window.confirm" not in guard


def test_note_edit_form_flag_is_reset_on_open_save_and_cancel() -> None:
    """`noteFormDirty` starts false on every fresh form (only one is ever
    open at a time) and is cleared on both ways out, so a stale true from a
    previous note can never leak into the next one."""
    app = app_js_text()
    form = _function(app, "renderEditForm")
    # Clean, unless it is the same note's form rebuilt over unsaved changes
    # (INBOX 432: `noteFormDraft` carries them across a list redraw).
    assert form.split("\n")[2].strip() == "noteFormDirty = Boolean(draft);"
    # Set by real edits to any of the three fields...
    assert 'textarea.addEventListener("input", () => { noteFormDirty = true; });' in form
    # Tags are chips since INBOX 606: typing in the tag field, and adding or
    # removing a chip (`setTags`), both mark the form.
    assert 'tagEntry.addEventListener("input", () => {\n    noteFormDirty = true;' in form
    assert "tagsInput.value = [...new Set(tags)].join(\", \");\n    noteFormDirty = true;" in form
    assert 'categorySelect.addEventListener("change", () => { noteFormDirty = true; });' in form
    # ...and cleared by both Save and Cancel.
    save_index = form.index('"Save changes"')
    cancel_index = form.index('"Cancel"')
    assert "noteFormDirty = false;" in form[save_index:cancel_index]
    assert "closeNoteForm()" in form[cancel_index:]
    assert "noteFormDirty = false;" in _function(app, "closeNoteForm")


def test_a_chat_answer_still_streaming_is_asked_about_on_close() -> None:
    """WORLD_CLASS_PLAN 22.1 item 4, "a chat mid-stream": the page guard also reads
    the streaming turn, but a tab switch does not (the stream keeps running)."""
    app = app_js_text()
    helper = _function(app, "chatMidStream")
    assert 'typeof chatStreaming !== "undefined"' in helper
    start = app.index('addEventListener("beforeunload"')
    block = app[start : app.index("});", start) + 3]
    assert "chatMidStream()" in block
    assert "chatMidStream" not in _function(app, "hasUnsavedWork")
