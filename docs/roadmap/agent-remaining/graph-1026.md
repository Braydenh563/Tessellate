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
- Node panel foot worded at every width, Pin added (graph.js `renderGraphPopupActions`,
  `graphPopupActionList`; 07-whiteboard-misc.css `.graph-popup-actions`).

## Left (owner's words, file:line)

- "access to the tools and controls and different mechanisms in it aren't really easy to understand": the gear is an unlabelled icon (`#graph-options-toggle`, index.html ~3896, aria "Display options"); give it a visible word and a '?' (`data-help-for`) per section of `#graph-options` (View, Physics, Show, Display, Filter, Time, Groups, Minimap; only Show has one now). The panel scrolls 890 in 512 at 1440 with every fold closed (gp.js).
- "my graph is messy": crossings did not fall (64 to 64, 295 to 312 at 150); a hub's rays still cross every cluster. Next lever: hub-centred category placement (graph-worker.js `groupAnchorsOrganic`, the hub's category at the middle) or edge bundling of rays per category.
- Label density: names drawn at the fit stay low on a phone (2 of 36, 0 of 150) and at 150 notes (9). `gcDraw` landmark pass (graph-canvas.js ~2579) and the label cut length.
- Settle: 4.1 to 5.1 s to rest at 36 and 150 notes; first paint is framed (0 off-screen), the rest is motion.
- Toast: clear of the legend's words but inside the legend row's box at 1440, and over the zoom strip at 390 (`#toast-box` lift for the Graph tab).
- A click on the lowest note of the 150-note map opened no panel in gp.js (`low: null`); not reproduced by hand.
