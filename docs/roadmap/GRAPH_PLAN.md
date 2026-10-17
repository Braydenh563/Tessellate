# The graph: a full redesign, front and back

**Status: written by direct instruction; executed in ROADMAP.md order after
the plans already listed (row 13).** The instruction, verbatim:

> the actual graph itself visually, what it looks like, how it acts and how
> it is rendered needs a full upgrade and redesign in the front and backend,
> the features dont feel like they fit the application, they are glitchy to
> drag around and the ui ux could be improved as well as the utility. the way
> the graph is shown on the main view is awkward and all the examples of 2nd
> brain maps, obsidian graphs, and knowledge graphs completely blow my mind,
> then I look at what is in this application and I am dissapointed.

## 1. What exists (checked in the code, not assumed)

`frontend/js/graph.js` (3,800 lines) draws an **SVG** d3 force graph: one
`<g>` per node with a circle, a label and a halo; edges as `<line>`s;
`forceManyBody(-340)`, `forceLink`, `alphaDecay(0.05)`; four layouts
(force, tree, radial, arc); colour by category or by cluster; a legend row;
a minimap; search highlight; a trace (path between two notes); focus mode
(`/graph/local/{id}` at depth 2); saved views; entity, document and map
nodes as opt-ins; physics sliders (gravity, spread); a time slider; drag
that pins a node. `routes_graph.py` (850 lines) serves `/graph`,
`/graph/local`, `/graph/structure` (clusters, hubs, orphans: a real
community pass) and `/graph/path`. The dock is on the Phase 8 grammar.

## 2. Why it disappoints: measured and read

1. **SVG per node does not scale, and it is why dragging is glitchy.** Every
   tick rewrites `transform` on N groups and `x1..y2` on E lines through
   d3's selection API; at a few hundred notes each tick is thousands of DOM
   attribute writes, so the simulation and the pointer fight for the main
   thread and a drag stutters. Obsidian renders its graph to a **canvas**
   (PixiJS/WebGL) precisely because of this.
