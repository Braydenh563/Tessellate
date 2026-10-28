# board-1028 remaining

Done (branch agent/board-1028; one code commit, see git log):
- B8: `wbDeleteFailed` (whiteboard.js) for sketch, node and object delete: drops the undo entry, restores redo, toasts.
- B16: edge-pan replays into d3-drag's own `mousemove.drag` listener, no broadcast.
- B21: eraser hit-tests every coalesced pointer sample (`wbEraseAt`); pointer events already carried touch and pen.
- B5 (part): `wbOnFrame` gate on the link-hover anchors and the port-drag hit test.
- U1, U2: `wbDefaultInk` and `wbReadableInk` (whiteboard-map.js) at render for default black or white strokes and for text against its sticky or the board.
- U3: Insert, Sticky note with Enter places a sticky at the view centre.
- U5: fold chevron, count and node buttons 24px floor, 44px on touch (`WB_INV_ZOOM_GRIPS` gained both).
- Tests: tests/test_wb_board_1028.py; tests/test_wb_edge_pan.py and tests/test_map_node_controls.py intents updated (20 to 24px floor, replay path).

Remaining:
- B5: the pen (whiteboard.js, containerEl pointermove near wbOnLockHoverMove's neighbours), lasso and marquee handlers collect or compute per event; coalescing them needs getCoalescedEvents so no point is lost. Not done.
- B3, B4 (incremental render): out of scope by brief.
- U1/U2 ink remap is unverified in the browser (logic is node-tested); a sweep on a dark board with a stored black stroke is the check.
- tests/test_static_compression.py was already red on the base (320627 over the 320600 cap), unrelated to these lazy files.
- Pre-existing reds on the base, not touched: tests/test_static_compression.py (total), tests/test_undo_coverage.py (chat-edit.js regenerateFrom, chatTooLong).
