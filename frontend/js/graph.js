// Tessellate: Graph view subsystem (extracted from app.js).
//
// This is the "Graph" tab: the Obsidian-style force-directed map, its
// alternate layouts (tree/radial/arc), path tracing between two notes,
// drag-to-link, cluster colouring, keyboard driving, the node-edit popup,
// and "grow the map" (§9, §41). D3 is vendored locally (frontend/vendor): 
// the offline rule allows no CDN.
//
// Loaded as a THIRD classic (non-module) <script> tag, BEFORE app.js: see
// index.html. That order is not arbitrary and not interchangeable with the
// whiteboard.js split that preceded this one: app.js's own top-level wiring
// (the "$(\"graph-similarity\").addEventListener(\"change\", renderGraph)"
// cluster, and half a dozen like it, popup close/save, new-note save, the
// resize handler) passes functions and reads `let`s defined below *as bare
// identifiers, evaluated the moment that line of app.js runs*, not inside a
// closure, not deferred to a later event. In the original single file this
// worked regardless of position because function declarations hoist across
// the whole script; split into two <script> tags, each tag is its own
// hoisting scope, so if app.js ran first those lines would throw
// `ReferenceError: renderGraph is not defined` and: because that is
// synchronous top-level script code, abort the rest of app.js's own wiring
// partway through, not just the graph feature. So this file has to have
// already run before app.js reaches that code, meaning this script tag comes
// first. (whiteboard.js has no such bare top-level references into this
// file or into app.js, everything it calls across files happens inside a
// function body: which is why it could stay ordered after app.js.)
//
// This file's own top-level code needs only `document` (for the Escape-key
// handler that closes an open trace) and literal constants, nothing here
// needs app.js or whiteboard.js to have run first. It does need `d3` from
// /vendor/d3.v7.min.js, which the existing script order already guarantees.
//
// Everything else here calls back into app.js's shared helpers (`$`, `api`,
// `apiJson`, `toast`, `confirmDialog`, `switchTab`, `renderInlineMarkdown`,
// `loadEntries`, and more) the same way whiteboard.js does: at runtime,
// inside a function body, by which point every script has loaded.

// --- graph view (Wave E) ----------------------------------------------------------
// An Obsidian-style force-directed map. D3 is vendored locally
// (frontend/vendor): the offline rule allows no CDN.

let graphHiddenCategories = new Set(); // legend toggles (Wave M)
// Refs kept so the on-screen zoom buttons can drive the same behaviour as
// scroll-zoom, and hover-highlight can look up a node's neighbours.
let graphSvg = null;
let graphZoom = null;
let graphNodesRef = null;

//: **A pin as a step on the undo stack** (INBOX 898). `before` and `after` are
//: `{ x, y }` or null for "not pinned". Undo and Redo write the pin through
//: `PUT /graph/pin/{id}` and set it on the live node of whichever renderer is
//: drawn, so the map shows it without a reload.
//: **Only a node with a row to keep it on is written down** (B78: `PUT
//: /graph/pin/document:2` was a 422 in the owner's console). A note and a
//: document have one; a tag, an entity, a file or a topic does not, so its
//: pin holds for the session and the server is not asked. The one door for
//: every pin write, in this file and in graph-canvas.js.
function graphPinSave(id, x, y) {
  if (!/^(document:)?\d+$/.test(String(id))) return Promise.resolve(null);
  return apiJson(`/graph/pin/${id}`, { method: "PUT", body: JSON.stringify({ x, y }) });
}

async function graphSetPin(id, point) {
  const x = point ? point.x : null;
  const y = point ? point.y : null;
  await graphPinSave(id, x, y);
  const live = (typeof gcTab !== "undefined" && gcTab?.byId?.get(id)) || (graphNodesRef || []).find((n) => n.id === id);
  if (!live) return;
  live.graph_pin_x = x;
  live.graph_pin_y = y;
  live.fx = x;
  live.fy = y;
  if (point) {
    live.x = x;
    live.y = y;
  }
  if (typeof gcTab !== "undefined" && gcTab?.byId?.get(id)) {
    gcPost(point ? { type: "pin", id, x, y } : { type: "unpin", id }, gcTab);
    gcRequestDraw(gcTab);
  } else {
    renderGraph();
  }
}

//: **Pins are layout, not data, so releasing them is undoable** (K9, K10). The
//: pinned notes as `{ id, x, y }`, read off the live nodes, so an Undo can put
//: each one back exactly where it was held.
function graphPinnedRows() {
  const nodes = (typeof gcTab !== "undefined" && gcTab?.nodes) || graphNodesRef || [];
  return nodes
    .filter((n) => !n.isGroup && n.graph_pin_x != null && /^(document:)?\d+$/.test(String(n.id)))
    .map((n) => ({ id: n.id, x: n.graph_pin_x, y: n.graph_pin_y }));
}

async function graphUnpinAllNow() {
  const rows = graphPinnedRows();
  const result = await apiJson("/graph/unpin-all", { method: "POST" });
  graphHighlightIds = null;
  await renderGraph();
  //: The server's list covers what is off screen (a filter, a focus) too.
  return { rows: result.released || rows, count: result.unpinned };
}

async function graphRestorePins(rows) {
  if (!rows.length) return;
  await apiJson("/graph/pins", { method: "PUT", body: JSON.stringify({ pins: rows }) });
  await renderGraph();
}

function graphPinStep(label, changes) {
  const each = (key) => async () => {
    for (const change of changes) await graphSetPin(change.id, change[key]);
  };
  if (changes.length) pushUndo(label, each("before"), each("after"));
}
// A saved view's node positions (GRAPH_PLAN Phase 5, INBOX 275's neighbour
// row), one render's worth. `graphApplyView` stashes `view.positions` here;
// the next `renderGraphCanvas()` (graph-canvas.js)
// its own `set()` calls trigger reads and clears it, and every render after
// that (the same `graphApplyView` call fires several more, one per control
// it restores: layout, colour, physics, entities...) just inherits the
// seeded positions forward through `prior`, the same as any other re-render
// already does. See that function's node-build step for the decision this
// exists to carry out: a restored arrangement holds, it does not re-settle.
let graphPendingViewPositions = null;
let graphMinimapTick = 0; // throttles minimap repaints during a cooling layout
//: A no-op kept for the label tickbox's handler (wiring.js): the canvas draws
//: its names in the frame, so there is no label layer to catch up.
let graphCatchUpLabels = () => {};
let graphDims = { w: 0, h: 0 };
// Set once the camera has auto-framed the map for the tab's current visit,
// and cleared again by switchTab() on the next fresh entry, see the two
// uses below for why. `renderGraph()` alone can't tell "just opened the
// tab" from "a filter checkbox changed" apart; the caller has to say which.
let graphAutoFitDone = false;
let graphHoveredId = null; // node the pointer is over (spotlight its links)
let graphAdjacency = null; // Map<id, Set<neighbourId>>


function graphNodeRadius(node) {
  //: The canvas renderer sizes a node by its *degree* (GRAPH_PLAN.md §5 Phase
  //: 1: `4 + 2·√degree`, clamped) and stores the answer on the node, because
  //: degree is the one thing about a graph a reader can check by looking. Every
  //: caller that only needs "how big is this dot", `fitGraphToView`,
  //: `graphNodeUnder`, the minimap: then gets the right number on either
  //: renderer without knowing which one drew it.
  if (node.r != null) return node.r;
  // A category heading in a tree layout is a fixed size, it has no access
  // count of its own, and sizing it by one would be inventing a number.
  if (node.isGroup) return node.id === "root" ? 14 : 11;
  
  // Sized dynamically based on PageRank centrality (hub importance) and usage.
  // This physically represents the most important notes in the Knowledge Graph.
  const centralityBonus = node.centrality ? Math.min(12, node.centrality * 800) : 0;
  const accessBonus = Math.min(6, Math.sqrt(node.access_count || 0) * 1.5);
  
  return 9 + Math.max(centralityBonus, accessBonus);
}

// --- graph layouts (§9) -----------------------------------------------------------
//
// Asked for directly: "can you add different types of graph views… like tree
// graph diagrams and the like". A layout decides *where* a note goes; the
// styling is a separate question. Force is the default because it shows the
// links; the trees are here because most notebooks have far more filing than
// links, and a force graph of mostly-unlinked notes is a cloud of dots.
//
// The hierarchy is real data, not an invention: notebook → category → note,
// with a note's replies (`parent_id`, the train-of-thought threads) nested
// under the note they answer, so a thread reads as one branch.

function graphLayout() {
  const saved = prefs.get("graph-layout", null);
  return ["force", "tree", "radial", "arc", "treemap"].includes(saved) ? saved : "force";
}

//: **Tree, Radial and Arc compute every position, so nothing in them moves.**
//: Reported on 2026-09-09: "on the other graph view types, they all have the
//: dotted border as they are static but that shouldnt be the case ... I was
//: on the tree graph, I test double clicked on a node and it broke them all
//: out of position."
//:
//: Both halves have the same cause. A computed layout holds its nodes by
//: setting `fx`/`fy` on every one of them, and `fx != null` is exactly the
//: test the held ring and the pin toggle read: so every node in a tree wore
//: the ring that means "you pinned this", and a double click cleared one
//: node's `fx`, handing it back to the force simulation, which re-solved from
//: there and pulled the whole tree apart.
//:
//: The decision, and it is the one the layouts already imply: a computed
//: layout is read-only for position. The shape is the meaning in a tree, a
//: ring or an arc, and a node dragged out of it makes the picture a lie. So
//: no ring, no drag, no double-click pin here. Pan, zoom, hover, select and
//: the node menu are untouched: nothing that reads the graph is lost, only
//: the two gestures that would rearrange a layout the app arranged.
function graphLayoutIsComputed() {
  return graphLayout() !== "force";
}

// Gravity and Spread scale the force simulation, and the tree layouts do not
// run one: their positions come from the hierarchy. Left enabled they are two
// controls that move, save, and change nothing, which reads as a broken app
// rather than an inapplicable setting. Disabled, with the reason on hover.
function setGraphPhysicsEnabled(layoutKind) {
  const applies = layoutKind === "force";
  const box = $("graph-physics");
  if (!box) return;
  const why = applies
    ? ""
    : "Only applies to the Force (web) layout: the other layouts' positions come from the filing hierarchy, not physics.";
  box.classList.toggle("is-disabled", !applies);
  for (const id of ["graph-gravity", "graph-spread", "graph-link-force"]) {
    const slider = $(id);
    if (!slider) continue;
    slider.disabled = !applies;
    // Restore the slider's own description when it applies again, rather than
    // leaving the explanation of why it did not.
    if (applies) {
      slider.title = {
        "graph-gravity": "How strongly notes pull together",
        "graph-spread": "How far apart linked notes sit",
        "graph-link-force": "How hard each link pulls its two notes together",
      }[id];
    } else {
      slider.title = why;
    }
  }
  // The labels are separate elements, so they need the attribute too or the
  // hover explanation is missing on exactly the words being greyed out.
  for (const label of box.querySelectorAll("label[for]")) {
    label.title = why;
  }
  //: The View section's Shape is the Force layout's too (the owner,
  //: 2026-10-10: "the graph shape options shouldnt be enabled when on a view
  //: other than force"): the worker's shapes are sets of forces, and Tree,
  //: Radial and Arc place every note by rule. Dimmed with its reason, the
  //: same as the sliders, rather than hidden.
  const shape = $("graph-shape");
  if (shape) {
    shape.disabled = !applies;
    shape.title = applies ? "How the force layout arranges itself" : "Shape applies to the Force layout only: pick Force under Layout to use it.";
    $("graph-shape-row")?.classList.toggle("is-disabled", !applies);
    const label = $("graph-shape-label");
    if (label) label.title = applies ? "" : shape.title;
  }
}

// A category level in a tree layout. It is a real node in the drawing so the
// join, the colours and the labels all work unchanged, but it is not a note,
// so anything that would open or edit one has to check.
function graphGroupNode(category) {
  return {
    id: `group:${category}`,
    isGroup: true,
    preview: category,
    category,
    access_count: 0,
    pinned: false,
  };
}

// Row height and column width for the tree. Fixed sizes, not a bounding box:
// `d3.tree().size([...])` squeezes every leaf into the panel's height, so a
// notebook with 29 notes got 18 pixels a row and the labels printed on top of
// each other (reported with a photo). `nodeSize` gives each note the room a
// label needs and lets the tree be as tall as it is, the panel pans and
// zooms, which is what those controls are for.
const TREE_ROW = 34;
const TREE_COL = 235;

// The radial is the opposite problem: it is a shape you read whole, so it has
// to fit the panel, and a fixed radius meant a 29-note notebook was drawn at
// 0.55×: every label technically present and none of them readable. Size the
// rings from the panel instead, and only grow past it when the notes need the
// circumference (below ~RADIAL_ARC pixels of arc each, labels collide).
const RADIAL_ARC = 22; // arc length a note needs on its ring
const RADIAL_LABEL = 118; // room the labels take outside the outermost ring
// A category name is written along its spoke, pointing out, so its ring has
// to clear the notes' ring by more than that name is long.
const RADIAL_GAP = 82;
// A reply hangs one shorter step outside the note it answers, and since a
// lone reply inherits its parent's angle exactly, the parent's label is
// written straight down the same spoke. That is why an intermediate note is
// labelled shorter than a leaf (RADIAL_STEM below): the step has to clear it.
const REPLY_RING = 78;

// The arc layout (§9's third hierarchy view, beside tree and radial): every
// node, category, note and reply alike, sits on one baseline, in the same
// left-to-right order a depth-first walk of the filing hierarchy would print
// them in (so a category's notes stay contiguous), and a parent-child edge is
// a shallow arc under the line instead of a tree's elbow or a radial's ring.
// It reads at a glance what tree/radial cannot: how many branches a
// notebook's filing has and how deep any one of them runs, in the width of a
// single row rather than the height of a tree or the footprint of a circle.
const ARC_STEP = 58; // horizontal spacing per node


// Where each ring goes. Every constraint here is a thing that was measured
// going wrong: categories too tight to name, notes too tight to label, the
// whole circle too big for the panel, or, just as bad, needlessly small in
// a panel with room to spare.
function radialRings(leafCount, groupCount, rings, width, height) {
  // The floor matters as much as the arc: a dozen categories all radiating
  // from a 58px ring read as one blob at the centre, whatever the maths said
  // about them technically not touching. It grows with the count, because
  // four categories on that same ring only look sparse.
  const inner = Math.max((groupCount * RADIAL_ARC) / (2 * Math.PI), 40 + groupCount * 3);
  const room = Math.max(Math.min(width, height) / 2 - 12, 130) - RADIAL_LABEL;
  const extra = rings > 2 ? REPLY_RING : 0;
  const notes = Math.max(
    (leafCount * RADIAL_ARC) / (2 * Math.PI),
    inner + RADIAL_GAP,
    // Fill the panel when it is bigger than the minimum, a readable circle
    // is a big one. `frameTree` zooms out when the minimum wins instead.
    Math.min(room - extra, 320)
  );
  return { inner, notes, outer: notes + extra };
}

//: True when following `node`'s replies-to chain comes back to it. A loop
//: would make the hierarchy infinite, so such a note hangs off its category.
function replyLoops(node, byId) {
  const seen = new Set([node.id]);
  for (let at = byId.get(node.parent_id); at; at = byId.get(at.parent_id)) {
    if (seen.has(at.id)) return true;
    seen.add(at.id);
  }
  return false;
}

//: GRAPH_PLAN VC11 (D3's hierarchy layouts as a category overview): the
//: notebook as a treemap, one rectangle a category with its area in proportion
//: to how many notes it holds, each note a dot in a cell of its category's
//: rectangle. Replies are cells of their category like any note: the shape is
//: about where the notes are filed, not about what answers what, so it draws
//: no lines (`links` is empty) and a category's rectangles tile the whole
//: width and height with no padding between them, so the areas stay exact; the
//: gap between two categories is drawn, not laid out (`gcDrawTreemap`). Each
//: note keeps its cell's size so its dot never outgrows it.
function layoutTreemap(nodes, width, height) {
  const byCategory = new Map();
  for (const node of nodes) {
    if (!byCategory.has(node.category)) byCategory.set(node.category, []);
    byCategory.get(node.category).push(node);
  }
  const done = { nodes: [], links: [], radial: false, arc: false, vertical: false, treemap: [] };
  if (!nodes.length) return done;
  const root = d3
    .hierarchy({
      children: [...byCategory].map(([category, notes]) => ({ category, children: notes.map((note) => ({ note })) })),
    })
    .sum((d) => (d.note ? 1 : 0))
    .sort((a, b) => b.value - a.value);
  d3
    .treemap()
    .size([width, height])
    .tile(d3.treemapSquarify)
    .paddingInner((d) => (d.depth === 0 ? 0 : 2))
    .paddingTop((d) => (d.depth === 1 ? 18 : 0))(root);
  for (const group of root.children) {
    done.treemap.push({ category: group.data.category, count: group.value, x0: group.x0, y0: group.y0, x1: group.x1, y1: group.y1 });
    for (const leaf of group.children) {
      const node = leaf.data.note;
      node.x = (leaf.x0 + leaf.x1) / 2;
      node.y = (leaf.y0 + leaf.y1) / 2;
      node.fx = node.x;
      node.fy = node.y;
      node.cell = { w: leaf.x1 - leaf.x0, h: leaf.y1 - leaf.y0 };
      node.depth = 2;
      node.isLeaf = true;
      node.shared = false;
      done.nodes.push(node);
    }
  }
  return done;
}

function layoutHierarchy(nodes, kind, width, height) {
  if (kind === "treemap") return layoutTreemap(nodes, width, height);
  // Build parent → children from the notes themselves.
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const groups = new Map();
  for (const node of nodes) {
    if (!groups.has(node.category)) groups.set(node.category, graphGroupNode(node.category));
  }
  const root = { id: "root", isGroup: true, preview: "Notebook", category: "", access_count: 0 };
  const children = new Map([[root.id, [...groups.values()]]]);
  for (const group of groups.values()) children.set(group.id, []);
  //: Every note's list exists before any is filled: a reply listed ahead of
  //: the note it answers looked its parent's list up before that note's own
  //: turn had made it, and `undefined.push` threw on every tree, radial and
  //: arc layout of such a notebook (the owner's log, INBOX 579: "switching
  //: the graph layout does nothing").
  for (const node of nodes) children.set(node.id, []);
  for (const node of nodes) {
    // A reply hangs off the note it answers, wherever that note is filed,
    // splitting a thread across categories would lose the thing it is.
    const parent =
      node.parent_id != null && byId.has(node.parent_id) && !replyLoops(node, byId)
        ? byId.get(node.parent_id)
        : groups.get(node.category);
    children.get(parent.id).push(node);
  }

  const laid = d3.hierarchy(root, (d) => children.get(d.id) || []);
  const radial = kind === "radial";
  const arc = kind === "arc";
  //: **In a portrait map the arc runs down, not across** (INBOX 430, "Arc view
  //: doesn't fit the screen"). One baseline slot per note is a line
  //: `count x ARC_STEP` long, and laid across a 362px phone map it is the
  //: short side of the screen: measured with `graphphone.js`, 430 notes drew
  //: 6,221px wide at the fit's floor. Down the long side it is half the
  //: squeeze, and the arcs bow to the left of it with the labels to the
  //: right, the way the tree writes them (`arcPath`, graph-canvas.js).
  const vertical = arc && height > width * 1.15;
  if (arc) {
    // Pre-order: a category is visited before any of its notes, and each
    // note before its own replies, so walking the hierarchy in this order
    // and handing out one baseline slot per stop keeps every branch
    // contiguous, the same property `separation` gives the tree and radial
    // layouts a different way.
    let slot = 0;
    laid.eachBefore((point) => {
      point.x = vertical ? 0 : slot * ARC_STEP;
      point.y = vertical ? slot * ARC_STEP : 0;
      slot += 1;
    });
  } else if (radial) {
    // `d3.tree`, not `d3.cluster`: cluster rings a node by its *height*, so a
    // category that happened to contain a thread was drawn one ring closer in
    // than its siblings and the circle came out ragged. Here a ring means a
    // depth, notebook, category, note, reply, which is what the view says
    // it means.
    d3
      .tree()
      .size([2 * Math.PI, 1])
      // Notes under different categories need more air than siblings, and the
      // gap has to shrink as the circle grows, the standard radial rule.
      // Categories get a wedge of their own on top of that, or the ones with
      // a single note in them end up sharing a slot with their neighbour.
      .separation((a, b) =>
        a.depth === 1 ? 2 : (a.parent === b.parent ? 1 : 2) / a.depth
      )(laid);
    const rings = radialRings(
      // Those wedges are real circumference, so count them: sizing the ring
      // off the notes alone would under-measure it by a third.
      (laid.leaves().length || 1) + groups.size,
      groups.size,
      laid.height || 1,
      width,
      height
    );
    const deep = Math.max((laid.height || 1) - 2, 1);
    laid.each((point) => {
      if (!point.depth) point.y = 0;
      else if (point.depth === 1) point.y = rings.inner;
      else {
        point.y = rings.notes + ((point.depth - 2) / deep) * (rings.outer - rings.notes);
      }
    });
  } else {
    d3.tree().nodeSize([TREE_ROW, TREE_COL])(laid);
  }

  const placed = [];
  const links = [];
  laid.each((point) => {
    const node = point.data;
    if (radial) {
      // d3's radial convention: x is the angle, y the distance out.
      node.angle = point.x;
      node.radius = point.y;
      node.x = point.y * Math.cos(point.x - Math.PI / 2);
      node.y = point.y * Math.sin(point.x - Math.PI / 2);
    } else if (arc) {
      // Already the real coordinates, assigned above, once, in traversal
      // order, and never touched again.
      node.x = point.x;
      node.y = point.y;
    } else {
      node.x = point.y; // depth runs left → right
      node.y = point.x;
    }
    node.fx = node.x;
    node.fy = node.y;
    node.depth = point.depth;
    node.isLeaf = !point.children;
    // A lone child inherits its parent's row (or, on the radial, its angle),
    // so the parent's label is written straight down the line joining them.
    // Only *that* parent has to keep its label short.
    node.shared = Boolean(point.children?.some((child) => child.x === point.x));
    placed.push(node);
    if (point.parent) {
      links.push({
        source: point.parent.data,
        target: node,
        // By what it hangs from, not by `parent_id`: a reply whose thread
        // loops, or whose parent is filtered off the map, is filed.
        kind: point.parent.data.isGroup ? "filing" : "thread",
      });
    }
  });
  return { nodes: placed, links, radial, arc, vertical };
}

// A tree drawn with straight diagonals reads as a fan of loose string. Elbows
// (horizontal out, vertical across, horizontal in) are what makes it look
// like a tree diagram, and on the radial one, arcs that follow the rings.
function hierarchyPath(link, radial) {
  const { source: a, target: b } = link;
  if (radial) {
    return d3
      .linkRadial()
      .angle((d) => d.angle)
      .radius((d) => d.radius)({ source: a, target: b });
  }
  const mid = (a.x + b.x) / 2;
  return `M${a.x},${a.y}C${mid},${a.y} ${mid},${b.y} ${b.x},${b.y}`;
}

// The arc layout's own edge shape: every node sits on the same baseline (see
// `layoutHierarchy`'s `arc` branch), so a parent-child edge is a flattened
// half-ellipse dipping below the line rather than a tree's elbow or a
// radial's ring-following curve. A pre-order walk always visits a parent
// before its children, so `a.x < b.x` here always: the arc only ever needs
// to sweep one way.
function arcPath(link) {
  const { source: a, target: b } = link;
  //: A baseline running down (a portrait map, `layoutHierarchy`): the same
  //: flattened half-ellipse turned on its side, bowing left of the line so
  //: the labels to its right stay clear.
  if (Math.abs(b.x - a.x) < 0.5 && b.y !== a.y) {
    const half = Math.max(Math.abs(b.y - a.y) / 2, 1);
    return `M${a.x},${a.y}A${half * 0.6},${half} 0 0,${a.y <= b.y ? 0 : 1} ${b.x},${b.y}`;
  }
  const rx = Math.max((b.x - a.x) / 2, 1);
  const ry = rx * 0.6; // flatter than a true semicircle, a full one over a
  // long span dominates the map more than the connection it is drawing.
  return `M${a.x},${a.y}A${rx},${ry} 0 0,1 ${b.x},${b.y}`;
}

//: How far the widest arc stands off the baseline (`arcPath`: ry is 0.6 of
//: half the span). The fits reserved 0.3 to 0.32 of the whole line for it,
//: but the widest arc is the root to its last category, which is a small
//: fraction of the line when the last category is big; the reserve was empty
//: sky and the line sat low or high by that much (K7). Measured from the links.
function arcRise(links, fallback) {
  let rise = 0;
  for (const l of links || []) rise = Math.max(rise, ((l.target.x - l.source.x) / 2) * 0.6);
  return rise || fallback;
}

// A tall tree does not want to be squeezed into the panel: zoomed to fit, 29
// rows of text become illegible. Fit the *width*, never magnify past 1:1, and
// start at the top, the panel pans, and a readable tree you scroll beats a
// complete one you can't read.
function frameTree(svg, zoomBehavior, nodes, width, height, radial, arc = false, instant = false) {
  //: In the part of the map the overlays and open panels leave (INBOX 792,
  //: `gcFitInsets`), as the force layout's fit is.
  const ins = typeof gcTab !== "undefined" && gcTab.svg === svg ? gcFitInsets(gcTab) : null;
  const offX = ins ? ins.left : 0;
  const offY = ins ? ins.top : 0;
  if (ins) {
    width = Math.max(1, width - ins.left - ins.right);
    height = Math.max(1, height - ins.top - ins.bottom);
  }
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  // Labels stick out past the node they belong to: to the right in a tree, in
  // every direction on a radial. The canvas has no element to measure, so the
  // box is the node positions plus a margin for them.
  let box = {
    x: Math.min(...xs) - 40,
    y: Math.min(...ys) - 30,
    width: Math.max(...xs) - Math.min(...xs) + 200,
    height: Math.max(...ys) - Math.min(...ys) + 60,
  };
  //: **An arc's arcs are part of it** (INBOX 544, the owner: it "starts a
  //: little too close and too high up"). The canvas renderer has nothing to
  //: `getBBox`, so the box above was the baseline alone, ±30px: the arcs
  //: bowing above it (up to 0.3 of the span, `arcPath`) and the labels
  //: hanging below were outside the frame, which centred the bare line and
  //: zoomed in until it filled the width.
  //: **A radial's names hang under its dots on every side** (the canvas
  //: renderer centres a label under its node), so its pad is the same left
  //: and right. The tree's +200 to the right only, kept above for the
  //: labels a tree draws beside its dots, put the ring 60px left of the
  //: view's centre (the owner, 2026-10-10: "it put me on a random corner").
  if (radial) {
    box = {
      x: Math.min(...xs) - 90,
      y: Math.min(...ys) - 30,
      width: Math.max(...xs) - Math.min(...xs) + 180,
      height: Math.max(...ys) - Math.min(...ys) + 60,
    };
  }
  //: **A treemap is framed by its rectangles** (the caller passes their
  //: corners, `corner: true`): the headers sit above and beside the dots, so
  //: the dots' own box would crop them and let the minimap sit on a name.
  const whole = nodes.length > 0 && nodes.every((n) => n.corner);
  if (whole) {
    box = {
      x: Math.min(...xs),
      y: Math.min(...ys),
      width: Math.max(...xs) - Math.min(...xs),
      height: Math.max(...ys) - Math.min(...ys),
    };
  }
  if (arc) {
    const spanXs = Math.max(...xs) - Math.min(...xs);
    const spanYs = Math.max(...ys) - Math.min(...ys);
    const rise = arcRise(typeof gcTab !== "undefined" ? gcTab.tree?.links : null, 0.3 * spanXs);
    box = spanXs >= spanYs
      ? { x: Math.min(...xs) - 40, y: Math.min(...ys) - rise - 20, width: spanXs + 80, height: rise + 120 }
      : { x: Math.min(...xs) - 0.3 * spanYs - 20, y: Math.min(...ys) - 30, width: 0.3 * spanYs + 240, height: spanYs + 60 };
  }
  const minX = box.x - 10;
  const maxX = box.x + box.width + 10;
  const minY = box.y - 10;
  const maxY = box.y + box.height + 10;
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  // A radial is a shape you read whole, so both dimensions have to fit. A
  // tree grows downwards without limit, so squeezing it into the panel is
  // exactly what made 29 rows unreadable, but a notebook that *nearly* fits
  // is worth a small zoom-out to see whole, and only falls back to panning
  // when the price of fitting would be text you can't read.
  //: An arc keeps a screen margin either side for the end labels, which are
  //: drawn at their own size whatever the zoom (INBOX 544).
  const edge = arc ? 200 : 20;
  const both = Math.min((width - edge) / spanX, (height - 20) / spanY);
  //: **An arc is framed whole** (INBOX 430, "Arc view doesn't fit the
  //: screen"): it is one line read end to end, and a line cut off at the edge
  //: of the screen reads as the whole of it. Its floor is the fit itself,
  //: whatever it costs the labels (they return as you zoom in, like any
  //: map's). A tree fits when it nearly does and otherwise fits its width.
  //: "Nearly" was 0.8; at 0.55 a 34-note tree ran a column off the top and
  //: bottom of the map (the owner, round 2, and INBOX 792: fit "should be
  //: based on ... the screen resolution/size"), so it is 0.4 now.
  const fit = radial || arc || whole || both >= 0.4 ? both : (width - 20) / spanX;
  //: A radial the same (measured before: 1,051px across a 362px phone map
  //: and a 997px tablet one at the 0.35 floor).
  const scale = arc || radial || whole ? Math.min(1, fit) : Math.max(0.35, Math.min(1, fit));
  //: Where it does not fit, **the root is centred** (INBOX 430, the owner:
  //: "the Tree view sits at the top instead of centred"). A tree's root is
  //: the middle of its column, not its top, so anchoring the top edge put
  //: the first category's notes in view and the notebook and its categories
  //: a screen or more below. The root at the centre of the map shows the
  //: shape the view is named for, with its branches going off either way.
  const root = nodes.find((n) => n.depth === 0);
  const tx =
    spanX * scale <= width - 20
      ? width / 2 - scale * (minX + maxX) / 2
      : 10 - scale * minX;
  const ty =
    spanY * scale <= height - 20
      ? height / 2 - scale * (minY + maxY) / 2
      : root
        ? height / 2 - scale * root.y
        : 10 - scale * minY;
  //: Same rule as `fitGraphToView`: see the note beside its own check.
  if (!graphMinimapFinite(tx, ty, scale)) return;
  const framed = d3.zoomIdentity.translate(tx + offX, ty + offY).scale(scale);
  //: Instant is applied now, not as a zero-length transition: d3 runs that
  //: on its next timer frame, and the canvas paints one frame before it.
  //: As long as the notes' own glide (`GC_LAYOUT_MS`), so frame and notes
  //: arrive together.
  if (instant) svg.interrupt().call(zoomBehavior.transform, framed);
  else svg.transition().duration(graphGlideMs(700)).call(zoomBehavior.transform, framed);
}

