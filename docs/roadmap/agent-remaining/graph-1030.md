# Graph 2,000-note cold layout (audit 1029 G3, 1028 S2), agent branch agent/graph-1030 (not pushed)

Measured on Chromium 1x, 4 cores at load 4 to 5 (other agents running), 2,000 notes and 3,796 links
(`graph-fixture.js`), a PerformanceObserver longtask sweep and a worker-message timeline; sweeps in the
session scratch `sgs/` (`lt.js`, `lt2.js`, `m.js`, `trace.js`, `wb.js`).

## Done

- Plain frames (`gcLightFrame`, `gcDrawLight`, graph-canvas.js): while a map of 2,500 notes and links or more
  is laying out, a tick strokes the shortest links up to 120,000 device pixels of line in one path and fills one
  dot path per colour. Raster time follows line length, not link count (3,796 links at 2x: 284 ms whole, 28 ms
  for the links under 300 units).
- Clearance force (graph-worker.js `clearanceForce`): cell-sorted coordinate arrays, a mark array for the
  per-line dedupe; same pushes as the brute force (tests/test_graph_clearance_corridor_1029.py). 55 to 77 ms a
  tick down to 30 to 40 in Chromium; 40.7 to 26.2 ms in the node bench.
- Cooling (`alphaDecayFor`): about 100 ticks at 2,000 notes (was 225); 750 notes and under unchanged.
- Cold open 1x: settled 24.7 s to 9.4-10.2 s; long tasks 149 (sum 15.7 s, max 559 ms) to 20-29 (sum 2.0-2.7 s,
  max 295-332 ms), 1 over 100 ms after the first paint. 4x CPU: 120 tasks (21.2 s) to 59 (8.7 s), settled 11.6 s.
- Layout quality at rest, 2,000 notes: link crossings 620k to 617k, dots overlapping 171-198 to 264, line through
  a foreign dot 29.4k to 31.6k, mean link 517 to 482. 500 notes: crossings 31.5k to 32.3k, overlaps 2 to 0,
  5.4 to 5.0 s. 36 notes: 68 crossings, 3.2 s.

## Left

- 4x CPU (and a 2x display, where the whole map's line length costs 284 ms to stroke): a light frame is still
  100 to 200 ms with the commit and the minimap (graphMinimapPaint 30 to 70 ms at 4x, every 8th tick, graph.js
  `graphMinimapQueuePaint`). Next: paint the minimap only at rest on a big map, or every 24th tick.
- The frame at rest is one whole draw (60 to 130 ms at 1x, 500 ms at 2x: curves, sprites, names): one long task
  at the end. Next: split the labels pass or draw nodes first and names a frame later (graph-canvas.js `gcDraw`).
- The first full frames (reveal after the first fit, `gcBalanceFit` passes) are 60 to 100 ms each at 1x.
- Clearance is still 30 to 40 of a 55 to 75 ms tick. Next: run it every second tick above alpha 0.1 with double
  strength, or skip links whose ends have not moved.
- A 2,000-note layout is slightly looser than at 225 ticks (overlaps 264 against 185). If the owner minds,
  raise `SETTLE_FULL_TICKS_UP_TO` (graph-worker.js:131) to 900 (about 135 ticks, 13 s).
- Not verified: a real GPU (raster costs above are software), an idle machine, a 2-core machine, dark theme.
