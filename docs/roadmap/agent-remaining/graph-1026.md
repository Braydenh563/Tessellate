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
