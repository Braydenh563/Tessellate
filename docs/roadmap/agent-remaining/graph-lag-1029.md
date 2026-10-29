# graph-lag-1029: graph interaction lag and the reopen drift (audit 1029 ranks 36 and 28)

Sweep: session scratchpad `graphlag.js` (hover 40 moves, wheel zoom 12 steps, rAF deltas at CPU 4x through CDP; drift = every note before and after a reload), `probe.js` (redraw-only loops with parts of the draw removed). Fixture: `scratchpad/graph-fixture.js 500 1015` (500 notes, 965 links).

## G6, the map opens where it was left
- Cause: a restored layout (alpha 0, every note placed) still owed the untangle passes, so the worker ran them and their relax over a map that had already had them. A second render on open (warm, alpha 0 from the hold) did the same.
- Fix: the worker's `init` at alpha 0 with every note placed marks the untangle spent, posts the positions as they came and ends (graph-worker.js, `case "init"`). Test: tests/test_graph_restore_holds.py (red 102.7 px, green under 0.5 px).
- 500 notes, reload: RMS 99.1 px, max 339 px, 500 moved over 5 px; after RMS 0.4 px, max 0.7 px (the save's whole-pixel rounding), 0 moved over 5 px, alpha 0 throughout.

done: step 1 (G6).
next: G5/G8 cheap frame, graph-canvas.js `gcDraw` (2310): cached scene bitmap for camera and hover-only frames.
