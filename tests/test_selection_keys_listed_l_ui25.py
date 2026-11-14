"""Source text: the sheet rows, handler keys and palette rows are markup and JS text; the palette was driven in Chromium at merge (Select all ticked 3 of 3).

L-ui-modernisation-25: the keys navigation.js answers outside the shortcut
table (Ctrl+A, Escape and Delete on a ticked list; the arrows, Home and End in
menus and lists) are listed in the shortcuts sheet's "Always available" rows,
which are not rebindable by design (index.html's help body says why), and the
three selection keys are palette rows through the same `openSelectionScope`,
offered only while a list with ticks is on screen. Driven in Chromium on the
Library's Files list (CHANGELOG)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
FEATURES = (ROOT / "frontend" / "js" / "app-features.js").read_text(encoding="utf-8")
NAV = (ROOT / "frontend" / "js" / "navigation.js").read_text(encoding="utf-8")


def _always_rows():
    start = HTML.index('data-help-for="shortcuts-overlay-always-help"')
    return HTML[start : HTML.index("</ul>", start)]


def test_the_sheet_lists_the_selection_and_menu_keys():
    rows = _always_rows()
    assert "<kbd>Ctrl</kbd> <kbd>A</kbd>" in rows
    assert "<kbd>Delete</kbd>" in rows
    assert "<kbd>Home</kbd> <kbd>End</kbd>" in rows


def test_the_handler_still_answers_the_listed_keys():
    assert 'event.key.toLowerCase() === "a"' in NAV and 'event.key === "Delete"' in NAV
    assert '["ArrowDown", "ArrowUp", "Home", "End"]' in NAV


def test_the_palette_rows_use_the_same_scope_and_show_only_with_ticks():
    block = FEATURES[FEATURES.index("...(openSelectionScope() ? [") :]
    block = block[: block.index("] : []),")]
    for act in ("selectAll()", "clear()", "remove()"):
        assert f"openSelectionScope()?.{act}" in block
    assert 'keys: "Ctrl+A"' in block and 'keys: "Delete"' in block
