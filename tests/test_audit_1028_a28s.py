"""Audit 1028 rows fixed by agent a28s (S62, S91, S92, U38, U48, B32, B28, B34, D53, K35).

Each test pins the cause of one row in the source, so the fix cannot be undone
without a failing line that names the row. The browser behaviour of each is
measured in the sweep named in its CHANGELOG line.
"""

from __future__ import annotations

from tests._app_js import JS_DIR, app_js_text


def _js(name: str) -> str:
    """A lazy bundle's file, which `app_js_text()` (the boot scripts) does not hold."""
    return (JS_DIR / name).read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    at = text.index(start)
    return text[at : text.index(end, at + 1)]


def test_s62_editor_palette_with_no_match_offers_a_notes_search():
    """S62: ">" and words that match no editor command left an empty list. A row
    now carries them to Find anything, notes only."""
    block = _between(app_js_text(), 'if (lowered.startsWith(">")) {', "const base = paletteBase(")
    assert "Search notes for" in block
    assert 'openFinder(typed, { kind: "note" })' in block


def test_s91_the_window_title_follows_the_view_and_keeps_the_unread_count():
    """S91 was already fixed when it was swept: the router paints the view into
    the window title and `paintTitle` keeps the unread count in front of it."""
    text = app_js_text()
    assert "setTitleView([item, view].filter(Boolean).join(\" · \"))" in text
    assert "document.title = pageTitle.count > 0 ? `(${pageTitle.count}) ${base}` : base;" in text


def test_u38_a_document_title_another_has_is_said_once_and_left_as_typed():
    """U38: the save says so in a toast, once per document and name; no suffix."""
    block = _between(_js("documents.js"), "async function docSaveOnce(", "} catch (error) {")
    assert "Another document is called" in block
    assert "said.has(" in block and "said.add(" in block
    assert '" (2)"' not in block


def test_s92_a_loaded_or_filtered_list_says_its_count_through_the_one_live_region():
    """S92: Notes and the Library announce their count, settled and once, through
    `announce` (the page's `#live-region`), not a region each."""
    text = app_js_text()
    assert 'announce(`${scope}: ${nounCount(visible.length, "note")}`, { settle: 600, once: true })' in text
    assert 'announce(`Library: ${nounCount(items.length, "item")}`, { settle: 600, once: true })' in _js("library.js")
    head = _between(text, "function announce(message,", "// Jump to an entry")
    assert "settle" in head and "once" in head
