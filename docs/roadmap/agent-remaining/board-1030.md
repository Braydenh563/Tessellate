# Board audit 1028 rows, agent board-1030 (branch agent/board-1030)

Done (all measured with `scratchpad/ui-sweeps/wb1030-board.js`, port 8795):
- B20 2bdd1af: persistent lock badge (replaces the hover pin); badge count 0 to 1 without hover.
- B31 d24244e: board switch cancels frames and timers, flushes a nudge; 5 pending to 0.
- B7 8db4f3e: wbDeleteSketch/Node/Object top level, refs gone.
- B6 8db4f3e: already guarded (`wbInitialized`); re-init adds 0 window or document listeners; pinned.
- B18 8db4f3e: already fine; no-op render of a 200-topic map reads layout 0 times (edit: 2); pinned.
- B17 fc3dc90: `wbParsedLink` cache by id plus data string; 20 lookups over 600 sketches 8.9 ms to 0.7 ms.
- B14 fc3dc90: already one dialog (`wbExportBoard`); pinned.
- B19: already bound and rerouting (start x 200 to 320 after widening the shape); pinned.

Left:
- B15 (L): four drag mechanisms; the synthetic mousemove bridge was already removed for B16, the rest (pointer capture, window pointermove, mouse events, d3.drag) is a rewrite of whiteboard.js drag code at about 17382 to 17575 and the d3.drag handlers per kind. Needs its own session with a touch-device sweep.
- B10, B26: skipped as briefed (native PDF; context menu regroup).
- wb1005-pages.js "right-click on it offers to unlock this one first" fails on base too (menu opens with the board entries and "Unlock 1 locked item" last); pre-existing, not from these changes.
- tests/test_scratchpad_size.py is over its cap at the base (770 tracked vs 766); this branch adds one file (wb1030-board.js).
