"""The Boards & maps sub-tab asks for its list while its code downloads (INBOX 1772).

The press used to start the `boards` bundle (about 820 KB gzipped, then parsed in
document order) and only the gallery's own first line, running after all of it,
asked for `/whiteboard/boards`; the miniature drawer (`map-preview.js`) was a third
step after the list. Measured at 4x CPU: the list request left 1168 ms after the
press, the first card drew at 1294 ms. The press now starts all three at once.
"""

from __future__ import annotations

from tests._app_js import JS_DIR


def _text(name: str) -> str:
    return (JS_DIR / name).read_text(encoding="utf-8")


def _press_branch() -> str:
    source = _text("library.js")
    start = source.index('if (targetId === "library-view-whiteboard") {')
    return source[start : start + 1800]


def test_the_press_starts_the_list_before_the_bundle() -> None:
    branch = _press_branch()
    assert "libraryBoardsPrefetch" in branch
    assert branch.index("libraryBoardsPrefetch") < branch.index("wbShowBoardsLanding()")


def test_the_press_starts_the_miniature_drawer_with_it() -> None:
    branch = _press_branch()
    assert 'ensureModule("mapPreview")' in branch
    assert branch.index('ensureModule("mapPreview")') < branch.index("wbShowBoardsLanding()")


def test_the_gallery_takes_the_early_list_once_and_only_while_it_is_young() -> None:
    source = _text("whiteboard.js")
    body = source[source.index("async function renderLibraryBoardsGallery()") :][:3500]
    assert "libraryBoardsPrefetch" in body
    assert "libraryBoardsPrefetch = null" in body, "one use, or a later redraw would show an old list"
    assert "Date.now()" in body, "an early list that waited out a slow bundle is asked for again"


def test_the_board_code_is_warmed_when_the_sub_tab_is_reached() -> None:
    source = _text("lazy-entries.js")
    assert 'library-view-whiteboard"]\', "boards")' in source
    assert '"pointerover", "focusin"' in source