2. **The physics is tuned for a demo, not a notebook.** A fixed charge, no
   collision force, `alphaDecay 0.05` (the graph settles in ~90 ticks and
   then freezes: a dragged node's neighbours barely follow), no
   `velocityDecay` tuning, and gravity that pulls everything into one
   clump. Obsidian's feel comes from a *live* simulation with `alphaTarget`
   raised on drag and decayed on release, collision radius from node size,
   and a centre force weak enough that clusters keep their shape.
3. **Nodes are all the same size and every label is always on.** A second
   brain graph reads because size encodes degree (or recency), labels
   appear by zoom level and on hover, and the hovered node's
   neighbourhood lights up while everything else dims to 20%. Here every
   node is one radius, every label is drawn, and hover changes one halo.
4. **Colour has no semantics a reader can learn.** Category colours are
   the graph's own palette; clusters use the same. There is no colour by
   tag, by age, by folder/space, and no way to *save* a colour rule, the
   thing Obsidian's "groups" do and the thing that makes a graph a lens.
5. **The view is awkward.** The graph sits in a card under a dock with a
   stats line and a legend row, in a page that scrolls; the canvas is a
   fixed height; fullscreen is a mode. A graph is a *space*: it should fill
   the tab, the chrome should float over it (the dock, a legend, a minimap,
   the zoom strip), and the page must not scroll.
6. **Utility stops at looking.** No lasso select → act (tag, link,
   move to a space, make a map); no "open in split" of a hovered note; no
   timeline scrub with a *play*; no local-graph pane beside an open note;
   no export of the picture that matches the screen.

## 3. The target, in one paragraph

A full-tab canvas graph that renders 5,000 nodes at 60 fps, where notes
are circles sized by degree, coloured by a *rule* you can choose and save
(category, tag, space, age, cluster, "has a map"), labels appear as you
zoom in and on hover, the hovered neighbourhood lights up, dragging feels
physical (the neighbours follow and the rest settles), the dock, legend,
minimap and zoom float over the space, and a lasso turns a region into an
action. The local graph of any note is one click away and can sit beside
the note. The same renderer draws the Dashboard widget's small graph and
the map's node graph, so the three cannot disagree.

## 4. Decisions to make first

- **Renderer: Canvas 2D first, WebGL later if measured.** Canvas 2D with
  d3-force in a Web Worker handles 5k nodes / 10k edges at 60 fps on a
  laptop; it needs no new dependency (d3 is vendored) and keeps the
  export path (`canvas.toBlob`) trivial. WebGL (PixiJS, MIT, vendorable)
  is the step if a measured notebook is bigger than that. Hit-testing via
  a quadtree (`d3.quadtree`), not per-node DOM events.
- **Simulation off the main thread.** `d3-force` runs in a Worker; the
  main thread receives positions per frame (a `Float32Array` transferred,
  not copied) and paints. Drag sends the pinned position back. This is
  what makes drag smooth regardless of N.
- **Layout persistence.** Positions are saved per view (the saved-views
  feature already stores layout/colour) so a notebook opens where it was
  left rather than re-exploding, `/graph/views` gets `positions` (a
  compact `{id: [x, y]}`), written on settle and on drag end.
- **Backend computes what the client should not.** Degree, cluster id,
  and age bucket come from `/graph` per node (cheap, one pass); community
  detection stays in `/graph/structure` and is cached per notebook
  version; a `?since=` cursor makes the payload incremental for big
  notebooks.

## 5. Phases

### Phase 1: the canvas renderer and physical drag (1–2 sessions)
Canvas 2D renderer behind the same `renderGraph()` entry; d3-force in a
Worker; quadtree hit-testing; drag with `alphaTarget(0.3)` on start and
decay on end, `forceCollide` from radius, `velocityDecay 0.4`, a weak
centre force; node radius by degree (`4 + 2·√degree`, clamped); labels by
zoom (`k > 1.4`) and on hover/selection; hover dims non-neighbours to
20%; the existing search highlight, trace, focus mode, colour modes, time
slider and saved views keep working through the new renderer.
**Gate:** a 2,000-note fixture built by a script (`scratchpad/graph-
fixture.js`) paints its first frame < 300 ms and holds ≥ 55 fps during a
2 s drag (Playwright `requestAnimationFrame` counter); no frame > 16 ms
on a 200-note board; `errors.js` 0.

### Phase 2: the space (½ session)
The graph fills the tab; the dock, legend, minimap and zoom strip float
over it on the popover shell; the page does not scroll on Graph; the
stats line becomes a chip in the dock's identity zone; fullscreen is
just "hide the app chrome". Dark theme measured with `contrast.js`.

### Phase 3: colour rules and groups (½ session)
"Colour by" becomes a rule picker (category, tag, space, age, cluster,
has a map, has a file) plus **groups**: a saved search → a colour, listed
in the legend, stored with the view. Legend entries toggle visibility.

### Phase 6: the node panel (½ session, INBOX 59)
The popup that opens on a node is a form with nine equal buttons under it.
Target: a header (title, category chip, the confidence as a small mark
beside it, not a chip), one muted meta line (date, links, views), the
attachment as a compact row, the content editor sized to its text (four
lines minimum, grows), tags, and a single primary Save that appears only
when something changed. Actions become one toolbar row of icon buttons
with tooltips in three groups: read (Open, Similar, Trace), shape (Grow,
Focus, Link, Remind), keep (Favourite; Bin last, separated, ghost). Open
is the one filled button. Width and the dock grammar per DESIGN.md; the
panel scrolls inside, never the page; measured at 1440 and 1024 and on
390 as a sheet. Gate: `scratchpad/ui-sweeps/graph4b.js` plus a node-panel
probe that counts buttons per row and the panel's own scrollHeight.

### Phase 5: backend (built; one row deliberately deferred, see below)
Built 2026-09-09 (HISTORY.md, "Built, Phase 5 (backend)"): the per-node
fields, `/graph/structure` cached per notebook version, and the payload
gate. Two more rows of the original phase were re-read against the code on
2026-09-20 rather than started:

- **Positions on `/graph/views`.** Views are localStorage on purpose
  (`graph.js`, "saved views": per-device workspace state of the same kind
  as `graph-layout`, not notebook content that belongs in a backup), and
  the positions that *are* notebook content, the pins, are already on the
  Entry as `graph_pin_x`/`graph_pin_y` and already restored by both
  renderers. The reason recorded for leaving this was "the local pane and
  multi-device views are the reason to move them, and neither exists yet";
  the local pane exists now and does not read saved views, and there is no
  second device to sync to in a local-first notebook. Nothing to build
  here as written.
- **What was genuinely missing** (a saved view did not restore where the
  unpinned notes sat) is built. Moved to HISTORY.md ("Built, Phase 5
  continued (positions on a saved view), 2026-09-21", GRAPH_PLAN.md); the
  decision it turned on ("Decision made, 2026-09-21: a restored view holds,
  it does not re-settle", below) stays here.
- **A `?since=` cursor.** Still nothing polls `/graph`: every call is
  `renderGraph()` behind a control, a tab activation or a save. A query
  parameter with no caller is the "feature that never ran once" shape
  CLAUDE.md section 6 puts second on its list. Left until something polls.

## 6. Consistency rules (learnability)

The graph uses the app's tokens for every colour; the dock is the Phase 8
dock; the legend is `.library-chip`s; the right-click menu is
`.action-menu`; the zoom strip is the whiteboard's `.graph-zoom` recipe
(they are the same control and must look it); keyboard: `+`/`-` zoom,
`0` fit, `F` focus selection, `Esc` clears: the same keys the whiteboard
uses.

## 7. Not verified until built

Frame rates are only meaningful on the sandbox's CPU; record them as
relative before/after numbers, not promises. WebGL is measured, not
assumed, before it is adopted.

---

## Built, Phase 6 (the node panel), 2026-09-09

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", GRAPH_PLAN.md) on 2026-09-09: a plan holds open work only.

## Built, Phase 5 (backend), 2026-09-09

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", GRAPH_PLAN.md) on 2026-09-09: a plan holds open work only.

## Built, Phase 4 (utility), part one, 2026-09-09

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", GRAPH_PLAN.md) on 2026-09-09: a plan holds open work only.

## Built, Phase 4 (utility), part two: the local map, 2026-09-13

Moved to HISTORY.md ("Moved from the plans, 2026-09-13", GRAPH_PLAN.md) on 2026-09-13: a plan holds open work only. Phase 4 is complete.

## Built, Phase 3 (colour rules and groups), 2026-09-09

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", GRAPH_PLAN.md) on 2026-09-09: a plan holds open work only.

## Built: Phase 1 (the canvas renderer and physical drag)

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", GRAPH_PLAN.md) on 2026-09-09: a plan holds open work only.

## Built, Phase 2 (the space)

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", GRAPH_PLAN.md) on 2026-09-09: a plan holds open work only.

## Placed from INBOX, 2026-09-09

The owner's reports this plan owns, moved whole from INBOX.md with their numbers (never reused). Each becomes a phase row when its phase is written; until then this list is the phase.

41. **(the panel: fixed, 5724587 and dbff8f0; the clean-up is Phase 4)**
    **Graph display options belong on the dock, and the options panel
    needs a redesign**; the graph needs a utility, UI and interaction
    clean-up. Owner: GRAPH Phase 2 remainder (gear button, INBOX 21) and
    Phase 4; the panel on the popover shell with the dock-menu sections.
78. **Graph minimap UX and utility**: Phase 6b, **built 2026-09-13**. The
    draggable viewport rectangle, click-to-jump, wheel zoom about the pointer
    and cluster-coloured dots landed earlier; this pass added the last two,
    the size toggle and the fade when the whole graph already fits. Size is a
    Small/Large select beside Position in the dock's Minimap section (the map
    itself is `aria-hidden` decoration that happens to be draggable, so a
    focusable control inside it would be one no screen reader could reach),
    and Large is the same picture at 1.5x, scaled on the element so the
    projection and the drag keep working off the rendered width they already
    measure. The fade is on the viewport rectangle's own area against the box,
    not on the zoom scale: "everything fits" is a fact about this graph's
    extent at this window size. Measured
    (`scratchpad/ui-sweeps/minimap6b.js`, 1440x950, 297 notes): fit-to-screen
    at k 0.56 gives a 168x112 rectangle, redundant true, opacity 0.12; at k
    1.6 the rectangle is 78.5x45.3, redundant false, opacity 0.45; Large
    renders 252x168 with the projection intact.
59. **Graph node popup panel redesign** (screenshot, 00:50; the owner:
    "include redesigning the graph node popup panels in the graph redesign
    plan"): title, five meta chips at one weight, a file card, a tall
    content editor, tags, Save, then a 3x3 grid of nine equal action
    buttons (Favourite, Grow, Focus, Similar, Link, Trace, Remind, Open,
    Bin). Placed as GRAPH_PLAN Phase 6. Owner: Opus, now.

## Placed from INBOX, 2026-09-09 (the owner's evening batch)

Built. Moved to HISTORY.md ("Moved from the plans, 2026-09-20", GRAPH_PLAN.md)
on 2026-09-20, with the measurement of each: a plan holds open work only.

## Decision made, 2026-09-20: three of the six options sections are folds

The recommendation on record (archive/agent-remaining/graph.md, "Open, found
and not fixed") was that Groups and Minimap become one collapsed `details`
each. Taken, and measured: it is no longer enough. The panel had grown from
the 587px that recommendation was written against to 655px of list in a 488px
box at 1440x900, because the Show section went from six switches to nine
(143px to 211px). Groups and Minimap folded give 517 in 488, still scrolling.

Decided, since which section gives way next is a design call and rule 3 says
to record one: **Physics folds too.** The rule the three share is that they
are set once and then left, while Show and Time are used with the map in
front of you. Physics is the clearest of the three on that test: its two
sliders are already disabled outright under the tree layouts, which is the
app saying they do not always apply. Its "Unpin all" rides the fold's own
`<summary>`, where it already rode the section head, and the button calls
`preventDefault` so releasing the pins does not also open or close the fold.

Each fold remembers whether it is open, for the reason the panel itself does.
Closed is the default. `details.settings-fold` is the app's existing
disclosure and is now a row in DESIGN.md's recipe index, with
`tests/test_ui_recipes.py` holding the four rules that dress it to one set of
families and the count of disclosures that name no family at all.

Measured after, `scratchpad/ui-sweeps/graphoptfold.js`: 451px of list in a
451px box at 1440x900 and again at 1024, nothing scrolling, 37px clear of the
cap; opening all three gives 669 in 488, which scrolls inside the panel as it
should. At 390 the panel still scrolls (795 in 286, against 1071 with the
three open), which is the phone's own cap rather than this panel's size.

## Decision made, 2026-09-13: a Show switch that is off means absent

INBOX 185 forced a decision the three switches in the Show section had never
actually been given: what "off" means. Entities and Documents add nodes that
exist nowhere else, so off has always meant absent for them. A board is an
`Entry`, so it was on the map either way and the switch only changed whether
the node said so. Two readings of one control drawn three times.

Decided: **off means the thing is not on the map.** `include_maps=false` drops
every board from `/graph` at the source, so there is no board node, no map
edge, and no board in the centrality pass or the path index. The switch is
labelled Boards rather than Mind maps, because a whiteboard is a board too and
a switch that hides one and not the other is the same confusion one step over.

Still open, and deliberately: `/graph/local` has no such switch, so focus mode
and the local pane still walk boards as notes. They are a neighbourhood of one
note rather than a picture of the notebook, and nothing has been asked about
them.

## Decision changed, 2026-09-09: a drag places, Shift pins

The plan and the code both carried "a drag is an intentional placement and
it stays placed", added after the report that arranging the map was
impossible because a released note was handed back to the simulation and
pulled wherever the forces wanted.

The owner has now asked for the other end of it (INBOX 96): "my original
annoyance was that I'd try to drag a node or cluster around and it would
just snap back ... but I move a node a little and then I have to unpin it
and there's got to be a better way."

Both complaints are satisfied by one rule, and the reason they are not in
conflict is that releasing is not the same as snapping back. At the end of a
drag the simulation's alpha is already decaying (`alphaTarget(0)`, which the
worker has always done), so a released node settles *from where it was
dropped*, with its neighbours, rather than being yanked to a fresh solution.
Placement without permanence is what the view wanted; a pin, for the notes
that must not move at all, is Shift and drag, or the node menu.

So, on both renderers: a plain drag places and releases, Shift and drag
pins, a node already pinned stays pinned at its new place, a zero-distance
drag is still a click, and only a real pin is written to
`graph_pin_x`/`graph_pin_y`. The dashed held ring follows `fx`, so it now
appears only on real pins, which is the last line of the owner's own
description of what they wanted.

The group drag this entry left open is built: moved to HISTORY.md ("Moved
from the plans, 2026-09-23", GRAPH_PLAN.md).

## Decision made, 2026-10-11: a drag moves, a double-click pins

The owner: "moving nodes keeps them stuck there, they should only be stuck
in place if I double click on them to freez their position. though if the
user moves them, they should settle into place in that general position".
INBOX 802's hold (a dropped note held at the drop until the layout rested,
then let go into a map with no heat left) read as a pin. Now the drag holds
the note under the pointer only while dragging; on release `fx`/`fy` clear
and the layout is left at a low heat (`RELEASE_ALPHA` 0.016, graph-worker.js),
so the note eases into place near the drop (a 360-unit drop: 58 from it at
rest, `test_graph_feel_100.py`). Double-click toggles a real pin with its
held ring; Shift and drag still pins; Unpin all clears only real pins; a
pinned note dragged stays pinned. Help says drag moves, double-click pins.

## Placed from INBOX, 2026-09-13

- **Hovering a node grows it into its own halo** (INBOX 149, the owner: "can
  you make graph nodes temporarily expand to fill their glow bubble when I
  hover over them or smth?? I feel like the graph nodes could look slightly
  nicer, cooler, more professional and more modern. visually"). Built, both
  renderers. Detail in HISTORY.md.

## Placed from INBOX, 2026-09-21

Item 275 (the graph's full screen spending one Escape on two things) is
fixed. Moved to HISTORY.md ("INBOX resolved, 2026-09-21").

## Decision made, 2026-09-21: a restored view holds, it does not re-settle

The open question Phase 5's "positions on a saved view" row left ("whether a
restored arrangement then holds or settles") is decided: **it holds.** A
person saved a picture of the map; reopening it must give them that picture,
not a fresh relaxation of the same forces that happens to start from it. So
`graphApplyView` seeds each saved node's x/y and the simulation starts at
alpha 0, not alpha 1: no reheat, nothing moves.

The one case that must still reheat is a note added *since* the view was
saved, which has no saved position at all: that note alone needs the
simulation to place it. When one exists, every saved note is held in place
(`fx`/`fy`, the same "freeze" a drag already uses to hold the rest of the map
still while one node moves) for exactly the length of that settle, and
released the moment it ends. A real pin (`graph_pin_x`/`graph_pin_y`,
notebook content) is a different, permanent hold and is never touched by
this: it is set and released by the code that already owns it.

Read this where the code carries it out: `graphCaptureView`/`graphApplyView`
(`frontend/js/graph.js`) and `renderGraphCanvas`/`gcStartWorker`
(`frontend/js/graph-canvas.js`, the default renderer).

Claim #238 (2026-10-11): the hold was a separate `freeze` after `init`, and a
view re-picks its layout, which clears the fit, so the init warmed for 450ms
first and moved every saved note. The hold now rides in the init (`held`), a
restore never warms or plays an intro, and graphviewpos.js compares with what
the view stored, not a snapshot taken mid-settle.

## Decision made, 2026-10-11: the drawn map is for reading

BACKLOG's "decide what the graph is *for*" (a picture for a person, or a
thing the AI walks): the picture. A person wants few, meaningful lines, so
the map draws links and, on a toggle, each note's two closest matches; the
AI's retrieval walks the links table and the index, weighted, and never
needs a line drawn to use it. Typed links and strength serve both without
the picture growing denser.


## Decision made, 2026-09-24: similarity is each note's two closest matches

INBOX 412 (the owner: "when I tick similarity on the graph, this happens, is
there a way to make it more visually understandable or parsable??"). What was
read first: Gephi and InfraNodus thin a weighted network by weight and map the
weight onto the stroke; Kumu scales a connection's width by its strength and
focuses a selection's neighbourhood; Obsidian and Logseq fade what a hovered
note is not joined to; Heptabase draws no inferred relations and lists them
beside the card. Decided, and measured on 42 notes over six topics with
vectors shaped like bge-small's (`scratchpad/ui-sweeps/graphsim.js`):

- **k = 2.** Each note keeps its two strongest similarity lines above the
  cutoff; a line survives if it is in either end's two. 200 lines became 58
  and 1,701 crossings 39; k = 3 gave 80 lines and 84 crossings with the same
  six clusters, so the fewer lines win. Pruned before the layout, so the
  springs stop pulling the topics into one ball.
- **Three strengths, relative to the range drawn**, in opacity and width, one
  dash, the strongest still under a link's opacity, stroked beneath the links.
- **Scores on demand**: the note in focus writes a percentage on each of its
  lines where there is room and lists all of them in its tooltip; a pill with
  no room is left out, never stacked.
- **One cutoff control**, Strength (55 to 95), in the Show grid's free cell,
  shown only while Similarity is on, so the panel stays 451px in its 451px box.
- **Reset to defaults** covers the layout, the colour rule, the physics, every
  Show switch, the cutoff, the time filter, the minimap and the legend's
  hidden kinds; it keeps groups and saved views (things somebody made and
  named) and which folds are open. It shares the panel's last row with
  Suggest links, and its toast carries the Undo.

## Decision made, 2026-09-26: the hubs are named, over a dot if they must be

**Superseded 2026-10-06 by the owner's own decision in INBOX 693** ("labels
never over dots or lines"): a hub's name now takes a place on no dot, out
to a step beyond its near places, or waits for the zoom (`gcPlaceLabels`).
The record of what was built is in HISTORY.md, INBOX resolved.

The label pass (`gcDraw`, `gcPlaceLabels`) placed a name under its dot or
not at all, and never over another dot. On the 417-note, 1,105-link fixture
that named none of the ten best-connected notes in view, at the fit (where
the zoom gate drew no label at all above 400 notes) or at 2x (30 labels, all
on the thin edge of the map, because in the dense middle "under" is always
another dot). Decided, and measured with `scratchpad/ui-sweeps/graphlabels.js`:

- **Four places, in order**: under, above, right, left. The first free of
  every placed label and every other dot wins. At 2x: 31 labels to 80.
- **Landmarks at the overview**: below the zoom gate on a map past
  `GC_LABEL_ALL_MAX`, the twelve best-connected notes in view with two or
  more links are still queued for a name. At the fit: 0 labels to 10.
- **The ten best-connected in view may sit on a dot**, and only they: they
  live where every place is on some other dot, and a map is read by them.
  Two names still never overlap (0 overlapping pairs at the fit and at 2x),
  every other label keeps the dot rule (0 on a dot), and a covered dot still
  takes the pointer, because a canvas label is paint and hit testing is on
  the notes. Hubs named: 0 to 10 of 10 at the fit, 0 to 9 of 10 at 2x.

## Decision made, 2026-10-03: the shape follows the links, and the unlinked sit on a ring

INBOX 443 (1) (the owner: "the graph shape could look nicer"), measured with
`scratchpad/ui-sweeps/graphlook.js` on 60 notes in 5 categories, 10 unlinked,
1440x900, and on a 300-note fixture whose links ignore categories:

- **The category gather scales with how category-shaped the links are**
  (`groupCohesion`, graph-worker.js): the share of non-similarity links joining
  two notes of one category. At 0.6 or more the pull is 0.05 and the ring 28
  per root of the count (the nearest-four colour purity rose 0.56 to 0.84); at
  0.2 or less it is the old 0.025 and 22. A flat 0.05 doubled the 300-note
  fixture's crossings, so it is not flat.
- **Unlinked notes have seats** on a ring that follows the cluster's outline
  (36 angle bins, smoothed by the widest neighbour), each category's on the arc
  facing its own place, evenly spaced, a second ring when an arc is full. Gap to
  the nearest linked note, in the cluster's own median spacings: 3.0 to 1.8.
- **Links wear a category.** Same colour at both ends takes that colour;
  a bridge stays neutral; a reasoned link is 1.9px at 0.62; curved by default
  (a note that never touched the switch is on). Tapered strokes were not built:
  a taper is one polygon per link, and the batched stroke per colour is what
  keeps a 2,000-link map inside a frame.
- **One size scale, 5 to 15**, and a glow at roughly two thirds of its old
  strength.
- **Not changed, on purpose:** the fit (`fitGraphToView` pads each dot by its
  radius plus 34 for its label, a decision from the "gap at the bottom" report);
  the server's 40-character preview, so the whole name on hover is as long as
  the server sends.

## Decision made, 2026-10-04: names on plates, clear of lines, and a calmer palette

INBOX 493 (the owner: "is there a way to make my graphed notes look
nicer??", a screenshot with labels in white over the lines). Measured with
`scratchpad/ui-sweeps/graphlook.js` (60 notes, 1440x900) and
`graphlabels.js` (417 notes):

- **A name stands on a plate**: its box in the card's colour at 0.88, 4px
  corners, in place of the 3px card stroke around each glyph, which left a
  line under a name showing between its letters.
- **Placement knows the lines**: eight places (under, above, beside, the four
  corners); the first free of labels, dots and lines wins, else the one
  crossing the fewest. Label-line crossings 43 to 28, names on a line 14 of
  15 to 12 of 19. Not while the layout moves (the grid would rebuild every
  frame); the names cross-fade to their places when it settles. Cost on the
  417-note map, settled: a frame 3.3 to 4.1ms at the fit, 2.6 to 4.9ms at 2x.
- **The automatic palette at 78% saturation**, same hue and lightness, so
  contrast is unchanged; a chosen colour is drawn as chosen.
- **Not changed:** the reasoned link's accent stroke (1.9px at 0.62, the
  decision above), the loudest thing left on the map.

## Decision made, 2026-10-04: a Display fold

The owner asked for Label backgrounds as a switch, and 514 adds Arrows and two
display sliders; the Show grid could not take them (the panel already scrolled
closed, 632px in 492 at 1440x900). Decided: **how the map is drawn is a fourth
fold, Display**, on the 2026-09-20 rule (set once, then left): Labels, Label
backgrounds, Curved links, Cluster glow, then 514's Arrows, Text fade and Link
thickness; Length by similarity and Group by category move to Physics (they are
forces) beside Link force, so Show stays four rows. Off, Label backgrounds draws each name
on the old 3px card-coloured outline; the placement keeps it clear of lines
either way (`scratchpad/ui-sweeps/graphdepth2.js graphplates`: 19 plates on, 19 outlines
off, off kept after a reload).

## Decision made, 2026-10-04: a Filter fold

KG8 asks for filter chips by kind of link and by property. Decided: **a fifth
fold, Filter**, after Display, on the same rule (set, then left): a row of
chips per kind of link on the map and a row per property value, built from
what is on the map, so the closed panel grows by one summary row and the
chips never cost the Show grid a row.

## Decision made, 2026-10-05: one PageRank, the map's

`/graph` and `/graph/local` shared one cache slot ("centrality", keyed by the
notebook and the similarity switch) while ranking two different graphs: the
map leaves drafts out, and boards unless Maps is on; focus mode indexed every
live note. Whichever call came first was served to the other (a note's size in
focus mode depended on which view had been opened since the last edit), and
Maps on was served the no-maps ranking. The similarity sweep's slot had the
same shape. Decided: **a note's centrality is the map's** (live, non-draft
notes; boards only with Maps on), one slot per (similarity, maps), built from
columns by `_centrality` itself and never from a caller's index; focus mode
shows the map's number, not a PageRank of its own neighbourhood, because
centrality is a global property and a local one would make every focus
view's centre its biggest dot. One similarity sweep per version, over the
map's notes, each caller keeping the pairs inside its own set.
`tests/test_graph_centrality_slot.py` (3, all failing before). A warm `/graph`
no longer builds an index at all, and reads its notes and links as column
rows instead of 15,000 ORM objects (the space is in the fingerprint now too).

**Measured at 5,000 notes** (`scratchpad/kg1005_graph_bench.sh`, in process,
10,000 links, two tags a note, the box shared with seven other agents, so the
numbers are relative; before and after alternated twice on one notebook):
warm `/graph` p50 3,273 to 4,127 ms before, 720 to 1,017 ms after; cold 6.9 to
7.4 s before, 4.5 to 4.7 s after; Maps on warm 2.8 to 2.9 s before, 0.8 to
1.1 s after; focus mode warm 80 to 101 ms either way; the payload is 3.0 MB
(234 KB gzipped in the browser, ARCH-14). Profiled warm handler: 2.77 s to
0.89 s, of which building the node dicts is now the largest part (0.37 s) and
`json.dumps` 0.15 s. Left: the payload itself (a fingerprint-keyed cache of the
encoded bytes needs the pins, access counts, attachments and board members in
its key, none of which moves the fingerprint), and the canvas side at 5,000
(FE-04, the frontend agent's).

## Placed from INBOX, 2026-10-04: parity with Obsidian's graph

514 (parity with Obsidian's graph) and 518 (wiki link origin, the payload cache,
the fingerprint, similarity per note) are built: moved to HISTORY.md ("INBOX
resolved, 2026-10-04"). Arrows default off.

## The knowledge graph, 2026-10-04 (INBOX 528)

528. **The owner, 2026-10-04, verbatim.** "what I want to take from obsidian
     is how ideas, context, relationships, and similarities are stored,
     recognised, sorted, visualised etc. My graph and the backend knowledge
     graph needs to be waaayy better more versatile and have more features
     than both obsidian and notion". Placed here: the phases below (KG1 to
     KG9) are the brief; KG1 and KG2 are built first.

Every phase, KG1 to KG9, is built (2026-10-04). The spec as it was written
((a) what existed, (b) research, (c) the gap table, (d) the target design,
(e) the build order) moved whole to HISTORY.md, "Moved from the plans,
2026-10-04 (the knowledge graph, INBOX 528)", beside each phase's Built
block. What stays here is the standing decisions and what is still open.

### Still open after KG1 to KG9

- A real local model's `name|kind` entity extraction and a topic's sentence
  were never run here (no model in the sandbox); both fall back cleanly.
- `/graph` at 5,000 notes: the map's read is slim (`slim=1`, 1,767 KB from
  3,145; built, HISTORY.md "Moved from the plans, 2026-10-05 (op3-1005)").
  The generic encoder is skipped and the PageRank's links are read as
  columns (same HISTORY block): the first build after a change is about
  0.7 s on this sandbox at load 7. Open: nothing measured worth a step;
  PageRank itself is 0.13 s.
- The note field's picker and the query table's rollups are built
  (2026-10-05): moved to HISTORY.md ("Moved from the plans, 2026-10-05
  (GRAPH_PLAN, the last KG rows)").

**Decisions made (recommendations taken):** a suggestion never links by
itself; every inferred relation carries a reason and a confidence, and the
reasons are the signals, not a model's prose; properties live in the note's
text and the table is an index; components stay the clusters, topics are a
labelled second layer; the structural signals work with embeddings off; one
mention scanner for notes and documents; a moved span is refused, never
guessed; a link's properties on a link with a private end are sealed exactly like its reason (encrypted at rest, read while unlocked, absent while locked), because they are free text a person wrote about the notes (sweep 1004).

**Not to build:** a block model (notes are short and `[[Note#Heading]]`
exists); a second canvas (the whiteboard is one); model-extracted
entity-to-entity triples at notebook scale (slow and unreliable on a small
local model; typing happens on accept, one pair at a time); Leiden as a
dependency (label propagation in Python suffices at 10k); formulas and
rollups beyond count, sum, min, max, earliest and latest.

## Decision made, 2026-10-10: a category is where a note is filed, a topic is what its links say it is about

The owner, 2026-10-10: "Should topics from the graph be more integrated app
wide?? How are they different from categories??"

- **A category is chosen.** One per note, set by you or by filing, a folder
  in the sidebar, the same until someone changes it. Notes, Library, Tidy and
  filing all read it.
- **A topic is found.** The graph's label propagation over the links
  (`entry/topics.py`) puts a note in at most one topic of three or more; it
  moves when the links move, is named by the tag, entity or word its notes
  share most, and can be renamed. The name is kept by the topic's notes (half
  of them shared), so it survives a recompute.
- **Neither writes the other.** A topic never files a note, and filing never
  reads topics. A topic whose notes sit in three categories is the useful
  disagreement. Turning a topic into a category is a person's own act
  (2026-10-11, ledger 945; Brief 39b's steps did not carry it): the topic's
  card has File as a category, the batch bar's one move with one Undo, the
  name offered being the topic's.
- **A topic is never "Topic 2" while its notes say something** (2026-10-11,
  the owner on a "Topic 2" chip): below the share bar the best term two of
  its notes share names it, then its most linked readable note's title
  ("Around ..."); "Topic N" is left for private or untitled notes.
- **Three notes stay at the fit's zoom clamp** (2026-10-11, ledger 967): at
  1440x900 they fill 0.80 of the free height, not more, because past
  `GRAPH_FIT_MAX_ZOOM` (2.5) the nodes and names grow cartoonish; a tiny
  map reads as tiny.
- **Integration is the same object shown everywhere, not a second taxonomy.**
  The note card and the note's panel on the map carry its topic as a chip that
  opens the graph on it; the name is renamed in place wherever it is written
  (the plate, the card, the panel); a topic is moved on the map by its name,
  its notes together and pinned.

## Placed from the owner's list, 2026-10-10

Every entry is built (the graph agent, 2026-10-10): the owner's words, the
recommendations and what was built moved to HISTORY.md, "Moved from the
plans, 2026-10-10 (graph-1010)". The categories-versus-topics answer is the
decision above; turning a topic into a category is the card's File as a category.

### Vendored capabilities to use, 2026-10-10 (Brief 75)

The owner: "make sure all the vendored repositories are made full use of. I want maximum utility." Ranked by the utility to the surface; `scratchpad/vendor_use.py` prints the counts ("available N, called M") and `tests/test_vendor_utilisation.py` ratchets them, so a row that lands raises its floor in the same commit. Each is a lead from a lower-bound count: grep the call site before building (CLAUDE.md section 1).

- **VC11, D3 hierarchy layouts as a category overview** (M, rank 11). D3's hierarchy module is 15 exports with 2 called; `treemap`, `pack` and `partition` would show the notebook's categories by size. Measure: a treemap of the categories at 1,000 notes renders in under 100 ms and every rectangle's area is within 1% of its note count; reachable from the graph's view switch with a `data-help-for` popover.

## Placed from Brief 60, 2026-10-10 (the measured census)

- The graph is not idle at rest: `scratchpad/ui-sweeps/frames.js` counted 1, 9 and 10 long tasks (58 to 70 ms) in 3 s, 150 to 170 ms of script a second and 38 to 52 gaps over 20 ms of 83 to 134 frames, 2.5 s after the tab opened; a drag was 12 to 44 gaps over 20 ms of 302. Find what still runs (the force simulation after it settles, or a redraw loop) and stop it at rest; target zero long tasks (WORLD_CLASS 26.5).
- `/graph` is 22 ms for 45 KB of 71 notes; 10 of that is `_payload_key` (`routes_graph.py:667`). Not measured at 5,000 notes.

## Placed from INBOX, 2026-10-10 (the owner on the graph, again)

- INBOX 798, the owner 2026-10-10 23:27Z, screenshot: "the graph is still completely broken 😞 I miss how it used to move 😞 look at how the movement is in main and base and refine off that" (34 notes in one vertical line, topic labels stacked on it) and "there is no smooth transition, I just change views or reset it and it just suddenly changes or disappears and reappears". Owner: the graphfeel agent, round 2 (root cause of the line; main's motion as the reference; animated view changes).
- INBOX 799, the owner 2026-10-10 23:45Z: "Alright work autonomously to fix, finish,redesign, improve and extend everything. I will be at work. Impress me! :D" (the standing order for the day: the queue in HANDOVER, three Opus agents at most, Sonnet for well-defined work).

## Placed from INBOX, 2026-10-11 (the owner on dragging the force graph)

Owner: the graph agent (Opus), when a slot frees.

- INBOX 802, graph, the owner 2026-10-11 03:35Z, verbatim: "The graph movement is a lot closer to how it is on main and better than you had it, but I still cant move the force graph as well. Can you like copy the physics of the force graph on main?? like if cant drag parts of the graph to different areas of the graph and have it kinda settle into place there. idk but I quite like how it is on the main branch. also the resetting or re-centering of the force graph is not smooth and doesnt smoothlly pan over." Recommendation, taken: port main's force simulation and its drag (a dragged node pins while held, the simulation reheats, neighbours follow, it settles where dropped); reset and recentre ease the view transform over the motion token, never jump. Then, 03:50Z, screenshot (the graph sits right of centre, an empty minimap top left): "why's the graph so positioned to the right and not in the middle??" Fit centres on the visible canvas, reserving only what a showing panel covers.

## Placed from the owner, 2026-10-11: a tessellation view (next PR)

The owner: "I'm thinking next pr we should add another graph view which better resembles the essence of the name tessellate". A third view beside the force graph and the map: every note owns one cell of a plane tiled with no gaps (a Voronoi tessellation over the existing 2D layout, or a hexagon grid placed by it), neighbours are related notes, categories are coloured regions with a heavier border, and a new note settles into its cell the way the logo's third cell does. First step: mock three variants (Voronoi, hexagon grid, hexagon clusters per category) at 50, 500 and 2,000 notes for the owner to pick from, then a brief here.
