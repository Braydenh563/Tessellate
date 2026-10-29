# Deep audit 2026-10-29: the graph

Scope: layout, worker, canvas drawing, labels, colours and legend, filters, clusters, hubs, neighbours, drag, zoom, pan, search and focus, open a note, settings and reset, toasts, phone gestures, readability at 40, 500 and 2,000 notes. Auditor had no stake in the build. Providers run against a fake transport; real inference is unverified (the graph does not call a model, except topic summary, which was not exercised).

Method: server on port 8803 with its own data dir, Playwright, CDP `Emulation.setCPUThrottlingRate` 4x, `longtask` observer, rAF frame sampling, `pngpixel.py` for contrast. Seeded 36, 500 and 2,000 notes (random links, so the 2,000 map is a dense hairball by construction). "run" = reproduced in the app, "code" = read from source only. "Open, re-verified" marks an item an earlier plan or audit already lists, which I reproduced rather than trusted.

## 1. Coverage

| Area (CODEMAP) | Items | Checked | Driven | Not reached |
| --- | --- | --- | --- | --- |
| `graph-canvas.js` functions | 156 | 156 read | about 70 through interaction (draw, hit test, drag, linkdrop, lasso, node menu, minimap, restore, save positions, label policy, camera fit) | gradient/legend helpers, export internals read only |
| `graph-worker.js` functions | 102 | 102 read | all paths reached except the radial/arc/tree internals (timed only) | untangle line-grid internals (crash found by reading) |
| `graph.js` functions | 134 | 134 read | about 60 (popup, peek, filters, search, keyboard, focus, selection dock, options, trace) | legacy SVG renderer (`renderGraphSvg`, no UI) read only |
| `routes_graph.py` routes | 45 | 45 read | 14 hit: GET /graph, ?slim, /match, /local, /structure, /topics/of, /path; PUT /pin, /pins, /topics/name; POST /unpin-all (+ auth, validation) | `/topics/summary` (model), time-slider endpoints |
| DOM ids in the graph pane | about 120 | all listed | about 85 clicked or read | time slider and play, saved-view delete, minimap corner and size options |
| Sizes | 40 (36), 500, 2,000 | all three, 1x and 4x | cold open, idle, hover sweep, wheel zoom, drag, reshuffle, option change, search typing, tab switch back | |
| Themes, viewports | light, dark; 1440x900 and 390x844 | contrast both themes; phone gestures light | | dark phone, keyboard-only in dark |

## 2. Findings

Severity high/med/low. Kind bug/missing/ux/ui/a11y/copy/perf/complexity/security/ai.