// --- tracing a path between two notes (§9) -----------------------------------
//
// The question a graph answers better than any list, *how are these two
// related?*: and the one this view could not answer at all. Everything above
// shows you **that** notes connect; this shows you the route, and names each
// step: a link somebody made, a reply, or a tag the two share.
//
// The search itself is on the server (`entry/paths.py`, `GET /graph/path`) and
// is shared with the AI's `path_between` tool, deliberately: a picture and an
// answer that disagree about what is connected is worse than either alone.

//: The traced path, or null. `{ ids: [...], steps: [...] }`, ids in order, so
//: the drawing can look up consecutive pairs without re-deriving them.
let graphTrace = null;

//: **Every route between the two notes, best first, and which one is showing.**
//: Asked for directly: "allow for multiple paths to be displayed if they
//: exist." `/graph/path` now returns `routes: [...]` alongside the best one it
//: always returned, so `graphTrace` above keeps meaning "the route currently
//: being read" and nothing that already depended on it had to change.
//:
//: The map draws *all* of them at once, each in its own colour, with the
//: selected one solid and the rest ghosted, because the answer to "is that the
//: only way these connect?" is a picture, and switching between routes one at a
//: time never shows you that there are three.
let graphTraceRoutes = [];
let graphTraceIndex = 0;

// The two pickers, filled from whatever the map is currently showing. Rebuilt
// on every render because the map's contents change: and the selection is
// carried across, since a rebuild that silently forgets which notes you were
// asking about is a control that undoes your work.
let traceModeActive = false;
let traceFromNode = null;
let traceToNode = null;

// The graph was redrawn, so the two picked nodes are stale objects from the
// previous layout. Re-point them at the new ones by id, dropping them instead
// would mean a filter change silently threw away the trace you were reading.
function fillTracePickers(nodes) {
  const byId = new Map(nodes.map((n) => [String(n.id), n]));
  if (traceFromNode) traceFromNode = byId.get(String(traceFromNode.id)) || null;
  if (traceToNode) traceToNode = byId.get(String(traceToNode.id)) || null;
  renderTraceState();
}

function setTracePanelOpen(open) {
  traceModeActive = open;
  if (!open) clearTrace({ quiet: true });
  $("graph-trace").classList.toggle("hidden", !open);
  $("graph-trace-toggle")?.setAttribute("aria-expanded", String(open));
  $("graph-trace-toggle")?.classList.toggle("is-on", open);
  // A mode has to look like one. Without this the map behaves differently
  // from a moment ago with nothing on screen saying so, which is the
  // difference between a tool and a glitch: the cursor becomes a crosshair
  // over the nodes and the graph card picks up a tinted edge.
  $("graph-card")?.classList.toggle("is-tracing", open);
  prefs.set("graph-trace-open", open ? "1" : "0");
  if (open) {
    renderTraceState();
    // Re-opening the panel: most commonly by coming back to the Graph tab
    // after clicking a note in the trace path's own readout, which jumps to
    // the Notes tab (flashEntry) and left the panel "open" in localStorage: 
    // used to unconditionally overwrite #graph-trace-result with the opening
    // prompt, discarding a trace someone had already run (reported: "trace
    // resets when a note hyperlink in the trace path is clicked on"). Show
    // whatever's actually true instead of always restarting the script.
    if (!traceFromNode) {
      showTraceMessage("Click a note to start.");
    } else if (!traceToNode) {
      showTraceMessage("Click where to end.");
    } else if (graphTrace) {
      renderTraceReadout({ ...graphTrace, hops: graphTrace.steps.length });
    }
    // else: both ends picked but no result yet, a trace is mid-flight,
    // leave whatever runTrace() last wrote (e.g. "Tracing…") alone.
  }
}

// Escape leaves the mode. A mode you can only leave by finding the button
// that started it is a trap, and this one changes what clicking does.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || !traceModeActive) return;
  // Any *visible* overlay, not merely a present one, and `querySelectorAll`,
  // not `querySelector`. Nine `.modal-overlay` elements sit in the markup
  // permanently with `.hidden` on them, so asking for the first one matched a
  // hidden element every time and Escape appeared to do nothing; asking
  // whether *the first* is visible would then miss a dialog further down the
  // document. Escape belongs to whatever is on top of the trace panel.
  const overlays = [...document.querySelectorAll(".modal-overlay, .confirm-overlay")];
  if (overlays.some((el) => !el.classList.contains("hidden"))) return;
  setTracePanelOpen(false);
});

// --- Trace, redesigned (§41) ------------------------------------------------------
//
// Reported as "annoying and pretty much unusable", and it was, for one reason
// that made everything else about it worse: **the map did not respond.**
// `traceModeActive` was set and consulted nowhere, so picking the two ends
// meant using two `<select>` elements that listed every note in the notebook
// by its opening words. On any real notebook that is a scroll through hundreds
// of near-identical lines, to choose two notes that are visible on screen.
//
// It is a two-click mode now: turn Trace on, click a note, click another. The
// panel stops being a form and becomes a readout of where you are, which end
// you are choosing, what is chosen, and a way to swap or undo it. Escape
// leaves. The rules that make a mode bearable rather than a trap:
//
// - it always says what the next click will do (`renderTraceState`);
// - one click back: Undo removes the last end rather than resetting both;
// - Swap, because "actually, the other direction" is the commonest correction
//   and re-picking both to get it is the thing that made this infuriating;
// - clicking the same note twice is a no-op with a reason, not a silent
//   failure or a path from a note to itself.

function pickTraceEnd(node) {
  if (!node) return;
  if (traceFromNode && String(traceFromNode.id) === String(node.id)) {
    showTraceMessage("That's already the start, pick a different note to end at.");
    return;
  }
  if (!traceFromNode || traceToNode) {
    // Starting over: a third click begins a new trace rather than doing
    // nothing, which is what someone who has read the answer wants next.
    traceFromNode = node;
    traceToNode = null;
    graphTrace = null;
    drawTrace();
    applyGraphHighlight();
  } else {
    traceToNode = node;
  }
  renderTraceState();
  if (traceFromNode && traceToNode) runTrace();
}

function traceLabel(node) {
  const text = (node?.preview || "").trim();
  return text.length > 32 ? `${text.slice(0, 31)}…` : text || `note #${node?.id}`;
}

// The panel as a readout: what is chosen, what the next click does, and the
// two corrections worth having.
function renderTraceState() {
  const holder = $("graph-trace-ends");
  if (!holder) return;
  holder.replaceChildren();

  const chip = (node, role) => {
    const span = document.createElement("span");
    span.className = "trace-chip" + (node ? " is-set" : " is-empty");
    span.textContent = node ? traceLabel(node) : role;
    if (node) span.title = node.preview || "";
    return span;
  };

  //: The vendored set, not a typed arrow: this sits between two chips as a
  //: mark, which is where an icon belongs, and a typed one drew at the system
  //: face beside chips built from Phosphor.
  const arrow = document.createElement("i");
  arrow.className = "ph ph-arrow-right graph-trace-arrow";
  arrow.setAttribute("aria-hidden", "true");
  holder.append(chip(traceFromNode, "click a note to start"), arrow,
                chip(traceToNode, "then click where to end"));

  if (traceFromNode && traceToNode) {
    const swap = document.createElement("button");
    swap.type = "button";
    swap.className = "ghost small";
    setLabel(swap, "ph:arrows-left-right Swap");
    swap.title = "Trace the other way round";
    swap.addEventListener("click", () => {
      [traceFromNode, traceToNode] = [traceToNode, traceFromNode];
      renderTraceState();
      runTrace();
    });
    holder.appendChild(swap);
  }
  if (traceFromNode) {
    const back = document.createElement("button");
    back.type = "button";
    back.className = "ghost small";
    setLabel(back, "ph:arrow-counter-clockwise Undo");
    back.title = "Unpick the last note";
    back.addEventListener("click", () => {
      // One step back, not a reset. Mis-clicking the second note should not
      // cost you the first one.
      if (traceToNode) traceToNode = null;
      else traceFromNode = null;
      graphTrace = null;
      renderTraceState();
      drawTrace();
      applyGraphHighlight();
      showTraceMessage(traceFromNode ? "Click where to end." : "Click a note to start.");
    });
    holder.appendChild(back);
  }
}

// Kept for the note context menu, which offers "trace from here".
function setTraceEnd(which, noteId) {
  setTracePanelOpen(true);
  const node = (graphNodesRef || []).find((n) => String(n.id) === String(noteId));
  if (!node) {
    showTraceMessage("That note isn't on the map right now, clear filters and try again.");
    return;
  }
  if (which === "from") traceFromNode = node;
  else traceToNode = node;
  renderTraceState();
  if (traceFromNode && traceToNode) runTrace();
}

function showTraceMessage(text) {
  const box = $("graph-trace-result");
  if (!box) return;
  box.replaceChildren(document.createTextNode(text));
  box.classList.remove("hidden");
  box.classList.add("is-empty");
}

function clearTrace({ quiet = false } = {}) {
  graphTrace = null;
  graphTraceRoutes = [];
  graphTraceIndex = 0;
  traceFromNode = null;
  traceToNode = null;
  if (traceModeActive && !quiet) {
    // This looked up a "graph-trace-status" element, which does not exist, 
    // the readout is #graph-trace-result, and showTraceMessage is how you
    // write to it. The lookup was guarded by `if (status)`, so the prompt
    // simply never appeared and trace mode began with no instructions.
    showTraceMessage("Click a starting note");
  } else {
    const box = $("graph-trace-result");
    if (box) {
      box.replaceChildren();
      box.classList.add("hidden");
      box.classList.remove("is-empty");
    }
  }
  // Both branches still have to repaint: clearing the readout without
  // redrawing leaves the old highlighted path drawn on the map.
  drawTrace();
  applyGraphHighlight();
}

async function runTrace() {
  if (!traceFromNode || !traceToNode) {
    showTraceMessage("Pick two notes to trace between.");
    return;
  }
  // Trace used to read two <select> values into local `from`/`to`. It became
  // click-two-notes-on-the-map, the selects went away, and these three
  // references to `from`/`to` were left behind pointing at nothing, so the
  // moment you picked a second note, Trace threw a ReferenceError and did
  // nothing at all, with the failure visible only in the console.
  const from = traceFromNode.id;
  const to = traceToNode.id;
  if (from === to) {
    showTraceMessage("Those are the same note, pick two different ones.");
    return;
  }
  showTraceMessage("Tracing…");
  const result = await apiJson(
    `/graph/path?source=${encodeURIComponent(from)}&target=${encodeURIComponent(to)}`
  ).catch(() => null);
  if (!result) {
    showTraceMessage("Couldn't trace that: the server didn't answer.");
    return;
  }
  if (!result.found) {
    graphTrace = null;
    // The server's reason, verbatim. "No path" on its own is the kind of
    // answer that makes people assume the feature is broken; what they need is
    // which of the three possible causes it was.
    showTraceMessage(result.reason || "No path between those two notes.");
    drawTrace();
    applyGraphHighlight();
    return;
  }
  //: `routes` is always present and always has the best route first when the
  //: server says `found`, but an older server (or a cached response from one)
  //: would not send it, and a readout that renders nothing is worse than one
  //: with a single route in it. Fall back to the top-level shape, which every
  //: version has sent.
  graphTraceRoutes = Array.isArray(result.routes) && result.routes.length
    ? result.routes
    : [{ hops: result.hops, nodes: result.nodes, steps: result.steps }];
  graphTraceIndex = 0;
  selectTraceRoute(0, { redraw: false });
  drawTrace();
  applyGraphHighlight();
}

// The chain in words, under the strip. The map shows the shape; this says what
// each step *is*, which the map cannot, a line between two notes looks the
// same whether you drew it or they merely share a tag.
// Redesigned twice (ROADMAP.md item 5). The first redesign this session
// put one row per note plus one row per connector, stacked vertically, 
// reported back immediately as "crushes the graph, takes up most of the
// page", because it was never actually looked at running: a path of even
// four or five hops is eight-plus rows tall in a box that sits in normal
// document flow directly above the canvas, so it pushed the whole map
// down out of view. This version goes back to a single horizontal,
// wrapping strip: the note chips and the arrow-plus-reason connectors
// between them all flow and wrap together like a sentence, the same
// footprint the *original* pre-redesign version had, but with the notes
// as visually distinct chips and a real arrow glyph instead of an em-dash,
// and `.graph-trace-path`'s own `max-height` + scroll (below, in the CSS)
// as a hard floor under how tall this can ever get, so no path length can
// repeat this mistake even if the wrapping math is ever wrong again.
//: Switch which of the routes is being read. Everything downstream: 
//: `graphTrace`, the readout, the highlighted nodes, which overlay line is
//: solid: hangs off `graphTraceIndex`, so this is the one place that changes
//: and the four surfaces cannot disagree about which route is selected.
function selectTraceRoute(index, { redraw = true } = {}) {
  if (!graphTraceRoutes.length) return;
  graphTraceIndex = Math.max(0, Math.min(index, graphTraceRoutes.length - 1));
  const route = graphTraceRoutes[graphTraceIndex];
  graphTrace = {
    ids: route.nodes.map((n) => n.id),
    steps: route.steps,
    nodes: route.nodes,
  };
  renderTraceReadout({ ...route, hops: route.steps.length });
  if (redraw) {
    drawTrace();
    applyGraphHighlight();
  }
}

//: The shapes "Generate story from path" can make.
//:
//: It was one hard-coded prompt, "write a cohesive, publishable narrative" , 
//: which is one good answer to a question with several. Asked to "improve and
//: extend the generate story from path feature": the path is a chain of
//: *reasons*, and what you want built out of it depends entirely on why you
//: traced it. An explainer, a timeline and an argument are three different
//: documents from the same five notes, and picking between them is one click
//: rather than a re-prompt in the chat.
//:
//: `ask` is written to be joined onto the shared preamble in `storyPrompt`, so
//: the part that says "use the connections, follow the order" is stated once
//: and every shape inherits it. A shape that restated it would be a shape that
//: could drift from it.
const TRACE_STORY_SHAPES = [
  {
    id: "story",
    label: "A narrative",
    icon: "ph:book-open-text",
    hint: "publishable prose that ties the notes together",
    ask: "Write a cohesive, publishable narrative weaving these thoughts together.",
  },
  {
    id: "explain",
    label: "An explainer",
    icon: "ph:lightbulb",
    hint: "how these connect, in plain language",
    ask:
      "Explain in plain language how these notes connect, as a short essay a " +
      "colleague could follow without knowing the background.",
  },
  {
    id: "timeline",
    label: "A timeline",
    icon: "ph:clock-counter-clockwise",
    hint: "how the thinking developed, in order",
    ask:
      "Lay these out as a timeline of how the thinking developed: what came " +
      "first, what it led to, and what changed along the way.",
  },
  {
    id: "argument",
    label: "An argument",
    icon: "ph:scales",
    hint: "claim, evidence, caveats",
    ask:
      "Build the argument these notes add up to. State the claim, give the " +
      "evidence from the notes, then the caveats and what would change it.",
  },
  {
    id: "teach",
    label: "Teaching notes",
    icon: "ph:graduation-cap",
    hint: "what to learn first, then next, and why",
    ask:
      "Turn this into teaching notes: what someone should learn first, what " +
      "next, and why each step depends on the one before it.",
  },
  {
    id: "brief",
    label: "A short brief",
    icon: "ph:note",
    hint: "one paragraph, twenty seconds to read",
    ask:
      "Write one tight paragraph a busy colleague could read in twenty " +
      "seconds and come away knowing how these connect.",
  },
];

//: The preamble every shape shares. The connection reasons are the whole point
//:, a story built from the notes alone is a story about five unrelated things,
//: and the *reasons* are what the traced path actually discovered.
function storyPrompt(shape, route) {
  const reasons = route.steps.map((step) => step.how).join("; ");
  const alternatives =
    graphTraceRoutes.length > 1
      ? ` This is route ${graphTraceIndex + 1} of ${graphTraceRoutes.length} between the same two notes; write about this one.`
      : "";
  return (
    `${shape.ask} Follow the exact order the notes are attached in, and use ` +
    `the connection between each step (${reasons}) as part of what ties it ` +
    `together, not just the notes' own text.${alternatives}`
  );
}

function renderTraceReadout(result) {
  const box = $("graph-trace-result");
  if (!box) return;
  box.classList.remove("hidden", "is-empty");
  const noteButton = (node) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "graph-trace-note";
    renderInlineMarkdown(button, node.preview, [], true);
    button.title = `Open this note (${node.category})`;
    button.addEventListener("click", () => flashEntry(node.id));
    return button;
  };
  const byId = new Map(result.nodes.map((n) => [n.id, n]));

  const header = document.createElement("div");
  header.className = "graph-trace-header";
  const summary = document.createElement("span");
  summary.className = "graph-trace-step";
  summary.textContent = nounCount(result.hops, "step");
  header.appendChild(summary);

  const path = document.createElement("div");
  path.className = "graph-trace-path";
  path.appendChild(noteButton(result.nodes[0]));
  for (const step of result.steps) {
    const connector = document.createElement("span");
    connector.className = "graph-trace-connector";
    //: GRAPH_PLAN KG8: every other reason the pair relates rides on the hop,
    //: counted on its label and spelt out on hover.
    const also = (step.also || []).map((g) => g.reason);
    connector.title = also.length ? `${step.how}\nAlso: ${also.join("; ")}` : step.how;
    //: The class already said icon; it is one now. A typed arrow drew at the
    //: system face inside a connector built from Phosphor everywhere else.
    const arrow = document.createElement("i");
    arrow.className = "ph ph-arrow-right graph-trace-arrow-icon";
    arrow.setAttribute("aria-hidden", "true");
    const how = document.createElement("span");
    how.className = "graph-trace-connector-label";
    how.textContent = also.length ? `${step.how} +${also.length}` : step.how;
    connector.append(arrow, how);
    path.append(connector, noteButton(byId.get(step.target)));
  }

  const pieces = [header, path];

  //: **The route switcher.** Only drawn when there is more than one route, so
  //: the common case, the two notes connect one way, is exactly the row it
  //: has always been rather than a row with a lonely "1 of 1" on it.
  //:
  //: Each chip carries the same `data-route` index the overlay lines do, which
  //: is what ties a chip to a coloured line on the map: chip 2 and the line
  //: drawn in colour 2 are the same route, and you can see that without
  //: clicking anything.
  if (graphTraceRoutes.length > 1) {
    const switcher = document.createElement("div");
    switcher.className = "graph-trace-routes";
    switcher.setAttribute("role", "tablist");
    switcher.setAttribute("aria-label", "Routes between these two notes");
    graphTraceRoutes.forEach((route, index) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "graph-trace-route-chip";
      chip.dataset.route = String(index);
      chip.setAttribute("role", "tab");
      const active = index === graphTraceIndex;
      chip.classList.toggle("is-active", active);
      chip.setAttribute("aria-selected", String(active));
      const swatch = document.createElement("span");
      swatch.className = "graph-trace-route-swatch";
      swatch.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      const hops = route.steps.length;
      label.textContent = `Route ${index + 1} · ${nounCount(hops, "step")}`;
      chip.append(swatch, label);
      chip.title =
        index === 0
          ? "The shortest route: the one the map draws solid by default"
          : "Another way these two notes connect";
      chip.addEventListener("click", () => selectTraceRoute(index));
      switcher.appendChild(chip);
    });
    pieces.splice(1, 0, switcher);
  }

  // Story Mode: Synthesize the path into a narrative.
  //
  // Was three inline `.style.x =` assignments against `var(--primary)` /
  // `var(--primary-fg)`, tokens that don't exist in this design system (it's
  // `--accent`/`--on-accent`), and the CSP's `style-src: 'self'` (no
  // `unsafe-inline`) refuses an inline style attribute outright regardless,
  // which is what `.style.x =` sets under the hood. Both silently no-op, so
  // the button rendered as a bare `.graph-trace-note` with none of its
  // intended emphasis. A real class with real tokens, per DESIGN.md.
  //
  //: **And it is a menu now, not one button.** It sent a single hard-coded
  //: "write a publishable narrative" prompt, which is one good answer to a
  //: question that has several: the same five notes and the same chain of
  //: reasons make a different document depending on why you traced them.
  //: `TRACE_STORY_SHAPES` holds the six, `storyPrompt` states the shared part
  //: once, and the summary still runs the default (a narrative) on a plain
  //: click so the one-press path nobody has to learn is unchanged.
  const story = document.createElement("details");
  story.className = "doc-dock-menu doc-toolbar-menu graph-trace-story";
  //: `.doc-toolbar-menu` deliberately: it is what `clampToolbarMenu` keys on,
  //: so this menu gets the app's viewport-fixed placement, its flip-when-there-
  //: is-no-room and its re-place-on-scroll for free rather than growing a
  //: fourth opinion about where a dropdown goes.
  const storyOpener = document.createElement("summary");
  storyOpener.className = "graph-trace-note story-mode-btn";
  setLabel(storyOpener, "ph:sparkle Generate from path");
  storyOpener.title = "Build something out of this path, using Atlas locally";
  const caret = document.createElement("i");
  caret.className = "ph ph-caret-down doc-toolbar-menu-caret";
  caret.setAttribute("aria-hidden", "true");
  storyOpener.appendChild(caret);
  const list = document.createElement("div");
  list.className = "doc-dock-menu-list";
  for (const shape of TRACE_STORY_SHAPES) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "doc-dock-menu-item";
    setLabel(item, `${shape.icon} ${shape.label}`);
    item.title = shape.hint;
    item.addEventListener("click", () => {
      story.open = false;
      const route = graphTraceRoutes[graphTraceIndex] || result;
      switchTab("chat");
      sendChatMessage(storyPrompt(shape, route), {
        noteIds: graphTrace.ids,
        attachedNotesOnly: true,
      });
    });
    list.appendChild(item);
  }
  story.append(storyOpener, list);
  header.appendChild(story);

  box.replaceChildren(...pieces);
}

// Arc layout puts every node on one shared baseline (`layoutHierarchy`'s
// `arc` branch: see `arcPath`), which is why *its* edges are curves in the
// first place: a straight line between two nodes on that baseline is just
// the baseline itself. The trace overlay drew a straight chord regardless of
// layout, so in Arc specifically the "highlighted path" sat exactly where
// the row of ordinary nodes already was, reported as connections being
// hard to see on non-tree layouts, and this is the layout where the overlay
// was not just hard to see but nearly the same line as no overlay at all.
//
// Taller than `arcPath`'s own curve (0.9 vs 0.6) so the highlighted route
// arches visibly clear of the row instead of tracking the same shape as the
// muted, thin edges underneath it, and unlike `arcPath`, which can assume
// `a.x < b.x` because a pre-order walk always visits a parent before its
// children, a traced path can run either direction through the hierarchy.
function tracePath(a, b) {
  if (Math.abs(b.x - a.x) < 0.5 && b.y !== a.y) {
    const half = Math.max(Math.abs(b.y - a.y) / 2, 1);
    return `M${a.x},${a.y}A${half * 0.9},${half} 0 0,${a.y <= b.y ? 0 : 1} ${b.x},${b.y}`;
  }
  const rx = Math.max(Math.abs(b.x - a.x) / 2, 1);
  const ry = rx * 0.9;
  const sweep = a.x <= b.x ? 1 : 0;
  return `M${a.x},${a.y}A${rx},${ry} 0 0,${sweep} ${b.x},${b.y}`;
}

// (Re)draw the overlay for the current trace. Segments whose notes are not on
// the map are dropped rather than drawn to nowhere, the readout above still
// names them.
function drawTrace() {
  // The overlay is painted from `graphTrace` / `graphTraceRoutes` inside the
  // frame (see `gcDrawTrace`), so redrawing it is a redraw request. Everything
  // above this line, running the search, filling the readout, the route chips,
  // is unchanged.
  gcRequestDraw();
}

// --- drag one note onto another to link them (§9) ----------------------------
//
// The map already had a link gesture, Link in the popup, then click the other
// note: which works and is two dialogs deep. Dropping one note on another is
// the gesture people try first, and it costs nothing to support: the drag
// behaviour is already there to move nodes about.
//
// The whole risk here is an *accidental* link, since every drag now ends over
// something or nothing. Three things answer that, and all three are needed:
// the target lights up while you are over it, the drop has to land on the
// note's own circle rather than near it, and the link that results is
// undoable from the toast.

//: How much of a miss still counts as a hit. Zero would demand pixel accuracy
//: on a moving target; the node's own radius plus this is the circle you are
//: actually aiming at.
//:
//: Raised from 6 after driving the gesture in a browser. A note is a 9px
//: circle, so six pixels of slop meant hitting a 15px target that is *drifting*
//:, dragging reheats the simulation, so everything else keeps moving while
//: you aim. Fourteen makes it a comfortable 23px and is still far short of the
//: nearest neighbour, so a drop in open space still links nothing.
const DROP_SLOP = 14;



