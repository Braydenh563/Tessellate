# Graph rows 42, 48, 57, 58 of audit 1029 (agent branch, not pushed)

Measured on the Playwright sweeps in the session scratch (`/tmp/claude-0/graphb/`: `search.js`, `c48c.js`, `f57.js`, `f57b.js`, `p58c.js`), server on :8841, 36 seeded notes plus extra categories.

## Done

- Row 42 (G11): `#graph-search-count` (role status, polite) says "12 matches", "1 match", "No matches"; Enter and Shift+Enter walk the matches (wrapping) and pan to each; Esc clears the search and the similar-notes highlight. Edits from the g11 draft applied (every anchor still existed), test moved to `tests/test_graph_search_keys_1029.py`, g11/ deleted, count rule in graph-lazy.css, Guide graph topic sentence, `tests/test_manual_parity.py` check. Live: 24 matches, Enter 1 moved the view from x 305 to 539, Enter 2 to 137, Shift+Enter back to 539, Esc emptied box and count; "zzzqqq" gave "No matches".
- Row 48 (G12, G21, X10): the dot rim on a light ground is 50% deeper (`gcRimShare`, was 25%): worst of the 22 automatic colours 1.87 to 3.46 sampled off the painted sprite (ground 247,246,244). `::placeholder` opacity 0.85 removed: graph search placeholder 3.68 to 4.86 on its field. `.toast-action` measured 7.72:1 on its opaque toast (white), so there is no token to darken; the axe 1.2 came from a toast behind another card (stacking, X10's first half).
- Row 57 (G9, G22, G23, G24): legend wraps to two rows (`5.2em` cap, then scrolls): 17 entries scrollWidth 2088 in 1308 and 5 out of sight, now 1308 in 1308, none hidden; the rule moved from boot CSS to graph-lazy.css. Filter fold: no lone "No kind 64" chip when no link has a kind (`gcLinkKindRows`; a turned-off untyped kind keeps its chip). Help panel 1,296 characters scrolling 568 in 510, now 780 characters in a lead line and seven items, 465 in 465. Minimap top corners clear Trace (`initGraphRailToken` grows `--graph-chrome-top` on the card; no new custom property, the count only falls): overlap with Trace 8,861 px2 to 0 at 1440x900; 0 again when Trace closes; 390 wide has no minimap overlap.
- Row 58 (G25): reproduced at 1280x640 with a long note (popup 517 of 533 tall, node dragged 280px, popup moved 0). `graphPopupCap` holds an undragged popup to 60% of the room (min 280): popup now 320 tall and tracks the node 78px past the first step down to the map's edge. At 1440x900 the follow already worked in both axes (dy stayed -20 across a 150px drag).

Ratchets: boot CSS gzip 179,097 before row 57, 179,069 after (cap 179,100); custom properties unchanged (428 cap). Boot JS unchanged at 572,727.

## Remaining

- G30 (row 57): done 2026-10-29. A reload of a shown map marks `#graph-stats` busy from 400 ms and a thin accent line runs under the count (graph-canvas.js `renderGraphCanvas`, graph-lazy.css; tests/test_graph_reload_line_1029.py). Measured with `/graph` held 1.5 s: none at 200 ms, line at 700 ms, gone after.
- Row 48: a dot with radius under 3 (`gcPaintCore`'s flat branch) has no rim, so the very smallest dots on a light ground keep the plain colour; not measured separately.
- Row 58: a popup that cannot be beside its node because the node is at the map's far edge stays clamped (by design); the local-graph pane popup (size not full) still does not follow.
- Row 57: the topic card (right column) and the minimap's top-right corner are not on the rail; only the Trace strips are.
- Not verified: phone widths for the Help panel and the count span; the dark theme for the new rim share (it keeps the old 25%); real inference not involved.

## Row 35 (G3), 2,000-note cold layout

Sweeps in the session scratch `r35/` (`measure.js` cold open with longtask and event observers, `timeline.js` worker messages, `wbench.js` per-force times in the real worker in Chromium, `wprof.js` node profile); fixture `scratchpad/graph-fixture.js 2000 4000` (3,796 links) and `500 1000` (951). A/B against the base on a copy of the same data, machine load 4 to 7 from other agents.

- done: 3f118d5 clearance corridor; 3fecbc2 draw once a tick, 8 ms yield, untangleGroups budget; 6e80fe0 no line grid while a costly map moves. Rest 27.9-29.7 s to 16.0-21.6 s; click p50 57-80 to 42-48 ms; 500 notes 8.5-10.4 to 6.2-9.2 s.
- left: each tick's full draw at 2,000 notes is 140-230 ms under load (gcDraw self, drawImage, gcDrawComposed's layers, minimap, then raster as "(program)"); click max 240-310 ms against the 100 ms target. Next: paint dots only (no curves or names) while `s.layoutRunning` on a costly map, or post at a fixed 100 ms on big maps (graph-worker.js `post`, graph-canvas.js tick handler near `gcTickSnaps`).
- left: the live phase is still about 110-180 ticks at 60-90 ms each; charge 12 ms and collide 8 ms a tick remain, clear about 45 ms. A typed-array grid in `clearanceForce` was the next cut: done 2026-10-29, 41-43 to 22-28 ms a call in node outside a vm sandbox (a `vm` context makes every global read slow and misprices the loop: 195 ms there). Next: the corridor still reads about 35 cells a chord, 512k a call.
- not verified: a real GPU, an idle machine, a 2-core machine (performance mode keeps the old duty cycle there; not measured).