| id | sev | kind | finding | evidence | verified | fix (the class) | effort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | high | bug | With more than 4,000 links the layout worker throws and never reports end. Positions are never saved, the map stays in a half-settled state, and it recurs on every open. | `graph-worker.js:1617` `UNTANGLE_MAX_EDGES = 4000`; `untangleSetup` returns at 1628 leaving `untangle.ea = null`; `settleUntangled` (~2634-2651) cap branch sets `done`, `passes = UNTANGLE_PASSES`, then `untangleCleanup()` reaches `lineGridBuild` 1983 `untangle.ea.length`: "Cannot read properties of null (reading 'length')". 2,000 notes, 4,230 edges: about 4 of 6 cold opens; `settledSig` never set. | run | A skipped stage must also skip its dependents (guard `untangleCleanup` on `untangle.ea`), plus a worker `onerror` that shows "layout failed, showing last good positions" instead of silence | S |
| G2 | high | bug | The node popup throws away unsaved edits on Escape, the X, a click on the map, or clicking another node. No confirm, no draft. | `graph.js:4885` `closeGraphPopup` has no dirty check; typed text absent on the server after Esc; the Save row showed dirty first. | run | One "dirty" gate for every popup/panel close path: save-on-close or keep a draft and say so (same class as composer draft loss) | S |
| G3 | high | perf | 2,000 notes: cold layout takes about 28 s to the worker's end message at both 1x and 4x. Main-thread long tasks while it settles: 1x 106 tasks, sum 10.3 s, max 684 ms; 4x 120 tasks, sum 21.2 s, max 641 ms. The page is unusable for that time. Ranked S2 in audit-1028-ranked. | longtask observer, worker end timestamp | run | Open, re-verified. Cap main-thread work per frame (simulate in the worker, post positions at a fixed rate and draw only when a tick arrives); reduce per-tick payload | L |
| G4 | high | perf | Every Shape, Colour or Size change at 2,000 notes re-runs the whole layout: about 12 s of continuous long tasks at 4x. Radial max task 1,274 ms; arc 2,186 ms; tree 1,705 ms at 4x. | longtask log per option | run | Colour and size need a redraw only; shapes need a warm re-layout from current positions, not a restart | M |
| G5 | high | perf | 500 notes at 4x CPU (a mid phone or old laptop): hover sweep p50 83 ms (16 of 31 frames over 50 ms, tasks 51-271 ms); wheel zoom p50 133 ms; node drag p50 83 ms; reshuffle p50 83 ms; cold settle 7.3 s with 46 long tasks summing 5.1 s. At 1x it is fine (hover p50 16.7, wheel 33). | frame sampler, longtask | run | Hit test with a spatial grid; skip label re-placement while the pointer moves; cache the edge layer as a bitmap during pan and zoom | M |
| G6 | med | bug | "The map opens where it was left" is not true. `graphPositions` is saved, the signature matches and `gcCachedPositions` is non-null, yet after reload nodes drift: RMS 52-87 world px, max about 170-220; 35 of 36 move more than 5 px. Alpha re-heats to 0.3 about 300 ms after load. No pins involved. | `graph-canvas.js:5061-5076` save/sig, restore ~5429; measured before/after reload | run | A restored layout must start at alpha 0 (or a tiny nudge) and only re-heat on a real change (data, filter, physics) | S |
| G7 | med | ux | At 500 notes there are zero labels at fit, and the 81-link hub is unnamed, which contradicts the 2026-09-26 decision "hubs are named". k=1.07 gives 0 labels, k=1.63 gives 12, k=2.46 gives 3, k=3.74 gives 6 labels for about 45 visible dots. Label count does not rise as you zoom in. Legibility judged with default settings first, as the owner sees it. Same family as INBOX 1306. | `graph-canvas.js` label policy ~2790-2870 (`landmarkIds`, `GC_LABEL_LANDMARK_HUBS`); `labelBoxes` count per zoom | run | Open, re-verified. Hub labels must be guaranteed (reserve the box first, then fill remaining space); labels should grow in number with zoom, with the no-overlap rule kept | M |
| G8 | med | perf | At 36 notes, 4x CPU: wheel zoom p50 33 ms with 14 of 59 frames over 50 ms; hover shows 12 long tasks of 50-89 ms. JS draw is only about 1.4 ms p50 at 1x; the profile shows 796 ms of native "program" in a 4.2 s window, so the cost is raster/composite. Possibly the backdrop blur on panels over the canvas (not isolated). | Profiler, frame sampler | run (cause unverified) | Test the glass-off list for graph-overlaid panels; promote the canvas to its own layer | S |
| G9 | med | ui | Legend clipped at 1440 wide with 10 categories: scrollWidth 1455 vs clientWidth 1308, overflow hidden, so the size hint "Bigger dot, more links" shows as "Bi". | `#graph-legend` rect read | run | Let the legend wrap or scroll, and drop the size hint first when short of room | S |
| G10 | med | perf | Search highlight at 2,000 notes: typing 13 characters costs 32-34 long tasks, sum 5.4 s, max 420 ms at 4x. The 150 ms debounce does not help because each pass is long. | `wiring.js:1163` calls `applyGraphHighlight`; longtask log | run | Match on the worker or a precomputed lowercase index; redraw once per frame | S |
| G11 | med | missing | Search has no match count, matches are unlabelled, Enter does not jump to a match, Esc does not clear the field. | `#graph-search` driven | run | Show "N matches", label matches, Enter cycles and pans, Esc clears | M |
| G12 | med | a11y | Light-theme dot contrast against the map ground is below 3:1 (WCAG 1.4.11): Work 2.89, Travel 2.94, Reading 2.11, Health 2.29, Uncategorised 1.62. Cooking 3.84 and Ideas 3.11 pass. Dark passes (min 3.45). | `p/contrast.py` on screenshots | run | Known palette issue, re-verified for nodes: add a thin darker ring on light, or darken the map ground, rather than retuning each hue | S |
| G13 | med | a11y | Touch target: the hit slop is `6 / k` screen px for every pointer, touch included (`gcNodeAtWorld` `graph-canvas.js:3448`). On the phone (390x844, k about 0.69) median dot radius is 5.4 px (min 3.4), so a target is about 19-23 px: under 24 px (2.5.8) and far under 44. Tap, long-press menu (44 px items), pan and pinch do work. | measured radii and slop | run | Larger slop for `pointerType==="touch"`, nearest-node-within-radius rather than first hit | S |
| G14 | med | ux | Selecting the first note refits the camera (a 22 px shift) because the dock opens (`gcRefitForPanels`), so a second right-click aimed at a node can miss. | camera x before/after | run | Do not refit on dock open if the node stays visible; or animate and re-hit-test | S |
| G15 | med | ux | A plain drag that ends over another node opens "How are these connected?" (`linkByDrop`). Cancelable, but easy to trigger at dense maps and on touch. | `graph-canvas.js` ~3828 | run | Make link-drop need a modifier or a drag from a handle; or confirm with a visible target ring first | S |
| G16 | med | bug | Data: the diagnostics report counts 4,234 links on a notebook of 37 notes while the graph shows 64 links. The other 1,500+ notes were deleted through the API, so link rows survive their notes (the same family as `/entries/count` still saying 2000 after 1,500 deletes while `/graph` gave 500). | diag report "Notebook: 37 notes ... 4,234 links"; `/entries/count` | run | Cross-ref audit-1029-notes N13. Delete must cascade `entry_links`, and the count must not be cached across deletes | S |
| G17 | low | ui | Topic chip in the popup is styled as a tag ("#later") but is not one of the note's tags (#work #idea). | `graph.js:4484` `renderGraphPopupTopic` `chip(... "tag")` | run | Use a distinct topic chip style and label ("Topic: later") | S |
| G18 | low | copy | Hover card says "Click to open, double-click to pin" but a click opens the popup, not the note (Open is the button). | hover card text vs behaviour | run | Say "Click for details, double-click to pin" | S |
| G19 | low | a11y | Esc from the popup leaves focus on BODY; it should return to the node or the map box. | `activeElement` after Esc | run | Restore focus to the opener on every popup close | S |
| G20 | low | a11y | Keyboard: 7 legend Tab stops before the map box; no keyboard multi-select or lasso ("Add to selection" is in the right-click menu only); popup topic chip is 70x24 (under 44 on phone). | Tab order walk | run | Roving tabindex for the legend; Space toggles selection on the focused node | M |
| G21 | low | a11y | Search placeholder contrast 3.68 in light; options toggle checkboxes are 32x18 (target size). | `contrast.py`, rects | run | Darken placeholder token; enlarge hit area to 44 | S |
| G22 | low | ux | The filter fold shows a "No kind 64" chip at default (a count of a thing that is not filtered). | filter fold | run | Hide zero-state chips | S |
| G23 | low | ui | Help panel is a wall of text and is clipped at the bottom; link peek buttons "Edit reason" and "Two-way" wrap to two lines. | rects | run | Help behind `data-help-for` per control; `white-space: nowrap` plus a wider peek | S |
| G24 | low | ui | With Trace open the minimap sits under the Trace bar; the Reset toast can cover zoom +/-; the hover card is partly under the legend. 1306 residue. | screenshots | run | Anchor map furniture to a shared layout rail, not independent corners | M |
| G25 | low | ux | Popup follows a dragged node in x only (INBOX 1413 partial). | popup rect while dragging | run | Open, re-verified. Follow in both axes with edge clamping | S |
| G26 | low | complexity | Dead and heavy code: the legacy SVG renderer (`renderGraphSvg`, 1,272 lines, plus helpers) is reachable only through `localStorage["graph-renderer"]="svg"` with no UI; `gcDraw` is 758 lines, `gcWireInteraction` 467, `renderGraphCanvas` 362, worker `run` 339. The complexity ratchet (`tests/complexity_seed.json`) covers Python only. | line counts | code | Delete the SVG path (replace, do not layer); add frontend function sizes to the ratchet | M |
| G27 | low | security | `/graph/pin` accepts x=1e308 and 1e30 with no bounds; the effect on camera fit was not tested. `/graph/local/99999` returns 200 with empty data instead of 404. | curl | run (effect unverified) | Clamp pins to a sane range server-side; 404 for unknown ids | S |
| G28 | low | perf | `/graph` payload is 1.45 MB at 2,000 notes (slim 830 KB), 0.34 s, gzip on. Diagnostics shows 16-19k page elements on a 37-note graph tab and many 200-540 ms rAF stalls in `gcRequestDraw` (3-61 calls/s, up to 155 ms each) during my heavy probes. | diag report below | run | Page elements come mostly from other tabs kept in DOM; not a graph fix. Send the slim shape by default | S |
| G29 | low | perf | Tab switch back to the graph, numbers only (another agent is fixing INBOX 1433): long task 454 ms (36 notes, 4x), 820 ms (500, 4x), 143 ms (2,000, 4x). The switch itself is 0-4 ms synchronous. | longtask observer | run | Not dug into, per the brief | n/a |
| G30 | low | ux | When the map reloads slowly (3.5 s delayed `/graph`), the stale map and stats stay with no loading hint. | slow-route test | run | A thin progress line on the stats chip while fetching | S |