function graphNodeUnder(dragged, event) {
  for (const other of graphNodesRef || []) {
    if (other === dragged || other.isGroup) continue;
    const dx = (other.x ?? 0) - event.x;
    const dy = (other.y ?? 0) - event.y;
    // Squared, not `Math.hypot`. This runs over every node on every pointer
    // event of a drag, so the square root is one transcendental call per note
    // per event for a comparison that does not need it.
    const reach = graphNodeRadius(other) + DROP_SLOP;
    if (dx * dx + dy * dy <= reach * reach) return other;
  }
  return null;
}

//: The kinds of connection a link can carry.
//:
//: **Mirrors `LINK_TYPES` in src/tessellate/core/database.py, and
//: `tests/test_link_types.py` fails the build if the two drift.** Duplicated
//: rather than fetched because this list is needed to draw a dialog before any
//: request has been made, and a picker that has to wait on the network to know
//: what it can offer is a picker that opens empty.
const GRAPH_LINK_TYPES = [
  ["related", "Related", "These belong together"],
  ["continues", "Continues", "This carries on from that"],
  ["context", "Extra context", "This explains or supports that"],
  ["supports", "Supports", "This is evidence for that"],
  ["contradicts", "Contradicts", "These disagree"],
  ["example_of", "Example of", "This is an instance of that"],
];

// Ask what kind of link this is before making it. Resolves to
// `{link_type, reason}`, or null when the user cancels.
//
// Asked for directly: dropping one note on another used to make a flat,
// unexplained link with no way back except an Undo toast you had to catch in
// time. Now the drop opens this, nothing is written until "Create link", and
// Cancel leaves the notebook untouched, which is the "ability to cancel the
// linkage" half of the request, and the reason this is a dialog rather than a
// toast offering to edit afterwards.
function askLinkDetails(from, to) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay confirm-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");

    const card = document.createElement("div");
    card.className = "card modal-card link-kind-card";

    //: The dialog head (INBOX 548): it was a bare `h3`, the 12px eyebrow.
    card.appendChild(dialogHead("How are these connected?", () => close(null)));

    const pair = document.createElement("p");
    pair.className = "muted link-kind-pair";
    pair.textContent = `“${from.preview}” → “${to.preview}”`;
    card.appendChild(pair);

    // Direction matters for half the vocabulary, "continues" and "example of"
    // read backwards if the arrow is the other way round, so it is stated
    // above rather than left to be inferred from which node was dragged.
    const list = document.createElement("div");
    list.className = "link-kind-list";
    let chosen = "related";
    const buttons = [];
    for (const [value, label, hint] of GRAPH_LINK_TYPES) {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "link-kind-option" + (value === chosen ? " active" : "");
      option.setAttribute("aria-pressed", String(value === chosen));
      const name = document.createElement("span");
      name.className = "link-kind-name";
      name.textContent = label;
      const why = document.createElement("span");
      why.className = "link-kind-hint";
      why.textContent = hint;
      option.append(name, why);
      option.addEventListener("click", () => {
        chosen = value;
        for (const other of buttons) {
          const on = other.dataset.value === value;
          other.classList.toggle("active", on);
          other.setAttribute("aria-pressed", String(on));
        }
      });
      option.dataset.value = value;
      buttons.push(option);
      list.appendChild(option);
    }
    card.appendChild(list);

    const reasonLabel = document.createElement("label");
    reasonLabel.className = "field";
    const reasonText = document.createElement("span");
    reasonText.textContent = "Why? (optional)";
    const reasonBox = document.createElement("input");
    reasonBox.type = "text";
    reasonBox.maxLength = 200;
    reasonBox.placeholder = "Left blank, Atlas will try to work it out";
    reasonLabel.append(reasonText, reasonBox);
    card.appendChild(reasonLabel);

    const row = document.createElement("div");
    row.className = "row confirm-actions";

    let settled = false;
    const close = (answer) => {
      if (settled) return;
      settled = true;
      document.removeEventListener("keydown", onKey, true);
      overlay.remove();
      returnFocus?.focus?.();
      resolve(answer);
    };
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        close(null);
      } else if (event.key === "Enter" && event.target.tagName === "INPUT") {
        event.stopPropagation();
        close({ link_type: chosen, reason: reasonBox.value.trim() || null });
      }
    };

    const returnFocus = document.activeElement;
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "ghost small";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", () => close(null));
    const create = document.createElement("button");
    create.type = "button";
    create.className = "small accent";
    create.textContent = "Create link";
    create.addEventListener("click", () =>
      close({ link_type: chosen, reason: reasonBox.value.trim() || null })
    );
    row.append(cancel, create);
    card.appendChild(row);
    overlay.appendChild(card);
    wireBackdropClose(overlay, () => close(null));
    document.addEventListener("keydown", onKey, true);
    document.body.appendChild(overlay);
    // Cancel takes focus, not Create: a stray Enter arriving with the dialog
    // must not be the thing that writes a link into the notebook.
    cancel.focus();
  });
}

async function linkByDrop(from, to) {
  // Already connected: say so rather than firing a request that will 400. The
  // adjacency map is what the map itself is drawn from, so this agrees with
  // what the user can see.
  if (graphAdjacency?.get(from.id)?.has(to.id)) {
    toast("Those two are already connected.");
    return;
  }
  const details = await askLinkDetails(from, to);
  if (!details) return; // cancelled: nothing is written

  const updated = await apiJson(`/entries/${from.id}/links`, {
    method: "POST",
    body: JSON.stringify({
      target_id: to.id,
      reason: details.reason,
      link_type: details.link_type,
    }),
  }).catch((error) => {
    toast(error.message, true);
    return null;
  });
  if (!updated) return;
  await loadEntries().catch(() => {});
  renderGraph();
  // The new link's own id, so Undo removes *this* link rather than whatever
  // link happens to join them, they may have been linked twice by different
  // routes, and guessing is how an undo deletes the wrong thing.
  const action = await pushLinkCreateUndo(
    from.id,
    to.id,
    updated,
    { target_id: to.id, reason: details.reason, link_type: details.link_type },
    "Linked two notes",
    renderGraph
  );
  toastAction(
    `Linked "${from.preview}" to "${to.preview}".`,
    "Undo",
    async () => {
      settleUndoFromToast(action);
      await action.undo();
      toast("Link removed.");
    }
  );
}

// --- colouring by cluster (§9) -----------------------------------------------
//
// A layout says where a note goes; this says what its colour *means*. By
// category is the filing, which is what somebody decided to call it. By
// cluster is the structure: which notes can actually reach each other through
// links, replies and shared tags. The two are often nothing like each other,
// and that difference is the most useful thing the map can show.

//: The last structure fetched, so the legend and the stats line agree with the
//: colours without three round trips.
let graphStructure = null;

//: GRAPH_PLAN Phase 3. The rule the colours follow; anything the select
//: does not offer collapses to category, so a stale saved view cannot ask
//: for a rule that no longer exists.
//: "type" is the note's type (D5, KG4's `type:` property), in the type's own
//: colour where Note types gives it one.
const GRAPH_COLOUR_RULES = ["category", "cluster", "topic", "kind", "type", "age", "space", "tag", "file"];

//: INBOX 430, View > Size: what a node's size says. Connections (the default)
//: is `4 + 2*sqrt(degree)`, GRAPH_PLAN §5 Phase 1; length is the note's words,
//: on a log scale so a 3,000-word note is not a moon beside a 30-word one;
//: recency halves every 30 days since it was last edited; none is one size.
//: Every rule stays in the same [4, 18] band, so the labels, the hit test and
//: the fit's padding need no second case.
const GRAPH_SIZE_RULES = ["connections", "length", "recency", "none"];

function graphSizeMode() {
  const value = document.getElementById("graph-size")?.value;
  return GRAPH_SIZE_RULES.includes(value) ? value : "connections";
}

function graphSizeRadius(node, degree, low = 4, high = 18, maxDegree = 0) {
  const mode = graphSizeMode();
  if (mode === "none") return 7;
  if (mode === "length") {
    const words = Math.max(0, Number(node.words) || 0);
    return low + (high - low) * Math.min(1, Math.log1p(words) / Math.log1p(2000));
  }
  if (mode === "recency") {
    const at = Date.parse(node.updated_at || node.created_at || "");
    const days = Number.isFinite(at) ? Math.max(0, (Date.now() - at) / 86400000) : Infinity;
    return low + (high - low) * Math.pow(0.5, days / 30);
  }
  //: 3.5 per root of a link, not 2: in a notebook of tens of notes the
  //: busiest hub has 5 or 6 links, and at 2 it drew barely 2px wider than a
  //: leaf (reported at release). 1 link 7.5, 4 links 11, 9 links 14.5.
  //: **Relative to this graph's busiest note** (the owner at release: "how
  //: come my graph doesn't look like that, there's not much size
  //: difference"): the README's notebook has hubs of ten links, a real one
  //: tops out at four, and on the fixed scale above 1 to 4 links is 7.5 to
  //: 11px. The busiest note now takes the full size and the rest their share
  //: of it (by root, as before), so the spread is the graph's own. Only from
  //: a busiest note of 3 links: below that every linked dot would draw huge.
  //: The curve is steep (share to the 1.5), not a root: with a root, half
  //: the busiest note's links drew at 70% of its size and the middle of a
  //: small notebook was all large dots ("clean and impressive" was the ask).
  //: A leaf stays about the fixed scale's size; only real hubs grow.
  const absolute = Math.max(low, Math.min(high, low + 3.5 * Math.sqrt(degree || 0)));
  if (!degree || maxDegree < 3) return absolute;
  const leaf = low + 2.5;
  return leaf + (high - leaf) * Math.pow(Math.min(1, degree / maxDegree), 1.5);
}

function graphColourMode() {
  const value = document.getElementById("graph-colour")?.value;
  return GRAPH_COLOUR_RULES.includes(value) ? value : "category";
}

//: Legend toggles for the non-category rules, keyed "rule:value". Category
//: keeps its own set (graphHiddenCategories) because saved views already
//: store it under that name.
let graphHiddenKeys = new Set();

// --- Groups: a saved search painted one colour (GRAPH_PLAN Phase 3) -------------
const GRAPH_GROUPS_KEY = "graph-groups";
const GRAPH_GROUP_COLOURS = ["#e4572e", "#17bebb", "#ffc914", "#76b041", "#a06cd5", "#f07ca2", "#2f80ed", "#8d6e63"];
//: id -> group index, rebuilt on every render from the live search results.
let graphGroupOf = new Map();

function graphGroups() {
  try {
    const parsed = prefs.json(GRAPH_GROUPS_KEY, []);
    return Array.isArray(parsed) ? parsed.filter((g) => g && typeof g.query === "string" && g.query.trim()) : [];
  } catch {
    return [];
  }
}

function graphSetGroups(groups) {
  prefs.set(GRAPH_GROUPS_KEY, JSON.stringify(groups));
  graphRenderGroups();
  renderGraph();
}

function graphGroupColour(index) {
  return GRAPH_GROUP_COLOURS[index % GRAPH_GROUP_COLOURS.length];
}

//: Which notes each group paints, from the same search the Notes tab runs.
//: Resolved per render so a group is a rule, not a snapshot. A failed search
//: paints nothing rather than everything.
async function graphResolveGroups() {
  const groups = graphGroups();
  const map = new Map();
  await Promise.all(
    groups.map(async (group, index) => {
      const reply = await apiJson(`/graph/match?q=${encodeURIComponent(group.query)}`).catch(() => null);
      for (const id of reply?.ids || []) {
        if (typeof id === "number" && !map.has(id)) map.set(id, index);
      }
    })
  );
  graphGroupOf = map;
  return groups;
}

function graphRenderGroups() {
  const list = document.getElementById("graph-groups");
  if (!list) return;
  list.replaceChildren();
  const groups = graphGroups();
  if (!groups.length) {
    const empty = document.createElement("p");
    empty.className = "muted graph-groups-empty";
    empty.textContent = "No groups yet. Add a search and its notes take one colour.";
    list.appendChild(empty);
    return;
  }
  groups.forEach((group, index) => {
    const row = document.createElement("div");
    row.className = "graph-group-row";
    row.setAttribute("role", "listitem");
    const dot = document.createElement("span");
    dot.className = "legend-dot";
    dot.style.background = graphGroupColour(index);
    const name = document.createElement("span");
    name.className = "graph-group-name";
    name.textContent = group.query;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost small icon-only";
    remove.title = `Remove the group “${group.query}”`;
    remove.setAttribute("aria-label", remove.title);
    setLabel(remove, "ph:x");
    remove.addEventListener("click", () => graphSetGroups(groups.filter((_, i) => i !== index)));
    row.append(dot, name, remove);
    list.appendChild(row);
  });
}

function initGraphGroups() {
  const add = document.getElementById("graph-group-add");
  const input = document.getElementById("graph-group-query");
  if (!add || !input || add._wired) return;
  add._wired = true;
  const submit = () => {
    const query = input.value.trim();
    if (!query) return;
    const groups = graphGroups();
    if (groups.some((g) => g.query.toLowerCase() === query.toLowerCase())) {
      toast("That group already exists.");
      return;
    }
    if (groups.length >= GRAPH_GROUP_COLOURS.length) {
      toast(`Up to ${GRAPH_GROUP_COLOURS.length} groups, so each keeps its own colour.`);
      return;
    }
    input.value = "";
    graphSetGroups([...groups, { query }]);
  };
  add.addEventListener("click", submit);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  });
  graphRenderGroups();
}

let graphFocusModeId = null;

//: **A way back from "around one note"** (the owner at release: "I opened it
//: in the graph and now I cant reset the graph. this is a massive usability
//: and learnability issue"). The local map's expand button, and a node's
//: "Focus" action, narrow the graph to the notes within two links of one
//: note, and nothing on screen said so or undid it. This chip beside the
//: dock's count says what the graph is showing and "Show all" restores it.
function graphSyncFocusChip() {
  document.getElementById("graph-focus-section")?.classList.toggle("hidden", !graphFocusModeId);
  const stats = document.getElementById("graph-stats");
  if (!stats) return;
  let chip = document.getElementById("graph-focus-chip");
  if (!graphFocusModeId) {
    chip?.remove();
    return;
  }
  if (!chip) {
    chip = document.createElement("button");
    chip.type = "button";
    chip.id = "graph-focus-chip";
    chip.className = "ghost small graph-focus-chip";
    chip.title = "The graph is showing only the notes near one note (Focus, in the gear, sets how far). Show every note again.";
    const icon = document.createElement("i");
    icon.className = "ph ph-x ph-lead";
    icon.setAttribute("aria-hidden", "true");
    chip.append("Around one note", icon, " Show all");
    chip.addEventListener("click", () => {
      graphFocusModeId = null;
      graphSyncFocusChip();
      renderGraph();
    });
    stats.after(chip);
  }
}

//: **The map's category colours.** Its own ordinal scale supplies the
//: automatic colour (a category's place in the sorted list, so the same
//: notebook always draws the same), and `categoryColour` (notes-list.js) puts the one
//: the person chose over it, so the legend, the nodes, the minimap and the
//: local map all agree with the dots in Notes. A colour chosen while the map
//: is on screen redraws it.
//:
//: **A calmer palette** (INBOX 493, the owner: "is there a way to make my
//: graphed notes look nicer??"). The automatic colours are Tableau's ten then
//: Set3, each taken to 78% of its saturation at the same hue and lightness,
//: so five clusters read as five families rather than five signals while
//: every dot keeps its contrast with the ground (lightness is untouched). A
//: colour the person chose is drawn as chosen, which is what keeps it the
//: same as its dot in Notes.
let graphCalmSchemeCache = null;
function graphCalmScheme() {
  if (!graphCalmSchemeCache) {
    graphCalmSchemeCache = d3.schemeTableau10.concat(d3.schemeSet3).map((hex) => {
      const c = d3.hsl(hex);
      c.s *= 0.78;
      return c.formatHex();
    });
  }
  return graphCalmSchemeCache;
}
function graphCategoryScale(categories) {
  const scale = d3.scaleOrdinal(categories, graphCalmScheme());
  return (name) => categoryColour(name, scale(name));
}
document.addEventListener("categorycolours", () => {
  if (document.getElementById("graph-canvas")?.checkVisibility?.()) renderGraph();
});

async function renderGraph() {
  closeGraphLinkPeek();
  const canvas = document.getElementById("graph-canvas");
  if (!canvas) return;
  canvas.classList.remove("hidden");
  //: The first draw of a visit fades in once the layout has taken its first
  //: frames, instead of showing the nodes mid-shuffle (owner, 2026-10-12:
  //: "so it isnt so in your face"). A later redraw (a switch, a filter)
  //: keeps what is on screen.
  const first = !canvas.dataset.revealed;
  if (first) canvas.classList.add("graph-entering");
  try {
    return await renderGraphCanvas();
  } finally {
    if (first) {
      canvas.dataset.revealed = "1";
      setTimeout(() => canvas.classList.remove("graph-entering"), 60);
    }
  }
}

//: The local graph's query (GRAPH_PLAN 514 (1)): depth and the three
//: switches, stored per surface ("focus" in the gear, "pane" beside a note).
function graphLocalQuery(prefix, depth) {
  const on = (id) => prefs.get(`graph-${prefix}-${id}`, null) !== "0";
  const stored = Number(prefs.get(`graph-${prefix}-depth`, null));
  const hops = stored >= 1 && stored <= 5 ? stored : depth;
  return `depth=${hops}&incoming=${on("in")}&outgoing=${on("out")}&neighbours=${on("neighbours")}`;
}

//: What the map asks for, from the Show switches; focus mode asks for one
//: note's neighbourhood instead.
function graphEndpoint() {
  const on = (id) => Boolean(document.getElementById(id)?.checked);
  if (graphFocusModeId) {
    return `/graph/local/${graphFocusModeId}?${graphLocalQuery("focus", 2)}&similarity=${on("graph-similarity")}`;
  }
  const flags = [
    ["graph-similarity", "similarity"],
    ["graph-entities", "include_entities"],
    ["graph-documents", "include_documents"],
    ["graph-maps", "include_maps"],
    ["graph-tags", "include_tags"],
    ["graph-unresolved", "include_unresolved"],
    ["graph-attachments", "include_attachments"],
  ];
  //: `slim=1`: the payload without the defaults (`graphFill`, below).
  return `/graph?${["slim=1", ...flags.filter(([id]) => on(id)).map(([, flag]) => `${flag}=true`)].join("&")}`;
}

//: **The slim payload, filled back** (GRAPH_PLAN, a slimmer node). The map
//: asks `/graph` with `slim=1`, and a note node comes without each key at its
//: default (routes_graph.py, `_NOTE_DEFAULTS`) and a link without its three
//: nulls: 3,145 KB at 5,000 notes before. Put back here, on arrival, so
//: every reader after the fetch (the colour rules, the panel, the local
//: pane's hand-over, the saved views) sees the shape it always read. A
//: node that carries its keys (`/graph/local`, an entity, a tag) is left as
//: it came.
function graphFill(data) {
  for (const n of data?.nodes || []) {
    if (n.kind && n.kind !== "note") continue;
    n.kind ??= "note";
    n.note_type ??= null;
    n.graph_pin_x ??= null;
    n.graph_pin_y ??= null;
    n.parent_id ??= null;
    n.has_file ??= false;
    n.pinned ??= false;
    n.map_ids ??= [];
    n.tags ??= [];
    n.access_count ??= 0;
    n.edited_at ??= null;
  }
  for (const e of data?.edges || []) {
    if (e.kind !== "link") continue;
    e.reason ??= null;
    e.reason_confidence ??= null;
    e.link_type ??= null;
  }
  return data;
}

// --- driving the graph from the keyboard ------------------------------------------
// The graph was the one tab that failed a keyboard-first test outright: every
// way of reaching a note was a mouse gesture, so the whole map, and the notes
// only reachable through it, was unusable without a pointer.
//
// A tab stop per node is not the answer; a big map would be hundreds of stops
// to get past. The map takes one stop, and inside it the arrow keys move to
// the nearest note in that direction, which is the way you already think about
// a map. Tab out again in one press.

let graphKeyboardId = null; // the note the keyboard is "on", or null

function graphNodeById(id) {
  return (graphNodesRef || []).find((n) => n.id === id) || null;
}

// The nearest node roughly in `direction` from the current one. Scored by
// distance, penalised by how far off the axis it sits, so "right" prefers a
// node to the right over a nearer one that happens to be below.
function graphNeighbourInDirection(from, direction) {
  const vectors = { right: [1, 0], left: [-1, 0], up: [0, -1], down: [0, 1] };
  const [dirX, dirY] = vectors[direction] || vectors.right;
  let best = null;
  let bestScore = Infinity;
  for (const node of graphNodesRef || []) {
    if (node === from) continue;
    const dx = node.x - from.x;
    const dy = node.y - from.y;
    const along = dx * dirX + dy * dirY;
    if (along <= 0) continue; // behind us
    const across = Math.abs(dx * dirY - dy * dirX);
    const score = along + across * 2.5;
    if (score < bestScore) {
      bestScore = score;
      best = node;
    }
  }
  return best;
}

function focusGraphNode(node, { announceIt = true } = {}) {
  if (!node) return;
  graphKeyboardId = node.id;
  // Reuse the hover spotlight: keyboard focus and pointer hover mean the same
  // thing here, and two highlight systems would fight each other.
  graphHoveredId = node.id;
  applyGraphHighlight();
  // The canvas renderer rings `graphKeyboardId` in the same pass as the hover
  // ring, so moving the keyboard focus is one more frame.
  gcRequestDraw();
  if (announceIt) {
    const links = graphAdjacency?.get(node.id)?.size || 0;
    announce(
      `${node.preview}. ${node.category}. ` +
        `${nounCount(links, "connection")}. Press Enter to open.`
    );
  }
}

// The popup positions itself from a click's coordinates, so a keyboard open
// has to supply the equivalent point: where the node actually is on screen.
function graphNodeScreenPoint(node) {
  const box = document.getElementById("graph-box");
  const rect = box ? box.getBoundingClientRect() : { left: 0, top: 0, width: 0, height: 0 };
  // Read from the zoom behaviour rather than by parsing a `transform`
  // attribute off a `<g>`. The old version did the latter, which only ever
  // worked on the SVG renderer and quietly mis-parsed a transform d3 had
  // written as a matrix; `d3.zoomTransform` is the same number on either
  // renderer because both attach the same `d3.zoom` to their own element.
  const transform = graphSvg && graphSvg.node() ? d3.zoomTransform(graphSvg.node()) : null;
  const scale = transform ? transform.k : 1;
  const tx = transform ? transform.x : 0;
  const ty = transform ? transform.y : 0;
  return {
    clientX: rect.left + tx + node.x * scale,
    clientY: rect.top + ty + node.y * scale,
  };
}

function initGraphKeyboard() {
  const box = document.getElementById("graph-box");
  if (!box || box.dataset.keyboardReady) return;
  box.dataset.keyboardReady = "1";
  box.tabIndex = 0;
  box.setAttribute("role", "application");
  box.setAttribute(
    "aria-label",
    "Map of your notes. Arrow keys move between notes, Shift with an arrow " +
      "pans the view, plus and minus zoom, 0 fits the whole map, Enter opens " +
      "a note, Escape leaves the map."
  );

  box.addEventListener("focus", () => {
    if (!graphNodesRef?.length) return;
    // **A pan is not a request to select a note.** Reported: "sometimes when
    // I scroll and pan on the graph, a random single separated and unlinked
    // note will highlight itself and show its label". This box is
    // `tabIndex = 0`, so a press anywhere on the map focuses it, and this
    // listener then handed the keyboard to `graphNodesRef[0]`, an arbitrary
    // note, while `focusGraphNode` (below) deliberately sets the *hover* id
    // too: the canvas dims every non-neighbour to 20% and draws that one
    // note's label. Measured after a single pan drag on empty map:
    // activeElement=graph-box, hovered=1, graphKeyboardId=1, and node 1 is
    // simply the first in the payload.
    //
    // `:focus-visible` is the browser's own answer to "did this focus come
    // from the keyboard", which is exactly the question: a Tab into the map
    // should land on a note, a mouse press should not. It is checked here
    // rather than by tracking pointerdown ourselves because the browser
    // already knows about every route in (Tab, shift-Tab, a script focus
    // after a keyboard action, assistive tech) and a hand-rolled flag would
    // have to learn them one bug at a time.
    if (!box.matches(":focus-visible")) return;
    const current = graphNodeById(graphKeyboardId) || graphNodesRef[0];
    focusGraphNode(current);
  });
  box.addEventListener("blur", () => {
    graphHoveredId = null;
    applyGraphHighlight();
  });

  box.addEventListener("keydown", (event) => {
    // The map's own shortcuts (arrows to move between notes, Enter/Space to
    // open one, N to step through links, +/-/0 to zoom) live on this box
    // because it's the thing with `role="application"`, but the note popup
    // and the "Grow the map" form are both DOM descendants of it too, so
    // every keystroke typed into their textareas/inputs bubbles up here as
    // well. Reported: typing in a just-grown note wouldn't take input and
    // kept reopening the note it was grown from, that was Space/Enter, on
    // every keystroke, being read as "open the currently keyboard-selected
    // node" instead of being typed. Any real text field wins outright.
    const typingTarget =
      ["INPUT", "TEXTAREA", "SELECT"].includes(event.target?.tagName) ||
      event.target?.isContentEditable;
    if (typingTarget) return;
    if (!graphNodesRef?.length) return;
    const current = graphNodeById(graphKeyboardId) || graphNodesRef[0];

    // Zoom and pan from the keyboard. Deliberately checked *before* the arrow
    // keys below, because Shift+arrow pans the view while a bare arrow moves
    // between notes: two different jobs on the same keys, which is the only
    // arrangement that leaves the plain arrows doing the thing this map is
    // mostly for. The characters are the ones every map on the web uses:
    // +/- to zoom, 0 to fit. `=` is listed with `+` because on a US layout
    // the plus is a shifted equals and nobody reaches for the shift.
    const zoomKeys = { "+": 1.3, "=": 1.3, "-": 1 / 1.3, _: 1 / 1.3 };
    if (Object.prototype.hasOwnProperty.call(zoomKeys, event.key) && graphSvg && graphZoom) {
      event.preventDefault();
      graphSvg.transition().duration(graphGlideMs(200)).call(graphZoom.scaleBy, zoomKeys[event.key]);
      announce(zoomKeys[event.key] > 1 ? "Zoomed in." : "Zoomed out.");
      return;
    }
    if (event.key === "0" && graphNodesRef.length) {
      event.preventDefault();
      fitGraphToView(graphSvg, graphZoom, graphNodesRef, graphDims.w, graphDims.h);
      announce("Fitted the whole map to view.");
      return;
    }
    const panBy = { ArrowRight: [-80, 0], ArrowLeft: [80, 0], ArrowUp: [0, 80], ArrowDown: [0, -80] };
    if (event.shiftKey && panBy[event.key] && graphSvg && graphZoom) {
      event.preventDefault();
      const [dx, dy] = panBy[event.key];
      // translateBy works in the transform's own (pre-scale) units, so a
      // fixed step would move a hair at high zoom and half the map at low.
      // Dividing by k keeps the movement a constant number of screen pixels.
      const k = d3.zoomTransform(graphSvg.node()).k || 1;
      graphSvg.transition().duration(graphGlideMs(150)).call(graphZoom.translateBy, dx / k, dy / k);
      return;
    }

    const directions = {
      ArrowRight: "right",
      ArrowLeft: "left",
      ArrowUp: "up",
      ArrowDown: "down",
    };
    // Alt+arrow is the app-wide Back/Forward shortcut (app.js's own
    // DEFAULT_SHORTCUTS): without this check, this box's own bare-arrow
    // "move to the neighbour note" handler ran first (it's the keydown
    // target while the map has focus) and consumed the keystroke with its
    // own preventDefault() before the global handler had anything clean
    // left to act on, so Alt+Left silently moved the graph selection
    // instead of navigating back. Bare arrows still work exactly as before.
    if (directions[event.key] && !event.altKey) {
      event.preventDefault();
      const next = graphNeighbourInDirection(current, directions[event.key]);
      // No node that way is not an error, say so rather than silently
      // doing nothing, which reads as the keys not working.
      if (next) focusGraphNode(next);
      else announce("No note in that direction.");
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (graphPopupShows(current)) closeGraphPopup(true);
      else openGraphPopup({ ...graphNodeScreenPoint(current), stopPropagation() {} }, current);
      return;
    }
    // Step through this note's own connections: the relationship the map is
    // actually for, which "nearest in a direction" doesn't follow.
    if (event.key === "n" || event.key === "N") {
      event.preventDefault();
      const linked = [...(graphAdjacency?.get(current.id) || [])];
      if (!linked.length) {
        announce("This note has no connections.");
        return;
      }
      const seen = graphNodeById(graphKeyboardId);
      const position = linked.indexOf(seen?.id);
      const nextId = linked[(position + 1) % linked.length];
      focusGraphNode(graphNodeById(nextId));
      return;
    }
    if (event.key === "Escape") {
      box.blur();
    }
  });
}

