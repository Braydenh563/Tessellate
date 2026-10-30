"""Board performance and hygiene rows of audit 1028 (B31, B6, B7, B18, B17, B14).

Source-shape checks, each naming the row; the browser numbers are in
`scratchpad/ui-sweeps/wb1030-board.js`.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def test_b31_switching_boards_cancels_pending_timers_and_frames() -> None:
    cancel = _function(BOARD, "wbCancelBoardTimers")
    for name in (
        "wbClampSyncFrame", "wbZoomFrame", "wbCullFrame", "wbSelectionBarFrame", "wbRenderFrame",
        "wbRevealTimer", "wbStickyDates.timer", "wbAddGate.panBarTimer", "wbMarkMoving.timer",
    ):
        assert name in cancel, name
    # A nudge not yet saved is written out, never dropped.
    assert "wbFlushNudge()" in cancel
    switch = _function(BOARD, "openWhiteboardBoard")
    assert switch.index("wbCancelBoardTimers()") < switch.index("window.currentBoardId = boardId")
