"""The Boards & maps sub-tab paints its cards without waiting for the board code (INBOX 1772).

The press used to start the `boards` bundle (the documents' editors, d3 and nine
whiteboard files, all parsed and run in document order) and only the gallery's own first line, in whiteboard.js, running after
all of it, asked for `/whiteboard/boards`; the miniature drawer (`map-preview.js`) was a
third step after the list. Measured at 4x CPU, 120 boards: the list left 1168 ms after the
press and the first card drew at 1294 ms; with the files already in the cache the card still
waited for the whole bundle to run.

Now the gallery is its own small file (`boards-gallery.js`, module `boardsGallery`), the
press starts it, the list and the miniature drawer at once, and the board code is asked for
in idle time once the cards are up.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR, lazy_modules_source


def _text(name: str) -> str:
    return (JS_DIR / name).read_text(encoding="utf-8")


def _press_branch() -> str:
    source = _text("library.js")
    start = source.index('if (targetId === "library-view-whiteboard") {')
    return source[start : start + 2600]


def test_the_press_starts_the_list_before_the_gallery() -> None:
    branch = _press_branch()
    assert "libraryBoardsPrefetch" in branch
    assert branch.index("libraryBoardsPrefetch") < branch.index('ensureModule("boardsGallery")')


def test_the_press_starts_the_miniature_drawer_with_it() -> None:
    branch = _press_branch()
    assert 'ensureModule("mapPreview")' in branch
    assert branch.index('ensureModule("mapPreview")') < branch.index('ensureModule("boardsGallery")')


def test_the_press_draws_from_the_gallery_file_not_the_board_code() -> None:
    branch = _press_branch()
    assert "renderLibraryBoardsGallery.show()" in branch
    assert "wbShowBoardsLanding" not in branch, "the stand-in would wait for the whole bundle"
    assert 'ensureModule("boards")' not in branch, "the board code is asked for after the cards, in the gallery file"


def test_the_gallery_takes_the_early_list_once_and_only_while_it_is_young() -> None:
    source = _text("boards-gallery.js")
    body = source[source.index("async function renderLibraryBoardsGallery()") :][:3500]
    assert "libraryBoardsPrefetch" in body
    assert "libraryBoardsPrefetch = null" in body, "one use, or a later redraw would show an old list"
    assert "Date.now()" in body, "an early list that waited out a slow bundle is asked for again"


def test_the_board_code_follows_the_cards_in_idle_time() -> None:
    source = _text("boards-gallery.js")
    show = source[source.index("renderLibraryBoardsGallery.show = ") :][:700]
    assert show.index("await renderLibraryBoardsGallery()") < show.index('ensureModule("boards")')
    assert "requestIdleCallback" in show
    assert "window.initWhiteboard" in show, "with the board code in, the landing is the board code's own (it leaves an open board)"


def test_a_press_on_the_landing_before_the_board_code_ran_fetches_it_and_presses_again() -> None:
    source = _text("boards-gallery.js")
    assert "if (window.initWhiteboard) return;" in source
    for control in ("wb-boards-new", "library-boards-new-map", "wb-boards-generate", "wb-boards-import"):
        assert f"#{control}" in source
    assert 'ensureModule("boards").then(() => button.click())' in source


def test_a_file_dropped_before_the_board_code_ran_is_held_and_dropped_again() -> None:
    source = _text("boards-gallery.js")
    drop = source[source.index("A file dragged over the landing starts the board code loading") :][:1500]
    assert 'landing?.addEventListener("dragover"' in drop and "ensureModule(\"boards\");" in drop
    assert "e.preventDefault();" in drop and "e.stopImmediatePropagation();" in drop
    assert 'new DragEvent("drop"' in drop and "held.items.add(file)" in drop


def test_the_new_arrow_is_mounted_with_the_cards_and_its_rows_wait_for_the_board_code() -> None:
    source = _text("boards-gallery.js")
    assert "function wbNewMenuMount()" in source and "  wbNewMenuMount();\n" in source
    assert "wbNewMenuMount" not in _text("whiteboard.js"), "the board bundle no longer builds it"
    mount = source[source.index("function wbNewMenuMount()") :][:1800]
    assert 'const afterBoards = (act) => () => ensureModule("boards").then(act);' in mount
    assert mount.count("run: afterBoards(") == 3


def test_the_hover_fetches_the_small_files_not_the_board_code() -> None:
    source = _text("lazy-entries.js")
    assert '["boardsGallery", "mapPreview"]' in source
    assert '"pointerover", "focusin"' in source
    warm = source[source.index("The gallery and the miniature drawer are fetched") :][:700]
    assert '"boards")' not in warm, "running 2.3 MB just before the press would delay the first card"


def test_the_gallery_file_is_in_both_bundles_that_call_it() -> None:
    modules = lazy_modules_source()
    gallery = re.search(r"boardsGallery: \[(.*?)\]", modules, re.S).group(1)
    assert '"/js/boards-gallery.js"' in gallery and "libraryList" in gallery, "its list code is library.js"
    app = _text("app.js")
    library = re.search(r"\n  library: \[(.*?)\],\n", app, re.S).group(1)
    assert '"/js/boards-gallery.js"' in library, "the board code calls the gallery, so every bundle that carries it carries the gallery"


def test_a_board_opened_by_code_is_not_covered_by_the_gallery_landing():
    # `openWhiteboardBoard` presses the sub-tab itself; the press draws the landing a step later
    # (once the gallery file is in), which hid a board opened from a link on the first Library visit.
    opener = _text("whiteboard.js")
    start = opener.index("async function openWhiteboardBoard(")
    body = opener[start : start + 1800]
    assert "openWhiteboardBoard.holdLanding = true" in body
    assert body.index("holdLanding = true") < body.index("wbShowCanvasView();")
    gallery = _text("boards-gallery.js")
    show = gallery[gallery.index("renderLibraryBoardsGallery.show = ") :][:600]
    assert "openWhiteboardBoard?.holdLanding" in show
    assert show.index("holdLanding") < show.index("wbShowBoardsLanding()")