//: **A fit fills the free part of the map** (INBOX 775, the owner: "it
//: didnt zoom in or fit to my screen?? I pressed the fit button and it didnt
//: do much"). The margin was 9% of the short side on every edge, and the
//: overlays (the dock, the legend, the minimap, the zoom strip) sat inside
//: it or over the notes; measured on 34 notes at 1440x900, the dots spanned
//: 0.80 of the height. The overlays are now kept clear as insets
//: (`gcFitInsets`), and the margin inside what is left is 1.5%.
const GRAPH_FIT_MARGIN = 0.015;
//: How far a fit zooms in at most. A map of three notes reaches it; past it
//: a dot is a disc the size of a button.
const GRAPH_FIT_MAX_ZOOM = 2.5;
//: Room for a name beside a dot, in screen pixels, before the drawn names
//: are measured (`gcBalanceFit`): names keep their size under a zoom.
const GRAPH_FIT_NAME_PX = 18;

//: The most of the free width or height the names' overhang may take on one
//: side. Names are kept on the canvas where they are placed (`gcClampBox`),
//: so past this a long name is moved in rather than the map shrunk for it:
//: on a 390 phone, three names 190px wide had the balance pass zoom 34 notes
//: from k 0.72 down to 0.28, a third of the width.
const GRAPH_FIT_OVER_SHARE = 0.08;

//: The camera that puts `box` (world units: minX, maxX, minY, maxY) in the
//: middle of the free part of a `width` x `height` map. `insets` are the
//: overlays' depth on each edge and `over` the drawing's overhang past the
//: box (names), both in screen pixels, so neither scales with the zoom. The
//: floor is the fix for "zooms out like crazy": no single outlier can push
//: the whole map below a still-readable scale.
function graphFitFrame(box, width, height, insets = null, over = null) {
  const edge = (o, side) => (o && Number.isFinite(o[side]) ? Math.max(0, o[side]) : 0);
  const freeW = Math.max(1, width - edge(insets, "left") - edge(insets, "right"));
  const freeH = Math.max(1, height - edge(insets, "top") - edge(insets, "bottom"));
  const hang = (side) => Math.min(edge(over, side), GRAPH_FIT_OVER_SHARE * (side === "left" || side === "right" ? freeW : freeH));
  const margin = Math.min(freeW, freeH) * GRAPH_FIT_MARGIN;
  const spanX = Math.max(box.maxX - box.minX, 1);
  const spanY = Math.max(box.maxY - box.minY, 1);
  const raw = Math.min(
    (freeW - 2 * margin - hang("left") - hang("right")) / spanX,
    (freeH - 2 * margin - hang("top") - hang("bottom")) / spanY
  );
  const k = Math.max(0.25, Math.min(GRAPH_FIT_MAX_ZOOM, raw));
  const cx = edge(insets, "left") + freeW / 2;
  const cy = edge(insets, "top") + freeH / 2;
  return {
    k,
    x: cx - ((box.minX + box.maxX) * k + hang("right") - hang("left")) / 2,
    y: cy - ((box.minY + box.maxY) * k + hang("bottom") - hang("top")) / 2,
  };
}

// Zoom/pan so every node fits with a margin (Wave N).
function fitGraphToView(svg, zoomBehavior, nodes, width, height, instant = false) {
  if (!nodes.length) return;
  // Reported: fit-to-view "zooms out like crazy so you only see the generic
  // cluster blobs". It bounded only the node *centres*, and its scale had no
  // floor (`graphFitFrame` has one). The box is each dot's own extent; a
  // name's room is in screen pixels (`GRAPH_FIT_NAME_PX`), and the tab's
  // canvas then balances on the names it actually drew (`gcBalanceFit`).
  const box = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
  for (const n of nodes) {
    const r = graphNodeRadius(n);
    box.minX = Math.min(box.minX, n.x - r);
    box.maxX = Math.max(box.maxX, n.x + r);
    box.minY = Math.min(box.minY, n.y - r);
    box.maxY = Math.max(box.maxY, n.y + r);
  }
  //: The Arc layout is one line of dots with its arcs rising above it, and the
  //: arcs are not nodes, so the box was a strip and the line sat mid-screen
  //: with the arcs cut off the top (owner, 2026-10-12: "it needs to fit a lot
  //: lower on the screen"). The widest arc stands about a third of the line's
  //: length over it; frame that too, so the line settles low and the arcs fit.
  if (graphLayout() === "arc" && nodes.length === (typeof gcTab !== "undefined" && gcTab.nodes ? gcTab.nodes.length : nodes.length)) {
    box.minY -= arcRise(typeof gcTab !== "undefined" ? gcTab.tree?.links : null, (box.maxX - box.minX) * 0.32);
  }
  const tab = typeof gcTab !== "undefined" && gcTab.svg === svg;
  //: Fitted to the whole map is a view a panel may refit (`gcRefitForPanels`);
  //: framed on some of it (a topic) is a place the person was taken to.
  if (tab) gcTab.userZoomed = nodes.length !== gcTab.nodes.length;
  const name = GRAPH_FIT_NAME_PX;
  const fit = graphFitFrame(box, width, height, tab ? gcFitInsets(gcTab) : null, { left: name, right: name, top: name, bottom: name });
  const scale = fit.k;
  const tx = fit.x;
  const ty = fit.y;
  //: **A transform is never built out of a number that is not one.** This is
  //: the app's own producer of the zoom transform, and d3 stores what it is
  //: handed: one NaN here becomes a NaN `k`, `x` and `y` on the node, and
  //: every later reader of it (the minimap's viewport rectangle, the zoom
  //: strip, a saved view) reads NaN out again, for as long as the person
  //: stays on the tab. `Math.max(0.25, Math.min(2.5, NaN))` is NaN, so the
  //: clamps in `graphFitFrame` are not the guard they look like: `Math.min` and
  //: `Math.max` propagate NaN rather than clamping it away, which is how an
  //: undefined width or a node with no position reaches this line looking
  //: clamped. Skipping the fit leaves the camera where it is, which is what
  //: a fit that cannot be computed should do.
  if (!graphMinimapFinite(tx, ty, scale)) return;
  //: The glide to the fitted view is travel, so a reader who asked for less
  //: motion gets the framed map at once (INBOX 443 (1)): the fit lands twice
  //: while a layout settles, and two half-second pans are the most movement
  //: this tab makes on its own.
  const framed = d3.zoomIdentity.translate(tx, ty).scale(scale);
  //: Instant is applied now (see `frameTree`): a zero-length transition
  //: still lands a frame late.
  //: The tab's canvas then balances the fit on what it actually drew
  //: (`gcBalanceFit`): the pad above is a guess at the labels.
  const balance = () => {
    //: The whole map only: a fit to some of it (a topic, `showTopicInGraph`)
    //: is framed on those notes, and balancing on all of them would undo it.
    if (typeof gcTab !== "undefined" && gcTab.svg === svg && nodes.length === gcTab.nodes.length) {
      gcTab.fitCheck = 2;
      gcRequestDraw(gcTab);
    }
  };
  if (instant) {
    svg.interrupt().call(zoomBehavior.transform, framed);
    balance();
  } else svg.transition().duration(graphGlideMs(500)).call(zoomBehavior.transform, framed).on("end", balance);
}

// Dim everything except nodes that match the search box AND (when hovering)
// the hovered note plus its direct neighbours; edges stay bright only when
// both ends survive. Search (Wave M) and hover-spotlight share one pass so
// they can't contradict each other.
// Set by "≈ Similar" to spotlight an explicit set of notes; cleared by the
// next search or refresh.
let graphHighlightIds = null;

//: **A phrase in the search is a filter** (CHAT_PLAN section 2, the graph's
//: row): "connected to Harbor", "untouched since June", "tagged work",
//: "pinned" light the notes they leave, read and resolved by the server
//: (`GET /read/filter`, ai/filters.py; this file reads no words itself). The
//: words left over still match the preview. A box with no filter in it
//: (`ids` null) is the plain search it always was.
const graphPhrase = { q: "", ids: null, rest: "", waiting: false, timer: 0 };

//: The server is asked after a pause, not per key: the plain words are matched
//: in the page at once, and a phrase that is a filter replaces them when the
//: answer comes. `waiting` is true from the first key to the answer, so the
//: count does not say "No matches" for the half-typed filter it is about to read.
function graphReadPhrase(query) {
  if (graphPhrase.q === query) return;
  graphPhrase.q = query;
  graphPhrase.ids = null;
  clearTimeout(graphPhrase.timer);
  graphPhrase.waiting = Boolean(query);
  if (!query) return;
  graphPhrase.timer = setTimeout(() => {
    apiJson("/read/filter?q=" + encodeURIComponent(query) + `&tz_offset_minutes=${-new Date().getTimezoneOffset()}`, { silent: true })
      .then((got) => {
        if (graphPhrase.q !== query) return;
        graphPhrase.waiting = false;
        if (got.ids) {
          graphPhrase.ids = new Set(got.ids);
          graphPhrase.rest = (got.rest || "").toLowerCase();
        }
        applyGraphHighlight(true);
      })
      .catch(() => {
        if (graphPhrase.q === query) graphPhrase.waiting = false;
      });
  }, 150);
}

//: **The search's matches, found once per change** (audit 1029 G10). The
//: canvas used to lowercase a note's preview every time it asked "does this
//: one match?": several times a note, and once per line end, every frame. Now
//: it asks a set. The key is the node array, the query and what the server
//: said about a phrase, so a hover or a pan reuses the last answer untouched.
const graphSearch = { nodes: null, size: 0, query: "", phrase: null, rest: "", ids: null, list: [], at: -1, current: null };

//: A note's lowercase name, kept on the node and made again only when the
//: preview itself changed (an edit, a rename): the label index.
function graphPreviewLower(node) {
  if (node._lcOf !== node.preview) {
    node._lcOf = node.preview;
    node._lc = String(node.preview || "").toLowerCase();
  }
  return node._lc;
}

function graphNodeMatches(node, query) {
  if (graphPhrase.ids && graphPhrase.q === query) {
    return graphPhrase.ids.has(node.id) && (!graphPhrase.rest || graphPreviewLower(node).includes(graphPhrase.rest));
  }
  return !query || graphPreviewLower(node).includes(query);
}

//: The notes `query` lights: `list` newest first (the order Enter walks them
//: in) and `ids` as a set, null for an empty box. A group is a heading over
//: notes, not a note, so it is never one. A new answer starts the walk again.
function graphSearchFor(nodes, query) {
  const g = graphSearch;
  const phrase = graphPhrase.q === query ? graphPhrase.ids : null;
  if (g.nodes === nodes && g.size === nodes.length && g.query === query && g.phrase === phrase && g.rest === graphPhrase.rest) return g;
  Object.assign(g, { nodes, size: nodes.length, query, phrase, rest: graphPhrase.rest, at: -1, current: null });
  g.list = query ? nodes.filter((n) => !n.isGroup && graphNodeMatches(n, query)) : [];
  g.list.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")) || a.id - b.id);
  g.ids = query ? new Set(g.list.map((n) => n.id)) : null;
  return g;
}

function graphSearchNodes() {
  return (typeof gcTab !== "undefined" && gcTab.nodes) || graphNodesRef || [];
}

//: "No matches", "1 match", "134 matches": the count beside the box (G11).
function graphSearchCountText(n) {
  return n ? nounCount(n, "match", "matches") : "No matches";
}

//: The set for what is in the box now, and the count said beside it. The count
//: stays empty while a phrase that may be a filter is still being read.
function graphSearchRefresh(query) {
  const found = graphSearchFor(graphSearchNodes(), query);
  const box = $("graph-search-count");
  const text = !query || (graphPhrase.waiting && !found.list.length) ? "" : graphSearchCountText(found.list.length);
  if (box && box.textContent !== text) box.textContent = text;
  return found;
}

//: `cheap` is a change of the query alone: the scene the canvas painted is
//: still right, so the frame is composed from it (`gcDrawComposed`). Anything
//: else that lands here may have changed what the scene shows.
function applyGraphHighlight(cheap) {
  const query = $("graph-search").value.trim().toLowerCase();
  if (query) graphHighlightIds = null; // typing takes over the spotlight
  graphReadPhrase(query);
  graphSearchRefresh(query);
  // Reported: no way to cancel the "≈ Similar" highlight - it only ever
  // reset as a side effect of something else (typing over it, or a full
  // refresh). Same shape as #graph-focus-clear: shown exactly while there's
  // something to clear, synced here since this is the one function every
  // path that sets or resets graphHighlightIds already runs through.
  $("graph-highlight-clear")?.classList.toggle("hidden", !graphHighlightIds);
  // The four-way spotlight (search, the "similar notes" set, a traced path,
  // the hover neighbourhood) is computed inside the canvas draw, from this
  // same state, see `gcHighlight`, so all this has to do is ask for a frame.
  gcRequestDraw(gcTab, cheap === true);
}

//: Typing re-reads the matches at once (about 0.6 ms at 2,000 notes) and asks
//: for a frame; `gcRequestDraw` keeps one frame queued, so a burst of keys is
//: one redraw. The pause that used to sit here made the first letters wait for
//: nothing: what is slow is the repaint, not the match (audit 1029 G10).
$("graph-search").addEventListener("input", () => applyGraphHighlight(true));

//: **Walking the matches** (audit 1029 G11). Enter goes to the next match and
//: pans to it, Shift+Enter to the one before, both wrapping; the match is ringed
//: and named whatever else is dimmed (`gcHighlight`'s `current`), and said in
//: the page's polite region. Escape clears the search and the "similar notes"
//: highlight; on an empty box it is left alone, for whatever else listens.
function graphSearchStepIndex(at, dir, n) {
  if (!n) return -1;
  if (at < 0) return dir < 0 ? n - 1 : 0;
  return (at + dir + n) % n;
}

function graphPanToNode(node) {
  if (!graphSvg || !graphZoom || !graphMinimapFinite(graphDims.w, graphDims.h, node.x, node.y)) return;
  const k = d3.zoomTransform(graphSvg.node()).k;
  const target = d3.zoomIdentity.translate(graphDims.w / 2, graphDims.h / 2).scale(k).translate(-node.x, -node.y);
  //: Moved by hand as far as the settle fit is concerned (INBOX 792).
  if (typeof gcTab !== "undefined" && gcTab.svg === graphSvg) gcTab.userZoomed = true;
  graphSvg.transition().duration(graphGlideMs(300)).call(graphZoom.transform, target);
}

function graphSearchGo(dir) {
  const box = $("graph-search");
  const found = graphSearchRefresh(box.value.trim().toLowerCase());
  const at = graphSearchStepIndex(found.at, dir, found.list.length);
  if (at < 0) {
    announce("No matches.");
    return;
  }
  const node = found.list[at];
  found.at = at;
  found.current = node.id;
  //: The suggestions list sits over the map's left side; a jump is the end of typing.
  if (typeof searchSuggest !== "undefined" && searchSuggest?.input === box) {
    searchSuggest.quiet = true;
    fillSearchSuggest();
  }
  announce(`Match ${at + 1} of ${found.list.length}: ${node.preview}`);
  graphPanToNode(node);
  gcRequestDraw(gcTab, true);
}

function graphSearchClear() {
  //: A spotlight is part of the scene the canvas painted, so lifting one is a
  //: whole frame; a search alone is not.
  const spotlit = Boolean(graphHighlightIds);
  $("graph-search").value = "";
  graphHighlightIds = null;
  applyGraphHighlight(!spotlit);
  announce("Search cleared.");
}

function graphSearchKey(event) {
  if (event.isComposing) return;
  const box = $("graph-search");
  if (event.key === "Enter" && box.value.trim()) {
    event.preventDefault();
    graphSearchGo(event.shiftKey ? -1 : 1);
  } else if (event.key === "Escape" && (box.value || graphHighlightIds)) {
    event.preventDefault();
    event.stopPropagation();
    graphSearchClear();
  }
}
$("graph-search").addEventListener("keydown", graphSearchKey);
//: Focusing the box paints the dimmed layer the search is drawn over, in an
//: idle moment, so the first key costs what the others do (about 250 ms at
//: 2,000 notes, once, otherwise paid inside the first keystroke).
$("graph-search").addEventListener("focus", () => {
  if (typeof gcTab === "undefined") return;
  const warm = () => {
    gcTab.warmDim = true;
    gcRequestDraw(gcTab, true);
  };
  if (window.requestIdleCallback) requestIdleCallback(warm, { timeout: 400 });
  else setTimeout(warm, 0);
});

// --- graph node popup: edit a note without leaving the map -------------------

let graphPopupId = null;
let graphPopupAnchor = null;
//: What the note said when it arrived. Save is a primary action and a primary
//: action that is always on screen stops meaning "do this": the panel is
//: opened to *read* a note far more often than to edit one (GRAPH_PLAN Phase
//: 6). Comparing against the loaded text, rather than listening for any
//: keystroke, means typing a word and deleting it again puts the button away.
let graphPopupClean = { content: "", tags: "" };

//: The header's identity line, the muted meta line under it, and the Save
//: gate all read the same entry, so they are filled from one place.
function renderGraphPopupHeader(entry, node) {
  const titleEl = $("graph-popup-title");
  //: The title used to be the *category*, with the category also sitting in
  //: the chip row below it: the note's own name was nowhere on a panel about
  //: that note. `entry.title` when the AI (or the owner) gave it one, the
  //: first line otherwise, which is what every other note surface shows.
  const firstLine = noteNamePlain(entry.content);
  titleEl.textContent =
    entry.title || firstLine.slice(0, 80).trim() || node.category || "Note";
  //: The title is ellipsised to one line now, so the whole of it has to be
  //: reachable some other way: hover is the cheapest, and it is what every
  //: other truncated label in this app already does.
  titleEl.title = titleEl.textContent;

  const confidence = $("graph-popup-confidence");
  //: `> 0`, not `typeof === "number"`: a note the AI never filed carries 0,
  //: and "0%" beside a title reads as a verdict on the note rather than as
  //: "there is no figure here". The old chip had the same bug and said
  //: "0% confident" out loud.
  //: And not on a note the person filed: that is theirs, with no percentage.
  const hasConfidence = typeof entry.ai_confidence === "number" && entry.ai_confidence > 0 && !entry.user_filed;
  confidence.classList.toggle("hidden", !hasConfidence);
  if (hasConfidence) {
    confidence.textContent = `${entry.ai_confidence}%`;
    confidence.title = `Atlas's estimate that this is the right category: ${entry.ai_confidence}%`;
  }

  const category = $("graph-popup-category");
  const name = entry.category || node.category || "";
  category.classList.toggle("hidden", !name);
  if (name) setLabel(category, `ph:folders ${name}`);
}

//: INBOX 1471: the same note's second click closes its panel (a click on
//: another note still switches it; Esc and the empty canvas close as before).
function graphPopupShows(node) {
  return graphPopupId === node.id && !$("graph-popup").classList.contains("hidden");
}

async function openGraphPopup(event, node) {
  event.stopPropagation();
  if (graphPopupId !== node.id) keepGraphPopupEdit();
  graphPopupId = node.id;
  graphLate.popupDragged = false;
  //: The open note wears the focus ring (graph-canvas.js `openId`).
  if (typeof gcTab !== "undefined" && gcTab.canvas) gcRequestDraw(gcTab);
  const popup = $("graph-popup");
  const status = $("graph-popup-status");
  status.textContent = "";
  status.classList.remove("error");
  //: The node's own preview while the note is on its way, not its category:
  //: the title says what this note is now, and a placeholder reading
  //: "Uncategorised" for the length of a fetch is a wrong answer to that
  //: question rather than an absent one. `preview` is the same string the
  //: canvas paints beside the node (`gcLabelText`), so the panel opens
  //: saying what the map said.
  const mapTitle = $("graph-popup-title");
  mapTitle.textContent = node.preview || node.category || "Note";
  mapTitle.title = mapTitle.textContent;
  $("graph-popup-confidence").classList.add("hidden");
  $("graph-popup-category").classList.add("hidden");
  $("graph-popup-info").textContent = "";
  $("graph-popup-content").value = "Loading…";
  $("graph-popup-tags").value = "";
  graphPopupClean = { content: "Loading…", tags: "" };
  syncGraphPopupSave();
  popup.classList.remove("hidden");

  // Remember where the click was: the popup has to be placed again once the
  // note arrives, because the info chips and action buttons render afterwards
  // and grow it. Positioning only on open is what let a tall note hang off
  // the bottom of the map.
  graphPopupAnchor = { x: event.clientX, y: event.clientY };
  placeGraphPopup();

  const entry = await apiJson(`/entries/${node.id}?open=1`).catch(() => null);
  if (!entry || graphPopupId !== node.id) {
    if (graphPopupId === node.id) {
      $("graph-popup-content").value = "";
      status.textContent = "Couldn't load this note.";
      status.classList.add("error");
    }
    return;
  }
  $("graph-popup-content").value = entry.content;
  $("graph-popup-tags").value = (entry.tags || []).join(", ");
  graphPopupClean = { content: entry.content, tags: (entry.tags || []).join(", ") };
  syncGraphPopupSave();
  renderGraphPopupHeader(entry, node);
  renderGraphPopupInfo(entry);
  renderGraphPopupTopic(entry);
  renderGraphPopupProps(entry);
  renderGraphPopupMedia(entry);
  renderGraphPopupActions(entry);
  //: The editor is sized to the note it just received, not to a fixed slot.
  //: `autoGrow` measures `scrollHeight`, so it has to run after the value is
  //: set and while the panel is visible, which it now is.
  if (typeof autoGrow === "function") autoGrow($("graph-popup-content"));
  placeGraphPopup(); // now that it's at its real height
  //: The body opens rendered, not as raw markdown waiting for a click: the
  //: editor used to mount on the box's first focus, and since the popup
  //: focuses the dialog rather than the box (INBOX 198) that focus never
  //: came. Mounting here also fetches the editor's bundle on the first
  //: popup of a session (app.js, `mountNoteSurfaceNow`). The view is taller
  //: than the textarea it replaces, so the popup is placed once more.
  if (typeof mountNoteSurfaceNow === "function") {
    mountNoteSurfaceNow($("graph-popup-content")).then(() => {
      if (graphPopupId === node.id) placeGraphPopup();
    });
  }
  //: The dialog takes focus, not the note's text box: focusing the box put
  //: its caret in the markdown, so the popup opened on raw `![...](...)`
  //: and only rendered once you clicked away (INBOX 198). Escape and Tab
  //: still work from the dialog itself.
  const dialog = $("graph-popup");
  if (dialog) {
    if (!dialog.hasAttribute("tabindex")) dialog.tabIndex = -1;
    dialog.focus({ preventScroll: true });
  }
}

//: Save appears when the content or the tags differ from what loaded, and
//: goes away again when they match. Called from the two fields' `input`
//: events (app.js wires them) and after every load or save.
function syncGraphPopupSave() {
  const save = $("graph-popup-save");
  if (!save) return;
  const dirty =
    $("graph-popup-content").value !== graphPopupClean.content ||
    $("graph-popup-tags").value !== graphPopupClean.tags;
  save.classList.toggle("hidden", !dirty);
}

//: Removes a link after asking, with an undo, and redraws. Shared by the
//: link's panel and its peek. Says whether it went.
async function graphRemoveLink(edge, sourceId) {
  if (!(await confirmDialog("Remove this connection entirely?\n\nThe two notes are untouched, only the link between them goes."))) return false;
  //: Captured before the delete, because after it there is nothing left to
  //: read the other end and the reason off.
  const targetId = edge.target?.id ?? edge.target;
  const linkType = edge.link_type || null;
  const reason = edge.reason || null;
  await apiJson(`/entries/${sourceId}/links/${edge.id}`, { method: "DELETE" }).catch((e) => toast(e.message, true));
  //: **A link is the one thing in this notebook you cannot rebuild from
  //: memory.** Which two notes, in which direction, with what reason, a
  //: confirm dialog is not an undo, and this had only the dialog. The
  //: recreated link gets a new id, so the redo closure re-reads it rather
  //: than assuming the old one comes back.
  let recreatedId = null;
  pushUndo(
    "Removed a link",
    async () => {
      const made = await apiJson(`/entries/${sourceId}/links`, {
        method: "POST",
        body: JSON.stringify({ target_id: targetId, link_type: linkType, reason }),
      });
      recreatedId = made.link_id ?? made.id ?? null;
      renderGraph();
    },
    async () => {
      if (recreatedId === null) return;
      await apiJson(`/entries/${sourceId}/links/${recreatedId}`, { method: "DELETE" });
      renderGraph();
    }
  );
  toast("Link removed.");
  renderGraph();
  return true;
}

//: **The peek: what a line on the map is, where it was clicked** (the owner,
//: 2026-10-04: "I cant click on links to see their reason in the graph??").
//: A click on a link went straight to the panel below, a modal editor, and a
//: thread, a similarity or a map's line answered nothing. Now any of them
//: opens the popover shell (`.help-popover`, DESIGN.md's popover tier) at the
//: pointer: the kind, the reason and how sure the app is of it, the two
//: notes (each opens its own panel), and for a link, Edit reason (the panel)
//: and Remove. Escape, a press elsewhere or a redraw closes it.
let graphLinkPeek = null;

function closeGraphLinkPeek() {
  if (!graphLinkPeek) return;
  graphLinkPeek.panel.remove();
  graphLinkPeek.anchor.remove();
  graphLinkPeek = null;
}

function graphLinkKind(edge) {
  if (edge.kind === "similar") return `Similar in meaning${typeof edge.score === "number" ? `, ${Math.round(edge.score * 100)}%` : ""}`;
  if (edge.kind === "thread") return "Thread: one note continues the other";
  if (edge.kind === "map") return "Joined on a mind map";
  if (edge.kind === "comention") return `Named together in ${edge.weight} notes`;
  return edge.link_type && edge.link_type !== "related" ? `Link: ${edge.type_name || edge.link_type}${edge.type_inverse ? ` (${edge.type_inverse} the other way)` : ""}` : "Link";
}

