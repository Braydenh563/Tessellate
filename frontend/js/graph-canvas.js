// Tessellate: the graph, drawn to a Canvas 2D surface.
//
// GRAPH_PLAN.md §4 ("Renderer: Canvas 2D first") and §5 Phase 1. This is the
// other half of `graph-worker.js`: the worker decides where the notes are,
// this paints them, and neither one touches the DOM per node.
//
// **Why this exists at all** (§2.1, measured before it was written): the SVG
// renderer builds one `<g>` per node with a circle, a halo, a shine and a
// label, plus two `<line>`s per edge, and rewrites every one of their
// attributes through d3's selection API on every tick. At a few hundred notes
// that is thousands of DOM attribute writes per frame on the same thread the
// pointer is being handled on, which is why dragging stuttered. Here a frame
// is a few hundred canvas path operations regardless of how many notes there
// are, and the simulation is not even on this thread.
//
// It is loaded as a classic script *after* graph.js and before app.js, so
// `renderGraph()` in graph.js can dispatch to `renderGraphCanvas()` by name at
// call time. Nothing in app.js's own top-level wiring names anything in here.
//
// What is deliberately shared with graph.js rather than re-implemented: the
// note popup, the new-note form, the link panel, trace, the minimap, saved
// views, keyboard driving, `fitGraphToView` and the tree/radial/arc layout
// maths. Those are all renderer-agnostic, they work on `graphNodesRef` and on
// `graphSvg`/`graphZoom`, and this file points those at the canvas.

// --- the drawing surface ------------------------------------------------------

//: **One surface, not a pile of module globals** (GRAPH_PLAN Phase 4, the
//: local pane). Everything the renderer needs to draw one graph into one
//: canvas lives on an object made here, and every function below is handed
//: the one it is working on. It used to be forty-odd module-level `let`s,
//: which is fine while there is exactly one canvas and impossible the moment
//: there are two: the pane beside a note and the tab would have written each
//: other's node array, transform, worker and hover state. `s = gcTab` as the
//: last parameter everywhere means the tab's own calls, and the sweeps',
//: read exactly as they did.
//:
//: `size` says which of the two this is. "full" is the tab: it owns the
//: chrome (the legend, the minimap, the stats line, the time slider, trace,
//: the keyboard) and writes the renderer-agnostic globals in graph.js that
//: the chrome reads. "pane" is the small one beside a note: same draw, same
//: worker, no chrome, and it touches none of those globals.
function gcSurface(options = {}) {
  return {
    size: options.size || "full",
    boxId: options.boxId || "graph-box",
    canvasId: options.canvasId || "graph-canvas",
    //: What a click on a node does on this surface. Null means the Graph
    //: tab's own behaviour (trace, link, the node popup).
    onNodeClick: options.onNodeClick || null,

    canvas: null, // the <canvas> element
    ctx: null,
    dpr: 1,
    dims: { w: 0, h: 0 },
    observer: null,
    drawQueued: false,
    minimapQueued: false,
    //: The pan/zoom behaviour and the d3 selection it is attached to. The tab
    //: also publishes these as `graphSvg`/`graphZoom`, which is what every
    //: camera helper in graph.js drives; a pane keeps them to itself.
    svg: null,
    zoom: null,
    //: The live pan/zoom matrix. Kept here as well as on the element (d3
    //: stores it there) because every draw needs it and `d3.zoomTransform` is
    //: a property lookup plus a null check on a hot path.
    transform: null,

    worker: null,
    //: **Which simulation a message from the worker belongs to.** Bumped every
    //: time the node array is replaced, sent with each `init`, and echoed on
    //: every tick. A `{type:"stop"}` cannot unsend a tick already posted (both
    //: directions of `postMessage` are asynchronous), and the tick handler
    //: writes positions *by index*, so a tick from the previous run landing
    //: after a relayout overwrites the new positions with the old ones.
    //: Measured: the tree switched to 500 ms into a warm force simulation came
    //: back with its depth-1 nodes spread over 351 px and its depth-2 nodes
    //: over 778 px, where a tree has every node of one depth at one x. That is
    //: the scatter reported as "the tree view on the graph is still broken",
    //: and it also explains why it was intermittent: at six other moments in
    //: the same cooling curve the same switch was clean. A computed layout
    //: never sends an `init` at all, so its epoch can match nothing and every
    //: tick arriving under it is dropped.
    epoch: 0,
    //: A slow payload that has been overtaken by a newer render must not paint
    //: over it. A canvas has nothing to clear, so this is the guard.
    renderSeq: 0,

    //: The drawing's own copy of the graph. On the tab `nodes` is the same
    //: array `graphNodesRef` points at, so everything in graph.js that walks
    //: the nodes (the keyboard, the minimap, `fitGraphToView`, drag-to-link)
    //: sees exactly what is on screen. Edges have their `source`/`target`
    //: resolved to node objects once per render rather than per frame.
    nodes: [],
    edges: [],
    adj: new Map(),
    byId: new Map(),
    quadtree: null,
    quadtreeDirty: true,
    layoutKind: "force",
    tree: null, // the laid-out hierarchy for tree/radial/arc, else null
    timeCutoff: null,
    colourOf: () => "#888",

    //: Set while a pan/zoom gesture is in flight, so a node sliding under a
    //: stationary cursor does not register as a hover. Same reasoning the SVG
    //: renderer's `graphIsPanning` carries; here it is cheaper, because there
    //: is no CSS `:hover` to fight as well.
    panning: false,
    wired: false,
    dropTarget: null,
    dragNode: null,
    //: The rest of a lasso selection travelling with `dragNode`, each with its
    //: offset from it and whether it was pinned before the gesture.
    dragGroup: [],
    //: The node the pointer is over. The tab mirrors it into
    //: `graphHoveredId`, which the node popup reads.
    hoveredId: null,
    hoverTo: null, // the node id growing
    hoverFrom: null, // the node id shrinking back
    hoverStart: 0,
    hoverEase: 1, // 0 to 1 across the two above

    //: GRAPH_PLAN Phase 4. A lasso (Shift and drag on empty map) selects
    //: notes; the selection dock acts on them. `lasso` holds world points
    //: while a lasso is being drawn, `selected` the ids it caught (or
    //: Shift-clicks added). `hiddenIds` is the right-click "Hide" for this
    //: visit only: it is not a saved preference, and the legend says how many
    //: are hidden. All three are the Graph tab's; a pane wires none of them.
    selected: new Set(),
    lasso: null,
    hiddenIds: new Set(),

    //: "the camera has framed this graph once already". The tab keeps the same
    //: fact in `graphAutoFitDone`, which switchTab clears on a fresh visit; a
    //: pane has no tab visit to hang it on and keeps its own. `fittedOnce` and
    //: `userZoomed` are why there are two fits and why the second one is
    //: conditional: see the tick handler.
    autoFitDone: false,
    fittedOnce: false,
    userZoomed: false,

    //: Timing for the gate (§5 Phase 1) and for `window.__graphDebug`.
    //: `firstFrame` is measured from the moment the payload has arrived to the
    //: end of the first paint, which is what the plan's "< 300 ms after data
    //: arrives" means.
    timing: { dataAt: 0, firstFrame: 0, lastFrame: 0, frames: 0 },
    //: The last thing the worker said about itself: how hot the layout still
    //: is, and how many steps it has taken. Reported on the debug surface
    //: because a slow-looking map is two separable questions, is the
    //: simulation crawling or is the paint dropping frames, and guessing which
    //: cost a round of theorising before this was here.
    alpha: 0,
    ticks: 0,
    tickMs: 0,
    //: How many labels the last frame wanted, how many it could place without
    //: one landing on another, and how many of those were asked for by name
    //: (the hovered or keyboard-focused note, and the search hits, which are
    //: drawn whether or not they clash). On the debug surface because "the
    //: labels are unreadable" and "the labels are fine" look identical from
    //: outside the canvas. `labelBoxes` is what the last frame actually
    //: placed, in world coordinates, read by `scratchpad/ui-sweeps/graph2.js`.
    labelsWanted: 0,
    labelsDrawn: 0,
    labelsPriority: 0,
    labelBoxes: [],

    //: The composed frame (`gcDrawComposed`): the scene layers and the camera
    //: they were painted at, whether anything but the camera or the hover has
    //: changed since, and the hover drawn over them.
    scene: null,
    sceneStale: true,
    paintMode: null,
    dimA: 0,
    overCentres: new Map(),
    overLit: new Map(),
    searchOver: false,
    warmDim: false,
  };
}

//: The Graph tab's surface: the one every existing caller means.
let gcTab = gcSurface({ size: "full", boxId: "graph-box", canvasId: "graph-canvas" });

//: **Where a surface ends and the tab's globals begin.** Three facts are read
//: outside this file by things that only ever meant the tab: whether the
//: camera has framed the map already (`graphAutoFitDone`, cleared by
//: switchTab on a fresh visit) and which node the pointer is over
//: (`graphHoveredId`, read by the node popup). The tab's
//: surface writes through to both; a pane keeps them to itself, so hovering a
//: note in the pane cannot light a node up on the tab behind it.
function gcAutoFitDone(s) {
  return s.size === "full" ? graphAutoFitDone : s.autoFitDone;
}

function gcSetAutoFitDone(s, value) {
  if (s.size === "full") graphAutoFitDone = value;
  else s.autoFitDone = value;
}

//: Which node the keyboard is on. `graphKeyboardId` is driven by the Graph
//: tab's own arrow-key handler, so it means nothing on a pane and must not
//: draw a focus ring there on whichever note happens to share the id.
function gcKeyboardId(s) {
  return s.size === "full" ? graphKeyboardId : null;
}

function gcSetHovered(s, id) {
  s.hoveredId = id;
  if (s.size === "full") graphHoveredId = id;
}

//: **The tab's state under its old names**, for graph.js's renderer-agnostic
//: helpers and for the sweeps in `scratchpad/ui-sweeps/`, both of which read
//: `gcNodes`, `gcTransform`, `gcSelected` and friends as bare globals. They
//: were module-level `let`s until the surface object above; these getters keep
//: every one of those readers working, and read-only, against the tab.
for (const [name, prop] of [
  ["gcNodes", "nodes"],
  ["gcEdges", "edges"],
  ["gcAdj", "adj"],
  ["gcById", "byId"],
  ["gcCanvas", "canvas"],
  ["gcCtx", "ctx"],
  ["gcDims", "dims"],
  ["gcTransform", "transform"],
  ["gcSelected", "selected"],
  ["gcLasso", "lasso"],
  ["gcColourOf", "colourOf"],
  ["gcTimeCutoff", "timeCutoff"],
  ["gcLayoutKind", "layoutKind"],
  ["graphHiddenIds", "hiddenIds"],
]) {
  Object.defineProperty(window, name, { configurable: false, get: () => gcTab[prop] });
}


//: The app's colour tokens, read once per render. One document, one theme,
//: so every surface reads the same ones.
let gcTokens = {};

//: Node radius, GRAPH_PLAN.md §5 Phase 1: `4 + 2*sqrt(degree)`, clamped to
//: [4, 18]. Degree is counted client-side from the edges until Phase 5 sends
//: it on the payload. The SVG renderer sized by PageRank centrality instead,
//: which is a number the reader cannot verify by looking, degree is "how many
//: lines come out of this dot", which is the one thing a graph makes visible.
//: The busiest note's link count, which `graphSizeRadius` scales against.
function gcMaxDegree(s, nodes) {
  let max = 0;
  for (const node of nodes) if (!node.isGroup) max = Math.max(max, (s.adj.get(node.id) || { size: 0 }).size);
  return max;
}
//: **One size scale, [5, 15]** (INBOX 443 (1), "a few large nodes with glow
//: halos"; was [4, 18]). The busiest note drew at 18 beside a leaf at 6.5 and
//: an unlinked note at 4, which put the biggest dot at nine times the
//: smallest one's area; now the biggest is five times it (15 against 6.5 and
//: 5), still plainly the hub, no longer a blob that its own glow doubled.
const GC_MIN_RADIUS = 5;
const GC_MAX_RADIUS = 15;
//: How far past a dot's edge a press still counts as on it, in screen pixels. A
//: finger gets 20 (audit 1029 G13): with the smallest dot that is a 44px target,
//: the floor; the nearest dot within it wins (`gcTreeIndex().find`).
const GC_SLOP_PX = window.matchMedia?.("(pointer: coarse)")?.matches ? 20 : 6;
function gcRadius(node, degree, maxDegree = 0) {
  if (node.isGroup) return node.id === "root" ? 14 : 11;
  //: By the View menu's Size rule (`graphSizeRadius`, graph.js): connections
  //: by default, the rule this function always drew.
  return graphSizeRadius(node, degree, GC_MIN_RADIUS, GC_MAX_RADIUS, maxDegree);
}

//: Zoom at which labels come on by themselves (§5 Phase 1). Below it a label
//: is unreadable anyway and 2,000 of them are a grey wash; above it there is
//: room for them. A hovered or spotlit node always shows its own.
const GC_LABEL_ZOOM = 1.4;

//: Below this radius on screen, in device pixels, a node is drawn as a plain
//: dot in a batched path rather than as its sprite (see the node pass in
//: `gcDraw`): its rim and glow are a pixel or less there.
const GC_LOD_PX = 4;

//: How far, in screen pixels, a press on a node has to travel before it is a
//: drag rather than a click (INBOX 587; see the drag handlers in
//: `gcWireInteraction`). Three is the usual slop for a mouse and a finger alike.
const GC_DRAG_THRESHOLD_PX = 3;
const GC_LABEL_ALL_MAX = 400;
//: How many search hits are still few enough to be answers rather than a
//: filter, and so are drawn even where they overlap something already there.
//: See the label pass in `gcDraw` for what happens past it.
const GC_LABEL_FORCE_MAX = 12;
//: **Landmarks** (`scratchpad/ui-sweeps/graphlabels.js`). Below the zoom gate
//: on a map past GC_LABEL_ALL_MAX, the best-connected notes in view still get
//: their names, up to this many and only where there is room: a map is read
//: by its hubs, and on the 417-note fixture the fitted map drew no label at
//: all, so its overview named nothing. A dozen is what a 1440 window holds at
//: the fit without the names turning into the grey wash the gate exists for.
const GC_LABEL_LANDMARKS = 12;
//: Of those, how many of the best-connected in view may be named over another
//: dot when nowhere else is free; see the label pass in `gcDraw`.
const GC_LABEL_LANDMARK_HUBS = 10;
//: **Every name only on a small map** (owner, 0.3.31: "the labels on the
//: graph are a bit much", a 35-note map named every dot at the fit). Past
//: this many notes the fitted overview names its best-connected third (the
//: landmarks pass, `GC_LABEL_LANDMARK_SHARE`), and zooming past
//: GC_LABEL_ZOOM, hovering or searching still names the rest.
const GC_LABEL_ALL_SMALL = 20;
const GC_LABEL_LANDMARK_SHARE = 0.35;
//: A note with this many links is a hub, named at the overview of a grouped
//: map besides each category's best-connected note (INBOX 693).
const GC_LABEL_HUB_DEGREE = 5;
const GC_LABEL_NARROW_W = 600;
const GC_LABEL_NARROW_CUT = 14;
//: How far a non-neighbour dims while something is hovered (§5 Phase 1).
const GC_DIM_ALPHA = 0.2;

//: Every colour comes from the app's tokens (§6). Read off the canvas element
//: rather than `:root` so whatever cascade actually applies, theme, a user
//: theme, the dark-mode block, is the one that answers.
function gcReadTokens(s = gcTab) {
  const style = getComputedStyle(s.canvas || document.documentElement);
  const get = (name, fallback) => (style.getPropertyValue(name) || "").trim() || fallback;
  gcTokens = {
    muted: get("--muted", "#8b93a7"),
    accent: get("--accent", "#4f7cff"),
    error: get("--error", "#d2453c"),
    ok: get("--ok", "#2f9e6b"),
    warn: get("--warn", "#c98a17"),
    ink: get("--ink", "#1b1f2a"),
    card: get("--card", "#ffffff"),
    font: get("--font-sans", "system-ui, sans-serif"),
    //: The hover's two durations are the stylesheet's motion tokens (Brief
    //: 100, DESIGN.md "Motion"), so the canvas eases with the rest of the
    //: app and is instant where the app's interface animations are off.
    fadeMs: gcMs(get("--ui-slow", "0.2s")),
    hoverMs: gcMs(get("--ui-slow", "0.2s")),
  };
}

//: A CSS time ("0.16s", "120ms") in milliseconds.
function gcMs(value) {
  const n = parseFloat(value);
  if (!Number.isFinite(n)) return 0;
  return /ms\s*$/.test(value) ? n : n * 1000;
}

//: **Less motion, by every switch that means it** (Brief 100): the system's
//: setting, and the app's own Reduce motion and Performance mode
//: (`data-motion`, settings.js). The canvas read only the first, so the app's
//: switch left the map easing while the rest of the page stood still.
function gcStill() {
  return Boolean(
    window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ||
      document.documentElement?.dataset?.motion === "reduced"
  );
}

//: The edge recipes, transcribed from `.graph-edge*` in
//: css/02-chat-graph.css and `.graph-edge-filing` in
//: css/06-timeline-dialogs.css. Transcribed rather than read back out of the
//: cascade because a canvas has no elements to ask: there is no
//: `.graph-edge-similar` in the DOM to run `getComputedStyle` against. The
//: colours still come from tokens (above), so a theme change moves both.
const GC_EDGE_STYLES = {
  link: { width: 1.3, alpha: 0.4, dash: null, colour: "muted" },
  thread: { width: 1.4, alpha: 0.55, dash: [7, 4], colour: "muted" },
  similar: { width: 1.2, alpha: 0.55, dash: [2, 5], colour: "accent" },
  map: { width: 1.3, alpha: 0.7, dash: [1, 4], colour: "accent" },
  filing: { width: 1.6, alpha: 0.25, dash: [3, 3], colour: "muted" },
  entity: { width: 1.6, alpha: 0.55, dash: null, colour: "muted" },
  //: KG5: two entities named together in two notes or more.
  comention: { width: 1.2, alpha: 0.45, dash: [1, 3], colour: "accent" },
  document: { width: 1.6, alpha: 0.55, dash: null, colour: "muted" },
  tagged: { width: 1.1, alpha: 0.4, dash: [2, 3], colour: "muted" },
  attachment: { width: 1.2, alpha: 0.45, dash: null, colour: "muted" },
  unresolved: { width: 1, alpha: 0.3, dash: [3, 4], colour: "muted" },
};
//: Nodes that are not notes (GRAPH_PLAN 514 adds tags, files and unwritten
//: [[names]]): never opened in the popup, ringed in their own dash.
const GC_KIND_DASH = { entity: [3, 2], document: [1, 3], tag: [4, 2], attachment: [1, 3], unresolved: [2, 2] };
function gcIsNote(node) {
  return !node.isGroup && !GC_KIND_DASH[node.type];
}
//: **A link between two notes of one colour takes that colour** (INBOX 443
//: (1), the owner: "the graph shape could look nicer"; the edges were all one
//: blue-grey). The line inside a category now says which category it is in, so
//: the clusters read as clusters before a label does, and the neutral grey
//: lines are left to mean what they should: a bridge between two. Bucketed by
//: colour, so the stroke state is still set once per colour (five categories
//: is five buckets, not five hundred strokes). The kinds that are not a
//: relation between two notes of a colour (a similarity, a board's reference,
//: a filing line, a contradiction) keep their own recipe. The number is the
//: least opacity a tinted line of that kind is drawn at.
const GC_EDGE_TINTED = { link: 0.55, thread: 0.6, entity: 0.55, document: 0.55 };
//: A line between two category clusters, while grouped: this much of its
//: kind's width and opacity (the line pass in `gcDraw`, INBOX 693).
const GC_CROSS_WIDTH = 0.65;
const GC_CROSS_ALPHA = 0.5;
//: **A hub's spokes are straight and quiet** (INBOX 1400 and 1306, the owner:
//: "a brown hub with many crossing edges", "feels very messy"). On the 36-note
//: seed one note held 24 of 64 links and 39 of 64 crossings, its spokes drawn
//: as 24 bows fanning across every cluster. A note is a hub at
//: `gcHubSpokeMin` links (three times the map's mean, never under
//: `GC_HUB_SPOKES`); its lines run straight, so they read as rays from one
//: place, and a ray to another category is drawn at `GC_HUB_SPOKE_ALPHA` of
//: the quiet bridge, until the pointer is on the hub or its far end.
const GC_HUB_SPOKES = 8;
const GC_HUB_SPOKE_ALPHA = 0.55;
function gcHubSpokeMin(degrees) {
  const list = Array.from(degrees || []).filter((d) => Number.isFinite(d));
  if (!list.length) return Infinity;
  const mean = list.reduce((a, b) => a + b, 0) / list.length;
  return Math.max(GC_HUB_SPOKES, Math.ceil(mean * 3));
}
// GRAPH-SIM-BEGIN
//: **Similarity is a backbone, not every pair** (INBOX 412, the owner: "when
//: I tick similarity on the graph, this happens, is there a way to make it
//: more visually understandable or parsable??"). Measured on a 42-note
//: notebook with vectors shaped like bge-small's: the server sent its cap of
//: 200 similarity lines against 24 links, up to 20 on one note, every one the
//: same dotted blue, and their springs pulled six topics into one ball with
//: 1,701 crossings. An embedding model scores almost everything in a notebook
//: as a little alike, so "above a cutoff" is most pairs.
//:
//: What the tools that draw weighted networks for a living do, read before
//: this was written: Gephi and InfraNodus thin by weight before drawing and
//: then map the weight onto the stroke (thickness, opacity); Kumu scales a
//: connection's width by its strength and focuses a selection's
//: neighbourhood; Obsidian and Logseq fade everything a hovered note is not
//: joined to; Heptabase does not draw inferred relations at all and lists
//: them beside the card instead. The fit here is the first two plus the
//: fade that was already on this map: each note keeps its `k` closest
//: matches (a k-nearest-neighbour graph: a line survives if it is one of the
//: k strongest of *either* end, so a note that is nobody's favourite still
//: shows its own two), graded by score, beneath the links.
//:
//: `k` is 2 (GRAPH_PLAN, "Decisions made, 2026-09-24"): measured on the same
//: notebook, 2 left 58 lines and 39 crossings, 3 left 80 lines and 84
//: crossings; both kept the six topics apart, so the fewer lines win.
const GC_SIM_TOP_K = 2;
//: The server's own floor (`SIMILARITY_EDGE_THRESHOLD` in routes_graph.py):
//: the slider starts here, which means "no extra cutoff".
const GC_SIM_FLOOR = 0.55;

function gcPruneSimilarity(edges, options = {}) {
  const k = options.k == null ? GC_SIM_TOP_K : options.k;
  const threshold = options.threshold == null ? GC_SIM_FLOOR : options.threshold;
  const endId = (end) => (end && end.id != null ? end.id : end);
  const byNote = new Map();
  const eligible = [];
  edges.forEach((edge, index) => {
    if (edge.kind !== "similar") return;
    // A line with no score cannot be graded, and drawing it at full strength
    // would make the one line nothing is known about the loudest.
    if (typeof edge.score !== "number" || !(edge.score >= threshold)) return;
    eligible.push(index);
    for (const end of [endId(edge.source), endId(edge.target)]) {
      if (!byNote.has(end)) byNote.set(end, []);
      byNote.get(end).push(index);
    }
  });
  const keep = new Set();
  for (const indices of byNote.values()) {
    // Strongest first; a tie goes to the line listed first, so the same
    // notebook always draws the same lines.
    indices.sort((a, b) => edges[b].score - edges[a].score || a - b);
    for (const index of indices.slice(0, k)) keep.add(index);
  }
  return edges.filter((edge, index) => edge.kind !== "similar" || keep.has(index));
}

//: Three strengths, not a continuous ramp: the canvas strokes one batched
//: path per style, and three are enough for the eye to rank (a fourth step
//: of opacity at these levels is not seen). Graded against the range that is
//: actually drawn rather than against 0..1, because every model has its own
//: baseline: bge-small put this notebook's lines between 0.64 and 0.83, and
//: on an absolute scale all of them would have landed in one band.
//:
//: The strongest band stays below a link's own opacity, so a similarity line
//: never out-shouts a connection somebody made. One dash for all three: the
//: dash says "inferred", the weight says "how strongly".
const GC_SIMILAR_BANDS = [
  { width: 0.8, alpha: 0.16, dash: [4, 4], colour: "accent" },
  { width: 1.2, alpha: 0.28, dash: [4, 4], colour: "accent" },
  { width: 1.8, alpha: 0.42, dash: [4, 4], colour: "accent" },
];

function gcSimilarityBand(score, lo, hi) {
  if (!(hi > lo)) return 2;
  const t = Math.max(0, Math.min(1, (score - lo) / (hi - lo)));
  return t < 1 / 3 ? 0 : t < 2 / 3 ? 1 : 2;
}

//: **Labels do not land on labels or on other notes.** `items` are label
//: boxes in the order they should win space (world units, `force` set on the
//: ones drawn whatever they cover); `discs` are the drawn notes. A label that
//: covers another note's dot hides the dot, which is the one thing on the
//: map that is clickable. Measured before: 13 of 18 placed labels sat on a
//: dot. The dots go into a grid so a big map costs a few cell reads per
//: label rather than a scan of every note. `blocked` are boxes no label may
//: take at all (the topic plates, KG6), forced ones included where they can.
function gcPlaceLabels(items, discs, lineCount = null, blocked = [], bounds = null) {
  let cell = 0;
  for (const item of items) cell = Math.max(cell, item.bottom - item.top, 1);
  cell = Math.max(cell * 4, 1);
  const grid = new Map();
  for (const disc of discs) {
    const x0 = Math.floor((disc.x - disc.r) / cell);
    const x1 = Math.floor((disc.x + disc.r) / cell);
    const y0 = Math.floor((disc.y - disc.r) / cell);
    const y1 = Math.floor((disc.y + disc.r) / cell);
    for (let cx = x0; cx <= x1; cx++) {
      for (let cy = y0; cy <= y1; cy++) {
        const key = `${cx},${cy}`;
        if (!grid.has(key)) grid.set(key, []);
        grid.get(key).push(disc);
      }
    }
  }
  const coversDisc = (box) => {
    const x0 = Math.floor(box.left / cell);
    const x1 = Math.floor(box.right / cell);
    const y0 = Math.floor(box.top / cell);
    const y1 = Math.floor(box.bottom / cell);
    for (let cx = x0; cx <= x1; cx++) {
      for (let cy = y0; cy <= y1; cy++) {
        for (const disc of grid.get(`${cx},${cy}`) || []) {
          if (disc.id === box.id) continue;
          const nx = Math.max(box.left, Math.min(disc.x, box.right));
          const ny = Math.max(box.top, Math.min(disc.y, box.bottom));
          if ((nx - disc.x) ** 2 + (ny - disc.y) ** 2 < disc.r * disc.r) return true;
        }
      }
    }
    return false;
  };
  //: **A name is nearer its own dot than any other** (INBOX 1300 C41, the
  //: owner: "labels overlap nodes"; measured at the fit on the 57-note seed,
  //: 6 of 16 names stood nearer another note's dot, and so read as its
  //: name). A place where some other dot is closer than its own is no place.
  const own = new Map(discs.map((disc) => [disc.id, disc]));
  const edgeGap = (box, disc) => {
    const nx = Math.max(box.left, Math.min(disc.x, box.right));
    const ny = Math.max(box.top, Math.min(disc.y, box.bottom));
    return Math.max(0, Math.hypot(nx - disc.x, ny - disc.y) - disc.r);
  };
  const nearerOther = (box) => {
    const mine = own.get(box.id);
    if (!mine) return false;
    const reach = edgeGap(box, mine);
    const x0 = Math.floor((box.left - reach) / cell) - 1;
    const x1 = Math.floor((box.right + reach) / cell) + 1;
    const y0 = Math.floor((box.top - reach) / cell) - 1;
    const y1 = Math.floor((box.bottom + reach) / cell) + 1;
    for (let cx = x0; cx <= x1; cx++) {
      for (let cy = y0; cy <= y1; cy++) {
        for (const disc of grid.get(`${cx},${cy}`) || []) {
          if (disc.id !== box.id && edgeGap(box, disc) < reach) return true;
        }
      }
    }
    return false;
  };
  //: A place past the edge of the canvas is no place (INBOX 693: names "cut
  //: by the viewport"); `bounds` is the canvas in world units.
  const outside = (box) =>
    bounds !== null &&
    (box.left < bounds.left || box.right > bounds.right || box.top < bounds.top || box.bottom > bounds.bottom);
  const clashes = (box) => {
    if (outside(box)) return true;
    for (const list of [placed, blocked]) for (const other of list) {
      if (
        box.left < other.right &&
        box.right > other.left &&
        box.top < other.bottom &&
        box.bottom > other.top
      ) {
        return true;
      }
    }
    return false;
  };
  const placed = [];
  //: **A name never sits on a line when it has anywhere else to go** (INBOX
  //: 493, the owner's screenshot: "labels in white over the lines"). Of its
  //: places (built in `gcDraw`) that are free of every placed label and
  //: every other dot, the first that crosses no line wins; with none, the
  //: one crossing the fewest, earlier places breaking a tie. Without a line
  //: count that is the first free place, the rule this always had. The box
  //: moves there whole, so `labelBoxes` still says exactly where the text
  //: is, and the plate it is drawn on (`gcDrawLabels`) hides any line left
  //: beneath it.
  let fewest = Infinity;
  const best = (spots, ok) => {
    let pick = null;
    fewest = Infinity;
    for (const spot of spots) {
      if (!ok(spot)) continue;
      //: Past six lines a place is simply crowded; counting on would only
      //: rank two bad places, at a cost every frame.
      const lines = lineCount ? lineCount(spot, Math.min(fewest, 6)) : 0;
      if (lines === 0) {
        fewest = 0;
        return spot;
      }
      if (lines < fewest) {
        fewest = lines;
        pick = spot;
      }
    }
    return pick;
  };
  //: **Never on a dot, never on a line, when there is any choice** (INBOX
  //: 693, the owner's decision: "labels never over dots or lines").
  //: Measured on the showcase notebook at the fit (graph692.js), 3 to 7
  //: names sat on another note's dot and 5 to 14 had a line through them.
  //: Two things gave way:
  //: - a landmark (one of the best-connected notes) was let sit on a dot
  //:   (GRAPH_PLAN, decision of 2026-09-26, measured on a 417-note map whose
  //:   dense middle had no free place); the owner's newer decision ends the
  //:   waiver: a landmark with no place off every dot is left off at this
  //:   zoom like any other name, and zooming in gives it one. Room kept
  //:   clear for a hub's name by the layout was tried twice and rejected (a
  //:   lane beside each hub, then a box under it): at the overview a name is
  //:   about as wide as its cluster, so clearing room for it pulled the
  //:   clusters into streaks and the fit zoom from 0.77 to 0.48;
  //: - an ordinary name went to the place crossing the fewest lines; now a
  //:   name that would sit on a line is left off until the view gives it
  //:   room (zoom in, or point at the note: its name is drawn on hover
  //:   whatever it covers). Names asked for by name and landmarks still take
  //:   their least-crossed place, on the plate that hides the line under it
  //:   (`gcDrawLabels`), because an overview with no hub named is not
  //:   clearer.
  for (const box of items) {
    const spots = [box, ...(box.alts || []).map((spot) => ({ ...box, ...spot, alts: undefined }))];
    if (box.force) {
      //: Asked for by name: drawn whatever it lands on, at the clearest
      //: place that covers no label and no dot if there is one.
      placed.push(
        best(spots, (spot) => !clashes(spot) && !coversDisc(spot) && !nearerOther(spot)) ||
          best(spots, (spot) => !clashes(spot) && !coversDisc(spot)) ||
          gcClampBox(box, bounds)
      );
      continue;
    }
    const clear = (spot) => !clashes(spot) && !coversDisc(spot) && !nearerOther(spot);
    if (box.landmark) {
      const pick = best(spots, clear);
      if (pick) placed.push(pick);
      continue;
    }
    const pick = best(spots, clear);
    if (pick && fewest === 0) placed.push(pick);
  }
  return placed;
}
//: A box moved the least it must to lie inside `bounds` (a name asked for by
//: name, with nowhere clear to go, still reads whole at the canvas's edge).
function gcClampBox(box, bounds) {
  if (!bounds) return box;
  const dx = Math.max(0, bounds.left - box.left) - Math.max(0, box.right - bounds.right);
  const dy = Math.max(0, bounds.top - box.top) - Math.max(0, box.bottom - bounds.bottom);
  if (!dx && !dy) return box;
  return { ...box, x: box.x + dx, y: box.y + dy, left: box.left + dx, right: box.right + dx, top: box.top + dy, bottom: box.bottom + dy };
}
//: **The drawn links as a grid of short segments**, for `gcPlaceLabels` to
//: ask whether a name would sit on one. World units, so a zoom keeps it; it
//: is rebuilt only when a position, the link set or the curve switch moved
//: (the signature is one pass of additions over the dots, far cheaper than
//: the rebuild it saves on every hover frame of a settled map). A curved
//: link is cut into eight chords of its bow, a long straight one into
//: pieces no longer than a cell, and each piece is filed under the cells its
//: box touches.
const GC_LINE_CELL = 48;

function gcLineGrid(s, curved) {
  let sig = s.nodes.length * 7 + s.edges.length * 13 + (curved ? 1 : 0) + (s.timeCutoff || 0);
  for (const node of s.nodes) if (Number.isFinite(node.x)) sig += node.x * 1.618 + node.y;
  if (s.lineGrid && s.lineGrid.sig === sig) return s.lineGrid;
  const cells = new Map();
  const file = (ax, ay, bx, by) => {
    const x0 = Math.floor(Math.min(ax, bx) / GC_LINE_CELL);
    const x1 = Math.floor(Math.max(ax, bx) / GC_LINE_CELL);
    const y0 = Math.floor(Math.min(ay, by) / GC_LINE_CELL);
    const y1 = Math.floor(Math.max(ay, by) / GC_LINE_CELL);
    for (let cx = x0; cx <= x1; cx++) {
      for (let cy = y0; cy <= y1; cy++) {
        const key = cx * 100003 + cy;
        let list = cells.get(key);
        if (!list) cells.set(key, (list = []));
        list.push(ax, ay, bx, by);
      }
    }
  };
  for (const edge of s.edges) {
    const a = edge.source;
    const b = edge.target;
    if (!a || !b || !Number.isFinite(a.x) || !Number.isFinite(b.x)) continue;
    if (!gcVisibleAtTime(a, s) || !gcVisibleAtTime(b, s)) continue;
    let px = a.x;
    let py = a.y;
    if (curved) {
      const c = gcBowPoint(a, b);
      for (let i = 1; i <= 8; i++) {
        const u = i / 8;
        const x = (1 - u) * (1 - u) * a.x + 2 * (1 - u) * u * c.x + u * u * b.x;
        const y = (1 - u) * (1 - u) * a.y + 2 * (1 - u) * u * c.y + u * u * b.y;
        file(px, py, x, y);
        px = x;
        py = y;
      }
    } else {
      const n = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / GC_LINE_CELL));
      for (let i = 1; i <= n; i++) {
        const x = a.x + ((b.x - a.x) * i) / n;
        const y = a.y + ((b.y - a.y) * i) / n;
        file(px, py, x, y);
        px = x;
        py = y;
      }
    }
  }
  s.lineGrid = { sig, cells };
  return s.lineGrid;
}

//: How many filed segments pass through the box (a Liang-Barsky clip,
//: written out so a frame of a few hundred labels allocates nothing),
//: counting no further than `limit`: the caller only wants to know whether a
//: place beats the best one so far. A segment filed under two cells the box
//: spans counts once per cell, which only makes a crowded place look more so.
function gcClipEdge(p, q, t) {
  if (p === 0) return q >= 0;
  const r = q / p;
  if (p < 0) {
    if (r > t[1]) return false;
    if (r > t[0]) t[0] = r;
  } else {
    if (r < t[0]) return false;
    if (r < t[1]) t[1] = r;
  }
  return true;
}
const gcClipT = [0, 1];
function gcBoxLineCount(grid, box, limit = Infinity) {
  let count = 0;
  const x0 = Math.floor(box.left / GC_LINE_CELL);
  const x1 = Math.floor(box.right / GC_LINE_CELL);
  const y0 = Math.floor(box.top / GC_LINE_CELL);
  const y1 = Math.floor(box.bottom / GC_LINE_CELL);
  const t = gcClipT;
  for (let cx = x0; cx <= x1; cx++) {
    for (let cy = y0; cy <= y1; cy++) {
      const list = grid.cells.get(cx * 100003 + cy);
      if (!list) continue;
      for (let i = 0; i < list.length; i += 4) {
        const ax = list[i];
        const ay = list[i + 1];
        const dx = list[i + 2] - ax;
        const dy = list[i + 3] - ay;
        t[0] = 0;
        t[1] = 1;
        if (
          gcClipEdge(-dx, ax - box.left, t) &&
          gcClipEdge(dx, box.right - ax, t) &&
          gcClipEdge(-dy, ay - box.top, t) &&
          gcClipEdge(dy, box.bottom - ay, t)
        ) {
          count += 1;
          if (count >= limit) return count;
        }
      }
    }
  }
  return count;
}

//: Where a score pill goes on a line from the note in focus (`a`) to one of
//: its matches (`b`): the first spot along the line, nearer the match than
//: the middle so the number reads as belonging to that note, where the pill
//: covers no label, no other pill and no dot. Measured first at the middle
//: of every line: on a fitted 42-note map, six pills around one note piled
//: onto each other and onto two labels, because lines to close matches are
//: short. `t` is the fraction of the way from `a` to `b`. When nowhere is
//: free the answer says so (`placed: false`) and the caller leaves that pill
//: out rather than stacking it: every score is also in the note's tooltip
//: (`gcTooltip`), which has room for all of them, and a pile of overlapping
//: pills was the measured failure this exists to prevent (10 overlaps among
//: six pills at the fitted zoom). Zooming in makes the room.
const GC_PILL_STOPS = [0.62, 0.5, 0.74, 0.38, 0.84, 0.28];

function gcPlacePill(a, b, w, h, boxes, discs) {
  const free = (box) => {
    for (const other of boxes) {
      if (box.left < other.right && box.right > other.left && box.top < other.bottom && box.bottom > other.top) {
        return false;
      }
    }
    for (const disc of discs) {
      const nx = Math.max(box.left, Math.min(disc.x, box.right));
      const ny = Math.max(box.top, Math.min(disc.y, box.bottom));
      if ((nx - disc.x) ** 2 + (ny - disc.y) ** 2 < disc.r * disc.r) return false;
    }
    return true;
  };
  const at = (stop) => {
    const x = a.x + (b.x - a.x) * stop;
    const y = a.y + (b.y - a.y) * stop;
    return { x, y, left: x - w / 2, right: x + w / 2, top: y - h / 2, bottom: y + h / 2 };
  };
  for (const stop of GC_PILL_STOPS) {
    const box = at(stop);
    if (free(box)) return { ...box, placed: true };
  }
  return { ...at(0.5), placed: false };
}
// GRAPH-SIM-END

//: The Similarity cutoff slider (`#graph-similarity-min`, 55 to 95), as a
//: score. Read from storage rather than the control so a pane beside a note,
//: which has no slider, draws the same lines the tab does.
function gcSimilarityCutoff() {
  let stored = null;
  try {
    stored = prefs.get("graph-similarity-min", null);
  } catch (error) {
    stored = null;
  }
  const value = Number(stored);
  if (!stored || !Number.isFinite(value)) return GC_SIM_FLOOR;
  return Math.max(GC_SIM_FLOOR, Math.min(0.95, value / 100));
}

const GC_EDGE_REASONED = { width: 1.9, alpha: 0.62, dash: null, colour: "accent" };
const GC_EDGE_CONTRADICTS = { width: 2.2, alpha: 0.85, dash: [6, 4], colour: "error" };

//: **Curved links are the default** (INBOX 443 (1), the owner: "the graph
//: shape could look nicer"; the lines were straight). Read from the switch
//: itself, like the labels, so what the menu shows and what is drawn cannot
//: disagree (the owner: "it is showing curved links even when it is visibly
//: off??"); the stored value only stands in for a pane, which has no switch,
//: and a notebook that never touched it is on.
function gcCurvedLinks(s = gcTab) {
  const box = s.size === "full" ? gcEl("graph-curved") : null;
  return box ? box.checked : prefs.get("graph-curved", null) !== "0";
}

//: A quadratic curve bowed to one side by a seventh of its length (48px at
//: most), the side chosen by the endpoints' ids so the same link bows the
//: same way whichever end the simulation lists first, and a link that is
//: drawn twice (both directions) lands on itself. Shared by the paint and the
//: pointer's hit test, which has to find the line where it is drawn.
//: Label backgrounds (the owner: "can we make the dark background behind the
//: graph labels togglable??"): on by default, read like Curved links.
function gcLabelPlates(s = gcTab) {
  const box = s.size === "full" ? gcEl("graph-label-plates") : null;
  return box ? box.checked : prefs.get("graph-label-plates", null) !== "0";
}

//: Text fade (GRAPH_PLAN 514 (5)): the zoom past which a big map names every
//: note, 2.6 at the left to 0.2 at the right, GC_LABEL_ZOOM at 50.
function gcLabelZoom() {
  const v = Number(gcEl("graph-label-fade")?.value ?? prefs.get("graph-label-fade", null) ?? 50);
  return 2.6 - 0.024 * (Number.isFinite(v) ? v : 50);
}

//: Link thickness: 0.4x at the left, 1x at 50, 2.2x at the right.
function gcLinkWidth() {
  const v = Number(gcEl("graph-link-width")?.value ?? prefs.get("graph-link-width", null) ?? 50);
  const at = Number.isFinite(v) ? v : 50;
  return at <= 50 ? 0.4 + (0.6 * at) / 50 : 1 + (1.2 * (at - 50)) / 50;
}

function gcArrows(s = gcTab) {
  const box = s.size === "full" ? gcEl("graph-arrows") : null;
  return box ? box.checked : prefs.get("graph-arrows", null) === "1";
}

//: **A line between two categories is straight** (INBOX 693, the owner:
//: "cross-cluster links drawn short, straight or one gentle bend ... no long
//: arcs spanning the canvas"): while notes gather by category (`_cluster`,
//: set in `renderGraphCanvas`), its bow is its midpoint, so every caller
//: (paint, hover, hit test, the label pass's line grid) draws and finds it
//: straight. The worker's `clearCurve` makes the same exception.
//: `out` and `side` are the draw loop's (Brief 100: no allocation per edge per
//: frame on a 2,000-note map): a scratch point written in place, and the side
//: the edge keeps for its render. Every other caller gets a fresh point.
function gcBowPoint(a, b, out = null, side = null) {
  const point = out || { x: 0, y: 0 };
  if (a._straight || a._hub || b._hub || (a._cluster != null && a._cluster !== b._cluster)) {
    point.x = (a.x + b.x) / 2;
    point.y = (a.y + b.y) / 2;
    return point;
  }
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const bow = Math.min(len * 0.14, 48) * (side || (String(a.id) < String(b.id) ? 1 : -1));
  point.x = (a.x + b.x) / 2 - (dy / len) * bow;
  point.y = (a.y + b.y) / 2 + (dx / len) * bow;
  return point;
}

//: An edge's look for one render (Brief 100): its recipe, its tint, its
//: confidence and its quiet cross-cluster variant depend on the render's
//: colours and similarity range, not on the frame, so they are worked out
//: once per render (`s.epoch`) rather than spread into new objects for every
//: edge on every frame of a hover fade. `_keys` holds each bucket key as it
//: is first needed, so a frame builds no strings either.
const gcBowScratch = { x: 0, y: 0 };
function gcEdgeLook(edge, a, b, simLo, simHi, epoch) {
  edge._styleEpoch = epoch;
  edge._keys = [];
  edge._side = String(a.id) < String(b.id) ? 1 : -1;
  const similar = edge.kind === "similar" && typeof edge.score === "number";
  edge._similar = similar;
  let style = similar ? GC_SIMILAR_BANDS[gcSimilarityBand(edge.score, simLo, simHi)] : gcEdgeStyle(edge);
  //: Same colour at both ends: the line wears it (see GC_EDGE_TINTED).
  const tint =
    !similar && edge.link_type !== "contradicts" && GC_EDGE_TINTED[edge.kind] && a.colour && a.colour === b.colour
      ? a.colour
      : null;
  if (tint) style = { ...style, alpha: Math.max(style.alpha, GC_EDGE_TINTED[edge.kind]) };
  //: How sure, as thickness and strength (INBOX 693, the legend's second
  //: channel): a reason the app deduced (`reason_confidence`, 0 to 1)
  //: draws its link from 0.6x to 1.2x, so a guess reads lighter than a
  //: reason in someone's words, which keeps its full line.
  if (edge.kind === "link" && typeof edge.reason_confidence === "number") {
    const sure = 0.6 + 0.6 * Math.max(0, Math.min(1, edge.reason_confidence));
    style = { ...style, width: style.width * sure, alpha: Math.min(1, style.alpha * sure) };
  }
  edge._tint = tint;
  edge._style = style;
  //: Quiet between two categories in every Force shape (INBOX 1300 C41:
  //: bridges drew at 0.40 beside 0.55 inside a category, and a long one
  //: through a cluster read as part of it); Clusters' own rule is the same.
  edge._cross =
    edge.link_type !== "contradicts" &&
    ((a._cluster != null && a._cluster !== b._cluster) ||
      (a._bridgeCat != null && b._bridgeCat != null && a._bridgeCat !== b._bridgeCat));
  edge._quietStyle = edge._cross
    ? { ...style, width: style.width * GC_CROSS_WIDTH, alpha: style.alpha * GC_CROSS_ALPHA * (a._hub || b._hub ? GC_HUB_SPOKE_ALPHA : 1) }
    : style;
}

function gcEdgeStyle(edge) {
  if (edge.link_type === "contradicts") return GC_EDGE_CONTRADICTS;
  if (edge.kind === "link" && edge.reason) return GC_EDGE_REASONED;
  return GC_EDGE_STYLES[edge.kind] || GC_EDGE_STYLES.link;
}

// --- the surface, sized for the device ----------------------------------------

//: DPR-aware sizing. A canvas has two sizes, the CSS box and the pixel
//: buffer: and getting that wrong is the single most common way a canvas
//: renderer ships blurry. The buffer is the box times the device pixel ratio,
//: and every draw starts by scaling the context by the same number so the
//: drawing code can go on thinking in CSS pixels.
function gcResize(s = gcTab, rect = null) {
  if (!s.canvas) return false;
  const box = document.getElementById(s.boxId);
  //: `rect` is the observer entry's content box: the observer fires after
  //: other observers' writes, where `clientWidth` paid a style pass (9 to 31ms
  //: measured on 2,000 notes); the entry carries the size already.
  const cw = rect ? Math.round(rect.width) : box ? box.clientWidth : 0;
  const ch = rect ? Math.round(rect.height) : box ? box.clientHeight : 0;
  //: **A box with no size is folded, not small** (the owner, 2026-10-10: "I
  //: collapsed and opened the local map and the stuff disappeared??"). The
  //: local map's body collapses to nothing; this read that as the 800x540
  //: fallback, the observer framed the map for a box that size (k 0.48 to
  //: 1.16, the middle at 294,189 of a 226x176 canvas) and nothing put it back
  //: on the way open, so every note was off the canvas. A drawn map keeps
  //: the size it last had while its box is folded or hidden; the fallback is
  //: for a box never measured.
  if (box && s.dims.w && (!cw || !ch)) return false;
  const width = cw || 800;
  const height = ch || 540;
  const dpr = window.devicePixelRatio || 1;
  if (width === s.dims.w && height === s.dims.h && dpr === s.dpr) return false;
  s.dims = { w: width, h: height };
  //: Whether this size was read off a laid-out box, not the fallback for one
  //: never measured (a map drawn while its tab is hidden): the resize
  //: observer reframes a fallback-sized map at once instead of gliding.
  s.dimsReal = Boolean(cw && ch);
  s.dpr = dpr;
  s.canvas.width = Math.max(1, Math.round(width * dpr));
  s.canvas.height = Math.max(1, Math.round(height * dpr));
  s.canvas.style.width = `${width}px`;
  s.canvas.style.height = `${height}px`;
  //: graph.js's camera helpers (`fitGraphToView`, the zoom strip, the minimap)
  //: read the tab's size from `graphDims`. A pane must not move it under them.
  if (s.size === "full") graphDims = { w: width, h: height };
  return true;
}

function gcEnsureCanvas(s = gcTab) {
  if (s.canvas) return s.canvas;
  s.canvas = document.getElementById(s.canvasId);
  if (!s.canvas) return null;
  //: **Not `desynchronized`.** The performance pass (2026-09-27) turned it on
  //: and measured the settle on a software-rendered sandbox: 937 to 1,091ms
  //: of main thread a second down to 97 to 163, the copy of the canvas into
  //: each compositor frame skipped. On the owner's GPU window it painted the
  //: map's transparent background black, and it came back only while a menu
  //: over the map forced ordinary compositing (INBOX 430, with screenshots):
  //: a low-latency canvas is handed to the screen as an opaque overlay, so
  //: its alpha never meets the page behind it. A visible fault beats a CPU
  //: figure from a machine with no GPU, so it is off; the settle cost on a
  //: software-only machine is back to what it was.
  s.ctx = s.canvas.getContext("2d");
  s.transform = d3.zoomIdentity;
  gcResize(s);
  // The card resizes for reasons no `resize` event fires for: the sidebar
  // opening, the legend collapsing, fullscreen. A ResizeObserver is the only
  // thing that sees all of them (§5 Phase 1 asks for one by name).
  if (!s.observer && typeof ResizeObserver !== "undefined") {
    s.observer = new ResizeObserver((entries) => {
      //: A tab flip folds the box to 0x0: the entry says so, and reading
      //: `clientWidth` in `gcResize` made the flip pay a style pass here.
      const own = entries.find((entry) => entry.target.id === s.boxId);
      if (own && !own.contentRect.width && s.dims.w) return;
      const before = { ...s.dims };
      const wasReal = s.dimsReal !== false;
      if (!gcResize(s, own?.contentRect)) {
        if (entries.some((entry) => entry.target.id !== s.boxId && !entry.target.matches(GC_FIT_MENUS))) gcRefitForPanels(s);
        return;
      }
      //: **The map stays framed when its card changes size** (INBOX 613, the
      //: owner: "the graph doesn properly fit to the area and showing or not
      //: showing panels"). A camera nobody has moved is framed again; one the
      //: person moved keeps its middle in the middle, so a panel opening or
      //: closing beside it never leaves the map off to one side.
      if (s.zoom && s.svg && before.w && before.h && s.nodes?.length) {
        if (!s.userZoomed && s.size === "full" && wasReal && !graphAutoFitOn()) s.userZoomed = true;
        //: A tree, radial or arc is framed by `frameTree`, as on first draw;
        //: the force fit read the arc's dots alone and overshot (1920x1080).
        if (!s.userZoomed && s.tree) frameTree(s.svg, s.zoom, gcTreeFrameNodes(s.tree, s.nodes), s.dims.w, s.dims.h, s.tree.radial, s.tree.arc, !wasReal);
        else if (!s.userZoomed) fitGraphToView(s.svg, s.zoom, s.nodes, s.dims.w, s.dims.h, !wasReal);
        else s.svg.call(s.zoom.translateBy, (s.dims.w - before.w) / 2 / s.transform.k, (s.dims.h - before.h) / 2 / s.transform.k);
      }
      gcRequestDraw(s);
    });
    const box = document.getElementById(s.boxId);
    if (box) s.observer.observe(box);
    if (s.size === "full") for (const el of document.querySelectorAll(GC_FIT_OVERLAYS.join(","))) s.observer.observe(el);
  }
  gcWireInteraction(s);
  return s.canvas;
}

// --- hovering a node -----------------------------------------------------------
//: Asked for: "can you make graph nodes temporarily expand to fill their glow
//: bubble when I hover over them or smth?? I feel like the graph nodes could
//: look slightly nicer, cooler, more professional and more modern. visually".
//:
//: Every node is already drawn with a halo 6px outside its core, and until now
//: the only thing hovering one changed was a ring around it. The dot now grows
//: out to that halo and the halo steps a little further out and brightens, so
//: the glow stays a glow around the node rather than something the node has
//: swallowed.
//:
//: **Animated here rather than in CSS.** The SVG renderer could do this with a
//: `:hover` rule; this one paints to a canvas, which has no elements to hover
//: and no transitions. So the eased value is held as one number and the draw
//: loop is asked for frames only while it is moving: `gcHoverFrom`/`gcHoverTo`
//: name the node it is leaving and the node it is entering, and both are
//: eased, so moving the pointer straight from one node to the next shrinks the
//: first while the second grows instead of snapping.
//:
//: The cost is bounded by construction: at most two nodes are ever mid-ease,
//: the animation is 140ms, and when nothing is easing `gcHoverEase` is exactly
//: 1 and no frames are requested at all.
//: **Toned down after the first version was shown.** The owner: "the halo
//: growth on the nodes is a bit visually jarring tbh". It was the full 6, so
//: the smallest nodes jumped 67% wider in 140ms while their halo pushed out
//: another 3 and brightened by half again: three things moving at once, and
//: the smaller the node the louder it read. Half the distance, half the light
//: and a little longer to travel it keeps the gesture (the node comes forward
//: under the pointer) without the pop.
//: **A node is a sprite, not three arcs.** The owner on the flat discs with
//: a halo ring: "the visual part of the main graph design needs a better
//: look", and on a first attempt with a highlight dot: "makes it look like a
//: bowling ball". So: one soft radial fill per node (a little lighter at the
//: centre, the category colour at the edge, no dot), a one-pixel rim a shade
//: darker than the fill so the disc has an edge against any background, and
//: a glow outside it that is wide and faint for a hub and narrow for a leaf.
//: Drawn once per colour and size into an offscreen canvas at the current
//: zoom and pixel ratio, then `drawImage`d, which is what keeps a
//: two-thousand-node map inside the frame budget: a radial gradient per node
//: per frame would not be.
const gcSpriteCache = new Map();

function gcHexToRgb(colour) {
  const m = /^#([0-9a-f]{6})$/i.exec(String(colour || "").trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

//: **The node itself** (Brief 100 (c), the owner: "improve the visual look
//: of nodes (keep the glow the same). just change the nodes themnselves").
//: Still flat in spirit (a gradient body read as "fake or too realistic", a
//: highlight dot as "a bowling ball"): the category colour with the faintest
//: shade across it, 8% lighter at the upper left to 8% deeper at the far
//: edge, which gives the disc a surface without a light source, and a crisp
//: one-pixel rim a quarter deeper in its own colour, so a dot on a dot or on
//: a line keeps its edge. A colour that is not a hex code keeps the flat
//: disc. The glow, drawn before this, is untouched.
function gcMixRgb(rgb, toward, share) {
  return `rgb(${rgb.map((v) => Math.round(v + (toward - v) * share)).join(", ")})`;
}
//: **The rim must clear 3:1 on a light ground** (audit 1029 G12/G21): the
//: automatic colours (Tableau, Set3) are 1.0 to 2.7 against the map's ground as
//: a disc, so the thin edge is the part that reads, and a quarter deeper left
//: the palest at 1.9. Half deeper puts the worst of the 22 at 3.8 (3.0 sampled off the painted sprite at 45%). A dark ground
//: (or a card token this cannot read) keeps the quarter.
function gcRimShare() {
  const ground = gcHexToRgb(gcTokens.card);
  return ground && ground[0] * 0.299 + ground[1] * 0.587 + ground[2] * 0.114 > 160 ? 0.5 : 0.25;
}

function gcPaintCore(c, half, r, colour) {
  const rgb = gcHexToRgb(colour);
  c.beginPath();
  c.arc(half, half, r, 0, Math.PI * 2);
  if (!rgb || r < 3) {
    c.fillStyle = colour;
    c.fill();
    return;
  }
  const shade = c.createRadialGradient(half - r * 0.35, half - r * 0.35, 0, half, half, r);
  shade.addColorStop(0, gcMixRgb(rgb, 255, 0.08));
  shade.addColorStop(0.6, colour);
  shade.addColorStop(1, gcMixRgb(rgb, 0, 0.08));
  c.fillStyle = shade;
  c.fill();
  c.beginPath();
  c.arc(half, half, r - 0.5, 0, Math.PI * 2);
  c.lineWidth = 1;
  c.strokeStyle = gcMixRgb(rgb, 0, gcRimShare());
  c.stroke();
}

function gcNodeSprite(colour, radiusPx, hub) {
  const r = Math.max(2, Math.round(radiusPx));
  const key = `${colour}|${r}|${hub ? 1 : 0}|${gcTokens.card}`;
  let sprite = gcSpriteCache.get(key);
  if (sprite) return sprite;
  if (gcSpriteCache.size > 600) gcSpriteCache.clear();
  //: Flat, like every other mark in the app (DESIGN.md: one fill, one edge,
  //: no rendered light): the category colour as a disc (shaded a breath by
  //: `gcPaintCore`, Brief 100 (c)), a ring in the
  //: card's own colour so a node reads clear of the links it sits on, and
  //: for a hub only, a soft bloom of its colour behind it. A gradient body
  //: was tried and read as "fake or too realistic"; a highlight dot as "a
  //: bowling ball". Neither belongs in an interface of flat glass.
  //: Every node glows a little (the owner: "I didnt mind the soft glow");
  //: a hub's glow is wider and a shade stronger, which is how a hub is told.
  //: **Calmer** (INBOX 443 (1)): the bloom reached 1.2 radii past a hub at
  //: 24% and 0.7 past a leaf at 16%, so on 30 dots the glows overlapped into a
  //: haze. Now 0.8 and 0.45 radii at 15% and 9%; a hub is still told by the
  //: wider, stronger one, and the hover lights the halo back up.
  const glow = hub ? Math.round(r * 0.8) + 3 : Math.round(r * 0.45) + 2;
  const ring = Math.max(1, Math.round(r * 0.18));
  const half = r + ring + glow + 1;
  const size = half * 2;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const c = canvas.getContext("2d");
  if (gcHexToRgb(colour)) {
    const bloom = c.createRadialGradient(half, half, r * 0.9, half, half, half);
    const rgb = gcHexToRgb(colour).join(", ");
    bloom.addColorStop(0, `rgba(${rgb}, ${hub ? 0.15 : 0.09})`);
    bloom.addColorStop(1, `rgba(${rgb}, 0)`);
    c.fillStyle = bloom;
    c.beginPath();
    c.arc(half, half, half, 0, Math.PI * 2);
    c.fill();
  }
  c.fillStyle = gcTokens.card || "#ffffff";
  c.beginPath();
  c.arc(half, half, r + ring, 0, Math.PI * 2);
  c.fill();
  gcPaintCore(c, half, r, colour);
  sprite = { canvas, half };
  gcSpriteCache.set(key, sprite);
  return sprite;
}

//: **A nebula behind each cluster.** The one thing a map of a notebook can
//: show that a list cannot is where the mass is, and seven clusters of
//: same-coloured dots say it only once the eye has done the grouping. A wide,
//: very faint radial wash of the cluster's colour behind each group does the
//: grouping for the eye, in the same language as the app's background art
//: (a soft field, not a drawn shape). Seven gradients a frame; a hull would
//: be a shape, and shapes lie about where a cluster ends.
function gcDrawNebulae(ctx, s, inView) {
  const nebulaBox = s.size === "full" ? gcEl("graph-nebula") : null;
  if (nebulaBox ? !nebulaBox.checked : prefs.get("graph-nebula", null) === "0") return;
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  const groups = new Map();
  for (const node of s.nodes) {
    if (!Number.isFinite(node.x) || !gcVisibleAtTime(node, s)) continue;
    const g = groups.get(node.colour) || { colour: node.colour, xs: [], ys: [] };
    g.xs.push(node.x);
    g.ys.push(node.y);
    groups.set(node.colour, g);
  }
  //: Additive in dark mode, so two washes that overlap brighten where the
  //: clusters meet instead of muddying to brown; on a light ground the plain
  //: blend is the one that stays faint.
  const previous = ctx.globalCompositeOperation;
  if (dark) ctx.globalCompositeOperation = "lighter";
  for (const g of groups.values()) {
    if (g.xs.length < 3) continue;
    const rgb = gcHexToRgb(g.colour);
    if (!rgb) continue;
    const cx = g.xs.reduce((a, b) => a + b, 0) / g.xs.length;
    const cy = g.ys.reduce((a, b) => a + b, 0) / g.ys.length;
    let spread = 0;
    for (let i = 0; i < g.xs.length; i++) spread += (g.xs[i] - cx) ** 2 + (g.ys[i] - cy) ** 2;
    const radius = Math.sqrt(spread / g.xs.length) * 1.6 + 40;
    if (!inView({ x: cx, y: cy, r: radius })) continue;
    const wash = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
    wash.addColorStop(0, `rgba(${rgb.join(", ")}, ${dark ? 0.09 : 0.06})`);
    wash.addColorStop(1, `rgba(${rgb.join(", ")}, 0)`);
    ctx.fillStyle = wash;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalCompositeOperation = previous;
}

//: GRAPH_PLAN VC11: the Treemap layout's category rectangles, behind the
//: notes. Each is the category's colour as a faint wash, a rim and its name and
//: count in the header the layout left for it (`layoutTreemap`); the gap
//: between two categories is drawn here, an inset, so the areas stay exact.
//: The name is clipped to its rectangle and left out of one too small to read.
function gcTreeFrameNodes(tree, nodes) {
  return tree.treemap && tree.treemap.length
    ? tree.treemap.flatMap((r) => [{ x: r.x0, y: r.y0, corner: true }, { x: r.x1, y: r.y1, corner: true }])
    : nodes;
}

function gcDrawTreemap(ctx, s, k) {
  const rects = s.tree && s.tree.treemap;
  if (!rects || !rects.length) return;
  ctx.save();
  ctx.lineJoin = "round";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.font = `600 ${12 / k}px ${gcTokens.font}`;
  const inset = 1.5;
  const heads = (s.treemapHeads = {});
  for (const rect of rects) {
    const x = rect.x0 + inset;
    const y = rect.y0 + inset;
    const w = rect.x1 - rect.x0 - 2 * inset;
    const h = rect.y1 - rect.y0 - 2 * inset;
    if (w <= 0 || h <= 0) continue;
    const colour = s.colourOf({ isGroup: true, category: rect.category });
    ctx.globalAlpha = 0.07;
    ctx.fillStyle = colour;
    ctx.fillRect(x, y, w, h);
    ctx.globalAlpha = 0.5;
    ctx.strokeStyle = colour;
    ctx.lineWidth = 1.5 / k;
    ctx.strokeRect(x, y, w, h);
    //: INBOX 1300 C37 ("the text at the top of the boxes gets cut off with
    //: no ellipse"): a name wider than its box ends in an ellipsis and keeps
    //: its count; it was clipped mid-letter. The legend names it whole.
    const text = gcEllipsize(rect.category || "Unfiled", ` (${rect.count})`, w - 12 / k, (t) => ctx.measureText(t).width);
    heads[rect.category] = text;
    if (!text) continue;
    ctx.globalAlpha = 1;
    ctx.fillStyle = gcTokens.ink;
    ctx.fillText(text, x + 6 / k, y + 9 / k);
  }
  ctx.restore();
}

//: `name` plus `suffix`, the name cut to end in an ellipsis where the two are
//: wider than `max`; empty when not even one letter, the ellipsis and the
//: suffix fit. `measure` gives a string's width in the units of `max`.
function gcEllipsize(name, suffix, max, measure) {
  if (measure(name + suffix) <= max) return name + suffix;
  let lo = 0;
  let hi = name.length - 1;
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2);
    if (measure(name.slice(0, mid).trimEnd() + "…" + suffix) <= max) lo = mid;
    else hi = mid - 1;
  }
  return lo ? name.slice(0, lo).trimEnd() + "…" + suffix : "";
}

//: B71 (INBOX 904, "so messy and stuck together I couldn't read it"): each
//: topic's name wants the spot straight above its outline's highest point,
//: and two topics with near tops wanted the same one, or a plate covered
//: another topic's dots. Seats the plates in the order given (the larger
//: topics first): the plate's own spot, then slid along the outline's top
//: edge, then lifted a row at a time, and the first seat clear of every seated
//: plate and every dot wins; a crowd with no clear seat takes the one with
//: the fewest hits. `entries` are {topic, cx, top, minX, maxX, w} in world
//: units (`top` the outline's highest y, `w` the plate's full width), `dots`
//: {x, y, r}. Returns {topic, x, left, right, top, bottom} in the same order.
function gcSeatTopicPlates(entries, dots, k) {
  const h = 17 / k;
  const gap = 10 / k;
  const cell = 48 / k;
  const grid = new Map();
  for (const d of dots) {
    const key = Math.floor(d.x / cell) + "," + Math.floor(d.y / cell);
    if (!grid.has(key)) grid.set(key, []);
    grid.get(key).push(d);
  }
  const dotHits = (box) => {
    let n = 0;
    for (let gx = Math.floor((box.left - 12 / k) / cell); gx <= Math.floor((box.right + 12 / k) / cell); gx++) {
      for (let gy = Math.floor((box.top - 12 / k) / cell); gy <= Math.floor((box.bottom + 12 / k) / cell); gy++) {
        for (const d of grid.get(gx + "," + gy) || []) {
          const r = d.r + 2 / k;
          if (d.x + r > box.left && d.x - r < box.right && d.y + r > box.top && d.y - r < box.bottom) n++;
        }
      }
    }
    return n;
  };
  const seated = [];
  for (const e of entries) {
    const lo = e.minX + e.w / 2;
    const hi = e.maxX - e.w / 2;
    const own = Math.min(Math.max(e.cx, Math.min(lo, hi)), Math.max(lo, hi));
    const slides = [0, -0.6, 0.6, -1.2, 1.2].map((m) => Math.min(Math.max(own + m * e.w, Math.min(lo, hi)), Math.max(lo, hi)));
    let best = null;
    for (let lift = 0; lift < 8 && !(best && best.cost === 0); lift++) {
      for (const x of slides) {
        const bottom = e.top - gap - lift * (h + 3 / k);
        const box = { topic: e.topic, x, left: x - e.w / 2, right: x + e.w / 2, top: bottom - h, bottom };
        let cost = dotHits(box);
        for (const p of seated) if (box.left < p.right + 3 / k && p.left < box.right + 3 / k && box.top < p.bottom + 2 / k && p.top < box.bottom + 2 / k) cost += 100;
        // Own spot wins a tie; each step off it costs a little, so a plate
        // is not lifted for nothing.
        cost += (lift * 0.02) + (Math.abs(x - own) > 0 ? 0.01 : 0);
        if (!best || cost < best.cost) best = { ...box, cost };
        if (cost < 0.5) break;
      }
      if (best && best.cost < 0.5) break;
    }
    const { cost, ...seat } = best;
    seated.push(seat);
  }
  return seated;
}

//: GRAPH_PLAN KG6: under the Topic colour rule, each topic of three or more
//: drawn notes gets its outline (a convex hull padded past its dots) and its
//: name on a plate above it, in the topic's colour. Full tab only.
function gcDrawTopicHulls(ctx, s, k) {
  //: The plates, in world units, for the label pass to keep names off (KG6).
  s.topicPlates = [];
  //: The force layout only (the owner, round 2, of a tree and an arc: topic
  //: hulls "squashed into a thin column", plates stacked on the line): a
  //: computed layout puts a topic's notes where their filing says, so its
  //: outline is a sliver across the others. The colours still say it.
  if (s.size !== "full" || s.tree || graphColourMode() !== "topic" || !graphStructure?.topics) return;
  const byTopic = new Map();
  const topicOf = graphStructure.topic_of || {};
  for (const node of s.nodes) {
    const topic = topicOf[String(node.id)];
    if (topic === undefined || !Number.isFinite(node.x) || !gcVisibleAtTime(node, s)) continue;
    if (!byTopic.has(topic)) byTopic.set(topic, []);
    const pad = (node.r || 6) + 10;
    for (let i = 0; i < 8; i++) byTopic.get(topic).push([node.x + pad * Math.cos(i * Math.PI / 4), node.y + pad * Math.sin(i * Math.PI / 4)]);
  }
  const names = new Map(graphStructure.topics.map((t) => [t.id, t.name]));
  ctx.save();
  ctx.lineJoin = "round";
  ctx.font = `600 ${12 / k}px ${gcTokens.font}`;
  const shapes = [];
  for (const [topic, points] of byTopic) {
    if (points.length < 24) continue;
    const hull = d3.polygonHull(points);
    if (!hull) continue;
    const top = hull.reduce((a, b) => (b[1] < a[1] ? b : a));
    const text = names.get(topic) || "";
    shapes.push({
      topic, hull, text, size: points.length,
      entry: {
        topic, cx: top[0], top: top[1], w: ctx.measureText(text).width + 10 / k,
        minX: hull.reduce((a, b) => Math.min(a, b[0]), Infinity), maxX: hull.reduce((a, b) => Math.max(a, b[0]), -Infinity),
      },
    });
  }
  //: The larger topic keeps the spot nearest its outline; a smaller one yields.
  shapes.sort((a, b) => b.size - a.size);
  const dots = [];
  for (const node of s.nodes) if (!node.isGroup && Number.isFinite(node.x) && gcVisibleAtTime(node, s)) dots.push({ x: node.x, y: node.y, r: node.r || 6 });
  const seats = gcSeatTopicPlates(shapes.map((p) => p.entry), dots, k);
  shapes.forEach((shape, i) => {
    const { topic, hull, text } = shape;
    const seat = seats[i];
    const colour = s.topicColour ? s.topicColour(String(topic)) : gcTokens.muted;
    ctx.beginPath();
    hull.forEach(([x, y], j) => (j ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath();
    ctx.globalAlpha = 0.06;
    ctx.fillStyle = colour;
    ctx.fill();
    ctx.globalAlpha = 0.45;
    ctx.strokeStyle = colour;
    ctx.lineWidth = 1.5 / k;
    ctx.setLineDash([6 / k, 4 / k]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 0.88;
    ctx.fillStyle = gcTokens.card;
    ctx.fillRect(seat.left, seat.top, seat.right - seat.left, seat.bottom - seat.top);
    s.topicPlates.push({ left: seat.left, right: seat.right, top: seat.top, bottom: seat.bottom, topic });
    //: The name in ink (a light topic colour is under 3:1 on the plate); the
    //: plate's edge carries the colour.
    ctx.globalAlpha = 1;
    ctx.lineWidth = 1.5 / k;
    ctx.strokeRect(seat.left, seat.top, seat.right - seat.left, seat.bottom - seat.top);
    ctx.fillStyle = gcTokens.ink;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, seat.x, (seat.top + seat.bottom) / 2);
  });
  ctx.restore();
}

//: GRAPH_PLAN KG8: the kinds of link taken off the map (a link's
//: `link_type`, "untyped" for none), kept between visits, and the property
//: chip that lights its notes.
const graphHiddenLinkKinds = new Set((() => {
  try {
    return prefs.json("graph-hidden-link-kinds", []);
  } catch {
    return [];
  }
})());
let gcPropLit = "";

function gcLinkKindHidden(edge) {
  return edge.kind === "link" && graphHiddenLinkKinds.has(edge.link_type || "untyped");
}

//: A counted filter is a chip, not a button (INBOX 803: "No kind 31" drawn
//: as a row of filled, bordered buttons, every kind being on by default).
//: The tag chip's ground with its count after the words; a link kind turned
//: off keeps its place struck through (the Read as row's toggle, quickadd),
//: and a lit property takes the chosen row's accent edge.
function gcFilterChip(label, count, pressed, title, onClick, { offWhenUnpressed = false } = {}) {
  const el = chip(label, "tag graph-filter-chip", onClick);
  el.setAttribute("aria-pressed", String(pressed));
  el.classList.toggle(offWhenUnpressed ? "is-off" : "is-lit", offWhenUnpressed ? !pressed : pressed);
  el.title = title;
  const n = document.createElement("span");
  n.className = "library-chip-count";
  n.textContent = String(count);
  el.append(n);
  return el;
}

//: The link kinds on the map, biggest first, as `[key, {label, n}]`. Empty when
//: no link has a kind: one chip, "No kind 64", filters nothing a person can
//: tell apart, so the row says so in words instead (audit 1029 G22). Unless that
//: kind was turned off earlier: its chip is the only way back.
function gcLinkKindRows(edges, hidden = new Set()) {
  const byKind = new Map();
  for (const e of edges) {
    if (e.kind !== "link") continue;
    const key = e.link_type || "untyped";
    const row = byKind.get(key) || { label: key === "untyped" ? "No kind" : e.type_name || key, n: 0 };
    row.n++;
    byKind.set(key, row);
  }
  const rows = [...byKind].sort((a, b) => b[1].n - a[1].n);
  return rows.some(([key]) => key !== "untyped" || hidden.has(key)) ? rows : [];
}

function gcRenderFilterChips(data) {
  const kinds = document.getElementById("graph-link-kinds");
  const props = document.getElementById("graph-prop-chips");
  if (!kinds || !props) return;
  const rows = gcLinkKindRows(data.edges, graphHiddenLinkKinds);
  kinds.replaceChildren(...rows.map(([key, row]) => {
    const shown = !graphHiddenLinkKinds.has(key);
    return gcFilterChip(row.label, row.n, shown, shown ? `Hide the ${row.label} links` : `Draw the ${row.label} links again`, () => {
      if (graphHiddenLinkKinds.has(key)) graphHiddenLinkKinds.delete(key);
      else graphHiddenLinkKinds.add(key);
      try {
        prefs.set("graph-hidden-link-kinds", JSON.stringify([...graphHiddenLinkKinds]));
      } catch {
        /* storage blocked: the choice holds for this visit */
      }
      renderGraph();
    }, { offWhenUnpressed: true });
  }));
  if (!rows.length) kinds.textContent = data.edges.some((e) => e.kind === "link") ? "No link has a kind yet." : "No links on the map.";
  const onMap = new Set(data.nodes.map((n) => n.id));
  const pairs = new Map();
  for (const e of typeof allEntries !== "undefined" ? allEntries : []) {
    if (!onMap.has(e.id)) continue;
    for (const [key, values] of Object.entries(e.properties || {})) {
      for (const value of values || []) {
        if (!value) continue;
        const pair = `${key}: ${String(value).replace(/^\[\[|\]\]$/g, "")}`;
        if (!pairs.has(pair)) pairs.set(pair, []);
        pairs.get(pair).push(e.id);
      }
    }
  }
  const top = [...pairs].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0])).slice(0, 12);
  props.replaceChildren(...top.map(([pair, ids]) => gcFilterChip(pair, ids.length, gcPropLit === pair, `Light the notes with ${pair}`, () => {
    gcPropLit = gcPropLit === pair ? "" : pair;
    graphHighlightIds = gcPropLit ? new Set(ids) : null;
    applyGraphHighlight();
    gcRenderFilterChips(data);
  })));
  if (!top.length) props.textContent = "No note on the map has properties.";
}

//: GRAPH_PLAN KG6: a topic's card. A summary is asked for, never fetched on
//: its own (a model pass); cached here and on the server by its notes; Stop
//: abandons the ask. With no model the server answers from the shared terms.
const gcTopicSummaries = new Map();
let gcTopicAsk = null;

function gcHideTopic() {
  gcTopicAsk?.abort();
  gcTopicAsk = null;
  document.getElementById("graph-topic")?.classList.add("hidden");
}

function gcShowTopic(topic, colour) {
  const box = document.getElementById("graph-topic");
  if (!box) return;
  gcTopicAsk?.abort();
  const key = [...topic.ids].sort((a, b) => a - b).join(",");
  const head = document.createElement("div");
  head.className = "graph-topic-head";
  const dot = document.createElement("span");
  dot.className = "graph-topic-dot";
  dot.style.setProperty("--topic-colour", colour);
  const name = document.createElement("strong");
  name.textContent = topic.name;
  //: The count is a muted line under the name, not a third item beside it: it
  //: wrapped to two lines as soon as the rename field took the name's room.
  const size = document.createElement("span");
  size.className = "muted graph-topic-count";
  size.textContent = nounCount(topic.size, "note");
  //: INBOX 547: a topic's name is found, and can be replaced by one of your
  //: own; an empty name brings the found one back.
  const tools = document.createElement("div");
  tools.className = "graph-topic-tools";
  const rename = smallButton("ph:pencil-simple", "Rename the topic", () => gcRenameTopicInline(topic, name, tools));
  rename.classList.add("icon-only");
  tools.append(rename);
  if (topic.named) {
    const back = smallButton("ph:arrow-counter-clockwise", `Use the found name, ${topic.found_name}`, () => gcSaveTopicName(topic, ""));
    back.classList.add("icon-only");
    tools.append(back);
  }
  const close = smallButton("ph:x", "Close the topic", gcHideTopic);
  close.classList.add("icon-only");
  tools.append(close);
  head.append(dot, name, tools, size);
  const terms = document.createElement("p");
  terms.className = "muted graph-topic-terms";
  terms.textContent = topic.terms.length ? `Shared: ${topic.terms.map((t) => `${t.term} (${t.notes})`).join(", ")}` : "Nothing its notes share stands out.";
  const summary = document.createElement("p");
  summary.className = "graph-topic-summary";
  summary.setAttribute("aria-live", "polite");
  const actions = document.createElement("div");
  actions.className = "row graph-topic-actions";
  const say = (row) => {
    //: No model answered: the composer's extractive summary, said so (K8).
    summary.textContent = (row.source === "terms" ? "Summary (no AI): " : "") + row.summary;
  };
  const ask = smallButton("ph:sparkle Summarise", "One sentence about these notes: your local model writes it, or the composer does when none answers", async () => {
    const controller = new AbortController();
    gcTopicAsk = controller;
    setBusy(ask, true, "Summarising…");
    const stop = smallButton("ph:stop Stop", "Stop asking", () => controller.abort());
    actions.appendChild(stop);
    const row = await apiJson("/graph/topics/summary", {
      method: "POST",
      readOnly: true,
      silent: true,
      signal: controller.signal,
      body: JSON.stringify({ ids: topic.ids, name: topic.name, terms: topic.terms.map((t) => t.term) }),
    }).catch(() => null);
    stop.remove();
    setBusy(ask, false);
    if (gcTopicAsk === controller) gcTopicAsk = null;
    if (!row) {
      if (controller.signal.aborted) summary.textContent = "Stopped.";
      else summary.textContent = "The summary could not be made.";
      return;
    }
    if (row.source === "model") gcTopicSummaries.set(key, row);
    say(row);
  });
  //: A topic becomes a category only when asked (ledger 945, GRAPH_PLAN
  //: "Topics and categories": neither writes the other on its own). One
  //: move with one Undo, the batch bar's own (`moveNotesToCategory`).
  const file = smallButton("ph:folder-simple-plus File as a category", "File these notes under one category, named for the topic", async () => {
    const wanted = (await promptDialog(`File these ${nounCount(topic.size, "note")} under the category`, topic.name.replace(/^#/, ""), { confirmLabel: "File" })).trim();
    if (wanted) await moveNotesToCategory(topic.ids, wanted);
  });
  actions.append(ask, file);
  const known = gcTopicSummaries.get(key);
  if (known) say(known);
  box.replaceChildren(head, terms, summary, actions);
  box.classList.remove("hidden");
}

//: A topic's name, saved (INBOX 547's route): an empty name brings the found
//: one back. Every place that shows the name is brought up to date here: the
//: legend, the open card, the plate on the next frame, and the note cards'
//: chips (`noteTopicsCache`, notes-list.js) the next time they draw.
async function gcSaveTopicName(topic, wanted) {
  const found = topic.found_name || topic.name;
  const was = topic.named ? topic.name : "";
  const row = await apiJson("/graph/topics/name", { method: "PUT", body: JSON.stringify({ ids: topic.ids, name: wanted }) }).catch(() => null);
  if (!row) return false;
  pushRequestUndo(`Renamed the topic “${found}”`, "/graph/topics/name", "PUT", { ids: topic.ids, name: was }, { ids: topic.ids, name: wanted }, async () => {
    if (typeof noteTopicsCache !== "undefined") noteTopicsCache.clear();
    await renderGraph();
  });
  topic.found_name = found;
  topic.named = Boolean(row.name);
  topic.name = row.name || found;
  const item = document.querySelector(`#graph-legend [data-topic="${topic.id}"]`);
  if (item?.lastChild) item.lastChild.textContent = `${topic.name} (${topic.size})`;
  if (typeof noteTopicsCache !== "undefined") noteTopicsCache.clear();
  if (!document.getElementById("graph-topic")?.classList.contains("hidden")) gcShowTopic(topic, gcTopicColour(topic));
  gcRequestDraw();
  return true;
}

//: **Renamed where it is written** (the owner, 2026-10-10: "I cant rename a
//: topic??", "I still cant edit topics in the graph or anywhere else"). The
//: only way in was a pencil on a card that only a legend entry under one
//: colour rule opened. Now a field opens over the name itself: on the map's
//: plate (double-click), on the topic's card and on a note's panel (their
//: pencils). Enter or leaving the field saves, Escape keeps the old name, and
//: an empty name brings the found one back. `anchor` is an element whose
//: place the field takes; with none it sits over the topic's plate.
function gcRenameTopicInline(topic, anchor = null, tools = null) {
  const s = gcTab;
  const box = s.canvas?.parentElement;
  document.querySelector(".graph-topic-rename")?.remove();
  const field = document.createElement("input");
  field.type = "text";
  field.maxLength = 80;
  field.className = "graph-topic-rename";
  field.value = topic.name;
  field.setAttribute("aria-label", `Rename the topic ${topic.name}`);
  field.title = "Enter to save, Escape to keep the name; empty brings the found name back";
  if (anchor) {
    anchor.classList.add("hidden");
    anchor.after(field);
  } else {
    const plate = (s.topicPlates || []).find((p) => p.topic === topic.id);
    if (!plate || !box) return;
    const t = s.transform || d3.zoomIdentity;
    field.classList.add("is-floating");
    const width = Math.max(140, (plate.right - plate.left) * t.k + 24);
    //: **The plate's own size** (OPEN row 795): the field stood 42px tall
    //: over a 17px plate. It takes the plate's height, a few pixels over for
    //: its border, centred on it, in the plate's own 12px type.
    const plateH = (plate.bottom - plate.top) * t.k;
    const height = Math.round(plateH + 6);
    field.style.width = `${width}px`;
    field.style.height = `${height}px`;
    field.style.left = `${t.applyX((plate.left + plate.right) / 2) - width / 2}px`;
    field.style.top = `${t.applyY(plate.top) - (height - plateH) / 2}px`;
    box.appendChild(field);
  }
  let done = false;
  let edit = null;
  const finish = async (save) => {
    if (done) return;
    done = true;
    const wanted = field.value.trim();
    field.remove();
    edit?.remove();
    tools?.classList.remove("hidden");
    anchor?.classList.remove("hidden");
    if (save && wanted !== topic.name) await gcSaveTopicName(topic, wanted);
  };
  //: On the card the name edits in place with Save and Cancel where the
  //: pencil and X were. Their mousedown is kept off the field so its blur
  //: (which saves) does not fire before the press that means Cancel.
  if (tools) {
    edit = document.createElement("div");
    edit.className = "graph-topic-tools";
    const save = smallButton("ph:check", "Save the name", () => finish(true));
    const cancel = smallButton("ph:x", "Keep the old name", () => finish(false));
    for (const b of [save, cancel]) {
      b.classList.add("icon-only");
      b.addEventListener("mousedown", (event) => event.preventDefault());
    }
    edit.append(save, cancel);
    tools.classList.add("hidden");
    tools.after(edit);
  }
  field.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key === "Enter") finish(true);
    else if (event.key === "Escape") finish(false);
  });
  field.addEventListener("blur", () => finish(true));
  field.focus();
  field.select();
}

//: The topic whose name plate is under a world point (plates are drawn under
//: the Topic colour rule, `gcDrawTopicHulls`), or null.
function gcPlateAtWorld(x, y, s = gcTab) {
  if (s.size !== "full" || !s.topicPlates?.length || !graphStructure?.topics) return null;
  const slop = 3 / ((s.transform && s.transform.k) || 1);
  const plate = s.topicPlates.find((p) => x >= p.left - slop && x <= p.right + slop && y >= p.top - slop && y <= p.bottom + slop);
  return plate ? graphStructure.topics.find((topic) => topic.id === plate.topic) || null : null;
}

function gcPlateTitle(topic, s = gcTab) {
  if (!topic) return "";
  return s.layoutKind === "force"
    ? `${topic.name}: drag to move the topic, double-click to rename, click for its card`
    : `${topic.name}: double-click to rename, click for its card`;
}

//: A topic's drawn notes: what a drag by its name carries.
function gcTopicMembers(topic, s = gcTab) {
  const ids = new Set(topic.ids.map(String));
  return s.nodes.filter((node) => ids.has(String(node.id)) && Number.isFinite(node.x) && gcVisibleAtTime(node, s));
}

//: The note a topic is held by: its most linked one (`core_id`), or the
//: first drawn member when that one is filtered out.
function gcTopicCore(topic, s = gcTab) {
  const members = gcTopicMembers(topic, s);
  return members.find((node) => String(node.id) === String(topic.core_id)) || members[0] || null;
}

//: A topic opened: its notes lit and its card shown, as its legend entry does.
function gcOpenTopic(topic) {
  graphHighlightIds = new Set(topic.ids);
  applyGraphHighlight();
  gcShowTopic(topic, gcTopicColour(topic));
}

//: A topic's colour as the map draws it (`s.topicColour`, set per render).
function gcTopicColour(topic, s = gcTab) {
  return s.topicColour ? s.topicColour(String(topic.id)) : gcTokens.muted;
}

const GC_HOVER_GROW = 3;         // half the gap from a core to its own halo
const GC_HOVER_HALO_GROW = 1.5;  // and the halo keeps clear by the same half
const GC_HOVER_MS = 190;

//: **A fit is balanced on what was drawn** (the owner, 2026-10-10, two
//: screenshots: "this is my graph's fitted view and it is a bit off",
//: "thats more fitted"). `fitGraphToView` pads every dot by the same 34
//: world units for a label that only some dots get, and only under them, so
//: the fitted map sat high or low and off to a side: measured on 60 notes at
//: 1440x900, margins left 318, right 351, top 96, bottom 80. After a fit
//: lands, the next frame's dots, placed names and topic plates are measured
//: on screen and the camera is set once so the drawing is centred with the
//: fit's own margin on the axis that limits it. The names keep their screen
//: size whatever the zoom, so the scale is solved with their overhang held
//: fixed rather than scaled with the dots.
//: `passes` more are allowed after this one: a new zoom places a different
//: set of names, so a second look settles what the first changed.
function gcBalanceFit(s, placed, passes = 0) {
  //: Not gated on `userZoomed`: the Fit button is pressed after a pan, and
  //: a gesture after the fit clears `fitCheck` instead (the zoom handler).
  //: Nor while the warm-up plays (`gcFrameIntro`): the drawn notes are on
  //: their way to the frame, not in it.
  if (s.size !== "full" || !s.nodes.length || !s.svg || !s.zoom || s.intro) return;
  const t = s.transform;
  const W = s.dims.w;
  const H = s.dims.h;
  let dMinX = Infinity, dMaxX = -Infinity, dMinY = Infinity, dMaxY = -Infinity;
  for (const node of s.nodes) {
    if (!Number.isFinite(node.x) || !gcVisibleAtTime(node, s)) continue;
    const r = node.r || 6;
    dMinX = Math.min(dMinX, node.x - r);
    dMaxX = Math.max(dMaxX, node.x + r);
    dMinY = Math.min(dMinY, node.y - r);
    dMaxY = Math.max(dMaxY, node.y + r);
  }
  if (!Number.isFinite(dMinX)) return;
  let cMinX = dMinX, cMaxX = dMaxX, cMinY = dMinY, cMaxY = dMaxY;
  for (const box of [...(placed || []), ...(s.topicPlates || [])]) {
    cMinX = Math.min(cMinX, box.left);
    cMaxX = Math.max(cMaxX, box.right);
    cMinY = Math.min(cMinY, box.top);
    cMaxY = Math.max(cMaxY, box.bottom);
  }
  //: Overhang past the dots, in screen pixels: constant under a zoom.
  const over = {
    left: (dMinX - cMinX) * t.k,
    right: (cMaxX - dMaxX) * t.k,
    top: (dMinY - cMinY) * t.k,
    bottom: (cMaxY - dMaxY) * t.k,
  };
  const box = { minX: dMinX, maxX: dMaxX, minY: dMinY, maxY: dMaxY };
  const { k, x, y } = graphFitFrame(box, W, H, gcFitInsets(s), over);
  if (!graphMinimapFinite(x, y, k)) return;
  //: Within a pixel and a percent is already balanced: no motion for nothing.
  if (Math.abs(k / t.k - 1) < 0.01 && Math.abs(x - t.x) < 1.5 && Math.abs(y - t.y) < 1.5) return;
  const framed = d3.zoomIdentity.translate(x, y).scale(k);
  const still = gcStill();
  const again = () => {
    if (passes <= 0) return;
    s.fitCheck = passes;
    gcRequestDraw(s);
  };
  if (still || s.canvas?.style.opacity === "0") {
    s.svg.interrupt().call(s.zoom.transform, framed);
    again();
  } else s.svg.transition().duration(graphGlideMs(220)).call(s.zoom.transform, framed).on("end", again);
}

//: The overlays a fit keeps the notes out from under, as the depth each one
//: takes from an edge of the map, in screen pixels (`graphFitFrame`): the
//: dock along the top, the legend along the bottom, and whichever panel is
//: open over the map (the owner, INBOX 792: fitting "should be based on what
//: panels are currently showing and the screen resolution/size"). Each is
//: counted against the edge it costs the least of the map's width or height
//: to clear. A closed panel has no box and costs nothing.
//: **Not the minimap or the zoom strip** (INBOX 802, "why's the graph so
//: positioned to the right and not in the middle??"): a 178px corner box
//: reserved a 190px column down the whole left side, so a fitted map sat
//: 132px right of centre (margins 418 and 286 on a 1406px canvas). They are
//: small corner furniture, not panels; a map centred on the canvas clears
//: them except at its very corners, as in every other graph view.
const GC_FIT_OVERLAYS = [
  "#graph-card > .graph-overlay > .dock",
  "#graph-card .graph-legend-row",
  "#graph-options",
  "#graph-help-panel",
  "#graph-selection-dock",
  "#graph-trace",
  "#graph-trace-result",
  "#graph-topic",
];
//: **A menu is not a panel** (the owner, 2026-10-11: "opening and closing
//: the graph settings button dropdown and the menu button move the graph a
//: bit"). The gear's options and the dock (whose ⋯ menu opens inside it)
//: still keep a Fit clear of themselves, but opening or closing one does not
//: refit the map: a menu over the map moves nothing on it (graphmenustill.js).
const GC_FIT_MENUS = "#graph-options, #graph-help-panel, #graph-card > .graph-overlay > .dock";
const GC_FIT_GAP = 4;
//: **The overlays a name is kept out from under**, in world units for this
//: frame (INBOX 1300 C41: at 1.8x on the 57-note seed, 6 names were drawn
//: under the dock, the legend, the minimap or the zoom strip, half read).
//: The fit's overlays plus the corner furniture the fit leaves alone. Read
//: from the DOM at most every 300ms (a layout read per frame is not free),
//: then mapped through this frame's transform.
function gcOverlayBoxes(s, t) {
  if (s.size !== "full" || !s.canvas) return [];
  const now = performance.now();
  if (!s._overlayRects || now - s._overlayAt > 300) {
    s._overlayAt = now;
    const c = s.canvas.getBoundingClientRect();
    s._overlayRects = [];
    for (const selector of [...GC_FIT_OVERLAYS, "#graph-minimap", "#graph-zoom"]) {
      const el = document.querySelector(selector);
      if (!el || el.hidden || !el.getClientRects().length) continue;
      const b = el.getBoundingClientRect();
      if (!b.width || !b.height || b.right <= c.left || b.left >= c.right || b.bottom <= c.top || b.top >= c.bottom) continue;
      s._overlayRects.push({ left: b.left - c.left, right: b.right - c.left, top: b.top - c.top, bottom: b.bottom - c.top });
    }
  }
  return s._overlayRects.map((r) => ({
    left: (r.left - t.x) / t.k,
    right: (r.right - t.x) / t.k,
    top: (r.top - t.y) / t.k,
    bottom: (r.bottom - t.y) / t.k,
  }));
}
function gcFitInsets(s = gcTab) {
  const insets = { top: 0, right: 0, bottom: 0, left: 0 };
  if (s.size !== "full" || !s.canvas || !s.dims.w || !s.dims.h) return insets;
  const c = s.canvas.getBoundingClientRect();
  if (!c.width || !c.height) return insets;
  for (const selector of GC_FIT_OVERLAYS) {
    const el = document.querySelector(selector);
    //: No client rects is not displayed; `offsetParent` would also skip a
    //: fixed sheet, which is the phone's panel.
    if (!el || el.hidden || !el.getClientRects().length) continue;
    const b = el.getBoundingClientRect();
    if (!b.width || !b.height || b.right <= c.left || b.left >= c.right || b.bottom <= c.top || b.top >= c.bottom) continue;
    const depth = {
      top: b.bottom - c.top,
      bottom: c.bottom - b.top,
      left: b.right - c.left,
      right: c.right - b.left,
    };
    const cost = (side) => depth[side] / (side === "top" || side === "bottom" ? c.height : c.width);
    const side = ["top", "bottom", "left", "right"].reduce((best, next) => (cost(next) < cost(best) ? next : best));
    insets[side] = Math.max(insets[side], depth[side] + GC_FIT_GAP);
  }
  return insets;
}

//: **A panel opening or closing refits a map that was fitted** (INBOX 792).
//: The overlays are watched by the canvas's own ResizeObserver (a panel
//: shown or hidden is a box going to or from no size); a camera the person
//: moved keeps where it is, and nothing refits before the first fit or
//: while the warm-up plays (`gcFrameIntro`).
function gcRefitForPanels(s) {
  if (s.userZoomed || s.intro || !s.zoom || !s.svg || !s.nodes?.length) return;
  if (s.tree) frameTree(s.svg, s.zoom, gcTreeFrameNodes(s.tree, s.nodes), s.dims.w, s.dims.h, s.tree.radial, s.tree.arc);
  else if (s.fittedOnce) fitGraphToView(s.svg, s.zoom, s.nodes, s.dims.w, s.dims.h);
}

//: Auto-fit turned back on: with it off a resize marks the camera as moved for good
//: (`userZoomed`), so the switch clears that and frames the map again.
function gcAutoFitTurnedOn(s = gcTab) {
  if (!s) return;
  s.userZoomed = false;
  gcRefitForPanels(s);
}

//: **A computed layout moves in from the map that was there** (the owner,
//: round 2: "I just change views or reset it and it just suddenly
//: changes"). A tree, radial or arc has no simulation to carry the notes
//: across, so each note seen before glides from where it stood to its new
//: place, eased over `GC_LAYOUT_MS`, and a note new to the picture (a
//: category's heading) fades in where it lands (`node._born`). Less motion
//: keeps the cut.
const GC_LAYOUT_MS = 700;
function gcTweenFromPrior(s, nodes, prior, move = true) {
  if (gcStill()) return;
  const now = performance.now();
  let moved = 0;
  for (const node of nodes) {
    const was = prior.get(node.id);
    if (!was || !Number.isFinite(was.x) || !Number.isFinite(was.y)) {
      node._born = now;
      continue;
    }
    if (!move) continue;
    node._fromX = was.x;
    node._fromY = was.y;
    node._toX = node.x;
    node._toY = node.y;
    node.x = was.x;
    node.y = was.y;
    moved += 1;
  }
  if (!moved) return;
  s.glideFrom = now;
  //: On the same token as `frameTree`'s camera, so frame and notes arrive
  //: together; 1ms, not 0, is a cut (0 means "glide by tick").
  s.glideMs = Math.max(1, graphGlideMs(GC_LAYOUT_MS));
  s.gliding = true;
  s.pathsStale = true;
}

//: How far a note new to the picture has faded in, 0 to 1 (`node._born`).
const GC_BORN_MS = 320;
function gcBornAlpha(node, now) {
  if (node._born === undefined) return 1;
  const share = (now - node._born) / GC_BORN_MS;
  if (share >= 1) {
    node._born = undefined;
    return 1;
  }
  return Math.max(0, share);
}

//: **A note leaving the picture fades out where it stood** (a hidden
//: category, a filter, a local view's neighbours, a deleted note): drawn as
//: it was, its own sprite and its lines, fading over `GC_BORN_MS`, with no
//: hit tests or labels. Measured before (Brief 100, `graph100.js`, hiding a
//: category of 200 on the 2,000-note map): past 300 notes nothing faded at
//: all, and below it the dot lost its rim and glow and its lines in the
//: first frame, a flat disc being all that faded. Less motion cuts, as a note
//: arriving does.
const GC_LEAVING_MAX = 2500;
function gcMarkLeaving(s, before, nodes) {
  s.leaving = null;
  if (!before?.length || gcStill()) return;
  const now = performance.now();
  const staying = new Set(nodes.map((n) => n.id));
  const gone = before.filter((n) => !staying.has(n.id) && Number.isFinite(n.x) && Number.isFinite(n.y) && n.colour);
  if (!gone.length || gone.length > GC_LEAVING_MAX) return;
  const scale = (s.transform?.k || 1) * (s.dpr || 1);
  const goneIds = new Set(gone.map((n) => n.id));
  const lines = new Path2D();
  let lineCount = 0;
  for (const edge of s.edges || []) {
    const a = edge.source;
    const b = edge.target;
    if (!a || !b || !(goneIds.has(a.id) || goneIds.has(b.id))) continue;
    if (!Number.isFinite(a.x) || !Number.isFinite(b.x)) continue;
    lines.moveTo(a.x, a.y);
    lines.lineTo(b.x, b.y);
    lineCount += 1;
  }
  s.leaving = {
    at: now,
    lines: lineCount ? lines : null,
    ghosts: gone.map((n) => ({
      x: n.x,
      y: n.y,
      r: n.r || 6,
      colour: n.colour,
      sprite: n._sprite || null,
      half: n._sprite ? n._sprite.half / scale : 0,
      alpha: n._dim ? GC_DIM_ALPHA : 1,
    })),
  };
}
//: Their lines, under every dot: stroked with the edge pass.
function gcDrawLeavingLines(ctx, s, now) {
  if (!s.leaving?.lines) return;
  const share = (now - s.leaving.at) / GC_BORN_MS;
  if (share >= 1) return;
  ctx.globalAlpha = 0.35 * (1 - gcEaseOut(share));
  ctx.strokeStyle = gcTokens.muted;
  ctx.lineWidth = 1 / (s.transform?.k || 1);
  ctx.stroke(s.leaving.lines);
}
function gcDrawLeaving(ctx, s, now) {
  if (!s.leaving) return;
  const share = (now - s.leaving.at) / GC_BORN_MS;
  if (share >= 1) {
    s.leaving = null;
    return;
  }
  const fade = 1 - gcEaseOut(share);
  for (const ghost of s.leaving.ghosts) {
    ctx.globalAlpha = ghost.alpha * fade;
    if (ghost.sprite) {
      ctx.drawImage(ghost.sprite.canvas, ghost.x - ghost.half, ghost.y - ghost.half, ghost.half * 2, ghost.half * 2);
      continue;
    }
    ctx.fillStyle = ghost.colour;
    ctx.beginPath();
    ctx.arc(ghost.x, ghost.y, ghost.r, 0, Math.PI * 2);
    ctx.fill();
  }
  s.bornPending = true;
}

//: `1 - (1 - t)^3`: fast away from the start, settling at the end. The same
//: shape as the `cubic-bezier(0.2, 0.8, 0.3, 1)` the stylesheet uses for the
//: SVG renderer's version of this, so the two renderers feel the same.
function gcEaseOut(t) {
  const c = Math.min(1, Math.max(0, t));
  return 1 - (1 - c) * (1 - c) * (1 - c);
}

//: Called when the hovered node changes. Whatever was growing starts
//: shrinking from wherever it had got to, so a fast sweep across a cluster
//: does not leave a node stuck large.
function gcHoverChanged(nextId, s = gcTab) {
  s.hoverFrom = s.hoverEase < 1 && s.hoverTo != null ? s.hoverTo : s.hoverFrom;
  if (s.hoverEase >= 1) s.hoverFrom = s.hoverTo;
  s.hoverTo = nextId;
  s.hoverStart = performance.now();
  s.hoverEase = 0;
}

//: How much bigger this node is drawing right now, in world units. Zero for
//: every node that is neither entering nor leaving the hover, which is all but
//: two of them.
function gcHoverGrow(node, base, s = gcTab) {
  if (node.id === s.hoverTo) return base * s.hoverEase;
  if (node.id === s.hoverFrom) return base * (1 - s.hoverEase);
  return 0;
}

//: Advances the ease and says whether another frame is owed. Called once per
//: draw, before anything is measured, so every radius in that frame agrees.
function gcHoverStep(s = gcTab) {
  if (s.hoverEase >= 1) return false;
  //: A reader who has asked for less motion gets the size change without the
  //: travel: the node is simply already large. Removing the growth as well
  //: would leave them with no hover feedback on this renderer at all, since
  //: there is no CSS here to give them a colour change instead.
  const still = gcStill();
  const ms = gcTokens.hoverMs ?? GC_HOVER_MS;
  s.hoverEase = still || !ms ? 1 : gcEaseOut((performance.now() - s.hoverStart) / ms);
  if (s.hoverEase >= 1) {
    s.hoverEase = 1;
    s.hoverFrom = null;
    return false;
  }
  return true;
}

//: **What the hover changes fades; nothing pops** (the owner, 2026-10-04:
//: "when I hover over parts of the graph, the labels and stuff just suddenly
//: appear and it is very visually confronting"). The node growth above eased,
//: but everything else a hover changes flipped in one frame: every dot and
//: line outside the neighbourhood dropped to its dim alpha, the names of the
//: dimmed notes vanished, the hovered note's name and its similarity scores
//: appeared, and its ring was drawn at full strength (measured,
//: `scratchpad/ui-sweeps/graphfade.js`: each went from rest to its end in the
//: first frame, nothing in between). Now every one of them carries a
//: lit-ness (0 dim or gone, 1 full) that travels toward its target by the
//: frame's share of GC_FADE_MS and is drawn through a smoothstep, so a fast
//: sweep across a cluster reverses from wherever each one had got to rather
//: than restarting. A label that moves to another of its four places, or
//: changes its words (the hovered note's whole title), cross-fades: the old
//: one is left as a ghost fading out where it was. Reduced motion lands
//: every one of them on the first frame.
const GC_FADE_MS = 180;

function gcSmooth(t) {
  const c = Math.min(1, Math.max(0, t));
  return c * c * (3 - 2 * c);
}

function gcFadeToward(value, target, step) {
  if (value == null) return target;
  return value < target ? Math.min(target, value + step) : Math.max(target, value - step);
}

//: The alpha a dot (or its ring) is drawn at for a lit-ness.
function gcLitAlpha(lit) {
  return GC_DIM_ALPHA + (1 - GC_DIM_ALPHA) * gcSmooth(lit);
}

//: This frame's step. A draw after an idle spell (the first frame of a hover)
//: counts as one ordinary frame, so a fade never starts by jumping a third of
//: the way; a slow frame mid-fade still advances by its real time, capped.
function gcFadeStep(s, still) {
  const now = performance.now();
  const last = s.fadeLast || 0;
  s.fadeLast = now;
  const ms = gcTokens.fadeMs ?? GC_FADE_MS;
  if (still || !ms) return 1;
  const dt = now - last > 100 ? 16.7 : Math.min(now - last, 64);
  return dt / ms;
}

// --- the draw ------------------------------------------------------------------

//: The glide between two worker ticks (INBOX 586; see the tick handler in
//: `gcStartWorker`): how long it lasts follows how far apart ticks are
//: arriving, between one display frame and the slowest duty cycle the worker
//: takes on a big map.
const GC_GLIDE_MIN_MS = 16;
const GC_GLIDE_MAX_MS = 120;

//: **A map that costs more than this to draw is drawn once a tick** (audit
//: 1029 row 35): 2,000 notes drew 472 full frames for 141 ticks, 417 of them
//: glides at about 13 ms each. The cost is smoothed over full draws only (a
//: hover or a pan composes from layers and says nothing about the scene).
const GC_GLIDE_COST_MS = 8;
function gcNoteDrawCost(s, ms) {
  s.drawCost = s.drawCost == null ? ms : s.drawCost * 0.7 + ms * 0.3;
}
function gcTickSnaps(s) {
  return (s.drawCost || 0) > GC_GLIDE_COST_MS;
}

//: **A layout that is cooling is drawn a few times a second, not every tick**
//: (perf3 1031, lagfix item 4: the owner saw 51 draws a second on a layout
//: still cooling). Below `GC_COOL_ALPHA` the notes only shift a few pixels a
//: tick (measured: 1 to 22 screen px at alpha 0.001, never under half a pixel
//: while a few notes keep settling), so a draw per tick, every 16 ms on a fast
//: machine, buys nothing the eye can follow. Such a tick is drawn when the
//: notes have moved `GC_COOL_MOVE_PX` from where they were last drawn, and
//: at most every `GC_COOL_DRAW_MS` (80 ms, 12 a second); a draw held back is made when that time
//: is up, so the map never rests a step behind the layout.
const GC_COOL_ALPHA = 0.05;
const GC_COOL_MOVE_PX = 0.5;
const GC_COOL_DRAW_MS = 80;

//: Points every note at the tick's position and answers how far (document
//: units) the one furthest from where it was last drawn now is.
function gcAimNodes(s, positions, count) {
  let drift = 0;
  for (let i = 0; i < count; i++) {
    const node = s.nodes[i];
    // A node being dragged is authoritative on this side: its position
    // came from the pointer this frame and the worker's copy is one
    // message behind.
    if (node === s.dragNode) continue;
    // From where the last glide was headed (or, the first time, from
    // where the note is), to the new tick.
    node._fromX = node._toX === undefined ? node.x : node._toX;
    node._fromY = node._toY === undefined ? node.y : node._toY;
    node._toX = positions[i * 2];
    node._toY = positions[i * 2 + 1];
    drift = Math.max(drift, Math.abs(node._toX - node.x), Math.abs(node._toY - node.y));
  }
  return drift;
}

//: A cooling layout, the notes not in the hand.
const gcCooling = (s) => s.alpha < GC_COOL_ALPHA && !s.dragNode;

//: Whether a tick puts the notes at its place at once rather than gliding to
//: it. A cooling layout does: a glide asks for a frame per display frame
//: until it ends, and ticks arriving every 16 ms keep restarting it, so the
//: cap below would hold the ticks' draws back and the glides would draw at
//: the display's rate anyway (synthetic ticks at 62 a second: 279 draws in 4 s).
const gcTickSettles = (s) => gcTickSnaps(s) || gcCooling(s);

//: Drawn.
function gcDrawTick(s, now) {
  s.lastTickDraw = now;
  s.heldDrift = 0;
  gcRequestDraw(s);
}

//: What a tick asks of the canvas. `heldDrift` adds up what ticks moved the
//: notes since the last draw (more than the true gap, never less), so a map
//: that settles at each tick (`gcTickSettles`) cannot wander off unseen.
function gcTickDraw(s, now, drift) {
  s.heldDrift = (s.heldDrift || 0) + drift;
  if (!gcCooling(s)) return gcDrawTick(s, now);
  if (s.heldDrift * (s.transform?.k || 1) < GC_COOL_MOVE_PX || s.coolTimer) return;
  const wait = (s.lastTickDraw || 0) + GC_COOL_DRAW_MS - now;
  if (wait <= 0) return gcDrawTick(s, now);
  s.coolTimer = setTimeout(() => {
    s.coolTimer = 0;
    gcDrawTick(s, performance.now());
  }, wait);
}

//: At rest, whatever the last ticks moved and no draw showed is drawn.
function gcDrawHeld(s) {
  if (s.heldDrift) gcDrawTick(s, performance.now());
}

//: Moves every note the share of the way from the tick before to the last
//: one that the time since the last one says, over the interval that brought
//: it, and reports whether there is more of the glide to draw. A note in the hand, and a note a new
//: render replaced, carry no target and are left alone.
function gcGlideStep(s) {
  if (!s.gliding) return false;
  //: A change of layout is one long eased glide (`gcTweenFromPrior`); a
  //: tick's is short and linear.
  const raw = Math.min(1, (performance.now() - s.glideFrom) / (s.glideMs || s.tickGap || GC_GLIDE_MIN_MS));
  const share = s.glideMs ? gcSmooth(raw) : raw;
  // Linear, not eased: glides follow one another tick after tick, and an
  // eased one would speed up and slow down inside every tick interval, which
  // is a pulse of its own.
  for (const node of s.nodes) {
    if (node._toX === undefined || node === s.dragNode) continue;
    node.x = node._fromX + (node._toX - node._fromX) * share;
    node.y = node._fromY + (node._toY - node._fromY) * share;
  }
  s.quadtreeDirty = true;
  if (raw >= 1) gcGlideFinish(s);
  return raw < 1;
}

function gcGlideFinish(s) {
  if (!s.gliding) return;
  s.gliding = false;
  s.glideMs = 0;
  for (const node of s.nodes) {
    if (node._toX === undefined) continue;
    if (node !== s.dragNode) {
      node.x = node._toX;
      node.y = node._toY;
    }
    node._toX = undefined;
    node._toY = undefined;
  }
  s.quadtreeDirty = true;
}

//: **A map on a hidden tab is not drawn.** Leaving Graph stops the worker,
//: but its last ticks are already on their way and each asks for a frame:
//: measured, 37 draws and 60 ms (240 ms at 4x CPU) after the press on the
//: next tab, in the window where that tab's own page is being drawn. The
//: tab's map only; a local map lives in a panel that decides for itself.
//: Coming back is `switchTab` -> `renderGraph`, which draws in full.
function gcTabHidden(s) {
  if (s.size !== "full") return false;
  const page = document.getElementById("tab-graph");
  return !!page && page.classList.contains("hidden");
}

//: `cheap`: only the camera or the hover changed, so the frame may be composed
//: from the scene layers (`gcDrawComposed`); anything else repaints them.
function gcRequestDraw(s = gcTab, cheap = false) {
  if (!cheap) s.sceneStale = true;
  if (s.drawQueued || !s.ctx || gcTabHidden(s)) return;
  s.drawQueued = true;
  requestAnimationFrame(() => {
    s.drawQueued = false;
    const full = s.sceneStale;
    const drawn = performance.now();
    s.lightDrawn = false;
    gcDraw(s);
    if (full && !s.lightDrawn) gcNoteDrawCost(s, performance.now() - drawn);
    if (s.minimapQueued) {
      s.minimapQueued = false;
      graphMinimapFrame();
    }
  });
}

//: **The minimap rides the draw's frame.** A pan used to repaint it
//: synchronously on every pointer event: measured over a forty-move pan,
//: forty full repaints, each one four passes over every node and three
//: document lookups, plus up to 700 fresh `<circle>` elements. Only the last
//: of those can be seen, exactly as with the canvas itself, so it belongs in
//: the frame with the draw rather than in the event. What does happen in the
//: event is the thing that has to: `gcTransform` is the new matrix before the
//: handler returns, so anything reading the camera reads the current one.
function gcRequestMinimapFrame(s = gcTab) {
  //: There is one minimap and it belongs to the tab. A pane panning its own
  //: camera must not move the picture of a map it is not drawing.
  if (s.size !== "full") {
    gcRequestDraw(s, true);
    return;
  }
  s.minimapQueued = true;
  gcRequestDraw(s, true);
}

//: **Two controls that were read out of the document on every frame.** The
//: search box and the labels switch are static elements, and `gcDraw` walked
//: the document for both of them on every frame of every pan, drag and hover:
//: 41 lookups each over a forty-move pan. Cached by id, re-found if the node
//: is ever replaced, which is the same shape the whiteboard's selection-bar
//: lookup needed for the same reason.
const gcElCache = new Map();
function gcEl(id) {
  const hit = gcElCache.get(id);
  if (hit && hit.isConnected) return hit;
  const found = document.getElementById(id);
  if (found) gcElCache.set(id, found);
  else gcElCache.delete(id);
  return found;
}

//: **A search that is only a search** (no traced path, no "similar notes"
//: spotlight) is drawn over the dimmed scene, as a hover is: the dimmed layer
//: does not depend on what was typed, so it is painted once and kept, and each
//: key draws only the notes it lights (audit 1029 G10: 80 ms a key at 2,000
//: notes at 1x, nearly all of it the canvas commit of a whole repaint).
function gcSearchOver(s) {
  if (s.size !== "full" || graphTrace || graphHighlightIds) return false;
  const box = gcEl("graph-search");
  return Boolean(box && box.value.trim());
}

//: What is dimmed and what is lit, in one pass, for the same reason the SVG
//: renderer's `applyGraphHighlight` does it in one pass: search, the "similar
//: notes" spotlight, a traced path and the hover neighbourhood are four
//: sources of the same signal, and two of them computed separately contradict
//: each other on screen.
function gcHighlight(s = gcTab) {
  //: Search, the spotlight and a traced path are the Graph tab's own
  //: controls. A pane beside a note has none of them, and inheriting them
  //: would dim a five-node local map to 20% because somebody left a search in
  //: the box on another tab.
  const chrome = s.size === "full";
  const search = chrome ? gcEl("graph-search") : null;
  const query = (search ? search.value : "").trim().toLowerCase();
  const onPath = chrome && graphTrace ? new Set(graphTrace.ids) : null;
  const ids = chrome ? graphHighlightIds : null;
  const searching = gcSearchOver(s);
  //: The scene layers carry no search (see `gcSearchOver`), so they are good
  //: for every query; the over layer, and a whole frame, do.
  const layered = searching && (s.paintMode === "rest" || s.paintMode === "dim");
  const found = query && !layered ? graphSearchFor(s.nodes, query) : null;
  const searchOk = (n) => (onPath ? onPath.has(n.id) : ids ? ids.has(n.id) : !found || found.ids.has(n.id));
  //: The dimmed layer of the composed frame (`gcDrawComposed`) is the map as
  //: every hover leaves it: no note is a neighbour.
  const neighbours =
    s.paintMode === "dim" ? GC_NO_NEIGHBOURS : s.hoveredId != null && s.adj ? s.adj.get(s.hoveredId) : null;
  const hoverOk = (id) => neighbours == null || id === s.hoveredId || neighbours.has(id);
  return {
    active: Boolean(found || ids || onPath),
    onPath,
    hovering: neighbours != null,
    searching,
    //: The match Enter last went to: ringed and named whatever else is dimmed.
    current: found ? graphSearch.current : null,
    searchOk,
    hoverOk,
  };
}

function gcVisibleAtTime(node, s = gcTab) {
  if (s.timeCutoff == null) return true;
  if (node.isGroup) return true;
  const at = new Date(node.created_at || Date.now()).getTime();
  return at <= s.timeCutoff;
}

// --- Phase 4: export at 2x with the legend ------------------------------------------
//: Re-renders the map into an offscreen canvas at `scale` times the screen's
//: pixel density by swapping the draw target for one frame (gcDraw reads
//: gcCtx and gcDpr; gcDims, the CSS size, stays the same, so the transform
//: is identical and nothing moves), then paints the legend and a caption
//: over it. Upscaling the live bitmap would only blur it.
function gcExportPng(scale = 2, s = gcTab) {
  if (!s.ctx || !s.canvas || !s.dims.w) return null;
  const out = document.createElement("canvas");
  out.width = Math.round(s.dims.w * s.dpr * scale);
  out.height = Math.round(s.dims.h * s.dpr * scale);
  const ctx = out.getContext("2d");
  const liveCtx = s.ctx;
  const liveDpr = s.dpr;
  ctx.fillStyle = gcTokens.page || (document.documentElement.dataset.mode === "dark" ? "#12141c" : "#eef1f5");
  ctx.fillRect(0, 0, out.width, out.height);
  try {
    s.ctx = ctx;
    s.dpr = liveDpr * scale;
    gcDraw(s);
  } finally {
    s.ctx = liveCtx;
    s.dpr = liveDpr;
  }
  ctx.setTransform(s.dpr * scale, 0, 0, s.dpr * scale, 0, 0);
  const rows = [...document.querySelectorAll("#graph-legend .legend-toggle:not(.legend-off)")]
    .map((item) => ({ text: item.textContent.trim(), colour: item.querySelector(".legend-dot")?.style.background || gcTokens.muted }))
    .filter((row) => row.text)
    .slice(0, 14);
  const noteCount = s.nodes.filter((n) => !n.isGroup).length;
  const caption = `${nounCount(noteCount, "note")} · ${new Date().toLocaleDateString()}`;
  ctx.font = "12px system-ui, sans-serif";
  const lineH = 18;
  const pad = 10;
  const width = Math.max(ctx.measureText(caption).width, ...rows.map((r) => ctx.measureText(r.text).width + 18)) + pad * 2;
  const height = (rows.length + 1) * lineH + pad * 2;
  const x = 12;
  const y = s.dims.h - height - 12;
  ctx.globalAlpha = 0.92;
  ctx.fillStyle = gcTokens.card || "#ffffff";
  ctx.beginPath();
  ctx.roundRect(x, y, width, height, 8);
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.fillStyle = gcTokens.ink || "#111";
  ctx.textBaseline = "middle";
  ctx.fillText(caption, x + pad, y + pad + lineH / 2);
  rows.forEach((row, i) => {
    const cy = y + pad + lineH * (i + 1) + lineH / 2;
    ctx.fillStyle = row.colour;
    ctx.beginPath();
    ctx.arc(x + pad + 5, cy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = gcTokens.ink || "#111";
    ctx.fillText(row.text, x + pad + 18, cy);
  });
  return out;
}

// --- the composed frame ------------------------------------------------------------
//
//: **A frame only the camera or the hover changed is composed, not painted**
//: (audit 1029 G5, G8). Measured at CPU 4x on 500 notes: the paint's own
//: script was 11 ms and the frame 67 to 133 ms; the rest was the raster of
//: every line, dot and wash at commit (`LayerTreeHost::DoUpdateLayers`).
//: Hiding the rest of the page, or a layer of its own for the canvas, changed
//: nothing; one full-size `drawImage` a frame held 16.7 ms. So the map is
//: painted into two layers at one camera, as it rests and with every note
//: dimmed; a pan or zoom draws them moved, a hover crossfades them and paints
//: only its own notes and lines on top. A moved layer is painted again once
//: the camera is still for `GC_SCENE_SETTLE_MS`, or at once when it no longer
//: covers the frame or is scaled past 2x. Anything else (`gcRequestDraw`
//: without `cheap`) paints the frame whole, as before.
const GC_SCENE_PAD = 0.15;
const GC_SCENE_SETTLE_MS = 160;
const GC_NO_NEIGHBOURS = new Set();
function gcPaintLayer(s, mode, old) {
  const pad = { x: Math.round(s.dims.w * GC_SCENE_PAD), y: Math.round(s.dims.h * GC_SCENE_PAD) };
  const canvas = old ? old.canvas : document.createElement("canvas");
  const w = Math.round((s.dims.w + 2 * pad.x) * s.dpr);
  const h = Math.round((s.dims.h + 2 * pad.y) * s.dpr);
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  //: Painted with no hover at all: the hover is the layer on top.
  const keep = { ctx: s.ctx, hoveredId: s.hoveredId, hoverTo: s.hoverTo, hoverFrom: s.hoverFrom, hoverEase: s.hoverEase, hoverEdge: s.hoverEdge };
  Object.assign(s, { ctx: canvas.getContext("2d"), paintMode: mode, paintPad: pad, paintFade: 1, hoveredId: null, hoverTo: null, hoverFrom: null, hoverEase: 1, hoverEdge: null });
  try {
    gcDraw(s);
  } finally {
    Object.assign(s, keep, { paintMode: null, paintPad: null });
  }
  return { canvas, pad };
}

function gcDrawComposed(s) {
  if (s.sceneStale || s.ctx.canvas !== s.canvas || !s.dims.w || !s.nodes.length) return false;
  const t = s.transform || d3.zoomIdentity;
  let scene = s.scene;
  if (scene && (scene.w !== s.dims.w || scene.h !== s.dims.h || scene.dpr !== s.dpr || scene.tokens !== gcTokens)) scene = null;
  if (scene && (t.k !== scene.t.k || t.x !== scene.t.x || t.y !== scene.t.y)) {
    const r = t.k / scene.t.k;
    const pad = scene.rest.pad;
    const left = t.x - r * (scene.t.x + pad.x);
    const top = t.y - r * (scene.t.y + pad.y);
    const covers = left <= 0 && top <= 0 && left + r * (s.dims.w + 2 * pad.x) >= s.dims.w && top + r * (s.dims.h + 2 * pad.y) >= s.dims.h;
    const still = performance.now() - (s.cameraAt || 0) >= GC_SCENE_SETTLE_MS;
    if (still || !covers || r > 2 || r < 0.5) {
      scene = null;
    } else {
      clearTimeout(s.sceneSettle);
      s.sceneSettle = setTimeout(() => gcRequestDraw(s, true), GC_SCENE_SETTLE_MS);
    }
  }
  if (!scene) {
    const old = s.scene;
    scene = s.scene = { t, w: s.dims.w, h: s.dims.h, dpr: s.dpr, tokens: gcTokens, dim: null, spare: old && (old.dim || old.spare) };
    scene.rest = gcPaintLayer(s, "rest", old && old.rest);
  }
  //: The hover: how dimmed the map is, and how lit each note it lights.
  const step = gcFadeStep(s, gcStill());
  const hovering = s.hoveredId != null && s.adj.has(s.hoveredId);
  //: A search dims the map as a hover does and lights its matches on top;
  //: with the pointer on a note too, the hover's neighbourhood is what is lit
  //: (and only the matches among it, `gcDraw` asks the search of each).
  const searching = gcSearchOver(s);
  s.searchOver = searching && !hovering;
  s.dimA = gcFadeToward(s.dimA, hovering || searching ? 1 : 0, step);
  let moving = s.dimA > 0 && s.dimA < 1;
  if (hovering && !s.overCentres.has(s.hoveredId)) s.overCentres.set(s.hoveredId, 0);
  s.overLit = new Map();
  for (const [id, a] of s.overCentres) {
    const next = gcFadeToward(a, id === s.hoveredId ? 1 : 0, step);
    if (next <= 0 || !s.adj.has(id)) {
      s.overCentres.delete(id);
      continue;
    }
    s.overCentres.set(id, next);
    if (next < 1) moving = true;
    for (const lit of [id, ...s.adj.get(id)]) s.overLit.set(lit, Math.max(s.overLit.get(lit) || 0, next));
  }
  //: `warmDim`: the search box was just focused, so the dimmed layer is painted
  //: now, while nobody is typing, and the first key draws only its matches.
  if ((s.dimA > 0 || s.warmDim) && !scene.dim) scene.dim = gcPaintLayer(s, "dim", scene.spare);
  s.warmDim = false;
  const ctx = s.ctx;
  const r = t.k / scene.t.k;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const shown = gcSmooth(s.dimA);
  const W = s.canvas.width;
  const H = s.canvas.height;
  //: Only the part of a layer the frame shows is read, and the first layer
  //: replaces the frame ("copy") rather than a clear and a blend over it.
  let first = true;
  for (const [layer, alpha] of [[scene.rest, 1 - shown], [scene.dim, shown]]) {
    if (!layer || alpha <= 0) continue;
    const sx = (r * (scene.t.x + layer.pad.x) - t.x) * (s.dpr / r);
    const sy = (r * (scene.t.y + layer.pad.y) - t.y) * (s.dpr / r);
    ctx.globalAlpha = alpha;
    ctx.globalCompositeOperation = first && alpha >= 1 ? "copy" : "source-over";
    if (first && alpha < 1) ctx.clearRect(0, 0, W, H);
    ctx.drawImage(layer.canvas, sx, sy, W / r, H / r, 0, 0, W, H);
    first = false;
  }
  if (first) ctx.clearRect(0, 0, W, H);
  ctx.globalCompositeOperation = "source-over";
  ctx.globalAlpha = 1;
  //: The hover's labels fade on their own, apart from the scene's.
  const labels = [s.labelLit, s.labelGhosts];
  s.labelLit = s.overLabelLit;
  s.labelGhosts = s.overLabelGhosts;
  s.paintMode = "over";
  s.paintFade = step;
  try {
    gcDraw(s);
  } finally {
    s.overLabelLit = s.labelLit;
    s.overLabelGhosts = s.labelGhosts;
    [s.labelLit, s.labelGhosts] = labels;
    s.paintMode = null;
  }
  s.composed = true;
  if (moving) gcRequestDraw(s, true);
  return true;
}

//: **A map this big is drawn plain while its layout is moving** (audit 1029
//: G3 / 1028 S2: 2,000 notes held the main thread for 100 to 230 ms a tick,
//: 62 long tasks over 100 ms in a cold open). Nobody reads names or curves on
//: notes still in flight, so a tick on such a map paints straight lines in one
//: stroke and one dot path per colour, and the full frame (curves, sprites,
//: names) is painted when it comes to rest, or when something needs it: the
//: first fit's reveal, a search, a trace, a hover, a drag, a tree layout.
const GC_LIGHT_ITEMS = 2500;
const GC_LIGHT_LINE_PX = 120000;
let gcLightLens = new Float32Array(0);
function gcLightFrame(s) {
  if (!s.layoutRunning || s.size !== "full" || s.tree || s.dragNode || s.hoveredId != null || s.paintMode) return false;
  if (s.fitCheck > 0 || s.revealAfterFit || s.nodes.length + s.edges.length < GC_LIGHT_ITEMS || !gcTickSnaps(s)) return false;
  const box = gcEl("graph-search");
  return !(graphTrace || graphHighlightIds || (box && box.value.trim()));
}

function gcDrawLight(s) {
  gcGlideStep(s);
  s.lightDrawn = true;
  s.scene = null;
  s.sceneStale = true;
  s.composed = false;
  s.bornPending = false;
  const ctx = s.ctx;
  const t = s.transform || d3.zoomIdentity;
  const k = t.k;
  ctx.setTransform(s.dpr, 0, 0, s.dpr, 0, 0);
  ctx.clearRect(0, 0, s.dims.w, s.dims.h);
  ctx.save();
  ctx.translate(t.x, t.y);
  ctx.scale(k, k);
  const m = 40 / k;
  const left = -t.x / k - m;
  const top = -t.y / k - m;
  const right = (s.dims.w - t.x) / k + m;
  const bottom = (s.dims.h - t.y) / k + m;
  //: Raster time is the length of line stroked, not the number of lines (3,796
  //: links, 1x: 23 ms, and 284 ms at 2x with the whole map in view; only the
  //: links under 300 units: 28 ms). So the frame strokes the shortest links
  //: up to `GC_LIGHT_LINE_PX` device pixels of line and leaves the long ones
  //: for the frame at rest.
  const reach = [];
  const lens = (gcLightLens.length < s.edges.length ? (gcLightLens = new Float32Array(s.edges.length)) : gcLightLens);
  const scale = k * s.dpr;
  let total = 0;
  for (const e of s.edges) {
    const a = e.source;
    const b = e.target;
    if (!a || !b || !(a.x === a.x) || !(b.x === b.x)) continue;
    if ((a.x < left && b.x < left) || (a.x > right && b.x > right) || (a.y < top && b.y < top) || (a.y > bottom && b.y > bottom)) continue;
    lens[reach.length] = Math.hypot(a.x - b.x, a.y - b.y) * scale;
    total += lens[reach.length];
    reach.push(e);
  }
  let cutoff = Infinity;
  if (total > GC_LIGHT_LINE_PX) {
    const sorted = lens.slice(0, reach.length).sort();
    let sum = 0;
    for (let i = 0; i < sorted.length && cutoff === Infinity; i++) {
      sum += sorted[i];
      if (sum > GC_LIGHT_LINE_PX) cutoff = sorted[i];
    }
  }
  const lines = new Path2D();
  for (let i = 0; i < reach.length; i++) {
    if (lens[i] >= cutoff) continue;
    lines.moveTo(reach[i].source.x, reach[i].source.y);
    lines.lineTo(reach[i].target.x, reach[i].target.y);
  }
  ctx.strokeStyle = gcTokens.muted;
  ctx.globalAlpha = 0.3;
  ctx.lineWidth = 1 / k;
  ctx.stroke(lines);
  const dots = new Map();
  for (const n of s.nodes) {
    if (!(n.x === n.x) || n.x < left || n.x > right || n.y < top || n.y > bottom) continue;
    let path = dots.get(n.colour);
    if (!path) dots.set(n.colour, (path = new Path2D()));
    //: A dot under 3 device pixels across is a square: the same to the eye,
    //: a third of the raster time of an arc.
    if (n.r * scale < 1.5) path.rect(n.x - n.r, n.y - n.r, 2 * n.r, 2 * n.r);
    else {
      path.moveTo(n.x + n.r, n.y);
      path.arc(n.x, n.y, n.r, 0, 6.2832);
    }
  }
  ctx.globalAlpha = 0.9;
  for (const [colour, path] of dots) {
    ctx.fillStyle = colour;
    ctx.fill(path);
  }
  ctx.restore();
  ctx.globalAlpha = 1;
}

function gcDraw(s = gcTab) {
  if (!s.ctx || !s.canvas) return;
  if (gcTabHidden(s)) return;
  if (gcLightFrame(s)) return gcDrawLight(s);
  if (!s.paintMode && gcDrawComposed(s)) return;
  //: `paintMode` (`gcDrawComposed`): null paints the frame whole; "rest" and
  //: "dim" paint a scene layer offscreen; "over" paints the hover on top.
  const over = s.paintMode === "over";
  const layer = s.paintMode === "rest" || s.paintMode === "dim";
  if (!s.paintMode) s.scene = null;
  const started = performance.now();
  //: Advanced once, before anything is measured, so every radius in this frame
  //: agrees, and another frame is asked for only while it is still moving.
  const easing = gcHoverStep(s);
  //: The glide's last frame lands the notes, so the paths are rebuilt on
  //: it too (`pathsStale` stays true until a frame after the glide).
  const gliding = gcGlideStep(s);
  //: A whole frame after composed ones lands every fade at once: the dims it
  //: would fade from are the scene's, not what was on screen.
  const snap = !s.paintMode && s.composed;
  s.composed = false;
  const fadeStep = s.paintMode ? s.paintFade : snap ? (gcFadeStep(s, true), 1) : gcFadeStep(s, gcStill());
  const litAlpha = over ? gcSmooth : gcLitAlpha;
  let fading = false;
  const ctx = s.ctx;
  const t = s.transform || d3.zoomIdentity;
  const k = t.k;
  const pad = s.paintPad || { x: 0, y: 0 };
  ctx.setTransform(s.dpr, 0, 0, s.dpr, s.dpr * pad.x, s.dpr * pad.y);
  if (!over) ctx.clearRect(-pad.x, -pad.y, s.dims.w + 2 * pad.x, s.dims.h + 2 * pad.y);
  ctx.save();
  ctx.translate(t.x, t.y);
  ctx.scale(k, k);

  // Cull to the visible world rectangle. On a 2,000-note map zoomed in, this
  // is the difference between drawing 2,000 nodes and drawing forty.
  const margin = 80 / k;
  const view = {
    left: (-t.x - pad.x) / k - margin,
    top: (-t.y - pad.y) / k - margin,
    right: (s.dims.w + pad.x - t.x) / k + margin,
    bottom: (s.dims.h + pad.y - t.y) / k + margin,
  };
  const inView = (n) =>
    n.x >= view.left && n.x <= view.right && n.y >= view.top && n.y <= view.bottom;

  const hl = gcHighlight(s);
  const labelsOn = (() => {
    //: The labels switch is the Graph tab's. A pane is small enough that its
    //: handful of labels are the point of it, so they are always on there.
    if (s.size !== "full") return true;
    const box = gcEl("graph-labels");
    return box ? box.checked : true;
  })();

  if (!over) {
    gcDrawNebulae(ctx, s, inView);
    gcDrawTreemap(ctx, s, k);
    gcDrawTopicHulls(ctx, s, k);
  }
  //: Read from the switch itself, like the labels above, so what the menu
  //: shows and what is drawn cannot disagree (the owner: "it is showing
  //: curved links even when it is visibly off??"); the stored value only
  //: stands in for a pane, which has no switch.
  const curvedLinks = gcCurvedLinks(s);

  // --- edges -------------------------------------------------------------
  // Bucketed by recipe and by whether they are dimmed, so the context's
  // stroke state is set once per bucket rather than once per edge. A dashed
  // stroke is the expensive one, and there are only ever a handful of dashes.
  const buckets = new Map();
  //: Similarity lines in buckets of their own, stroked first so they sit
  //: beneath every link (INBOX 412: the server appends them after the links,
  //: so bucket order alone painted them on top).
  const simBuckets = new Map();
  //: The note whose similarity scores are written on its lines: the one
  //: pointed at, else the one the keyboard is on, else the one whose panel is
  //: open. Its lines are the ones not dimmed, so the numbers sit on the only
  //: lines still in full view.
  const openId = s.size === "full" && typeof graphPopupId !== "undefined" ? graphPopupId : null;
  const scoreFor =
    s.hoveredId != null
      ? s.hoveredId
      : gcKeyboardId(s) != null
        ? gcKeyboardId(s)
        : openId;
  s.simScoreLabels = [];
  const arrows = !s.tree && gcArrows(s);
  //: A spark drifts along the pointed-at note's arrowed links, unless motion
  //: is reduced (the system's setting or the app's own).
  const drifting =
    arrows &&
    s.hoveredId != null &&
    !gcStill() &&
    document.documentElement.dataset.motion !== "reduced";
  const drift = [];
  //: The glow and core only while few sparks are in view (the last frame's
  //: count): a dense view gets the spark and the taper, inside the +0.5 ms
  //: budget on the 417-note map (graphspark.js).
  const sparkRich = (s.sparksDrawn || 0) <= 300;
  let sparks = 0;
  const widthScale = gcLinkWidth();
  const simLo = s.simRange ? s.simRange[0] : GC_SIM_FLOOR;
  const simHi = s.simRange ? s.simRange[1] : 1;
  for (const edge of s.edges) {
    const a = edge.source;
    const b = edge.target;
    if (!a || !b || !Number.isFinite(a.x) || !Number.isFinite(b.x)) continue;
    if (!gcVisibleAtTime(a, s) || !gcVisibleAtTime(b, s)) continue;
    // Both ends off-screen on the same side: nothing of the line can be in
    // frame. A cheap, conservative test, an edge crossing the viewport with
    // both ends outside still gets drawn.
    if (
      (a.x < view.left && b.x < view.left) ||
      (a.x > view.right && b.x > view.right) ||
      (a.y < view.top && b.y < view.top) ||
      (a.y > view.bottom && b.y > view.bottom)
    ) {
      continue;
    }
    //: The hover draws only the lines of the notes it lights, at how lit each is.
    const centre = over ? (s.searchOver ? 1 : Math.max(s.overCentres.get(a.id) || 0, s.overCentres.get(b.id) || 0)) : 1;
    if (!centre) continue;
    const bySearch = !hl.active || (hl.searchOk(a) && hl.searchOk(b));
    const byHover =
      over || !hl.hovering || a.id === s.hoveredId || b.id === s.hoveredId;
    const dim = !(bySearch && byHover);
    if (over && dim) continue;
    //: A scene layer is drawn as it will rest, and keeps nothing of it.
    const lit = over ? centre : layer ? (dim ? 0 : 1) : (edge._lit = gcFadeToward(edge._lit, dim ? 0 : 1, fadeStep));
    if (!layer && !over && lit !== (dim ? 0 : 1)) fading = true;
    //: Eleven steps of lit-ness, so a fade still strokes in buckets.
    const level = Math.round(gcSmooth(lit) * 10);
    if (edge._styleEpoch !== s.epoch) gcEdgeLook(edge, a, b, simLo, simHi, s.epoch);
    const similar = edge._similar;
    //: **A line between clusters is quiet until asked about** (INBOX 693,
    //: the owner: cross-cluster links "thin and muted (only highlighted on
    //: hover)"). The clusters are what the map says; the lines between them
    //: are the footnote. Thinner and fainter, unless the pointer is on one
    //: of its ends; a contradiction keeps its warning.
    const quiet = edge._cross && !(hl.hovering && byHover);
    const style = quiet ? edge._quietStyle : edge._style;
    const slot = level * 2 + (quiet ? 1 : 0);
    const key = edge._keys[slot] || (edge._keys[slot] = `${edge.kind}|${edge._tint || style.colour}|${style.width}|${style.alpha}|${style.dash}|${level}`);
    const into = similar ? simBuckets : buckets;
    let bucket = into.get(key);
    if (!bucket) {
      bucket = { style, level, tint: edge._tint, path: new Path2D() };
      into.set(key, bucket);
    }
    if (similar && scoreFor != null && (a.id === scoreFor || b.id === scoreFor)) {
      // From the note in focus towards its match, whichever end is which.
      const [from, to] = a.id === scoreFor ? [a, b] : [b, a];
      s.simScoreLabels.push({ from, to, score: edge.score });
    }
    if (s.tree) {
      // A tree's edges are curves between fixed points. `hierarchyPath` and
      // `arcPath` already return SVG path data, and Path2D speaks it, so the
      // curve maths is shared with the SVG renderer rather than rewritten.
      //: Cached for a still tree; rebuilt every frame while its notes glide in
      //: (`gcTweenFromPrior`), or the lines are left where the notes started.
      if (!edge._path2d || s.pathsStale) {
        edge._path2d = new Path2D(s.tree.arc ? arcPath(edge) : hierarchyPath(edge, s.tree.radial));
      }
      bucket.path.addPath(edge._path2d);
      // No arrow on a link that runs both ways (INBOX 693, `two_way` from /graph).
    } else if (arrows && edge.kind === "link" && !edge.two_way) {
      const bow = curvedLinks ? gcBowPoint(a, b, gcBowScratch, edge._side) : null;
      gcLinkSpark(bucket, a, bow, b, k, sparkRich);
      sparks += 1;
      if (drifting && (a.id === s.hoveredId || b.id === s.hoveredId)) drift.push({ a, bow: bow && { x: bow.x, y: bow.y }, b, bucket });
    } else if (curvedLinks) {
      const bow = gcBowPoint(a, b, gcBowScratch, edge._side);
      bucket.path.moveTo(a.x, a.y);
      bucket.path.quadraticCurveTo(bow.x, bow.y, b.x, b.y);
    } else {
      bucket.path.moveTo(a.x, a.y);
      bucket.path.lineTo(b.x, b.y);
    }
  }
  const strokeBucket = (bucket) => {
    const style = bucket.style;
    ctx.strokeStyle = bucket.tint || gcTokens[style.colour] || gcTokens.muted;
    // `.graph-edge.graph-dim` is opacity 0.06 in the stylesheet; kept, because
    // a dimmed edge that is still readable defeats the spotlight.
    ctx.globalAlpha = (over ? 0 : 0.06) + (style.alpha - (over ? 0 : 0.06)) * (bucket.level / 10);
    //: An arrowed link thins from its source half to its target half.
    ctx.lineWidth = (style.width * widthScale * (bucket.wide ? 0.8 : 1)) / k;
    ctx.setLineDash(style.dash ? style.dash.map((v) => v / k) : []);
    ctx.stroke(bucket.path);
    if (bucket.wide) {
      ctx.lineWidth = (style.width * widthScale * 1.25) / k;
      ctx.stroke(bucket.wide);
      gcFillSparks(ctx, bucket, ctx.globalAlpha);
    }
  };
  for (const bucket of simBuckets.values()) strokeBucket(bucket);
  for (const bucket of buckets.values()) strokeBucket(bucket);
  ctx.setLineDash([]);
  if (!over) gcDrawLeavingLines(ctx, s, performance.now());
  if (!over) s.sparksDrawn = sparks;
  if (drift.length) {
    gcDrawDrift(ctx, drift, k);
    fading = true;
  }
  ctx.globalAlpha = 1;

  if (!layer) {
    if (gcDrawEdgeHover(ctx, s, k, fadeStep, curvedLinks)) fading = true;
  }

  // --- the traced path ----------------------------------------------------
  if (!over) gcDrawTrace(ctx, k, s);

  // --- nodes --------------------------------------------------------------
  // Two batched fills per colour (halo, then core) and one batched stroke for
  // the ordinary ring. Only the handful of nodes that are hovered, matched,
  // pinned, held, hub or on a path get their own stroke.
  const haloByColour = new Map();
  const labelZoom = s.size === "full" ? gcLabelZoom() : GC_LABEL_ZOOM;
  const ringed = (s.ringed = []);
  const hubs = { path: new Path2D(), any: false };
  const labelled = [];
  const drawn = [];
  const hotHalos = [];
  for (const node of s.nodes) {
    if (!Number.isFinite(node.x)) continue;
    if (!gcVisibleAtTime(node, s)) continue;
    if (!inView(node)) continue;
    const lift = over ? (s.searchOver ? 1 : s.overLit.get(node.id)) : 1;
    if (!lift) continue;
    const dim = !(hl.searchOk(node) && (over || hl.hoverOk(node.id)));
    if (over && dim) continue;
    //: A scene layer or the hover writes its own lit-ness here; the whole
    //: frame after composed ones lands every fade at once (`snap`), so none
    //: of it leaks into a fade.
    node._lit = over ? lift : layer ? (dim ? 0 : 1) : gcFadeToward(node._lit, dim ? 0 : 1, fadeStep);
    if (!layer && !over && node._lit !== (dim ? 0 : 1)) fading = true;
    const key = node.colour;
    let halo = haloByColour.get(key);
    if (!halo) {
      //: Four batched fills per colour, not two: a soft glow outside the halo
      //: and a shine inside the core (the SVG renderer has both; the canvas
      //: renderer had flat discs, and the owner asked for nodes that look
      //: "more visually pleasing while keeping it professional"). Batched
      //: per colour like the halo, so the cost is two fills per colour per
      //: frame rather than two per node.
      halo = { colour: node.colour, nodes: [] };
      haloByColour.set(key, halo);
    }
    //: The hover growth, applied once and remembered on the node, so the core,
    //: the halo, the plain ring, the hub ring and the special ring below all
    //: draw against the same radius this frame. Reading it four times would
    //: let the ring and the dot it rings disagree by a fraction of a pixel
    //: mid-ease, which reads as a shimmer on the outline.
    node._grow = gcHoverGrow(node, GC_HOVER_GROW, s);
    //: The at most two nodes mid-ease, kept aside so their halo can be lit
    //: without breaking the colour batching every other node relies on.
    const heat = gcHoverGrow(node, 1, s);
    if (heat > 0) hotHalos.push({ node, heat });
    const r = node.r + node._grow;
    const haloR = node.r + 6 + gcHoverGrow(node, GC_HOVER_HALO_GROW, s);
    void haloR;
    halo.nodes.push(node);
    drawn.push(node);
    node._dim = dim;
    //: The note whose popup is open keeps the focus ring (Brief 100 (c), a
    //: ring on the selected node), so the map says which dot the card is for.
    const focused = node.id === s.hoveredId || node.id === gcKeyboardId(s) || node.id === openId || node.id === hl.current;
    //: The node the pointer just left keeps its ring while it shrinks back,
    //: fading with it, and the one it arrived on fades its ring in.
    const leaving = !focused && node.id === s.hoverFrom && heat > 0;
    const ringFade = leaving || (focused && node.id === s.hoverTo) ? heat : 1;
    const matched = hl.active && hl.searchOk(node);
    const onPath = hl.onPath ? hl.onPath.has(node.id) : false;
    const special =
      focused ||
      leaving ||
      matched ||
      onPath ||
      node.pinned ||
      //: Held only means something in Force: a computed layout holds every
      //: note, and the test without the layout gave every treemap dot the
      //: fallback accent ring below (INBOX 1300 C37, "all the same").
      (node.fx != null && s.layoutKind === "force") ||
      !gcIsNote(node) ||
      node === s.dropTarget;
    if (special) {
      ringed.push({ node, focused: focused || leaving, ringFade, matched, onPath, dim });
    } else if (!dim && (s.adj.get(node.id) || { size: 0 }).size >= 3) {
      // **A hub's ring is batched, not drawn per node.** Average degree in a
      // real notebook is about four, so "degree >= 3" is most of the map: one
      // `beginPath`/`stroke` each was 2,000 stroke calls a frame at the fitted
      // zoom and on its own blew the 16 ms budget. Every hub ring is the same
      // colour and the same width, so it is one path and one stroke.
      hubs.path.moveTo(node.x + node.r + node._grow, node.y);
      hubs.path.arc(node.x, node.y, node.r + node._grow, 0, Math.PI * 2);
      hubs.any = true;
    }
    // Labels come on by zoom, and a hovered or spotlit note always shows its
    // own: including with the Labels tickbox off, which is what
    // `.graph-labels-hidden g.graph-focus .graph-label { opacity: 1 }` does on
    // the SVG renderer. "Labels off" means "not all of them", not "never".
    // "Labels on" means on. Reported with a screenshot: the tickbox was on
    // and one hovered label showed, because every other label waited for a
    // zoom past GC_LABEL_ZOOM that a fitted 35-note map never reaches. Below
    // GC_LABEL_ALL_MAX nodes the tickbox shows them all at any zoom; above
    // it the zoom gate stays, since 2,000 labels at the fitted zoom are
    // paint the eye cannot read and the frame budget cannot afford.
    const labelsForAll = labelsOn && s.nodes.length <= GC_LABEL_ALL_SMALL && k > labelZoom - GC_LABEL_ZOOM;
    //: A match is named whatever the tickbox says: the label is why somebody typed.
    if (!dim && ((labelsOn && (labelsForAll || k > labelZoom)) || matched || focused)) {
      labelled.push(node);
    }
  }
  //: The overview's landmarks: see GC_LABEL_LANDMARKS. Only when the zoom gate
  //: is what kept every other label off, and only notes with a real
  //: neighbourhood (degree 2 or more), so a map of islands does not name
  //: twelve arbitrary dots. They join the queue below as ordinary labels:
  //: the collision pass decides whether each has room.
  if (labelsOn && labelled.length < drawn.length && k <= labelZoom && s.nodes.length > GC_LABEL_ALL_SMALL) {
    const already = new Set(labelled.map((node) => node.id));
    const degree = (node) => (s.adj.get(node.id) || { size: 0 }).size;
    // A big map keeps its dozen hubs of degree 2+; a mid-sized one names
    // its best-connected third, a lone note included only if it has a link.
    //: **Hubs only, in every shape but Organic** (INBOX 693, the
    //: owner: "labels for hubs only by default plus collision-free placement
    //: for the rest at zoom"). Measured on the showcase notebook at the fit,
    //: the best-connected third named 23 notes, leaves among them, and the
    //: names were what made a cluster look busy. Grouped, the overview names
    //: each category's hub (its best-connected note, two links or more) and
    //: any other note with `GC_LABEL_HUB_DEGREE` links, at most
    //: GC_LABEL_LANDMARKS; the rest are named past the zoom gate.
    // Every shape but Organic (`_straight`), whose overview keeps its
    // best-connected third on pills, the look the owner kept.
    const grouped = s.nodes.some((node) => node._straight);
    const big = s.nodes.length > GC_LABEL_ALL_MAX;
    const count = big || grouped
      ? GC_LABEL_LANDMARKS
      : Math.max(8, Math.round(s.nodes.length * GC_LABEL_LANDMARK_SHARE));
    let pool = drawn.filter((node) => !node._dim && !already.has(node.id) && degree(node) >= (big ? 2 : 0));
    if (grouped && !big) {
      const top = new Map();
      for (const node of pool) {
        const best = top.get(node.category || "");
        if (degree(node) >= 2 && (!best || degree(node) > degree(best))) top.set(node.category || "", node);
      }
      const heads = new Set(top.values());
      pool = pool.filter((node) => heads.has(node) || degree(node) >= GC_LABEL_HUB_DEGREE);
      pool.sort((a, b) => Number(heads.has(b)) - Number(heads.has(a)) || degree(b) - degree(a));
    } else {
      pool.sort((a, b) => degree(b) - degree(a));
    }
    const landmarks = pool.slice(0, count);
    for (const node of landmarks) labelled.push(node);
  }
  //: Sprites at the zoom's own pixel size, so a node stays crisp at any
  //: scale; the sizes are rounded to whole pixels, which keeps the cache to
  //: a few dozen entries per colour.
  const pixelScale = k * (s.dpr || 1);
  //: **Level of detail** (audit 2026-10-05, FE-04). A node smaller on screen
  //: than `GC_LOD_PX` is a dot whose glow and rim are a pixel or less, and
  //: `drawImage` of its sprite was the largest single cost on a 5,000-note
  //: map (7.8 s of a 32 s profile). Those dots are gathered into one path per
  //: colour and lit-ness and filled once each; a node large enough for its
  //: rim to be seen keeps its sprite.
  const lodPaths = new Map();
  let lodNodes = 0;
  const bornAt = performance.now();
  s.bornPending = false;
  for (const halo of haloByColour.values()) {
    for (const node of halo.nodes) {
      const born = gcBornAlpha(node, bornAt);
      if (born < 1) s.bornPending = true;
      let alpha = gcLitAlpha(node._lit) * born;
      if (over) alpha = gcSmooth(node._lit) * born;
      if (node.type === "unresolved") alpha *= 0.4;
      const rWorld = node.r + node._grow;
      if (rWorld * pixelScale < GC_LOD_PX && !node._grow) {
        const key = `${halo.colour}|${Math.round(alpha * 8)}`;
        let batch = lodPaths.get(key);
        if (!batch) {
          batch = { colour: halo.colour, alpha: Math.round(alpha * 8) / 8, path: new Path2D() };
          lodPaths.set(key, batch);
        }
        batch.path.moveTo(node.x + rWorld, node.y);
        batch.path.arc(node.x, node.y, rWorld, 0, Math.PI * 2);
        lodNodes += 1;
        continue;
      }
      ctx.globalAlpha = alpha;
      //: The node keeps the sprite it drew last (Brief 100): the cache key
      //: was a new string for every node on every frame of a hover fade.
      const px = Math.max(2, Math.round(rWorld * pixelScale));
      if (node._spritePx !== px || node._spriteEpoch !== s.epoch || node._spriteFor !== gcTokens) {
        const hub = (s.adj.get(node.id)?.size || 0) >= 3;
        node._sprite = gcNodeSprite(halo.colour, px, hub);
        node._spritePx = px;
        node._spriteEpoch = s.epoch;
        node._spriteFor = gcTokens;
      }
      const sprite = node._sprite;
      const halfWorld = sprite.half / pixelScale;
      ctx.drawImage(sprite.canvas, node.x - halfWorld, node.y - halfWorld, halfWorld * 2, halfWorld * 2);
    }
  }
  for (const batch of lodPaths.values()) {
    ctx.globalAlpha = batch.alpha;
    ctx.fillStyle = batch.colour;
    ctx.fill(batch.path);
  }
  if (!over) s.lodNodes = lodNodes;
  if (!over) gcDrawLeaving(ctx, s, bornAt);
  //: The hovered node's halo, lit. A second fill over the one the batch
  //: already laid down, because pulling this node out of its colour batch to
  //: give it a different alpha would cost a fill per colour rather than a fill
  //: per hovered node, and there are at most two of those.
  //:
  //: 0.16 over the batch's 0.18 composites to 0.31: `1 - (1 - 0.18)(1 - 0.16)`.
  //: Multiplying by `heat` is what makes it ease in and out with the size,
  //: including on the node being left, whose `heat` is counting down.
  for (const hot of hotHalos) {
    if (hot.node._dim) continue;
    ctx.globalAlpha = 0.16 * hot.heat * gcSmooth(hot.node._lit);
    ctx.fillStyle = hot.node.colour;
    ctx.beginPath();
    ctx.arc(
      hot.node.x,
      hot.node.y,
      hot.node.r + 6 + gcHoverGrow(hot.node, GC_HOVER_HALO_GROW, s),
      0,
      Math.PI * 2,
    );
    ctx.fill();
  }

  // The ordinary ring (`.graph-core { stroke: var(--card) }`) in one pass.
  ctx.globalAlpha = 1;
  //: No card-coloured ring and no accent ring on hubs any more: the sprite
  //: carries its own rim, and a hub is told by its size and its wider glow
  //: rather than by a painted outline (`hubs` is still gathered so the
  //: keyboard and hover paths that read it keep working).
  void hubs;

  if (!over) gcDrawSelection(ctx, k, s);
  for (const item of ringed) {
    const node = item.node;
    ctx.globalAlpha = litAlpha(node._lit) * item.ringFade;
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.r + (node._grow || 0), 0, Math.PI * 2);
    if (node === s.dropTarget) {
      ctx.strokeStyle = gcTokens.ok;
      ctx.lineWidth = 4 / k;
    } else if (item.onPath) {
      ctx.strokeStyle = gcTokens.accent;
      ctx.lineWidth = 3.5 / k;
    } else if (item.focused) {
      ctx.strokeStyle = gcTokens.accent;
      ctx.lineWidth = 3.5 / k;
    } else if (item.matched) {
      ctx.strokeStyle = gcTokens.accent;
      ctx.lineWidth = 3 / k;
    } else if (node.fx != null && s.layoutKind === "force") {
      // Held in place by a drag or a double-click: the same dashed ink ring
      // `.graph-held` draws, so a held note looks held on both renderers.
      //
      //: Force layout only. Tree, radial and arc hold every node by setting
      //: `fx`/`fy` from the computed hierarchy, so this test was true for all
      //: of them at once and the whole board wore the ring that means "you
      //: pinned this". Reported on 2026-09-09: "on the other graph view
      //: types, they all have the dotted border as they are static but that
      //: shouldnt be the case".
      ctx.strokeStyle = gcTokens.ink;
      ctx.lineWidth = 2 / k;
      ctx.setLineDash([3 / k, 2 / k]);
    } else if (node.pinned) {
      ctx.strokeStyle = gcTokens.warn;
      ctx.lineWidth = 2 / k;
    } else if (GC_KIND_DASH[node.type]) {
      ctx.strokeStyle = gcTokens.ink;
      ctx.lineWidth = 2 / k;
      if (node.type === "unresolved") ctx.globalAlpha *= 0.5;
      ctx.setLineDash(GC_KIND_DASH[node.type].map((v) => v / k));
    } else {
      // Unreachable while `ringed` only takes the nodes the branches above
      // name; kept so a future ring condition added to that test cannot draw
      // with whatever stroke the previous node happened to leave set.
      ctx.strokeStyle = gcTokens.accent;
      ctx.lineWidth = 2.5 / k;
    }
    ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.globalAlpha = 1;

  // --- labels -------------------------------------------------------------
  //: What the debug surface and the fit balance read is the scene's labels.
  const book = over ? {} : s;
  book.labelsWanted = 0;
  book.labelsDrawn = 0;
  book.labelsPriority = 0;
  // Cleared per frame, not only written per frame: a map whose labels have
  // just been switched off would otherwise report the boxes of the last frame
  // that had any.
  book.labelBoxes = [];
  let placedLabels = [];
  if (labelled.length && s.paintMode !== "dim") {
    const size = 12 / k;
    // Divided by the zoom so a label is a constant size on screen: the whole
    // context is scaled by k, and a fixed font size would make labels grow
    // with the map until three of them filled the card.
    ctx.font = `500 ${size}px ${gcTokens.font}`;
    // A tree's rows are 34px apart, so a label under the node lands on the
    // next row's; beside it is the only place it fits. The web spreads in two
    // dimensions and reads better with the label under the dot. (Radial and
    // arc labels are centred under the node here rather than rotated onto the
    // spoke, which is the one place this renderer is visibly plainer than the
    // SVG one: recorded in GRAPH_PLAN.md's "Built" section.)
    const beside = Boolean(s.tree) && !s.tree.radial && (!s.tree.arc || s.tree.vertical);
    ctx.textAlign = beside ? "left" : "center";
    ctx.textBaseline = "middle";
    ctx.lineJoin = "round";
    ctx.lineWidth = 3 / k;
    ctx.strokeStyle = gcTokens.card;
    ctx.fillStyle = gcTokens.ink;
    // **Labels do not stack.** Reported with a screenshot: with the Labels
    // tickbox on, a fitted map drew all of them (every board under
    // `GC_LABEL_ALL_MAX`), and in the dense middle of a force layout that is
    // a pile of overlapping words that says less than no label at all.
    //
    // So a label is drawn only if its own text box is still free. The order
    // decides which one wins the space, and it is not the order the nodes
    // happen to be in: whatever the pointer or the keyboard is on first (it
    // was asked for by name), then the search hits (the reason someone
    // typed), then the best-connected notes, which are the ones a map is
    // read by. Those two priority classes are drawn even when they clash,
    // because a label you asked for and cannot see is a bug, not tidiness.
    // The rest come back on hover or above `GC_LABEL_ZOOM`, which is the
    // gesture the map already teaches.
    //
    // The overlap test is a linear scan of what has been placed: the placed
    // set is bounded by the frame's area over a label's, a few dozen, so
    // this is thousands of number comparisons and no allocation, not the
    // quadtree it looks like it wants.
    const labelRank = (node) =>
      node.id === s.hoveredId || node.id === gcKeyboardId(s) || node.id === hl.current
        ? 0
        : hl.active && hl.searchOk(node)
          ? 1
          : 2;
    // **A search that matches half the notebook is not a request for half the
    // notebook's labels.** Found by the probe on the 300-note fixture:
    // searching a word every note contains made all 264 hits rank 1, and rank
    // 1 was drawn through any clash, so the pile the collision pass exists to
    // prevent came straight back through the search box. A handful of hits is
    // a question about those notes and each one keeps its label whatever it
    // lands on; past that it is a filter, and a filter's job is done by the
    // dimming, with the labels queued ahead of everything else and still
    // subject to the same test as everything else. The hovered or
    // keyboard-focused note is never in this trade: there is exactly one of
    // it, and it was pointed at.
    //: **The landmarks** are the ten best-connected notes in view, what the
    //: map is read by. They were let sit on a dot (GRAPH_PLAN.md, "Decision
    //: made, 2026-09-26"); since INBOX 693 they are not ("labels never over
    //: dots or lines", the owner), and only keep the right to the place
    //: crossing the fewest lines when none crosses none (`gcPlaceLabels`).
    const landmarkIds = new Set(
      drawn
        .filter((node) => !node._dim && (s.adj.get(node.id) || { size: 0 }).size >= 2)
        .sort((a, b) => (s.adj.get(b.id) || { size: 0 }).size - (s.adj.get(a.id) || { size: 0 }).size)
        .slice(0, GC_LABEL_LANDMARK_HUBS)
        .map((node) => node.id)
    );
    const hits = labelled.reduce((n, node) => n + (labelRank(node) === 1 ? 1 : 0), 0);
    const forceHits = hits <= GC_LABEL_FORCE_MAX;
    labelled.sort((a, b) => {
      const rank = labelRank(a) - labelRank(b);
      if (rank) return rank;
      const degreeA = (s.adj.get(a.id) || { size: 0 }).size;
      const degreeB = (s.adj.get(b.id) || { size: 0 }).size;
      return degreeB - degreeA;
    });
    book.labelsWanted = labelled.length;
    book.labelsPriority = 0;
    const padX = 4 / k;
    const padY = 2 / k;
    const items = [];
    for (const node of labelled) {
      const text = gcLabelText(node, s);
      // `measureText` is cheap but not free at a few hundred labels a frame,
      // and the answer only changes when the text or the zoom does. The zoom
      // is only a scale: see `gcLabelWidth` for why that is not a re-measure.
      if (node._labelText !== text || node._labelSize !== size) {
        node._labelText = text;
        node._labelSize = size;
        node._labelWidth = gcLabelWidth(text, size);
      }
      const width = node._labelWidth;
      const x = beside ? node.x + node.r + 7 : node.x;
      const y = beside ? node.y : node.y + node.r + 13;
      const left = (beside ? x : x - width / 2) - padX;
      const rank = labelRank(node);
      if (rank < 2) book.labelsPriority += 1;
      //: **Where else the name may go** when its own place is taken. Under the
      //: dot is the web's reading position and stays first; then above it,
      //: then to its right, then to its left. Measured on the 417-note
      //: fixture at 2x: under-only named none of the ten best-connected notes
      //: in view, because in the dense middle "under" is always another dot.
      //: A tree keeps its one place (beside), which its row spacing is built
      //: around.
      const r = node.r + (node._grow || 0);
      const half = size / 2 + padY;
      const alts = beside
        ? []
        : [
            { x: node.x, y: node.y - r - 13 / k, align: "center" },
            { x: node.x + r + 6 / k, y: node.y, align: "left" },
            { x: node.x - r - 6 / k, y: node.y, align: "right" },
            //: The four corners (INBOX 493), off the dot's diagonal: a hub's
            //: lines leave it in every direction, and between two of them is
            //: often the only place its name can stand clear of all of them.
            { x: node.x + r * 0.72 + 3 / k, y: node.y + r * 0.72 + 9 / k, align: "left" },
            { x: node.x - r * 0.72 - 3 / k, y: node.y + r * 0.72 + 9 / k, align: "right" },
            { x: node.x + r * 0.72 + 3 / k, y: node.y - r * 0.72 - 9 / k, align: "left" },
            { x: node.x - r * 0.72 - 3 / k, y: node.y - r * 0.72 - 9 / k, align: "right" },
            //: Then a step further out (INBOX 693): a name may no longer sit
            //: on a dot or a line, and a hub in the middle of its cluster
            //: (the layout puts it there now) has a leaf or a spoke at every
            //: near place. Measured on the showcase notebook at the fit:
            //: without these, three of its seven category hubs went unnamed.
            { x: node.x, y: node.y + r + 27 / k, align: "center" },
            { x: node.x, y: node.y - r - 27 / k, align: "center" },
            { x: node.x + r + 20 / k, y: node.y + 12 / k, align: "left" },
            { x: node.x - r - 20 / k, y: node.y + 12 / k, align: "right" },
            { x: node.x + r + 20 / k, y: node.y - 12 / k, align: "left" },
            { x: node.x - r - 20 / k, y: node.y - 12 / k, align: "right" },
          ].map((spot) => {
            const l = spot.align === "center" ? spot.x - width / 2 : spot.align === "left" ? spot.x : spot.x - width;
            return { ...spot, left: l - padX, right: l + width + padX, top: spot.y - half, bottom: spot.y + half };
          });
      // The id and the rank ride along with the geometry because the only
      // way to ask "do the labels on screen overlap" from outside a canvas is
      // to be handed the boxes: a screenshot of a pile of words and a
      // screenshot of a clean map are the same bytes to a sweep.
      items.push({
        id: node.id,
        rank,
        force: rank === 0 || (rank === 1 && forceHits),
        left,
        right: left + width + padX * 2,
        top: y - size / 2 - padY,
        bottom: y + size / 2 + padY,
        text,
        x,
        y,
        align: beside ? "left" : "center",
        alts,
        landmark: landmarkIds.has(node.id),
      });
    }
    //: The dots a label may not cover: every note drawn this frame, at the
    //: size it is drawn (hover growth included).
    const discs = drawn.map((node) => ({
      id: node.id,
      x: node.x,
      y: node.y,
      r: node.r + (node._grow || 0),
    }));
    // `paint-order: stroke` on `.graph-label`, the halo goes down first so a
    // label stays legible over an edge or another node.
    //: Not while the layout is still moving (or a dot is being dragged):
    //: every position would change the grid each frame, at 1.5ms a build on
    //: 1,100 links, for names that are moving anyway. The names step to
    //: their clear places when it settles, cross-fading (`gcDrawLabels`).
    //: The hover places its few labels against its own notes only: no line grid.
    //: Names keep off the lines once the layout is at rest, or nearly so on
    //: a map cheap to draw: rebuilt per tick it was a fifth of each tick's
    //: draw at 2,000 notes (audit 1029 row 35).
    const costly = s.layoutRunning && gcTickSnaps(s);
    const lines = over || s.tree || s.dragNode || costly || s.alpha > 0.03 ? null : gcLineGrid(s, curvedLinks);
    // The canvas itself, a few pixels in: a name is never cut by its edge
    // (INBOX 693, labels "cut by the viewport"; `gcPlaceLabels`).
    const inset = 4 / k;
    const frame = {
      left: -t.x / k + inset,
      top: -t.y / k + inset,
      right: (s.dims.w - t.x) / k - inset,
      bottom: (s.dims.h - t.y) / k - inset,
    };
    const blocked = [...(s.topicPlates || []), ...gcOverlayBoxes(s, t)];
    const placed = gcPlaceLabels(items, discs, lines ? (box, limit) => gcBoxLineCount(lines, box, limit) : null, blocked, frame);
    placedLabels = placed;
    book.labelBoxes = placed;
    book.labelsDrawn = placed.length;
  }
  if (s.paintMode !== "dim" && gcDrawLabels(ctx, s, placedLabels, fadeStep, k)) fading = true;
  if (!over && s.fitCheck > 0) {
    const left = s.fitCheck - 1;
    s.fitCheck = 0;
    gcBalanceFit(s, placedLabels, left);
  }
  if (!over && s.revealAfterFit && !(s.fitCheck > 0)) {
    s.revealAfterFit = false;
    gcReveal(s);
  }

  // --- the pointed-at note's similarity scores -------------------------------
  //: Kumu's focus and Obsidian's hover both answer "what is this one joined
  //: to"; a similarity line also has "how closely", which a line's weight
  //: only ranks. So the note in focus writes the number on each of its
  //: similarity lines, at the middle, as a small pill over everything else
  //: (the lines it sits on are the only ones not dimmed). A percentage
  //: rather than a cosine, because "72%" reads and "0.72" is a statistic.
  //: The pills fade in with the note they belong to, and the last note's
  //: fade out where they were (see GC_FADE_MS).
  if (layer) s.simScoreLabels = [];
  if (!layer && scoreFor !== s.pillFor) {
    if (s.pillDrawn?.length && s.pillA > 0) s.pillGhost = { list: s.pillDrawn, a: s.pillA };
    s.pillA = 0;
    s.pillFor = scoreFor;
    s.pillDrawn = [];
  }
  if (!layer && s.pillGhost) {
    s.pillGhost.a = gcFadeToward(s.pillGhost.a, 0, fadeStep);
    if (s.pillGhost.a > 0) {
      fading = true;
      ctx.font = `600 ${11 / k}px ${gcTokens.font}`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      for (const pill of s.pillGhost.list) gcDrawPill(ctx, pill, k, gcSmooth(s.pillGhost.a));
    } else {
      s.pillGhost = null;
    }
  }
  if (s.simScoreLabels.length) {
    s.pillA = gcFadeToward(s.pillA || 0, 1, fadeStep);
    if (s.pillA < 1) fading = true;
    s.pillDrawn = [];
    const size = 11 / k;
    ctx.font = `600 ${size}px ${gcTokens.font}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    //: Obstacles: the labels this frame placed, the pills placed so far, and
    //: every drawn dot at the size it is drawn plus a hair of clearance.
    const boxes = book.labelBoxes.slice();
    //: A dimmed dot is drawn at 20% and is not what the reader is looking
    //: at, so a pill may sit over it; a lit one may not.
    const dots = drawn
      .filter((node) => !node._dim)
      .map((node) => ({ x: node.x, y: node.y, r: node.r + (node._grow || 0) + 2 / k }));
    // Strongest first, so if space runs out it is the weakest that overlaps.
    const pills = s.simScoreLabels.slice().sort((p, q) => q.score - p.score);
    s.simScoreLabels = [];
    for (const pill of pills) {
      const text = `${Math.round(pill.score * 100)}%`;
      const w = ctx.measureText(text).width + 8 / k;
      const h = size + 5 / k;
      const spot = gcPlacePill(pill.from, pill.to, w, h, boxes, dots);
      if (!spot.placed) continue;
      boxes.push(spot);
      s.simScoreLabels.push({ id: pill.to.id, score: pill.score, ...spot });
      const drawn = { spot, w, h, text };
      s.pillDrawn.push(drawn);
      gcDrawPill(ctx, drawn, k, gcSmooth(s.pillA));
    }
  }

  ctx.restore();
  if (layer) return;
  gcHoverCardFrame(s);
  if (s === gcTab && typeof graphPopupId !== "undefined" && graphPopupId !== null) placeGraphPopup();
  s.timing.lastFrame = performance.now() - started;
  s.timing.frames += 1;
  // **Only a frame with something in it stops the clock.** A frame drawn
  // before the first positions exist is a blank canvas, and calling that "the
  // first frame" would be measuring nothing and reporting a good number for
  // it: the exact shape of self-deception the gate exists to prevent.
  if (!s.timing.firstFrame && s.timing.dataAt && drawn.length) {
    s.timing.firstFrame = performance.now() - s.timing.dataAt;
  }
  //: One more frame while the hover is still growing or shrinking. Nothing
  //: is scheduled once `gcHoverStep` reports it has arrived, so an idle graph
  //: costs no frames at all.
  s.pathsStale = gliding && Boolean(s.glideMs);
  const busy = fading || gliding || s.bornPending;
  if (!s.paintMode) {
    //: Nothing but the hover is left moving: the next frame can be composed,
    //: from the hover this one showed.
    s.sceneStale = busy;
    s.dimA = hl.hovering || hl.searching ? 1 : 0;
    s.overCentres = new Map(hl.hovering ? [[s.hoveredId, 1]] : []);
  }
  //: A fade of the whole map keeps painting whole frames; a hover's ease, or
  //: anything the hover layer moves, asks for a composed one.
  const cheap = over || !busy;
  if (cheap && (easing || busy)) gcRequestDraw(s, true);
  else if (easing || fading || gliding || s.bornPending) gcRequestDraw(s);
}

//: The line under the pointer, drawn again over the rest, wider and in its
//: own colour, at its own lit-ness (GC_FADE_MS), so pointing at a line lights
//: it the way pointing at a note lights the note; the one just left fades out.
//: **Arrows are sparks, not triangles** (the owner: "make the graph arrows
//: impressive and styled in a way unique to the app"). A four-point star,
//: its tail long like a comet's, 70% of the way along the link where no dot
//: covers it, in the link's own colour on a soft two-step glow; the line is
//: wider on its source half than its target half, so the direction reads even
//: zoomed out. All batched per bucket: one more stroke and four fills per
//: colour, whatever the number of links.
function gcQuadAt(a, c, b, t) {
  const u = 1 - t;
  return {
    x: u * u * a.x + 2 * u * t * c.x + t * t * b.x,
    y: u * u * a.y + 2 * u * t * c.y + t * t * b.y,
    dx: 2 * u * (c.x - a.x) + 2 * t * (b.x - c.x),
    dy: 2 * u * (c.y - a.y) + 2 * t * (b.y - c.y),
  };
}

function gcLinkSpark(bucket, a, bow, b, k, rich = true) {
  const c = bow || { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  // The two halves (de Casteljau at 0.5): wide from the source, thin to the target.
  const m1x = (a.x + c.x) / 2, m1y = (a.y + c.y) / 2;
  const m2x = (c.x + b.x) / 2, m2y = (c.y + b.y) / 2;
  const mx = (m1x + m2x) / 2, my = (m1y + m2y) / 2;
  if (!bucket.wide) {
    bucket.wide = new Path2D();
    bucket.sparks = new Path2D();
    bucket.glows = new Path2D();
    bucket.cores = new Path2D();
    bucket.halos = new Path2D();
  }
  bucket.wide.moveTo(a.x, a.y);
  bucket.wide.quadraticCurveTo(m1x, m1y, mx, my);
  bucket.path.moveTo(mx, my);
  bucket.path.quadraticCurveTo(m2x, m2y, b.x, b.y);
  const p = gcQuadAt(a, c, b, 0.7);
  const len = Math.hypot(p.dx, p.dy) || 1;
  const ux = p.dx / len, uy = p.dy / len;
  const tips = [
    [p.x + (ux * 7) / k, p.y + (uy * 7) / k],
    [p.x - (uy * 4.5) / k, p.y + (ux * 4.5) / k],
    [p.x - (ux * 18) / k, p.y - (uy * 18) / k],
    [p.x + (uy * 4.5) / k, p.y - (ux * 4.5) / k],
  ];
  bucket.sparks.moveTo(tips[0][0], tips[0][1]);
  for (let i = 1; i <= 4; i++) {
    const from = tips[i - 1], to = tips[i % 4];
    // Pulled in towards the centre: concave sides, a spark rather than a kite.
    bucket.sparks.quadraticCurveTo(
      p.x + 0.2 * (from[0] + to[0] - 2 * p.x), p.y + 0.2 * (from[1] + to[1] - 2 * p.y), to[0], to[1]);
  }
  if (!rich) return;
  bucket.rich = true;
  // Two discs, wide and faint then close and brighter: a soft glow for the
  // price of two fills, where a canvas blur would be one per spark.
  bucket.glows.moveTo(p.x + 8 / k, p.y);
  bucket.glows.arc(p.x, p.y, 8 / k, 0, Math.PI * 2);
  bucket.halos.moveTo(p.x + 4.5 / k, p.y);
  bucket.halos.arc(p.x, p.y, 4.5 / k, 0, Math.PI * 2);
  bucket.cores.moveTo(p.x + 1.4 / k, p.y);
  bucket.cores.arc(p.x, p.y, 1.4 / k, 0, Math.PI * 2);
}

function gcFillSparks(ctx, bucket, alpha) {
  ctx.setLineDash([]);
  ctx.fillStyle = ctx.strokeStyle;
  ctx.globalAlpha = Math.min(1, alpha * 2.4);
  if (bucket.rich) {
    ctx.globalAlpha = Math.min(1, alpha * 0.22);
    ctx.fill(bucket.glows);
    ctx.fill(bucket.halos);
    ctx.globalAlpha = Math.min(1, alpha * 2.4);
  }
  ctx.fill(bucket.sparks);
  if (!bucket.rich) return;
  //: A white core is what makes it a spark rather than a mark, on either
  //: theme (the card's colour read as a hole in the dark graphspark.js shot).
  ctx.fillStyle = "#ffffff";
  ctx.fill(bucket.cores);
}

//: The pointed-at note's arrowed links carry a drifting spark, source to
//: target, one lap in 2.4s; only while pointed at, so an idle map stays idle.
function gcDrawDrift(ctx, drift, k) {
  const now = performance.now();
  for (const item of drift) {
    const c = item.bow || { x: (item.a.x + item.b.x) / 2, y: (item.a.y + item.b.y) / 2 };
    const p = gcQuadAt(item.a, c, item.b, (now / 2400) % 1);
    ctx.globalAlpha = 0.9;
    ctx.fillStyle = item.bucket.tint || gcTokens[item.bucket.style.colour] || gcTokens.muted;
    ctx.beginPath();
    ctx.arc(p.x, p.y, 2.4 / k, 0, Math.PI * 2);
    ctx.fill();
  }
}

function gcDrawEdgeHover(ctx, s, k, fadeStep, curved) {
  const hot = (s.edgeHot || []).filter((item) => item.edge !== s.hoverEdge);
  const current = (s.edgeHot || []).find((item) => item.edge === s.hoverEdge);
  if (s.hoverEdge) hot.push(current || { edge: s.hoverEdge, a: 0 });
  let fading = false;
  s.edgeHot = hot.filter((item) => {
    item.a = gcFadeToward(item.a, item.edge === s.hoverEdge ? 1 : 0, fadeStep);
    if (item.a > 0 && item.a < 1) fading = true;
    return item.a > 0;
  });
  for (const { edge, a: lit } of s.edgeHot) {
    const a = edge.source;
    const b = edge.target;
    if (!a || !b || !Number.isFinite(a.x) || !Number.isFinite(b.x)) continue;
    const style = edge.kind === "similar" ? GC_SIMILAR_BANDS[2] : gcEdgeStyle(edge);
    const tint = edge.kind !== "similar" && a.colour && a.colour === b.colour ? a.colour : null;
    ctx.strokeStyle = tint || gcTokens[style.colour] || gcTokens.muted;
    ctx.globalAlpha = 0.9 * gcSmooth(lit);
    ctx.lineWidth = (style.width + 2) / k;
    ctx.setLineDash([]);
    ctx.beginPath();
    if (s.tree && edge._path2d) {
      ctx.stroke(edge._path2d);
      continue;
    }
    ctx.moveTo(a.x, a.y);
    if (curved && !s.tree) {
      const bow = gcBowPoint(a, b);
      ctx.quadraticCurveTo(bow.x, bow.y, b.x, b.y);
    } else ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
  return fading;
}

//: One similarity score pill, at `alpha` of its full strength.
function gcDrawPill(ctx, pill, k, alpha) {
  const { spot, w, h, text } = pill;
  ctx.globalAlpha = 0.94 * alpha;
  ctx.fillStyle = gcTokens.card;
  ctx.beginPath();
  ctx.roundRect(spot.left, spot.top, w, h, h / 2);
  ctx.fill();
  ctx.globalAlpha = alpha;
  ctx.lineWidth = 1 / k;
  ctx.strokeStyle = gcTokens.accent;
  ctx.stroke();
  ctx.fillStyle = gcTokens.accent;
  ctx.fillText(text, spot.x, spot.y);
  ctx.globalAlpha = 1;
}

//: Paints the labels, each at its own lit-ness (see GC_FADE_MS): the ones
//: placed this frame fade toward full, the ones placed last frame and not now
//: fade out where they were (held as an offset from their dot, so a settling
//: layout carries them), and a label that changed place or words leaves a
//: ghost of its old self fading out. The collision pass only ever sees this
//: frame's labels: a name on its way out holds no space. Says whether
//: anything is still mid-fade.
function gcDrawLabels(ctx, s, placed, fadeStep, k) {
  const lit = s.labelLit || new Map();
  if (!s.labelGhosts) s.labelGhosts = [];
  const next = new Map();
  let fading = false;
  const draws = [];
  for (const item of placed) {
    const node = s.byId.get(item.id);
    if (!node) continue;
    const dy = item.y - node.y;
    const key = `${item.align}|${Math.abs(dy) < 1e-6 ? 0 : Math.sign(dy)}|${item.text}`;
    if (node._labelSpot && node._labelA > 0 && node._labelSpot.key !== key) {
      s.labelGhosts.push({ node, spot: node._labelSpot, a: node._labelA });
      node._labelA = 0;
    }
    node._labelSpot = {
      key,
      dx: item.x - node.x,
      dy,
      align: item.align,
      text: item.text,
      box: { l: item.left - node.x, t: item.top - node.y, w: item.right - item.left, h: item.bottom - item.top },
    };
    node._labelA = gcFadeToward(node._labelA || 0, 1, fadeStep);
    if (node._labelA < 1) fading = true;
    next.set(node.id, node);
    draws.push({ node, spot: node._labelSpot, a: node._labelA, x: item.x, y: item.y });
  }
  const leaving = [];
  for (const [id, node] of lit) {
    if (next.has(id) || !node._labelSpot || !Number.isFinite(node.x)) continue;
    node._labelA = gcFadeToward(node._labelA || 0, 0, fadeStep);
    if (node._labelA <= 0) continue;
    fading = true;
    next.set(id, node);
    leaving.push({ node, spot: node._labelSpot, a: node._labelA });
  }
  s.labelGhosts = (s.labelGhosts || []).filter((ghost) => {
    ghost.a = gcFadeToward(ghost.a, 0, fadeStep);
    if (ghost.a <= 0 || !Number.isFinite(ghost.node.x)) return false;
    fading = true;
    leaving.push(ghost);
    return true;
  });
  s.labelLit = next;
  if (!draws.length && !leaving.length) return fading;
  ctx.font = `500 ${12 / k}px ${gcTokens.font}`;
  ctx.textBaseline = "middle";
  //: **A name stands on a plate, not a halo** (INBOX 493: "labels in white
  //: over the lines"). The 3px card-coloured stroke around each glyph left
  //: every line that ran under a name showing between the letters, chopped
  //: into a white outline of the word. The plate is the label's own box in
  //: the card's colour, nearly opaque and rounded, so a line that has to run
  //: under a name (one with no clear place, see `gcPlaceLabels`) stops at the
  //: plate's edge and the word reads on a clean ground. On the map's own
  //: ground the plate is the ground, so it is invisible except where it is
  //: doing that job. The ones leaving go down first, under the ones arriving.
  //: Off (Label backgrounds), the name is drawn on the old 3px card-coloured
  //: halo instead; the placement still keeps it clear of lines.
  const radius = 4 / k;
  const plates = gcLabelPlates(s);
  if (!plates) {
    ctx.lineJoin = "round";
    ctx.lineWidth = 3 / k;
    ctx.strokeStyle = gcTokens.card;
  }
  for (const draw of leaving.concat(draws)) {
    const x = draw.x ?? draw.node.x + draw.spot.dx;
    const y = draw.y ?? draw.node.y + draw.spot.dy;
    const box = draw.spot.box;
    const a = gcSmooth(draw.a) * (s.paintMode === "over" ? gcSmooth(draw.node._lit ?? 1) : 1);
    if (!plates) {
      ctx.globalAlpha = a;
      ctx.textAlign = draw.spot.align;
      ctx.strokeText(draw.spot.text, x, y);
    } else if (box) {
      ctx.globalAlpha = 0.88 * a;
      ctx.fillStyle = gcTokens.card;
      ctx.beginPath();
      ctx.roundRect(x - draw.spot.dx + box.l, y - draw.spot.dy + box.t, box.w, box.h, radius);
      ctx.fill();
    }
    ctx.globalAlpha = a;
    ctx.fillStyle = gcTokens.ink;
    ctx.textAlign = draw.spot.align;
    ctx.fillText(draw.spot.text, x, y);
  }
  ctx.globalAlpha = 1;
  return fading;
}

//: **A label's width, measured once per text, not once per zoom step**
//: (INBOX 424c). The label font is `12 / k` px so a label keeps its size on
//: screen, which made every frame of a wheel zoom a new font size, and the
//: per-node cache beside the call (text and size) a miss for every label:
//: measured at 4x CPU, sixteen wheel steps on a 400-note graph spent 152ms in
//: `measureText` alone. A glyph advance is proportional to the font size, so
//: the width is measured once at a fixed reference size and scaled. Keyed by
//: the text, and dropped whenever the font the tokens name changes (a theme
//: with its own typeface), so a width can never be for another font.
const GC_LABEL_REF_PX = 100;
const gcLabelWidths = new Map();
let gcLabelWidthFont = "";
let gcLabelMeasureCtx = null;

function gcLabelWidth(text, size) {
  const font = `500 ${GC_LABEL_REF_PX}px ${gcTokens.font}`;
  if (font !== gcLabelWidthFont || !gcLabelMeasureCtx) {
    gcLabelWidths.clear();
    gcLabelWidthFont = font;
    if (!gcLabelMeasureCtx) gcLabelMeasureCtx = document.createElement("canvas").getContext("2d");
    gcLabelMeasureCtx.font = font;
  }
  let width = gcLabelWidths.get(text);
  if (width === undefined) {
    width = gcLabelMeasureCtx.measureText(text).width;
    //: A bound, not an eviction policy: a notebook's labels are a few
    //: thousand strings at most, and this only stops a pathological one
    //: (labels that change on every frame) from growing without end.
    if (gcLabelWidths.size > 20000) gcLabelWidths.clear();
    gcLabelWidths.set(text, width);
  }
  return (width * size) / GC_LABEL_REF_PX;
}

//: **A name is cut at a word, and the pointed-at one is whole** (INBOX 443
//: (1), "labels truncated with ..."): every label was the first 21 characters
//: and an ellipsis, so "Fitness plan and the ..." and "Quarterly planning wi..."
//: stopped mid-word or on a dangling "the". Now the cut falls on a space (when
//: one is past the middle of the limit), a trailing small word or mark is
//: dropped, and the note under the pointer or the keyboard is shown in full
//: (up to GC_LABEL_FULL), which is where the full name is wanted.
const GC_LABEL_FULL = 56;
const GC_LABEL_SMALL_WORDS = new Set([
  "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for", "with", "from", "by", "is", "are", "how", "what", "why",
]);

function gcLabelCut(text, limit) {
  //: The word cut is the app's own `clipText` (shell-reminders.js); this only
  //: adds the small-word rule on top of it.
  const clipped = clipText(text, limit);
  if (!clipped.endsWith("…") || clipped === String(text).trim()) return clipped;
  const words = clipped.slice(0, -1).split(" ");
  while (words.length > 2 && GC_LABEL_SMALL_WORDS.has(words[words.length - 1].toLowerCase())) words.pop();
  return `${words.join(" ")}…`;
}

function gcLabelText(node, s = gcTab) {
  //: A hub (four links or more) has the room of its own halo and is the name
  //: the map is read by, so it keeps ten characters more than the crowd.
  const hub = (s.adj.get(node.id) || { size: 0 }).size >= 4;
  //: **A phone's names are shorter** (INBOX 1400: at the fit a 390 px map
  //: named 2 of 36 notes, `gm.js`): a 26-character name is 170 px there, near
  //: half the map's width, and the room pass turned nearly all of them away.
  //: Below `GC_LABEL_NARROW_W` the cut is `GC_LABEL_NARROW_CUT` characters
  //: (a hub's a few more); the whole name is on hover and in the panel.
  const narrow = !s.tree && s.dims && s.dims.w < GC_LABEL_NARROW_W;
  const limit = s.tree
    ? s.tree.arc ? 12 : s.tree.radial ? 16 : 30
    : narrow
      ? GC_LABEL_NARROW_CUT + (hub ? 6 : 0)
      : hub ? 36 : 26;
  const text = node.preview || "";
  const pointed = !s.tree && (node.id === s.hoveredId || node.id === gcKeyboardId(s));
  const cut = gcLabelCut(text, pointed ? GC_LABEL_FULL : limit);
  //: A title another note shares says where this one is filed, or, filed
  //: together, when it was written (INBOX 1300 C41).
  if (!s.dupTitles || !s.dupTitles.has(text)) return cut;
  const twin = (s.nodes || []).some((n) => n !== node && n.preview === text && (n.category || "") === (node.category || ""));
  const at = Date.parse(node.created_at || "");
  const where = twin && Number.isFinite(at) ? new Date(at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : node.category || "Unfiled";
  return `${cut} (${where})`;
}

//: The trace overlay. Drawn from the `graphTrace`/`graphTraceRoutes` state
//: that trace mode, the route chips and the readout (graph.js) fill in.
function gcDrawTrace(ctx, k, s = gcTab) {
  if (s.size !== "full") return;
  const routes = graphTraceRoutes.length
    ? graphTraceRoutes
    : graphTrace
      ? [{ steps: graphTrace.steps }]
      : [];
  if (!routes.length || !s.byId) return;
  const colours = [gcTokens.accent, gcTokens.ok, gcTokens.warn];
  const isArc = s.tree && s.tree.arc;
  const drawRoute = (route, index, selected) => {
    ctx.strokeStyle = colours[index % 3];
    ctx.globalAlpha = selected ? 0.85 : 0.42;
    ctx.lineWidth = (selected ? 4 : 2) / k;
    ctx.setLineDash(selected ? [] : [6 / k, 5 / k]);
    ctx.lineCap = "round";
    ctx.beginPath();
    for (const step of route.steps || []) {
      const from = s.byId.get(step.source);
      const to = s.byId.get(step.target);
      if (!from || !to || !Number.isFinite(from.x) || !Number.isFinite(to.x)) continue;
      if (isArc) {
        ctx.stroke(new Path2D(tracePath(from, to)));
      } else {
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
      }
    }
    if (!isArc) ctx.stroke();
  };
  routes.forEach((route, index) => {
    if (index === graphTraceIndex) return; // drawn last so it wins the overlap
    drawRoute(route, index, false);
  });
  if (routes[graphTraceIndex]) drawRoute(routes[graphTraceIndex], graphTraceIndex, true);
  ctx.globalAlpha = 1;
  ctx.setLineDash([]);
}

// --- hit-testing ----------------------------------------------------------------

//: A `d3.quadtree` over the node positions (§4: "Hit-testing via a quadtree,
//: not per-node DOM events"). Rebuilt lazily: marked dirty by every draw, and
//: actually rebuilt only when something asks what is under the pointer, which
//: is at most once a frame and only while the pointer is over the map.
function gcTreeIndex(s = gcTab) {
  if (s.quadtree && !s.quadtreeDirty) return s.quadtree;
  s.quadtree = d3
    .quadtree()
    .x((n) => n.x)
    .y((n) => n.y)
    .addAll(s.nodes.filter((n) => Number.isFinite(n.x) && Number.isFinite(n.y)));
  s.quadtreeDirty = false;
  return s.quadtree;
}

//: The node under a point given in world coordinates, or null. The search
//: radius is generous by exactly the slop a pointer needs at the current zoom:
//: a 4px dot at k=0.3 is a one-pixel target otherwise.
function gcNodeAtWorld(x, y, s = gcTab) {
  if (!s.nodes.length) return null;
  const slop = GC_SLOP_PX / ((s.transform && s.transform.k) || 1);
  const found = gcTreeIndex(s).find(x, y, GC_MAX_RADIUS + slop + 8);
  if (!found) return null;
  if (!gcVisibleAtTime(found, s)) return null;
  const distance = Math.hypot(found.x - x, found.y - y);
  return distance <= found.r + slop ? found : null;
}

function gcWorldPoint(event, s = gcTab) {
  const point = d3.pointer(event, s.canvas);
  const t = s.transform || d3.zoomIdentity;
  return t.invert(point);
}

//: The line under a point, for the hover and the link peek (the owner,
//: 2026-10-04: "I cant click on links to see their reason in the graph??").
//: Every relation drawn between two notes answers, not only a `link`: a
//: thread, a similarity and a map's reference have something to say too.
//: Linear over the edges: about 10,000 distance checks a pointer move on
//: 1,100 lines, and an index kept in step with a moving layout would cost
//: more. 8px either side of the line on screen at any zoom.
const GC_PEEK_KINDS = new Set(["link", "thread", "similar", "map"]);
function gcEdgeAtWorld(x, y, s = gcTab) {
  const tolerance = 8 / ((s.transform && s.transform.k) || 1);
  let best = null;
  let bestDistance = tolerance;
  const curved = !s.tree && gcCurvedLinks(s);
  for (const edge of s.edges) {
    if (!GC_PEEK_KINDS.has(edge.kind)) continue;
    const a = edge.source;
    const b = edge.target;
    if (!a || !b || !Number.isFinite(a.x) || !Number.isFinite(b.x)) continue;
    //: A line whose box (its ends, and the bow a curve stays inside) is out of
    //: reach is passed over before any distance is measured.
    const c = curved ? gcBowPoint(a, b, gcBowScratch) : a;
    if (
      x < Math.min(a.x, b.x, c.x) - tolerance ||
      x > Math.max(a.x, b.x, c.x) + tolerance ||
      y < Math.min(a.y, b.y, c.y) - tolerance ||
      y > Math.max(a.y, b.y, c.y) + tolerance
    ) {
      continue;
    }
    if (!gcVisibleAtTime(a, s) || !gcVisibleAtTime(b, s)) continue;
    let distance;
    if (curved) {
      //: Sampled along the curve it is drawn as: eight steps are a pixel or
      //: two of error on a 150px line, well inside the tolerance.
      distance = Infinity;
      for (let i = 0; i <= 8; i++) {
        const u = i / 8;
        const px = (1 - u) * (1 - u) * a.x + 2 * (1 - u) * u * c.x + u * u * b.x;
        const py = (1 - u) * (1 - u) * a.y + 2 * (1 - u) * u * c.y + u * u * b.y;
        distance = Math.min(distance, Math.hypot(px - x, py - y));
      }
    } else {
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const lengthSq = dx * dx + dy * dy || 1;
      let t = ((x - a.x) * dx + (y - a.y) * dy) / lengthSq;
      t = Math.max(0, Math.min(1, t));
      distance = Math.hypot(a.x + t * dx - x, a.y + t * dy - y);
    }
    if (distance < bestDistance) {
      bestDistance = distance;
      best = edge;
    }
  }
  return best;
}

// --- pointer, zoom and drag -----------------------------------------------------


function gcWireInteraction(s = gcTab) {
  if (s.wired || !s.canvas) return;
  s.wired = true;
  const selection = d3.select(s.canvas);

  const zoom = d3
    .zoom()
    .scaleExtent([0.05, 5])
    //: The default extent reads `clientWidth` on every gesture's first use: a forced layout (30ms on 2,000 notes).
    .extent(() => [[0, 0], [s.dims.w, s.dims.h]])
    .wheelDelta(zoomWheelDelta)
    // A drag that starts on a node moves the node; anywhere else pans. Without
    // this filter d3-zoom claims the gesture first and a node can never be
    // picked up.
    .filter((event) => {
      if (event.type === "wheel") return true;
      //: **The wheel pressed down pans from anywhere, over a node too** (B37:
      //: "pressing down the scroll wheel and dragging sometimes glitches a
      //: little initially"). Only the primary button was let through, so a
      //: middle drag moved the camera 1.8px of 93 and the press kept its
      //: default (Windows' autoscroll circle, below). The node drag declines
      //: any button but the primary on its own.
      if (event.button === 1) return true;
      if (event.button) return false;
      // Shift and drag on empty map is the lasso, not a pan.
      if (event.shiftKey) return false;
      const [x, y] = gcWorldPoint(event, s);
      //: Nor a topic's name plate in the force layout: that is its handle.
      return !gcNodeAtWorld(x, y, s) && !(s.layoutKind === "force" && gcPlateAtWorld(x, y, s));
    })
    .on("start", () => {
      s.panning = true;
      gcSetHovered(s, null);
      gcRequestDraw(s, true);
    })
    .on("zoom", (event) => {
      //: **A touch lasso is refused here rather than in `.filter`.** The
      //: filter runs once, at the start of the gesture, and a hold that arms
      //: the lasso (`gcArmTouchLasso`) happens 500ms *inside* a gesture
      //: d3-zoom has already claimed as a one-finger pan: by the time the
      //: lasso exists there is nothing left to filter. So the pan is thrown
      //: away while a lasso is being drawn, and d3's own stored transform is
      //: pinned back to what is on screen so the refusal cannot accumulate:
      //: every later move is measured from where the map actually is, and
      //: lifting the finger leaves the camera exactly where the hold found
      //: it. `__zoom` is the property `d3.zoomTransform` reads.
      if (s.lasso) {
        s.canvas.__zoom = s.transform;
        return;
      }
      // `sourceEvent` is set for a real gesture and null for a programmatic
      // transform, which is how "the user went to look at something" is told
      // apart from "the renderer framed the map".
      //: A gesture also cancels a pending fit balance (`gcBalanceFit`): the
      //: user has taken the camera, a late correction would yank it back.
      if (event.sourceEvent) {
        s.userZoomed = true;
        s.fitCheck = 0;
      }
      s.transform = event.transform;
      //: The camera alone moved: the frame is the scene, moved (`gcDrawComposed`).
      s.cameraAt = performance.now();
      gcRequestMinimapFrame(s);
    })
    .on("end", () => {
      s.panning = false;
      gcRequestDraw(s, true);
    });
  selection.call(zoom).on("dblclick.zoom", null);
  //: A middle press that keeps its default starts the page's autoscroll
  //: (Windows) before the first move; its release is a paste on Linux. The
  //: board refuses both the same way (`initWhiteboard`).
  //: Capture, because d3-zoom's own mousedown listener stops the event.
  s.canvas.addEventListener("mousedown", (event) => {
    if (event.button === 1) event.preventDefault();
  }, true);
  s.canvas.addEventListener("auxclick", (event) => {
    if (event.button === 1) event.preventDefault();
  }, true);

  // The rest of the app drives zoom through `graphSvg`/`graphZoom`, the
  // +/-/fit buttons, the keyboard, the minimap, saved views, `fitGraphToView`.
  // Pointing those two at the canvas is what makes every one of them keep
  // working without a line of change: `d3.zoom` does not care what element it
  // is attached to, and `d3.zoomTransform` reads the transform off the node.
  //: Only the tab publishes them. A pane keeps its camera on its own surface,
  //: so the zoom strip and the minimap go on driving the tab while a pane is
  //: open beside a note.
  s.svg = selection;
  s.zoom = zoom;
  if (s.size === "full") {
    graphSvg = selection;
    graphZoom = zoom;
  }

  selection.call(
    d3
      .drag()
      // **The canvas, not its parent.** d3-drag's default container is
      // `this.parentNode`, so without this the pointer would be measured
      // against `#graph-box` while the subject's coordinates are measured
      // against the canvas: an offset that is zero today and stops being zero
      // the moment anything is laid out above the canvas inside the box.
      .container(() => s.canvas)
      .subject((event) => {
        //: **Nothing is dragged in a computed layout.** A tree, a ring or an
        //: arc *is* its shape, and a node pulled out of it makes the picture
        //: a lie; the position also comes back on the next relayout, so the
        //: gesture would not even hold. A null subject means d3-drag declines
        //: the gesture and the zoom behaviour keeps the pointer, so panning
        //: still works where a drag used to start.
        if (s.layoutKind !== "force") return null;
        const [x, y] = gcWorldPoint(event, s);
        const node = gcNodeAtWorld(x, y, s);
        //: A topic's name plate is its handle (the owner, 2026-10-10: "I
        //: want to be able to drag whole topics around on the graph"): the
        //: drag takes the topic's most linked note and carries the rest.
        const topic = node ? null : gcPlateAtWorld(x, y, s);
        const held = node || (topic && gcTopicCore(topic, s));
        if (!held) return null;
        const [sx, sy] = (s.transform || d3.zoomIdentity).apply([held.x, held.y]);
        return { node: held, topic, x: sx, y: sy };
      })
      //: **A press is not a drag until it has moved** (INBOX 587, the owner:
      //: "when I click nodes on the graph, it moves the graph slightly??").
      //: d3-drag says `start` on the press itself, and the press used to pin
      //: the node, freeze the map but its neighbours and tell the worker a
      //: drag had begun, which reheats the simulation: every click on a note
      //: set its neighbours moving and the layout drifted a little each time.
      //: Now `start` only remembers the press; the drag begins once the
      //: pointer is `GC_DRAG_THRESHOLD_PX` from it (`gcDragBegin`, with the
      //: press's own event, so the node is taken from where it was), and a
      //: press that never travels is a click, which tells the worker nothing.
      .on("start", (event) => {
        event.subject.pressed = event;
      })
      .on("drag", (event) => {
        const pressed = event.subject.pressed;
        if (pressed) {
          if (Math.hypot(event.x - pressed.x, event.y - pressed.y) < GC_DRAG_THRESHOLD_PX) return;
          event.subject.pressed = null;
          gcDragBegin(pressed);
        }
        gcDragMove(event);
      })
      .on("end", (event) => {
        if (event.subject.pressed) {
          event.subject.pressed = null;
          //: A click. `holdFired` is a long press that opened the node's menu
          //: (see `gcDragEnd`).
          if (s.holdFired) {
            // a hold opened the node's menu: nothing more
          } else if (event.subject.topic) gcOpenTopic(event.subject.topic);
          else gcClickNode(event.sourceEvent, event.subject.node, s);
          gcRequestDraw(s);
          return;
        }
        gcDragEnd(event);
      })
  );

  function gcDragBegin(event) {
    const node = event.subject.node;
    s.dragNode = node;
    node._dragStartX = node.x;
    node._dragStartY = node.y;
    node._wasPinned = node.fx != null;
    //: **Shift is what pins.** INBOX 96, the owner: "my original annoyance
    //: was that I'd try to drag a node or cluster around and it would just
    //: snap back ... but I move a node a little and then I have to unpin
    //: it and there's got to be a better way." Both halves of that are one
    //: rule: a plain drag places a node and lets the map settle around it,
    //: an explicit pin holds it against the simulation for good. Read at
    //: `start` rather than at `end` because the modifier is part of the
    //: gesture the reader began, and a Shift pressed or released mid-drag
    //: would otherwise change what the gesture meant halfway through.
    node._dragShift = Boolean(event.sourceEvent && event.sourceEvent.shiftKey);
    //: **Alt is what links** (audit 1029 G15: a plain drag onto another note
    //: opened "How are these connected?"). Shift already pins, so the link
    //: takes the other modifier, read here for the same reason.
    node._dragAlt = Boolean(event.sourceEvent && event.sourceEvent.altKey);
    //: A topic moved by its name stays where it is put, as a group: a
    //: released group would drift back into the layout one note at a time.
    s.dragTopic = event.subject.topic || null;
    if (s.dragTopic) node._dragShift = true;
    const [wx, wy] = (s.transform || d3.zoomIdentity).invert([event.x, event.y]);
    node.fx = wx;
    node.fy = wy;
    gcPost({ type: "drag", phase: "start", id: node.id, x: wx, y: wy }, s);
    //: **A lasso selection moves as one** (GRAPH_PLAN, "Decision changed,
    //: 2026-09-09", its one open line: "a dragged cluster moving together
    //: the same way"). Grabbing a note that is part of a selection of two
    //: or more carries the rest at their offsets from it, each under the
    //: same rule as the note in hand: a plain drag places, Shift pins, and
    //: a note that was pinned stays pinned at its new place. A note outside
    //: the selection drags alone, as it always has.
    const carriedNodes = s.dragTopic
      ? gcTopicMembers(s.dragTopic, s)
      : s.selected.has(node.id) && s.selected.size > 1
        ? gcSelectedNodes(s)
        : null;
    s.dragGroup =
      carriedNodes
        ? carriedNodes
            .filter((other) => other !== node && !other.isGroup)
            .map((other) => ({
              node: other,
              dx: other.x - node.x,
              dy: other.y - node.y,
              startX: other.x,
              startY: other.y,
              wasPinned: other.fx != null,
            }))
        : [];
    for (const mate of s.dragGroup) {
      mate.node.fx = wx + mate.dx;
      mate.node.fy = wy + mate.dy;
      gcPost({ type: "drag", phase: "start", id: mate.node.id, x: mate.node.fx, y: mate.node.fy }, s);
    }
    // **Everything holds still except this note's own neighbours.**
    //
    // Two rules were in conflict here and both are real. The SVG renderer
    // froze the entire map for the length of a drag, because drag-to-link
    // asks you to aim at a note and aiming at a moving target is not a
    // gesture: that was a direct report. But GRAPH_PLAN.md §3 asks for
    // the opposite thing, and it is the whole point of this phase:
    // "dragging feels physical (the neighbours follow and the rest
    // settles)". Freezing everything makes a drag a pointer-follow with a
    // simulation running behind it that cannot move anything.
    //
    // Freezing everything *except the direct neighbourhood* satisfies both:
    // the notes attached to the one in your hand come along, which is the
    // physicality, and every other note on the map holds the position you
    // are aiming at, which is the gesture.
    const following = s.adj.get(node.id) || new Set();
    const carried = new Set(s.dragGroup.map((mate) => mate.node.id));
    gcPost({
      type: "freeze",
      ids: s.nodes
        .filter((n) => n !== node && n.fx == null && !following.has(n.id) && !carried.has(n.id))
        .map((n) => n.id),
    }, s);
  }

  function gcDragMove(event) {
    const node = event.subject.node;
    const [wx, wy] = (s.transform || d3.zoomIdentity).invert([event.x, event.y]);
    node.fx = wx;
    node.fy = wy;
    node.x = wx;
    node.y = wy;
    s.quadtreeDirty = true;
    gcPost({ type: "drag", phase: "move", id: node.id, x: wx, y: wy }, s);
    for (const mate of s.dragGroup) {
      mate.node.fx = mate.node.x = wx + mate.dx;
      mate.node.fy = mate.node.y = wy + mate.dy;
      gcPost({ type: "drag", phase: "move", id: mate.node.id, x: mate.node.fx, y: mate.node.fy }, s);
    }
    s.dropTarget = gcDropTargetFor(s, node, { x: wx, y: wy });
    gcRequestDraw(s);
  }

  function gcDragEnd(event) {
    const node = event.subject.node;
    s.dragNode = null;
    const over = s.dropTarget;
    s.dropTarget = null;
    const movedFar =
      Math.abs(node.x - node._dragStartX) > 2 || Math.abs(node.y - node._dragStartY) > 2;
    //: A plain drag places the node and releases it: the worker's own
    //: `keep: false` path clears `fx`/`fy` and lets `alphaTarget(0)`
    //: decay, so the node settles from where it was dropped with its
    //: neighbours rather than snapping back to where it came from. That
    //: decay is the "better way" the report asks for, and it was already
    //: written; what was wrong is that a moved node never reached it,
    //: because any drag over 2px counted as a pin.
    //:
    //: A zero-distance drag is still a click and pins nothing, and a node
    //: that was already pinned stays pinned at its new place: dragging a
    //: pinned node is a reposition, not a request to release it.
    const keep = node._dragShift || node._wasPinned;
    gcPost({ type: "drag", phase: "end", id: node.id, keep }, s);
    const pins = [];
    const steps = [];
    for (const mate of s.dragGroup) {
      const mateKeeps = node._dragShift || mate.wasPinned;
      gcPost({ type: "drag", phase: "end", id: mate.node.id, keep: mateKeeps }, s);
      const mateMoved =
        Math.abs(mate.node.x - mate.startX) > 2 || Math.abs(mate.node.y - mate.startY) > 2;
      if (!mateKeeps) {
        mate.node.fx = null;
        mate.node.fy = null;
      } else if (mateMoved) {
        //: The same "only a real pin is written down" rule as the note in
        //: hand, below.
        mate.node.graph_pin_x = mate.node.fx;
        mate.node.graph_pin_y = mate.node.fy;
        pins.push({ id: mate.node.id, x: mate.node.fx, y: mate.node.fy });
        steps.push({ id: mate.node.id, before: mate.wasPinned ? { x: mate.startX, y: mate.startY } : null, after: { x: mate.node.fx, y: mate.node.fy } });
      }
    }
    //: One write for the carried notes (`PUT /graph/pins`): a topic of forty
    //: was forty requests.
    const savePins = () => apiJson("/graph/pins", { method: "PUT", body: JSON.stringify({ pins }) })
      .catch(() => toast("The moved notes were not pinned where you left them.", true, { action: ["Try again", savePins] }));
    s.dragGroup = [];
    const wasTopic = s.dragTopic;
    s.dragTopic = null;
    gcPost({ type: "thaw" }, s);
    if (!keep) {
      node.fx = null;
      node.fy = null;
    }
    if (over && movedFar) {
      linkByDrop(node, over);
    } else if (!movedFar && !s.holdFired) {
      //: **A hold is not a tap that took a while.** In a force layout a
      //: click on a node *is* a zero-distance drag, and this is where it
      //: is turned into one, so a long press that opened the node's menu
      //: ended here as well and opened that node's panel underneath it:
      //: measured at 390, the menu was still on screen with the panel in
      //: front of it holding the focus. `holdFired` is set by the hold
      //: and cleared by the next press on the canvas
      //: (`gcWireNodeMenu`), so it says "this gesture was a hold" and
      //: nothing about the one after it.
      if (wasTopic) gcOpenTopic(wasTopic);
      else gcClickNode(event.sourceEvent, node, s);
    } else if (!node.isGroup && keep) {
      //: Only a real pin is written down. A placement that the simulation
      //: is free to relax has no position worth surviving a reload, and
      //: saving one was what made every small nudge into a pin the reader
      //: then had to find and undo.
      node.graph_pin_x = node.fx;
      node.graph_pin_y = node.fy;
      //: A topic carried by its core note is one write with its mates
      //: (ledger 931: it was the group's PUT plus this one).
      steps.push({
        id: node.id,
        before: node._wasPinned ? { x: node._dragStartX, y: node._dragStartY } : null,
        after: { x: node.fx, y: node.fy },
      });
      if (pins.length) pins.push({ id: node.id, x: node.fx, y: node.fy });
      else graphPinSave(node.id, node.graph_pin_x, node.graph_pin_y).catch(() => {
        // Best-effort, exactly as on the SVG path: the placement has
        // already taken effect in memory, so a failed save costs the
        // reload and nothing else.
      });
    }
    if (steps.length) graphPinStep(steps.length === 1 ? "Moved a pinned note" : `Moved ${steps.length} pinned notes`, steps);
    if (pins.length) savePins();
    gcRequestDraw(s);
  }

  s.canvas.addEventListener("pointermove", (event) => {
    if (s.panning || s.dragNode) return;
    const [x, y] = gcWorldPoint(event, s);
    const node = gcNodeAtWorld(x, y, s);
    const id = node ? node.id : null;
    //: A line answers the pointer only where no note does, and only on the
    //: tab, whose click opens the peek (`openGraphLinkPeek`, graph.js).
    const edge = !node && s.size === "full" ? gcEdgeAtWorld(x, y, s) : null;
    //: A topic's name plate says what it does (the owner could not find how
    //: to rename one): the hand cursor, and the two gestures on its title.
    const plate = !node && !edge && s.size === "full" ? gcPlateAtWorld(x, y, s) : null;
    if (plate !== s.hoverPlate) {
      s.hoverPlate = plate;
      s.canvas.classList.toggle("graph-plate-hover", Boolean(plate) && s.layoutKind === "force");
      if (!node && !edge) s.canvas.title = gcPlateTitle(plate, s);
    }
    if (id !== s.hoveredId || edge !== s.hoverEdge) {
      if (id !== s.hoveredId) {
        gcSetHovered(s, id);
        gcHoverChanged(id, s);
      }
      s.hoverEdge = edge;
      s.canvas.classList.toggle("graph-edge-hover", Boolean(edge));
      // The native tooltip the SVG renderer got from a `<title>` child. A
      // canvas has no children, so the canvas itself carries whichever one
      // applies.
      //: On the tab a note answers with its hover card (`gcHoverCardFrame`),
      //: so the native tooltip is only the pane's.
      s.canvas.title = node ? (s.size === "full" ? "" : gcTooltip(node, s)) : edge ? "Click to see this connection" : gcPlateTitle(plate, s);
      gcRequestDraw(s, true);
    }
  });
  s.canvas.addEventListener("pointerleave", () => {
    if (s.hoveredId == null && !s.hoverEdge && !s.hoverPlate) return;
    gcSetHovered(s, null);
    gcHoverChanged(null, s);
    s.hoverEdge = null;
    s.hoverPlate = null;
    s.canvas.classList.remove("graph-edge-hover", "graph-plate-hover");
    s.canvas.title = "";
    gcRequestDraw(s, true);
  });

  s.canvas.addEventListener("click", (event) => {
    const [x, y] = gcWorldPoint(event, s);
    const hit = gcNodeAtWorld(x, y, s);
    if (hit) {
      //: **A node is clicked here in every layout but force.** Reported:
      //: "the note node popups dont show on any of the graph views when I
      //: click on a node except for the force view." In a force layout a
      //: click on a node is a zero-distance drag, and d3-drag's `end`
      //: turns it into one (`gcClickNode`), which is why this used to
      //: return. But a computed layout has no drag at all: `subject()`
      //: deliberately returns null for tree, radial and arc so a node
      //: cannot be pulled out of a shape that *is* the meaning, and with
      //: no drag there is no `end` and nothing ever opened the popup.
      //: The click event is the only thing those three layouts get, so it
      //: is where their click lives.
      if (s.layoutKind === "force" || s.holdFired) return;
      gcClickNode(event, hit, s);
      return;
    }
    //: The link panel, the node popup and the new-note form are the Graph
    //: tab's, and all three are placed against `#graph-box`. A pane that
    //: opened one would put it over a map on another tab.
    if (s.size !== "full") return;
    //: In force a plate's click is the drag's (`gcOpenTopic` at its end).
    const plate = s.layoutKind === "force" ? null : gcPlateAtWorld(x, y, s);
    if (plate) {
      gcOpenTopic(plate);
      return;
    }
    const edge = gcEdgeAtWorld(x, y, s);
    if (edge) {
      openGraphLinkPeek(edge, event, s.nodes);
      return;
    }
    closeGraphLinkPeek();
    closeGraphPopup();
    closeGraphNewNote();
  });

  s.canvas.addEventListener("dblclick", (event) => {
    const [x, y] = gcWorldPoint(event, s);
    const node = gcNodeAtWorld(x, y, s);
    const plate = node || s.size !== "full" ? null : gcPlateAtWorld(x, y, s);
    if (plate) {
      gcRenameTopicInline(plate);
      return;
    }
    if (!node) {
      // Grow the map: double-click empty space to add a note right there.
      //: The tab only, same reason as the click above: the form is placed
      //: against the tab's own box.
      if (s.size === "full") openGraphNewNote(event);
      return;
    }
    //: A double click in a computed layout used to clear that one node's
    //: `fx`/`fy` and hand it to the force simulation, which then re-solved
    //: from there and pulled the rest of the tree apart with it: reported as
    //: "I test double clicked on a node and it broke them all out of
    //: position". There is no pin to toggle where every position is computed.
    if (s.layoutKind !== "force") return;
    gcTogglePin(node, s);
  });
  //: The lasso, the right-click menu and the selection dock all read elements
  //: that exist once, on the Graph tab. A pane wires none of them.
  if (s.size === "full") {
    gcWireLasso(s);
    gcWireNodeMenu(s);
    gcWireSelectionDock(s);
  }
}

function gcTogglePin(node, s = gcTab) {
  const wasPinned = node.fx != null;
  if (wasPinned) {
    node.fx = null;
    node.fy = null;
    gcPost({ type: "unpin", id: node.id }, s);
  } else {
    node.fx = node.x;
    node.fy = node.y;
    gcPost({ type: "pin", id: node.id, x: node.x, y: node.y }, s);
  }
  gcRequestDraw(s);
  if (node.isGroup) return;
  node.graph_pin_x = wasPinned ? null : node.fx;
  node.graph_pin_y = wasPinned ? null : node.fy;
  graphPinStep(wasPinned ? "Unpinned a note" : "Pinned a note", [{
    id: node.id,
    before: wasPinned ? { x: node.x, y: node.y } : null,
    after: node.graph_pin_x == null ? null : { x: node.graph_pin_x, y: node.graph_pin_y },
  }]);
  graphPinSave(node.id, node.graph_pin_x, node.graph_pin_y).catch(() => {
  });
}

// --- Phase 4: the lasso ----------------------------------------------------------
function gcPointInPolygon(x, y, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, yi] = points[i];
    const [xj, yj] = points[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

//: **The lasso on a phone** (Phase 11 item 4). Its desktop gesture is Shift
//: and drag, and a finger has no Shift, so the hold `gcWireNodeMenu` wires
//: arms it instead: hold on empty map, then drag the shape you want. Called
//: from there rather than wiring a second hold here, so there is one hold on
//: this canvas and one place that decides what is under it.
//:
//: The hint is said once a session, because the first hold on empty map is
//: the only one that needs telling: after that the shape drawing under the
//: finger says it.
let gcLassoHintSaid = false;

function gcArmTouchLasso(event, x, y, s = gcTab) {
  if (s.lasso || s.size !== "full") return;
  s.lasso = { points: [[x, y]] };
  try {
    s.canvas.setPointerCapture(event.pointerId);
  } catch {
    // A pointer already lifted cannot be captured; the lasso still draws.
  }
  gcRequestDraw(s);
  if (!gcLassoHintSaid && typeof toast === "function") {
    gcLassoHintSaid = true;
    toast("Drag to select notes");
  }
}

//: A rectangle's four corners from its start and the pointer (K10: Shift and
//: drag is a box; a straight drag as a freehand loop encloses nothing).
function gcBoxPoints(from, to) {
  return [from, [to[0], from[1]], to, [from[0], to[1]]];
}

function gcWireLasso(s = gcTab) {
  s.canvas.addEventListener("pointerdown", (event) => {
    if (!event.shiftKey || event.button) return;
    const [x, y] = gcWorldPoint(event, s);
    if (gcNodeAtWorld(x, y, s)) return;
    s.lasso = { points: [[x, y]], box: true, from: [x, y] };
    s.canvas.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  s.canvas.addEventListener("pointermove", (event) => {
    if (!s.lasso) return;
    if (s.lasso.box) s.lasso.points = gcBoxPoints(s.lasso.from, gcWorldPoint(event, s));
    else s.lasso.points.push(gcWorldPoint(event, s));
    gcRequestDraw(s);
  });
  const finish = (event) => {
    if (!s.lasso) return;
    const points = s.lasso.points;
    s.lasso = null;
    try {
      s.canvas.releasePointerCapture(event.pointerId);
    } catch {
    }
    if (points.length > 2) {
      const caught = s.nodes.filter((n) => !n.isGroup && gcPointInPolygon(n.x, n.y, points)).map((n) => n.id);
      // A second Shift-lasso adds to the first, so two sweeps build one selection.
      for (const id of caught) s.selected.add(id);
    }
    gcSelectionChanged(s);
    gcRequestDraw(s);
  };
  s.canvas.addEventListener("pointerup", finish);
  s.canvas.addEventListener("pointercancel", finish);
}

function gcDrawSelection(ctx, k, s = gcTab) {
  if (s.selected.size) {
    ctx.save();
    ctx.globalAlpha = 1;
    ctx.strokeStyle = gcTokens.accent;
    ctx.lineWidth = 3 / k;
    ctx.setLineDash([4 / k, 3 / k]);
    for (const node of s.nodes) {
      if (!s.selected.has(node.id)) continue;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r + 5 / k, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }
  if (s.lasso && s.lasso.points.length > 1) {
    ctx.save();
    ctx.beginPath();
    s.lasso.points.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath();
    ctx.fillStyle = gcTokens.accent;
    ctx.globalAlpha = 0.08;
    ctx.fill();
    ctx.globalAlpha = 0.9;
    ctx.strokeStyle = gcTokens.accent;
    ctx.lineWidth = 1.5 / k;
    ctx.setLineDash([6 / k, 4 / k]);
    ctx.stroke();
    ctx.restore();
  }
}

// --- Phase 4: the selection dock ---------------------------------------------------
function gcSelectionChanged(s = gcTab) {
  const dock = document.getElementById("graph-selection-dock");
  const count = document.getElementById("graph-selection-count");
  if (!dock || !count) return;
  const live = [...s.selected].filter((id) => s.byId.has(id));
  s.selected = new Set(live);
  dock.classList.toggle("hidden", !live.length);
  count.textContent = `${live.length} selected`;
  //: Pins hold in the force layout only: the others compute every position.
  const force = s.layoutKind === "force";
  for (const id of ["graph-selection-pin", "graph-selection-unpin"]) {
    const button = document.getElementById(id);
    if (!button) continue;
    button.disabled = !force;
    button.title = force
      ? (id.endsWith("unpin") ? "Let the selected notes move freely again (undoable)" : "Hold the selected notes where they are (undoable)")
      : "Pins only hold in the Force layout";
  }
}

//: Pin or unpin every selected note in one step (K10): one undo, one write.
//: The same bookkeeping as `gcTogglePin`, for a set.
function gcPinSelection(s, pinned) {
  const changes = [];
  for (const node of gcSelectedNodes(s)) {
    if (node.isGroup || (node.fx != null) === pinned) continue;
    const before = node.graph_pin_x == null ? null : { x: node.graph_pin_x, y: node.graph_pin_y };
    node.fx = pinned ? node.x : null;
    node.fy = pinned ? node.y : null;
    gcPost(pinned ? { type: "pin", id: node.id, x: node.x, y: node.y } : { type: "unpin", id: node.id }, s);
    node.graph_pin_x = pinned ? node.fx : null;
    node.graph_pin_y = pinned ? node.fy : null;
    changes.push({ id: node.id, before, after: pinned ? { x: node.x, y: node.y } : null });
  }
  gcRequestDraw(s);
  if (!changes.length) return toast(pinned ? "Those notes are already pinned." : "None of those notes are pinned.");
  const saved = changes.filter((c) => /^(document:)?\d+$/.test(String(c.id)));
  const write = pinned
    ? apiJson("/graph/pins", { method: "PUT", body: JSON.stringify({ pins: saved.map((c) => ({ id: c.id, x: c.after.x, y: c.after.y })) }) })
    : Promise.all(saved.map((c) => graphPinSave(c.id, null, null)));
  if (saved.length) write.catch(() => toast("The pins were not saved.", true));
  const words = nounCount(changes.length, "note");
  graphPinStep(pinned ? `Pinned ${words}` : `Unpinned ${words}`, changes);
  toast(pinned ? `Pinned ${words}.` : `Unpinned ${words}.`);
}

function gcSelectedNodes(s = gcTab) {
  return [...s.selected].map((id) => s.byId.get(id)).filter(Boolean);
}

function gcWireSelectionDock(s = gcTab) {
  const on = (id, fn) => document.getElementById(id)?.addEventListener("click", fn);
  on("graph-selection-clear", () => {
    s.selected.clear();
    gcSelectionChanged(s);
    gcRequestDraw(s);
  });
  on("graph-selection-pin", () => gcPinSelection(s, true));
  on("graph-selection-unpin", () => gcPinSelection(s, false));
  on("graph-selection-tag", async () => {
    const nodes = gcSelectedNodes(s);
    if (!nodes.length) return;
    const tag = (await promptDialog("Tag these notes", "", { confirmLabel: "Add tag" })).trim().replace(/^#/, "");
    if (!tag) return;
    let done = 0;
    const changes = [];
    for (const node of nodes) {
      const tags = Array.from(new Set([...(node.tags || []), tag]));
      const wasTags = [...(node.tags || [])];
      // PUT: the entries route has no PATCH, and EntryUpdate leaves every
      // field it is not given alone.
      const ok = await apiJson(`/entries/${node.id}`, { method: "PUT", body: JSON.stringify({ tags }) }).catch(() => null);
      if (ok) {
        node.tags = tags;
        done += 1;
        changes.push({ id: node.id, before: { tags: wasTags }, after: { tags } });
      }
    }
    if (changes.length) pushEntriesPutUndo(`Tagged ${nounCount(changes.length, "note")} #${tag}`, changes, () => renderGraph());
    toast(`Tagged ${nounCount(done, "note")} #${tag}.`);
    renderGraph();
  });
  on("graph-selection-link", async () => {
    const nodes = gcSelectedNodes(s);
    if (nodes.length < 2) {
      toast("Select at least two notes to link them.");
      return;
    }
    // Pairwise up to six notes (fifteen links); past that a hub, every note
    // linked to the first, which keeps the map readable.
    const pairs = [];
    if (nodes.length <= 6) {
      for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) pairs.push([nodes[i], nodes[j]]);
    } else {
      for (let i = 1; i < nodes.length; i++) pairs.push([nodes[0], nodes[i]]);
    }
    //: **Undoable, like every other bulk change** (INBOX 690, the owner: "I
    //: highlighted a bunch of notes on the graph and pressed link together
    //: but now I cant undo it"). Each made link is kept by its id, so the
    //: undo removes exactly those and no link that was already there.
    const made = [];
    for (const [a, b] of pairs) {
      if (s.adj.get(a.id)?.has(b.id)) continue;
      const ok = await apiJson(`/entries/${a.id}/links`, { method: "POST", body: JSON.stringify({ target_id: b.id }) }).catch(() => null);
      const linkId = ok?.links?.find((link) => link.entry_id === b.id)?.link_id;
      if (linkId != null) made.push({ from: a.id, to: b.id, linkId });
    }
    renderGraph();
    if (!made.length) return toast("Those notes were already linked.");
    const words = nounCount(made.length, "pair");
    const action = pushUndo(`Linked ${words} on the graph`, () => gcUnlinkPairs(made), () => gcRelinkPairs(made));
    toastAction(`Linked ${words}.`, "Undo", async () => {
      settleUndoFromToast(action);
      await gcUnlinkPairs(made);
    });
  });
  //: The other half of Link together: every link between the selected
  //: notes goes, undoable (INBOX 690: links already made, before the undo
  //: above existed, can be taken back the same way they were made).
  on("graph-selection-unlink", async () => {
    const nodes = gcSelectedNodes(s).filter((node) => Number.isInteger(node.id));
    const ids = new Set(nodes.map((node) => node.id));
    const gone = [];
    for (const node of nodes) {
      const entry = await apiJson(`/entries/${node.id}`).catch(() => null);
      for (const link of entry?.links || []) {
        if (!ids.has(link.entry_id) || gone.some((g) => g.linkId === link.link_id)) continue;
        gone.push({ from: node.id, to: link.entry_id, linkId: link.link_id, reason: link.reason || null });
      }
    }
    if (!gone.length) return toast("None of the selected notes are linked to each other.");
    await gcUnlinkPairs(gone);
    const words = nounCount(gone.length, "link");
    const action = pushUndo(`Removed ${words} on the graph`, () => gcRelinkPairs(gone), () => gcUnlinkPairs(gone));
    toastAction(`Removed ${words}.`, "Undo", async () => {
      settleUndoFromToast(action);
      await gcRelinkPairs(gone);
    });
  });
  on("graph-selection-map", async () => {
    //: Notes only: a lens can put tags, categories and boards on the graph
    //: as nodes of their own, and none of those is a note a map can hold.
    const nodes = gcSelectedNodes(s).filter((node) => Number.isInteger(node.id));
    if (!nodes.length) return;
    const name = (await promptDialog("Name the mind map", "", { confirmLabel: "Create map" })).trim();
    if (!name) return;
    //: **Built from the graph, not listed under one topic** (INBOX 607, the
    //: owner: "surely there's a better and more dynamic way it can build the
    //: map based off the connections and links"). The links between the
    //: chosen notes go too, as the graph draws them, and the server builds
    //: the tree they describe: the picked or most connected note in the
    //: middle, linked notes under the note they link to, the rest by
    //: category, every link the tree cannot hold kept as a cross-link
    //: (`routes_map_from_notes.py`). It was one root with every note in a
    //: single column under it, and the links thrown away.
    const ids = new Set(nodes.map((node) => node.id));
    const edges = [];
    for (const id of ids) {
      for (const other of s.adj.get(id) || []) if (ids.has(other) && id < other) edges.push([id, other]);
    }
    const picked = [graphFocusModeId, graphPaneShownId].find((id) => ids.has(id)) ?? null;
    const board = await apiJson("/whiteboard/maps/from-notes", {
      method: "POST",
      body: JSON.stringify({ name, note_ids: [...ids], edges, root_id: picked }),
    }).catch(() => null);
    if (!board?.id) {
      toast("Could not create the map.");
      return;
    }
    pushBinPairUndo(`Made the mind map “${name}”`, `/entries/${board.id}`, `/entries/${board.id}/restore`, true, () => (typeof refreshBoardList === "function" ? refreshBoardList() : null));
    //: **The way to it, on the notice and in the bell** (INBOX 607: "the
    //: notification included no link to it"). Open lays the map out against
    //: its topics' real sizes as it opens, the step an import takes too.
    toastAction(
      `Mind map \u201c${name}\u201d made from ${nounCount(ids.size, "note")}.`,
      "Open",
      async () => {
        await openWhiteboardBoard(board.id);
        await wbMapTidyFresh();
      },
      { go: { open: "board", id: board.id } },
    );
  });
}

// --- Phase 4: the right-click menu, and Phase 11's hold ------------------------------
function gcCloseNodeMenu() {
  closeActionMenus();
}

function gcWireNodeMenu(s = gcTab) {
  s.canvas.addEventListener("contextmenu", (event) => {
    const [x, y] = gcWorldPoint(event, s);
    const node = gcNodeAtWorld(x, y, s);
    if (!node || node.isGroup) return;
    event.preventDefault();
    gcShowNodeMenu(node, event.clientX, event.clientY, s);
  });
  //: **A finger has no second button** (UI_MODERNISATION_PLAN Phase 11 item
  //: 4: "long-press for the node menu (no right click), lasso by long-press
  //: then drag"). One hold, wired once, answering both: what is under the
  //: press decides which. A node gets the same menu a right-click opens; the
  //: empty map arms the lasso, which is the other thing this canvas has that
  //: a phone could not reach at all, because its desktop gesture is Shift
  //: and drag. `wireLongPress` (navigation.js) is the app's one hold: touch only,
  //: 500ms, cancelled by a move, so the app answers a hold at one speed
  //: everywhere. `tests/test_ui_recipes.py` counts this file's contextmenu
  //: listeners against its `wireLongPress` calls.
  //: Cleared at the start of every press and set by the hold below, so the
  //: two places a tap on a node is turned into an open (d3-drag's `end` in a
  //: force layout, the canvas `click` in the computed ones) can tell a hold
  //: from a slow tap without a timer of their own.
  s.canvas.addEventListener("pointerdown", () => {
    s.holdFired = false;
  });
  wireLongPress(s.canvas, (event, point) => {
    s.holdFired = true;
    const [x, y] = gcWorldPoint(event, s);
    const node = gcNodeAtWorld(x, y, s);
    if (node && !node.isGroup) {
      gcShowNodeMenu(node, point.x, point.y, s);
      return;
    }
    gcArmTouchLasso(event, x, y, s);
  });
  //: On the canvas, not the window: a wheel over the map zooms it out from
  //: under the menu's node, which is the case this closes for. On the window
  //: it ran on every wheel tick on every tab (traced: 49ms over one scroll of
  //: Reminders), and closed the node menu when the wheel was over the menu
  //: itself.
  s.canvas.addEventListener("wheel", gcCloseNodeMenu, { passive: true });
}

//: **The menu at the pointer is the app's own recipe** (DESIGN.md, "A menu at
//: the pointer"). This was a hand-built `.action-menu` with its own rows, its
//: own clamp against the window and its own three closers, written before
//: `openMenuAtPoint` existed. It is the same object: `kebabMenu`'s rows on a
//: one-pixel anchor parked where the press was, which brings the clamp that
//: measures and corrects, the arrow keys, Escape, the outside press, and the
//: 44px row the touch band gives every menu in the app, none of which the
//: hand-built one had. The `graph-node-menu` class stays on the opened menu:
//: it carries the 13rem minimum width that keeps "Remove from selection" on
//: one line, and `scratchpad/ui-sweeps/graph4.js` reads the menu by it.
function gcShowNodeMenu(node, clientX, clientY, s = gcTab) {
  const isNote = gcIsNote(node);
  const selected = s.selected.has(node.id);
  const items = [];
  if (isNote) {
    items.push({
      label: "ph:arrow-square-out Open",
      title: "Open this note in the notes list",
      run: () => flashEntry(node.id),
    });
  } else if (node.type === "attachment" || node.type === "document") {
    items.push({
      label: "ph:arrow-square-out Open",
      title: node.type === "document" ? "Open this document" : "Open this file",
      run: () => gcOpenNodeTarget(node),
    });
  }
  items.push({
    label: node.fx != null ? "ph:push-pin-slash Unpin" : "ph:push-pin Pin in place",
    title: node.fx != null ? "Let the layout move this note again" : "Keep this note where it is",
    run: () => gcTogglePin(node, s),
  });
  if (isNote) {
    items.push({
      label: "ph:crosshair Focus on this note",
      title: "Show only this note and what it connects to",
      run: () => {
        graphFocusModeId = node.id;
        renderGraph();
      },
    });
  }
  items.push({
    label: selected ? "ph:selection-slash Remove from selection" : "ph:selection-plus Add to selection",
    title: "The selection bar acts on every note in it at once",
    run: () => {
      if (s.selected.has(node.id)) s.selected.delete(node.id);
      else s.selected.add(node.id);
      gcSelectionChanged(s);
      gcRequestDraw(s);
    },
  });
  items.push({
    label: "ph:eye-slash Hide on this map",
    title: "Take this note off the map for this visit",
    run: () => {
      s.hiddenIds.add(node.id);
      s.selected.delete(node.id);
      gcSelectionChanged(s);
      renderGraph();
    },
  });
  openMenuAtPoint(items, "Note actions", clientX, clientY);
  document.querySelector(".action-menu:not(.hidden)")?.classList.add("graph-node-menu");
}

//: The word "entity" explains nothing on its own, and it is the label on a
//: switch, a legend entry and a node. INBOX 183, the owner: "idk what entities
//: are". One sentence, written once here, given in all three places.
const GC_ENTITY_CATEGORY = "Entity";
const GC_ENTITY_HELP =
  "An entity is a person, place or thing Atlas found named across your notes, " +
  "joined to every note that mentions it. Click it for its page";

//: **A note's hover card** (INBOX 1300 C11, the owner: "I wanna be able to
//: hover over and click graph nodes and see their values and dates etc").
//: What the card says, worked out apart from the DOM so it is tested in
//: node: the title, the category, the facts (dates, links, views, length),
//: the note's properties and its tags. `day` and `ago` format a date, so a
//: test passes its own clock. A node that is not a note says what it is.
function gcHoverCardFacts(node, entry, day, ago) {
  const card = { title: node.preview || "Untitled", sub: node.category || "", facts: [], props: [], tags: "", note: "" };
  const kinds = {
    entity: GC_ENTITY_HELP,
    document: "A document your notes are attached to",
    map: "A mind map, joined to the notes on it",
    tag: "A tag, joined to the notes that carry it",
    attachment: "A file on the note it is joined to",
    unresolved: "No note has this name yet. Click to write it",
    board: "A whiteboard, joined to the notes on it",
    whiteboard: "A whiteboard, joined to the notes on it",
  };
  if (kinds[node.type]) {
    card.note = kinds[node.type];
    return card;
  }
  if (node.created_at) card.facts.push(["Created", day(node.created_at)]);
  //: A person's last edit (`edited_at`), never `updated_at`, which the
  //: app's own writes (filing, a view count) also move.
  if (node.edited_at) card.facts.push(["Edited", ago(node.edited_at)]);
  const links = node._links || 0;
  card.facts.push(["Links", links ? String(links) : "None"]);
  card.facts.push(["Views", node.access_count ? String(node.access_count) : "Not opened yet"]);
  if (node.words) card.facts.push(["Words", String(node.words)]);
  for (const [key, values] of Object.entries((entry && entry.properties) || {}).slice(0, 5)) {
    const shown = (values || []).filter(Boolean).map((v) => String(v).replace(/^\[\[|\]\]$/g, ""));
    if (shown.length) card.props.push([key, shown.join(", ")]);
  }
  card.tags = (node.tags || []).slice(0, 6).map((t) => `#${t}`).join(" ");
  return card;
}

//: The card's element, built once into the map's box: `role="tooltip"`, the
//: canvas `aria-describedby` it while it shows, never focusable (the arrow
//: keys move the note it describes, Enter opens the note).
function gcHoverCardEl(s) {
  if (s._hoverCard && s._hoverCard.isConnected) return s._hoverCard;
  const box = s.canvas && s.canvas.parentElement;
  if (!box) return null;
  const card = document.createElement("div");
  card.id = "graph-hovercard";
  card.className = "graph-hovercard";
  card.setAttribute("role", "tooltip");
  card.hidden = true;
  box.appendChild(card);
  s._hoverCard = card;
  //: Called after layout and before paint whenever the card's size changes,
  //: so it is placed by its new size in the same frame.
  card._sizer = new ResizeObserver(() => {
    card._w = card.offsetWidth;
    card._h = card.offsetHeight;
    card._at = null;
    if (!card.hidden) gcHoverCardFrame(s);
  });
  card._sizer.observe(card);
  return card;
}

function gcHoverCardFill(card, node, s) {
  const entry = typeof allEntries !== "undefined" ? allEntries.find((e) => e.id === node.id) : null;
  const facts = gcHoverCardFacts(
    node,
    entry,
    (iso) => {
      const at = parseServerTime(iso);
      return at ? at.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "";
    },
    relativeTime
  );
  const head = document.createElement("div");
  head.className = "graph-hovercard-head";
  const dot = document.createElement("span");
  dot.className = "legend-dot";
  dot.style.background = node.colour || gcTokens.muted;
  dot.setAttribute("aria-hidden", "true");
  const title = document.createElement("strong");
  title.textContent = facts.title;
  head.append(dot, title);
  const parts = [head];
  const line = (text, cls) => {
    const p = document.createElement("p");
    p.className = cls;
    p.textContent = text;
    parts.push(p);
  };
  if (facts.sub) line(facts.sub, "graph-hovercard-sub");
  if (facts.note) line(facts.note, "graph-hovercard-sub");
  const grid = (rows, cls) => {
    if (!rows.length) return;
    const dl = document.createElement("dl");
    dl.className = cls;
    for (const [key, value] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = key;
      const dd = document.createElement("dd");
      dd.textContent = value;
      dl.append(dt, dd);
    }
    parts.push(dl);
  };
  grid(facts.facts, "graph-hovercard-facts");
  grid(facts.props, "graph-hovercard-facts graph-hovercard-props");
  if (facts.tags) line(facts.tags, "graph-hovercard-sub");
  const matches = gcTooltipMatches(node, s);
  if (matches) line(matches.trim().split("\n").slice(0, 4).join("\n"), "graph-hovercard-sub graph-hovercard-matches");
  if (gcIsNote(node)) line("Click for details, double-click to pin", "graph-hovercard-hint");
  card.replaceChildren(...parts);
}

//: Once a frame (`gcDraw`): which note the card is about, the pointer's or
//: else the keyboard's, and where it stands, beside the dot and inside the
//: map. Hidden while a drag or a pan moves the map, while the note's popup
//: is open, and on a pane (which keeps the native tooltip).
function gcHoverCardFrame(s) {
  if (s.size !== "full") return;
  const id = s.hoveredId != null ? s.hoveredId : gcKeyboardId(s);
  const node = id != null && s.byId ? s.byId.get(id) : null;
  const popup = document.getElementById("graph-popup");
  const show = node && !node.isGroup && !s.dragNode && !s.panning && !s.intro && (!popup || popup.classList.contains("hidden"));
  const card = show ? gcHoverCardEl(s) : s._hoverCard;
  if (!card) return;
  if (!show) {
    if (!card.hidden) {
      card.hidden = true;
      s.canvas.removeAttribute("aria-describedby");
    }
    card._for = null;
    return;
  }
  const fill = card._for !== node.id || card._epoch !== s.epoch;
  if (fill) {
    gcHoverCardFill(card, node, s);
    card._for = node.id;
    card._epoch = s.epoch;
  }
  if (card.hidden) {
    card.hidden = false;
    s.canvas.setAttribute("aria-describedby", card.id);
  }
  //: The size comes from the card's ResizeObserver (`gcHoverCardEl`), after
  //: the browser's own layout: a size read here, after the fill, forced a
  //: layout on every hover change (audit 1029 G5).
  if (fill && !card._sizer) {
    card._w = card.offsetWidth;
    card._h = card.offsetHeight;
  }
  const t = s.transform;
  const sx = node.x * t.k + t.x;
  const sy = node.y * t.k + t.y;
  const r = (node.r + (node._grow || 0)) * t.k;
  const w = card._w || 0;
  const h = card._h || 0;
  const gap = 12;
  let left = sx + r + gap;
  if (left + w > s.dims.w - gap) left = sx - r - gap - w;
  left = Math.max(gap, Math.min(left, s.dims.w - w - gap));
  const top = Math.max(gap, Math.min(sy - h / 2, s.dims.h - h - gap));
  const at = `${Math.round(left)},${Math.round(top)}`;
  if (card._at === at) return;
  card._at = at;
  //: Moved on its own layer (`will-change`, graph-lazy.css): a move is a
  //: composite, not a repaint of the card and its shadow every hover.
  card.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;
}

function gcTooltip(node, s = gcTab) {
  const links = (s.adj && s.adj.get(node.id) ? s.adj.get(node.id).size : 0) || 0;
  //: A node that is not a note says what it is, because none of the three
  //: kinds can be opened and a tooltip is the only thing they answer to. An
  //: entity gets the sentence; a document and a board get their own word,
  //: which is at least one somebody has met before.
  if (node.type === "entity") return `${node.preview}\n${GC_ENTITY_HELP}`;
  if (node.type === "document") return `${node.preview}\nA document your notes are attached to`;
  if (node.type === "map") return `${node.preview}\nA mind map, joined to the notes on it`;
  if (node.type === "tag") return `${node.preview}\nA tag, joined to the notes that carry it`;
  if (node.type === "attachment") return `${node.preview}\nA file on the note it is joined to`;
  if (node.type === "unresolved") return `${node.preview}\nNo note has this name yet. Click to write it`;
  if (node.type === "board" || node.type === "whiteboard") {
    return `${node.preview}\nA whiteboard, joined to the notes on it`;
  }
  return (
    `${node.preview}\n[${node.category}] · ${nounCount(links, "connection")}` +
    `${node.access_count ? ` · used ${node.access_count}×` : ""}` +
    gcTooltipMatches(node, s)
  );
}

//: The note's similarity lines as a list, strongest first (INBOX 412): the
//: one place every score fits whatever the zoom, which is what lets the pills
//: on the canvas leave one out rather than stack it.
function gcTooltipMatches(node, s = gcTab) {
  const matches = [];
  for (const edge of s.edges || []) {
    if (edge.kind !== "similar" || typeof edge.score !== "number") continue;
    const other = edge.source === node ? edge.target : edge.target === node ? edge.source : null;
    if (other) matches.push({ other, score: edge.score });
  }
  if (!matches.length) return "";
  matches.sort((p, q) => q.score - p.score);
  const lines = matches.map((m) => `${Math.round(m.score * 100)}%  ${gcLabelText(m.other, s)}`);
  return `\nClosest in meaning:\n${lines.join("\n")}`;
}

//: A click on a node, with the same three modes the SVG renderer had: trace
//: mode picks an end, an in-flight "Link" picks the other note, otherwise the
//: note opens in the popup.
//: The note a dragged one would link to, or null. `graphNodeUnder` aims at
//: `graphNodesRef`, which is the tab's map, so drag-to-link is a Graph-tab
//: gesture; a pane drags to place only. Never while carrying a group:
//: dropping a selection on a note is not "link these two", and guessing which
//: of the carried notes was meant would be. And only with Alt held at the
//: start of the drag (`_dragAlt`): a plain drag places the note, so a drop
//: that was only a move never opens the link dialog.
function gcDropTargetFor(s, node, point) {
  if (s.size !== "full" || s.dragGroup.length || s.dragTopic || !node._dragAlt) return null;
  return graphNodeUnder(node, point);
}

function gcClickNode(event, node, s = gcTab) {
  //: A surface can say what a click means on it. The pane opens the note in
  //: the tab it is sitting beside rather than in the Graph tab's popup, which
  //: is anchored to a canvas the reader is not looking at.
  if (s.onNodeClick) {
    s.onNodeClick(node, event);
    return;
  }
  if (event && event.shiftKey && !node.isGroup) {
    if (s.selected.has(node.id)) s.selected.delete(node.id);
    else s.selected.add(node.id);
    gcSelectionChanged(s);
    gcRequestDraw(s);
    return;
  }
  if (node.type === "unresolved") {
    gcWriteUnresolved(node);
    return;
  }
  //: KG5: an entity opens its page (entity-page.js).
  if (node.type === "entity") {
    openEntityPage(String(node.id).slice("entity:".length));
    return;
  }
  //: **A file or a document on the map opens what it stands for** (B73: "Cant
  //: select on separate attachment nodes in the graph??"). Both fell to the
  //: line below and a click did nothing at all.
  if (gcOpenNodeTarget(node)) return;
  if (!gcIsNote(node)) return;
  if (traceModeActive) {
    pickTraceEnd(node);
    return;
  }
  if (typeof linkSource !== "undefined" && linkSource !== null) {
    beginOrCompleteLink(node);
    return;
  }
  if (graphPopupShows(node)) {
    closeGraphPopup();
    return;
  }
  openGraphPopup(event || { clientX: 0, clientY: 0, stopPropagation() {} }, node);
}

//: What a file node or a document node opens: the file in the lightbox every
//: attachment opens in, the document in the editor. False for any other node,
//: so a caller falls through to its own meaning of a click.
function gcOpenNodeTarget(node) {
  const id = String(node.id).replace(/^[a-z]+:/, "");
  if (node.type === "attachment" && /^\d+$/.test(id)) {
    openLightbox([{ filename: node.preview, getUrl: () => mediaSrc(`/files/${id}`) }], 0);
    return true;
  }
  if (node.type === "document" && /^\d+$/.test(id)) {
    openDocument(Number(id));
    return true;
  }
  return false;
}

//: GRAPH_PLAN 514 (3): a click on an unwritten [[name]] writes the note, with
//: the name as its heading; the server links every note that named it.
async function gcWriteUnresolved(node) {
  try {
    const created = await apiJson("/entries", {
      method: "POST",
      body: JSON.stringify({ content: `# ${node.preview}`, defer_filing: true }),
    });
    if (created.filing_state === "pending" && typeof watchFiling === "function") watchFiling(created);
    pushEntryCreateUndo(created, `Wrote the note “${node.preview}”`);
    toastAction(`Wrote “${node.preview}”.`, "Open", () => flashEntry(created.id), { go: { open: "entry", id: created.id } });
    await renderGraph();
  } catch (error) {
    toast(error.message || "Couldn't write that note.", true);
  }
}

// --- the worker ------------------------------------------------------------------

function gcPost(message, s = gcTab) {
  if (s.worker) s.worker.postMessage(message);
}

function gcStop(s = gcTab) {
  gcPost({ type: "stop" }, s);
}

//: What the worker's forces are tuned by, read fresh from the controls'
//: stored values. Sent with every `init`, and again on its own when a switch
//: the forces depend on changes without a rebuild (Curved links).
function gcWorkerParams(s = gcTab) {
  return {
    gravity: prefs.number("graph-gravity", 50, { min: 0, max: 100 }),
    spread: prefs.number("graph-spread", 50, { min: 0, max: 100 }),
    linkForce: Number(prefs.get("graph-link-force", null) || 50),
    lengthByScore: prefs.get("graph-length-score", null) !== "0",
    //: The tab's map only: a local map of one note's neighbours is
    //: arranged by its links, and a ring of category places would pull
    //: three notes apart.
    groupBy: s.size === "full" && prefs.get("graph-group", null) !== "0",
    //: Unlinked notes take a seat on a ring round the cluster (the worker's
    //: `orbitForce`); a local map has none to seat.
    orbit: s.size === "full",
    //: The lines the worker keeps clear of dots are the lines drawn
    //: (`clearanceForce`, INBOX 693): curved or straight.
    curved: gcCurvedLinks(s),
    //: How the force layout arranges itself (INBOX 693, `#graph-shape`; the
    //: worker's `SHAPES`).
    shape: gcShape(s),
  };
}

//: The Shape control's value: the tab's own, remembered; a pane beside a
//: note is always Organic, the shape a neighbourhood of a few notes reads in.
const GC_SHAPES = ["organic", "clusters", "galaxy"];
function gcShape(s = gcTab) {
  if (s.size !== "full") return "organic";
  const saved = prefs.get("graph-shape", null);
  return GC_SHAPES.includes(saved) ? saved : "organic";
}

//: **Reshuffle layout** (INBOX 692, the owner: "can you add a resuffle
//: button or feature to the graph to rearrange how the graph sits on the
//: main force view??"). A new seed for the worker (`reshuffle` there: the
//: categories dealt round in a new order, every unpinned note sent to a new
//: start near its category's new place, drawn moving rather than jumping,
//: then the layout settles from full heat), and the camera framed on the
//: result the way a first open frames it: once as it cools, once at rest
//: (the tick handler's two fits, `gcStartWorker`), because the person
//: asked for a new picture and should see all of it. Only the force
//: layout: a tree, radial or arc layout is computed, not settled, and has
//: nothing to shuffle. Returns whether it did anything.
function gcReshuffle(s = gcTab) {
  if (s.tree || !s.worker || !s.nodes.length) return false;
  s.layoutSeed = 1 + Math.floor(Math.random() * 0x7ffffffe);
  s.settledSig = null;
  s.userZoomed = false;
  s.fittedOnce = true;
  gcSetAutoFitDone(s, false);
  gcPost(
    {
      type: "reshuffle",
      seed: s.layoutSeed,
      animate: !gcStill(),
    },
    s
  );
  return true;
}

//: `viewSeed`, when the caller is restoring a saved view, is
//: `{alpha, freezeIds}`: the alpha to hand the worker's `init` (0 to start at
//: rest, the decision above) and which node ids to freeze right after init
//: so they hold still while `alpha: 1` places the notes that have no saved
//: spot. `null` (every other caller) is the unchanged "alpha 1, nothing
//: frozen" behaviour.
//: The heat an update starts from: the worker's `DRAG_ALPHA`.
const GC_UPDATE_ALPHA = 0.3;
function gcStartWorker(nodes, edges, world, s = gcTab, viewSeed = null) {
  if (!s.worker) {
    // Version-stamped for the same reason index.html's script tags are
    // (tests/test_asset_cache_busting.py): a desktop wrapper with its own
    // cache can otherwise go on running yesterday's worker forever, and a
    // stale worker is invisible, nothing logs, the map just behaves like the
    // build before last. The stamp is the worker file's own, from the map
    // the served page carries (`lazyAssetStamp`, app.js).
    s.worker = new Worker(`/js/graph-worker.js${lazyAssetStamp("/js/graph-worker.js")}`);
    s.worker.onmessage = (event) => {
      const message = event.data || {};
      //: A message from a simulation that no longer matches what is on screen
      //: is dropped whole, buffer included: handing a stale buffer back would
      //: decrement an `inFlight` count that the newer `init` has already
      //: reset, and the worker allocates a replacement for nothing worse than
      //: one skipped frame's worth of pool.
      if (message.epoch !== s.epoch) return;
      if (message.type === "tick") {
        s.ticksSeen = (s.ticksSeen || 0) + 1;
        s.alpha = message.alpha;
        s.ticks = message.ticks || 0;
        s.tickMs = message.tickMs || 0;
        s.layoutRunning = message.running !== false;
        const positions = message.positions;
        const count = Math.min(s.nodes.length, positions.length / 2);
        //: **Drawn between ticks, not at them** (INBOX 586, "the graph is a
        //: little jittery when nodes move around or adjust position"). The
        //: worker steps on its own timer (16 ms, or as long as a tick took on
        //: a big map) and the canvas paints on the display's: the two beat,
        //: so a note moved two steps in one frame, none in the next, one in
        //: the one after. Each tick is now kept with the one before it, and a
        //: frame draws the point between them that its time says
        //: (`gcGlideStep`): the motion one tick interval late, at an even
        //: speed across the frames in between.
        //: How long a glide lasts is the interval ticks have been arriving
        //: at, smoothed (a timer's few milliseconds of jitter would otherwise
        //: make every glide a different speed), and a gap after the layout was
        //: at rest is not an interval at all.
        const now = performance.now();
        const gap = s.lastTickAt && now - s.lastTickAt < GC_GLIDE_MAX_MS * 2 ? now - s.lastTickAt : null;
        s.lastTickAt = now;
        if (gap !== null) {
          const smoothed = s.tickGap ? s.tickGap * 0.8 + gap * 0.2 : gap;
          s.tickGap = Math.min(GC_GLIDE_MAX_MS, Math.max(GC_GLIDE_MIN_MS, smoothed));
        }
        const drift = gcAimNodes(s, positions, count);
        s.glideFrom = now;
        s.glideMs = 0;
        s.gliding = true;
        if (gcTickSettles(s)) gcGlideFinish(s);
        // The positions moved, so the hit-test index is stale. Marked here
        // rather than at the end of every draw: a settled map redraws on
        // hover without anything having moved, and rebuilding a 2,000-point
        // quadtree per pointermove for nothing is a millisecond a frame.
        s.quadtreeDirty = true;
        gcTickDraw(s, now, drift);
        // **Framed twice: once straight away, once when it settles.**
        //
        // The SVG renderer framed the map exactly once, when the simulation
        // cooled below alpha 0.08, about 110 ticks. Measured on the 2,000-note
        // fixture in this sandbox, a tick costs ~80 ms, so that is nine seconds
        // of watching a graph whose notes are mostly outside the frame at
        // zoom 1, with no way to know that is what you are looking at. The
        // first tick is framed immediately instead, so the map is *visible*
        // from the first moment, and the settle re-frames it once the layout
        // has actually decided its shape.
        //
        // The second fit is skipped if the user has zoomed or panned in the
        // meantime: recentring the camera out from under someone who has
        // deliberately gone to look at something is the reported bug
        // `graphAutoFitDone` exists for, and an early fit must not reintroduce
        // it by making the late fit unconditional.
        //: The warm-up's playback (`frame`, below) is framed already: the
        //: fits wait for the live layout, which starts where it ends.
        if (!message.intro) s.intro = false;
        if (!gcAutoFitDone(s) && s.nodes.length && !s.intro) {
          if (!s.fittedOnce) {
            s.fittedOnce = true;
            //: Instant (INBOX 738): a glide from the default camera is the
            //: zoomed-in first frames the hiding exists to keep off screen.
            //: And framed on where this tick put the notes, not where the
            //: glide has them: `x`/`y` are still the starting spiral until
            //: the next paint, which is what the first fit used to frame
            //: (k 2.5, the clamp, on 60 notes).
            gcGlideFinish(s);
            fitGraphToView(s.svg, s.zoom, s.nodes, s.dims.w, s.dims.h, true);
            s.fitTicks = s.ticksSeen;
            gcRevealAfterBalance(s);
          } else if (message.alpha < 0.08) {
            gcSetAutoFitDone(s, true);
            if (!s.userZoomed) {
              fitGraphToView(s.svg, s.zoom, s.nodes, s.dims.w, s.dims.h);
              //: The layout keeps drifting between alpha 0.08 and rest, so
              //: this frame could end lopsided: a wide empty band along one
              //: edge (owner, 0.3.31: "the graph auto size leaves quite a bit
              //: of a gap at the bottom"). One more fit at "end", below.
              s.fitAgainAtEnd = true;
            }
          }
        }
        // Hand the buffer back so the worker can reuse it (see its `pool`).
        s.worker.postMessage({ type: "recycle", buffer: positions.buffer }, [positions.buffer]);
        if (s.size === "full") {
          graphMinimapTick += 1;
          if (graphMinimapTick % 8 === 0) graphMinimapQueuePaint();
        }
      } else if (message.type === "frame") {
        gcFrameIntro(s, message.positions, message.start);
      } else if (message.type === "end") {
        s.layoutRunning = false;
        //: At rest is where the last tick said: the glide is finished here,
        //: not by the next paint, so the fit below frames the final shape.
        gcGlideFinish(s);
        gcDrawHeld(s);
        //: What just came to rest, so the next render of exactly these
        //: inputs can hold it instead of settling it again (`gcStartWorker`).
        s.settledSig = s.layoutSig;
        gcSavePositions(s);
        if (s.size === "full") graphMinimapQueuePaint();
        if (!gcAutoFitDone(s) && s.nodes.length) {
          gcSetAutoFitDone(s, true);
          //: Nothing moved since the first fit (the settled map as the one
          //: frame, less motion): framing it again from the guess undid its
          //: balance, a hop just after the cut-in.
          if (s.ticksSeen !== s.fitTicks) fitGraphToView(s.svg, s.zoom, s.nodes, s.dims.w, s.dims.h);
        } else if (s.fitAgainAtEnd && !s.userZoomed && s.nodes.length) {
          fitGraphToView(s.svg, s.zoom, s.nodes, s.dims.w, s.dims.h);
        }
        s.fitAgainAtEnd = false;
        if (!s.revealAfterFit) gcReveal(s);
        // GRAPH_PLAN Phase 5: the settle a restored view's unplaced notes
        // forced is over, so the notes it held still (`viewSeed.freezeIds`,
        // below) are released the same way a drag's freeze is: `thaw`, no
        // alpha change, so releasing them does not itself start another
        // settle.
        if (s._viewRestorePending) {
          s._viewRestorePending = false;
          gcPost({ type: "thaw" }, s);
        }
      }
    };
    s.worker.onerror = () => {
      // A worker that will not start must not take the map with it: the nodes
      // already have positions (inherited, pinned or spiral), so the canvas
      // still draws a static graph.
      gcRequestDraw(s);
      gcReveal(s);
    };
  }
  s.fittedOnce = false;
  s.intro = false;
  s.ticksSeen = 0;
  s.fitTicks = -1;
  //: Hidden until the first fit (the owner, 2026-10-07: "the crazy starting
  //: zoom in on the graph before it fits"): the first frames drew at the
  //: default camera. Shown at that fit, or after 4 s whatever happens (a
  //: worker that fails reveals at once, `onerror`). It was 1.5 s, which a
  //: busy machine's first open (the worker script and d3 fetched, the
  //: layout warmed) overran, revealing the default camera.
  //: **Only a canvas that has shown nothing yet** (the owner, round 2:
  //: "I just change views or reset it and it just suddenly changes or
  //: disappears and reappears"). A new layout, a return to the tab, Refresh
  //: or a saved view starts from the map on screen and moves from there.
  const reframe = !gcAutoFitDone(s);
  if (reframe && s.canvas && !s.shown) {
    s.canvas.style.opacity = "0";
    setTimeout(() => gcReveal(s), 4000);
  }
  const hidden = s.canvas?.style.opacity === "0";
  //: **A saved view's notes are held from the first step** (claim #238): the
  //: `freeze` below arrived after `init`, and an init that warmed (a view
  //: re-picks its layout, which clears the fit, so `reframe`) stepped every
  //: note 450ms before the hold landed: 726px off the saved spots once a
  //: note had been added since. Held in the init itself now, with no warm-up
  //: and no intro for a restore.
  const held = new Set(viewSeed?.freezeIds || []);
  const restoring = Boolean(viewSeed?.restore);
  const init = {
    type: "init",
    epoch: s.epoch,
    // Performance mode (settings.js): the physics yields twice as long
    // between ticks, half the CPU for a layout that converges a little later.
    perf: document.documentElement.dataset.perf === "on",
    nodes: nodes.map((n) => ({
      id: n.id,
      x: n.x,
      y: n.y,
      fx: n.fx == null ? null : n.fx,
      fy: n.fy == null ? null : n.fy,
      held: held.has(n.id),
      r: n.r,
      group: n.category || "",
    })),
    edges: edges.map((e) => ({
      source: e.source.id != null ? e.source.id : e.source,
      target: e.target.id != null ? e.target.id : e.target,
      kind: e.kind,
      //: A link somebody gave a reason for sits a little closer (the worker's
      //: `KIND_LENGTH`).
      curated: e.kind === "link" && Boolean(e.reason),
      //: A similarity line's score or a deduced link's confidence, for
      //: Length by similarity. The worker was never sent it, so that switch
      //: changed nothing on this renderer (INBOX 412, measured).
      score: typeof e.score === "number" ? e.score : typeof e.reason_confidence === "number" ? e.reason_confidence : null,
    })),
    params: gcWorkerParams(s),
    //: The arrangement a Reshuffle dealt (`gcReshuffle`), kept by every
    //: re-render after it; 0 is the default map. Not in the hold signature
    //: below: a reshuffle is already the settled layout it describes.
    seed: s.layoutSeed || 0,
    world,
    // GRAPH_PLAN Phase 5, "positions on a saved view": 0 starts the layout
    // at rest instead of relaxing it (see the decision on `viewSeed` above),
    // 1 is every other caller's unchanged behaviour.
    alpha: viewSeed ? viewSeed.alpha : 1,
    //: Step the layout out of its starting spiral before the first post
    //: (the worker's `WARM_MS`) whenever the map is framed again, so the
    //: frame is set on where it ends.
    warm: reframe && !restoring && !(viewSeed && viewSeed.alpha === 0),
    //: And then play those steps back, framed on where they end (the
    //: worker's `INTRO_HOLD`), unless the reader asked for less motion: they
    //: get the settled map at once, as before.
    intro: !gcStill() && !restoring,
    //: Behind the first fade the playback starts near the settled map
    //: (the worker's `BLOOM`); on a map already showing, from where its
    //: notes stand.
    bloom: hidden,
  };
  //: **A layout that already settled is held, not settled again** (INBOX
  //: 424c/d). Every visit to the Graph tab refetched the map and restarted
  //: the simulation at full heat from the positions it had already come to
  //: rest in, so each visit paid a whole settle for a picture that ended up
  //: where it started: measured at 4x CPU on a 400-note, 1,200-link graph,
  //: about 7s of main-thread work in the eight seconds after arriving, and
  //: the map visibly shuffling the whole time. The signature is everything
  //: the worker's answer depends on apart from where the notes start (which
  //: notes, their pins and sizes, every line, the forces, the world); when
  //: it is the signature of the layout that last came to rest, and every
  //: note is starting from where that layout left it (`holdIfSettled`, from
  //: the render), the layout starts at rest, exactly the way a restored
  //: view does. Anything that changes an input changes the signature, and
  //: that render heats the layout as it always did.
  const sig = JSON.stringify([
    init.perf,
    //: Not the radius (audit G4): the Size rule only changes how big a dot is drawn, and
    //: a settled map stays where it is rather than re-laying out (12 s at 2,000 notes).
    //: The new radii still reach the worker in `init`, for the next drag or real change.
    init.nodes.map((n) => [n.id, n.fx, n.fy]),
    init.edges.map((e) => [e.source, e.target, e.kind, e.score, e.curated]),
    init.params,
    world,
  ]);
  if (init.alpha && viewSeed?.holdIfSettled && s.settledSig === sig) init.alpha = 0;
  //: **An update moves the map from where it is** (Brief 100 (a)): a filter,
  //: a hidden category or a deleted note, every note still there already
  //: placed and the forces unchanged, reheats as a drag does rather than
  //: from full heat, which shuffled the whole map for one note's change.
  const forces = JSON.stringify([init.params, init.seed, init.perf]);
  if (init.alpha === 1 && viewSeed?.holdIfSettled && s.lastForces === forces) init.alpha = GC_UPDATE_ALPHA;
  s.lastForces = forces;
  s.layoutSig = sig;
  s.settledSig = null;
  gcPost(init, s);
  // Freeze the view's own notes *after* init, so the worker reads their
  // current (just-seeded) x/y as the position to hold, exactly the "freeze
  // holds where a note already is" contract `freeze` has for a drag.
  if (viewSeed && viewSeed.freezeIds && viewSeed.freezeIds.length) {
    gcPost({ type: "freeze", ids: viewSeed.freezeIds }, s);
    s._viewRestorePending = true;
  }
}

//: **The camera is framed on where the warm-up ends, before it is played**
//: (the worker's `intro`, INBOX 775): the notes then move into a frame that
//: already holds them, rather than the frame chasing the notes (INBOX 738's
//: zoomed-in start). Instant, and the map is shown here.
//: **The map opens where it was left** (Brief 100 (a); INBOX 864, and the
//: owner 2026-10-11: "there is still no smooth transition loading up the app
//: nd viewing the graph, it kinda just appears"). Measured before
//: (`load.js`, 200 notes, the app loading onto Graph): the canvas waited
//: hidden, came in at 0.8 opacity in one frame, and the spiral then spread
//: from 241 to 630 px wide in four frames. The settled positions are kept in
//: this browser, for the layout and the forces they were settled under, and
//: a page's first draw starts from them the way a saved view does
//: (`graphApplyView`): every note they know holds, a note they do not is
//: placed by the settle with the rest held, and the first fit frames the
//: picture the reader last saw. A per-viewer convenience only: an empty,
//: stale or blocked store gives the warm-up as before.
const GC_POS_KEY = "graphPositions";
const GC_POS_MAX = 5000;
function gcPositionsSig(s) {
  return JSON.stringify([s.layoutSeed || 0, gcWorkerParams(s)]);
}
function gcSavePositions(s) {
  if (s.size !== "full" || s.tree || graphFocusModeId || !s.nodes.length || s.nodes.length > GC_POS_MAX) return;
  const at = {};
  for (const node of s.nodes) {
    if (Number.isFinite(node.x) && Number.isFinite(node.y)) at[node.id] = [Math.round(node.x), Math.round(node.y)];
  }
  try {
    prefs.set(GC_POS_KEY, JSON.stringify({ sig: gcPositionsSig(s), at }));
  } catch (e) {
    // A full or blocked store costs only the next open's head start.
  }
}
function gcCachedPositions(s) {
  if (s.size !== "full" || graphFocusModeId) return null;
  try {
    const kept = prefs.json(GC_POS_KEY, null);
    if (!kept || kept.sig !== gcPositionsSig(s) || !kept.at) return null;
    const out = {};
    for (const [id, xy] of Object.entries(kept.at)) {
      if (Array.isArray(xy) && Number.isFinite(xy[0]) && Number.isFinite(xy[1])) out[id] = { x: xy[0], y: xy[1] };
    }
    return out;
  } catch (e) {
    return null;
  }
}

function gcFrameIntro(s, positions, start) {
  if (gcAutoFitDone(s) || !s.nodes.length || positions.length < s.nodes.length * 2) return;
  s.fittedOnce = true;
  s.intro = true;
  //: The playback's first frame is where the notes are drawn from the
  //: reveal on: a glide from where the canvas last had them (the starting
  //: spiral, behind the fade) was a 327 px jump in its first frame.
  if (start && start.length >= s.nodes.length * 2) {
    s.nodes.forEach((node, i) => {
      if (node === s.dragNode) return;
      node.x = start[i * 2];
      node.y = start[i * 2 + 1];
      node._toX = undefined;
      node._toY = undefined;
    });
    s.gliding = false;
    s.glideMs = 0;
    s.quadtreeDirty = true;
    gcRequestDraw(s);
  }
  const target = s.nodes.map((node, i) => ({ x: positions[i * 2], y: positions[i * 2 + 1], r: node.r }));
  //: Instant behind the fade of a first open; on a map already showing, the
  //: camera eases to the new frame while the notes move.
  fitGraphToView(s.svg, s.zoom, target, s.dims.w, s.dims.h, s.canvas?.style.opacity === "0");
  gcReveal(s);
}

//: The world the simulation solves in, a square whose side grows with
//: sqrt(count). Carried over from the SVG renderer along with the reason it is
//: square and count-based rather than a multiple of the frame: a graph box is
//: wide and short, so multiplying the frame gave a few hundred pixels of
//: vertical room and the layout settled against the walls into a lattice,
//: reported as "the graph nodes are like locked into a box".
function gcWorldFor(count, width, height) {
  const perNode = 2 * (GC_MAX_RADIUS + 28);
  // 1.25, not 1.6. The world is the wall a reheated layout cannot push past,
  // and it was sized for a simulation whose span grew like sqrt(count) with
  // nothing holding it in; the worker now scales its repulsion and its centre
  // force by the note count (`densityScale`/`centreScale` in graph-worker.js),
  // so the natural spread is a good deal smaller than the room this used to
  // reserve and the gap between the two was somewhere a node could wander to
  // and be lost.
  //: **Where it bites, measured rather than asserted**
  //: (`scratchpad/ui-sweeps/graphtouch.js`, which reads this function at three
  //: counts and two widths). This line used to say "measured at 35 and 300
  //: notes this changes nothing at all: both are under the viewport floor
  //: below", and the floor is not one number: it is 2531 on a 1440 desktop map
  //: and 1168 on a 390 phone. At 35 notes the floor decides at both widths
  //: (680 here against 2531 and 1168), so the change really is neutral there.
  //: At 300 it decides only on the desktop: the count term is 1992, under the
  //: desktop floor and over the phone's, so on a phone this constant shrank
  //: the world from 2550 to 1992, by 22%, which is the direction it was
  //: changed for and a smaller screen is where a lost node is hardest to find.
  //: Above about five hundred notes it decides at every width.
  const roomy = Math.sqrt(Math.max(count, 1)) * perNode * 1.25;
  const side = Math.max(roomy, width * 1.8, height * 1.8);
  return {
    left: (width - side) / 2,
    top: (height - side) / 2,
    right: (width - side) / 2 + side,
    bottom: (height - side) / 2 + side,
    //: The map's shape, for the worker's centring pull (`tuning`): a portrait
    //: map gets a portrait layout (INBOX 430).
    aspect: width > 0 && height > 0 ? height / width : 1,
  };
}

// --- the render ------------------------------------------------------------------

//: The Canvas 2D renderer, behind the same `renderGraph()` entry, on the same
//: data, with the same ids and the same dock controls. Everything from the
//: fetch down to the stats line is the SVG renderer's own sequence: what
//: changes is that the drawing is a canvas and the simulation is a worker.
//: **Which empty state, and why it is empty** (tests/test_graph_empty_filtered.py).
//: `filtered` is absent for a notebook with nothing to map, and carries the
//: render's own data when there were notes and the map's filters took every
//: one off: the legend (a category or a rule key), a group switched off,
//: notes hidden from the node menu, or Hide unlinked on a notebook with no
//: links. That second case used to draw "Nothing to map yet" and offer to
//: capture a note, over a full notebook. It names what is doing the hiding,
//: because the controls are in three different places (the legend, the node
//: menu, the options panel), and offers the one action that undoes them all.
function gcShowEmpty(show, filtered = null) {
  const empty = document.getElementById("graph-empty");
  if (!empty) return;
  empty.style.display = show ? "grid" : "none";
  empty.classList.toggle("hidden", !show);
  const isFiltered = Boolean(show && filtered);
  document.getElementById("graph-empty-fresh")?.classList.toggle("hidden", isFiltered);
  document.getElementById("graph-empty-filtered")?.classList.toggle("hidden", !isFiltered);
  if (!isFiltered) return;
  const { data, s, groups } = filtered;
  const reasons = [];
  if (graphHiddenCategories.size || graphHiddenKeys.size) reasons.push("the legend");
  if ((groups || []).some((g) => g && g.hiddenOnMap)) reasons.push("a group");
  if (s.hiddenIds.size) reasons.push(`${s.hiddenIds.size} ${s.hiddenIds.size === 1 ? "note" : "notes"} you hid from the node menu`);
  if (document.getElementById("graph-hide-orphans")?.checked) reasons.push("Hide unlinked");
  const count = data.nodes.filter((n) => !n.isGroup).length;
  const what = count === 1 ? "Your one note is" : `All ${count} notes are`;
  const why = document.getElementById("graph-empty-filtered-why");
  if (why) {
    why.textContent = reasons.length
      ? `${what} filtered out by ${reasons.join(", ").replace(/, ([^,]*)$/, " and $1")}.`
      : `${what} filtered out by the map's settings.`;
  }
}

//: Undo every filter that can take a note off the map, and nothing else: the
//: layout, the colour rule, the physics and the Show switches are how the map
//: looks, not which notes are on it, and Reset to defaults already exists for
//: those. One render at the end, whatever was on.
function gcShowEveryNote(s = gcTab) {
  graphHiddenCategories.clear();
  graphHiddenKeys.clear();
  s.hiddenIds.clear();
  const orphans = document.getElementById("graph-hide-orphans");
  if (orphans) orphans.checked = false;
  const groups = graphGroups();
  if (groups.some((g) => g && g.hiddenOnMap)) {
    for (const g of groups) if (g) g.hiddenOnMap = false;
    // Renders the map itself.
    graphSetGroups(groups);
    return;
  }
  renderGraph();
}

document.getElementById("graph-empty-show-all")?.addEventListener("click", () => gcShowEveryNote());

//: **A note new to a placed map starts beside what it is linked to** (Brief
//: 100 (a): "new ones grow in"). It started on the centre spiral, so a note
//: added, or a category shown again, flew in from the middle of the map
//: through everything between. Now it starts at the middle of its placed
//: neighbours, else of its placed category, a few units off so two do not
//: coincide, and fades in there (`node._born`); only a note with neither
//: keeps the spiral.
function gcSeedBesideNeighbours(s, nodes) {
  if (!nodes.some((n) => Number.isFinite(n.x)) || nodes.every((n) => Number.isFinite(n.x))) return;
  const byCategory = new Map();
  for (const node of nodes) {
    if (!Number.isFinite(node.x)) continue;
    const sum = byCategory.get(node.category) || { x: 0, y: 0, n: 0 };
    sum.x += node.x;
    sum.y += node.y;
    sum.n += 1;
    byCategory.set(node.category, sum);
  }
  nodes.forEach((node, index) => {
    if (Number.isFinite(node.x)) return;
    let x = 0, y = 0, n = 0;
    for (const id of s.adj.get(node.id) || []) {
      const mate = s.byId.get(id);
      if (!mate || !Number.isFinite(mate.x)) continue;
      x += mate.x;
      y += mate.y;
      n += 1;
    }
    const home = n ? { x: x / n, y: y / n } : byCategory.get(node.category);
    if (!home || (!n && !home.n)) return;
    const cx = n ? home.x : home.x / home.n;
    const cy = n ? home.y : home.y / home.n;
    const angle = index * 2.399963;
    node.x = cx + 12 * Math.cos(angle);
    node.y = cy + 12 * Math.sin(angle);
  });
}

async function renderGraphCanvas(s = gcTab) {
  if (!gcEnsureCanvas(s)) return;
  const sequence = ++s.renderSeq;
  //: **Whether this render frames the map is decided now, before the first
  //: await** (the owner, 2026-10-10: "I went onto the radial view and it put
  //: me on a random corner", "same with the tree"). A layout switch clears
  //: the fit flag and calls this; while `/graph` is fetched, the force layout
  //: it is replacing is still cooling, and its first tick under alpha 0.08
  //: read the cleared flag as its own settle fit, framed the old force
  //: positions and set the flag again. The radial then arrived with the flag
  //: set, skipped `frameTree`, and sat under the force camera: measured on 60
  //: notes, the radial's centre 541px left and 247px up of the view's at the
  //: force's k 0.79. Captured here, the old simulation can spend the flag
  //: and this render still frames what it draws.
  const reframe = !gcAutoFitDone(s);
  const wantSimilarity = document.getElementById("graph-similarity").checked;
  const wantEntities = document.getElementById("graph-entities")
    ? document.getElementById("graph-entities").checked
    : false;
  const wantDocuments = document.getElementById("graph-documents")
    ? document.getElementById("graph-documents").checked
    : false;
  const wantMaps = document.getElementById("graph-maps")
    ? document.getElementById("graph-maps").checked
    : false;
  graphSyncFocusChip();
  void wantEntities, wantDocuments, wantMaps;
  if (!s.shown) gcArriving(s, true);
  const endpoint = graphEndpoint();
  //: A failed read is not an empty graph. Reported class of bug: the map
  //: drew "Nothing to map yet" over a notebook full of linked notes because
  //: the only thing distinguishing the two was a null this returned silently.
  //: See `surfaceFailed` in navigation.js.
  //: A reload of a map already shown that takes a while says so: a thin
  //: line under the count from 400 ms (audit 1029 G30). The first visit
  //: has its glow (`gcArriving`).
  const stats = s.shown ? document.getElementById("graph-stats") : null;
  const slow = stats && setTimeout(() => stats.setAttribute("aria-busy", "true"), 400);
  const data = await apiJson(endpoint).then(graphFill).catch(() => null);
  clearTimeout(slow);
  stats?.removeAttribute("aria-busy");
  if (!data) {
    gcArriving(s, false);
    surfaceFailed(document.getElementById("graph-empty"), "your map", renderGraph);
    //: And the overview goes with the map it summarises, exactly as it does
    //: when there is nothing to map.
    graphMinimapShown(false);
    return;
  }
  surfaceRecovered(document.getElementById("graph-empty"));
  // A slow answer that has been overtaken by a newer render must not paint
  // over it. The SVG path had the same race and answered it by clearing the
  // SVG; a canvas has nothing to clear, so the sequence number is the guard.
  if (sequence !== s.renderSeq) return;
  s.timing = { dataAt: performance.now(), firstFrame: 0, lastFrame: 0, frames: 0 };
  // A fresh visit to the tab (`graphAutoFitDone` cleared by switchTab) is also
  // a fresh camera: forget that the last visit's viewer had zoomed somewhere.
  if (reframe) {
    gcSetAutoFitDone(s, false);
    s.userZoomed = false;
  }

  //: Both reads before the first write below: apart, each paid its own style pass.
  gcReadTokens(s);
  gcResize(s);
  gcShowEmpty(data.nodes.length === 0);
  if (!data.nodes.length) gcArriving(s, false);
  //: The minimap goes with the map: an overview of nothing is a grey
  //: rectangle in a corner.
  graphMinimapShown(data.nodes.length > 0);

  const colour = graphCategoryScale(data.categories);
  const clusterColour = d3.scaleOrdinal(graphCalmScheme());
  const colourMode = graphColourMode();
  graphStructure = colourMode === "cluster" || colourMode === "topic"
    ? await apiJson(`/graph/structure${colourMode === "topic" ? "?topics=1" : ""}`).catch(() => null)
    : null;
  if (sequence !== s.renderSeq) return;
  // GRAPH_PLAN Phase 3: the colour follows a rule, and a group (a saved
  // search) paints over the rule for the notes it matches.
  const groups = await graphResolveGroups();
  if (sequence !== s.renderSeq) return;
  const ruleColour = gcRuleScale(colourMode, data);
  s.topicColour = clusterColour;
  s.colourOf = (node) => {
    if (node.type === "unresolved") return gcTokens.muted;
    const groupIndex = graphGroupOf.get(node.id);
    if (groupIndex !== undefined && !node.isGroup) return graphGroupColour(groupIndex);
    if (node.isGroup) return colour(node.category);
    if (colourMode === "category") return colour(node.category);
    if (colourMode === "cluster" || colourMode === "topic") {
      if (!graphStructure) return colour(node.category);
      const cluster = (colourMode === "topic" ? graphStructure.topic_of || {} : graphStructure.cluster_of)[String(node.id)];
      return cluster === undefined ? gcTokens.muted : clusterColour(String(cluster));
    }
    return ruleColour(gcRuleKey(colourMode, node));
  };
  graphRenderLegend(data, colourMode, colour, clusterColour, ruleColour, groups, s);
  graphLegendRove(document.getElementById("graph-legend"));
  gcLegendEdgeKey(data);
  gcLegendSizeKey();
  gcSelectionChanged(s);

  const ruleHides = !["category", "cluster", "topic"].includes(colourMode);
  let visibleNodes = data.nodes.filter(
    (n) =>
      !graphHiddenCategories.has(n.category) &&
      !s.hiddenIds.has(n.id) &&
      !(ruleHides && graphHiddenKeys.has(`${colourMode}:${gcRuleKey(colourMode, n)}`)) &&
      !(graphGroupOf.has(n.id) && groups[graphGroupOf.get(n.id)]?.hiddenOnMap)
  );
  const kept = new Set(visibleNodes.map((n) => n.id));
  //: Pruned here, before anything else reads the edges, so the springs, a
  //: note's degree (its size), the stats line and the drawing all see the
  //: same backbone (INBOX 412; see `gcPruneSimilarity`). After the hidden
  //: notes are taken out, so a note hidden from the map does not use up
  //: one of its neighbour's two lines.
  gcRenderFilterChips(data);
  const visibleEdges = gcPruneSimilarity(
    data.edges.filter((e) => kept.has(e.source) && kept.has(e.target) && !gcLinkKindHidden(e)),
    { threshold: gcSimilarityCutoff() }
  );
  {
    const scores = visibleEdges
      .filter((e) => e.kind === "similar" && typeof e.score === "number")
      .map((e) => e.score);
    s.simRange = scores.length ? [Math.min(...scores), Math.max(...scores)] : null;
  }
  const hideOrphans = document.getElementById("graph-hide-orphans");
  if (hideOrphans && hideOrphans.checked) {
    const connected = new Set();
    for (const edge of visibleEdges) {
      connected.add(edge.source);
      connected.add(edge.target);
    }
    visibleNodes = visibleNodes.filter((n) => connected.has(n.id));
  }
  if (!visibleNodes.length) {
    //: Filtered only when the data had notes: an empty notebook reaches this
    //: branch too, and said "All 0 notes are filtered out" (INBOX 472).
    gcShowEmpty(true, data.nodes.length ? { data, s, groups } : null);
    //: And the overview goes with the map, as it does for an empty notebook:
    //: it would otherwise go on drawing the last visit's dots beside a
    //: message saying there is nothing on the map.
    graphMinimapShown(false);
    s.nodes = [];
    s.edges = [];
    s.adj = new Map();
    s.byId = new Map();
    graphNodesRef = s.nodes;
    gcStop(s);
    gcRequestDraw(s);
    return;
  }

  const width = s.dims.w;
  const height = s.dims.h;
  s.layoutKind = graphLayout();
  s.tree =
    s.layoutKind === "force"
      ? null
      : layoutHierarchy(visibleNodes.map((n) => ({ ...n })), s.layoutKind, width, height);

  // A note already on screen keeps the spot it had settled into, so a legend
  // toggle or a slider change does not replay the whole "explode outward"
  // animation. Same inheritance the SVG renderer does, and for the same
  // reported reason.
  const prior = new Map((graphNodesRef || []).map((n) => [n.id, { x: n.x, y: n.y }]));
  // GRAPH_PLAN Phase 5, "positions on a saved view" (INBOX 275's neighbour
  // row). One-shot: consumed here so a second `renderGraphCanvas()` from the
  // same `graphApplyView` call (it fires once per control it restores:
  // layout, colour, physics, entities...) does not re-seed on top of a
  // layout that has already moved on; every render after this one just
  // inherits the result forward through `prior`, above, the same as any
  // other re-render already does. Only meaningful for force: a tree/radial/
  // arc layout is recomputed deterministically below and never reads this.
  const restoring = Boolean(graphPendingViewPositions) && s.layoutKind === "force";
  const viewPositions =
    graphPendingViewPositions || (s.layoutKind === "force" && !prior.size ? gcCachedPositions(s) : null);
  graphPendingViewPositions = null;
  // Decision made, 2026-09-21 (GRAPH_PLAN): a restored arrangement holds, it
  // does not re-settle. A note the view captured gets exactly its saved
  // spot; a note added *since* the view was saved has no saved spot, and is
  // the only reason the simulation may reheat at all on this render (passed
  // to `gcStartWorker` below).
  const unplacedByView = viewPositions
    ? visibleNodes.some((n) => !viewPositions[n.id])
    : false;
  // Ids seeded from a saved view but not genuinely pinned: frozen only for
  // the length of the settle the unplaced notes above force, then released
  // (`gcStartWorker`'s "end" handling, below) the same way a drag freezes
  // every other note on the map and thaws it on release. A real pin
  // (`graph_pin_x`/`graph_pin_y`, notebook content) is never in this list:
  // its `fx`/`fy` below is permanent and owned by that block already.
  const seededUnpinnedIds = [];
  const nodes = s.tree
    ? s.tree.nodes
    : visibleNodes.map((n) => {
        const was = prior.get(n.id);
        const built = was && Number.isFinite(was.x) ? { ...n, ...was } : { ...n };
        const saved = viewPositions && viewPositions[n.id];
        if (saved) {
          built.x = saved.x;
          built.y = saved.y;
        }
        if (built.graph_pin_x != null && built.graph_pin_y != null) {
          built.fx = built.graph_pin_x;
          built.fy = built.graph_pin_y;
        } else if (saved && unplacedByView) {
          seededUnpinnedIds.push(built.id);
        }
        return built;
      });
  const edges = s.tree ? s.tree.links : visibleEdges.map((e) => ({ ...e }));

  s.byId = new Map(nodes.map((n) => [n.id, n]));
  s.adj = new Map(nodes.map((n) => [n.id, new Set()]));
  for (const edge of edges) {
    const from = edge.source && edge.source.id != null ? edge.source.id : edge.source;
    const to = edge.target && edge.target.id != null ? edge.target.id : edge.target;
    if (s.adj.has(from)) s.adj.get(from).add(to);
    if (s.adj.has(to)) s.adj.get(to).add(from);
    // Resolve to the node objects once, here, rather than on every frame.
    edge.source = s.byId.get(from) || edge.source;
    edge.target = s.byId.get(to) || edge.target;
    edge._path2d = null;
  }
  //: **A dot's size counts the notebook's links, not the lines drawn**
  //: (INBOX 1300 C37, the owner on the treemap: "the nodes are all the same
  //: size, should they be different??"). A treemap draws no lines, so every
  //: note counted 0 and drew at 5px. The other layouts draw their links (a
  //: tree also draws its filing), so they keep the drawn count.
  const linkDegree = new Map();
  if (s.tree && s.tree.treemap) {
    for (const edge of visibleEdges) {
      for (const end of [edge.source, edge.target]) {
        const id = end && end.id != null ? end.id : end;
        linkDegree.set(id, (linkDegree.get(id) || 0) + 1);
      }
    }
  }
  const degreeOf = (node) => (linkDegree.size ? linkDegree.get(node.id) || 0 : (s.adj.get(node.id) || { size: 0 }).size);
  let maxDegree = 0;
  for (const node of nodes) if (!node.isGroup) maxDegree = Math.max(maxDegree, degreeOf(node));
  //: Which category's cluster a note stands in, in the Clusters shape; null
  //: otherwise. Read by `gcBowPoint` and the line pass: a line between
  //: clusters is straight and quiet. `_straight`: every line is drawn
  //: straight, in every shape but Organic (INBOX 693, the owner: curved lines
  //: crossing "through the middle of the hub"; the worker's `clearCurve`).
  const shape = s.tree ? null : gcShape(s);
  for (const node of nodes) {
    node._links = degreeOf(node);
    node.r = gcRadius(node, node._links, maxDegree);
    //: A treemap cell is only so big: the dot stays inside it.
    if (node.cell) node.r = Math.min(node.r, Math.max(2.5, Math.min(node.cell.w, node.cell.h) * 0.36));
    node.colour = s.colourOf(node);
    node._cluster = shape === "clusters" ? node.category || "" : null;
    //: Which category a note stands in for the quiet bridge (`gcEdgeLook`),
    //: in every Force shape, not only Clusters (INBOX 1300 C41).
    node._bridgeCat = !s.tree && gcIsNote(node) ? node.category || "" : null;
    node._straight = Boolean(shape) && shape !== "organic";
  }
  const hubMin = gcHubSpokeMin(nodes.filter((node) => !node.isGroup).map((node) => node._links));
  for (const node of nodes) node._hub = !s.tree && !node.isGroup && node._links >= hubMin;
  //: Titles two notes or more share (INBOX 1300 C41, two "Ice Breakers:"
  //: with nothing to tell them apart): `gcLabelText` adds where each is.
  const titleCount = new Map();
  for (const node of nodes) if (gcIsNote(node) && node.preview) titleCount.set(node.preview, (titleCount.get(node.preview) || 0) + 1);
  s.dupTitles = new Set([...titleCount].filter(([, n]) => n > 1).map(([title]) => title));
  //: **A note with no position yet is placed here, not in the worker.**
  //: d3-force assigns its phyllotaxis spiral inside `forceSimulation`, which
  //: means the main thread has no positions at all until the first tick comes
  //: back: so the frame drawn the instant the payload arrives would be an
  //: empty canvas, and the gate's "first frame after data" would be timing a
  //: blank. The same spiral is laid down here (identical constants, so the
  //: worker keeps these rather than re-placing anything) and the first frame
  //: is a real picture of the notebook that then relaxes into its layout.
  if (!s.tree) {
    const centreX = width / 2;
    const centreY = height / 2;
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    gcSeedBesideNeighbours(s, nodes);
    nodes.forEach((node, index) => {
      if (Number.isFinite(node.x) && Number.isFinite(node.y)) return;
      const radius = 10 * Math.sqrt(0.5 + index);
      const angle = index * goldenAngle;
      node.x = centreX + radius * Math.cos(angle);
      node.y = centreY + radius * Math.sin(angle);
    });
  }
  // Everything the worker could still be about is now gone: whatever it says
  // next is about the previous node array and is dropped on arrival.
  //: From the map that was there (`gcTweenFromPrior`): a computed layout
  //: glides across; on the force layout the worker carries the notes, and
  //: only a note new to the picture is marked to fade in.
  if (!s.tree && prior.size) gcTweenFromPrior(s, nodes, prior, false);
  gcMarkLeaving(s, graphNodesRef, nodes);
  s.epoch += 1;
  s.nodes = nodes;
  s.edges = edges;
  graphNodesRef = nodes;
  graphAdjacency = s.adj;
  s.quadtreeDirty = true;

  initGraphMinimap();
  initGraphViews();

  if (s.tree) {
    gcStop(s);
    //: The positions a tree leaves behind are the tree's, not a force
    //: layout's, so nothing may be held from them afterwards.
    s.settledSig = null;
    if (reframe || !gcAutoFitDone(s)) {
      gcSetAutoFitDone(s, true);
      //: From the default camera (the first frame of a page load) the
      //: framing is instant, as the force layout's first fit is (INBOX 738):
      //: a glide from k 1 to an arc's 0.31 is the zoomed-in start reported.
      const untouched = !s.transform || (s.transform.k === 1 && s.transform.x === 0 && s.transform.y === 0);
      frameTree(s.svg, s.zoom, gcTreeFrameNodes(s.tree, nodes), width, height, s.tree.radial, s.tree.arc, untouched);
    }
    //: After the frame, which is set on where the notes are going.
    gcTweenFromPrior(s, nodes, prior);
  } else {
    //: The stale simulation could still have spent the flag during the
    //: awaits above (it is only cut off by the epoch bump, just now).
    if (reframe) gcSetAutoFitDone(s, false);
    gcStartWorker(nodes, edges, gcWorldFor(nodes.length, width, height), s, {
      alpha: viewPositions && !unplacedByView ? 0 : 1,
      freezeIds: seededUnpinnedIds,
      restore: restoring,
      //: Every note is where the last layout left it: see the hold in
      //: `gcStartWorker`. A saved view's own seeding is its own decision.
      holdIfSettled: !viewPositions && visibleNodes.every((n) => Number.isFinite(prior.get(n.id)?.x)),
    });
  }

  graphRenderStats(data, nodes, edges, colourMode, s.layoutKind);
  graphSyncTimeSlider(data, (cutoff) => {
    s.timeCutoff = cutoff;
    gcRequestDraw(s);
  });
  fillTracePickers(nodes);
  drawTrace();
  applyGraphHighlight();
  initGraphKeyboard();
  //: A full paint, because this is exactly the moment the dots are wrong: a
  //: different set of notes, at different places. A pan only ever moves the
  //: rectangle (`graphMinimapFrame`), so nothing else on that path repaints
  //: them, and the force layout's own repaint rides the worker's ticks, which
  //: a computed layout does not have at all.
  graphMinimapPaint();
  gcRequestDraw(s);
}

// --- the chrome around the drawing ------------------------------------------------
//
// The legend, the stats line and the time slider describe the data, not the
// drawing.

//: One entry per category (click to filter) or per cluster (click to
//: spotlight). A legend whose dots do not match the colours on screen is worse
//: than no legend, so which of the two it shows follows the colour mode.
//: The key a rule reads off a node, and the order its legend lists them in.
const GC_AGE_BUCKETS = ["Today", "This week", "This month", "This quarter", "Older"];
//: A note with no `type:` property, under the "Note type" rule.
const GC_NO_TYPE = "No type";
function gcRuleKey(rule, node) {
  if (rule === "kind") return node.kind || "note";
  if (rule === "type") return node.note_type || GC_NO_TYPE;
  if (rule === "space") return node.space_id || "default";
  if (rule === "tag") return (node.tags && node.tags[0]) || "No tag";
  if (rule === "file") return node.has_file ? "Has a file" : "No file";
  //: WORLD_CLASS_PLAN D5: the note's type (KG4's `type:` property).
  if (rule === "type") return node.note_type || "No type";
  if (rule === "age") {
    const days = node.created_at ? (Date.now() - Date.parse(node.created_at)) / 86400000 : Infinity;
    if (days <= 1) return GC_AGE_BUCKETS[0];
    if (days <= 7) return GC_AGE_BUCKETS[1];
    if (days <= 30) return GC_AGE_BUCKETS[2];
    if (days <= 90) return GC_AGE_BUCKETS[3];
    return GC_AGE_BUCKETS[4];
  }
  return node.category;
}
function gcRuleDomain(rule, data) {
  if (rule === "age") return GC_AGE_BUCKETS;
  if (rule === "file") return ["Has a file", "No file"];
  const keys = new Set(data.nodes.filter((n) => !n.isGroup).map((n) => gcRuleKey(rule, n)));
  return [...keys].sort((a, b) => String(a).localeCompare(String(b)));
}
function gcRuleScale(rule, data) {
  if (rule === "age") return d3.scaleOrdinal(GC_AGE_BUCKETS, ["#2f80ed", "#56a3f5", "#8ec2f7", "#c3dcf7", "#9aa1ad"]);
  if (rule === "file") return d3.scaleOrdinal(["Has a file", "No file"], ["#17bebb", "#9aa1ad"]);
  if (rule === "type") {
    //: A type's own colour (Note types, `type_colours` on the payload) wins,
    //: matched without case because a note's block may spell the name its
    //: own way; an untyped note is grey, like "No file"; any other type takes
    //: the colour its name hashes to (`categoryAutoDot`), the one the Colour
    //: sheet's preview shows as Automatic, so the two never disagree.
    //: Stored as a category palette key (the swatch picker's) or a hex.
    const hex = (c) => (Object.hasOwn(CATEGORY_PALETTE, c) ? CATEGORY_PALETTE[c] : c);
    const own = new Map(Object.entries(data.type_colours || {}).map(([name, c]) => [name.toLowerCase(), hex(c)]));
    return (key) => (key === GC_NO_TYPE ? "#9aa1ad" : own.get(String(key).toLowerCase()) || categoryAutoDot(key));
  }
  return d3.scaleOrdinal(gcRuleDomain(rule, data), graphCalmScheme());
}

//: One Tab stop for the legend's toggles (audit 1029 G20): seven buttons were
//: seven stops before the map. The arrows, Home and End walk them.
function graphLegendRove(legend) {
  const items = [...(legend?.querySelectorAll(".legend-toggle") || [])];
  items.forEach((item, index) => (item.tabIndex = index ? -1 : 0));
  if (!legend || legend.dataset.roved) return;
  legend.dataset.roved = "1";
  legend.addEventListener("keydown", (event) => {
    const list = [...legend.querySelectorAll(".legend-toggle")];
    const at = list.indexOf(document.activeElement);
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    const to = event.key === "Home" ? 0 : event.key === "End" ? list.length - 1 : at + step;
    if (at < 0 || !list[to] || (step === undefined && event.key !== "Home" && event.key !== "End")) return;
    event.preventDefault();
    list.forEach((item) => (item.tabIndex = item === list[to] ? 0 : -1));
    list[to].focus();
  });
}

function graphRenderLegend(data, colourMode, colour, clusterColour, ruleColour = null, groups = [], s = gcTab) {
  const legend = document.getElementById("graph-legend");
  if (!legend) return;
  legend.replaceChildren();
  if (s.hiddenIds.size) {
    const hidden = document.createElement("button");
    hidden.className = "legend-item legend-toggle legend-off";
    hidden.title = "Show the notes hidden from this map again";
    hidden.textContent = `${s.hiddenIds.size} hidden on this map. Show`;
    hidden.addEventListener("click", () => {
      s.hiddenIds.clear();
      renderGraph();
    });
    legend.appendChild(hidden);
  }
  // Groups lead the legend whatever the rule: they paint over it.
  groups.forEach((group, index) => {
    const off = Boolean(group.hiddenOnMap);
    const item = document.createElement("button");
    item.className = "legend-item legend-toggle legend-group";
    item.title = off ? `Show the notes matching “${group.query}” again` : `Hide the notes matching “${group.query}”`;
    item.classList.toggle("legend-off", off);
    item.setAttribute("aria-pressed", String(!off));
    const dot = document.createElement("span");
    dot.className = "legend-dot";
    dot.style.background = graphGroupColour(index);
    const count = [...graphGroupOf.values()].filter((i) => i === index).length;
    item.append(dot, document.createTextNode(`${group.query} (${count})`));
    item.addEventListener("click", () => {
      const next = graphGroups();
      if (next[index]) next[index].hiddenOnMap = !next[index].hiddenOnMap;
      graphSetGroups(next);
    });
    legend.appendChild(item);
  });
  if (ruleColour && !["category", "cluster", "topic"].includes(colourMode)) {
    for (const key of gcRuleDomain(colourMode, data)) {
      const token = `${colourMode}:${key}`;
      const off = graphHiddenKeys.has(token);
      const item = document.createElement("button");
      item.className = "legend-item legend-toggle";
      item.title = off ? `Show ${key} again` : `Hide ${key} from the map`;
      item.classList.toggle("legend-off", off);
      item.setAttribute("aria-pressed", String(!off));
      const dot = document.createElement("span");
      dot.className = "legend-dot";
      dot.style.background = ruleColour(key);
      item.append(dot, document.createTextNode(String(key)));
      item.addEventListener("click", () => {
        if (graphHiddenKeys.has(token)) graphHiddenKeys.delete(token);
        else graphHiddenKeys.add(token);
        renderGraph();
      });
      legend.appendChild(item);
    }
    return;
  }
  const entry = (title, dotColour, text, onClick, off) => {
    const item = document.createElement("button");
    item.className = "legend-item legend-toggle";
    item.title = title;
    if (off !== undefined) {
      item.classList.toggle("legend-off", off);
      item.setAttribute("aria-pressed", String(!off));
    }
    const dot = document.createElement("span");
    dot.className = "legend-dot";
    dot.style.background = dotColour;
    item.append(dot, document.createTextNode(text));
    item.addEventListener("click", onClick);
    legend.appendChild(item);
    return item;
  };
  //: GRAPH_PLAN KG6: a topic is named by what its notes share more than the
  //: notebook does; its entry says those terms and finds its notes.
  if (colourMode === "topic" && graphStructure?.topics) {
    for (const topic of graphStructure.topics) {
      const item = entry(
        nounCount(topic.size, "note") + (topic.terms.length ? `: ${topic.terms.map((t) => `${t.term} (${t.notes})`).join(", ")}` : ""),
        clusterColour(String(topic.id)),
        `${topic.name} (${topic.size})`,
        () => {
          graphHighlightIds = new Set(topic.ids);
          applyGraphHighlight();
          gcShowTopic(topic, clusterColour(String(topic.id)));
        }
      );
      item.dataset.topic = topic.id;
    }
    return;
  }
  gcHideTopic();
  if (colourMode === "cluster" && graphStructure) {
    graphStructure.clusters.forEach((cluster, position) => {
      entry(
        `${nounCount(cluster.size, "note")}, around "${cluster.core.preview}"` +
          (cluster.categories.length ? ` · ${cluster.categories.join(", ")}` : ""),
        clusterColour(String(position)),
        `${cluster.core.preview} (${cluster.size})`,
        () => {
          graphHighlightIds = new Set(cluster.ids);
          applyGraphHighlight();
        }
      );
    });
    if (graphStructure.orphan_count) {
      entry(
        "Notes with no link, no reply and no shared tag",
        gcTokens.muted,
        `unconnected (${graphStructure.orphan_count})`,
        () => {
          graphHighlightIds = new Set(graphStructure.orphans.map((n) => n.id));
          applyGraphHighlight();
        }
      );
    }
    if (graphHiddenCategories.size) {
      // The category filters still apply in this mode, they just have no
      // controls. Saying so beats a map quietly missing notes.
      const note = document.createElement("span");
      note.className = "legend-item";
      note.textContent = `${graphHiddenCategories.size} category filter${
        graphHiddenCategories.size === 1 ? "" : "s"
      } still on: switch to “By category” to change them`;
      legend.appendChild(note);
    }
    return;
  }
  for (const category of data.categories) {
    const off = graphHiddenCategories.has(category);
    entry(
      off ? `Show ${category} again` : `Hide ${category} from the map`,
      colour(category),
      category,
      () => {
        if (graphHiddenCategories.has(category)) graphHiddenCategories.delete(category);
        else graphHiddenCategories.add(category);
        renderGraph();
      },
      off
    );
  }
  //: **The one kind of node the legend never named.** INBOX 183, the owner:
  //: "idk what entities are". `data.categories` is built from the notes before
  //: the entity nodes are appended (`routes_graph.py`), so an entity has
  //: always been drawn in a colour with nothing in the legend to explain it:
  //: an extra dot in an extra colour, on a map of notes, with no word attached
  //: to it anywhere on the screen. This is the same sentence the Show
  //: section's '?' gives and the same one a hovered entity node gives, so the
  //: three cannot drift, and the entry filters like any other because an
  //: entity node carries "Entity" as its category.
  if (!data.categories.includes(GC_ENTITY_CATEGORY) && data.nodes.some((n) => n.type === "entity")) {
    const off = graphHiddenCategories.has(GC_ENTITY_CATEGORY);
    entry(
      GC_ENTITY_HELP,
      colour(GC_ENTITY_CATEGORY),
      `${GC_ENTITY_CATEGORY} (${data.nodes.filter((n) => n.type === "entity").length})`,
      () => {
        if (off) graphHiddenCategories.delete(GC_ENTITY_CATEGORY);
        else graphHiddenCategories.add(GC_ENTITY_CATEGORY);
        renderGraph();
      },
      off
    );
  }
}

//: **What the two kinds of line mean, said on the map** (INBOX 412). Only
//: while similarity lines are on it: with links alone there is one kind of
//: line and nothing to tell apart. A fact, not a toggle, so a `span` like the
//: cluster mode's filter note rather than a `.legend-toggle` button; the
//: longer sentence is the Show section's '?', and this entry's `title`.
function gcLegendEdgeKey(data, s = gcTab) {
  const legend = document.getElementById("graph-legend");
  //: Three channels and no more (INBOX 693, the owner: "should links
  //: visualise differently or have a different style based on distance,
  //: similarity, type of link etc??"): solid for a link, dashed for a
  //: suggestion by meaning; thickness and strength for how sure (a closer
  //: match, a reason deduced with more confidence, `gcDraw`); faint for a
  //: line between two category clusters. The key shows the ones this map has.
  const similar = (data?.edges || []).some((e) => e.kind === "similar");
  const category = new Map((data?.nodes || []).map((n) => [n.id, n.category || ""]));
  const id = (end) => (end && typeof end === "object" ? end.id : end);
  const cross =
    !graphLayoutIsComputed() &&
    (data?.edges || []).some((e) => e.kind !== "similar" && category.get(id(e.source)) !== category.get(id(e.target)));
  if (!legend || !data || !(similar || cross)) return;
  const key = document.createElement("span");
  key.className = "legend-item legend-edge-key";
  key.title =
    "Solid lines are links, thicker where the app is surer of a reason it found. Dashed lines join each note to its closest matches in meaning: darker is closer. " +
    "Faint lines run between two categories. Point at a note to see the scores.";
  const swatch = (kind, word) => {
    const line = document.createElement("span");
    line.className = `legend-line legend-line-${kind}`;
    line.setAttribute("aria-hidden", "true");
    key.append(line, document.createTextNode(word));
  };
  //: A link with a reason is drawn in the accent (`GC_EDGE_REASONED`), a
  //: plain one in --muted: the swatch is whichever this map mostly has, so
  //: the key never shows a line the map does not.
  const links = (data.edges || []).filter((e) => e.kind === "link");
  const reasoned = links.filter((e) => e.reason).length;
  swatch(reasoned * 2 > links.length ? "reasoned" : "link", "Link");
  if (similar) swatch("similar", "Similar");
  if (cross) swatch("cross", "Between categories");
  legend.appendChild(key);
}

//: **What a dot's size means, said on the map** (INBOX 1300 C37, the owner:
//: "the nodes are all the same size, should they be different??"; a question
//: is a report that the map did not say). A fact, not a toggle, like the line
//: key above: two dots and the Size rule's meaning. None says nothing.
const GC_SIZE_KEY = {
  connections: "Bigger dot, more links",
  length: "Bigger dot, longer note",
  recency: "Bigger dot, edited more recently",
};
function gcLegendSizeKey() {
  const legend = document.getElementById("graph-legend");
  const words = GC_SIZE_KEY[graphSizeMode()];
  if (!legend || !words) return;
  const key = document.createElement("span");
  key.className = "legend-item legend-edge-key legend-size-key";
  key.title = "Change what size means under Size, in the graph's options";
  //: Styled here, not in boot CSS (at its byte cap): the muted ink, the
  //: first dot at six tenths of the second.
  for (const scale of [0.6, 1]) {
    const dot = document.createElement("span");
    dot.className = "legend-dot";
    dot.style.background = gcTokens.muted;
    dot.style.transform = `scale(${scale})`;
    dot.setAttribute("aria-hidden", "true");
    key.appendChild(dot);
  }
  key.append(document.createTextNode(words));
  legend.appendChild(key);
}

//: A plain-language readout of what is on screen. The counts are facts about
//: this notebook and stay on the line; the sentence explaining how a layout
//: works is the same every time you read it, so it is the line's tooltip.
function graphRenderStats(data, nodes, edges, colourMode, layoutKind) {
  const line = document.getElementById("graph-stats");
  if (!line) return;
  const counts = { link: 0, thread: 0, similar: 0, filing: 0, map: 0 };
  for (const edge of edges) counts[edge.kind] = (counts[edge.kind] || 0) + 1;
  const noteCount = nodes.filter((n) => !n.isGroup).length;
  const parts = [nounCount(noteCount, "note")];
  if (counts.link) parts.push(nounCount(counts.link, "link"));
  if (counts.thread) parts.push(nounCount(counts.thread, "thread"));
  if (counts.similar)
    parts.push(`${counts.similar} similarity line${counts.similar === 1 ? "" : "s"}`);
  if (counts.filing) parts.push(`${counts.filing} filed under a category`);
  if (counts.map) parts.push(`${counts.map} on a mind map`);
  const shape =
    colourMode === "cluster" && graphStructure
      ? `${graphStructure.clusters.length} cluster${
          graphStructure.clusters.length === 1 ? "" : "s"
        }` +
        (graphStructure.small_clusters
          ? ` + ${graphStructure.small_clusters} pair${
              graphStructure.small_clusters === 1 ? "" : "s"
            }`
          : "") +
        `, ${graphStructure.orphan_count} connected to nothing.`
      : layoutKind === "tree"
        ? "filed left to right; replies branch off the note they answer."
        : layoutKind === "radial"
          ? "categories around the centre; replies branch off the note they answer."
          : layoutKind === "arc"
            ? "one line, filed left to right; arcs below show what answers what."
            : layoutKind === "treemap"
              ? "each category's area in proportion to its notes."
              : "";
  //: Notes with nothing joined to them draw as loose dots with no word on
  //: why (dog3-1026 row 17): say so, and say how to join two.
  const unlinked = noteCount > 0 && !edges.some((edge) => edge.kind === "link" || edge.kind === "thread");
  if (unlinked) parts.push("no links yet");
  line.textContent = parts.join(" · ");
  line.title = unlinked
    ? "No note is linked to another yet. Open a note's link button to join two, or select two notes here and press Link."
    : shape;
  graphSyncLayoutChip(layoutKind);
}

//: **The map says which layout it is in when it is not Force.** A saved Tree
//: or Arc is static by design (no drag, no settling), which read as a broken
//: graph to someone who had forgotten choosing it. The dock's chip names it
//: and opens the Layout choice (the gear's panel, or the phone's sheet).
function graphSyncLayoutChip(layoutKind) {
  const chip = document.getElementById("graph-layout-chip");
  if (!chip) return;
  const named = layoutKind && layoutKind !== "force";
  chip.classList.toggle("hidden", !named);
  if (named) setLabel(chip, `ph:tree-structure ${layoutKind[0].toUpperCase()}${layoutKind.slice(1)} layout`);
  if (chip._wired) return;
  chip._wired = true;
  chip.addEventListener("click", (event) => {
    event.stopPropagation();
    if (window.matchMedia(PHONE_TABS).matches) {
      if (!graphSheetClose) openGraphControlsSheet(chip);
    } else {
      setGraphOptionsOpen(true);
    }
    //: A timeout, not a frame: the wake-source ratchet counts frame loops, and
    //: this runs once after the panel or sheet is in place.
    setTimeout(() => focusSelect(document.getElementById("graph-layout")), 0);
  });
}

//: The time slider's bounds, recomputed every render. They used to be computed
//: once behind a flag that never reset, so any note created after the first
//: render sat beyond the slider's own "all time" end and stayed permanently
//: hidden once the filter had run. The guard below keeps what the user was
//: actually doing with it: parked at the end, or deliberately looking at an
//: earlier cut-off.
function graphSyncTimeSlider(data, apply) {
  const slider = document.getElementById("graph-time-slider");
  const label = document.getElementById("graph-time-label");
  if (!slider || !data.nodes.length) return;
  const stamps = data.nodes
    .map((n) => new Date(n.created_at || Date.now()).getTime())
    .filter(Number.isFinite);
  const min = stamps.length ? Math.min(...stamps) : Date.now();
  const max = stamps.length ? Math.max(...stamps) : Date.now();
  const previousMax = Number(slider.max);
  const wasAtEnd = !slider.dataset.graphInit || Number(slider.value) >= previousMax;
  slider.min = min;
  slider.max = max;
  slider.step = (max - min) / 100 || 1;
  slider.value = wasAtEnd ? max : Math.min(Number(slider.value), max);
  slider.dataset.graphInit = "1";
  const say = (value) => {
    if (!label) return;
    label.textContent =
      value >= max ? "All time" : `Up to ${new Date(value).toLocaleDateString()}`;
  };
  const set = (value) => {
    say(value);
    // `null` rather than the maximum when the slider is at its end: "no filter"
    // and "a cut-off that happens to be the newest note" are the same picture
    // but not the same state, and the debug surface reports which.
    apply(value >= max ? null : value);
  };
  slider.oninput = (event) => set(Number(event.target.value));
  say(Number(slider.value));
  set(Number(slider.value));
  graphWireTimePlay(slider, set);
}

// --- Phase 4: Play on the time slider --------------------------------------------------
//: Sweeps the cutoff from the first note to the last over about eight
//: seconds, so the notebook grows on screen in the order it was written.
//: A touch on the slider, or a second press, stops it where it is.
let gcTimePlayFrame = null;
function graphWireTimePlay(slider, set) {
  const button = document.getElementById("graph-time-play");
  if (!button || button._wired) return;
  button._wired = true;
  const setPlaying = (on) => {
    button.setAttribute("aria-pressed", String(on));
    button.title = on ? "Pause" : "Play through time";
    setLabel(button, on ? "ph:pause" : "ph:play");
  };
  const stop = () => {
    if (gcTimePlayFrame) cancelAnimationFrame(gcTimePlayFrame);
    gcTimePlayFrame = null;
    setPlaying(false);
  };
  button.addEventListener("click", () => {
    if (gcTimePlayFrame) {
      stop();
      return;
    }
    const min = Number(slider.min);
    const max = Number(slider.max);
    if (!(max > min)) return;
    const duration = 8000;
    const startValue = Number(slider.value) >= max ? min : Number(slider.value);
    const startAt = performance.now() - ((startValue - min) / (max - min)) * duration;
    setPlaying(true);
    const tick = (now) => {
      const value = Math.min(max, min + ((now - startAt) / duration) * (max - min));
      slider.value = value;
      set(value);
      if (value >= max) {
        stop();
        return;
      }
      gcTimePlayFrame = requestAnimationFrame(tick);
    };
    gcTimePlayFrame = requestAnimationFrame(tick);
  });
  slider.addEventListener("pointerdown", stop);
  setPlaying(false);
}

// --- the read-only debug surface -------------------------------------------------
//
//: `window.__graphDebug` exists so the gate script (scratchpad/ui-sweeps/
//: graph.js) can assert that a control changed *what is drawn* rather than
//: only that the control moved. It is deliberately a getter returning a frozen
//: snapshot: nothing outside this file can write to it, so it cannot become a
//: back door into the renderer's state, and reading it can never change what
//: the next frame draws.
Object.defineProperty(window, "__graphDebug", {
  configurable: false,
  get() {
    const t = gcTab.transform || { x: 0, y: 0, k: 1 };
    return Object.freeze({
      renderer: gcTab.canvas && !gcTab.canvas.classList.contains("hidden") ? "canvas" : "svg",
      nodes: gcTab.nodes.length,
      edges: gcTab.edges.length,
      layout: gcTab.layoutKind,
      colourMode: graphColourMode(),
      transform: Object.freeze({ x: t.x, y: t.y, k: t.k }),
      hovered: graphHoveredId,
      focusModeId: graphFocusModeId,
      hiddenCategories: Object.freeze([...graphHiddenCategories]),
      timeCutoff: gcTab.timeCutoff,
      trace: graphTrace ? Object.freeze([...graphTrace.ids]) : null,
      highlight: graphHighlightIds ? graphHighlightIds.size : 0,
      alpha: gcTab.alpha,
      ticks: gcTab.ticks,
      tickMs: gcTab.tickMs,
      lodNodes: gcTab.lodNodes || 0,
      labelsWanted: gcTab.labelsWanted,
      labelsDrawn: gcTab.labelsDrawn,
      labelsPriority: gcTab.labelsPriority,
      // Capped: this is a debug read on every frame's worth of geometry, and
      // a 2,000-label frame would put a megabyte through the getter.
      labelBoxes: gcTab.labelBoxes.slice(0, 300).map((b) => Object.freeze({ ...b })),
      firstFrameMs: gcTab.timing.firstFrame,
      lastFrameMs: gcTab.timing.lastFrame,
      frames: gcTab.timing.frames,
      radii: Object.freeze(gcTab.nodes.slice(0, 40).map((n) => n.r)),
      colours: Object.freeze(gcTab.nodes.slice(0, 40).map((n) => n.colour)),
      positions: Object.freeze(
        gcTab.nodes.slice(0, 40).map((n) => Object.freeze([Math.round(n.x), Math.round(n.y)]))
      ),
      // Enough geometry for a sweep to check the *shape* of a computed
      // layout rather than only that one was chosen: which node is where,
      // how deep the hierarchy put it, and where each edge's two ends are.
      // `positions` above cannot answer "does depth increase away from the
      // root" or "do two edges cross", which are the two questions the tree
      // report turns on. Capped like the labels, and for the same reason.
      nodeGeometry: Object.freeze(
        gcTab.nodes.slice(0, 300).map((n) =>
          Object.freeze({
            id: n.id,
            x: Math.round(n.x * 10) / 10,
            y: Math.round(n.y * 10) / 10,
            r: n.r,
            depth: n.depth == null ? null : n.depth,
            group: Boolean(n.isGroup),
          })
        )
      ),
      edgeGeometry: Object.freeze(
        gcTab.edges.slice(0, 300).map((e) =>
          Object.freeze([
            Math.round(e.source.x * 10) / 10,
            Math.round(e.source.y * 10) / 10,
            Math.round(e.target.x * 10) / 10,
            Math.round(e.target.y * 10) / 10,
          ])
        )
      ),
    });
  },
});

// --- GRAPH_PLAN Phase 4: the local map beside an open note or document ------------
//
//: The last open item of Phase 4, and the reason the surface object above
//: exists. The pane is a second `gcSurface` at `size: "pane"`: its own canvas,
//: camera, worker and hover state, so the Graph tab's node array, zoom and
//: minimap are untouched by anything that happens in it. It draws
//: `/graph/local` at depth 1 for whatever is open, wires none of the chrome
//: (no legend, no minimap, no time slider, no lasso, no node menu), and a
//: click on one of its notes opens that note rather than a popup anchored to a
//: canvas the reader is not looking at.

let graphPaneSurface = null;
//: What the pane is drawn for. "Follow what is open" is called from three
//: places and most calls change nothing, so this is what makes the common case
//: a comparison rather than a fetch and a relayout.
let graphPaneShownId = null;

function graphPaneEnsure() {
  if (graphPaneSurface) return graphPaneSurface;
  graphPaneSurface = gcSurface({
    size: "pane",
    boxId: "graph-pane-box",
    canvasId: "graph-pane-canvas",
    //: The pane's notes open where the reader already is. `flashEntry` is the
    //: app's own "go to this note", the same one the graph's node popup, the
    //: search results and a wiki link use.
    onNodeClick: (node) => {
      if (node.isGroup || typeof flashEntry !== "function") return;
      flashEntry(node.id);
    },
  });
  return graphPaneSurface;
}

//: The pane's colours are the tab's colours when the tab has drawn, and its own
//: category scale when it has not. A local map whose "Work" notes are a
//: different colour from the same notes on the Graph tab is worse than no
//: colour at all, and the tab's `colourOf` already carries the rule, the groups
//: and the cluster structure the reader chose.
function graphPaneColour(data) {
  if (gcTab.nodes.length) return gcTab.colourOf;
  const scale = graphCategoryScale(data.categories);
  return (node) => scale(node.category);
}

async function renderGraphPane(entryId) {
  const pane = document.getElementById("graph-pane");
  if (!pane || pane.hidden) return;
  const s = graphPaneEnsure();
  if (!gcEnsureCanvas(s)) return;
  const count = document.getElementById("graph-pane-count");
  const empty = document.getElementById("graph-pane-empty");
  const sequence = ++s.renderSeq;
  if (entryId == null) {
    graphPaneShownId = null;
    s.epoch += 1;
    gcStop(s);
    s.nodes = [];
    s.edges = [];
    s.adj = new Map();
    s.byId = new Map();
    s.quadtreeDirty = true;
    if (count) count.textContent = "No note open";
    if (empty) empty.hidden = false;
    gcRequestDraw(s);
    return;
  }
  const data = await apiJson(`/graph/local/${entryId}?${graphLocalQuery("pane", 1)}`).catch(() => null);
  if (!data || sequence !== s.renderSeq) return;
  graphPaneShownId = entryId;
  gcReadTokens(s);

  const nodes = data.nodes.map((n) => ({ ...n }));
  const edges = data.edges.map((e) => ({ ...e }));
  s.byId = new Map(nodes.map((n) => [n.id, n]));
  s.adj = new Map(nodes.map((n) => [n.id, new Set()]));
  for (const edge of edges) {
    const from = edge.source && edge.source.id != null ? edge.source.id : edge.source;
    const to = edge.target && edge.target.id != null ? edge.target.id : edge.target;
    if (s.adj.has(from)) s.adj.get(from).add(to);
    if (s.adj.has(to)) s.adj.get(to).add(from);
    edge.source = s.byId.get(from) || edge.source;
    edge.target = s.byId.get(to) || edge.target;
    edge._path2d = null;
  }
  const colourOf = graphPaneColour(data);
  s.colourOf = colourOf;
  const maxDegree = gcMaxDegree(s, nodes);
  for (const node of nodes) {
    node.r = gcRadius(node, (s.adj.get(node.id) || { size: 0 }).size, maxDegree);
    node.colour = colourOf(node);
  }
  gcResize(s);
  //: The same spiral the tab lays down before the worker has said anything, and
  //: for the same reason: without it the first frame after the payload lands is
  //: a blank canvas.
  const centreX = s.dims.w / 2;
  const centreY = s.dims.h / 2;
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  nodes.forEach((node, index) => {
    const radius = 10 * Math.sqrt(0.5 + index);
    node.x = centreX + radius * Math.cos(index * goldenAngle);
    node.y = centreY + radius * Math.sin(index * goldenAngle);
  });
  s.epoch += 1;
  s.nodes = nodes;
  s.edges = edges;
  s.layoutKind = "force";
  s.tree = null;
  s.quadtreeDirty = true;
  //: A pane is opened fresh at every note, so the camera frames the new
  //: neighbourhood every time rather than keeping the last one's.
  s.autoFitDone = false;
  s.fittedOnce = false;
  s.userZoomed = false;
  if (count) {
    count.textContent = nounCount(nodes.length, "note");
  }
  if (empty) empty.hidden = nodes.length > 1;
  gcStartWorker(nodes, edges, gcWorldFor(nodes.length, s.dims.w, s.dims.h), s);
  gcRequestDraw(s);
}

//: **Where the pane hangs, and what it is about.** Both answers change with the
//: tab, and the app has no event that says so (one `CustomEvent` exists in the
//: whole frontend, for an inline image), so this is called from the three
//: places that already know: `switchTab`, `flashEntry` and `openDocument`, each
//: wrapped once at boot by `graphPaneWire`. A poll would have to run for the
//: life of the page to catch three moments that announce themselves.
function graphPaneFollow() {
  const pane = document.getElementById("graph-pane");
  if (!pane) return;
  const tab = prefs.get("activeTab", null) || "notes";
  const hostId = tab === "notes" ? "sidebar" : tab === "documents" ? "doc-sidebar" : null;
  if (!hostId) {
    pane.hidden = true;
    //: A hidden pane's worker has nothing to solve for. The nodes keep their
    //: positions, so coming back is a redraw rather than a fresh explosion.
    if (graphPaneSurface) gcStop(graphPaneSurface);
    return;
  }
  const host = document.getElementById(hostId);
  if (!host) return;
  if (pane.parentElement !== host) host.appendChild(pane);
  const wanted =
    tab === "notes"
      ? typeof lastOpenedEntryId === "number"
        ? lastOpenedEntryId
        : null
      : graphPaneDocumentNote();
  //: **The pane arrives with the thing it is about, and leaves with it.** A
  //: panel headed "Local map" reading "No note open" is 263px of chrome with
  //: nothing in it, and the sidebar it hangs in has about 130px of room at
  //: 1440 once the categories and Most used have had theirs: measured with
  //: `errors.js`, an always-present pane put the column at 968 inside 761, so
  //: a reader who had opened nothing paid the whole cost of a map of nothing.
  //: The column scrolls either way (`overflow-y: auto`), so this is about
  //: what is worth scrolling past rather than about a clip.
  pane.hidden = wanted == null;
  if (pane.hidden) {
    if (graphPaneSurface) gcStop(graphPaneSurface);
    graphPaneShownId = null;
    return;
  }
  if (wanted === graphPaneShownId && graphPaneSurface && graphPaneSurface.nodes.length) {
    gcRequestDraw(graphPaneSurface);
    return;
  }
  renderGraphPane(wanted);
}

//: A document is not a node on `/graph/local`, which walks notes. The pane
//: beside one is the local map of the notes that document draws on, which is
//: the same relationship the Documents sidebar already lists; the first of them
//: is the one it centres on.
function graphPaneDocumentNote() {
  if (typeof currentDoc !== "object" || !currentDoc) return null;
  const notes = currentDoc.notes || currentDoc.entries || [];
  const first = notes[0];
  if (first == null) return null;
  if (typeof first !== "object") return first;
  return first.id != null ? first.id : first.entry_id != null ? first.entry_id : null;
}

function graphPaneWire() {
  const pane = document.getElementById("graph-pane");
  if (!pane || pane.dataset.wired === "yes") return;
  pane.dataset.wired = "yes";

  const toggle = document.getElementById("graph-pane-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const collapsed = pane.dataset.collapsed === "true";
      pane.dataset.collapsed = collapsed ? "false" : "true";
      toggle.setAttribute("aria-expanded", collapsed ? "true" : "false");
      toggle.title = collapsed ? "Hide the local map" : "Show the local map";
      toggle.setAttribute("aria-label", toggle.title);
      const icon = toggle.querySelector("i");
      if (icon) icon.className = collapsed ? "ph ph-caret-up" : "ph ph-caret-down";
      //: The box had no size while it was collapsed, so the canvas has to be
      //: measured again on the way back or it paints into the dimensions it
      //: last had.
      if (collapsed && graphPaneSurface) {
        gcResize(graphPaneSurface);
        gcRequestDraw(graphPaneSurface);
      }
    });
  }

  const focus = document.getElementById("graph-pane-focus");
  if (focus) {
    focus.addEventListener("click", () => {
      if (graphPaneShownId == null) return;
      graphFocusModeId = graphPaneShownId;
      switchTab("graph");
      renderGraph();
    });
  }

  //: Wrapped rather than called from inside each: `app.js` and `documents.js`
  //: are not the graph's files, and three edits across two of them to announce
  //: something the graph is the only consumer of is a worse trade than one
  //: wrapper each here, next to the thing that needs them.
  for (const name of ["switchTab", "flashEntry", "openDocument"]) {
    const original = window[name];
    if (typeof original !== "function" || original.__graphPaneWrapped) continue;
    const wrapped = function (...args) {
      const result = original.apply(this, args);
      if (result && typeof result.then === "function") {
        return result.then((value) => {
          graphPaneFollow();
          return value;
        });
      }
      graphPaneFollow();
      return result;
    };
    wrapped.__graphPaneWrapped = true;
    window[name] = wrapped;
  }
  graphPaneFollow();
}

onDomReady(graphPaneWire);

//: Remove and remake a set of links by note pair (INBOX 690). A remade link
//: gets a new id, written back so the next undo or redo finds it.
async function gcUnlinkPairs(pairs) {
  for (const pair of pairs) {
    await api(`/entries/${pair.from}/links/${pair.linkId}`, { method: "DELETE" }).catch(() => null);
  }
  renderGraph();
}

async function gcRelinkPairs(pairs) {
  for (const pair of pairs) {
    const body = JSON.stringify({ target_id: pair.to, reason: pair.reason || null });
    const made = await apiJson(`/entries/${pair.from}/links`, { method: "POST", body }).catch(() => null);
    pair.linkId = made?.links?.find((link) => link.entry_id === pair.to)?.link_id ?? pair.linkId;
  }
  renderGraph();
}

//: The map arrives over two `--ui-slow` (Brief 100): over `--ui-fast` it was
//: one frame on a busy machine, which read as the graph simply appearing.
//: The token is 0 with interface animations off, so that case cuts.
//: **A soft placeholder while the first map is on its way** (Brief 100, the
//: owner: "it kinda just appears after the page loads"). Measured on a first
//: open (scratchpad/g100 load.js FIRST=1): the tab's skeleton went and the
//: card stood empty for 430 to 730ms while /graph, the worker and its
//: warm-up ran, then the map arrived. The box breathes a faint glow from the
//: render's start until the canvas reveals (`gcReveal`), an empty or failed
//: read, or 6s, whichever is first; the glow fades as the map fades in
//: (graph-lazy.css).
function gcArriving(s, on) {
  const box = document.getElementById(s.boxId);
  if (!box) return;
  box.classList.toggle("graph-arriving", on);
  clearTimeout(s.arrivingTimer);
  if (on) s.arrivingTimer = setTimeout(() => box.classList.remove("graph-arriving"), 6000);
}

//: Shown once the first fit has balanced on the names it drew
//: (`gcBalanceFit`, hidden, so instant): shown at the guess, the balance was a
//: 3.5% zoom hop 50 ms after the first paint (36 notes, less motion, where the
//: reveal is a cut). The draw that balances reveals (`gcDraw`); the
//: timer is for a draw that never comes.
function gcRevealAfterBalance(s) {
  if (s.canvas?.style.opacity !== "0") return gcReveal(s);
  s.revealAfterFit = true;
  gcRequestDraw(s);
  clearTimeout(s.revealTimer);
  s.revealTimer = setTimeout(() => {
    if (!s.revealAfterFit) return;
    s.revealAfterFit = false;
    gcReveal(s);
  }, 250);
}

function gcReveal(s) {
  s.shown = true;
  gcArriving(s, false);
  if (s.canvas && s.canvas.style.opacity === "0") {
    //: Cut, not faded, for a reader who asked for less motion (Brief 100:
    //: "reduced motion keeps everything instant"); the token alone follows
    //: Interface animations, which play under the system hint.
    s.canvas.style.transition = gcStill() ? "none" : "opacity calc(var(--ui-slow) * 2) var(--ease-out)";
    s.canvas.style.opacity = "";
  }
}
