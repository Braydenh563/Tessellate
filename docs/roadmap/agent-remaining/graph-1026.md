# graph-1026: INBOX 1400 and 1306 (force view composition, node panel, controls)

Sweeps (session scratchpad, not the repo's, which is at its file cap): `gm.js`
(composition and toast), `gp.js` (node panel and options panel), `seedg.py`
(the 36-note seed of `scratchpad/ui-sweeps/seed-graph40.py`, plus N follow-up
notes with long titles: `seedg.py PORT 114` gives 150 notes, 170 links drawn).

## Before and after (gm.js; 1440x900 unless said)

| Map | k at fit | fill w x h | names drawn | names overlapping | crossings | hub (links, crossings) | off-screen first paint / at rest | settle ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36 notes dark, before | 1.35 | 0.49 x 0.80 | 10 | 0 | 64 | 24, 39 | 0 / 0 | 4,269 |
| 36 notes dark, after | 1.46 | 0.54 x 0.80 | 20 | 0 | 64 | 24, 45 (rays, faint) | 0 / 0 | 4,454 |
| 36 notes 390x844, before | 0.83 | 0.93 x 0.61 | 3 | 0 | 64 | 24, 39 | 0 / 0 | 7,242 |
| 36 notes 390x844, after | 0.84 | 0.93 x 0.57 | 2 | 0 | 64 | 24, 45 | 0 / 0 | 4,101 |
| 150 notes dark, before | 0.73 | 0.59 x 0.82 | 7 | 0 | 295 | 43, 176 | 0 / 0 | 4,936 |
| 150 notes dark, after | 0.82 | 0.71 x 0.82 | 9 | 0 | 312 | 43, 187 | 0 / 0 | 5,104 |
| 150 notes 390x844, before | 0.51 | 0.96 x 0.63 | 0 | 0 | 293 | 43, 176 | 0 / 0 | 4,473 |
| 150 notes 390x844, after | 0.47 | 0.90 x 0.63 | 0 | 0 | 313 | 43, 186 | 0 / 0 | 4,622 |

Toast over the map: opaque both themes, text contrast 17.1 light, 14.0 dark; its
box meets `.graph-legend-row`'s box at 1440 (the row is wider than its words: the
words end at x 1054, the toast starts at 1075) and the zoom strip at 390.

Node panel (gp.js, 150 notes, 1440): foot was 9 bare icons in three groups (11 of
12 buttons icon-only); now Open (filled), Focus, Pin, Link worded and a ⋯ (3 of 8
icon-only: close, rename, the ⋯). On screen at the hub and at the right edge; focus
lands in the panel; Esc closes it.

## Done

- Composition: `landscapePull` (graph-worker.js `tuning`), hub rays (`gcHubSpokeMin`,
  `gcBowPoint`, `gcEdgeLook`), tests `tests/test_graph_compose_1400.py`.
- Options worded, View help (index.html `#graph-options-toggle`, `#graph-view-help`; Guide `graph`, `graph-controls`, `graph-display`).
- Node panel foot worded at every width, Pin added (graph.js `renderGraphPopupActions`,
  `graphPopupActionList`; 07-whiteboard-misc.css `.graph-popup-actions`).

## Left (owner's words, file:line)

- "access to the tools and controls and different mechanisms in it aren't really easy to understand": Options is worded and View has its ? (done, gd.js: dock 47px one row at 1440 and 1024, 111 at 390 as before; help on screen at all three). Left: a ? for Physics, Display, Filter, Time, Groups, Minimap (`#graph-options`, index.html ~4130 to 4400, the Show recipe at ~4182); the panel scrolls 890 in 512 at 1440 with every fold closed (gp.js).
- "my graph is messy": crossings did not fall (64 to 64, 295 to 312 at 150); a hub's rays still cross every cluster. Next lever: hub-centred category placement (graph-worker.js `groupAnchorsOrganic`, the hub's category at the middle) or edge bundling of rays per category.
- Label density: names drawn at the fit stay low on a phone (2 of 36, 0 of 150) and at 150 notes (9). `gcDraw` landmark pass (graph-canvas.js ~2579) and the label cut length.
- Settle: 4.1 to 5.1 s to rest at 36 and 150 notes; first paint is framed (0 off-screen), the rest is motion.
- Toast: clear of the legend's words but inside the legend row's box at 1440, and over the zoom strip at 390 (`#toast-box` lift for the Graph tab).
- A click on the lowest note of the 150-note map opened no panel in gp.js (`low: null`); not reproduced by hand.

