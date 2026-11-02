"""Audit 1028 rows fixed by agent a28s (S62, S91, S92, U38, U48, B32, B28, B34, D53, K35).

Each test pins the cause of one row in the source, so the fix cannot be undone
without a failing line that names the row. The browser behaviour of each is
measured in the sweep named in its CHANGELOG line.
"""

from __future__ import annotations

from tests._app_js import app_js_text


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
