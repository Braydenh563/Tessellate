# graph-lag-1029: graph interaction lag and the reopen drift (audit 1029 ranks 36 and 28)

Sweep: session scratchpad `graphlag.js` (hover 40 moves, wheel zoom 12 steps, rAF deltas at CPU 4x through CDP; drift = every note before and after a reload), `probe.js` (redraw-only loops with parts of the draw removed). Fixture: `scratchpad/graph-fixture.js 500 1015` (500 notes, 965 links).

## G6, the map opens where it was left
- Cause: a restored layout (alpha 0, every note placed) still owed the untangle passes, so the worker ran them and their relax over a map that had already had them. A second render on open (warm, alpha 0 from the hold) did the same.
- Fix: the worker's `init` at alpha 0 with every note placed marks the untangle spent, posts the positions as they came and ends (graph-worker.js, `case "init"`). Test: tests/test_graph_restore_holds.py (red 102.7 px, green under 0.5 px).
- 500 notes, reload: RMS 99.1 px, max 339 px, 500 moved over 5 px; after RMS 0.4 px, max 0.7 px (the save's whole-pixel rounding), 0 moved over 5 px, alpha 0 throughout.

## G5, G8, the composed frame
- Cause: the time was raster at commit (`LayerTreeHost::DoUpdateLayers`, about 80 ms a frame at 4x), not script (the paint's own JS 11 ms). Its own layer for the canvas, or a hidden page, changed nothing, so G8's blur theory was wrong.
- Fix: `gcDrawComposed` (graph-canvas.js, before `gcDraw`) paints the map once into a rest layer and a dimmed layer. Camera and hover frames (`gcRequestDraw(s, true)`) blit the visible part of each and paint only the hover's notes and lines on top. A plain `gcRequestDraw` still paints the whole frame. The hover card is measured by a ResizeObserver and moved by a transform on its own layer, so it no longer forces a layout or repaints every frame. `gcEdgeAtWorld` rejects by bounding box first.
- A/B at 500 notes and 4x, three alternating rounds at machine load 4 to 9 (other agents' pytest): hover p50 100 to 116.7 ms before, 50 after; zoom p50 133 to 183 ms before, 16.7 to 33.3 after; pan p95 116 to 150 ms before, 33 to 50 after. A held hover composes at 16.7. Drift after a reload is still 0.4 px RMS.
- G28: the map already reads `/graph?slim=1` (graph.js 1968), so no change was made.

done: step 1 (G6), step 2 (G5/G8 composed frame).
remaining:
- Hover p50 is 50 ms, against a 16 ms target. An in-page A/B puts the hover card's refill on each new note at about 17 ms of it (50 with the card, 33.3 without). The rest is the floor here: SwiftShader software compositing (`SoftwareRenderer::DoDrawQuad`) on a loaded machine. Possible next steps: refill the card only once the pointer rests (a UX decision for the owner, so an INBOX entry), and re-measure on an idle machine with a real GPU.
- The graph renders twice on open (two worker inits, the second warm at alpha 0); harmless since G6, but it costs work.
