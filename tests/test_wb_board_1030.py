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


def test_b7_deletes_are_top_level_functions_with_no_render_refs() -> None:
    for name in ("wbDeleteSketch", "wbDeleteNode", "wbDeleteObject"):
        # Declared at column 0: not a closure re-made by each render.
        assert f"\nasync function {name}(d) {{" in BOARD, name
    assert "DeleteSketchRef" not in BOARD and "DeleteNodeRef" not in BOARD and "DeleteObjectRef" not in BOARD
    interchange = (ROOT / "frontend" / "js" / "whiteboard-interchange.js").read_text(encoding="utf-8")
    assert "DeleteObjectRef" not in interchange
    render = _function(BOARD, "renderWhiteboard")
    assert "async function wbDelete" not in render and "async function delete" not in render


def test_b6_init_is_guarded_so_a_second_call_adds_no_listeners() -> None:
    start = BOARD.index("async function initWhiteboard() {")
    head = BOARD[start : start + 200]
    assert "if (wbInitialized) return;\n  wbInitialized = true;" in head, "set before the first await"
    assert BOARD.count("wbInitialized = ") == 2, "set once, reset nowhere"


def test_b18_a_render_does_not_remeasure_unchanged_topics() -> None:
    # The no-op render of a 200-topic map reads layout 0 times (wb1030-map.js):
    # an element measured once keeps its own number.
    assert "known = this._wbMeasuredH" in BOARD


def test_b17_link_lookups_parse_each_sketch_once_per_version_of_its_data() -> None:
    parsed = _function(BOARD, "wbParsedLink")
    assert "hit.data === sketch.data" in parsed, "an edited sketch is parsed again"
    for name in ("wbLinkedSketchesFor", "wbLinkSketchIndex"):
        body = _function(BOARD, name)
        assert "wbParsedLink(sketch)" in body and "JSON.parse(sketch" not in body, name
    assert "wbLinkParseCache.clear()" in _function(BOARD, "openWhiteboardBoard")


def test_b14_branch_export_opens_the_one_export_dialog() -> None:
    mapjs = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    branch = _function(mapjs, "wbMapExportBranch")
    assert "wbExportBoard();" in branch and "wbMultiSelection.add(" in branch, "selection, then the one dialog"
    assert BOARD.count("function wbExportBoard()") == 1
    assert 'overlay.className = "modal-overlay confirm-overlay wb-export-overlay"' in BOARD
    assert mapjs.count("wb-export-overlay") == 0, "no second export dialog in the map file"
