"""Opening a board from code is not undone by the gallery's late landing (ledger L374, mindmap3 sweep).

`openWhiteboardBoard` presses the Boards sub-tab, whose handler loads the small gallery file and then
calls `show`, which showed the landing and hid the canvas. After an import into a library with many
boards the file arrived after the map had opened, so "an import opens the map it just created" failed
(driven: the canvas class went `wb-entering` to `hidden` within 400 ms, a trace through
`wbShowBoardsLanding`). The opener stamps the time and `show` stands down for five seconds when the
canvas is up.
"""

from __future__ import annotations

from tests._app_js import JS_DIR, frontend_text


def _text(name: str) -> str:
    return frontend_text(name) if name.startswith("whiteboard") else (JS_DIR / name).read_text(encoding="utf-8")


def test_the_opener_stamps_its_time_before_pressing_the_sub_tab() -> None:
    source = _text("whiteboard.js")
    start = source.index("async function openWhiteboardBoard(")
    body = source[start : start + 1200]
    assert "openWhiteboardBoard.at = performance.now()" in body
    assert body.index("openWhiteboardBoard.at") < body.index('data-target="library-view-whiteboard"')


def test_show_stands_down_when_a_board_was_just_opened_by_code() -> None:
    source = _text("boards-gallery.js")
    start = source.index("renderLibraryBoardsGallery.show = ")
    body = source[start : start + 900]
    assert "window.openWhiteboardBoard?.at" in body
    assert body.index("openWhiteboardBoard?.at") < body.index("wbShowBoardsLanding()")
    assert '$("wb-canvas-view")' in body
