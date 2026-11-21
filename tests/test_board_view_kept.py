"""A board's view (pan and zoom) is kept past a reload, per device (WHITEBOARD 1340 "saving the view with the board", OPEN F2).

Until now `wbBoardViews` was memory for the session. The same view is written to `prefs` under `wb-view-<id>` when the board is left
and when the page is hidden, and read back when the session has none. The restore rule (a view that shows too little of the content is
dropped and the board framed) is the one that already guarded the session copy, so a stale view cannot leave a board blank.
Driven in Chromium 2026-11-10: pan and zoom a board, reload, open it again (numbers in the remaining file).
"""

from tests._app_js import frontend_text

WB = frontend_text("whiteboard.js")


def test_the_view_is_written_to_prefs_when_the_board_is_left_and_the_page_hidden():
    assert 'prefs.set(`wb-view-${id}`, JSON.stringify({ x: t.x, y: t.y, k: t.k }));' in WB
    assert 'window.addEventListener("pagehide", wbRememberBoardView);' in WB


def test_the_restore_reads_the_stored_view_when_the_session_has_none_and_checks_it_the_same_way():
    assert "const saved = boardId == null ? null : wbBoardViews.get(boardId) || wbRememberBoardView.stored(boardId);" in WB
    start = WB.index("wbRememberBoardView.stored = (id) => {")
    body = WB[start : start + 600]
    assert "Number.isFinite(view.x) && Number.isFinite(view.y) && Number.isFinite(view.k)" in body and "catch" in body
    assert "wbViewShowsContent(saved, bounds, free)" in WB