done: 3444cbf (composition, node panel), next commit (Options worded, View help)
next: the ? per options fold, index.html ~4130; hub-centred placement, graph-worker.js groupAnchorsOrganic ~771

## Round 2 (crossings, settle, phone names)

Sweeps (session scratchpad): `gm2.js` (gm.js on this worktree), `runm.sh`, `cap.js` (captures the
worker's init message), `off.js` (replays it through graph-worker.js in node: crossings by kind, H hub,
B bridge, I inside a category; `UNT=0` skips the untangle), `draw.js` (a layout to PNG).

| Map | crossings before | after | hub crossings before | after | names | settle ms before | after |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 36 dark 1440 (gm2.js) | 64 | 61 | 45 | 38 | 20 to 11 | 4,454 | 2,976 |
| 36 dark 390 (gm2.js) | 64 | 55 | 45 | 38 | 2 to 10 | 4,115 | 2,387 |
| 36, off.js seed 0 1440 / 390 | 64 / 64 | 45 / 46 | 45 / 45 | 33 / 38 | | | |
| 36, off.js mean of 3 layouts | 90.7 | 48.3 | 57.3 | 32.7 | | | |
| 150, off.js seed 0 1440 / 390 | 331 / 339 | 294 / 302 | 114 / 119 | 110 / 123 | | | |
| 150, off.js mean of 3 layouts (before relax) | 437 | 278 | 190 | 102 | | | |
| 150 dark 1440 / 390 (gm2.js, before only) | 347 / 353 | not run | 118 / 125 | not run | 10 / 1 | 5,681 / 4,751 | not run |

0 overlapping names and 0 off-screen in every run. Built: `untangleLayout` (graph-worker.js; Organic
only, after a new layout rests, never after a drag; swaps and turns inside a category's reach, then a
glide and a 0.05 relax), the ring ordered by affinity in Organic, several cheap ticks a frame below
`WARM_ALPHA`, `GC_LABEL_NARROW_CUT` (graph-canvas.js `gcLabelText`). Tests
`tests/test_graph_untangle_1400.py`.

Measured and dropped: the hub held at the ring's centre (`off.js`: 36 notes 64 to 67, 150 notes
331 to 373; bridges then cross every ray); rim offsets in Organic (no gain); moves past 1.2 of a
category's reach (crossings 245 but the map 1.9 times taller).

## Left after round 2 (owner's words, file:line)

- "my graph is messy": the targets are not met. Crossings fell 30 to 47% offline on the 36-note seed
  but only 5 to 14% in the browser at seed 0 (61 and 55 of 64), and 11% at 150 notes after the relax
  (294 of 331). The relax at `UNTANGLE_RELAX` gives back a third of the gain at 150; most crossings
  left are bridges against the hub's rays (BH 26 of 45 at 36). Next: run the untangle on the warm-up
  (graph-worker.js `warmLayout`) so the 0.3 update the Graph tab sends does not re-settle it, and a
  move that checks a line's clearance instead of the relax.
- 150-note browser after: not measured (server switch between data dirs costs a restart; `off.js` only).
- "?" help on Physics, Display, Filter, Time, Groups, Minimap (`#graph-options`, index.html ~4130 to 4400): not started.
- Options panel scrolls 890 in 512 with every fold closed (gp.js): not started.
- Toast over `.graph-legend-row` at 1440 and the zoom strip at 390 (`#toast-box`): still OVERLAP in gm2.js.

done: 7812ece (untangle, ring by affinity, quick cooling, phone names)
next: untangle on the warm-up, graph-worker.js warmLayout ~264; options ? per fold, index.html ~4130

## Round 3 (Options help and fit, toast, untangle passes)

