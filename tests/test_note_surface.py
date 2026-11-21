"""One editor everywhere: the lint DOCUMENTS_PLAN Phase 8 names.

The plan's decision is that every note editor in the app is one factory,
`noteSurface`, over the Phase 2 adapter, and that what differs between them is
size and chrome, never behaviour. A browser sweep
(`scratchpad/ui-sweeps/notesurface.js`) is what proves the engine mounts and
the toolbar, the shortcuts and the "/" menu reach it. What a sweep cannot see
is a *new* note textarea added next month with none of that, in a tab nobody
was sweeping: it renders perfectly and is simply the old editor again, which
is the whole failure this phase exists to end.

So this is the ratchet: a textarea in the page whose content is note text is in
the factory's table, or it is in the list of boxes that are deliberately not
note editors, with a reason. There is no third state.
"""

from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import app_js_text, frontend_text

ROOT = Path(__file__).resolve().parent.parent
DOCS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "09-editor.css").read_text(encoding="utf-8")


def _region(text: str, name: str) -> str:
    start = text.index(f"// {name}-BEGIN")
    end = text.index(f"// {name}-END")
    return text[start:end]


def _table_ids() -> set[str]:
    region = _region(DOCS, "NOTE-SURFACE")
    table = region[region.index("const NOTE_SURFACES = {"):]
    table = table[: table.index("\n};")]
    return set(re.findall(r'"([a-z0-9-]+)":\s*\{', table))


# Textareas in the page that hold something other than note text, each with the
# reason it is not a note editor. A new entry here is a decision, not a
# formality: it says "this box is not somewhere a person writes a note".
NOT_NOTE_TEXT = {
    # The document's own surface: it *is* the engine already (Phase 2), and it
    # mounts through `mountDocEditor` with the gutter, the find panel and the
    # autosave a document needs.
    "doc-content",
    # A sentence, not a note (the plan says so): the reminders' magic box.
    "reminder-magic",
    # Chat is its own recipe: send on Enter, "/" and `[[` only.
    "chat-input",
    # A skill's steps: instructions read line by line by `skills.normalise`,
    # not note text. Phase 8c gives this box the "/" menu and nothing else,
    # with its own command set (`skillCommands` in editor.js: the placeholders
    # the form declares and the tools it has ticked). A Live view here would
    # render a heading or a table that no step can be.
    "skill-steps",
}


def test_the_factory_is_built_on_the_phase_2_adapter() -> None:
    """Not a second editor with its own idea of what a surface is."""
    region = _region(DOCS, "NOTE-SURFACE")
    for needed in ("function mountNoteSurface(", "cmSurface(view, noteSurfaceMeta(host))",
                   "const NOTE_SURFACES = {", "loadCodeMirror()"):
        assert needed in region, f"the note surface region no longer carries {needed}"
    # The textarea stays the value carrier: both directions of the mirror.
    assert "host.dispatchEvent(new Event(\"input\"" in region, (
        "the mirror no longer raises the input event the draft save and the "
        "character count hang off"
    )
    assert "Object.defineProperty(host, \"value\"" in region, (
        "a script writing box.value no longer reaches the view"
    )


def test_every_note_textarea_is_in_the_factory_table() -> None:
    ids = _table_ids()
    assert ids, "NOTE_SURFACES is empty"
    boxes = set(re.findall(r'<textarea[^>]*\sid="([a-z0-9-]+)"', HTML))
    # A textarea whose id is not in either list is the thing this lint is for.
    unplaced = sorted(
        box for box in boxes
        if box not in ids and box not in NOT_NOTE_TEXT and _looks_like_note_text(box)
    )
    assert not unplaced, (
        "these note textareas are not mounted through noteSurface(): "
        + ", ".join(unplaced)
        + ". Add them to NOTE_SURFACES in documents.js, or to NOT_NOTE_TEXT here "
        "with the reason they are not a note editor."
    )


def _looks_like_note_text(box_id: str) -> bool:
    """A textarea for note-shaped prose, by the names this app uses.

    Deliberately narrow. The page holds textareas for a skill's steps, a
    prompt, a JSON blob and an import paste, and none of those is a note; the
    ones this phase is about are the capture box, the edit forms, the graph's
    note boxes and the two Write-with-AI panes.
    """
    return box_id in {
        "entry-content",
        "entry-edit-content",
        "graph-popup-content",
        "graph-new-content",
        "draft-thoughts",
        "draft-text",
    }


def test_the_note_surface_has_one_recipe_in_the_editor_stylesheet() -> None:
    """Size and chrome, in one place, out-specifying the library."""
    assert ".note-surface {" in CSS, "the .note-surface recipe is gone from 09-editor.css"
    for size in ("inline", "box"):
        assert f".note-surface-{size} .cm-editor .cm-scroller" in CSS, (
            f"the {size} size no longer bounds the editor's own scroller"
        )
    assert ".note-surface > textarea.note-surface-mirror" in CSS, (
        "the mirrored textarea is no longer laid over the view; hiding it takes "
        "the selection API and every popup positioned off its rectangle with it"
    )