function openGraphLinkPeek(edge, event, nodes) {
  closeGraphLinkPeek();
  const end = (e) => (typeof e === "object" ? e : nodes.find((n) => n.id === e));
  const ends = [end(edge.source), end(edge.target)].filter(Boolean);
  const anchor = document.createElement("span");
  anchor.className = "graph-link-peek-anchor";
  anchor.style.left = `${event.clientX}px`;
  anchor.style.top = `${event.clientY}px`;
  document.body.appendChild(anchor);
  const panel = document.createElement("div");
  panel.className = "help-popover graph-link-peek";
  panel.id = "graph-link-peek";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "This connection");
  panel.tabIndex = -1;
  const kind = document.createElement("p");
  kind.className = "graph-link-peek-kind";
  kind.textContent = graphLinkKind(edge);
  const reason = document.createElement("p");
  reason.className = "graph-link-peek-reason";
  reason.textContent = edge.reason ? edge.reason : edge.kind === "link" ? "No reason given yet." : "";
  reason.classList.toggle("muted", !edge.reason);
  const facts = document.createElement("p");
  facts.className = "library-file-meta graph-link-peek-meta";
  facts.textContent = edge.reason_confidence != null
    ? `Deduced, ${deducedStrength(edge.reason_confidence)}`
    : edge.reason ? "In your words" : "";
  const notes = document.createElement("div");
  notes.className = "graph-link-peek-notes";
  for (const node of ends) {
    const open = smallButton(`ph:note ${graphNodeLabel(node, node.id)}`, "Open this note", (click) => {
      closeGraphLinkPeek();
      openGraphPopup(click, node);
    });
    open.classList.add("ghost");
    notes.appendChild(open);
  }
  panel.append(kind, notes, ...[reason, facts].filter((el) => el.textContent));
  if (edge.kind === "link" && edge.id != null) {
    const sourceId = typeof edge.source === "object" ? edge.source.id : edge.source;
    const actions = document.createElement("div");
    actions.className = "graph-link-peek-actions";
    const editReason = smallButton("ph:pencil-simple Edit reason", "Write or change why these are linked", () => {
      closeGraphLinkPeek();
      openGraphLinkPanel(edge, nodes);
    });
    const remove = smallButton("ph:trash Remove", "Remove this link", async () => {
      closeGraphLinkPeek();
      await graphRemoveLink(edge, sourceId);
    });
    //: INBOX 693, the owner: "what if the user makes a link meaning for the
    //: note link to be omnidirectional and not a directional link??". One
    //: switch, pressed for a link that runs both ways; Arrows draws none on
    //: it (`gcDraw`). Saved on the link (PATCH two_way).
    const direction = smallButton("ph:arrows-left-right Two-way", "Two-way: this link runs both ways and is drawn with no arrow. One-way: from the note that made it", async () => {
      const next = !edge.two_way;
      try {
        await apiJson(`/entries/${sourceId}/links/${edge.id}`, { method: "PATCH", body: JSON.stringify({ two_way: next }) });
      } catch (error) {
        toast(error.message || "Couldn't change the link's direction.", true);
        return;
      }
      pushRequestUndo(
        next ? "Made a link two-way" : "Made a link one-way",
        `/entries/${sourceId}/links/${edge.id}`,
        "PATCH",
        { two_way: !next },
        { two_way: next },
        () => renderGraph()
      );
      for (const drawn of gcTab.edges) if (drawn.id === edge.id && drawn.kind === "link") drawn.two_way = next;
      edge.two_way = next;
      direction.setAttribute("aria-pressed", String(next));
      gcRequestDraw();
      toast(next ? "This link now runs both ways." : "This link now runs one way.");
    });
    direction.id = "graph-link-two-way";
    direction.setAttribute("aria-pressed", String(Boolean(edge.two_way)));
    editReason.classList.add("ghost");
    direction.classList.add("ghost");
    remove.classList.add("ghost", "danger");
    actions.append(editReason, direction, remove);
    panel.appendChild(actions);
  }
  document.body.appendChild(panel);
  graphLinkPeek = { panel, anchor };
  placeHelpPopover(panel, anchor);
  panel.focus({ preventScroll: true });
}

document.addEventListener(
  "keydown",
  (event) => {
    if (event.key !== "Escape" || !graphLinkPeek) return;
    event.preventDefault();
    event.stopPropagation();
    closeGraphLinkPeek();
  },
  true
);
document.addEventListener("pointerdown", (event) => {
  if (graphLinkPeek && !graphLinkPeek.panel.contains(event.target) && event.target.id !== "graph-canvas") closeGraphLinkPeek();
});

//: A note's name for a one-line place: cut at the last whole word, with the
//: ellipsis only when something was cut ("This g" read as broken text).
function graphNodeLabel(n, id) {
  const text = n?.preview || `Note ${id}`;
  if (text.length <= 60) return text;
  const cut = text.slice(0, 60);
  return `${cut.slice(0, cut.lastIndexOf(" ") + 1 || 60).trimEnd()}…`;
}

// A link edge's own management panel, asked for directly: "a visual way
// to see the reasons for each connection and a way to manage/add/remove/
// edit them." Clicking a `kind: "link"` edge (see `renderGraph`'s own
// click handler) opens this rather than only ever showing the reason on
// hover. A dynamic overlay, the same `promptDialog`/`confirmDialog`
// pattern, rather than fixed markup, this is the one place in the app
// that edits a *connection* rather than a note or a whiteboard item, so it
// doesn't share a container with either.
function openGraphLinkPanel(edge, nodes) {
  const sourceId = typeof edge.source === "object" ? edge.source.id : edge.source;
  const targetId = typeof edge.target === "object" ? edge.target.id : edge.target;
  const sourceNode = nodes.find((n) => n.id === sourceId);
  const targetNode = nodes.find((n) => n.id === targetId);
  const label = graphNodeLabel;

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay confirm-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Manage this connection");

  const card = document.createElement("div");
  card.className = "card modal-card confirm-card graph-link-panel";

  // Two notes on their own lines, not one run-on sentence joined by an
  // arrow: reported as unreadable once both previews ran long enough to
  // wrap, since nothing showed which half belonged to which note.
  card.appendChild(dialogHead("Manage this connection", () => close()));
  const title = document.createElement("div");
  title.className = "confirm-text graph-link-panel-title";
  const sourceLine = document.createElement("div");
  sourceLine.textContent = label(sourceNode, sourceId);
  const arrow = document.createElement("div");
  arrow.className = "muted graph-link-panel-arrow";
  //: Through `setLabel`, so the leading mark is a Phosphor icon rather than a
  //: typed arrow at the system face.
  setLabel(arrow, "ph:arrows-down-up connected to");
  const targetLine = document.createElement("div");
  targetLine.textContent = label(targetNode, targetId);
  title.append(sourceLine, arrow, targetLine);
  card.appendChild(title);

  if (edge.reason_confidence != null) {
    const note = document.createElement("p");
    note.className = "muted";
    note.textContent = `Deduced (${deducedStrength(edge.reason_confidence)}): editing replaces it with your own words.`;
    card.appendChild(note);
  }

  const textarea = document.createElement("textarea");
  textarea.className = "graph-link-panel-reason";
  textarea.placeholder = "Why are these connected? (optional)";
  textarea.value = edge.reason || "";
  textarea.rows = 3;
  card.appendChild(textarea);

  const returnFocus = document.activeElement;
  const close = () => {
    overlay.remove();
    returnFocus?.focus?.();
  };

  const row = document.createElement("div");
  row.className = "row confirm-actions";

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.textContent = "Save";

  const generateBtn = document.createElement("button");
  generateBtn.type = "button";
  generateBtn.className = "ghost";
  setLabel(generateBtn, "ph:sparkle Generate");
  generateBtn.addEventListener("click", async () => {
    setBusy(generateBtn, true, "Generating…");
    try {
      const res = await apiJson(`/entries/${sourceId}/links/${edge.id}/generate-reason`, { method: "POST" });
      textarea.value = res.reason;
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(generateBtn, false);
    }
  });

  saveBtn.addEventListener("click", async () => {
    await apiJson(`/entries/${sourceId}/links/${edge.id}/reason`, {
      method: "PUT",
      body: JSON.stringify({ reason: textarea.value.trim() || null }),
    }).catch((e) => toast(e.message, true));
    toast("Saved.");
    close();
    renderGraph();
  });

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "ghost danger";
  setLabel(removeBtn, "ph:trash Remove link");
  removeBtn.addEventListener("click", async () => {
    if (await graphRemoveLink(edge, sourceId)) close();
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "ghost";
  cancelBtn.textContent = "Close";
  cancelBtn.addEventListener("click", close);

  row.append(saveBtn, generateBtn, removeBtn, cancelBtn);
  card.appendChild(row);
  overlay.appendChild(card);
  wireBackdropClose(overlay, () => close());
  document.body.appendChild(overlay);
  textarea.focus();
}

// Show a note's images in the popup, biggest reason being sketches.
//
// A sketch is stored as a note carrying the caption plus a PNG attachment, so
// on the map it is an ordinary node and the popup showed its caption and
// nothing else. There was no way to see the drawing from the graph at all, 
// "Open" only took you to the Notes tab, where you still had to find the card
// and click its thumbnail. Reported as "sketches don't open from the graph",
// and that is exactly right: the one thing the note is *about* was missing.
//: **And the same for everything that is not a picture.** Reported: "files and
//: attachments dont render in the timeline and popups." This popup and the
//: timeline's both filtered to `is_image` and dropped the rest, so a note
//: whose whole point is the PDF attached to it opened a popup with nothing in
//: it: no hint that anything was attached, which reads as the note having
//: lost the file. `fileCard` is the app's own control for an attached file
//: (the note cards, the chat transcript and the widgets all use it); this
//: surface was the one place a file did not appear at all.
//: **A note's pictures are in two places, and this used to look in one.**
//: Reported (INBOX 183, the owner): "the graph popups dont render images or
//: files", with a screenshot of a node panel for an image with nothing in it.
//: Reproduced before it was touched: a note carrying a real *attachment* drew
//: its thumbnail correctly (naturalWidth 2 on a 2x2 probe) and a note whose
//: picture is a library upload referenced from its own markdown drew nothing
//: at all, `#graph-popup-media` hidden with 0 children. Pasted, dropped and
//: AI-attached pictures all end up as `![alt](/media/...)` in the body and
//: there is no column that mirrors them (`noteAnyImage` in library.js says the
//: same thing about the other direction), so a panel that reads only
//: `entry.attachments` is blind to the commonest kind of image note there is.
//:
//: Only this app's own stored files, the same rule `noteFirstImage` keeps: an
//: external `https://` image is blocked by the CSP (`img-src 'self' data:
//: blob:`), so drawing one would guarantee a broken frame.
const GRAPH_POPUP_MEDIA_REF = /(!?)\[([^\]\n]{0,200})\]\((\/(?:media|files)\/[^)\s]{1,500})\)/g;

function graphPopupMediaRefs(entry) {
  const refs = [];
  const seen = new Set();
  //: An attachment's own url is `/files/<id>`, and a note can both carry the
  //: file and link to it in its text. Same url, one card.
  for (const attachment of entry.attachments || []) seen.add(`/files/${attachment.id}`);
  for (const match of (entry.content || "").matchAll(GRAPH_POPUP_MEDIA_REF)) {
    const url = match[3];
    if (seen.has(url)) continue;
    seen.add(url);
    refs.push({ image: match[1] === "!", name: match[2] || url.split("/").pop(), url });
  }
  return refs;
}

//: The name of a file, then what it is and how big, which is what the Library
//: says about the same file (`.library-file-meta`: "one line of facts, dot
//: separated"). `fileCard` states the kind already; the size is the fact this
//: panel was missing, and it is the one that answers "is this the scan or the
//: thumbnail" without opening it. `formatFileSize` returns "" for an unknown
//: or zero size, which is why nothing is appended in that case rather than a
//: claim the panel cannot make.
//: The attachment card states it itself now (INBOX 440 (2)), given the size.
function graphPopupFileCard(name, url, size) {
  return fileCard(name, url, size);
}

function renderGraphPopupMedia(entry) {
  const box = $("graph-popup-media");
  box.replaceChildren();
  const all = entry.attachments || [];
  const images = all.filter((a) => a.is_image);
  const files = all.filter((a) => !a.is_image);
  const refs = graphPopupMediaRefs(entry);
  const refFiles = refs.filter((r) => !r.image);
  box.classList.toggle("hidden", all.length === 0 && refFiles.length === 0);
  if (!all.length && !refFiles.length) return;
  for (const attachment of files) {
    box.appendChild(
      graphPopupFileCard(
        attachment.filename || attachment.name || "",
        attachment.url || `/files/${attachment.id}`,
        attachment.size
      )
    );
  }
  //: A file the note links to rather than carries. Its size is not on the
  //: note's payload, so the card states its kind and its name and stops there.
  for (const ref of refFiles) box.appendChild(fileCard(ref.name, ref.url));
  for (const attachment of images) {
    const img = document.createElement("img");
    img.className = "graph-popup-thumb";
    img.alt = attachment.filename;
    img.title = `${attachment.filename}: click to view full size`;
    // The bytes need the auth header, so they arrive as an object URL rather
    // than a plain src. Cached per attachment by attachmentObjectUrl.
    attachmentObjectUrl(attachment)
      .then((url) => {
        img.src = url;
        placeGraphPopup(); // the popup just got taller
      })
      .catch(() => img.remove());
    img.addEventListener("click", () => {
      openLightbox(
        images.map((a) => ({ filename: a.filename, getUrl: () => attachmentObjectUrl(a), openUrl: `/files/${a.id}` })),
        images.indexOf(attachment)
      );
    });
    box.appendChild(img);
  }
  //: A stored url carries the token in the query string (`mediaSrc`), which is
  //: how every other surface that renders note markdown draws these: no fetch,
  //: no object url, and the browser's own cache.
  //: Pictures the note's own markdown references are not repeated here: the
  //: body below renders them itself (the live surface, DOCUMENTS Phase 8b),
  //: so a thumbnail of the same picture drew it twice (INBOX 198). Files
  //: referenced in the text stay, since the body shows those as a link.
  placeGraphPopup();
}

//: **The room a graph panel has** (the owner, 2026-10-11: "the graph popups
//: get cut off now at the bottom", the action dock behind the status bar at
//: a 1000px window): the map's box, ending where the shell's status bar
//: starts if the box runs under it. Read from the bar's own box, which is
//: `--status-bar-h` tall (00-tokens-shell.css), so the bound follows the
//: shell's layout rather than a number copied here. Returns the box with
//: `room`, the usable height from the box's top.
function graphPanelRoom() {
  const box = $("graph-box").getBoundingClientRect();
  const bar = document.getElementById("status-bar");
  const barTop = bar && bar.offsetParent !== null ? bar.getBoundingClientRect().top : innerHeight;
  const bottom = Math.min(box.bottom, barTop, innerHeight);
  return { box, room: Math.max(0, bottom - box.top) };
}

//: Placed again whenever it changes size after it was placed (the body's
//: editor mounting, a picture arriving, the action row folding): placing
//: only at known moments is what let a panel that grew afterwards hang
//: past the map's bottom edge.
const graphLate = {
  newAt: null,
  popupResize: null,
  //: The popup's own placement (INBOX 1413): `popupDragged` once the head has
  //: moved it (it then stays where put until closed), `popupDrag` the live gesture.
  popupDragged: false,
  popupDrag: null,
};
function watchGraphPopupSize(popup, place) {
  if (typeof ResizeObserver !== "function" || popup.dataset.placeWatch) return;
  popup.dataset.placeWatch = "1";
  let frame = 0;
  graphLate.popupResize = graphLate.popupResize || new ResizeObserver((entries) => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      for (const e of entries) e.target.graphPlace?.();
    });
  });
  popup.graphPlace = place;
  graphLate.popupResize.observe(popup);
}

// Clamp the popup inside the graph box. Called on open and again once the
// note has loaded, since the popup is taller by then.
//: **The popup keeps room to follow its node in y** (audit 1029 G25). A long
//: note took the map's whole height less 16 (517 of 533 at 1280x640), so its
//: slide was 16px: the node moved 280px and the popup 0, which read as
//: following in x only. An undragged popup is held to 60% of the room (never
//: under 280px; the body scrolls inside it and the dock stays pinned); one the
//: head has moved stays where put and keeps the whole room.
function graphPopupCap(room, dragged) {
  const full = Math.max(120, room - 16);
  return dragged ? full : Math.min(full, Math.max(280, Math.round(room * 0.6)));
}

function placeGraphPopup() {
  const popup = $("graph-popup");
  watchGraphPopupSize(popup, placeGraphPopup);
  if (!graphPopupAnchor || popup.classList.contains("hidden")) return;
  const { box, room } = graphPanelRoom();
  //: **Save stands above the dock, not under it** (INBOX 1421). Both are pinned
  //: at the panel's foot and Save is one layer higher, so at `bottom: 0` it was
  //: drawn over the dock for as tall as the dock is. The dock's own offset
  //: already has the panel's padding inside it, so that comes off.
  const dock = popup.querySelector(".graph-popup-actions");
  const saveRow = $("graph-popup-saverow");
  if (dock && saveRow) {
    const pad = parseFloat(getComputedStyle(popup).paddingBottom) || 0;
    saveRow.style.bottom = `${Math.max(0, dock.offsetHeight - pad)}px`;
  }
  //: **On a phone the panel is a sheet, and JS has to be the one to say so**
  //: (GRAPH_PLAN Phase 6). The position is inline `left`/`top` written here,
  //: which no stylesheet rule can override without `!important`, so a media
  //: query alone could style the sheet and never place it. The band is the
  //: app's own 600px one, spelled the same way as in the stylesheet.
  if (window.matchMedia("(max-width: 599.98px)").matches) {
    popup.classList.add("graph-popup-sheet");
    // Three quarters of the map: enough to read the note, and the map it
    // came from stays visible above it so the sheet has an origin.
    popup.style.maxHeight = `${Math.max(160, Math.round(room * 0.75))}px`;
    popup.style.left = "0px";
    const sheet = popup.getBoundingClientRect();
    popup.style.top = `${Math.max(0, Math.round(room - sheet.height))}px`;
    return;
  }
  popup.classList.remove("graph-popup-sheet");
  // Never taller than the room it has, beyond that its body scrolls inside
  // it and the action dock stays pinned at its foot (the CSS's sticky row).
  popup.style.maxHeight = `${graphPopupCap(room, graphLate.popupDragged)}px`;
  const size = popup.getBoundingClientRect();
  const maxLeft = Math.max(8, box.width - size.width - 8);
  const maxTop = Math.max(8, room - size.height - 8);
  let spot = null;
  if (graphLate.popupDragged) {
    //: Where the person put it: only kept inside the map when the map or
    //: the popup changes size.
    spot = { left: parseFloat(popup.style.left) || 8, top: parseFloat(popup.style.top) || 8 };
    spot.left = Math.min(Math.max(spot.left, 0), Math.max(0, box.width - size.width));
    spot.top = Math.min(Math.max(spot.top, 0), Math.max(0, room - size.height));
  } else {
    spot = graphPopupFollowSpot(box, room, size);
  }
  if (!spot) {
    spot = {
      left: Math.min(Math.max(graphPopupAnchor.x - box.left + 12, 8), maxLeft),
      top: Math.min(Math.max(graphPopupAnchor.y - box.top + 12, 8), maxTop),
    };
  }
  const left = `${Math.round(spot.left)}px`;
  const top = `${Math.round(spot.top)}px`;
  if (popup.style.left !== left) popup.style.left = left;
  if (popup.style.top !== top) popup.style.top = top;
}

//: **An undragged popup stands beside its own node** (INBOX 1413), on the
//: right, else the left, else under or over it, so it never covers the node it
//: is about; it follows the node as the map pans, zooms and settles
//: (`gcDraw` calls `placeGraphPopup` once a frame, so it costs nothing when
//: nothing moves) and is hidden (not closed) while the node is out of view.
function graphPopupFollowSpot(box, room, size) {
  const popup = $("graph-popup");
  const s = typeof gcTab !== "undefined" ? gcTab : null;
  const node = s && s.byId && graphPopupId != null ? s.byId.get(graphPopupId) : null;
  if (!node || !Number.isFinite(node.x) || !s.canvas || s.size !== "full") return null;
  const c = s.canvas.getBoundingClientRect();
  const t = s.transform;
  const sx = c.left - box.left + node.x * t.k + t.x;
  const sy = c.top - box.top + node.y * t.k + t.y;
  const r = Math.max(4, (node.r || 6) * t.k);
  const gone = sx < 0 || sy < 0 || sx > box.width || sy > room;
  popup.classList.toggle("graph-popup-away", gone);
  const gap = 12;
  const w = size.width;
  const h = size.height;
  const clampX = (v) => Math.min(Math.max(v, 8), Math.max(8, box.width - w - 8));
  const clampY = (v) => Math.min(Math.max(v, 8), Math.max(8, room - h - 8));
  const tries = [
    [sx + r + gap, sy - 20],
    [sx - r - gap - w, sy - 20],
    [sx - w / 2, sy + r + gap],
    [sx - w / 2, sy - r - gap - h],
  ];
  const clear = (x, y) => x + w < sx - r || x > sx + r || y + h < sy - r || y > sy + r;
  let best = null;
  for (const [x, y] of tries) {
    const spot = { left: clampX(x), top: clampY(y) };
    if (clear(spot.left, spot.top)) return spot;
    best = best || spot;
  }
  return best;
}

//: The head drags the popup (pointer and touch); the buttons and fields keep
//: their own clicks. Once moved it stays put, inside the map, until closed.
function graphPopupDragStart(ev) {
  const popup = $("graph-popup");
  if (ev.button > 0 || ev.target.closest("button, input, textarea, a")) return;
  if (popup.classList.contains("graph-popup-sheet")) return;
  const at = popup.getBoundingClientRect();
  graphLate.popupDrag = { id: ev.pointerId, dx: ev.clientX - at.left, dy: ev.clientY - at.top };
  try { ev.currentTarget.setPointerCapture(ev.pointerId); } catch (e) { /* synthetic events */ }
  popup.classList.add("graph-popup-dragging");
  ev.preventDefault();
}
function graphPopupDragMove(ev) {
  const d = graphLate.popupDrag;
  if (!d || d.id !== ev.pointerId) return;
  const popup = $("graph-popup");
  const { box, room } = graphPanelRoom();
  const size = popup.getBoundingClientRect();
  const left = Math.min(Math.max(ev.clientX - d.dx - box.left, 0), Math.max(0, box.width - size.width));
  const top = Math.min(Math.max(ev.clientY - d.dy - box.top, 0), Math.max(0, room - size.height));
  graphLate.popupDragged = true;
  popup.classList.remove("graph-popup-away");
  popup.style.left = `${Math.round(left)}px`;
  popup.style.top = `${Math.round(top)}px`;
}
function graphPopupDragEnd(ev) {
  const d = graphLate.popupDrag;
  if (!d || d.id !== ev.pointerId) return;
  graphLate.popupDrag = null;
  $("graph-popup").classList.remove("graph-popup-dragging");
}
{
  const head = document.querySelector("#graph-popup .graph-popup-head");
  if (head) {
    head.addEventListener("pointerdown", graphPopupDragStart);
    head.addEventListener("pointermove", graphPopupDragMove);
    head.addEventListener("pointerup", graphPopupDragEnd);
    head.addEventListener("pointercancel", graphPopupDragEnd);
  }
}