Sweeps (session scratchpad): `g3_opt.js` (panel fit), `g3_help.js` (every ? opens, fold unchanged),
`g3_toast.js` (toast against chrome rects), `g3_init2.js` (worker messages and crossings at `end`),
`g3_xcheck.js` (offline positions in the browser's counter), `g3_off5.js` (loop-driven offline, passes).

| Item | Before | After |
| --- | --- | --- |
| Options panel, folds closed, 1440x900 | 904 in 512 (scrolls) | 520 in 520 (fits); 7 sections each with a ? |
| Toast rect against legend row / zoom strip | 1440: overlaps legend; 390: overlaps both | 0 intersections at 1440, 1024, 820, 390 |
| 36 notes, crossings at rest, 1440 / 390 | 63 / 55 | 62 / 53 (2 passes); 50 / 48 with 3 passes |
| 186 notes, crossings at rest, 1440 / 390 | 722 / 677 | 683 / 617 |
| `end` after init, 36 notes | 6.3 s | 3.8 s (1440), 3.4 s (390) |

The "offline 45" was a capture artefact: `init36w.json` is a second init (alpha 0.3) from an earlier
layout. On a fresh init the offline harness gives 55 to 58 (`g3init36.json`); the browser counter agrees
with the offline one on the same positions (45 on offline's own positions, `g3_xcheck.js`).

Left:
- Three untangle passes reach 50 / 48 at 36 notes but `tests/test_graph_layout.py` (no link through a
  note) finds 7: `untangleFree` (graph-worker.js ~1690) checks notes, not lines. Next: a move that checks
  a line's clearance, then `UNTANGLE_PASSES = 3`. A pass is cut at `UNTANGLE_MS` 200, which truncates it at 186 notes.
- The second init the brief named (alpha 0.3 on the Graph tab) did not appear on a cold open (one init, alpha 1);
  it follows a render after the first layout settled. Not changed: `warmLayout` only steps to alpha 0.08.
- Show and Time are folds now: Show's Similarity strength slider is hidden while Show is closed.
- Phone sheet for Options (390): fit not measured (the sheet scrolls by design); ? popovers open in view.

done: 444dd43 (? and fit), e4d28b1 (toast), two untangle passes with a quick relax
next: moved to Round 4 (built there)


## Round 4 (line clearance, untangle budget, Show fold)

Sweeps (session scratchpad, not the repo): `g4_run.js` (browser: crossings and notes on lines at rest, `end` time),
`g4_off.js` (the real worker replayed in node), `g4_exp.py` (variants: no guard, no cleanup, soft margins).
Browser medians of 3 runs, one server (port 8806), same data per row.

| Item | Before | After |
| --- | --- | --- |
| 36 notes, crossings at rest, 1440 / 390 | 62 / 53 | 53 / 51 |
| 186 notes, crossings at rest, 1440 / 390 | 372 / 355 | 353 / 323 |
| 36 notes, notes on lines at rest, 1440 | 10 | 0 |
| `test_graph_layout.py` scenario, notes on lines after 3 passes | 7 | 0 (5 repeat runs) |
| `end` after init, 36 notes | 3.8 s | 4.1 s (+9% at 1440, +11% at 390) |
| `end` after init, 186 notes | 6.8 s | 7.2 s (+5% at 1440) |
| Pass time budget | 200 ms | 2 ms a note, 200 to 600 ms (36: 200, 186: 372) |
| Options panel, Show closed, Similarity on | Strength hidden | Match strength under Size, no new fold height at 1440x900 (scrolls by 26 px with Similarity on: 554 in 528) |

The 186-note dataset here differs from Round 3's, so the absolute numbers do not compare with that table.

Decisions:
- A guard on each move failed on the measure. A strict clearance rejected every move at 186 notes (140 of 186
  already sit near a line); a no-more-clashes count cost 11 crossings at 36 notes (61 against 50). So the passes
  run free and one cleanup at the end (`untangleCleanup`) projects the notes left on a line off it: iterative,
  collision radii as the collide force, a ring search for what is left, no tick after it (`untangle.holding`),
  or the forces pull the notes straight back.
- Three passes at 36 notes (53 / 57 crossings with two, 50 / 49 with three, offline); two past `UNTANGLE_BIG`
  (100) because the third costs a second of relax for a tenth of the crossings. A pass that gains under 3% ends the rest.
- Glide after a pass 12 frames, after the cleanup 8 (18 each regressed settle by 40%).
- Budget by map size: at 186 notes the larger budget alone is worth 3 to 4% fewer crossings; the cap is the settle time.
- Slider moved, Show not opened: opening it costs the panel the height of its toggles (over the 11rem cap).

Left:
- The cleanup is skipped over 100 notes (measured 220 to 320 ms and no gain): at 186 notes about 45 notes stay on lines. (Built in Round 5.)
- Settle is at +9% / +11% / +5%, at the edge of the 10% cap; a fourth pass or a longer glide would break it.
- Not verified: the phone sheet for Options at 390 (fit not measured), the canvas curve against the worker's 5-point
  polyline, and real inference (fake transport only).

done: untangle (3 passes, cleanup, scaled budget), Match strength under Size
next: moved to Round 5 (built there)


## Round 5 (line grid: the note-on-line cleanup above 100 notes)

Sweeps (session scratchpad): `g5_run.js` (browser, crossings and notes on lines at rest, `end` time), `g5ab.sh` (the head
worker and the new one alternated on one server, so load drift cancels), `g5_prof.js` (cleanup helpers timed in node),
`g5_nocl.sh` (cleanup on and off, 8 layouts offline). Data: `seedg.py` 186 notes (EXTRA 150) and 400 notes (EXTRA 364).
Medians of 3 runs, port 8809.

| Item | Before | After |
| --- | --- | --- |
| 186 notes, notes on lines at rest, 1440 / 390 | 45 / 52 | 19 / 23 |
| 186 notes, crossings at rest, 1440 / 390 | 353 / 323 | 385 / 339 |
| 186 notes, `end` after init, 1440 / 390 | 7.10 s / 5.68 s | 6.84 s / 5.82 s (round 4: 7.2 s at 1440) |
| 400 notes, notes on lines, 1440 / 390 | 165 / 179 | 118 / 134 |
| 400 notes, crossings, 1440 / 390 | 1482 / 1549 | 1549 / 1663 |
| 400 notes, `end` after init, 1440 / 390 | 9.71 s / 9.79 s | 10.10 s / 11.33 s |
| Cleanup time at 186 notes (node, one layout) | 221 to 320 ms, cut by its clock | 150 to 200 ms, not cut |

Built: `lineGridBuild` / `lineGridNear` / `lineGridTouches` / `lineGridRefile` (graph-worker.js, above `untangleOnLine`): the
lines (chord and 5-point curve) filed in cells of 1/0.75 of the largest reach, the cleanup's near list, its "is any note
stuck" scan and its step-off checks ask the 3 by 3 cells round a note, then the exact test on the cached points. A moved
note's lines are filed again. `untangleFree` turns most notes down on one comparison, `untangleNear` builds the curve only
when the chord is within the bow. Each half of the cleanup gets half of `untangleBudget()` (was 100 ms flat), the guard
`nodes.length <= UNTANGLE_BIG` is gone, and the pushes run 30 turns (was 60; 6 layouts offline: 15 on lines with 30, 18 with 60).
Test: `tests/test_graph_untangle_1400.py` (grid against the all-pairs test, pair for pair; 150 notes cleared inside the budget).
The test that read `nodes.length <= UNTANGLE_BIG` in the loop changed because its intent moved (the cleanup now runs at any size).

Decisions:
- Crossings rise with the clean-up: offline, 8 layouts at 186 notes, cleanup off 374 and 47 on lines, on 382 and 16. The
  rest of the browser's +8% is the passes finishing more moves in their budget now that `untangleFree` is cheaper (the
  head's 353 repeats exactly; the new code gives 361 or 385 by the clock). A note off a line is worth more than the
  crossings it adds: not changed.
- Settle at 186 notes is inside the +10% cap: alternated with the head worker at 1440, 6 pairs gave +3% (median) and 3 more
  -4% to +5%; at 390, +2%. Load drifts the absolute times by 30% (a busy machine gave 7.3 to 8.5 s for the same head), so only pairs compare.

Left:
- At 400 notes the map rests 4% (1440) to 16% (390) later and about 120 notes still stand on a line: the cleanup is cut by
  its half-budget (300 ms at 400). A node grid for `untangleLineOver` and `untangleFree`, and cached geometry in the push
  turns, are the next costs (`untangleNear` builds a curve per near pair per turn).
- The step-off runs for notes in index order; a note the budget reaches late stays on its line. Nearest-first would spend it better.
- Not verified: the phone sheet for Options at 390, the canvas curve against the worker's 5-point polyline, an interactive
  drag after the cleanup at 400 notes, and real inference (fake transport only).

done: line grid and the cleanup above 100 notes
next: the 400-note cost (above), if the owner wants the last 120 notes off lines
