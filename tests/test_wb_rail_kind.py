"""INBOX 657, the owner: "I cant select on any of the other left sidebar
subtabs on the mindmap other than the library". A map reached from the board
picker (or made by New board) kept the board's rail, Notes, Layers and Pages,
and `wbOpenSidebar` sends each of those back to Library on a map. The rail's
kind is now set in `fetchWhiteboardState`, the one fetch every way onto a
board goes through. `scratchpad/ui-sweeps/maprail657.js`: 4 FAIL before,
PASS after, from the picker and from `openWhiteboardBoard`."""

from tests._app_js import frontend_text

WB = frontend_text("whiteboard.js")


def test_every_board_fetch_sets_the_rail_for_its_kind():
    start = WB.index("async function fetchWhiteboardState")
    body = WB[start:WB.index("\n}\n", start)]
    assert body.index("await wbRefreshMapState();") < body.index("wbSyncSidebarKind();")
    assert WB.count("wbSyncSidebarKind();") == 1
