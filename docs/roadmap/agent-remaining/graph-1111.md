# Graph (W26) remaining, spoke claude/pr216-graph, 2026-11-11

Fixtures: scratchpad/graph-fixture.js (500 notes 951 links; 2,000 notes 3,796 links). Measured with a longtask observer from the `switchTab('graph')` call to the first `settledSig`, Chromium headless, 1440x900.

| run | settle | tasks over 50 ms | worst |
| --- | --- | --- | --- |
| 2,000, 1x, before | 3.7 s | 10 | 107 ms |
| 2,000, 1x, after | 3.3 s | 5 | 96 ms |
| 2,000, 4x, before | 4.1 s | 23 | 318 ms |
| 2,000, 4x, after | 4.1 s | 15 | 315 ms |
| 500, 1x, after | 1.7 s | 5 | 118 ms |

Done: settle is under 5 s at 1x and 4x on both fixtures (it already was). Fixes: minimap one-parse build, balance passes wait for rest once shown, link grid chords by length (tests/test_graph_w26_1111.py).

Not done (the 50 ms bound, 1x):
- The Graph tab switch makes 3 to 5 tasks of 50 to 130 ms in the first 800 ms, with no worker running (`Worker` stubbed: 3 tasks). Native time, not JS (CPU profile: `(program)` 76 to 112 ms, JS under 10): style recalc over the tab's 1,700 elements (1,214 are the minimap SVG) and a forced layout in `renderGraphCanvas` / `gcResize` (`getBoundingClientRect`, graph-canvas.js:962). Dashboard, Library and Timeline switches make 0. Next: the minimap as one canvas (graph.js:4057 `graphMinimapPaint`, ids pinned by tests/test_perf_hot_paths.py:86), and the forced layout read in `gcResize`.
- The first fit frame is 53 to 97 ms (cold: sprites, names for 2,000 notes, `gcPlaceLabels`). It must be whole (the map is hidden until its balance, `gcRevealAfterBalance`).
- The frame at rest is a chain: whole frame 44 to 72 ms, then the scene layer (26 to 43 ms) composed 50 to 77 ms, the second balance 22 to 34 ms, the layer again 46 to 51 ms. Warm, one whole frame is 28 ms (edges 12.6, nebulae 5.7, sprites about 6). Next: paint the scene layer straight from the stale light frame (skip the whole frame, `gcDrawComposed` refuses while `sceneStale`), cache `gcDrawNebulae` in the rest layer, integer-aligned sprite blits (bench 8.3 to 3.8 ms for 1,478 sprites).
- 4x: tasks of 100 to 315 ms are the same frames at four times the cost; only a cheaper frame cuts them.
- Hover p50 and wheel at rest (GRAPH_PLAN line 614) not touched.
- W21 not started: S51 (resume tile, dashboard.js:690) and S52 (#graph-search) are already built; "every count is the true total" unverified.