//: The facts about a note, as **one muted line**.
//:
//: This was five chips (category, date, links, views, confidence) plus up to
//: six tag chips, every one of them the same weight, so the panel opened with
//: eleven equal marks above the note it was about, and the provenance ones
//: (confidence, views) shouted as loudly as the category. Reported with a
//: screenshot, INBOX 59.
//:
//: Category and confidence moved into the header where identity belongs; the
//: tags were already in the tags field two rows down, spelled a second way.
//: What is left is the three facts that are genuinely the same rank: when it
//: was made, how connected it is, how often it has been read. A `·`-joined
//: muted line says "the same kind of small fact" in a way five bordered chips
//: cannot.
//: A note (or a document's node) found and framed on the map: the half of
//: `showNoteInGraph` (note-cards.js) that runs once the bundle is here.
async function graphShowNote(id, { document: isDocument = false } = {}) {
  if (isDocument) {
    const box = $("graph-documents");
    if (box && !box.checked) {
      box.checked = true;
      box.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  const nodeId = isDocument ? `document:${id}` : id;
  const deadline = Date.now() + 4000;
  let node = null;
  while (Date.now() < deadline) {
    node = graphNodeById(nodeId);
    if (node && Number.isFinite(node.x)) break;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  if (!node || !Number.isFinite(node.x)) {
    toast(`That ${isDocument ? "document" : "note"} is not on the graph right now: a filter or the view may be hiding it.`, "info");
    return;
  }
  focusGraphNode(node);
  if (typeof graphSvg !== "undefined" && graphSvg && typeof graphZoom !== "undefined" && graphZoom) {
    graphSvg.transition().duration(graphGlideMs(400)).call(graphZoom.translateTo, node.x, node.y);
  }
}

//: **A note's topic, in its panel** (the owner, 2026-10-10: "I still cant
//: edit topics in the graph or anywhere else"). The chip opens the topic on
//: the map; the pencil renames it in place (`gcRenameTopicInline`). Read from
//: the map's own topics under the Topic colour rule, else asked for
//: (`/graph/topics/of`, which a rename keeps current).
async function renderGraphPopupTopic(entry) {
  const box = $("graph-popup-topic");
  if (!box) return;
  box.classList.add("hidden");
  box.replaceChildren();
  let topic = null;
  const mapped = graphStructure?.topics && graphStructure.topic_of?.[String(entry.id)];
  if (mapped !== undefined && mapped !== null && graphStructure?.topics) {
    topic = graphStructure.topics.find((t) => t.id === mapped) || null;
  } else {
    const row = await apiJson(`/graph/topics/of?ids=${entry.id}&members=1`, { silent: true }).catch(() => null);
    topic = row?.topics?.[String(entry.id)] || null;
  }
  if (!topic || graphPopupId !== entry.id) return;
  const mark = chip(`ph:circles-three ${topic.name}`, "topic", () => showTopicInGraph(entry.id));
  mark.title = `In the topic ${topic.name}, ${nounCount(topic.size, "note")}. Show it on the map`;
  //: `members=1` above: a rename is stored by the topic's notes.
  const rename = smallButton("ph:pencil-simple", "Rename the topic", () => gcRenameTopicInline(topic, mark, rename));
  rename.classList.add("icon-only");
  box.append(mark, rename);
  box.classList.remove("hidden");
}

//: The map's topic for a note, the Topic colour rule switched on to find it
//: (topics are only read under it). Null after five seconds without one.
async function graphTopicFor(entryId) {
  const colour = $("graph-colour");
  if (colour && colour.value !== "topic") {
    colour.value = "topic";
    colour.dispatchEvent(new Event("change", { bubbles: true }));
  }
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    const id = graphStructure?.topic_of?.[String(entryId)];
    const topic = id === undefined ? null : graphStructure.topics?.find((t) => t.id === id);
    if (topic && gcTab.nodes.some((node) => Number.isFinite(node.x)) && gcTab.alpha < 0.3) return topic;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return null;
}

//: A note's topic on the map: the Graph tab under the Topic colour rule, the
//: topic's notes lit, its card open, and the camera on its notes (a note
//: card's topic chip, `noteTopicChip`, and the panel's).
async function showTopicInGraph(entryId) {
  await switchTab("graph");
  const topic = await graphTopicFor(entryId);
  if (!topic) {
    toast("That note's topic is not on the graph right now: a filter or the view may be hiding it.", "info");
    return;
  }
  closeGraphPopup();
  gcOpenTopic(topic);
  const members = gcTopicMembers(topic);
  if (members.length) fitGraphToView(gcTab.svg, gcTab.zoom, members, gcTab.dims.w, gcTab.dims.h);
}

//: **A note's properties, in its panel** (the owner, 2026-10-10: "is it
//: possible to add and customise the metadata a little more??"). The
//: `---` fields the card shows, each value a press that lights the notes on
//: the map sharing it (`/entries/query`, the Notes filter's own question), and
//: Properties to add or change them (the note's ⋯ has the same sheet).
function renderGraphPopupProps(entry) {
  const box = $("graph-popup-props");
  if (!box) return;
  const table = document.createElement("dl");
  table.className = "note-props";
  for (const [key, values] of Object.entries(entry.properties || {}).slice(0, 8)) {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    for (const value of (values || []).filter(Boolean)) {
      const shown = String(value).replace(/^\[\[|\]\]$/g, "");
      const light = chip(shown, "refs", async () => {
        const row = await apiJson(`/entries/query?q=${encodeURIComponent(propQuery(key, shown))}`, { silent: true }).catch(() => null);
        if (!row) return;
        graphHighlightIds = new Set(row.ids || []);
        applyGraphHighlight();
        toast(`${nounCount(graphHighlightIds.size, "note")} with ${key} ${shown}, lit on the map.`, "info");
      });
      light.title = `Light the notes whose ${key} is ${shown}`;
      dd.append(light, " ");
    }
    if (!dd.firstChild) dd.textContent = "–";
    table.append(dt, dd);
  }
  //: **A section, not a stray button** (INBOX 1300 C27, the owner: "the ui
  //: structure and formatting and placement of this properties button ...
  //: needs to be fixed"). It was a lone ghost "Properties" between the topic
  //: chip and the text field, 0px off the field and its icon past the text
  //: edge, so it read as the text's heading. Now a small-caps head with the
  //: count, its one action at the row's end (Add when there are none, Edit
  //: when there are), then the table.
  const count = table.childElementCount / 2;
  const head = document.createElement("div");
  head.className = "graph-popup-props-head";
  const label = document.createElement("span");
  label.className = "graph-popup-props-label";
  label.textContent = count ? `Properties · ${count}` : "Properties";
  const edit = smallButton(
    count ? "ph:pencil-simple Edit" : "ph:plus Add",
    "Add or change this note's properties (status, due, a type's fields), kept in its text",
    () => openNotePropertiesSheet(entry)
  );
  edit.setAttribute("aria-label", count ? "Edit this note's properties" : "Add properties to this note");
  head.append(label, edit);
  box.replaceChildren(head, ...(count ? [table] : []));
}

function renderGraphPopupInfo(entry) {
  const box = $("graph-popup-info");
  const links = (entry.links || []).length;
  const views = entry.access_count || 0;
  const parts = [
    new Date(entry.created_at).toLocaleDateString(),
    nounCount(links, "link"),
    nounCount(views, "view"),
  ];
  //: When a person last changed it (INBOX 1300 C11, "see their values and
  //: dates"), as the hover card says it: `edited_at`, which the app's own
  //: writes do not move.
  if (entry.edited_at) parts.splice(1, 0, `Edited ${relativeTime(entry.edited_at)}`);
  //: **Star and "Favourite", not pin and "Pinned".** `entry.pinned` is one
  //: flag with one meaning, it floats a note to the top *and* collects it
  //: into the sidebar's Favourites row: and app.js's own note cards were
  //: renamed to say so. The graph and the dashboard were not, so the same
  //: flag had two names and two icons depending on which screen you were
  //: looking at. Found while fixing the star button's missing glyph. The
  //: toolbar's star now carries the state, so this line only says it for the
  //: reader who is scanning the text rather than the icons.
  if (entry.pinned) parts.push("Favourite");
  box.textContent = parts.join(" · ");
}

// Everything you can do to this note from the map, as one toolbar row.
//
//: **Nine equal buttons in a 3x3 grid is a menu, not a toolbar.** Reported
//: with a screenshot (INBOX 59): Favourite, Grow, Focus, Similar, Link,
//: Trace, Remind, Open, Bin, all the same width, the same weight and the
//: same distance apart, so the one you almost always want (Open) took as
//: long to find as the one you almost never do (Bin), and the block was
//: taller than the note's own text.
//:
//: The grid is now one row of icon buttons in three groups, each group a
//: verb class, separated by a hairline rather than by a heading:
//:
//: - **read** (Open, Similar, Trace): go somewhere, change nothing.
//: - **shape** (Grow, Focus, Link, Remind): change the map or the note's
//:   place in it.
//: - **keep** (Favourite, then Bin after a gap): the note's own fate.
//:
//: Open is the single filled control, the DESIGN.md button ramp's "the one
//: action this surface is for" (test_dock_grammar's one-primary rule is
//: about docks; this panel follows the same rule by hand). Every other
//: button is tonal, and Bin is last, set apart, so the destructive one is
//: never the neighbour of the one you meant.
//:
//: The labels live in `title`/`aria-label` only. That is a real trade: the
//: previous pass added words to these cells *because* an unlabelled star
//: beside eight labelled buttons read as a failed render. In a row of nine
//: icons with no words anywhere, nothing is the odd one out, and the state
//: the words carried (Favourite vs Favourited, Trace vs Trace to) is in the
//: tooltip and in `aria-pressed`.
//: **On a phone the same nine actions are two words and a menu.** Reported
//: (INBOX 883, 884): "the buttons at the bottom of a note popup panel ...
//: all wrap onto like 3 different rows when on phone", and "i have no clue
//: what the buttons do as I cant hover over them and see a tooltip". Nine
//: bare icons are readable with a pointer (the tooltip says what each is) and
//: unreadable under a finger. Below 600, or on any device that cannot hover,
//: the row is Open and Link as labelled buttons (the note's two most-used
//: moves, the words in the button) and a ⋯ (`kebabMenu`) holding the rest as
//: labelled rows, so every action has a visible name and the strip is one
//: line. The list of actions is built once (`graphPopupActionList`) and drawn
//: either way, so the two shapes cannot disagree about what a note can do.
const GRAPH_POPUP_COMPACT = "(max-width: 599.98px), (hover: none)";

function graphPopupActionList(entry) {
  const tracingFrom = Boolean(traceFromNode);
  const list = [
    {
      key: "open",
      group: "read",
      icon: "note-pencil",
      word: "Open",
      title: "Open this note in the Notes tab",
      primary: true,
      run: () => {
        const id = entry.id;
        closeGraphPopup();
        flashEntry(id);
      },
    },
    {
      key: "similar",
      group: "read",
      icon: "approximate-equals",
      word: "Similar notes",
      title: "Highlight notes that mean something similar",
      run: async () => {
        const related = await apiJson(`/entries/${entry.id}/related`).catch(() => []);
        if (!related.length) {
          toast("No similar notes found.");
          return;
        }
        // Reuse the existing highlight pass by searching for these ids.
        graphHighlightIds = new Set(related.map((r) => r.id).concat(entry.id));
        applyGraphHighlight();
        closeGraphPopup();
        toast(`Highlighted ${related.length} similar note${related.length === 1 ? "" : "s"}.`);
      },
    },
    // Two clicks, the same shape as Link: this note becomes one end of the
    // trace, and the next one you pick becomes the other. The tooltip says
    // which end it will be, because a button that does two different things
    // without saying which is a button you have to try to understand.
    {
      key: "trace",
      group: "read",
      icon: "path",
      word: tracingFrom ? "Trace to here" : "Trace from here",
      title: tracingFrom
        ? "Trace to here: find how this note connects to the one you started from"
        : "Trace from here: start tracing a path from this note",
      run: () => {
        closeGraphPopup();
        setTraceEnd(tracingFrom ? "to" : "from", entry.id);
        if (!tracingFrom) toast("Now pick the other note, use Trace to here.");
      },
    },
    {
      key: "grow",
      group: "shape",
      icon: "plant",
      word: "Grow a linked note",
      title: "Grow: add a new note linked to this one",
      run: (event) => openGraphNewNote(event, entry.id),
    },
  ];
  if (graphFocusModeId !== entry.id) {
    list.push({
      key: "focus",
      group: "shape",
      icon: "target",
      word: "Focus on this note",
      short: "Focus",
      title: "Focus: show only this note and its neighbours",
      run: () => {
        graphFocusModeId = entry.id;
        recordTabVisit("graph", `focus:${entry.id}`);
        $("graph-focus-clear")?.classList.remove("hidden");
        closeGraphPopup();
        renderGraph();
        toast("Focus Mode active. Showing local neighborhood.");
      },
    });
  }
  //: Pin from the panel (INBOX 1400): the same toggle as a double-click on
  //: the dot (`gcTogglePin`), offered only while the note is on the drawn map.
  const mapNode = typeof gcTab !== "undefined" && gcTab.byId ? gcTab.byId.get(entry.id) : null;
  if (mapNode && !gcTab.tree) {
    const pinned = mapNode.fx != null;
    list.push({
      key: "pin",
      group: "shape",
      icon: pinned ? "push-pin-slash" : "push-pin",
      word: pinned ? "Unpin" : "Pin in place",
      short: pinned ? "Unpin" : "Pin",
      title: pinned ? "Let this note move with the map again" : "Hold this note where it is (double-click a dot does the same)",
      pressed: pinned,
      run: () => {
        gcTogglePin(mapNode);
        renderGraphPopupActions(entry);
      },
    });
  }
  list.push(
    {
      key: "link",
      group: "shape",
      icon: "link",
      word: "Link",
      title: "Link: start linking this note to another",
      run: () => {
        closeGraphPopup();
        beginOrCompleteLink(entry);
        toast("Now click another note on the map to link them.");
      },
    },
    {
      key: "remind",
      group: "shape",
      icon: "alarm",
      word: "Remind me",
      title: "Remind me about this note",
      run: () => {
        closeGraphPopup();
        switchTab("reminders");
        $("reminder-text").value = `Follow up: ${stripFrontmatter(entry.content).trim().slice(0, 60)}`;
        setDue(defaultDueValue()); // keeps the visible date/time fields in step
        $("reminder-text").focus();
      },
    },
    {
      key: "favourite",
      group: "keep",
      icon: "star",
      word: entry.pinned ? "Remove from Favourites" : "Add to Favourites",
      title: entry.pinned ? "Remove from Favourites" : "Add to Favourites",
      pressed: Boolean(entry.pinned),
      run: async () => {
        const was = Boolean(entry.pinned);
        const flipped = await apiJson(`/entries/${entry.id}`, {
          method: "PUT",
          body: JSON.stringify({ pinned: !was }),
        }).catch((e) => toast(e.message, true));
        if (flipped) pushEntryPutUndo(entry.id, was ? "Removed from Favourites" : "Added to Favourites", { pinned: was }, { pinned: !was });
        toast(entry.pinned ? "Removed from Favourites." : "Added to Favourites.");
        closeGraphPopup();
        await loadEntries().catch(() => {});
        renderGraph();
      },
    },
    {
      key: "bin",
      group: "keep",
      icon: "trash",
      word: "Move to the bin",
      title: "Move this note to the bin",
      danger: true,
      run: async () => {
        if (!(await confirmDialog("Move this note to the bin?"))) return;
        closeGraphPopup();
        try {
          await binNoteWithUndo(entry);
        } catch (e) {
          toast(e.message, true);
        }
        renderGraph();
      },
    }
  );
  return list;
}

let graphPopupActionsEntry = null; // the note the row was last drawn for

function renderGraphPopupActions(entry) {
  graphPopupActionsEntry = entry;
  const box = $("graph-popup-actions");
  box.replaceChildren();
  const list = graphPopupActionList(entry);
  const compact = window.matchMedia(GRAPH_POPUP_COMPACT).matches;
  box.classList.toggle("is-compact", compact);
  //: **Every action has a visible name, at every width** (INBOX 1400, the
  //: owner: "the popup panels could be improved", "access to the tools ...
  //: aren't really easy to understand"). The desktop row was nine bare icons
  //: in three groups, readable only by hovering each for its tooltip
  //: (`gp.js`: 11 of 12 buttons icon-only). Now the four moves a map is for
  //: are words, Open filled, then Focus, Pin and Link, and the ⋯
  //: (`kebabMenu`) holds the rest as labelled rows in their read, shape and
  //: keep groups; on a phone the words are Open and Link, the rest the ⋯,
  //: the shape INBOX 883 gave it.
  const shown = compact ? ["open", "link"] : ["open", "focus", "pin", "link"];
  const row = document.createElement("div");
  row.className = "graph-popup-tool-group graph-popup-tool-shown";
  for (const key of shown) {
    const a = list.find((x) => x.key === key);
    if (!a) continue;
    const b = smallButton(`ph:${a.icon} ${a.short || a.word}`, a.title, (event) => a.run(event), !a.primary);
    b.dataset.action = a.key;
    if (a.primary) b.classList.add("graph-popup-tool-primary");
    if (a.pressed != null) b.setAttribute("aria-pressed", String(a.pressed));
    row.appendChild(b);
  }
  const rest = list.filter((x) => !shown.includes(x.key));
  row.appendChild(
    kebabMenu(
      rest.map((a) => ({
        label: `ph:${a.icon} ${a.word}`,
        title: a.title,
        run: () => a.run(null),
        danger: a.danger,
        group: a.group,
      })),
      "More note actions"
    )
  );
  box.appendChild(row);
}

//: A rotation or a window resize can cross the compact line with a panel
//: open; redraw the row so it is never the wrong shape for the width.
try {
  window.matchMedia(GRAPH_POPUP_COMPACT).addEventListener("change", () => {
    const open = graphPopupId !== null && !$("graph-popup").classList.contains("hidden");
    if (open && graphPopupActionsEntry) renderGraphPopupActions(graphPopupActionsEntry);
  });
} catch (e) {
  /* matchMedia is absent in some test shells; the row is drawn on open. */
}

//: The keyboard stays on the map: Esc, or Close from inside the popup, used to leave focus on <body> (audit 1029 G19).
function closeGraphPopup(returnFocus = false) {
  keepGraphPopupEdit();
  const held = returnFocus || $("graph-popup").contains(document.activeElement);
  graphPopupId = null;
  graphLate.popupDragged = false;
  if (typeof gcTab !== "undefined" && gcTab.canvas) gcRequestDraw(gcTab);
  $("graph-popup").classList.add("hidden");
  $("graph-popup").classList.remove("graph-popup-away");
  clearGraphKeyboardFocus();
  if (held) $("graph-box")?.focus({ preventScroll: true });
}

//: **Keyboard focus ends when the keyboard leaves.** `focusGraphNode` is
//: reached only by the arrow and Tab navigation, and nothing ever unset
//: it: after one keyboard step the note kept its ring and its label for the
//: rest of the visit, including with Labels off (the owner, 2026-09-14:
//: "there's still a note label showing even when I have them off??"). The
//: focus clears when the map loses keyboard focus, when a pointer takes
//: over on the canvas, and when the popup closes.
function clearGraphKeyboardFocus() {
  if (graphKeyboardId === null && graphHoveredId === null) return;
  const wasHovered = graphHoveredId === graphKeyboardId;
  graphKeyboardId = null;
  if (wasHovered) graphHoveredId = null;
  applyGraphHighlight();
  gcRequestDraw();
}
$("graph-box")?.addEventListener("focusout", (event) => {
  if (!$("graph-box").contains(event.relatedTarget)) clearGraphKeyboardFocus();
});
$("graph-box")?.addEventListener("pointerdown", () => {
  if (graphKeyboardId !== null) clearGraphKeyboardFocus();
});

//: **One guard for every way out of the popup** (audit G2: Escape, the X, a
//: click on the map and a click on another note all dropped unsaved typing).
//: `closeGraphPopup` and `openGraphPopup` (another note) both call this first.
//: A dirty popup is saved on the way out, as the document editor autosaves, and
//: Ctrl+Z undoes it (`pushEntryPutUndo`); a save that fails hands the text back
//: on the clipboard instead of dropping it.
function graphPopupIsDirty() {
  if (graphPopupId === null || $("graph-popup").classList.contains("hidden")) return false;
  if (graphPopupClean.content === "Loading…") return false;
  return (
    $("graph-popup-content").value !== graphPopupClean.content || $("graph-popup-tags").value !== graphPopupClean.tags
  );
}

function keepGraphPopupEdit() {
  if (!graphPopupIsDirty()) return;
  saveGraphPopup({ leaving: true });
}

async function saveGraphPopup({ leaving = false } = {}) {
  if (graphPopupId === null) return;
  const id = graphPopupId;
  const status = $("graph-popup-status");
  const content = $("graph-popup-content").value;
  const tagsText = $("graph-popup-tags").value;
  const was = graphPopupClean;
  const tags = tagsText
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  status.classList.remove("error");
  status.textContent = "Saving…";
  try {
    const wasTags = String(was.tags || "").split(",").map((t) => t.trim()).filter(Boolean);
    const saved = await apiJson(`/entries/${id}`, {
      method: "PUT",
      body: JSON.stringify({ content, tags }),
    });
    pushEntryPutUndo(id, "Edited a note on the map", { content: was.content, tags: wasTags }, { content, tags });
    if (typeof offerWikiRename === "function") offerWikiRename(id, saved);
    if (leaving) toast("Saved your edit to the note.");
    //: The popup may have moved on to another note while the request ran.
    if (graphPopupId === id) {
      status.textContent = "Saved.";
      //: What was just written is the new clean state, so the button puts
      //: itself away for the 600ms the panel is still open.
      graphPopupClean = { content, tags: tagsText };
      syncGraphPopupSave();
    }
    await loadEntries().catch(() => {});
    renderGraph(); // content/tags may change what the map shows
    if (!leaving) {
      setTimeout(() => {
        if (graphPopupId === id) closeGraphPopup();
      }, 600);
    }
  } catch (error) {
    if (leaving) {
      toastAction(`Couldn't save your edit: ${error.message}`, "Copy text", () => {
        navigator.clipboard?.writeText(content).catch(() => {});
      });
      return;
    }
    status.textContent = error.message;
    status.classList.add("error");
  }
}

// --- grow the map: add a note as a new node ----------------------------------
// The graph stops being read-only here, you can extend your notebook from the
// map itself, and a note grown from an existing one is linked to it, so the
// new node appears already connected.

let graphNewLinkFrom = null; // note id the new one should link to, if any

function openGraphNewNote(event, linkFrom = null) {
  closeGraphPopup();
  graphNewLinkFrom = linkFrom;
  const popup = $("graph-new");
  $("graph-new-content").value = "";
  $("graph-new-note-title").value = "";
  $("graph-new-tags").value = "";
  $("graph-new-status").textContent = "";
  $("graph-new-status").classList.remove("error");
  setLabel($("graph-new-title"), linkFrom ? "ph:plus Connected note" : "ph:plus New note");
  $("graph-new-hint").textContent = linkFrom
    ? "This note will be linked to the one you grew it from."
    : "It joins the map as soon as you add it.";
  popup.classList.remove("hidden");
  graphLate.newAt = event ? { x: event.clientX, y: event.clientY } : null;
  placeGraphNewNote();
  watchGraphPopupSize(popup, placeGraphNewNote);
  $("graph-new-content").focus();
}

//: Where New note was asked for, kept so a later size change (its fields
//: settling, the tag row) places it again from the same point: measured,
//: it grew 30px after opening and its foot went under the status bar.
function placeGraphNewNote() {
  const popup = $("graph-new");
  if (popup.classList.contains("hidden")) return;
  const { box, room } = graphPanelRoom();
  // Never taller than the room it has, beyond that the popup scrolls
  // itself rather than growing off the edge (same fix placeGraphPopup()
  // already has; this popup was missing it, so on a short viewport its
  // Save/Close/Tags controls rendered below the fold with nothing to
  // scroll them into view).
  popup.style.maxHeight = `${Math.max(120, room - 16)}px`;
  const size = popup.getBoundingClientRect();
  // Centre it when there's no click position (toolbar button).
  const rawX = graphLate.newAt ? graphLate.newAt.x - box.left + 12 : (box.width - size.width) / 2;
  const rawY = graphLate.newAt ? graphLate.newAt.y - box.top + 12 : 60;
  popup.style.left = `${Math.min(Math.max(rawX, 8), Math.max(8, box.width - size.width - 8))}px`;
  popup.style.top = `${Math.min(Math.max(rawY, 8), Math.max(8, room - size.height - 8))}px`;
}

function closeGraphNewNote() {
  graphNewLinkFrom = null;
  $("graph-new").classList.add("hidden");
}

async function saveGraphNewNote() {
  const content = withTitle($("graph-new-content").value.trim(), $("graph-new-note-title").value);
  const status = $("graph-new-status");
  if (!content) {
    status.textContent = "Type something first.";
    status.classList.add("error");
    return;
  }
  const tags = $("graph-new-tags")
    .value.split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  status.classList.remove("error");
  status.textContent = "Adding…";
  try {
    //: Filed in the background and `#tags` read from the text, as Capture's
    //: are (INBOX 434): the map draws the note at once, wherever it lands.
    const created = await apiJson("/entries", {
      method: "POST",
      body: JSON.stringify({ content, tags, defer_filing: true, inline_tags: true }),
    });
    if (created.filing_state === "pending") watchFiling(created);
    pushEntryCreateUndo(created, "Added a note to the map");
    if (graphNewLinkFrom !== null) {
      await apiJson(`/entries/${graphNewLinkFrom}/links`, {
        method: "POST",
        body: JSON.stringify({ target_id: created.id }),
      }).catch(() => {}); // the note still exists even if linking fails
    }
    closeGraphNewNote();
    toast(graphNewLinkFrom !== null ? "Added and linked." : "Added to the map.");
    await loadEntries().catch(() => {});
    await renderGraph();
    // Land the eye on the note that was just created.
    graphHighlightIds = new Set([created.id]);
    applyGraphHighlight();
    setTimeout(() => {
      graphHighlightIds = null;
      applyGraphHighlight();
    }, 2500);
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
  }
}

// --- export as PNG (ROADMAP.md gap 3) --------------------------------------

async function exportGraphPng() {
  // The canvas is exported as it is: no clone, no inlining of every computed
  // style (`canvas.toBlob`). The one thing it still has to do by hand is the
  // background, a transparent PNG over a dark page reads as "half my graph is
  // missing" the moment it is opened anywhere else, so the frame is repainted
  // onto an opaque copy.
  const liveCanvas = document.getElementById("graph-canvas");
  if (!liveCanvas || liveCanvas.classList.contains("hidden") || !graphNodesRef || !graphNodesRef.length) {
    toast("Nothing to export yet.", "info");
    return;
  }
  // GRAPH_PLAN Phase 4: exactly the visible frame, re-rendered at 2x with
  // the legend and a caption painted on (gcExportPng); the live bitmap is
  // the fallback if the renderer is not wired yet.
  const out =
    gcExportPng(2) ||
    (() => {
      const fallback = document.createElement("canvas");
      fallback.width = liveCanvas.width;
      fallback.height = liveCanvas.height;
      const ctx = fallback.getContext("2d");
      ctx.fillStyle = resolvedTheme() === "dark" ? "#12141c" : "#eef1f5";
      ctx.fillRect(0, 0, fallback.width, fallback.height);
      ctx.drawImage(liveCanvas, 0, 0);
      return fallback;
    })();
  try {
    const blob = await new Promise((resolve, reject) =>
      out.toBlob((result) => (result ? resolve(result) : reject(new Error("Couldn't export the graph."))), "image/png")
    );
    await saveFile("graph.png", blob);
    toast("Graph exported as PNG.");
  } catch (error) {
    toast(error.message || "Couldn't export the graph.", true);
  }
}

// --- minimap + saved views (ROADMAP §85.4 items 7) ---------------------------

//: The four corners the minimap can be pinned to, and where that choice lives.
//: Top-left is the default because it is the one corner nothing else claims, 
//: the toolbar owns the top strip, the agent monitor bottom-left, and the zoom
//: buttons bottom-right (which is what the old hard-coded position collided
//: with).
const GRAPH_MINIMAP_CORNERS = ["off", "tl", "tr", "bl", "br"];
const GRAPH_MINIMAP_CORNER_KEY = "graph-minimap-corner";
//: Per-device workspace state, beside the corner: see `applyMinimapSize`.
const GRAPH_MINIMAP_SIZE_KEY = "graph-minimap-size";
//
// Both exist for the same reason, named in the roadmap's own words: once a
// notebook is dense enough that the force layout stops being readable, there
// is "nothing to re-find a specific arrangement", no overview of where you
// are in the map, and no way to come back to a combination of filters that
// worked.

let graphMinimapProjection = null; // the last full paint's placement, reused by graphMinimapFrame
const GRAPH_MINIMAP_W = 168;
const GRAPH_MINIMAP_H = 112;

//: **The links, which the minimap did not draw at all** (INBOX 164: "the graph
//: minimap needs an upgrade"). Measured on a 172-note map: 172 dots, 0 edges.
//: A scatter of points says where the notes are; what makes one part of a graph
//: recognisable from another is what is joined to what, and that was the half
//: the overview left out. The note beside `graphMinimapPaint` saying the minimap
//: "has no edges" was a cost decision, and this is the cost: built once per
//: render rather than once per paint (a cooling layout paints every eighth
//: tick), drawn at a hard cap, and a line is two coordinates with no hit
//: testing, which is a different thing from the canvas's own edge pass.
const GRAPH_MINIMAP_MAX_EDGES = 600;
let graphMinimapPairs = null;
let graphMinimapPairsFrom = null; // the adjacency map those pairs were built from

//: Every link once, as `[aId, bId]`. `graphAdjacency` holds both directions, so
//: a naive walk draws every line twice, which at 600 lines of 0.5px is visibly
//: heavier ink for no more information. Keyed on the adjacency map's own
//: identity: `renderGraph` replaces it whenever the set of notes or links
//: changes, so this recomputes exactly then and never on a pan.
function graphMinimapEdgePairs() {
  if (graphMinimapPairsFrom === graphAdjacency && graphMinimapPairs) return graphMinimapPairs;
  const pairs = [];
  if (graphAdjacency) {
    for (const [from, neighbours] of graphAdjacency) {
      for (const to of neighbours) {
        //: One direction only, by a stable comparison rather than a `Set` of
        //: joined keys: String() because an id can arrive as a number from the
        //: API and as a string from a tree layout's own copies.
        if (String(from) < String(to)) pairs.push([from, to]);
      }
    }
  }
  graphMinimapPairs = pairs;
  graphMinimapPairsFrom = graphAdjacency;
  return pairs;
}

// Where the nodes are, scaled into the minimap box. Recomputed on every paint
// rather than cached: the force layout keeps moving until it cools, so a
// cached extent would be wrong for the first few seconds, which is exactly
// when someone is watching it settle.
//: **An overview of nothing is not an overview.** Reported with a screenshot
//: of the empty graph: *"the empty minimap goes behind the top bar and sits
//: right in the corner with no gap. the mini map probably shouldnt even
//: appear when the graph is empty."* Both halves are the same fact. The paint
//: below has always bailed out when there was nothing to plot, which left the
//: box itself on screen holding an empty rectangle, and measured
//: (`scratchpad/ui-sweeps/graphminimap.js`) the empty state lays the card out
//: differently enough that the box lands at y=73 against a dock ending at
//: y=132, so it is drawn under the top bar as well. A box with no dots has
//: nothing to say either way, so it goes.
//:
//: `hidden` rather than a new class, because that is what the corner setting
//: already toggles, and `applyMinimapPosition` re-adds it on the next paint:
//: the two cannot fight, since neither ever removes `hidden` for a graph that
//: has no nodes.
function graphMinimapShown(shown) {
  const box = document.getElementById("graph-minimap");
  //: Never over the person's own choice: "off" is a setting, and a graph
  //: filling up is not a reason to overrule it.
  if (!box || prefs.get(GRAPH_MINIMAP_CORNER_KEY, null) === "off") return;
  box.classList.toggle("hidden", !shown);
}

//: **At most one paint a frame, and none nobody can see** (INBOX 424b).
//: The layout's ticks ask for a repaint (every eighth one, and every one the
//: worker sends while a node is dragged), and each paint used to rebuild the
//: whole overview: measured at 4x CPU, a 40-move node drag on a 400-note,
//: 1,200-link graph spent 1.56s in `graphMinimapPaint`, most of it
//: `createElementNS`, `setAttribute` and `replaceChildren` for about 1,000
//: elements whose count had not changed. Now the ticks queue a paint, the
//: frame runs it once, the paint moves the existing dots and lines rather
//: than making new ones, and a minimap that is switched off, on a tab that is
//: not showing, or in a window that is hidden is not painted at all: it is
//: marked stale and painted when it can be seen again.
let graphMinimapQueued = 0;
let graphMinimapStale = false;

function graphMinimapCanShow() {
  if (document.hidden) return false;
  if (prefs.get(GRAPH_MINIMAP_CORNER_KEY, null) === "off") return false;
  const page = document.getElementById("tab-graph");
  return !page || !page.classList.contains("hidden");
}

function graphMinimapQueuePaint() {
  if (!graphMinimapCanShow()) {
    graphMinimapStale = true;
    return;
  }
  if (graphMinimapQueued) return;
  graphMinimapQueued = requestAnimationFrame(() => {
    graphMinimapQueued = 0;
    graphMinimapPaint();
  });
}

//: The other half of the skip above: a paint that was passed over while the
//: window was hidden happens when it comes back. (A tab switch back to Graph
//: renders the map, which paints the minimap in full.)
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && graphMinimapStale) graphMinimapQueuePaint();
});

//: Exactly `count` element children of `tag` in `group`, reusing the ones
//: already there: a layout tick moves the notes, it does not add or remove
//: any, so after the first paint this appends and removes nothing.
function graphMinimapChildren(group, count, tag, className) {
  const kids = group.children;
  while (kids.length > count) group.lastElementChild.remove();
  if (kids.length < count) {
    const fragment = document.createDocumentFragment();
    for (let i = kids.length; i < count; i++) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
      if (className) el.setAttribute("class", className);
      fragment.appendChild(el);
    }
    group.appendChild(fragment);
  }
  return kids;
}

