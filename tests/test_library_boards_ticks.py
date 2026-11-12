"""The Library's Boards & maps ticks line up with the cards drawn.

`syncLibraryBoardsTicks` (library.js) grafts a selection tick onto each card
whiteboard.js drew. It used to fetch the board list again and match it to the
cards by position, bailing when the lengths differed: it narrowed by the
search box and the sort but not by the Maps / Boards / All chip, so with a chip
on no card got a tick ("Select all" and the bulk Delete were dead under the
filters people use to find a map).

INBOX 496 ("it takes a while to load the boards and maps library subtab") took
the second fetch away: every visit asked for the whole list twice. Each card
now carries the board it was drawn from (`card.wbBoard`), so the tick is that
board whatever the filter, and the gallery and the tick cannot drift because
there is one list. `scratchpad/ui-sweeps/boardticks.js` drives it in Chromium.
"""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def _body(text: str, signature: str) -> str:
    start = text.index(signature)
    end = text.index("\n}\n", start)
    return text[start:end]


def test_gallery_and_tick_sync_narrow_through_one_function() -> None:
    whiteboard = (JS / "boards-gallery.js").read_text(encoding="utf-8")

    assert "window.wbBoardsOfTypeFilter = function" in whiteboard

    gallery = _body(whiteboard, "function drawLibraryBoardsGallery(listed)")
    assert "window.wbBoardsOfTypeFilter(boards)" in gallery
    # The private copy this replaced must not come back beside it.
    assert "BOARD_FILTERS.find" not in gallery
    assert "card.wbBoard = board" in gallery


def test_tick_sync_reads_the_card_and_fetches_nothing() -> None:
    library = (JS / "library.js").read_text(encoding="utf-8")
    ticks = _body(library, "function syncLibraryBoardsTicks()")
    assert "card.wbBoard" in ticks
    assert "apiPagedList" not in ticks and "apiJson" not in ticks


def test_a_rearrangement_redraws_without_a_request() -> None:
    whiteboard = (JS / "boards-gallery.js").read_text(encoding="utf-8")
    assert '$("library-boards-search")?.addEventListener("input", redrawLibraryBoardsGallery)' in whiteboard
    sort = whiteboard[whiteboard.index("prefs.set(BOARD_SORT_KEY, select.value);"):][:120]
    assert "redrawLibraryBoardsGallery()" in sort
    chip = whiteboard[whiteboard.index("prefs.set(BOARD_FILTER_KEY, filter.key);"):][:120]
    assert "redrawLibraryBoardsGallery()" in chip
    # A visit draws what it had, and redraws only when the answer changed.
    render = _body(whiteboard, "async function renderLibraryBoardsGallery()")
    assert "libraryBoardsLastText" in render
