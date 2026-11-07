"""PR 216 review of Settings, What it remembers, Confirmed patterns: a long list is read
to its end instead of cut at the first page, and a row with no notes list still draws.
Source-reading tests, in this repo's way for settings code; the page behaviour was
driven in a browser (see the CHANGELOG line)."""

from __future__ import annotations

from tests._app_js import with_pieces


def _block(name: str, size: int = 2400) -> str:
    js = with_pieces("settings-controls.js")
    return js[js.index(name) :][:size]


def test_every_page_of_the_confirmed_list_is_read():
    pages = _block("const confirmedPages = async () => {", 600)
    # Each request starts where the rows read so far end, and stops on an empty page.
    assert "/insights/confirmed?limit=200&offset=${items.length}" in pages
    assert "while (items.length < total)" in pages and "break;" in pages
    draw = _block("const drawConfirmed = async () => {")
    assert "confirmedPages()" in draw and 'apiJson("/insights/confirmed")' not in draw


def test_a_row_without_a_notes_list_still_draws():
    draw = _block("const drawConfirmed = async () => {")
    assert "item.notes.slice" not in draw and "item.notes.length" not in draw
    assert "const notes = item.notes || [];" in draw