## 3. Already good (verified)

- Reset to defaults works, offers Undo, and its toast is opaque.
- Removing a link has a confirm dialog and Ctrl+Z restores it (edges 64, 63, 64). The note's wikilink text stays, so the row goes but the text does not.
- Pin, unpin and the selection dock (Pin, Unpin, Tag, Link together, Unlink, Mind map, clear) work.
- Focus mode, hide with "N hidden on this map. Show", legend toggles (aria-pressed), groups, saved-view buttons, PNG export (graph.png downloads), fullscreen, Mind maps (goes to #/library/boards).
- Open from the graph goes to #/notes/N with a flash; New note from the graph works and an empty save says "Type something first."; double-click on empty space opens New note.
- Minimap click pans (217 px).
- Keyboard map box has a visible 2 px ring; arrows, N, +/-/0 and Enter work.
- Popup header drag works.
- Phone gestures work (tap, long-press, pan, pinch), controls are at least 44 px, no horizontal scroll.
- Error states: a 500 on refresh shows "Could not load your map" with a retry and says nothing is lost; offline shows "Can't reach Tessellate. Retrying..." and recovers; hiding every category shows "Every note is hidden ... Show every note" and the button restores all 37.
- Auth is required on every graph route (401 without a token); topic names render through `textContent` (an `<img>` name is stored but safe); bad ids give 422; over-long `q` gives 422.
- Idle is 0 long tasks and 16.7 ms frames at every size.

## 4. Not verified

- Time slider and play; link-kind and property chips; saved-view save, restore and delete; physics sliders per fold.
- Minimap corner and size options; trace route highlighting details; topic rename effects and summary (model).
- Private notes and the vault-locked graph (see notes audit N21); LAN and CSRF.
- The 1e30 pin effect on fit; the real-model path.
- Dark theme on the phone and a keyboard-only dark pass.
- Zoom limits (k 0.06 and 5) were observed only in passing.
- G8's cause (blur vs raster) is a guess.
- The 2,000-note map has random links, so its legibility says little about a real notebook; only the hub labels were judged.

## 5. Diagnostics (Copy diagnostics report, `diagCollect()`, end of the run, 37 notes)

```
== Tessellate diagnostics ==
Made 2026-10-29T02:21:43.987Z | version 0.6.2 build 40019e8a88
Device: HeadlessChrome 153, Chromium 153 on Linux | viewport 1440x900 @1x | 4 cores | 16 GB
Notebook: 37 notes, 0 boards, 0 documents, 4,234 links | 16,035 page elements | heap 25 MB
Settings: embedding_backend=fastembed, llm_provider=ollama, local_only_ai=true, web_search_enabled=false; frame sampler on

== Lag (15 kinds, worst first) ==
x190 raf 132-538ms [graph] graph-canvas.js gcRequestDraw 3-61 calls/s, 2.6-155.4ms each (132-538ms of every second)
x11 frame 201-477ms [graph] animation loops (top: graph-canvas.js gcRequestDraw) 14-290ms
x13 frame 207-306ms [graph] app.js Response.json.then 72-157ms
x1 request 3543ms [graph] /graph   (the 3.5 s delay I injected)
x4 input 352-736ms [graph] pointerout on div#tab-dashboard.tab-page.hidden
x6 frame 206-341ms [graph] app.js Response.json.then 106-282ms (forced layout 21-277ms) after pointerdown button#graph-options-toggle
x2 frame 305-336ms [graph] notes-list.js paintEntriesProgress 283-322ms

== Errors in the browser (0 total) == none
== Slow routes ==  GET /tidy x2 max 2084 ms; GET /graph x1 1497 ms; GET / 1059 ms
== Slow database statements ==  INSERT INTO entries 433 ms (x3); UPDATE entries SET suggested_tags 336 ms; INSERT INTO entry_links 334 ms (x3)
== Server exceptions == none   == Failed jobs == none

Animation loops by cost since load:
  graph-canvas.js gcRequestDraw    169 calls  448 ms total  2.65 avg  27.6 max
  graph.js graphMinimapQueuePaint  14 calls    8 ms
```

The lag rows come from my own stress probes (2,000-note seeding, throttling, injected delays), so read them as a tool check, not as a user report. The "4,234 links on 37 notes" line is real and is G16.
