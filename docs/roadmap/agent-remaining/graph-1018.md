# graph-1018 (GRAPH_PLAN open work; B70, B71 from bugs-1017.md)

## Step 0 audit (grep of code and HISTORY.md, 2026-10-18)

| Item | State | Evidence |
| --- | --- | --- |
| Phases 1 to 6 (canvas, space, colour rules, utility, backend, node panel) | built | GRAPH_PLAN.md:178-204 pointers into HISTORY.md "Moved from the plans, 2026-09-09/13"; `gcDraw` graph-canvas.js:2073 |
| Phase 5 positions on `/graph/views`, `?since=` cursor | closed on purpose (no caller) | GRAPH_PLAN.md:135-159 |
| 953 hover grows into halo, 952 node panel, 41, 78 minimap | built | HISTORY.md (Brief 100, Moved from the plans 2026-09-20), `graphMinimapFrame` graph-canvas.js:1938 |
| 958, 959, 960 (INBOX 798/799/802: feel, drag, glide, fit) | built | HISTORY.md:50501 Brief 100; graph100-1011.md; `RELEASE_ALPHA` graph-worker.js:78, `graphGlideMs` graph-canvas.js:1585 |
| 956 not idle at rest | built (measured, now closed) | `scratchpad/ui-sweeps/graphrest1018.js`: draws 31 to 60 a second for 6 s after open (the by-design settle), then 0 draws, 0 layouts, 0 script ms for 6 more seconds; long tasks 0 at rest |
| 957 `/graph` payload at 5,000 notes | measured, nothing worth a step | `scratchpad/kg1005_graph_bench.py` 5,000 notes: cold 1,133 ms, warm 113 ms, 3,299 KB (slim 1,920 KB, warm 86 ms); cProfile: `_payload_key` is 136 of 186 ms of a warm call (ORM column loads 75, sqlite fetch 29, repr 22), so a cheaper key (Core reads, which skips the space filter) is the only lever and the call is a cache hit already |
| 955 VC11 D3 hierarchy category overview (treemap) | open | GRAPH_PLAN.md:599; no `treemap` in frontend/js |
| 954, 929 real local model extraction | not verifiable here (no model) | GRAPH_PLAN.md:566 |
| 965 SVG graph flag | WORLD_CLASS_PLAN.md:984 (not GRAPH's rows to build) | leave |
| Tessellation view (owner 2026-10-11) | open, needs the owner to pick a variant | GRAPH_PLAN.md:656; no code |
| Neighbours barely follow a drag | built this run (below) | graph100-1011.md "Open"; `carryForce` graph-worker.js |
| Hover frame at 2,000 notes 22 to 24 ms | open | graph100-1011.md "Open" |
| B70 outlier | partly (tetherForce graph-worker.js:1206) | bugs-1017.md:81; owner question below |
| B71 overlap | built this run: topic plates (below); dots overlap 0 at rest | graphtopics1018.js |

## Done
- B71: topic plates seated (`gcSeatTopicPlates`, graph-canvas.js, tests/test_graph_plate_seats.py): plate-plate overlaps 1 to 0, plates on dots 10 to 0, dot overlaps 0, 200 notes 1440x900.

- Drag neighbours: `carryForce` + `FOLLOW_PULL` (graph-worker.js, tests/test_graph_neighbours_follow.py): in the app held 0.28 to 0.48 of the drag distance, settled 0.28 to 0.40 (`graphdrag1018.js`, baseline on a copy served from :8796); node 0.30 to 0.61.

## Next
- VC11 treemap category overview (new lazy module; the plan's measure: 1,000 notes under 100 ms, area within 1%), then hover frame at 2,000 notes.

## Owner questions
- B70: which note, tags and links does "Gym Routine Overview" have (it sat far from its cluster)? Not reproduced on synthetic data: worst-over-median nearest same-category distance 1.94 on the 200-note seed.
- Tessellation view: which of Voronoi, hexagon grid, hexagon clusters per category? (no mocks built; needs the pick first)