//: One attribute, written only when it changed. The last value lives on the
//: element itself, so the check is a property read rather than a
//: `getAttribute`; a settled map redrawn for a drag of one note rewrites the
//: handful of dots that moved, not all of them.
function graphMinimapSet(el, name, value) {
  const key = `_mm_${name}`;
  if (el[key] === value) return;
  el[key] = value;
  el.setAttribute(name, value);
}

function graphMinimapPaint() {
  if (graphMinimapQueued) {
    cancelAnimationFrame(graphMinimapQueued);
    graphMinimapQueued = 0;
  }
  graphMinimapStale = false;
  const svg = document.getElementById("graph-minimap-svg");
  if (!svg || !graphNodesRef?.length) {
    graphMinimapShown(false);
    return;
  }
  const nodes = graphNodesRef.filter((n) => Number.isFinite(n.x) && Number.isFinite(n.y));
  if (!nodes.length) {
    graphMinimapShown(false);
    return;
  }
  graphMinimapShown(true);

  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  // A single node, or a perfectly straight line of them, gives a zero-width
  // extent and a division by zero further down.
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  const pad = 6;
  const scale = Math.min(
    (GRAPH_MINIMAP_W - pad * 2) / spanX,
    (GRAPH_MINIMAP_H - pad * 2) / spanY
  );
  const toMini = (x, y) => [
    pad + (x - minX) * scale + (GRAPH_MINIMAP_W - pad * 2 - spanX * scale) / 2,
    pad + (y - minY) * scale + (GRAPH_MINIMAP_H - pad * 2 - spanY * scale) / 2,
  ];

  const dots = document.getElementById("graph-minimap-dots");
  const frame = document.getElementById("graph-minimap-frame");
  if (!dots || !frame) return;

  //: **The links, under the dots.** Strided for the same reason the dots are,
  //: and with the same kind of stride: evenly, so a dense notebook draws the
  //: whole shape faintly rather than one corner of it solidly. A line whose
  //: other end is not in this render (a filtered-out note) is skipped rather
  //: than drawn to the origin, which is the obvious way for this to produce a
  //: starburst out of the top-left corner.
  const edgesGroup = document.getElementById("graph-minimap-edges");
  if (edgesGroup) {
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const pairs = graphMinimapEdgePairs();
    const edgeStride = Math.max(1, Math.ceil(pairs.length / GRAPH_MINIMAP_MAX_EDGES));
    const ends = [];
    for (let i = 0; i < pairs.length; i += edgeStride) {
      const from = byId.get(pairs[i][0]);
      const to = byId.get(pairs[i][1]);
      if (from && to) ends.push(from, to);
    }
    const lines = graphMinimapChildren(edgesGroup, ends.length / 2, "line", "graph-minimap-edge");
    for (let i = 0; i < lines.length; i++) {
      const [ax, ay] = toMini(ends[i * 2].x, ends[i * 2].y);
      const [bx, by] = toMini(ends[i * 2 + 1].x, ends[i * 2 + 1].y);
      const line = lines[i];
      graphMinimapSet(line, "x1", ax.toFixed(1));
      graphMinimapSet(line, "y1", ay.toFixed(1));
      graphMinimapSet(line, "x2", bx.toFixed(1));
      graphMinimapSet(line, "y2", by.toFixed(1));
    }
  }

  // One <circle> per node, over the lines above. Deliberately not reusing the
  // main render path: the minimap has no labels, no arrowheads, no halos and no
  // hit-testing, so a flat SVG of lines and dots is both cheaper and clearer
  // than a scaled clone of a canvas that is already too dense to read, which is
  // the problem this is here to solve, not to reproduce in miniature. The edges
  // came back because the *shape* of a graph is its links (INBOX 164); the rest
  // of that list stays out.
  //: **One dot per note stops being one dot per note past a few hundred.**
  //: The box is 168x112 with a 1.6px dot: about 700 dots is the point at which
  //: another one lands on top of an existing one and adds nothing but a DOM
  //: element. Measured on the 2,000-note fixture, rebuilding all 2,000
  //: `<circle>`s while a drag was in flight was a real, repeated main-thread
  //: cost for a picture that looked identical, so a big notebook is sampled
  //: at an even stride instead. Evenly, not randomly or by prefix: a
  //: contiguous slice would draw one corner of the map and leave the rest
  //: blank, and a random sample would shimmer between repaints.
  const MINIMAP_MAX_DOTS = 700;
  const stride = Math.max(1, Math.ceil(nodes.length / MINIMAP_MAX_DOTS));
  const circles = graphMinimapChildren(dots, Math.ceil(nodes.length / stride), "circle", null);
  for (let i = 0, c = 0; i < nodes.length; i += stride, c++) {
    const node = nodes[i];
    const [mx, my] = toMini(node.x, node.y);
    const dot = circles[c];
    graphMinimapSet(dot, "cx", mx.toFixed(1));
    graphMinimapSet(dot, "cy", my.toFixed(1));
    graphMinimapSet(dot, "r", "1.6");
    graphMinimapSet(dot, "fill", node.colour || "currentColor");
  }

  //: **Where you are, and not only what you can see.** The viewport rectangle
  //: answers "which part of the map is on screen"; it cannot answer "where is
  //: the note I am reading", which on a 172-dot cloud is the question someone
  //: opens an overview to ask. A ring around the note that is selected, or the
  //: one the keyboard is on: the two ways a note becomes "the one in hand", and
  //: both of them already have state this can read rather than a new one to
  //: keep in step. Drawn after the dots so the ring is not buried under one.
  const here = document.getElementById("graph-minimap-here");
  if (here) {
    const marked = new Set();
    if (typeof gcSelected !== "undefined" && gcSelected) {
      for (const id of gcSelected) marked.add(id);
    }
    if (graphKeyboardId != null) marked.add(graphKeyboardId);
    const rings = document.createDocumentFragment();
    //: A cap, because a lasso can select hundreds and a hundred rings is a
    //: second, brighter dot cloud over the first. Past a handful the selection
    //: is the shape of the map rather than a place in it.
    let drawn = 0;
    //: Nothing in hand is the common case on every tick: no walk, and no
    //: `replaceChildren` of an empty group with an empty fragment.
    for (const node of marked.size ? nodes : []) {
      if (!marked.has(node.id) || drawn >= 12) continue;
      const [mx, my] = toMini(node.x, node.y);
      const ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      ring.setAttribute("class", "graph-minimap-here");
      ring.setAttribute("cx", mx.toFixed(1));
      ring.setAttribute("cy", my.toFixed(1));
      ring.setAttribute("r", "3.4");
      rings.appendChild(ring);
      drawn += 1;
    }
    if (drawn || here.firstChild) here.replaceChildren(rings);
  }

  // Clicking the minimap centres the map on that point. Stored on the element
  // so the handler (wired once, below) can invert the projection without
  // recomputing the extent it was painted with.
  svg._toCanvas = (mx, my) => [
    minX + (mx - pad - (GRAPH_MINIMAP_W - pad * 2 - spanX * scale) / 2) / scale,
    minY + (my - pad - (GRAPH_MINIMAP_H - pad * 2 - spanY * scale) / 2) / scale,
  ];
  //: Kept so a pan can move the rectangle without repainting the dots: the
  //: projection is a property of where the *notes* are, and a pan does not
  //: move a note. See `graphMinimapFrame`.
  graphMinimapProjection = { toMini, frame };
  graphMinimapFrame();
}

//: **Every camera move glides on the motion token** (Brief 100 (d), INBOX
//: 802: reset and recentre ease the view). The moves had seven durations of
//: their own, 150 to 700ms, and only the fit asked about reduced motion, and
//: only the system's: the zoom buttons, the arrow keys and Locate glided
//: with the app's own Reduce motion on. Each keeps its length relative to the
//: others, scaled by `--ui-slow` (0.2s, `gcTokens.hoverMs`), and is 0 when
//: either setting asks for less motion or the token is off.
function graphGlideMs(base) {
  if (typeof gcStill === "function" && gcStill()) return 0;
  const token = typeof gcTokens !== "undefined" && gcTokens.hoverMs != null ? gcTokens.hoverMs : 200;
  return Math.round((base * token) / 200);
}

//: Every number that reaches an SVG attribute goes through here first. Named
//: rather than inlined because it is checked in three places in this file and
//: the shape of the bug it prevents (one NaN, four broken attributes, a
//: console full of parse errors and a rectangle that vanishes) is the same
//: every time.
function graphMinimapFinite(...values) {
  return values.every((value) => Number.isFinite(value));
}

//: **The viewport rectangle alone, for a pan.**
//:
//: Which part of the map is on screen is the only thing a pan or a zoom
//: changes about the minimap: the dots are where the notes are, and a pan
//: does not move a note. Repainting the whole minimap on every pointer event
//: of a pan was measured at four passes over every node, three document
//: lookups and up to 700 fresh `<circle>` elements per event, for a picture
//: identical to the one already on screen apart from this rectangle. The full
//: paint still runs where the positions really did change: the simulation's
//: ticks, a relayout, a saved view.
function graphMinimapFrame() {
  if (!graphMinimapProjection) {
    graphMinimapPaint();
    return;
  }
  const { toMini, frame } = graphMinimapProjection;
  if (!frame.isConnected) {
    graphMinimapProjection = null;
    graphMinimapPaint();
    return;
  }
  const transform = graphSvg ? d3.zoomTransform(graphSvg.node()) : null;
  //: **The guard checks what it reads, all of it.** It used to check
  //: `graphDims.w` and stop there, which left `graphDims.h` and the whole
  //: transform unchecked. Measured, intermittently, on a four thousand note
  //: notebook: 112 console errors in one sweep, `<rect> attribute x: Expected
  //: length, "NaN"` and the same for y, width and height, twenty-eight times
  //: over. Captured at the moment of the write, `graphDims` was 800x540 and
  //: every node position was finite; `d3.zoomTransform` itself held NaN in
  //: `k`, `x` and `y`, and `invert` on a NaN transform is NaN, which lands in
  //: four attributes at once. d3 stores whatever transform it is handed and
  //: has no opinion about NaN, so a reader has to have one.
  //:
  //: `fitGraphToView` below refuses to *build* such a transform now, which is
  //: the producer this app controls. This is the reader's half, and it is
  //: worth keeping separately: the browser's own zoom gestures write the
  //: transform too, and a rectangle left where it was beats four attributes
  //: the SVG cannot parse.
  if (!transform || !graphMinimapFinite(transform.k, transform.x, transform.y)) return;
  if (!graphMinimapFinite(graphDims.w, graphDims.h) || !graphDims.w) return;
  const [x0, y0] = transform.invert([0, 0]);
  const [x1, y1] = transform.invert([graphDims.w, graphDims.h]);
  const [fx0, fy0] = toMini(x0, y0);
  const [fx1, fy1] = toMini(x1, y1);
  // Clamped to the minimap's own box. Zoomed far enough out, the viewport is
  // wider than every node in the map, so the raw rectangle runs past the edge
  //, measured at 201x39 inside a 168x112 box. The SVG would clip it anyway,
  // but a rectangle with two edges off-screen reads as "the frame is broken"
  // rather than "you are looking at all of it"; clamped, it sits flush with
  // the border and says the second thing.
  const clampedX0 = Math.max(0, Math.min(fx0, fx1));
  const clampedY0 = Math.max(0, Math.min(fy0, fy1));
  const clampedX1 = Math.min(GRAPH_MINIMAP_W, Math.max(fx0, fx1));
  const clampedY1 = Math.min(GRAPH_MINIMAP_H, Math.max(fy0, fy1));
  const frameW = Math.max(0, clampedX1 - clampedX0);
  const frameH = Math.max(0, clampedY1 - clampedY0);
  //: Last line of defence, and cheap: `toMini` is a closure over a previous
  //: paint's extent, so the four numbers above can go non-finite for a reason
  //: neither guard above can see. Leaving the rectangle where it was is
  //: always better than writing "NaN" into an attribute.
  if (!graphMinimapFinite(clampedX0, clampedY0, frameW, frameH)) return;
  frame.setAttribute("x", clampedX0.toFixed(1));
  frame.setAttribute("y", clampedY0.toFixed(1));
  frame.setAttribute("width", frameW.toFixed(1));
  frame.setAttribute("height", frameH.toFixed(1));
  //: **An overview of what you can already see is not an overview** (GRAPH_PLAN
  //: Phase 6b, INBOX 78: the minimap's "UX and utility"). Zoomed out far enough
  //: that every note is on screen, the rectangle is the whole box and the map
  //: says nothing at all, while still taking a corner of the canvas and a
  //: click. It fades out there and comes back the moment you zoom in.
  //:
  //: The test is the rectangle's own area against the box, not the transform's
  //: scale: "everything fits" is a fact about this graph's extent at this
  //: window size, and a scale threshold would be wrong on the next notebook.
  //: 0.985 rather than 1 because the clamps above land a hair inside the box.
  const box = document.getElementById("graph-minimap");
  if (box) {
    const covered = frameW * frameH >= GRAPH_MINIMAP_W * GRAPH_MINIMAP_H * 0.985;
    box.classList.toggle("graph-minimap-redundant", covered);
  }
}

// --- the dock's real height, in the token everything clears it by ------------
//
// `--graph-dock-h` (02-chat-graph.css) is a calc of one row of controls, and
// the dock is not one row at every width: measured at a 700px viewport it
// wraps to 111px while the token still read 51px. Everything that clears the
// dock reads that token, so at that width the minimap's top corners sat 60px
// too high, underneath the dock they exist to stay clear of, and the options
// panel was capped against a top that did not exist.
//
// The same answer, for the same reason, as `initHeaderHeightToken` in phone-shell.js:
// a ResizeObserver writes the measured height back into the token everything
// already reads, so nothing gains a second property to learn. Through the
// CSSOM rather than a `style=` attribute, which this app's CSP refuses. No
// feedback loop is possible: the dock's height comes from its own content and
// nothing inside it is sized from this token.
function initGraphDockHeightToken() {
  const card = document.getElementById("graph-card");
  const dock = card?.querySelector('.dock[data-dock-name="graph"]');
  if (!card || !dock || typeof ResizeObserver === "undefined") return;
  if (dock._heightWired) return;
  dock._heightWired = true;
  const write = (e) => {
    //: The entry has the box; a rect read forced a style pass on tab flips.
    //: One observer serves the rail too (`initGraphRailToken`): its strips'
    //: entries come here, and only the dock's own entry sizes this token.
    card._railWrite?.();
    const own = e ? e.find((x) => x.target === dock) : null;
    if (e && !own) return;
    const h = Math.round(own ? own.borderBoxSize[0].blockSize : dock.getBoundingClientRect().height);
    // Zero while the tab is not on screen (the card is display:none until
    // then), and a zero here would stack the minimap and the selection bar
    // on top of the dock at the next paint. The stylesheet's own calc stands
    // until there is a real measurement to replace it with.
    if (h > 0) card.style.setProperty("--graph-dock-h", `${h}px`);
  };
  card._chromeWatch = new ResizeObserver(write);
  //: No direct `write()` here: observing delivers the first entry before the first paint, and a
  //: read at parse time forced a layout (11ms on 2,000 notes) for a number the entry carries.
  card._chromeWatch.observe(dock);
}

//: **The rail the map's furniture hangs from** (audit 1029 G24, 1306 residue).
//: The Trace strip and its result sit in the overlay column, full width, under
//: the dock; the minimap's top corners were placed from the dock alone and sat
//: under them (8,861 px² of overlap at 1440x900). The offset is how far the
//: lowest shown strip reaches below the dock, 0 while none is shown (a hidden
//: strip has no box), and `--graph-chrome-top` grows by it on the card.
function graphRailOffset(strips, dockBottom) {
  const shown = strips.filter((s) => s.bottom > s.top);
  return shown.length ? Math.max(0, Math.round(Math.max(...shown.map((s) => s.bottom)) - dockBottom)) : 0;
}

function initGraphRailToken() {
  const card = document.getElementById("graph-card");
  const dock = card?.querySelector('.dock[data-dock-name="graph"]');
  const strips = card ? [...card.querySelectorAll(".graph-overlay > .graph-trace, .graph-overlay > .graph-trace-result")] : [];
  //: Rides the dock's ResizeObserver (`initGraphDockHeightToken`, run first), no second observer.
  if (!dock || !strips.length || !card._chromeWatch || typeof ResizeObserver === "undefined" || card._railWired) return;
  card._railWired = true;
  const write = () => {
    const boxes = strips.map((el) => el.getBoundingClientRect());
    const offset = graphRailOffset(boxes, dock.getBoundingClientRect().bottom);
    //: The existing token plus the rail, so no second property is declared
    //: (the stylesheet's custom-property count only falls); cleared at 0.
    if (offset) card.style.setProperty("--graph-chrome-top", `calc(var(--space-3) * 2 + var(--graph-dock-h) + ${offset}px)`);
    else card.style.removeProperty("--graph-chrome-top");
  };
  card._railWrite = write;
  for (const el of strips) card._chromeWatch.observe(el);
}

//: **A toast over the map stands above the legend** (INBOX 1400: it met the
//: legend row's box at 1440 and the zoom strip at 390). The toast box's bottom
//: is the legend row's own distance from the window's bottom plus a step, kept
//: current by an observer and on resize; graph-lazy.css steps it left of the
//: zoom strip. Written on the box itself, never as a property on the page, and
//: cleared while the row is not drawn (another tab, or the legend hidden),
//: where the toast keeps the place its stylesheet gives it.
function initGraphToastClearance() {
  const row = document.querySelector("#graph-card .graph-legend-row");
  const box = document.getElementById("toast-box");
  if (!row || !box || row._liftWired) return;
  row._liftWired = true;
  const write = () => {
    const at = row.getBoundingClientRect();
    const lift = at.height > 0 ? Math.max(0, Math.round(window.innerHeight - at.top)) : 0;
    box.style.bottom = lift > 0 ? `${lift + 8}px` : "";
  };
  //: The popups' observer (`watchGraphPopupSize`) calls `graphPlace` on any element it watches,
  //: so the legend row rides it rather than owning a second observer.
  watchGraphPopupSize(row, write);
  window.addEventListener("resize", write);
  write();
}

function initGraphMinimap() {
  const svg = document.getElementById("graph-minimap-svg");
  if (!svg || svg._wired) return;
  svg._wired = true;
  // Where in canvas coordinates a pointer event over the minimap is pointing.
  // Null whenever the map has not been painted yet (`_toCanvas` is set by
  // graphMinimapPaint) or the zoom behaviour is not up, which is every call
  // before the first render.
  const canvasPointFor = (event) => {
    if (!svg._toCanvas || !graphSvg || !graphZoom) return null;
    const rect = svg.getBoundingClientRect();
    return svg._toCanvas(
      ((event.clientX - rect.left) / rect.width) * GRAPH_MINIMAP_W,
      ((event.clientY - rect.top) / rect.height) * GRAPH_MINIMAP_H
    );
  };

  // Centre the map on a canvas point at a given scale. `animate` is off while
  // a drag is in flight: a 250ms transition per pointermove queues dozens of
  // overlapping tweens and the map lurches behind the cursor instead of
  // tracking it. A single click still animates, because a jump that teleports
  // loses you your bearings.
  const centreOn = (cx, cy, scale, animate) => {
    //: The minimap's own way of writing the transform, and it reads
    //: `graphDims` and a projected point, so it is guarded for the reason
    //: `fitGraphToView` is.
    if (!graphMinimapFinite(graphDims.w, graphDims.h, cx, cy, scale)) return;
    const target = d3.zoomIdentity
      .translate(graphDims.w / 2, graphDims.h / 2)
      .scale(scale)
      .translate(-cx, -cy);
    const sel = animate ? graphSvg.transition().duration(graphGlideMs(250)) : graphSvg;
    sel.call(graphZoom.transform, target);
  };

  const jump = (event, animate = true) => {
    const point = canvasPointFor(event);
    if (!point) return;
    // Keep the zoom level, change only where it is centred, a click on the
    // minimap is for navigating. Zooming from here is the wheel, below.
    centreOn(point[0], point[1], d3.zoomTransform(graphSvg.node()).k, animate);
  };

  // Press and hold to scrub the map around, rather than clicking, looking,
  // clicking again. Pointer events (not mouse) so a finger on a tablet drags
  // the same way; pointer capture so leaving the little box mid-drag keeps
  // sending moves here instead of dropping the drag where the cursor left.
  let dragging = false;
  svg.addEventListener("pointerdown", (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    if (!canvasPointFor(event)) return;
    dragging = true;
    svg.setPointerCapture?.(event.pointerId);
    svg.classList.add("graph-minimap-dragging");
    // The press itself centres, so a plain click still works, there is no
    // separate click listener any more, which is what stopped a click from
    // firing this and then a second, animated jump on mouseup.
    jump(event, true);
    event.preventDefault();
  });
  svg.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    jump(event, false);
  });
  const endDrag = (event) => {
    if (!dragging) return;
    dragging = false;
    svg.releasePointerCapture?.(event.pointerId);
    svg.classList.remove("graph-minimap-dragging");
  };
  svg.addEventListener("pointerup", endDrag);
  svg.addEventListener("pointercancel", endDrag);

  // Wheel (and a trackpad pinch, which browsers deliver as a wheel event with
  // ctrlKey set) zooms about the point under the cursor, the same gesture the
  // main canvas already answers to. `passive: false` because preventDefault is
  // the whole point: without it the page scrolls behind the minimap.
  svg.addEventListener(
    "wheel",
    (event) => {
      const point = canvasPointFor(event);
      if (!point) return;
      event.preventDefault();
      const current = d3.zoomTransform(graphSvg.node());
      // deltaY is device-dependent (lines vs pixels vs a pinch's fine steps),
      // so only its sign is trusted; the step is ours.
      const factor = event.deltaY < 0 ? 1.2 : 1 / 1.2;
      const extent = graphZoom.scaleExtent ? graphZoom.scaleExtent() : [0.1, 8];
      const scale = Math.max(extent[0], Math.min(extent[1], current.k * factor));
      centreOn(point[0], point[1], scale, false);
    },
    { passive: false }
  );
  // One control for both "is it showing" and "where", see index.html on why
  // these were merged rather than sitting beside each other.
  //
  // Per-device workspace state, so localStorage beside `graph-layout` and the
  // saved views below, not preferences.
  const applyMinimapPosition = (choice) => {
    const box = document.getElementById("graph-minimap");
    if (!box) return;
    const chosen = GRAPH_MINIMAP_CORNERS.includes(choice) ? choice : "tl";
    for (const c of GRAPH_MINIMAP_CORNERS) box.classList.remove(`graph-minimap-${c}`);
    //: Choosing a corner is not, on its own, a claim that there is anything
    //: to show. This used to `toggle("hidden", chosen === "off")`, which
    //: un-hid the box unconditionally, and since it runs after the first
    //: render it put the empty box back on screen every time. `graphMinimapPaint`
    //: below has the last word: it hides the box again when there are no dots.
    if (chosen === "off") {
      box.classList.add("hidden");
    } else {
      box.classList.add(`graph-minimap-${chosen}`);
      box.classList.remove("hidden");
      graphMinimapPaint();
    }
    const picker = document.getElementById("graph-minimap-corner");
    if (picker) picker.value = chosen;
  };

  // Existing installs kept only "hidden or not" under an older key. Read it
  // once so nobody who had deliberately turned the minimap off has it come
  // back on after an update; the new key takes over from the first change.
  const storedCorner = prefs.get(GRAPH_MINIMAP_CORNER_KEY, null);
  const legacyHidden = prefs.get("graph-minimap-hidden", null) === "1";
  applyMinimapPosition(storedCorner || (legacyHidden ? "off" : "tl"));

  document.getElementById("graph-minimap-corner")?.addEventListener("change", (event) => {
    const choice = event.target.value;
    prefs.set(GRAPH_MINIMAP_CORNER_KEY, choice);
    applyMinimapPosition(choice);
  });

  //: **Two sizes** (GRAPH_PLAN Phase 6b, INBOX 78). 168x112 is a glance; on a
  //: dense notebook, or a large screen where a corner of the canvas costs
  //: nothing, it is too small to aim with, and the answer people reach for is
  //: to zoom the whole graph out instead, which is the opposite of what the
  //: minimap is for. The large size is the same picture at 1.5x: the box is
  //: scaled in CSS, the viewBox is untouched, and every measurement in here
  //: already divides by the element's own rendered width, so nothing about the
  //: projection or the drag has to know which size is on.
  //:
  //: In the dock menu beside Position rather than as a control on the map
  //: itself: the map is `aria-hidden` decoration that happens to be
  //: draggable, and a focusable button inside an aria-hidden box is a control
  //: no screen reader can reach.
  const applyMinimapSize = (choice) => {
    const box = document.getElementById("graph-minimap");
    if (!box) return;
    const chosen = choice === "lg" ? "lg" : "sm";
    box.classList.toggle("graph-minimap-lg", chosen === "lg");
    const picker = document.getElementById("graph-minimap-size");
    if (picker) picker.value = chosen;
  };
  applyMinimapSize(prefs.get(GRAPH_MINIMAP_SIZE_KEY, null));
  document.getElementById("graph-minimap-size")?.addEventListener("change", (event) => {
    const choice = event.target.value;
    prefs.set(GRAPH_MINIMAP_SIZE_KEY, choice);
    applyMinimapSize(choice);
  });
}

// --- saved views -------------------------------------------------------------
//
// A "view" is every control that changes *what the map shows and how*, plus
// where you were looking. Stored in localStorage rather than the database on
// purpose: these are per-device workspace state of the same kind as
// `graph-layout` and the sidebar widths already kept there (see
// MIRRORED_UI_EXTRAS in app.js), not notebook content that belongs in a
// backup.
const GRAPH_VIEWS_KEY = "graph-saved-views";

function graphSavedViews() {
  try {
    const parsed = prefs.json(GRAPH_VIEWS_KEY, []);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return []; // corrupt or hand-edited: an empty list beats a broken tab
  }
}

function graphCaptureView() {
  const transform = graphSvg ? d3.zoomTransform(graphSvg.node()) : null;
  return {
    layout: prefs.get("graph-layout", null) || "force",
    colour: prefs.get("graph-colour", null) || "",
    hiddenCategories: [...graphHiddenCategories],
    hiddenKeys: [...graphHiddenKeys],
    groups: graphGroups(),
    // graph.md section 1: `#graph-physics` is the Physics *section*
    // (`.dock-menu-section`, index.html), not a checkbox -- it was never
    // anything a saved view could read `.checked` off, so every view stored
    // `physics: true` no matter what the sliders said. "Physics", to a
    // reader, means what Gravity and Spread are set to, so a view captures
    // those two directly now, the same values `renderGraph()` itself reads
    // out of localStorage (graph.js line ~1713).
    gravity: document.getElementById("graph-gravity")?.value ?? "50",
    spread: document.getElementById("graph-spread")?.value ?? "50",
    time: document.getElementById("graph-time-slider")?.value ?? null,
    // Same bug, two more controls: the ids below were never on the page
    // (the checkboxes are `#graph-entities`/`#graph-documents`; app.js binds
    // their "change" listener to those two ids, not to the ones this
    // function used to read), so a saved view's Entities/Documents state was
    // always the `?? false`
    // fallback, regardless of what was actually shown when it was saved.
    entities: document.getElementById("graph-entities")?.checked ?? false,
    documents: document.getElementById("graph-documents")?.checked ?? false,
    orphans: document.getElementById("graph-hide-orphans")?.checked ?? false,
    transform: transform ? { x: transform.x, y: transform.y, k: transform.k } : null,
    // GRAPH_PLAN Phase 5, "positions on a saved view" (INBOX 275's neighbour
    // row): the one thing a saved view used to lose. Every visible node's
    // current spot, force layout or not (a tree/radial/arc one is
    // recomputed deterministically on restore and never reads this back,
    // see `graphApplyView`/`renderGraphCanvas`, but capturing it uniformly
    // costs nothing and keeps this function from having to know the
    // layout). `graphNodesRef` is the live node array the canvas
    // draws from, so this is "what is actually on screen", not a stale copy.
    positions: Object.fromEntries(
      (graphNodesRef || [])
        .filter((n) => Number.isFinite(n.x) && Number.isFinite(n.y))
        .map((n) => [n.id, { x: n.x, y: n.y }])
    ),
  };
}

