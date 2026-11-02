"""Notes held in the offline outbox are drawn in the notes list (lo12 item 1).

Measured in a browser (8812, POST /entries aborted): two held notes drew two
`li.pending-note` rows above the saved notes, each with a "Waiting to save"
`.chip.item-label`, and a flush removed them. The suite cannot see the DOM, so
these hold the wiring that makes it happen."""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def test_the_row_builder_lives_in_the_lazy_quick_note_script():
    quick = (JS / "quick-note.js").read_text(encoding="utf-8")
    assert "function renderPendingNoteRows()" in quick
    assert 'chip("ph:cloud-slash Waiting to save", "item-label")' in quick
    # No server-only action on a held note: no menu, no buttons.
    body = quick.split("function renderPendingNoteRows()")[1].split("// --- Quick note")[0]
    assert "kebabMenu" not in body and "createElement(\"button\")" not in body


def test_every_write_to_the_outbox_redraws_the_rows():
    quick = (JS / "quick-note.js").read_text(encoding="utf-8")
    write = quick.split("function writeNoteOutbox(list)")[1].split("function newNoteClientKey")[0]
    assert "renderPendingNoteRows();" in write


def test_the_list_render_asks_for_the_rows_only_when_something_is_held():
    code = app_js_text()
    assert '"renderPendingNoteRows"]' in code  # a lazy entry point
    notes = (JS / "notes-list.js").read_text(encoding="utf-8")
    render = notes.split("function renderEntries(")[1].split("A selection is of what is on screen")[0]
    assert 'prefs.get("noteOutbox", null)' in render
    assert "renderPendingNoteRows();" in render


def test_by_site_groups_a_hostless_link_by_its_scheme():
    """lo12 item 3: mailto: sat under its own address; now "Email", and any
    other hostless scheme under its name. The sort uses the same key, or a
    group would not be one run of rows."""
    lib = (JS / "library.js").read_text(encoding="utf-8")
    assert 'site: host || (scheme === "mailto" ? "Email" : scheme),' in lib
    assert "bookmarkAddress(bookmark.url).site" in lib
    assert "const host = (url) => bookmarkAddress(url).site;" in lib


def test_by_month_contents_puts_documents_in_their_month():
    """lo12 item 2: the date mode used to trail one "Documents" section."""
    lib = (JS / "library.js").read_text(encoding="utf-8")
    render = lib.split("async function renderContents()")[1].split("function contentsSetAll")[0]
    assert "contentsMonthKey(item.doc.created_at || item.doc.updated_at)" in render
    assert 'if (shownDocs.length && contentsMode !== "date")' in render
