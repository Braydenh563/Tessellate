# wbopen-1031: OPEN batches B45 (806 to 819) and B48 (848 to 861)

Branch agent/wbopen-1031. Done: 5f75052 (the `.drawio` export, repaired sweeps); next: OPEN.md and HISTORY.md accounting commit.

Outcome per row is in OPEN.md's ledger ("wbopen-1031 (...)"); built rows' text is in HISTORY.md "Moved from the plans, 2026-10-31 (wbopen-1031 ...)".

Left, one line each:

- 807 merged cells in board tables: no span model yet (`data.cells` is a grid of strings; `wbSvgTable` in whiteboard-format.js:1491 and the table renderer would need `data.merges`). L.
- 813 Row 4 at 390, press to editable: by cause in wbpress-1031 (b3af755). The cost was browser style recalculation (forced flushes, root-anchored `:has()` rules, an edge reorder cascade, a closed select menu rebuilt, a full edge redraw after the server answer), not layout. Interleaved before and after, median of 10: 390 px 20 topics 83 to 42 ms (0.51x, 0.54x at 4x CPU throttle), 200 topics 173 to 110 ms (0.64x); 1440 20 topics 0.96x, 200 topics 0.81x. Left: 200 topics at 390 is still above 50 ms (`renderWbObjects`, `wbRenderMapEdges` geometry, `wbBeginTextEdit` flush).
- 815 watches in JavaScript are evaluated natively (`evaluate`, api/run_sandbox.py:272): a design limit.
- 816 Python runtime reloads per document: needs the Pyodide extra installed to time the cold Debug.
- 817 the console on .html, .css, .svg, .sql is a fresh worker (`runHtml`, run_sandbox.py:603).
- 818 write tools that are not acts need seven `_ACTS` rows with inverses (ai/act_registry.py:96).
- 819 Row 2's New as a split button (DESIGN.md recipe): decide the one-press default (recommend a blank board), then index.html bytes (boot file, at the cap) and tour.js:293 and :338, reveal-targets.js:395.
- 855 document comments with the board's thread shape: take the row's recommendation (documents.js `renderDocComments`, whiteboard.js `wbCommentRow`).
- 856 voice: 112 JS files still hold their own failure strings (decision 55, surface by surface).
- 858 hover frame at 2,000 notes 22 to 24 ms: measure on an idle machine.
- 860 owner hardware and the desktop webview: not verifiable here.
- 861 calendar events table: BACKLOG.md says tried and deferred as L.

Found, not fixed: tests/test_scratchpad_size.py fails on the base (768 tracked files under scratchpad/, cap 766), before this branch's changes.