def test_the_note_surface_does_not_borrow_the_document_pipeline() -> None:
    """A note must not reach the document's autosave or its findings.

    Both were live bugs waiting to happen: `docSurfaceChangeHandlers` is the
    document's own pipeline, and `docProseFound` holds findings at the
    *document's* offsets, which drawn over a note underline whatever words
    happen to sit at those positions.
    """
    region = _region(DOCS, "NOTE-SURFACE")
    assert "docSurfaceChangeHandlers" not in region, (
        "a note surface is pushing into the document's change handlers"
    )
    assert "docFindingsPlugin" not in region, (
        "a note surface is drawing the document's prose findings"
    )


def test_app_js_mirrors_the_table_for_the_boot_time_door():
    """documents.js is a lazy bundle, so its delegated focus listener is not
    there on a fresh boot. app.js keeps the same ids in `NOTE_SURFACE_IDS`
    and fetches the bundle on the first focus of one of them; a box added to
    one list and not the other is a bare textarea until the Library tab has
    been visited, which is invisible to every other test here."""
    app = app_js_text()
    start = app.index("const NOTE_SURFACE_IDS = new Set([")
    block = app[start : app.index("]);", start)]
    ids = set(re.findall(r'"([a-z0-9-]+)"', block))
    assert ids == _table_ids(), (
        f"app.js NOTE_SURFACE_IDS {sorted(ids)} differs from documents.js NOTE_SURFACES {sorted(_table_ids())}"
    )


def test_the_board_card_keeps_its_contract_on_the_engine() -> None:
    """Phase 8c, the board half. The card's editor is a `NOTE_SURFACES` row
    now, and the four behaviours it hung off the textarea's own listeners
    (Enter commits, Escape abandons, blur commits, keys never reach the
    board's gestures) are carried where a mounted view still honours them:
    keys the engine runs first, and listeners on the card's content element.
    `scratchpad/ui-sweeps/wbcardeditor.js` drives all four."""
    assert "wb-card-editor" in _table_ids()
    wb = frontend_text("whiteboard.js")
    body = wb.split("function wbEditNodeText(", 1)[1].split("\nfunction ", 1)[0]
    assert 'box.id = "wb-card-editor"' in body
    assert "box.noteSurfaceKeys" in body and 'key: "Enter"' in body and 'key: "Escape"' in body
    assert 'content.addEventListener("keydown", (event) => event.stopPropagation()' in body, (
        "the guard that keeps Tab and Enter out of the board's branch gestures is gone"
    )
    assert 'content.addEventListener("focusout"' in body, "blur no longer commits"
    region = _region(DOCS, "NOTE-SURFACE")
    assert "host.noteSurfaceKeys" in region, "the engine no longer runs a host's own keys"


def test_a_note_box_gone_before_the_editor_loads_is_not_mounted():
    """cardarrows sweep at 390: a card's editor closed with Escape while
    CodeMirror loaded threw "Cannot read properties of null (reading
    'insertBefore')" in `mountNoteSurface`. After the load, a box with no
    parent gets the plain surface and nothing is inserted."""
    docs = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    start = docs.index("async function mountNoteSurface(")
    body = docs[start : docs.index("\n}\n", start)]
    loaded = body.index("await loadCodeMirror()")
    guard = body.index("if (!host.parentNode) return textareaSurface(host);")
    assert loaded < guard < body.index("host.parentNode.insertBefore(wrap, host)")


def test_a_late_mount_does_not_take_the_focus_from_an_open_sheet():
    """Dashboard Write link, then "?" (measured, Playwright): the shortcuts
    sheet focused its Close button and the editor's mount took the focus about
    150 ms later. Both places that hand the focus to the editor after a late mount
    do so only while no modal dialog is open (`activeOverlay`)."""
    docs = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
    assert "!activeOverlay() && s?.focus()" in docs
    wiring = (ROOT / "frontend" / "js" / "wiring.js").read_text(encoding="utf-8")
    start = wiring.index("function startNewNote()")
    assert "!activeOverlay() && s?.focus()" in wiring[start : wiring.index("\n}\n", start)]


def test_a_late_mount_does_not_take_the_focus_back_from_a_box_left_meanwhile():
    """e2e capture-filing "Undo takes a new note back", under load: Save puts the
    caret in the composer (`focusCaptureBox`), the editor bundle is still
    loading, the person leaves the box (blur), and the mount then focused the
    editor anyway about 400 ms later. Ctrl+Shift+Z met a text field and Redo,
    which a text field keeps for itself, never ran. The delegated listener hands
    the focus on only while the box it mounted for is still the focused one."""
    start = DOCS.index('document.addEventListener("focusin"', DOCS.index("NOTE-SURFACE-END") - 900)
    body = DOCS[start : DOCS.index("});", start)]
    assert body.index("document.activeElement !== host") < body.index("s?.focus()")


def test_a_broken_editor_bundle_is_asked_for_once():
    """D47: with the bundle blocked, the idle warm-up failed and then
    code-colour's `loadCodeMirror()` asked again (measured, 2 requests and 2
    warnings; `scratchpad/ui-sweeps/docfallback.js` now reads 1 and 1). The
    loader itself refuses once `docCmBroken` is set, so no caller can retry."""
    start = DOCS.index("function loadCodeMirror() {")
    body = DOCS[start : DOCS.index("\n}\n", start)]
    assert body.index("if (docCmBroken) return Promise.resolve(null);") < body.index("docCmLoad = new Promise")
