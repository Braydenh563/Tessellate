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
- W21 verified, no code change: S51 (resume tile, dashboard.js:690) and S52 (#graph-search) already built. Counts read: `/insights/stats` total and categories exclude bin, drafts and boards, from SQL counts (routes_insights.py:38); due count pages `/reminders` to the end (dashboard.js:470); import toast, preview and Undo use `imported`/`ids`, which the server does not cap (routes_settings_transfer.py:656). Timeline count says "N+" while `timelineNextCursor` is set (timeline.js:756): honest, not a total. A true total needs a count on `/timeline` (routes_timeline.py:377, outside this batch's files). Tag cloud is the top 60 tags by design (routes_insights.py:670); it shows no total.

Hub follow-up (2026-11-11, tried and not kept):
- At rest the chain is whole frame (fc 2) then composed, then a balance pass 2 and composed again. Making pass 2 ride the layer paint (`again()` asking `gcRequestDraw(s, true)` once shown) removed one whole frame (30 ms) but left the composed frames at 46 and 59 ms: tasks over 50 ms unchanged, total 188 to 167 ms. Reverted: a balance inside a padded layer paint is a risk for 11% of the work.
- A composed frame measured by part (2,000 notes, 1x): layer paint 15 to 22 ms, the `over` pass 0.8 to 1.2 ms, the whole 37 to 48 ms. The other 21 to 24 ms is the `drawImage` of the layer, where the sandbox's software raster flushes the layer's pending paint. A GPU raster would not show it, so no code cut is left in the composed path; a real-GPU measure is the next step, not more code.

## W13 and W27 (this branch)

- W13 traced at 4x: handlers over 50 ms are `(program)` style and layout; the only big JS forced layout in the Settings open is `nameMarkRasterise` (avatars.js:1305, 86 ms, companion, out of scope). Settings tools, Library, Dashboard: script self time 18 ms or less per function. Nothing left in `settings*.js`, `dashboard.js`, `library*.js`.
- W27: boot gzip 250,954 to 250,434. Moved: applyHarmony, applyContrast, resetThemeOnly, copyLogs, clearManualOverrides, nearLogBottom, clearEmbeddingBackendLatch, looksLikeEmbeddingModel (settings-controls.js); inlineActionIs, translateNoteInDesk (entry-menu.js); searchHighlightTerms, notesSpanSpaces (entry-card.js).
- Tried and kept at boot (a test names them or a lazy-to-lazy call breaks): resetAppearance, saveCurrentLook, clearLogs, evidenceSwitchReset, entryOverflowMenu, dailyNotePair, publishDraft, focusFirstIn, zoomWheelDelta, taskLogButton, paletteCaughtNow, wirePrefsDirtyMarks (calls nameMark), askAtlasAboutNote (noteNamePlain test). Each needs its test's source path updated: next batch if the cap needs it.

## W25 (this branch)

- Palette keystroke, 2,000-note fixture, 51 keystrokes over 7 queries (probe in scratch only): 1x JS p50 6, p90 8, max 17 ms, frame p90 25; 4x JS p50 27, p90 41, max 49 ms, frame (input to next paint) p50 69, p90 98, max 133 ms. Under the 150 ms target, so no code change (the memo, the ranking window and the setting rows from W25 D6 and D10 already did it).
- Tab open at 4x: see W13 (native style and layout). Settings open stays a design pass (s7-1110.md D8: one 267 KB template).
- Found, not fixed: a page error on a cold load, `docCmSyncLanguage is not defined` (documents.js:1090 calls it at load, defined in documents-view.js:715); documents files are out of this spoke's scope. **Gone at head (1111 next-queue):** a cold load into Documents, opening a doc and five file-type switches through the real menu gave 0 page errors and 0 console errors (documents-view.js loads before documents.js, `tests/test_documents_view_order_1111.py`).

## W14, W15, W31 check (graph-1111)
- W14: every row is fixed or not reproduced in OPEN.md (Q10 is built: "Still when idle" in Appearance, tests/test_companion_rest_w14.py), so no overlap with the settings spoke and nothing left to build; B56, B58 stay "not reproduced".
- W15: B64 fall measured on the simulation (see its OPEN row); B63 needs the owner's log, B65 left rows are pose-keyed frames (W31) or a real desktop; B66 scan needs one more Windows log. Nothing else runnable here.
- W31: not started. E1 to E6 are frame and design work (Opus design for the masculine side, new desk frames) and the row says not beside W15 or W24 (overlay tests); left for a session that owns the overlay.