async function graphSaveCurrentView() {
  const name = (await promptDialog("Name this view", "", { confirmLabel: "Save view" })).trim();
  if (!name) return;
  const views = graphSavedViews().filter((v) => v.name !== name); // same name replaces
  views.push({ name, ...graphCaptureView() });
  prefs.set(GRAPH_VIEWS_KEY, JSON.stringify(views));
  renderGraphViews();
  toast(`Saved the view “${name}”.`);
}

function graphApplyView(view) {
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (!el || value === null || value === undefined) return;
    if (el.type === "checkbox") el.checked = Boolean(value);
    else el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  };
  // GRAPH_PLAN Phase 5, "positions on a saved view". The `set()` calls below
  // each dispatch a real "change" and several of them (layout, colour,
  // physics, entities, documents, orphans) independently call `renderGraph`,
  // which is async and guards itself against a stale call with its own
  // sequence number (`renderGraphCanvas`'s `s.renderSeq`): every render but
  // the *last one dispatched here that actually renders* bails before it
  // reaches the node-building step below, so setting this once, before any
  // of them fire, and letting the render consume-and-clear it, is race-free
  // without this function needing to know which `set()` call that will be.
  graphPendingViewPositions =
    view.positions && Object.keys(view.positions).length ? view.positions : null;
  prefs.set("graph-layout", view.layout);
  if (view.colour) prefs.set("graph-colour", view.colour);
  //: The layout is a list (INBOX 670; it was a radio group, which `set()` on
  //: its `<div>` wrote a `value` expando on and fired "change" from, so the
  //: map was right and the View menu still showed the old layout). The list
  //: is set by value among its own options, so a saved string that no option
  //: carries leaves it alone rather than blank.
  const layoutSelect = $("graph-layout");
  if (layoutSelect && [...layoutSelect.options].some((o) => o.value === view.layout)) {
    layoutSelect.value = view.layout;
    layoutSelect.dispatchEvent(new Event("change", { bubbles: true }));
  }
  set("graph-colour", view.colour);
  // Real controls, not the section div: `set()` dispatches "change" on each,
  // which is exactly what the gravity/spread listener (app.js, "Physics
  // sliders: persist, then rebuild the simulation with the new forces")
  // already listens for, so restoring a view re-persists and re-renders
  // through the same path dragging the slider does.
  set("graph-gravity", view.gravity);
  set("graph-spread", view.spread);
  set("graph-entities", view.entities);
  set("graph-documents", view.documents);
  set("graph-hide-orphans", view.orphans);
  set("graph-time-slider", view.time);
  graphHiddenCategories = new Set(view.hiddenCategories || []);
  graphHiddenKeys = new Set(view.hiddenKeys || []);
  if (Array.isArray(view.groups)) {
    prefs.set(GRAPH_GROUPS_KEY, JSON.stringify(view.groups));
    graphRenderGroups();
  }

  // The transform lands *after* the rebuild those change events kick off, 
  // restoring the pan/zoom first would only have it overwritten by the
  // auto-fit that runs when a fresh layout settles.
  setTimeout(() => {
    if (!view.transform || !graphSvg || !graphZoom) return;
    graphSvg.call(
      graphZoom.transform,
      d3.zoomIdentity.translate(view.transform.x, view.transform.y).scale(view.transform.k)
    );
    graphMinimapPaint();
  }, 400);
  toast(`Showing “${view.name}”.`);
}

function renderGraphViews() {
  const select = document.getElementById("graph-view-picker");
  if (!select) return;
  const views = graphSavedViews();
  select.replaceChildren();
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = views.length ? "Saved views…" : "No saved views";
  select.appendChild(blank);
  for (const view of views) {
    const option = document.createElement("option");
    option.value = view.name;
    option.textContent = view.name;
    select.appendChild(option);
  }
  select.disabled = !views.length;
  //: **A disabled control says why it is disabled.** Found by the vibecoded
  //: sweep (`scratchpad/ui-sweeps/vibecheck.js`), which counts exactly this:
  //: a greyed control with no title and no described-by leaves the reader
  //: with no way to find out what would turn it back on, which reads as the
  //: app being broken rather than as nothing having been saved yet.
  const why = "Save a view first: the Save this view row in this menu";
  select.title = views.length ? "Jump to a saved view" : why;
  const remove = document.getElementById("graph-view-delete");
  if (remove) {
    remove.disabled = !views.length;
    remove.title = views.length ? "Delete the view chosen above" : why;
  }
}

function initGraphViews() {
  const select = document.getElementById("graph-view-picker");
  if (!select || select._wired) return;
  select._wired = true;
  select.addEventListener("change", () => {
    const view = graphSavedViews().find((v) => v.name === select.value);
    if (view) graphApplyView(view);
  });
  initGraphGroups();
  document.getElementById("graph-view-save")?.addEventListener("click", graphSaveCurrentView);
  document.getElementById("graph-view-delete")?.addEventListener("click", async () => {
    const name = select.value;
    if (!name) {
      toast("Pick a view to delete first.");
      return;
    }
    if (!(await confirmDialog(`Delete the saved view “${name}”?`))) return;
    prefs.set(
      GRAPH_VIEWS_KEY,
      JSON.stringify(graphSavedViews().filter((v) => v.name !== name))
    );
    renderGraphViews();
    toast("View deleted.");
  });
  renderGraphViews();
}

// Wired at parse time as well as from the first render: the token has to be
// right before the tab is first looked at, and the render path that calls it
// below does not run at all while the notebook has nothing to draw. Both
// calls are idempotent (`_heightWired`), and the observer's first callback
// arrives with a real height as soon as the card stops being display:none.
initGraphDockHeightToken();
initGraphRailToken();
initGraphToastClearance();

//: The remembered on-by-default switches, restored when graph.js loads: the
//: canvas renderer (the default) never ran the SVG render that used to do it,
//: so Curved links, Cluster glow and Label backgrounds came back on after a
//: reload while drawn from the box.
const GRAPH_STORED_SWITCHES = ["graph-curved", "graph-label-plates", "graph-nebula", "graph-length-score", "graph-group",
  "graph-focus-in", "graph-focus-out", "graph-focus-neighbours", "graph-pane-in", "graph-pane-out", "graph-pane-neighbours", "graph-autofit"];
//: Off by default, so stored "1" means on; and the sliders' stored values.
const GRAPH_STORED_OFF = ["graph-arrows"];
const GRAPH_STORED_SLIDERS = ["graph-label-fade", "graph-link-width", "graph-focus-depth", "graph-pane-depth"];
function graphRestoreSwitches() {
  for (const id of GRAPH_STORED_SWITCHES) {
    const box = $(id);
    if (box) box.checked = prefs.get(id, null) !== "0";
  }
  for (const id of GRAPH_STORED_OFF) if ($(id)) $(id).checked = prefs.get(id, null) === "1";
  for (const id of GRAPH_STORED_SLIDERS) {
    const stored = prefs.get(id, null);
    if ($(id) && stored !== null && Number.isFinite(Number(stored))) $(id).value = stored;
  }
}
graphRestoreSwitches();

//: GRAPH_PLAN 514: what each new control redraws. The kinds of node are a
//: fetch (renderGraph), the drawing ones a frame, the local ones a fetch of
//: their own surface.
for (const id of ["graph-tags", "graph-attachments", "graph-unresolved"]) $(id)?.addEventListener("change", renderGraph);
//: The owner, 2026-10-26: views "need to better fit the user's screen and
//: readjust to fit when switching between views (maybe make that togglable
//: but on by default)". Off keeps the camera across a layout change or resize.
function graphAutoFitOn() {
  return prefs.get("graph-autofit", null) !== "0";
}
$("graph-autofit")?.addEventListener("change", (event) => {
  prefs.set("graph-autofit", event.target.checked ? "1" : "0");
  if (event.target.checked) gcAutoFitTurnedOn();
});
$("graph-arrows")?.addEventListener("change", (event) => {
  prefs.set("graph-arrows", event.target.checked ? "1" : "0");
  gcRequestDraw();
});
for (const id of ["graph-label-fade", "graph-link-width"]) {
  $(id)?.addEventListener("input", () => gcRequestDraw());
  $(id)?.addEventListener("change", (event) => {
    prefs.set(id, event.target.value);
    gcRequestDraw();
  });
}
for (const prefix of ["focus", "pane"]) {
  for (const id of ["depth", "in", "out", "neighbours"]) {
    $(`graph-${prefix}-${id}`)?.addEventListener("change", (event) => {
      const box = event.target;
      prefs.set(box.id, box.type === "checkbox" ? (box.checked ? "1" : "0") : box.value);
      if (prefix === "focus") {
        if (graphFocusModeId) renderGraph();
      } else if (typeof renderGraphPane === "function" && graphPaneShownId != null) {
        renderGraphPane(graphPaneShownId);
      }
    });
  }
}

$("graph-label-plates")?.addEventListener("change", (event) => {
  prefs.set("graph-label-plates", event.target.checked ? "1" : "0");
  gcRequestDraw();
});

// INBOX 692: a new arrangement of the force layout, animated, then framed
// (`gcReshuffle`, graph-canvas.js). Wired here, in the graph's own bundle,
// beside the other Physics controls, so it can never be pressed before the
// function it calls has loaded.
$("graph-reshuffle")?.addEventListener("click", () => {
  if (!gcReshuffle()) toast("Reshuffle works on the force layout: pick Force under Layout first.");
});

//: Moved from wiring.js (2026-10-10, the boot script budget): see the note
//: left there.
// On-screen zoom controls drive the same d3 zoom behaviour as scroll/pinch.
//: **The map's head menus shut each other** (INBOX 796, the owner:
//: "dropdown menus in the graph dont close when another is opened causing a
//: visual clash and overlay for all 3 of these buttons"). The '?' and the
//: gear stop their click from reaching the page, so their own outside-click
//: close does not undo them, which also kept every other menu's
//: outside-click close from running. Caught on the way down, before either
//: handler runs: the others close, the one pressed then does what it does.
//: In the tab's own bundle: the boot scripts have no bytes left.
const GRAPH_HEAD_MENUS = "#graph-help-toggle, #graph-options-toggle, #graph-more-menu > summary";
function graphCloseOtherMenus(opener) {
  closeActionMenus();
  for (const entry of [...openHelpPopovers]) if (entry.trigger !== opener) entry.close();
  for (const menu of document.querySelectorAll("details.dock-menu[open]")) {
    if (!menu.contains(opener)) menu.open = false;
  }
  const panel = $("graph-options");
  if (panel && !panel.classList.contains("hidden") && !$("graph-options-toggle").contains(opener)) setGraphOptionsOpen(false);
}
document.addEventListener("click", (event) => {
  const opener = event.target.closest?.(GRAPH_HEAD_MENUS);
  if (opener) graphCloseOtherMenus(opener);
}, true);

function graphZoomBy(factor) {
  if (!graphZoom || !graphSvg) return;
  //: The zoom buttons move the camera as a gesture does: no settle fit or
  //: panel refit may take it back (INBOX 792).
  if (typeof gcTab !== "undefined" && gcTab.svg === graphSvg) gcTab.userZoomed = true;
  graphSvg.transition().duration(graphGlideMs(200)).call(graphZoom.scaleBy, factor);
}
$("graph-zoom-in").addEventListener("click", () => graphZoomBy(1.3));
$("graph-zoom-out").addEventListener("click", () => graphZoomBy(1 / 1.3));
$("graph-zoom-fit").addEventListener("click", () => {
  if (graphNodesRef && graphNodesRef.length) {
    fitGraphToView(graphSvg, graphZoom, graphNodesRef, graphDims.w, graphDims.h);
  }
});

function toggleGraphFullscreen() {
  const card = $("graph-card");
  if (card) {
    const isFull = card.classList.toggle("graph-fullscreen");
    // **Full screen hides the app chrome** (INBOX 29: "the top bar stays").
    // The card has covered the screen for a while, inset by one step and
    // fixed, but the top bar, the tab bar inside it and the status bar were
    // still laid out under it and still showing through that inset, so full
    // screen read as a card sitting on the app rather than as the map having
    // the screen. The class goes on <body> because the chrome is not inside
    // the card: what is hidden is listed in 02-chat-graph.css beside the
    // `.graph-fullscreen` rule itself.
    document.body.classList.toggle("graph-fullscreen-on", isFull);
    // The single zoom-cluster button now does both jobs a separate "Close
    // Full Screen" toolbar button used to split between them, asked for
    // directly: "move the close full screen button in the graph to be next
    // to the new graph button or smth so it isnt making an extra row." That
    // second button (`#graph-fullscreen-close`, toolbar) called this exact
    // same function and existed only because this one gave no sign it also
    // exits: so rather than relocate a redundant second button, this one
    // now says which of its two jobs it will do next.
    const fsBtn = $("graph-fullscreen");
    if (fsBtn) {
      fsBtn.title = isFull ? "Exit full screen" : "Full screen";
      fsBtn.setAttribute("aria-label", fsBtn.title);
      fsBtn.setAttribute("aria-pressed", String(isFull));
      const icon = fsBtn.querySelector("i");
      if (icon) icon.className = isFull ? "ph ph-arrows-in" : "ph ph-frame-corners";
    }
    window.dispatchEvent(new Event('resize'));
    if (graphNodesRef && graphNodesRef.length) {
      setTimeout(() => {
        const box = $("graph-box");
        graphDims.w = box.clientWidth || 800;
        graphDims.h = box.clientHeight || 540;
        // The canvas resizes itself from its ResizeObserver; only the camera is refitted.
        if (isFull) {
          fitGraphToView(graphSvg, graphZoom, graphNodesRef, graphDims.w, graphDims.h);
        }
      }, 50);
    }
  }
}

$("graph-fullscreen")?.addEventListener("click", toggleGraphFullscreen);

// INBOX 693: the force layout's Shape (`gcShape`, the worker's `SHAPES`).
// Remembered; a change re-lays the map out from where every note stands, so
// the notes travel to the new shape rather than jumping to it.
(() => {
  const shape = $("graph-shape");
  if (!shape) return;
  // graph-canvas.js (and `gcShape`) loads after this file: an unknown value
  // leaves a select empty, so that is the test for one.
  shape.value = prefs.get("graph-shape", null) || "organic";
  if (!shape.value) shape.value = "organic";
  shape.addEventListener("change", () => {
    prefs.set("graph-shape", shape.value);
    graphHighlightIds = null;
    renderGraph();
  });
})();

$("graph-curved")?.addEventListener("change", (event) => {
  prefs.set("graph-curved", event.target.checked ? "1" : "0");
  //: The layout keeps dots clear of the lines as drawn (the worker's
  //: `clearanceForce`, INBOX 693), and a curve and a straight line pass
  //: different dots, so the forces hear about it and the map eases round.
  if (!gcTab.tree) gcPost({ type: "params", params: gcWorkerParams(gcTab) });
  gcRequestDraw();
});

//: The cluster wash is on by default and remembered off (the owner: "the
//: nebulae could be a togglable feature??"); like Curved links it is a redraw.
$("graph-nebula")?.addEventListener("change", (event) => {
  prefs.set("graph-nebula", event.target.checked ? "1" : "0");
  gcRequestDraw();
});

//: Link length by similarity changes the forces, so it is a relayout rather
//: than a redraw (the owner: "distance based on similarity score or smth??").
$("graph-length-score")?.addEventListener("change", (event) => {
  prefs.set("graph-length-score", event.target.checked ? "1" : "0");
  renderGraph();
});
//: Group by category changes the forces too (graph-worker.js `applyGrouping`).
$("graph-group")?.addEventListener("change", (event) => {
  prefs.set("graph-group", event.target.checked ? "1" : "0");
  renderGraph();
});

//: The Match strength row shows only while Similarity is on (INBOX 412): a
//: cutoff for lines that are not drawn is a control that does nothing. Its
//: value is remembered like the other Show settings and read by the render
//: (`gcSimilarityCutoff`), so a change is a relayout: fewer lines means
//: fewer springs, and the clusters should move apart when they go.
function graphSyncSimilarityRow() {
  const row = document.getElementById("graph-similarity-min-row");
  const box = document.getElementById("graph-similarity");
  if (row && box) row.classList.toggle("hidden", !box.checked);
  const slider = document.getElementById("graph-similarity-min");
  if (slider) {
    const value = Number(slider.value);
    slider.setAttribute(
      "aria-valuetext",
      value <= 55 ? "Each note's two closest matches" : `Matches of ${value}% and above`
    );
  }
}
(() => {
  const slider = document.getElementById("graph-similarity-min");
  if (!slider) return;
  let stored = null;
  try {
    stored = prefs.get("graph-similarity-min", null);
  } catch (error) {
    stored = null;
  }
  if (stored && Number.isFinite(Number(stored))) slider.value = stored;
  slider.addEventListener("input", graphSyncSimilarityRow);
  slider.addEventListener("change", () => {
    try {
      prefs.set("graph-similarity-min", slider.value);
    } catch (error) {
      /* A browser with storage refused still filters, it just forgets. */
    }
    renderGraph();
  });
  document.getElementById("graph-similarity")?.addEventListener("change", graphSyncSimilarityRow);
  graphSyncSimilarityRow();
})();

// --- reset to defaults ---------------------------------------------------------
//
// INBOX 412, the owner: "there is no reset the graph settings to default
// option either". Obsidian's graph has one in the corner of its settings box
// ("Restore default settings"); the app's own precedent is Settings >
// Appearance's "Reset to defaults" and the shortcuts' one, and a reset that
// can be taken back is `toastAction`'s Undo (DESIGN.md, the recipe index).
//
// **What a reset covers.** Every control that changes how the map is drawn:
// the layout and the colour rule (View menu), the physics, every Show switch,
// the similarity cutoff, the time filter, the minimap, and the categories or
// kinds hidden from the legend. **What it leaves alone:** groups and saved
// views, which are things somebody made and named rather than settings, and
// which folds of the panel are open, which is where the reader is rather
// than what the map looks like. `tests/test_graph_similarity.py` fails if a
// control is added to the panel's persisted set without joining this table.
//
// Values are what the markup and the readers default to: `graphLayout()`
// falls back to force, the colour select's first option is category, the
// sliders start at 50, the minimap at top left and small, and `"max"` puts
// the time slider at its "All time" end, which is a number only a render
// knows.
const GRAPH_DEFAULTS = {
  layout: "force",
  "graph-colour": "category",
  "graph-size": "connections",
  "graph-gravity": "50",
  "graph-spread": "50",
  "graph-link-force": "50",
  "graph-similarity": false,
  "graph-similarity-min": "55",
  "graph-entities": false,
  "graph-documents": false,
  "graph-maps": false,
  "graph-tags": false,
  "graph-attachments": false,
  "graph-unresolved": false,
  "graph-arrows": false,
  "graph-autofit": true,
  "graph-label-fade": "50",
  "graph-link-width": "50",
  "graph-focus-depth": "2",
  "graph-focus-in": true,
  "graph-focus-out": true,
  "graph-focus-neighbours": true,
  "graph-hide-orphans": false,
  "graph-labels": true,
  "graph-curved": true,
  "graph-label-plates": true,
  "graph-nebula": true,
  "graph-length-score": true,
  "graph-group": true,
  "graph-time-slider": "max",
  "graph-minimap-corner": "tl",
  "graph-minimap-size": "sm",
  hiddenCategories: [],
  hiddenKeys: [],
};

//: The same shape as `GRAPH_DEFAULTS`, read off the controls as they stand,
//: so Undo puts back exactly what the reset replaced.
function graphCaptureSettings() {
  const out = {};
  for (const [key, fallback] of Object.entries(GRAPH_DEFAULTS)) {
    if (key === "layout") {
      out.layout = graphLayout();
    } else if (key === "hiddenCategories") {
      out.hiddenCategories = [...graphHiddenCategories];
    } else if (key === "hiddenKeys") {
      out.hiddenKeys = [...graphHiddenKeys];
    } else {
      const el = document.getElementById(key);
      if (!el) out[key] = fallback;
      else if (el.type === "checkbox") out[key] = el.checked;
      else if (key === "graph-time-slider") out[key] = Number(el.value) >= Number(el.max) ? "max" : el.value;
      else out[key] = el.value;
    }
  }
  return out;
}

function graphSettingsEqual(a, b) {
  return Object.keys(GRAPH_DEFAULTS).every(
    (key) => JSON.stringify(a[key]) === JSON.stringify(b[key])
  );
}

//: Every control is set the way a person would set it: its value, then the
//: event its own handler listens for, so each one persists and redraws
//: through the path it already has (the same move `graphApplyView` makes).
//: The redraws that pile up are cheap: `renderGraphCanvas` drops every
//: render but the last by its sequence number.
function graphApplySettings(settings) {
  const layout = $("graph-layout");
  if (layout && layout.value !== settings.layout && [...layout.options].some((o) => o.value === settings.layout)) {
    layout.value = settings.layout;
    layout.dispatchEvent(new Event("change", { bubbles: true }));
  }
  graphHiddenCategories = new Set(settings.hiddenCategories || []);
  graphHiddenKeys = new Set(settings.hiddenKeys || []);
  for (const [key, value] of Object.entries(settings)) {
    if (key === "layout" || key === "hiddenCategories" || key === "hiddenKeys") continue;
    const el = document.getElementById(key);
    if (!el) continue;
    if (el.type === "checkbox") {
      if (el.checked === Boolean(value)) continue;
      el.checked = Boolean(value);
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } else if (key === "graph-time-slider") {
      // The time slider answers `input` (graph-canvas.js, `graphSyncTimeSlider`).
      el.value = value === "max" ? el.max : value;
      el.dispatchEvent(new Event("input", { bubbles: true }));
    } else if (String(el.value) !== String(value)) {
      el.value = value;
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  graphSyncSimilarityRow();
  setGraphPhysicsEnabled(settings.layout);
  // One more, for the legend filters, which have no control of their own to
  // fire an event on.
  renderGraph();
}

//: Reset also lets go of every pinned note (K9, the owner: "resetting the
//: graph to defaults doesnt unstick stuck nodes, should it?"): a pin is a
//: layout the person made, and the Undo in the toast puts them back.
async function graphResetToDefaults() {
  const before = graphCaptureSettings();
  const pins = graphPinnedRows();
  if (graphSettingsEqual(before, GRAPH_DEFAULTS) && !pins.length) {
    toast("The map is already on its default settings.");
    return;
  }
  let released = pins;
  const reset = async () => {
    if (pins.length) released = (await graphUnpinAllNow().catch(() => null))?.rows || pins;
    graphApplySettings(GRAPH_DEFAULTS);
  };
  await reset();
  offerUndo(
    "Reset the map's settings",
    pins.length ? `Map settings reset, ${pins.length} pinned note${pins.length === 1 ? "" : "s"} released.` : "Map settings reset to defaults.",
    async () => {
      graphApplySettings(before);
      await graphRestorePins(released);
      toast("Map settings restored.");
    },
    reset
  );
}

document.getElementById("graph-options-reset")?.addEventListener("click", graphResetToDefaults);

//: (Moved from wiring.js: the helpers it calls live in this lazy bundle.)
// Direct instruction: "I want to be able to unroot and reset the graph to
// free float if I want with a button." One request releases every pinned
// node at once (routes_graph.py's unpin_all_nodes) rather than tracking
// each one down to double-click it individually; renderGraph() afterwards
// re-fetches from /graph, which is what actually clears fx/fy, the same
// path #graph-refresh already uses, so a freshly unpinned layout settles
// through the ordinary simulation rather than a special-cased one.
for (const id of ["graph-unpin-all", "graph-unpin-all-menu"]) document.getElementById(id)?.addEventListener("click", async (event) => {
  // The first rides the Physics fold's own `<summary>` (index.html), so a
  // press on it is also a press on the disclosure. `preventDefault` cancels
  // the summary's activation behaviour and nothing else: a `type="button"`
  // has no default action of its own to lose. The second is the ⋯ menu's.
  event.preventDefault();
  document.getElementById("graph-more-menu")?.removeAttribute("open");
  try {
    const { rows, count } = await graphUnpinAllNow();
    if (!count) return toast("Nothing was pinned.");
    offerUndo(
      "Unpinned every note",
      `${nounCount(count, "note")} released: the layout can move freely again.`,
      () => graphRestorePins(rows),
      () => graphUnpinAllNow()
    );
  } catch (error) {
    toast(error.message || "Couldn't unpin the graph.", true);
  }
});

// --- the graph's controls on a phone: one sheet (moved from wiring.js) -------------------------------
// UI_MODERNISATION_PLAN Phase 11 item 4, "the docks as one bottom sheet with
// the colour rule, groups and views". At 390 the Graph tab answers a question
// about the map in one of three places: the gear's floating panel (physics,
// what to show, time, groups, the minimap, suggest links), the View menu
// (layout, the colour rule, Trace, the legend) and the ⋯ menu (saved views,
// export). Each opens *over* the 362x653 map it is about, and the first of
// them covers 42% of it.
//
// One sheet instead, from the gear, holding all three in that order: what the
// map is, then what it shows, then what is saved. The same elements, moved in
// while it is open and put back on close, so every handler, every id and every
// saved preference is the one that was already there; nothing about this
// surface is built twice. Above 600 the gear opens its panel and the ⋯ is a
// menu.
//
// The two `<details>` are hidden by the stylesheet below 600 rather than
// emptied, because what is in them moves and comes back: an opener whose menu
// is somewhere else is an opener that opens nothing.

//: `#graph-options` moves as itself, keeping its class, so the rules written
//: for `.graph-options .dock-menu-section` still reach its sections inside
//: the sheet; the two menus' children move into a holder wearing the menu
//: list's own classes, for the same reason. What is deliberately left behind
//: is the folded arrange zone: below 1100 `foldDockArrange` parks the View
//: menu *inside* the ⋯ menu's list, so taking that list's children whole
//: would bring an emptied View menu into the sheet under the rows that came
//: out of it.
function graphControlsSheetParts() {
  const moreList = document.querySelector("#graph-more-menu .dock-menu-list");
  const options = $("graph-options");
  const groups = [];
  if (options) groups.push({ holder: "options", nodes: [options] });
  if (moreList) {
    groups.push({
      holder: "menu",
      nodes: [...moreList.children].filter(
        (el) => !el.classList.contains("dock-arrange") && !el.classList.contains("dock-arrange-label")
      ),
    });
  }
  return groups.filter((group) => group.nodes.length);
}

function openGraphControlsSheet(opener) {
  if (graphSheetClose) return;
  const groups = graphControlsSheetParts();
  if (!groups.length) return;
  // Where each node came from, taken before anything moves: a node's parent
  // and the sibling it sat in front of are what put it back exactly.
  const home = [];
  for (const group of groups) {
    for (const node of group.nodes) home.push({ node, parent: node.parentNode, next: node.nextSibling });
  }
  const panel = $("graph-options");
  const wasHidden = panel ? panel.classList.contains("hidden") : true;
  opener?.setAttribute("aria-expanded", "true");
  graphSheetClose = openSheet({
    label: "Map controls",
    name: "graph",
    returnFocus: opener,
    build: (card) => {
      const body = document.createElement("div");
      body.className = "graph-controls-body";
      for (const group of groups) {
        if (group.holder === "options") {
          for (const node of group.nodes) {
            node.classList.remove("hidden");
            body.appendChild(node);
          }
          continue;
        }
        const holder = document.createElement("div");
        holder.className = "doc-dock-menu-list dock-menu-list";
        for (const node of group.nodes) holder.appendChild(node);
        body.appendChild(holder);
      }
      card.appendChild(body);
    },
    onClose: () => {
      for (const spot of home) spot.parent.insertBefore(spot.node, spot.next);
      if (panel && wasHidden) panel.classList.add("hidden");
      graphSheetClose = null;
      opener?.setAttribute("aria-expanded", "false");
    },
  });
}
