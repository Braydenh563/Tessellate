// whiteboard-map.js: the mind map layer (split out of whiteboard.js on
// 2026-09-24).
//
// What is here: a board with a real tree on it (MINDMAP_PLAN.md §5, from
// Phase 2 on), as one contiguous block moved verbatim out of whiteboard.js:
// the map's kinds, themes, perspectives, focus, metrics and templates; the
// node builder and painter; branch drag and drop, transplant and join; the
// edges (anchors, curves, ribbons, labels, the plus points); editing a map
// (add, outdent, navigate, delete); tidy (Reingold-Tilford with variable
// node sizes); the cross-link tool; the edit strip; the node and link radial
// menus; and the map's chrome, layout and pin-on-drag. No function was
// renamed and none changed.
//
// What stayed in whiteboard.js: the concept map (`wbArrangeMindMap` and the
// `wbMindMap*` helpers just above where this block was, which work on cards
// joined by link sketches, a different data model: see this file's own
// "maps:" section comment), the selection, the object renderer that calls
// into this file, and `initWhiteboard`, which wires the map's controls.
//
// **Loaded in the Library bundle, before whiteboard.js** (`LAZY_MODULES` in
// app.js), for the reason documents-code.js gives: measured with a scope
// analysis of both files, this file's top level reads nothing from
// whiteboard.js (declarations, tables, `window.wbMapState = null` and two
// window listeners that clear this file's own cache), while whiteboard.js's
// top-level wiring names functions defined here. Listed first, every one of
// them exists before whiteboard.js runs.

// --- maps: a board with a real tree on it (MINDMAP_PLAN.md §5, Phase 2) -----
//
// The backend half (§9) already stores, serves and exports all of this. Until
// this section existed the object renderer drew only `image` and `text`, so a
// map's nodes were in the database, in `GET /tree` and in every export except
// the one place anyone would look for them, the canvas. That is the blocker
// §9.3 names, and everything below is the frontend half of it.
//
// **This is not `wbArrangeMindMap` in whiteboard.js.** That is the concept
// map: whiteboard *cards* (a card is a real note) joined by link sketches,
// with a spanning tree inferred by BFS because a link carries no direction. A
// map node is a `WhiteboardObject` with a real `parent_id`, so its tree is
// stored rather than guessed, and a `topic` can exist with no note behind it.
// MINDMAP_PLAN.md §9.2 records why the two data models stayed separate. They
// share a canvas and nothing else, and neither function here calls that one.

//: The object kinds that are map nodes. `topic` is text that lives only on
//: the map; the other four are pointers at library items, drawn with that
//: item's own icon and its *resolved* title, never a copy of it, since a
//: copied title goes stale the moment the note behind it is renamed (§9.2).
const WB_MAP_KINDS = new Set(["topic", "note", "document", "file", "link"]);
const WB_MAP_REFERENCE_KINDS = new Set(["note", "document", "file", "link"]);

//: The Phosphor icon per kind, matching what the same item already shows in
//: the Library: a node has to read as the same object in both places, and
//: picking a second icon for a document here is exactly how it stops doing so.
const WB_MAP_ICONS = {
  topic: "ph-circle",
  note: "ph-note",
  document: "ph-file-text",
  file: "ph-paperclip",
  link: "ph-link-simple",
};

//: How far apart `wbMapTidy` puts things: the gap between two siblings on the
//: breadth axis, and between one depth and the next. Deliberately *not*
//: `MAP_ROW`/`MAP_COL` from routes_whiteboard.py: those are where the server
//: drops a node when nobody said, which only has to be "not on top of its
//: parent"; a tidy layout measures real node sizes and needs only the gap.
const WB_MAP_GAP_BREADTH_BASE = 26;
const WB_MAP_GAP_DEPTH_BASE = 76;
//: **The map's spacing** (theme `spacing`; the owner, 2026-10-10: "the
//: spacing is really close to the other things and bunched up"): Compact,
//: normal (no value) or Roomy, the tidy's two gaps scaled. Read as two
//: names below so every reader of a gap takes the map's.
const WB_MAP_SPACING = Object.freeze({ compact: 0.6, roomy: 1.6 });
function wbMapSpacing() {
  return (wbIsMap() && WB_MAP_SPACING[wbMapTheme().spacing]) || 1;
}
function wbMapGapBreadth() {
  return Math.round(WB_MAP_GAP_BREADTH_BASE * wbMapSpacing());
}
function wbMapGapDepth() {
  return Math.round(WB_MAP_GAP_DEPTH_BASE * wbMapSpacing());
}

//: A node's size when it is not in the DOM, collapsed away, or being laid
//: out before its first paint. Matches `wbMapCreateNode`'s own defaults, so a
//: tidy run immediately after a Tab does not jump when the node then renders.
const WB_MAP_NODE_W = 200;
const WB_MAP_NODE_H = 56;

//: What the open board is, as far as maps are concerned: `{type, layout,
//: labels, crossLinks}`, or `null` on an ordinary whiteboard (which is every
//: board that predates this feature, and stays one).
//:
//: On `window` because library.js's gallery asks too, and a module-level
//: `let` here would be invisible to it, the same reason `window.currentBoardId`
//: lives there rather than here.
window.wbMapState = null;

function wbIsMap() {
  return window.wbMapState?.type === "map";
}

function wbMapLayout() {
  return window.wbMapState?.layout || "free";
}

//: Does a tidy move anything: a laid-out map, or a Free one with a branch
//: that has its own structure (`wbMapStructuredPositions`).
function wbMapLaysOut() {
  return wbMapLayout() !== "free" || (wbState.objects || []).some((o) => o.data?.branch_layout);
}

//: **The map's own look** (MINDMAP_PLAN.md §13e). Ten of the eleven things a
//: topic can be given are set here once for the whole map, and a topic that
//: was never told otherwise follows. `{}` for every map that has never been
//: themed, which is every map made before this existed, so the fast path out
//: of `wbMapThemedData` is the one an unthemed map takes.
//: One frozen empty object rather than a fresh `{}` per call, and a `for
//: ... in` rather than `Object.keys` below, for one reason: this is called
//: once per node and three or four times per edge on every render and every
//: drag frame, and 13a's whole finding was that the drag's cost was per-member
//: work nobody noticed writing. An allocation per edge per frame is exactly
//: that shape.
const WB_MAP_NO_THEME = Object.freeze({});

function wbMapTheme() {
  return window.wbMapState?.theme || WB_MAP_NO_THEME;
}

//: One node's data with the map's theme underneath it: what this topic
//: actually draws, as opposed to what it was told.
//:
//: **The node always wins, and `false` is a value.** This is the whole of the
//: theme's safety: a field the topic carries is left alone, so a map-wide
//: change can never overwrite a choice somebody made. `null`, `undefined` and
//: `""` all mean "nothing was chosen here" (`wbMapSetNodeStyle` writes `null`
//: to unset, and every select in the strip stores `""` as no value at all),
//: while an explicit `false` is somebody saying "not on this one" against a
//: theme that says on: the same three-state `edge_arrow` has always used.
//:
//: Resolved on every read rather than written onto the nodes, which is what
//: makes changing the theme one request instead of one per topic, and what
//: makes it reversible.
function wbMapThemedData(node) {
  const data = node?.data || {};
  const theme = wbMapTheme();
  const look = wbMapLevelLook(node);
  let merged = null;
  //: The level first (decision 40): its own look, else its preset's. Then
  //: the map-wide theme, for a field neither the topic nor its level set.
  for (const field in look) {
    const own = data[field];
    if (own !== undefined && own !== null && own !== "") continue;
    if (!merged) merged = { ...data };
    merged[field] = look[field];
  }
  for (const field in theme) {
    if (WB_MAP_THEME_META.has(field)) continue;
    const own = (merged || data)[field];
    if (own !== undefined && own !== null && own !== "") continue;
    if (!merged) merged = { ...data };
    merged[field] = theme[field];
  }
  return merged || data;
}

//: What this topic would draw for one field if it said nothing: its level's,
//: the map's, or `undefined` for the app's own. The strip's write handlers
//: ask, so that choosing what the topic already draws stores nothing rather
//: than pinning it (`edge_arrow`'s rule, applied to the rest of the strip).
//: `node` defaults to the selected topic, which is the strip's own subject.
function wbMapThemeDefault(field, node = wbSelectedMapNode()) {
  const look = wbMapLevelLook(node);
  if (look[field] !== undefined) return look[field];
  //: A core topic's blank shape is the ellipse, so its strip offers
  //: "As the map draws (ellipse)" and the Rounded pin, as a level's does.
  if (field === "shape" && node?.data?.core) return "ellipse";
  return WB_MAP_THEME_META.has(field) ? undefined : wbMapTheme()[field];
}

// --- levels (MINDMAP_PLAN.md §14, decisions 38 to 40) ------------------------
//
// The owner, INBOX 641: "I'm still not happy on the mindmap with how the core
// nodes work". Measured (`mc1-mapcore-audit.js`): the centre, a main branch
// and a leaf drew at 13.6px, weight 400, 31px tall, identically. A map is a
// hierarchy, and XMind and Coggle both draw it as one before anybody styles
// anything: the centre big and filled, the main branches heavier, the rest
// quiet. So every topic draws as its level unless told otherwise.

//: The two theme keys that are not a look a topic can take: the preset's name
//: and the per-level overrides. Never merged onto a topic's data.
const WB_MAP_THEME_META = new Set(["hierarchy", "levels", "spacing", "rainbow", "legend"]);

//: The seven fields a level can set (the server's `MAP_LEVEL_FIELDS`). `fill`
//: here is `solid`, `tint` or `none`: a level's fill, read by the paint pass
//: only where the topic and its branch said nothing (`wbMapFillOf`).
const WB_MAP_LEVEL_FIELDS = ["font_size", "bold", "italic", "shape", "spine", "fill", "edge_width", "effect"];

//: **The four presets** (decision 39), one look per level: 0 the centre, 1 a
//: main branch, 2 everything deeper and a floating topic. Classic is the
//: default and is stored as no value. Sizes in px for the reason `font_size`
//: already is one: they compose with the strip's own S, L and XL.
const WB_MAP_HIERARCHIES = Object.freeze({
  classic: Object.freeze([
    Object.freeze({ font_size: 22, bold: true, shape: "pill", fill: "solid", spine: "none" }),
    Object.freeze({ font_size: 17, bold: true, fill: "tint", edge_width: "thick" }),
    Object.freeze({}),
  ]),
  //: Coggle's: the centre as Classic, then text sitting on its line.
  outline: Object.freeze([
    Object.freeze({ font_size: 22, bold: true, shape: "pill", fill: "solid", spine: "none" }),
    Object.freeze({ font_size: 17, bold: true, shape: "none", edge_width: "thick" }),
    Object.freeze({ shape: "none" }),
  ]),
  //: XMind's: a filled box per level, lighter with each step down.
  boxed: Object.freeze([
    Object.freeze({ font_size: 22, bold: true, shape: "rect", fill: "solid", spine: "none" }),
    Object.freeze({ font_size: 16, bold: true, fill: "solid", spine: "none", edge_width: "thick" }),
    Object.freeze({ fill: "tint" }),
  ]),
  flat: Object.freeze([WB_MAP_NO_THEME, WB_MAP_NO_THEME, WB_MAP_NO_THEME]),
});

//: The map's mutable state, one object (the global-scope ratchet).
//: `levelById`: each topic's level, from the render's one walk (`wbMapLevels`);
//: a topic not in it (made since the last render) takes no level look until the
//: next. `looksFor` and `looks`: the looks per level for the open map's theme,
//: allocated once per theme rather than once per read (13a: read per topic and
//: per edge on every drag frame). `accentInk`: the ink for the accent, read once
//: per accent (`wbMapAccentInk` keys it), since a computed-style read per topic
//: inside the paint loop would force a style recalculation per topic.
//: `defer`/`cancelAll`: the map's one-shot timers and frames (a rename's focus, the typed-ahead
//: editor, the study bar's focus), kept so a board switch cancels what the old map left in
//: flight (`wbCancelBoardTimers`, audit 1028 B32). `frames` 0 is a timer, n a frame n deep.
const wbMapCache = {
  levelById: new Map(), looksFor: null, looks: null, accentInk: null, accentFor: null,
  pending: new Set(),
  defer(fn, frames = 0) {
    let id = 0;
    const cancel = () => (frames ? cancelAnimationFrame(id) : clearTimeout(id));
    const run = () => {
      this.pending.delete(cancel);
      fn();
    };
    const step = (left) => {
      id = requestAnimationFrame(left > 1 ? () => step(left - 1) : run);
    };
    if (frames) step(frames);
    else id = setTimeout(run);
    this.pending.add(cancel);
  },
  cancelAll() {
    for (const cancel of this.pending) cancel();
    this.pending.clear();
  },
};

//: **The level of every topic** (decision 38). The first root is the centre,
//: as is any root with topics under it; a root with nothing under it is a
//: floating topic and draws as a sub-topic. Its children are main branches;
//: everything below is level 2.
function wbMapLevels(index) {
  const levels = new Map();
  index.roots.forEach((root, i) => {
    const kids = index.childrenOf.get(root.id) || [];
    const top = i === 0 || kids.length ? 0 : 2;
    const walk = (node, level) => {
      if (levels.has(node.id)) return;
      levels.set(node.id, level);
      for (const child of index.childrenOf.get(node.id) || []) walk(child, Math.min(2, level + 1));
    };
    walk(root, top);
  });
  wbMapCache.levelById = levels;
  return levels;
}

function wbMapLevelOf(node) {
  return node ? wbMapCache.levelById.get(node.id) : undefined;
}

function wbMapLevelLooks() {
  const theme = wbMapTheme();
  if (wbMapCache.looksFor === theme && wbMapCache.looks) return wbMapCache.looks;
  const preset = WB_MAP_HIERARCHIES[theme.hierarchy] || WB_MAP_HIERARCHIES.classic;
  const own = theme.levels || {};
  wbMapCache.looks = preset.map((look, level) => {
    const mine = own[String(level)];
    return mine && Object.keys(mine).length ? Object.freeze({ ...look, ...mine }) : look;
  });
  wbMapCache.looksFor = theme;
  return wbMapCache.looks;
}

//: What one topic's level draws, `{}` off a map or before its first render.
function wbMapLevelLook(node) {
  if (!node || !wbIsMap() || !WB_MAP_KINDS.has(node.kind)) return WB_MAP_NO_THEME;
  const level = wbMapLevelOf(node);
  return level === undefined ? WB_MAP_NO_THEME : wbMapLevelLooks()[level] || WB_MAP_NO_THEME;
}

// whiteboard-map-look.js: whiteboard-map-look.js: map topic fill, focus and look helpers. (moved out, L286).
//: **Focus** (§5 item 18, Kumu's): start at one node and reveal the map a
//: step at a time, so a map of two hundred nodes can be read as the six that
//: matter right now.
//:
//: Never persisted, unlike the perspective above: focus is a gesture inside
//: one reading of a map, and coming back tomorrow to a map that only shows
//: four of its nodes, with no memory of having asked for that, is a map that
//: looks broken.
let wbMapFocusState = null;

//: How far focus reaches by default. One step shows the node, its parent and
//: its children, which is the smallest view that still says where you are.
const WB_MAP_FOCUS_DEFAULT_DEPTH = 1;
const WB_MAP_FOCUS_MAX_DEPTH = 6;

//: Everything focus is hiding: every node more than `depth` steps from the
//: focused one, counting parents, children *and* cross-links.
//:
//: Cross-links count because a map's own answer to "what is near this" cannot
//: exclude the edges the user drew to say exactly that; and the walk is a
//: plain breadth-first one over an undirected view of the tree, because
//: "near" is not a direction.
function wbMapFocusHidden(index) {
  const hidden = new Set();
  if (!wbMapFocusState) return hidden;
  const start = index.byId.get(wbMapFocusState.id);
  if (!start) {
    // The focused node was deleted while focus was on. Clearing it here
    // rather than leaving an empty canvas: a view pinned to something that no
    // longer exists shows nothing and explains nothing.
    wbMapFocusState = null;
    return hidden;
  }
  const near = new Map([[start.id, 0]]);
  const queue = [start.id];
  const crossed = new Map();
  for (const link of window.wbMapState?.crossLinks || []) {
    if (!crossed.has(link.from_id)) crossed.set(link.from_id, []);
    if (!crossed.has(link.to_id)) crossed.set(link.to_id, []);
    crossed.get(link.from_id).push(link.to_id);
    crossed.get(link.to_id).push(link.from_id);
  }
  while (queue.length) {
    const id = queue.shift();
    const step = near.get(id);
    if (step >= wbMapFocusState.depth) continue;
    const node = index.byId.get(id);
    const neighbours = [
      ...(index.childrenOf.get(id) || []).map((child) => child.id),
      ...(node?.parent_id != null && index.byId.has(node.parent_id) ? [node.parent_id] : []),
      ...(crossed.get(id) || []),
    ];
    for (const next of neighbours) {
      if (near.has(next) || !index.byId.has(next)) continue;
      near.set(next, step + 1);
      queue.push(next);
    }
  }
  for (const node of index.nodes) {
    if (!near.has(node.id)) hidden.add(node.id);
  }
  return hidden;
}

//: Everything not on screen: a collapsed branch, and whatever focus is
//: holding back. One function so the renderer, the arrow keys and the edge
//: pass cannot disagree about what is visible, which is how a key once moved
//: the selection to a node nobody could see.
function wbMapConcealed(index) {
  // A copy, not the set `wbMapHidden` returned: adding focus's own hidden ids
  // to that one would be this function editing another function's answer.
  const concealed = new Set(wbMapHidden(index));
  for (const id of wbMapFocusHidden(index)) concealed.add(id);
  //: Study's hidden answers (decision 36), a view like focus.
  if (wbStudy.on) for (const id of wbStudy.hidden) concealed.add(id);
  //: Build up's not-yet-shown topics (INBOX 1774), the same kind of view.
  if (wbMapBuild.on) for (const id of wbMapBuild.hidden) concealed.add(id);
  return concealed;
}

function wbMapSetFocus(id, depth = WB_MAP_FOCUS_DEFAULT_DEPTH) {
  const index = wbMapIndex();
  if (!index.byId.has(id)) return;
  wbMapFocusState = { id, depth: Math.max(1, Math.min(WB_MAP_FOCUS_MAX_DEPTH, depth)) };
  wbSyncMapFocusChrome();
  renderWhiteboardNow();
}

function wbMapClearFocus() {
  if (!wbMapFocusState) return;
  wbMapFocusState = null;
  wbSyncMapFocusChrome();
  renderWhiteboardNow();
}

function wbMapStepFocus(by) {
  if (!wbMapFocusState) return;
  wbMapSetFocus(wbMapFocusState.id, wbMapFocusState.depth + by);
}

//: The focus bar: what is focused, how far it reaches, and the way out.
//:
//: Over the canvas rather than in the top bar, beside the gesture hints, for
//: two reasons: the bar is already fifteen controls wide, and a state this
//: strong (most of the map is not being drawn) has to be visible *where the
//: map is*, not in a strip above it that the eye has learned to skip.
function wbSyncMapFocusChrome(passed = null) {
  const bar = document.getElementById("wb-map-focus");
  if (!bar) return;
  if (!wbIsMap() || !wbMapFocusState) {
    bar.hidden = true;
    return;
  }
  const label = document.getElementById("wb-map-focus-label");
  const depth = document.getElementById("wb-map-focus-depth");
  const index = passed || wbMapIndex();
  const node = index.byId.get(wbMapFocusState.id);
  const name = node ? wbMapLabel(node) : "";
  if (label) label.textContent = name.length > 40 ? `${name.slice(0, 39)}…` : name;
  const shown = index.nodes.length - wbMapFocusHidden(index).size;
  if (depth) {
    depth.textContent = `${nounCount(wbMapFocusState.depth, "step")}, ${shown} of ${index.nodes.length} nodes`;
  }
  bar.hidden = false;
}

//: **Map metrics** (§5 item 20), and only the honest ones. Node count, depth
//: and how much of the map stands for something real are facts about this
//: tree; "influence" and the rest of the centrality family need a graph with
//: cycles in it to mean anything, so the one graph measure here is the count
//: of cross-links, which is the thing that makes a map a network at all.
//:
//: An orphan branch is a root that is not the *first* root: a map has one
//: trunk by construction (the creation flow makes one), so a second root is
//: either deliberate or a node that lost its parent, and either way it is
//: worth being told about rather than left to be noticed.
function wbMapStats(index) {
  const facets = wbMapFacets();
  let deepest = 0;
  const depthOf = new Map();
  for (const root of index.roots) {
    const stack = [[root, 1]];
    while (stack.length) {
      const [node, depth] = stack.pop();
      if (depthOf.has(node.id)) continue;
      depthOf.set(node.id, depth);
      deepest = Math.max(deepest, depth);
      for (const child of index.childrenOf.get(node.id) || []) stack.push([child, depth + 1]);
    }
  }
  const references = index.nodes.filter((n) => WB_MAP_REFERENCE_KINDS.has(n.kind));
  const leaves = index.nodes.filter((n) => !(index.childrenOf.get(n.id) || []).length);
  const widest = index.nodes.reduce(
    (best, node) => {
      const kids = (index.childrenOf.get(node.id) || []).length;
      return kids > best.kids ? { node, kids } : best;
    },
    { node: null, kids: 0 }
  );
  const filed = new Set();
  for (const node of index.nodes) {
    const name = facets.get(node.id)?.category;
    if (name) filed.add(name);
  }
  return {
    nodes: index.nodes.length,
    topics: index.nodes.length - references.length,
    references: references.length,
    depth: deepest,
    roots: index.roots.length,
    orphans: Math.max(0, index.roots.length - 1),
    leaves: leaves.length,
    crossLinks: (window.wbMapState?.crossLinks || []).length,
    collapsed: index.nodes.filter((n) => n.data?.collapsed).length,
    categories: filed.size,
    widest: widest.node ? { label: wbMapLabel(widest.node), kids: widest.kids } : null,
  };
}

//: --- the map's own look (MINDMAP_PLAN.md §13e) -----------------------------
//:
//: The owner, INBOX 305: "the customisation features are lacking severely."
//: §13.4 measured what that meant and it was not the topic: a topic has
//: eleven fields, and the map as a whole had none, so every one of the eleven
//: was set one topic at a time and "Reset to branch" on a single node was the
//: only bulk operation of any kind.
//:
//: **Ten fields, and the question that chose them** is asked once of each:
//: does this describe *this topic*, or how *this map* draws topics? An icon,
//: a core mark, a picture, a link out, a line's label and a line's waypoint
//: are the first kind, and a map-wide default for any of them would be a bug
//: rather than a theme. The ten below are the second.
const WB_MAP_THEME_GROUPS = [
  //: The map's own two, which are not a topic's look at all (§13e's
  //: remainder): the palette its branches claim colours from, and the face
  //: its text is set in. Both are names; the server holds the colours.
  {
    label: "The whole map",
    fields: [
      { key: "palette", label: "Branch colours", kind: "select", options: [
        ["", "Classic"], ["deep", "Deep"], ["soft", "Soft"], ["vivid", "Vivid"],
        ["bold", "Bold"], ["paired", "Paired"], ["bright", "Bright"], ["earth", "Earth"],
      ] },
      { key: "font", label: "Font", kind: "select", options: [
        ["", "The app's own"], ["serif", "Serif"], ["mono", "Monospace"], ["wide", "Wide sans"],
      ] },
      { key: "spacing", label: "Spacing", kind: "select", options: [
        ["", "Normal"], ["compact", "Compact"], ["roomy", "Roomy"],
      ] },
      { key: "rainbow", label: "Colour every level", kind: "check" },
      { key: "legend", label: "Show a legend", kind: "check" },
    ],
  },
  {
    label: "Text",
    fields: [
      { key: "font_size", label: "Size", kind: "select", number: true, options: [
        ["", "The app's own"], ["12", "S"], ["19", "L"], ["25", "XL"],
      ] },
      { key: "align", label: "Alignment", kind: "select", options: [
        ["", "The app's own"], ["left", "Left"], ["center", "Centre"], ["right", "Right"],
      ] },
      { key: "bold", label: "Bold", kind: "check" },
      { key: "italic", label: "Italic", kind: "check" },
    ],
  },
  {
    label: "The topic box",
    fields: [
      { key: "shape", label: "Box", kind: "select", options: [
        ["", "Rounded"], ["pill", "Pill"], ["rect", "Box"],
        ["ellipse", "Ellipse"], ["circle", "Circle"], ["hexagon", "Hexagon"],
        ["diamond", "Diamond"], ["cloud", "Cloud"], ["chevron", "Chevron"],
        ["underline", "Underline"], ["none", "Plain"],
      ] },
      { key: "spine", label: "Edge bar", kind: "select", options: [
        ["", "Solid bar"], ["dashed", "Dashed bar"], ["none", "No bar"],
      ] },
    ],
  },
  {
    label: "The branch line",
    fields: [
      { key: "edge_style", label: "Shape", kind: "select", options: [
        ["", "Curved line"], ["elbow", "Elbow line"], ["straight", "Straight line"],
      ] },
      { key: "edge_width", label: "Thickness", kind: "select", options: [
        ["", "Line"], ["thin", "Thin line"], ["thick", "Thick line"],
      ] },
      { key: "edge_dashed", label: "Dashed", kind: "check" },
      { key: "edge_arrow", label: "Arrowhead", kind: "select", options: [
        ["", "As the line draws"], ["on", "Always"], ["off", "Never"],
      ] },
    ],
  },
];

//: Write one patch onto the map's theme and redraw.
//:
//: One request whatever the map's size, because the theme is resolved when a
//: topic is painted rather than written onto every topic: that is what makes
//: it reversible, and what makes a deliberate per-topic choice impossible to
//: overwrite with it.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapSetTheme(...args) {
  return wbRecordGesture(wbMapSetThemeNow, args);
}

async function wbMapSetThemeNow(patch) {
  const boardId = window.currentBoardId;
  if (!boardId || !wbIsMap()) return false;
  try {
    await apiJson(`/whiteboard/boards/${boardId}`, {
      method: "PUT",
      body: JSON.stringify({ theme: patch }),
    });
    const theme = { ...wbMapTheme() };
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === false || value === "") delete theme[key];
      else theme[key] = value;
    }
    window.wbMapState = { ...window.wbMapState, theme };
    //: A palette is a name here and its colours are the server's, so a new
    //: one is read back with the tree rather than looked up in a second copy.
    if ("palette" in patch) await wbRefreshMapState();
    wbApplyMapFont();
    renderWhiteboardNow();
    wbSyncMapLinkStyle();
    //: New gaps mean new places: the whole map, laid out again.
    if ("spacing" in patch && wbMapLayout() !== "free") await wbMapTidy({ quiet: true });
    const selected = wbSelectedMapNode();
    if (selected) wbSyncMapStrip(selected);
    return true;
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "change how this map draws" }), true);
    return false;
  }
}

//: **"Back to the branch" at the map's scope, not a second idea** (§13e).
//: The ring's reset drops one topic's own look so it follows what it
//: inherits; with a theme, what a topic inherits is the map, so the same
//: sentence said about every topic is the bulk operation §13.4 found missing.
//: One endpoint and one transaction, `move-many`'s own reason: a reset that
//: is one request per topic leaves a two-hundred-topic map half done if any
//: one of them fails.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapClearEveryTopic(...args) {
  return wbRecordGesture(wbMapClearEveryTopicNow, args);
}

async function wbMapClearEveryTopicNow() {
  const boardId = window.currentBoardId;
  if (!boardId || !wbIsMap()) return;
  const ok = await confirmDialog(
    "Every topic goes back to following this map, losing the colours, shapes "
    + "and line styles that were set on them one at a time. Pictures stay.",
    { confirmLabel: "Back to the map", cancelLabel: "Leave them" }
  );
  if (!ok) return;
  try {
    const out = await apiJson(`/whiteboard/boards/${boardId}/nodes/clear-style`, { method: "POST" });
    const count = Number(out?.cleared) || 0;
    //: A full re-fetch rather than a patch of `wbState`: the endpoint dropped
    //: a key from every topic's data in one transaction, and the objects this
    //: tab is holding are now wrong about all of them.
    await fetchWhiteboardState();
    renderWhiteboardNow();
    toast(count
      ? `${nounCount(count, "topic")} back to following this map.`
      : "Every topic was already following this map.");
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "reset the topics" }), true);
  }
}

//: The dialog, from the recipe index's own two rows: a `.card.modal-card`
//: through the app's helper (`wbInfoDialog`), a plain `<select>` for a
//: dropdown of values and a `label.setting-check` for an on/off. Nothing new
//: is drawn on the canvas for it: §13b took the topic strip from fourteen
//: controls to five and §13's decision 5 says nothing is added, so this is
//: one row inside the View menu's existing Map section.
//:
//: Every control saves as it is changed, the way the View menu's own
//: background and grid do; there is no OK, because a dialog of looks with an
//: OK asks what you are agreeing to when what you want is to watch the map
//: change behind it.
function wbMapThemeDialog() {
  if (!wbIsMap()) {
    toast("A theme is a map's: this board is a free canvas.");
    return;
  }
  const body = document.createElement("div");
  body.className = "wb-map-theme";
  const lead = document.createElement("p");
  lead.className = "muted wb-map-theme-lead";
  lead.textContent = "Every topic that was never given one of these follows the map.";
  body.appendChild(lead);

  //: **The hierarchy, and which level the rows below set** (MINDMAP_PLAN.md
  //: decisions 39 and 40). XMind's theme has a tab per level; here one row
  //: says whose look the Text, box and line rows are writing: the whole
  //: map's (the ten fields of decision 8) or one level's own. A select, not
  //: the `.seg` of four it was (INBOX 665: four worded choices, "Main
  //: branches" the longest, are a list of values, and a well of them is the
  //: multi-pill the owner asked to be rid of), in the same label column as
  //: every row under it.
  body.appendChild(wbMapThemeSelect({ key: "hierarchy", label: "Hierarchy", kind: "select", options: [
    ["", "Classic"], ["outline", "Outline"], ["boxed", "Boxed"], ["flat", "Flat"],
  ] }));
  const scope = document.createElement("div");
  scope.className = "wb-menu-row wb-map-theme-row wb-map-theme-scope";
  const scopeName = document.createElement("span");
  scopeName.textContent = "Setting";
  const scopeSelect = document.createElement("select");
  scopeSelect.className = "ghost small";
  scopeSelect.setAttribute("aria-label", "Whose look the rows below set");
  for (const [level, words] of [["map", "The whole map"], ["0", "The centre"], ["1", "Main branches"], ["2", "Sub-topics"]]) {
    const option = document.createElement("option");
    option.value = level;
    option.textContent = words;
    scopeSelect.appendChild(option);
  }
  scope.append(scopeName, scopeSelect);
  const rows = document.createElement("div");
  rows.className = "wb-map-theme-rows";
  const show = (level) => {
    rows.replaceChildren(...(level === "map" ? wbMapThemeMapRows() : wbMapThemeLevelRows(Number(level))));
  };
  scopeSelect.addEventListener("change", () => show(scopeSelect.value));
  body.append(scope, rows);
  show("map");

  //: **Saved looks** (L-mindmap-1): the whole theme under a name, kept in `prefs` like the rest of what the board remembers about looking (a look is a preference, not a map's content, so it needs no migration and follows the device). Applying one is a single theme patch, so it is one Undo step; keys the saved look never set are cleared so the map ends up exactly as saved. The server drops anything it does not know, so a look from a newer build degrades instead of failing.
  const looksKey = "wb-map-saved-looks";
  const readLooks = () => prefs.json(looksKey, {});
  const looks = document.createElement("div");
  looks.className = "wb-menu-row wb-map-theme-row wb-map-theme-looks";
  const looksName = document.createElement("span");
  looksName.textContent = "Saved looks";
  const looksSelect = document.createElement("select");
  looksSelect.className = "ghost small";
  looksSelect.setAttribute("aria-label", "Apply a saved look to this map");
  const fillLooks = (picked = "") => {
    const saved = Object.keys(readLooks());
    looksSelect.replaceChildren(...[["", saved.length ? "Choose one to apply" : "None saved yet"], ...saved.map((n) => [n, n])].map(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      return option;
    }));
    looksSelect.value = saved.includes(picked) ? picked : "";
    forgetLook.disabled = !looksSelect.value;
  };
  const saveLook = smallButton("ph:floppy-disk Save this look", "Keep this map's look under a name, to apply to another map", async () => {
    const name = String((await promptDialog("What should this look be called?", "", { confirmLabel: "Save the look" })) ?? "").trim().slice(0, 40);
    if (!name) return;
    const saved = readLooks();
    if (!(name in saved) && Object.keys(saved).length >= 20) {
      toast("Twenty saved looks is the most: forget one first.", "info");
      return;
    }
    saved[name] = JSON.parse(JSON.stringify(wbMapTheme()));
    if (!prefs.setJSON(looksKey, saved)) { toast("This browser would not keep the look.", "info"); return; }
    fillLooks(name);
    toast(`Saved the look "${name}".`);
  });
  const forgetLook = smallButton("ph:trash Forget", "Remove the chosen saved look (maps that use it keep their look)", () => {
    const saved = readLooks();
    const name = looksSelect.value;
    if (!(name in saved)) return;
    delete saved[name];
    prefs.setJSON(looksKey, saved);
    fillLooks();
  });
  looksSelect.addEventListener("change", async () => {
    forgetLook.disabled = !looksSelect.value;
    const look = readLooks()[looksSelect.value];
    if (!look) return;
    const patch = Object.fromEntries(Object.keys(wbMapTheme()).map((key) => [key, null]));
    if (await wbMapSetTheme({ ...patch, ...look })) {
      scopeSelect.value = "map";
      show("map");
      toast(`Applied the look "${looksSelect.value}".`);
    }
  });
  fillLooks();
  looks.append(looksName, looksSelect, saveLook, forgetLook);
  body.insertBefore(looks, body.children[1]);

  const foot = document.createElement("div");
  foot.className = "row wb-map-theme-foot";
  const reset = smallButton(
    "ph:arrow-counter-clockwise Bring every topic back to the map",
    "Drop the look set on each topic one at a time, so they all follow this map",
    () => { close(); wbMapClearEveryTopic(); }
  );
  foot.appendChild(reset);
  body.appendChild(foot);
  const close = wbInfoDialog("How this map looks", body);
}

//: The whole map's rows: decision 8's ten fields and the map's own two.
function wbMapThemeMapRows() {
  const out = [];
  for (const group of WB_MAP_THEME_GROUPS) {
    const head = document.createElement("h4");
    head.className = "setting-subhead";
    head.textContent = group.label;
    out.push(head);
    for (const field of group.fields) {
      out.push(field.kind === "check" ? wbMapThemeCheck(field) : wbMapThemeSelect(field));
    }
  }
  return out;
}

//: **One level's own look** (decision 40): the seven fields a level can set,
//: each a select whose blank row is what the hierarchy draws there, so a
//: level that says nothing is never mistaken for one that says "none".
const WB_MAP_LEVEL_ROWS = [
  { key: "font_size", label: "Size", number: true, options: [["12", "S"], ["14", "M"], ["17", "L"], ["22", "XL"], ["28", "XXL"]] },
  { key: "bold", label: "Bold", bool: true },
  { key: "italic", label: "Italic", bool: true },
  { key: "shape", label: "Box", options: [["rounded", "Rounded"], ["pill", "Pill"], ["rect", "Box"], ["ellipse", "Ellipse"], ["circle", "Circle"], ["hexagon", "Hexagon"], ["diamond", "Diamond"], ["cloud", "Cloud"], ["chevron", "Chevron"], ["underline", "Underline"], ["none", "Plain"]] },
  { key: "spine", label: "Edge bar", options: [["solid", "Solid bar"], ["dashed", "Dashed bar"], ["none", "No bar"]] },
  { key: "fill", label: "Fill", options: [["solid", "Solid colour"], ["tint", "Tinted"], ["none", "No fill"]] },
  { key: "edge_width", label: "Line into it", options: [["thin", "Thin line"], ["normal", "Line"], ["thick", "Thick line"]] },
  { key: "effect", label: "Effect", options: [["shadow", "Shadow"], ["glow", "Glow"], ["none", "No effect"]] },
];

const WB_MAP_LEVEL_NAMES = ["the centre", "the main branches", "the sub-topics"];

function wbMapThemeLevelRows(level) {
  const theme = wbMapTheme();
  const preset = (WB_MAP_HIERARCHIES[theme.hierarchy] || WB_MAP_HIERARCHIES.classic)[level];
  const presetName = { outline: "Outline", boxed: "Boxed", flat: "Flat" }[theme.hierarchy] || "Classic";
  const own = theme.levels?.[String(level)] || {};
  const head = document.createElement("h4");
  head.className = "setting-subhead";
  head.textContent = `How ${WB_MAP_LEVEL_NAMES[level]} look`;
  const out = [head];
  for (const field of WB_MAP_LEVEL_ROWS) {
    //: The centre has no line into it, so nothing to thicken.
    if (level === 0 && field.key === "edge_width") continue;
    const options = field.bool ? [["on", "On"], ["off", "Off"]] : field.options;
    const said = preset[field.key];
    const shown = said === undefined ? "the app's own"
      : field.bool ? (said ? "on" : "off")
        : field.number ? wbMapSizeStepper.say(said)
          : (options.find(([v]) => v === String(said))?.[1] || String(said)).toLowerCase();
    const row = document.createElement("div");
    row.className = "wb-menu-row wb-map-theme-row";
    const name = document.createElement("span");
    name.textContent = field.label;
    const select = document.createElement("select");
    select.className = "ghost small";
    select.setAttribute("aria-label", `${field.label}, for ${WB_MAP_LEVEL_NAMES[level]}`);
    for (const [value, label] of [["", `As ${presetName} draws (${shown})`], ...options]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    }
    const value = own[field.key];
    select.value = value === undefined ? "" : field.bool ? (value ? "on" : "off") : String(value);
    select.addEventListener("change", () => {
      const raw = select.value;
      const next = raw === "" ? null : field.bool ? raw === "on" : field.number ? Number(raw) : raw;
      wbMapSetLevelField(level, field.key, next);
    });
    row.append(name, select);
    out.push(row);
  }
  return out;
}

//: One field of one level's look, written as the whole `levels` set (the
//: server replaces it whole, so the Undo step that puts it back is exact).
function wbMapSetLevelField(level, field, value) {
  const levels = JSON.parse(JSON.stringify(wbMapTheme().levels || {}));
  const look = { ...(levels[String(level)] || {}) };
  if (value === null || value === undefined) delete look[field];
  else look[field] = value;
  if (Object.keys(look).length) levels[String(level)] = look;
  else delete levels[String(level)];
  return wbMapSetTheme({ levels: Object.keys(levels).length ? levels : null });
}

function wbMapThemeSelect(field) {
  //: A `div`, not a `label`, deliberately: `enhanceSelect` leaves the real
  //: `<select>` in the DOM aria-hidden at 1px and draws its own opener beside
  //: it, so a label wrapping one sends the click to the half nobody can see.
  //: The name is on the select itself instead (`aria-label`).
  const row = document.createElement("div");
  row.className = "wb-menu-row wb-map-theme-row";
  const name = document.createElement("span");
  name.textContent = field.label;
  const select = document.createElement("select");
  select.className = "ghost small";
  select.setAttribute("aria-label", `${field.label}, for every topic on this map`);
  for (const [value, label] of field.options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    select.appendChild(option);
  }
  select.value = String(wbMapTheme()[field.key] ?? "");
  select.addEventListener("change", () => {
    const raw = select.value;
    //: `null`, not `""`: the empty option is "this map says nothing", and the
    //: endpoint reads a null as the field being dropped from the theme.
    const value = raw === "" ? null : (field.number ? Number(raw) : raw);
    wbMapSetTheme({ [field.key]: value });
  });
  row.append(name, select);
  return row;
}

function wbMapThemeCheck(field) {
  const row = document.createElement("label");
  row.className = "setting-check wb-map-theme-check";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = Boolean(wbMapTheme()[field.key]);
  const name = document.createElement("span");
  name.textContent = field.label;
  //: `null` rather than `false` when it is turned off, for the reason the
  //: whole theme is a sparse blob: a map that says nothing about a field
  //: draws exactly the map that was drawn before any of this existed.
  box.addEventListener("change", () => {
    wbMapSetTheme({ [field.key]: box.checked ? true : null });
  });
  row.append(box, name);
  return row;
}

function wbShowMapStats() {
  if (!wbIsMap()) {
    toast("Stats are about a map's tree: this board is a free canvas.");
    return;
  }
  const stats = wbMapStats(wbMapIndex());
  wbInfoDialog("What this map is made of", wbMapStatsList(stats));
}

//: The facts as a list: the dialog's body, and the sidebar's This map tab
//: (INBOX 596), one builder so the two never say different things.
//:
//: `tiles` is the sidebar's shape (INBOX 791, the owner: "this side tab looks
//: a little messy"): the seven counts as a grid of number-over-label tiles
//: two across, the two sentences (the widest branch, loose roots) as stacked
//: lines under it, instead of a two-column list whose values wrapped to three
//: lines in 130px. The facts and their words are the same rows.
function wbMapStatsList(stats, { tiles = false } = {}) {
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const rows = [
    ["Nodes", `${stats.nodes} (${stats.references} from the library, ${stats.topics} topics of their own)`, stats.nodes],
    ["Depth", `${plural(stats.depth, "level", "levels")}`, stats.depth],
    ["Ends", `${plural(stats.leaves, "node", "nodes")} with nothing under them`, stats.leaves],
    ["Widest branch", stats.widest ? `${stats.widest.label} (${stats.widest.kids} children)` : "None yet", null],
    ["Cross-links", `${stats.crossLinks}`, stats.crossLinks],
    ["Categories behind it", `${stats.categories}`, stats.categories],
    ["Collapsed", `${stats.collapsed}`, stats.collapsed],
  ];
  if (stats.orphans) {
    rows.push([
      "Loose roots",
      `${plural(stats.orphans, "branch", "branches")} not hanging off the first one`,
      null,
    ]);
  }
  const body = document.createElement(tiles ? "div" : "dl");
  body.className = tiles ? "wb-map-tiles" : "wb-map-stats";
  const counts = document.createElement("dl");
  counts.className = "wb-map-stat-grid";
  for (const [term, value, count] of rows) {
    const name = document.createElement("dt");
    name.textContent = term;
    const said = document.createElement("dd");
    if (!tiles) {
      said.textContent = value;
      body.append(name, said);
      continue;
    }
    if (count === null) {
      //: A sentence, not a count: a line of its own under the grid.
      const line = document.createElement("p");
      line.className = "wb-map-stat-line";
      const label = document.createElement("span");
      label.className = "muted";
      label.textContent = term;
      line.append(label, document.createTextNode(value));
      body.append(line);
      continue;
    }
    const tile = document.createElement("div");
    tile.className = "wb-map-stat";
    tile.title = value;
    name.textContent = term === "Categories behind it" ? "Categories" : term;
    said.textContent = String(count);
    tile.append(said, name);
    counts.append(tile);
  }
  if (tiles) body.prepend(counts);
  return body;
}

//: A read-only dialog: a title, a block of content, one way out.
//:
//: `confirmDialog` is the app's dialog for a *question*, and its shape says
//: so: a sentence and two buttons, one of them destructive by default.
//: Reporting facts through it would put an OK and a Cancel under a table of
//: numbers, which asks the reader what they are agreeing to.
function wbInfoDialog(title, body) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay confirm-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", title);
  const card = document.createElement("div");
  card.className = "card modal-card space-dialog wb-info-card";
  const returnFocus = document.activeElement;
  const close = () => {
    document.removeEventListener("keydown", onKey, true);
    overlay.remove();
    returnFocus?.focus?.();
  };
  const onKey = (event) => {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    close();
  };
  //: The head's X is the one way out (INBOX 548): a filled Close under a
  //: table of facts was a second, louder one.
  card.append(dialogHead(title, close), body);
  overlay.appendChild(card);
  wireBackdropClose(overlay, close);
  document.addEventListener("keydown", onKey, true);
  document.body.appendChild(overlay);
  //: The close, handed back: a dialog whose body holds an action that leads
  //: somewhere else (the map theme's "bring every topic back") has to be able
  //: to get out of the way first, because the confirmation it opens installs
  //: its own capture-phase Escape handler behind this one's.
  return close;
}

//: The three panels, resynced together.
//:
//: Called from the render as well as from `wbSyncMapChrome`, because all three
//: describe the map as it is *now*: the template offer has to go the moment a
//: second node exists, the legend has to grow a row when a node arrives from a
//: category nothing else on the map is filed under, and the focus bar counts
//: nodes. Syncing them only on board load left the offer sitting over a map
//: someone had already started building.
//:
//: `index` is passed in where the caller already has one: `wbMapIndex` walks
//: every object, and the render has just done that.
function wbSyncMapViews(index = null) {
  wbSyncMapFocusChrome(index);
  wbRenderMapLegend(index);
  wbRenderMapTemplates();
  wbSyncMapTemplates(index);
  wbSyncMapEmpty(index);
}

//: The way back from an empty map.
//:
//: Reported: "if i delete all nodes in a mindmap, I cant make more nodes."
//: Measured on the running app before touching anything: a map with zero
//: nodes drew no node to press Tab against, no node to right-click, and the
//: template offer is dismissible for good per board, so a map someone had
//: cleared had no route to a first topic at all.
//:
//: Shown at zero nodes only. At one node the template offer takes over, which
//: is the richer thing to say at that moment, and the two would otherwise
//: stack over the same canvas.
function wbSyncMapEmpty(passed = null) {
  const panel = document.getElementById("wb-map-empty");
  if (!panel) return;
  const index = wbIsMap() ? passed || wbMapIndex() : null;
  panel.hidden = !index || index.nodes.length > 0;
}

function wbMapTemplatesDismissedKey(boardId) {
  return `wbMapTemplatesDone:${boardId}`;
}

//: Shown when the map is still just its root, which is exactly when a
//: starting shape is worth offering and never after.
function wbSyncMapTemplates(passed = null) {
  const panel = document.getElementById("wb-map-templates");
  if (!panel) return;
  const boardId = window.currentBoardId;
  let dismissed = false;
  try {
    dismissed = Boolean(boardId && prefs.get(wbMapTemplatesDismissedKey(boardId), null));
  } catch {
    dismissed = false;
  }
  const index = wbIsMap() ? passed || wbMapIndex() : null;
  // Not while focus is on: they share the strip under the top bar, and a map
  // being read one branch at a time is not a map anyone wants a starting shape
  // for.
  panel.hidden = !index || dismissed || Boolean(wbMapFocusState) || index.nodes.length !== 1;
  wbSyncMapFirstHint(index);
}

//: **The first-open hint, shown once for this browser** (MINDMAP_PLAN §12.5,
//: "the empty map says how to start"; the audit in `archive/agent-remaining/mindmap.md`
//: found six actions reachable only from a ring nobody meets by accident).
//:
//: The lifetime the decision asks for is "gone on the first topic added and
//: never shown again", which is a *browser* flag rather than the templates
//: card's own per-board one: the point of the sentence is to teach that a topic
//: carries a ring, and a person who has built a branch has learned it. So the
//: flag is written the moment any map is seen with more than its root, which is
//: the same event the templates offer withdraws on.
//:
//: Written on the way past rather than on a node-created event on purpose:
//: this runs on every map render, so a map built in another tab, imported from
//: an outline or grown by the agent retires the hint just as a Tab press does.
const WB_MAP_FIRST_HINT_KEY = "wbMapFirstHintDone";

function wbSyncMapFirstHint(index) {
  const hint = document.getElementById("wb-map-first-hint");
  if (!hint) return;
  let done = false;
  try {
    done = Boolean(prefs.get(WB_MAP_FIRST_HINT_KEY, null));
  } catch {
    // A browser that refuses storage shows the hint every time, which is the
    // gentler of the two failures: the alternative is never showing it.
    done = false;
  }
  if (!done && index && index.nodes.length > 1) {
    done = true;
    try {
      prefs.set(WB_MAP_FIRST_HINT_KEY, "1");
    } catch {
      // Same reason as above.
    }
  }
  hint.hidden = done;
}

function wbDismissMapTemplates() {
  try {
    if (window.currentBoardId) {
      prefs.set(wbMapTemplatesDismissedKey(window.currentBoardId), "1");
    }
  } catch {
    // Not remembering the dismissal is a smaller failure than refusing to
    // dismiss it, so this is deliberately silent.
  }
  wbSyncMapTemplates();
}

//: The board's map nodes as a tree, rebuilt from `wbState.objects`.
//:
//: **A node whose parent is not on this board is a root**, which is why this
//: is not a walk down from `parent_id == null`. Same rule as `_build_tree`
//: server-side, for the same reason (§9.1): a stale pointer would otherwise
//: make every node under it vanish from the canvas while still sitting in the
//: database, which is the worst way to lose something.
function wbMapIndex() {
  const nodes = (wbState.objects || []).filter((o) => WB_MAP_KINDS.has(o.kind));
  const byId = new Map(nodes.map((o) => [o.id, o]));
  const childrenOf = new Map();
  const roots = [];
  for (const obj of nodes) {
    const parent = obj.parent_id != null ? byId.get(obj.parent_id) : null;
    if (!parent || parent.id === obj.id) {
      roots.push(obj);
    } else {
      if (!childrenOf.has(parent.id)) childrenOf.set(parent.id, []);
      childrenOf.get(parent.id).push(obj);
    }
  }
  // Sibling order throughout (`wbMapBySiblingOrder`), never the object
  // array's, so two renders of an unchanged map are identical.
  for (const list of childrenOf.values()) list.sort(wbMapBySiblingOrder);
  roots.sort(wbMapBySiblingOrder);
  for (const obj of nodes) obj._leaf = !childrenOf.has(obj.id);
  const index = { nodes, byId, childrenOf, roots };
  wbMapMarkBranchLayouts(index);
  return index;
}

//: **A structure per branch** (XMind; MINDMAP_PLAN "canvasdepth, ranked" row
//: 1): each topic under one whose `data.branch_layout` is set carries that
//: layout as `_bl` and the topic that set it as `_blTop`, the nearest one
//: winning, so the line and bar code reads its own layout without a walk up
//: the tree per line. Transient, like `_fresh`; never saved.
function wbMapMarkBranchLayouts(index) {
  if (!index.nodes.some((o) => o.data?.branch_layout || o._bl)) return;
  const stack = index.roots.map((o) => [o, null, null]);
  while (stack.length) {
    const [node, bl, top] = stack.pop();
    node._bl = bl || undefined;
    node._blTop = top ?? undefined;
    const own = node.data?.branch_layout;
    for (const kid of index.childrenOf.get(node.id) || []) stack.push([kid, own || bl, own ? node.id : top]);
  }
}

//: **A topic's place among its siblings** (INBOX 445; MINDMAP_PLAN §12.0
//: names Ctrl+Shift+arrows for it). Siblings were sorted by id, which made
//: creation order the only order a branch could ever have: Enter on a middle
//: topic put the new one at the end, and nothing could move a topic up. The
//: key is `data.order` when a topic has been placed and its own id when it
//: has not, which is the order every map made before this already had, and
//: the server sorts by the same key (`_sibling_key` in routes_whiteboard.py),
//: so the tree, the exports and the agent's outline agree with the canvas.
function wbMapOrderKey(obj) {
  const order = obj?.data?.order;
  return typeof order === "number" && Number.isFinite(order) ? order : obj.id;
}

function wbMapBySiblingOrder(a, b) {
  return wbMapOrderKey(a) - wbMapOrderKey(b) || a.id - b.id;
}

//: The siblings a topic sits among: its parent's children, or the roots.
function wbMapSiblingsOf(index, node) {
  return node.parent_id != null && index.byId.has(node.parent_id)
    ? index.childrenOf.get(node.parent_id) || []
    : index.roots;
}

//: A key between two neighbours' keys, for a topic placed between them;
//: either side may be missing (the first or the last place).
function wbMapKeyBetween(before, after) {
  if (before && after) return (wbMapOrderKey(before) + wbMapOrderKey(after)) / 2;
  if (before) return wbMapOrderKey(before) + 1;
  if (after) return wbMapOrderKey(after) - 1;
  return null;
}

//: Ctrl+Shift+Up/Down (and Left/Right, for the layouts whose siblings run
//: across): swap a topic with the sibling before or after it. **One undo
//: step for the whole visible change**: the two keys and every position the
//: tidy then moved, compared against a snapshot, because a tidy pushes no
//: undo entry of its own and taking back only the keys would leave two
//: branches drawn in each other's places.
async function wbMapMoveAmongSiblings(id, dir) {
  const index = wbMapIndex();
  const node = index.byId.get(id);
  if (!node) return false;
  const siblings = wbMapSiblingsOf(index, node);
  const at = siblings.findIndex((s) => s.id === id);
  const other = siblings[at + dir];
  if (!other) {
    toast(dir < 0 ? "This topic is already first among its siblings." : "This topic is already last among its siblings.");
    return false;
  }
  const before = new Map(index.nodes.map((o) => [o.id, WB_KIND_INFO.object.payload(o)]));
  const mine = wbMapOrderKey(node);
  const theirs = wbMapOrderKey(other);
  node.data = { ...node.data, order: theirs };
  other.data = { ...other.data, order: mine };
  await Promise.all([wbSaveObject(node), wbSaveObject(other)]);
  if (wbMapLayout() === "free") {
    toast("Moved in the outline. This map's layout is Free, so the canvas stays as it is.");
  } else {
    await wbMapTidyBranch(node.parent_id ?? null);
  }
  renderWhiteboardNow();
  const entries = [];
  for (const obj of wbMapIndex().nodes) {
    const was = before.get(obj.id);
    if (was && (was.x !== obj.x || was.y !== obj.y || was.data !== obj.data)) {
      entries.push({ action: "move", kind: "object", id: obj.id, before: was });
    }
  }
  if (entries.length) wbPushUndo(entries.length === 1 ? entries[0] : { action: "batch", entries });
  return true;
}

//: **Sort a topic's branches** (XMind's "Sort", MindManager's "Sort
//: subtopics"): its children reordered by their words, A to Z or Z to A,
//: numbers read as numbers, so "Step 2" comes before "Step 10". The same
//: `data.order` key the move keys write, so the outline and the exports
//: agree; one Undo step (the name is in `WB_RECORDED`).
async function wbMapSortChildren(id, dir = 1) {
  const index = wbMapIndex();
  const kids = index.childrenOf.get(id) || [];
  if (kids.length < 2) {
    toast("This topic needs at least two branches to sort.");
    return false;
  }
  const word = (o) => String(wbMapLabel(o) || "");
  const sorted = [...kids].sort((x, y) => dir * word(x).localeCompare(word(y), undefined, { numeric: true, sensitivity: "base" }) || x.id - y.id);
  sorted.forEach((kid, at) => { kid.data = { ...kid.data, order: at + 1 }; });
  await wbSaveMany(sorted.map((item) => ({ kind: "object", item })));
  if (wbMapLayout() === "free") toast("Sorted in the outline. This map's layout is Free, so the canvas stays as it is.");
  else await wbMapTidyBranch(id);
  renderWhiteboardNow();
  wbAnnounce(`Branches sorted ${dir > 0 ? "A to Z" : "Z to A"}.`);
  return true;
}

//: Every node reachable from `id`, itself first, deepest last. Seen-guarded
//: for the ring case above; every walk in this section goes through it.
function wbMapSubtree(index, id) {
  const start = index.byId.get(id);
  if (!start) return [];
  const found = [start];
  const seen = new Set([id]);
  for (let i = 0; i < found.length; i += 1) {
    for (const child of index.childrenOf.get(found[i].id) || []) {
      if (seen.has(child.id)) continue;
      seen.add(child.id);
      found.push(child);
    }
  }
  return found;
}

//: Branch colour, which is Coggle's rule: a **first-level** topic takes the
//: next colour of the palette and every descendant inherits it, unless a node
//: carries its own `data.color`, which then becomes what *its* subtree
//: inherits, so recolouring a branch recolours the branch, not one box.
//:
//: The palette is the categorical scale the graph tab already colours its
//: clusters with (`d3.schemeTableau10`, graph.js ~1405), not a new list of
//: hex. Two surfaces colouring "one group of related things" differently is
//: this app's recurring failure, and a map branch and a graph cluster are the
//: same idea seen twice.
//:
//: Computed for the whole board in one walk rather than per node: a node's
//: colour depends on its ancestors, so a per-node lookup would walk the tree
//: once per node to learn what a single walk already knew.
function wbMapColors(index) {
  const palette = wbMapPalette();
  const rainbow = !!wbMapTheme().rainbow;
  //: **Rainbow every level**: the `slot`th colour of the palette that is not the
  //: parent's (`_rainbow_pick` in wb_preview.py is the thumbnail's copy).
  const rainbowPick = (slot, inherited) => {
    const choices = palette.filter((c) => c !== inherited);
    const from = choices.length ? choices : palette;
    return from[slot % from.length];
  };
  const colors = new Map();
  const seen = new Set();
  let branch = 0;
  //: **A branch is as old as its oldest topic** (the owner, 2026-10-10:
  //: "when I added a mindmap node in between, it changed the colour of the
  //: other nodes in the branch"): a topic inserted between a root and its
  //: child is the newest id on the map, and by its own id it went to the end
  //: of the palette, shifting every branch after it. The server's
  //: `_map_branch_colors` orders a root's children the same way.
  const oldest = new Map();
  const ageOf = (node) => {
    if (oldest.has(node.id)) return oldest.get(node.id);
    oldest.set(node.id, node.id);
    let min = node.id;
    for (const child of index.childrenOf.get(node.id) || []) min = Math.min(min, ageOf(child));
    oldest.set(node.id, min);
    return min;
  };
  const walk = (node, inherited, slot = 0, depth = 0) => {
    if (seen.has(node.id)) return;
    seen.add(node.id);
    const picked = !node.data?.color && rainbow && depth > 1 && palette.length ? rainbowPick(slot, inherited) : null;
    const own = node.data?.color || picked || inherited || null;
    colors.set(node.id, own);
    //: Creation order, not sibling order: a branch keeps its colour when it
    //: is moved up or down (INBOX 445), and the Library's thumbnail, which
    //: hands out `MAP_BRANCH_PALETTE` by id on the server, keeps agreeing.
    const kids = [...(index.childrenOf.get(node.id) || [])].sort((a, b) => ageOf(a) - ageOf(b) || a.id - b.id);
    kids.forEach((child, at) => {
      // `inherited == null` is true for exactly one generation, the roots'
      // own children, which *are* the first-level topics. Starting the colours
      // at the root instead would give every branch on the map the same
      // colour, which is the one thing branch colour exists not to do.
      const next = child.data?.color
        || (inherited == null && palette.length ? palette[branch++ % palette.length] : own);
      walk(child, next, at, depth + 1);
    });
  };
  for (const root of [...index.roots].sort((a, b) => a.id - b.id)) walk(root, null);
  return colors;
}

//: **Which topics are filled**, `Map<id, boolean>`, in one walk for the same
//: reason `wbMapColors` is: a fill can come from any ancestor. The owner's
//: ask was "the option to fill an individual node or have it cascade to its
//: children as well", so `data.fill` is `self` (this topic alone), `branch`
//: (this topic and everything under it, including topics added later) or
//: `none` (one topic kept unfilled inside a filled branch; what is under it
//: still belongs to the branch, so the choice touches exactly the box it was
//: made on). No field is no choice: the topic follows its branch.
function wbMapFills(index) {
  const fills = new Map();
  const seen = new Set();
  const walk = (node, inherited) => {
    if (seen.has(node.id)) return;
    seen.add(node.id);
    const own = node.data?.fill;
    //: `solid` (a topic filled in its branch colour, §14) is this topic's
    //: alone; `self` and `branch` are the tint; `none` is an explicit no that
    //: beats a branch above it and a level's fill (`wbMapFillOf`); nothing
    //: said is `undefined`, which is where the level's fill comes in.
    fills.set(node.id, own === "solid" ? "solid"
      : own === "self" || own === "branch" ? "tint"
        : own === "none" ? false : inherited);
    const next = own === "branch" ? "tint" : inherited;
    for (const child of index.childrenOf.get(node.id) || []) walk(child, next);
  };
  for (const root of index.roots) walk(root, undefined);
  return fills;
}

//: The nodes a collapsed branch hides. The collapsed node itself stays, it
//: is the thing you click to get the branch back, and it carries the count
//: badge that says how much is behind it.
function wbMapHidden(index) {
  const hidden = new Set();
  for (const node of index.nodes) {
    if (!node.data?.collapsed) continue;
    for (const descendant of wbMapSubtree(index, node.id)) {
      if (descendant.id !== node.id) hidden.add(descendant.id);
    }
  }
  return hidden;
}

//: What a node is *called*. A topic says what it says; a reference node's
//: label was resolved server-side (`_reference_label`) and arrives in
//: `wbMapState.labels`, with `data.content` as the fallback covering the
//: moment between creating one and the next tree refresh.
function wbMapLabel(obj) {
  if (obj.kind === "topic") return obj.data?.content || "";
  //: A caption the person gave a reference node wins over the item's name
  //: (B38); without one the node still follows the item's name.
  if (obj.data?.caption) return obj.data.caption;
  const resolved = window.wbMapState?.labels?.get(obj.id);
  if (resolved) return resolved;
  return obj.data?.content || `${obj.kind} ${obj.data?.ref_id ?? ""}`.trim();
}

//: `**bold**`, `*italic*` and `` `code` `` inside a node's own text.
//:
//: **Built as DOM nodes, never as an HTML string.** A node's text is the one
//: thing on a map guaranteed to be arbitrary user input, and this app's own
//: rule (and its CSP) says the same thing twice: nothing user-written reaches
//: `innerHTML`. `document.createTextNode` cannot be escaped wrongly because
//: there is no escaping step to get wrong.
//:
//: Inline only. A node label is a phrase, not a document, the full markdown
//: pass (`renderMarkdown`, which a text box reaches through `data.md`) builds
//: paragraphs and headings, which inside a 56px box is a worse answer than no
//: formatting at all.
//:
//: Each alternative is anchored and bounded by a negated class, so there is no
//: nested quantifier for CodeQL's polynomial-ReDoS shape to find.
//: A fourth alternative reads `[text](address)` (L375). Same shape as the others (a negated class on each side, no nested quantifier).
const WB_MAP_INLINE = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`|\[[^\]\n]+\]\([^)\s]+\))/;

function wbMapInlineText(el, raw) {
  if (!el) return;
  el.replaceChildren();
  //: **`$formula$` first** (L-mindmap-2), cut out before the bold, code and link grammar sees it, the way a note's inline text does: the same `INLINE_MATH_RE` rule (no space inside the dollars, "$5 and $10" stays money) and the same TeX-to-MathML drawing as the notes (`mdInlineMathElement`, which asks for the documents bundle itself if it has not loaded and redraws in place). Inline code needed nothing: `code` already draws as a code span above.
  const text = String(raw || "");
  const run = (chunk) => {
    for (const piece of String(chunk || "").split(WB_MAP_INLINE)) {
      if (!piece) continue;
      let tag = null;
      let inner = piece;
      const linked = /^\[([^\]\n]+)\]\(([^)\s]+)\)$/.exec(piece);
      //: A link whose address is not http, https or mailto stays the words it was typed as (L375): the same three schemes as a topic's own link, so a `javascript:` or `data:` address is never made live. The anchor carries the real address (a middle click and the status bar tell the truth), but a plain click only selects, as on any topic: it opens from Ctrl/Cmd or from a topic that was already selected before the press, through `window.open` with `noopener`, the way the Link door does.
      if (linked && WB_MAP_LINK_SCHEMES.test(linked[2])) {
        const anchor = document.createElement("a");
        anchor.className = "wb-map-inline-link";
        anchor.textContent = linked[1];
        anchor.href = linked[2];
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
        let wasSelected = false;
        anchor.addEventListener("pointerdown", () => { wasSelected = !!anchor.closest(".wb-selected"); });
        anchor.addEventListener("click", (ev) => {
          ev.preventDefault();
          if (el.isContentEditable) return;
          if (ev.ctrlKey || ev.metaKey || wasSelected) window.open(linked[2], "_blank", "noopener,noreferrer");
        });
        el.append(anchor);
        continue;
      }
      if (piece.length > 4 && piece.startsWith("**") && piece.endsWith("**")) {
        tag = "strong";
        inner = piece.slice(2, -2);
      } else if (piece.length > 2 && piece.startsWith("*") && piece.endsWith("*")) {
        tag = "em";
        inner = piece.slice(1, -1);
      } else if (piece.length > 2 && piece.startsWith("`") && piece.endsWith("`")) {
        tag = "code";
        inner = piece.slice(1, -1);
      }
      if (!tag) {
        el.append(document.createTextNode(piece));
        continue;
      }
      const marked = document.createElement(tag);
      marked.textContent = inner;
      el.append(marked);
    }
  };
  const math = typeof INLINE_MATH_RE === "undefined" || typeof mdInlineMathElement !== "function" ? null : new RegExp(INLINE_MATH_RE.source, "g");
  let cursor = 0;
  for (let hit = math?.exec(text); hit; hit = math.exec(text)) {
    run(text.slice(cursor, hit.index));
    el.append(mdInlineMathElement(hit[1].trim()));
    cursor = math.lastIndex;
  }
  run(text.slice(cursor));
}

//: **The topic's current object, not the one its handlers were built with.**
//: `wbBuildMapNode` runs once, when a node enters, and its handlers close over
//: that `d`; a state refresh (`fetchWhiteboardState`, an undo, a reload of the
//: board) replaces the object instances and d3 hands the node the new one, but
//: the closures keep the old. The resize grip then read a size the node no
//: longer had (found by `mapstrip.js`: a plain drag after "Back to the branch"
//: put the cleared 25px text size back, and saved the old object's data over
//: the new), and the link and reference doors opened the old target. Looked up
//: by id at the moment of use.
function wbMapLiveDatum(d) {
  return (wbState.objects || []).find((o) => o.id === d.id) || d;
}

//: The static half of a map node, built once as the node enters the DOM.
//:
//: Everything that changes while a map is edited, text, colour, the chevron's
//: direction, the count badge, lives in `wbPaintMapNode` instead, and the
//: chevron and badge are created here *always* and hidden when they have
//: nothing to say. Creating them on demand would mean the enter selection and
//: the update selection each had to know how to build one, which is exactly
//: how the same control ends up drawn two slightly different ways.
function wbBuildMapNode(el, d) {
  el.classed("wb-map-node", true);
  const body = el.append("div").attr("class", "wb-map-node-body");
  //: **A callout over the words** (XMind; canvasdepth2): a row of the card's
  //: own flow, so a tidy measures it and nothing is laid over it. Built for
  //: every topic and hidden while it has none, the icon's rule.
  el.append("div").attr("class", "wb-map-callout").property("hidden", true)
    .on("dblclick", (event) => {
      event.stopPropagation();
      wbMapEditCallout(wbMapLiveDatum(d));
    });
  //: And labels under them (XMind), the next row of the same flow.
  //: Its stamps ride the same row; a press on one toggles yours (a vote, taken
  //: back by a second press), and its menu takes a count down, none of it
  //: starting a drag or the labels' double-click.
  el.append("div").attr("class", "wb-map-tags").property("hidden", true)
    .on("pointerdown", (event) => {
      if (event.target.closest(".wb-map-stamp-wrap")) event.stopPropagation();
    })
    .on("click", (event) => {
      const stamp = event.target.closest(".wb-map-stamp");
      if (event.target.closest(".wb-map-stamp-wrap")) event.stopPropagation();
      if (stamp) wbMapStampSet(wbMapLiveDatum(d), stamp.dataset.stamp, "toggle");
    })
    .on("dblclick", (event) => {
      event.stopPropagation();
      if (!event.target.closest(".wb-map-stamp-wrap")) wbMapEditLabels(wbMapLiveDatum(d));
    });
  //: **Built for every node, hidden when it has nothing to say**, the same
  //: rule the chevron and the count badge already follow here and for the
  //: same reason: a reference node's kind icon and a topic's own chosen icon
  //: (§12.1 item 2) are one element, so the enter selection cannot build one
  //: shape and `wbPaintMapNode` a slightly different one. The class is set in
  //: the paint pass, which is the only place that knows what the node wears.
  //: **A task's box** (MINDMAP_PLAN.md decision 15). Built for every node and
  //: hidden on one that is not a task, the rule the icon beside it follows. A
  //: real checkbox to a screen reader and a real button to the hand: a press
  //: ticks it without starting a node drag or a rename, and the id is read at
  //: the click rather than kept, because the datum this closure saw is
  //: replaced by every state fetch.
  body.append("button")
    .attr("type", "button")
    .attr("class", "wb-map-task")
    .attr("role", "checkbox")
    .property("hidden", true)
    .on("pointerdown", (event) => event.stopPropagation())
    .on("dblclick", (event) => event.stopPropagation())
    .on("click", (event) => {
      event.stopPropagation();
      wbMapToggleTaskDone(d.id);
    })
    .append("i").attr("class", "ph ph-square").attr("aria-hidden", "true");
  //: Markers (decision 34): a row before the icon and the label, filled by
  //: the paint pass and hidden while the topic carries none.
  body.append("span").attr("class", "wb-map-markers").property("hidden", true);
  body.append("i").attr("class", "wb-map-node-icon").attr("aria-hidden", "true");
  //: **A topic whose body is a picture** (MINDMAP_PLAN.md §12.1 item 2's
  //: fourth, Coggle's text/link/image/icon). Built for every node and hidden
  //: when there is nothing to show, the same rule the icon above and the
  //: chevron below already follow, and for the same reason: one element built
  //: one way, rather than the enter selection and the paint pass each knowing
  //: how to make one.
  //:
  //: `alt` is deliberately empty and the element is `aria-hidden`: the topic's
  //: own label is right beside it and says what this node is, so a screen
  //: reader that also announced the picture would say the same thing twice.
  //: A caption nobody wrote is not a description.
  //: **`draggable="false"`, and deliberately no `pointerdown` guard.** The two
  //: look interchangeable and are opposites here. The link button beside this
  //: stops the press because it is a control: pressing it must not also start
  //: a node drag. The picture is the node's *body*, the largest thing to take
  //: hold of on a picture topic, so a stopped press would make the card
  //: undraggable by the part of it anyone would grab. What does have to be
  //: refused is the browser's own image drag, which would otherwise start an
  //: HTML5 drag of the file over a canvas that has a `drop` handler for
  //: exactly that, and that is what this attribute is for.
  body.append("img")
    .attr("class", "wb-map-node-picture")
    .attr("alt", "")
    .attr("aria-hidden", "true")
    .attr("draggable", "false")
    .property("hidden", true);
  //: **The topic's place in the outline** (MINDMAP_PLAN.md decision 17),
  //: "1.2", on a map that numbers its branches. Its own element before the
  //: label rather than text inside it, so a rename never edits it and the
  //: label's editor never sees it. Hidden on a map that does not number and
  //: on a root, which is the map's subject rather than a place in it.
  body.append("span").attr("class", "wb-map-number").attr("aria-hidden", "true").property("hidden", true);
  //: **No `contenteditable="false"` at birth** (FEAT-02's 100ms gate): the
  //: attribute is the default it states, and setting it forced a style
  //: recalculation of the whole map in the middle of building one topic
  //: (traced, `mmd2-1005-maptrace.js`: 28 to 49ms, 1,213 elements, on every
  //: Tab at 301 topics). `wbBeginTextEdit` turns editing on and
  //: `wbEndTextEdit` writes "false" back, which is a topic already drawn.
  const text = body.append("div")
    .attr("class", "wb-map-text");
  //: How many of the tasks under this topic are done (decision 15), "2/5",
  //: hidden on a topic with none under it. Quiet text after the label, not a
  //: pill: a count is a fact about the branch, not a control.
  body.append("span").attr("class", "wb-map-progress").property("hidden", true);
  //: **The marker of a note behind this topic** (MINDMAP_PLAN.md decision
  //: 18). Hidden until there is one, the link marker's rule. A press opens
  //: the note in the help popover's shell, anchored here; the id is read at
  //: the press, as the task box does, because this closure's datum is
  //: replaced by every state fetch.
  body.append("button")
    .attr("type", "button")
    .attr("class", "wb-map-note")
    .attr("aria-haspopup", "dialog")
    .attr("aria-expanded", "false")
    .property("hidden", true)
    .on("pointerdown", (event) => event.stopPropagation())
    .on("dblclick", (event) => event.stopPropagation())
    .on("click", function (event) {
      event.stopPropagation();
      wbMapOpenNote(d.id, this);
    })
    .append("i").attr("class", "ph ph-notepad").attr("aria-hidden", "true");
  //: Where a topic points (§12.1 item 2's "link"). A real button, not a
  //: decoration: the whole point of setting a link is opening it, and a
  //: marker you have to go back to the strip to follow is a label. Hidden
  //: until there is one. `pointerdown` is stopped so following the link is
  //: not also the first frame of a node drag, the same guard the chevron and
  //: the two add buttons below already carry.
  body.append("button")
    .attr("type", "button")
    .attr("class", "wb-map-link")
    .property("hidden", true)
    .on("pointerdown", (event) => event.stopPropagation())
    .on("click", (event) => {
      event.stopPropagation();
      wbMapOpenLink(wbMapLiveDatum(d));
    })
    .append("i").attr("class", "ph ph-link").attr("aria-hidden", "true");

  if (d.kind === "topic") {
    // A topic is renamed in place, through the same two functions a text box
    // uses: one edit path for the board, not two. A reference node has no
    // text of its own to edit: its label belongs to the note behind it, so
    // double-clicking one opens that note instead (below).
    text.on("dblclick", function (event) {
      event.stopPropagation();
      wbBeginTextEdit(this);
    });
    text.on("blur", function () {
      wbEndTextEdit(this);
      //: Trailing blank lines are not part of a name ("Central idea\n\n" was saved, sweep 1028b W16); Enter stays a new line (the owner, 2026-10-10).
      const edited = wbEditedText(this).replace(/\s+$/, "");
      //: **The topic as it is now, by the id the element wears** (INBOX 537):
      //: this closure's `d` is the row from when the node was built, and a
      //: state fetch or an Undo since replaced it; a rename saved through it
      //: wrote stale data, and one left open across an Undo renamed a topic
      //: that was not being edited (measured, `boardundo.js`).
      const live = this.isConnected
        ? (wbState.objects || []).find((o) => String(o.id) === this.closest(".wb-object")?.dataset.id)
        : null;
      if (!live) return;
      //: A rename is undoable like every other change to a topic, and only a
      //: real change is saved or recorded.
      if (live.data.content !== edited) {
        //: **A new topic's first name is part of making it** (audit FEAT-15):
        //: one Undo takes the topic away, as in XMind, rather than first
        //: renaming it back to "New topic". Only while its create is still
        //: the last step: anything done in between keeps the rename its own.
        //: The add is a recorded gesture, so its create is usually inside a
        //: batch with the tidy's moves.
        wbHistoryFor();
        const top = wbUndoStack[wbUndoStack.length - 1];
        const madeIt = (e) => e?.action === "create" && e.kind === "object" && e.id === live.id;
        if (!(live._fresh && (madeIt(top) || (top?.action === "batch" && top.entries.some(madeIt))))) {
          wbPushUndo({ action: "move", kind: "object", id: live.id, before: WB_KIND_INFO.object.payload(live) });
        }
        live.data = { ...live.data, content: edited };
        wbSaveObject(live);
      }
      delete live._fresh;
      // Back to the formatted view: `wbBeginTextEdit` put the raw source in
      // for editing, and without this the markers stay on screen as literal
      // asterisks until something else triggers a render.
      wbMapInlineText(this, live.data.content);
      //: **The keys stay on the map after a name is committed** (audit
      //: FEAT-16): the blur left focus on `<body>`, so a screen reader lost
      //: its place and announced nothing. Back to the canvas, which is where
      //: Tab and Enter already acted, and the name said. Only when nothing
      //: else took the focus: a press on another field keeps it.
      const label = wbMapLabel(live);
      wbMapCache.defer(() => {
        const at = document.activeElement;
        if (at && at !== document.body) return;
        document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
        wbAnnounce(label || "Untitled topic");
      });
    });
    text.on("keydown", function (event) {
      if (!this.isContentEditable) return;
      // While typing, Tab/Enter are text and the branch gestures must not
      // fire: the same `stopPropagation` the card editor above needs, and
      // for the same reason.
      event.stopPropagation();
      //: **Enter is a new line in the name** (the owner, 2026-10-10:
      //: "Pressing enter when typing on a mindmap node makes a new node
      //: instead of a new line"). A topic's name wraps (`pre-wrap`), so a
      //: second line is a real thing to want; plain Enter is the browser's
      //: own line break. The branch gestures stay one key away while typing,
      //: each committing the name first (the blur below saves it): Tab adds
      //: a child, Ctrl+Enter a sibling below, Shift+Enter a sibling above
      //: (the canvas's own Enter and Shift+Enter, MINDMAP_PLAN 3), and
      //: Escape, a press elsewhere or Ctrl+S's blur keep the name.
      const id = Number(this.closest(".wb-object")?.dataset.id);
      if (event.key === "Escape") {
        event.preventDefault();
        this.blur();
      } else if (event.key === "Tab" && !event.shiftKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        this.blur();
        if (id) wbMapAddChild(id);
      } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey || event.shiftKey)) {
        event.preventDefault();
        this.blur();
        if (id) wbMapAddSibling(id, { above: event.shiftKey && !event.ctrlKey && !event.metaKey });
      }
    });
    text.on("pointerdown", function (event) {
      if (this.isContentEditable) event.stopPropagation();
    });
  } else {
    el.on("dblclick", (event) => {
      event.stopPropagation();
      wbMapOpenReference(wbMapLiveDatum(d));
    });
  }

  //: The count badge: how much a collapsed branch is holding. Without it a
  //: collapsed node is indistinguishable from a leaf, which is the difference
  //: between "folded away" and "not there".
  //:
  //: **A button, because §12.1 item 7 says it reopens on click.** It was a
  //: `<span aria-hidden>` and read as a decoration: the number told you
  //: something was folded away and the only way back was the chevron beside
  //: it. As a button it also answers Space and Enter for free once focused,
  //: which is the other half of the same item (and of §12.0's Space
  //: decision).
  el.append("button")
    .attr("type", "button")
    .attr("class", "wb-map-count")
    .property("hidden", true)
    .on("pointerdown", (event) => event.stopPropagation())
    .on("click", (event) => {
      event.stopPropagation();
      wbMapToggleCollapse(d.id);
    });

  // The chevron (collapse) and the `+` (add a child) are the pointer half of
  // the keyboard gestures: `.ghost.small.icon-only`, the app's own tonal
  // icon-button recipe, not a shape invented for the canvas. Both stop
  // `pointerdown` so grabbing one is not also the start of a node drag.
  const stopDrag = (event) => event.stopPropagation();
  el.append("button")
    .attr("type", "button")
    .attr("class", "ghost small icon-only wb-map-collapse")
    .property("hidden", true)
    .on("pointerdown", stopDrag)
    .on("click", (event) => {
      event.stopPropagation();
      wbMapToggleCollapse(d.id);
    })
    .append("i").attr("class", "ph ph-caret-down").attr("aria-hidden", "true");
  //: **One resize grip, on the topic's own corner** (INBOX 610, the owner:
  //: "utility and usability for the mindmap is unintuitive like with
  //: resizing the mindmap nodes, resizing the text"). There were two 16px
  //: glyphs floating above the topic's top left, "Aa" and an arrow pointing
  //: down and right, each a drag: one for the box, one for the words, and the
  //: words grew as the pointer went *down*. Measured in
  //: `scratchpad/ui-sweeps/bm1005-nodetasks.js`: neither was on the corner it
  //: resized from, and dragging "Aa" upwards made the text smaller.
  //:
  //: Now the board's own grip (DESIGN.md, "a grip you drag on a canvas"): a
  //: small filled square on the bottom right corner, shown when the topic is
  //: selected or pointed at, which grows the box the way a card on a board
  //: grows. Held with Shift it scales the words with the box, which keeps
  //: the old grip's "a little bigger than that" without a second control;
  //: the four named sizes are on the topic's bar now, one press each.
  //:
  //: One corner, not the board's eight: the chevron and its count own the
  //: middle of the edge the branch leaves from, and the add buttons hang off
  //: the bottom left. The bottom right is the corner none of them reach on
  //: either layout, measured by the same sweep. It writes width and height
  //: and never x or y (`wbMapStartResizeDrag` says why).
  //:
  //: Plain pointer events with capture, not a d3 drag: `preventDefault` on
  //: `pointerdown` suppresses the compatibility `mousedown` that `objDrag`
  //: listens for, so grabbing the grip cannot also be the first frame of a
  //: node drag. The class is in `objDrag`'s own filter as well.
  el.append("button")
    .attr("type", "button")
    .attr("class", "wb-map-resize-grip")
    .attr("title", "Drag to resize this topic. Hold Shift to scale its text with it")
    .attr("aria-label", "Resize this topic")
    .on("pointerdown", function (event) {
      event.stopPropagation();
      event.preventDefault();
      wbMapStartResizeDrag(this, event, wbMapLiveDatum(d));
    });

  //: **Two ways to grow the map, in one row.** `+` makes a topic; the second
  //: button makes a node that *points at* a real note, document, file or link
  //: (§5 item 11: the half §10.4 recorded as missing: "a reference node was
  //: never placed by hand", so the kind rendered and was unreachable outside
  //: the AI tools).
  //:
  //: A second button rather than a mode on `+`: the two are different acts,
  //: not two settings of one, and a `+` that sometimes opens a dialog is the
  //: "a second modal that only appears after you commit the first" shape
  //: CLAUDE.md records costing five reports on bookmark URLs. Both are also
  //: in the node's context menu, because a right-click is where people look
  //: for "what can I do with this" and these only appear on hover.
  //:
  //: A flex row rather than two absolutely-positioned buttons: two of them
  //: hand-placed off the same corner is how they come to overlap by a few
  //: pixels that a screenshot does not show, which this file has already had
  //: to fix twice for the count badge (see `.wb-map-count`'s own comment).
  const actions = el.append("div").attr("class", "wb-map-actions");
  actions.append("button")
    .attr("type", "button")
    .attr("class", "ghost small icon-only wb-map-add")
    .attr("title", "Add a child (Tab)")
    .attr("aria-label", "Add a child topic")
    .on("pointerdown", stopDrag)
    .on("click", (event) => {
      event.stopPropagation();
      wbMapAddChild(d.id);
    })
    .append("i").attr("class", "ph ph-plus").attr("aria-hidden", "true");
  actions.append("button")
    .attr("type", "button")
    .attr("class", "ghost small icon-only wb-map-ref")
    .attr("title", "Add a child from the library…")
    .attr("aria-label", "Add a child that points at a note, document, file or link")
    .on("pointerdown", stopDrag)
    .on("click", (event) => {
      event.stopPropagation();
      wbMapAddReference(d.id);
    })
    .append("i").attr("class", "ph ph-link-simple").attr("aria-hidden", "true");
}

//: **The ink a core node's label takes on its own fill** (INBOX 201: "I want
//: more and better ways to differentiate core idea nodes in the mindmap", and
//: MINDMAP_PLAN §12.5's decision that a core idea is told apart by shape,
//: weight and size at once).
//:
//: A core node is filled in its branch colour, so its label sits on a
//: saturated surface rather than on the card, and nothing in CSS can work out
//: which of black or white to write on `var(--wb-branch)`: `color-mix` cannot
//: branch on luminance, and a branch colour is a palette entry or anything the
//: colour picker was pointed at. So it is computed here, once per painted
//: node, by WCAG relative luminance.
//:
//: **Pure black and pure white, not the app's ink tokens.** The worst case is
//: a colour exactly at the crossover, where both candidates contrast equally:
//: with 0 and 1 that tie is 4.58:1, over the 4.5 bar, and every softer pair
//: drops it under (a `#0f1115` dark ink brings the same tie to 4.32:1, which
//: is a fail on some part of any palette). On a coloured fill this reads as
//: chart ink rather than as text on a page, which is what it is.
//:
//: The two themes need no second branch: the fill is the same palette entry in
//: both, so the contrast this returns holds in both.
const WB_CORE_INK_DARK = "#000000";
const WB_CORE_INK_LIGHT = "#ffffff";

function wbColourChannels(colour) {
  const value = String(colour || "").trim();
  const hex = value.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const raw = hex[1];
    const wide = raw.length === 3 ? raw.split("").map((c) => c + c).join("") : raw;
    return [0, 2, 4].map((i) => parseInt(wide.slice(i, i + 2), 16));
  }
  const rgb = value.match(/rgba?\(([^)]+)\)/i);
  if (rgb) {
    const parts = rgb[1].split(",").map((n) => parseFloat(n));
    if (parts.length >= 3 && parts.every((n) => Number.isFinite(n))) return parts.slice(0, 3);
  }
  return null;
}

function wbRelativeLuminance(channels) {
  const [r, g, b] = channels.map((c) => {
    const v = Math.min(255, Math.max(0, c)) / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}


//: **Read again only when the accent can have changed** (MINDMAP_PLAN 15,
//: row 4): once per render was a forced style recalculation of the whole tab
//: inside every add's paint (840 elements, the first of three per add at
//: 390). The accent comes from the root's own attributes (the theme, the
//: palette, Settings' custom colour on its style) and the system scheme, so
//: those, read without a style pass, say when to read it again.
function wbMapAccentInk(node) {
  const root = document.documentElement;
  let sig = window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "d" : "l";
  for (const attr of root.attributes) sig += `|${attr.name}=${attr.value}`;
  if (wbMapCache.accentInk == null || wbMapCache.accentFor !== sig) {
    wbMapCache.accentInk = wbCoreInkFor(getComputedStyle(node).getPropertyValue("--accent").trim()) || "";
    wbMapCache.accentFor = sig;
  }
  return wbMapCache.accentInk || null;
}

function wbCoreInkFor(colour) {
  const channels = wbColourChannels(colour);
  if (!channels) return null;
  const l = wbRelativeLuminance(channels);
  const onDark = (l + 0.05) / 0.05;
  const onLight = 1.05 / (l + 0.05);
  return onDark >= onLight ? WB_CORE_INK_DARK : WB_CORE_INK_LIGHT;
}

//: The ink itself when it reads on `bg` at 4.5:1, else the one that does.
function wbReadableInk(ink, bg, min = 4.5) {
  const a = wbColourChannels(ink), b = wbColourChannels(bg);
  if (!a || !b) return ink;
  const la = wbRelativeLuminance(a), lb = wbRelativeLuminance(b);
  const ratio = (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  return ratio >= min ? ink : (wbCoreInkFor(bg) || ink);
}

//: The half that changes: label, branch colour, chevron, badge. Runs for
//: every visible map node on every render, so it does no work that the enter
//: selection could have done once.
function wbPaintMapNode(el, d, index, colors, fills) {
  const node = el.node();
  if (!node) return;
  const text = node.querySelector(".wb-map-text");
  // Never while it is being typed into: a render triggered by something else
  // moving on the board would otherwise replace the caret and the half-typed
  // word: the exact bug `objectUpdate` already avoids for a text box.
  if (text && document.activeElement !== text) {
    wbMapInlineText(text, wbMapLabel(d));
  }

  // A custom property rather than a colour on each part: the fill, the edge
  // and the branch's own edges all derive from one value in CSS, so a
  // recoloured branch cannot end up with a border of the old colour.
  // Set through CSSOM (`style.setProperty`), not a `style=` attribute: the
  // CSP rejects those outright, and thirty-five of them once shipped as
  // silently dead markup (CLAUDE.md).
  const colour = colors?.get(d.id);
  if (colour) node.style.setProperty("--wb-branch", colour);
  else node.style.removeProperty("--wb-branch");
  //: A core node is filled in that colour, so its label needs the ink that
  //: reads on it: see `wbCoreInkFor`. Written for every node rather than only
  //: the core ones, because a node marked core after this pass ran would
  //: otherwise take the previous node's ink until the next render.
  //: A topic with no branch colour (the centre) is filled in the accent, so
  //: its ink is worked out from that (§14: the centre is solid by default).
  const ink = colour ? wbCoreInkFor(colour) : wbMapAccentInk(node);
  if (ink) node.style.setProperty("--wb-core-ink", ink);
  else node.style.removeProperty("--wb-core-ink");

  const children = index?.childrenOf.get(d.id) || [];
  const collapsed = Boolean(d.data?.collapsed);
  const chevron = node.querySelector(".wb-map-collapse");
  if (chevron) {
    chevron.hidden = children.length === 0;
    chevron.title = collapsed ? "Expand this branch" : "Collapse this branch";
    chevron.setAttribute("aria-label", chevron.title);
    chevron.setAttribute("aria-expanded", collapsed ? "false" : "true");
    const icon = chevron.querySelector("i");
    if (icon) icon.className = collapsed ? "ph ph-caret-right" : "ph ph-caret-down";
  }
  const badge = node.querySelector(".wb-map-count");
  if (badge) {
    // The whole subtree, not just the direct children: what the badge is
    // answering is "how much is folded away here", and a branch three deep
    // that reported "2" would be understating itself by an order of magnitude.
    const buried = collapsed && index ? wbMapSubtree(index, d.id).length - 1 : 0;
    badge.hidden = buried <= 0;
    badge.textContent = String(buried);
    const label = `Open the ${nounCount(buried, "topic")} folded in here`;
    badge.title = label;
    badge.setAttribute("aria-label", label);
  }
  el.classed("wb-map-collapsed", collapsed);
  el.classed("wb-map-pinned", Boolean(d.data?.pinned));
  //: The fill (`wbMapFills`): here rather than in `wbPaintMapNodeStyle`
  //: because it can come from an ancestor, which only the render's one walk
  //: of the tree knows.
  //: And a level's fill where neither said anything (decision 39):
  //: `wb-map-solid` is the branch colour with the ink that reads on it.
  const fill = wbMapFillOf(d, fills);
  el.classed("wb-map-filled", fill === "tint");
  el.classed("wb-map-solid", fill === "solid");
  //: Its level, for the stylesheet (padding and the spine a centre has none
  //: of) and for a sweep to read.
  const level = wbMapLevelOf(d);
  if (level === undefined) delete node.dataset.level;
  else node.dataset.level = String(level);
  //: **The spine is on the edge the parent is on** (MINDMAP_PLAN §13e). It is
  //: the left edge in every layout that grows right, the top edge downward
  //: (a class on the view, `wb-map-down`), and the *right* edge for a topic
  //: whose parent is to its right: a bar on the far side from the branch it
  //: belongs to points at nothing, which is the reason the downward case
  //: exists at all. Per node rather than per view, because both-sides has
  //: topics of both kinds on one map.
  const layout = d._bl || wbMapLayout();
  let mirrored = layout === "tree-left";
  if (layout === "tree-both" && index) {
    const parent = index.byId.get(d.parent_id);
    if (parent) mirrored = d.x + (d.width || WB_MAP_NODE_W) / 2 < parent.x + (parent.width || WB_MAP_NODE_W) / 2;
  }
  el.classed("wb-map-node-mirrored", Boolean(mirrored));
  const number = node.querySelector(".wb-map-number");
  if (number) {
    const place = wbMapNumberOf(index, d.id);
    number.hidden = !place;
    number.textContent = place;
  }
  const progress = node.querySelector(".wb-map-progress");
  if (progress) {
    const tally = index ? wbMapTaskTally(index).get(d.id) : null;
    progress.hidden = !tally;
    if (tally) {
      progress.textContent = `${tally.done}/${tally.total}`;
      progress.title = `${tally.done} of ${nounCount(tally.total, "task")} under this topic are done`;
      progress.classList.toggle("wb-map-progress-complete", tally.done === tally.total);
    }
  }
  wbPaintMapNodeStyle(node, d);
}

//: **Every topic's count of the tasks under it** (decision 15), in one walk
//: of the tree per index rather than one walk per topic: the paint pass asks
//: for every visible node on every render, and a subtree walk each would be
//: the per-member cost 13a measured. Kept against the index object, which a
//: render builds once and drops afterwards.
const wbMapTaskTallies = new WeakMap();

function wbMapTaskTally(index) {
  let tallies = wbMapTaskTallies.get(index);
  if (tallies) return tallies;
  tallies = new Map();
  const visit = (node, seen) => {
    let done = 0;
    let total = 0;
    for (const child of index.childrenOf.get(node.id) || []) {
      if (seen.has(child.id)) continue;
      seen.add(child.id);
      const below = visit(child, seen);
      done += below.done;
      total += below.total;
      const task = child.data?.task;
      if (task === "open" || task === "done") {
        total += 1;
        if (task === "done") done += 1;
      }
    }
    if (total) tallies.set(node.id, { done, total });
    return { done, total };
  };
  const seen = new Set();
  for (const root of index.roots) {
    seen.add(root.id);
    visit(root, seen);
  }
  wbMapTaskTallies.set(index, tallies);
  return tallies;
}

//: **Every topic's place in the outline** (decision 17), `id -> "1.2"`, in
//: one walk per index for the reason the task tally is: the paint pass asks
//: for every visible node. A root has none, and each root counts from 1.
//: Sibling order is the index's (`wbMapBySiblingOrder`), which is the
//: server's `_sibling_key`, so the canvas and the exports agree.
const wbMapNumberCache = new WeakMap();

function wbMapNumbers(index) {
  let numbers = wbMapNumberCache.get(index);
  if (numbers) return numbers;
  numbers = new Map();
  const seen = new Set();
  const stack = (index.roots || []).map((root) => ["", root]);
  while (stack.length) {
    const [prefix, node] = stack.pop();
    if (seen.has(node.id)) continue;
    seen.add(node.id);
    const kids = index.childrenOf.get(node.id) || [];
    kids.forEach((child, i) => {
      const place = prefix ? `${prefix}.${i + 1}` : String(i + 1);
      if (!numbers.has(child.id)) numbers.set(child.id, place);
      stack.push([place, child]);
    });
  }
  wbMapNumberCache.set(index, numbers);
  return numbers;
}

//: This topic's number, or "" on a map that does not number its branches.
function wbMapNumberOf(index, id) {
  if (!index || !window.wbMapState?.numbered) return "";
  return wbMapNumbers(index).get(id) || "";
}

//: Turn the numbering on or off for this map: one `PUT`, then a render,
//: because every topic's prefix changes with it.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapSetNumbered(...args) {
  return wbRecordGesture(wbMapSetNumberedNow, args);
}

async function wbMapSetNumberedNow(on) {
  const boardId = window.currentBoardId;
  if (!boardId || !wbIsMap()) return false;
  try {
    await apiJson(`/whiteboard/boards/${boardId}`, {
      method: "PUT",
      body: JSON.stringify({ numbered: Boolean(on) }),
    });
    window.wbMapState = { ...window.wbMapState, numbered: Boolean(on) };
    renderWhiteboardNow();
    wbSyncMapChrome();
    wbAnnounce(on ? "Branches numbered." : "Branches not numbered.");
    return true;
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "change the numbering" }), true);
    wbSyncMapChrome();
    return false;
  }
}

//: **The note behind a topic, shown on demand** (MINDMAP_PLAN.md decision
//: 18). The help popover's shell (`.help-popover`, placed by
//: `placeHelpPopover`), anchored to the marker or, for a topic with no note
//: yet, to the topic: not a new surface and nothing added to the canvas
//: (decision 5). It holds one plain text box and saves when it closes, the
//: theme dialog's rule that there is no OK for something you watch change.
//: Closed by Escape (spent here, so the map does not also deselect), by a
//: press anywhere else, or by opening another board. An emptied note is no
//: note, and the save is one undo step through `wbMapSetNodeStyle`.
let wbMapNoteState = null;

function wbMapOpenNote(id, anchor) {
  const node = (wbState.objects || []).find((o) => o.id === id);
  //: A note node (MINDMAP_PLAN 12.2 item 5, second half) opens the same shell on the
  //: notebook's own text; every other reference kind has no note of its own.
  const entryId = node?.kind === "note" && Number.isInteger(node.data?.ref_id) ? node.data.ref_id : null;
  if (!node || (WB_MAP_REFERENCE_KINDS.has(node.kind) && entryId == null)) return;
  //: The mark is a toggle: pressed again while its note is open, it closes
  //: (and saves) it, as the help popover's own '?' does.
  if (wbMapNoteState?.id === id) {
    wbMapCloseNote();
    return;
  }
  wbMapCloseNote();
  const target = anchor && anchor.isConnected && !anchor.hidden
    ? anchor
    : document.querySelector(`.wb-object[data-id="${id}"]`);
  if (!target) return;
  const panel = document.createElement("div");
  panel.className = "help-popover wb-map-note-peek";
  panel.id = "wb-map-note-peek";
  panel.setAttribute("role", "dialog");
  const label = wbMapLabel(node) || "this topic";
  const said = entryId == null ? `The note behind ${label}` : `The text of ${label}`;
  panel.setAttribute("aria-label", said);
  const box = document.createElement("textarea");
  box.className = "wb-map-note-text";
  box.rows = 6;
  box.maxLength = entryId == null ? 10000 : 200000;
  box.value = typeof node.data?.note === "string" ? node.data.note : "";
  box.placeholder = "Write what this topic needs saying";
  box.setAttribute("aria-label", said);
  const hint = document.createElement("p");
  hint.className = "muted wb-map-note-hint";
  hint.textContent = entryId == null ? "Saved when you close it. Esc closes." : "Saved to the note when you close it. Esc closes.";
  panel.append(box, hint);
  //: Every key typed here is the note's: Tab, Enter and Delete are map
  //: gestures on the canvas, and Escape would also deselect the topic.
  panel.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key === "Escape" || (event.key === "Enter" && (event.ctrlKey || event.metaKey))) {
      event.preventDefault();
      wbMapCloseNote({ restoreFocus: true });
    }
  });
  const outside = (event) => {
    if (panel.contains(event.target) || target.contains(event.target)) return;
    wbMapCloseNote();
  };
  document.addEventListener("pointerdown", outside, true);
  document.body.appendChild(panel);
  wbMapNoteState = { id, panel, anchor: target, outside, before: box.value, entryId, loaded: entryId == null };
  if (target.classList.contains("wb-map-note")) target.setAttribute("aria-expanded", "true");
  placeHelpPopover(panel, target);
  box.focus({ preventScroll: true });
  if (entryId != null) wbMapOpenNote.load(wbMapNoteState, box);
}

// whiteboard-map-notes.js: whiteboard-map-notes.js: map note topics, the note behind a topic and folding. (moved out, L286).
//: Open every folded branch on the map (§12.1 item 7's third route, after the
//: badge and the chevron), saved in one request (`wbSaveMany`, BD2).
async function wbMapExpandAll() {
  const folded = wbMapIndex().nodes.filter((o) => o.data?.collapsed);
  if (!folded.length) {
    toast("Nothing is folded away on this map.");
    return;
  }
  for (const node of folded) node.data = { ...node.data, collapsed: false };
  await wbSaveMany(folded.map((item) => ({ kind: "object", item })));
  renderWhiteboardNow();
  wbSyncMapToolState();
  toast(`Opened ${folded.length} branch${folded.length === 1 ? "" : "es"}.`);
}

//: **Fold to a level** (the features audit, Phase D: "fold-to-level (Alt+1
//: to 9)"; XMind's and MindNode's "show levels"). Alt+N leaves the first N
//: levels of every trunk open and folds each topic at level N that has a
//: branch under it, so a map of two hundred topics reads as its outline at
//: one press and opens a level at a time. Level 1 is the trunks alone. Only
//: the topics whose fold changes are saved, and the whole press is one Undo
//: step (`WB_RECORDED`, whiteboard.js).
async function wbMapFoldToLevel(level) {
  if (!wbIsMap()) return;
  const index = wbMapIndex();
  const changed = [];
  //: **One more or one less level** (INBOX 1774): `{ by: 1 }` opens the
  //: shallowest ring of folded topics, `{ by: -1 }` folds the deepest ring
  //: of open ones, so a ragged map is never re-levelled and a branch opened
  //: by hand is never shut by "more".
  if (level && typeof level === "object") {
    const by = Number(level.by) < 0 ? -1 : 1;
    const ring = wbMapBuild.ring(index, wbMapHidden(index), by);
    if (!ring.ids.length) {
      toast(by > 0 ? "Every level is showing." : "Only the centre is showing.");
      return;
    }
    for (const id of ring.ids) {
      const node = index.byId.get(id);
      node.data = { ...node.data, collapsed: ring.fold };
      changed.push(node);
    }
    await wbSaveMany(changed.map((item) => ({ kind: "object", item })));
    renderWhiteboardNow();
    wbSyncMapToolState();
    const shown = wbMapBuild.levels(index, wbMapHidden(index));
    toast(shown === 1 ? "Showing the trunks only." : `Showing ${shown} levels.`);
    return;
  }
  const want = Math.max(1, Math.min(9, Math.round(Number(level) || 1)));
  const seen = new Set();
  const stack = index.roots.map((root) => [root, 1]);
  while (stack.length) {
    const [node, depth] = stack.pop();
    if (seen.has(node.id)) continue;
    seen.add(node.id);
    const kids = index.childrenOf.get(node.id) || [];
    for (const child of kids) stack.push([child, depth + 1]);
    if (!kids.length) continue;
    const fold = depth >= want;
    if (Boolean(node.data?.collapsed) !== fold) {
      node.data = { ...node.data, collapsed: fold };
      changed.push(node);
    }
  }
  await wbSaveMany(changed.map((item) => ({ kind: "object", item })));
  if (changed.length) {
    renderWhiteboardNow();
    wbSyncMapToolState();
  }
  if (want === 1) toast(changed.length ? `Folded ${changed.length} branch${changed.length === 1 ? "" : "es"}.` : "Every branch is already folded.");
  else toast(`Showing ${want} levels.`);
}

//: **Fold every branch** (INBOX 1773) is `wbMapFoldToLevel(1)`, the twin of
//: Open every folded branch. `open` counts the topics with a branch under
//: them that are open (what a level-1 fold would change); `sync` enables the
//: two twins only when they would change something. Properties, not globals.
wbMapFoldToLevel.open = function foldOpen(index) {
  const map = index || wbMapIndex();
  return map.nodes.filter((n) => !n.data?.collapsed && (map.childrenOf.get(n.id) || []).length).length;
};
wbMapFoldToLevel.sync = function foldSync() {
  if (!wbIsMap()) return;
  const index = wbMapIndex();
  const open = wbMapFoldToLevel.open(index);
  const folded = index.nodes.filter((n) => n.data?.collapsed).length;
  for (const id of ["wb-map-fold-all", "wb-side-map-fold"]) {
    const el = document.getElementById(id);
    if (el) el.disabled = !open;
  }
  for (const id of ["wb-map-expand-all", "wb-side-map-expand"]) {
    const el = document.getElementById(id);
    if (el) el.disabled = !folded;
  }
};

//: --- drag a branch onto a new parent (MINDMAP_PLAN.md §12.1 item 8) --------
//:
//: Three things, and they are one gesture: dragging a topic takes its branch
//: with it, dropping it on another topic re-parents the branch there, and
//: Ctrl held moves the topic alone and lets its children up to its old parent.

//: The whole branch's starting positions, in the shape `wbApplyBulkMove`
//: already understands. Reusing the marquee's own machinery rather than
//: writing a second mover: it already recomputes from a fixed baseline each
//: frame (rather than compounding a delta), and it already keeps each moved
//: node's tree edges and link sketches live, both of which this needs and
//: neither of which is obvious until they are missing.
function wbMapBranchDragOrigin(d, alone) {
  if (alone || !wbIsMap() || !WB_MAP_KINDS.has(d.kind)) return null;
  const index = wbMapIndex();
  const keys = wbMapSubtree(index, d.id)
    .filter((o) => o.id !== d.id)
    .map((o) => wbMultiKey("object", o.id));
  return keys.length ? wbCaptureBulkMoveOrigin(null, keys) : null;
}

//: The topic under the pointer that this branch could be dropped on, or null.
//:
//: **Geometry, not `elementFromPoint`.** The dragged node follows the pointer,
//: so it is the element under it for the whole gesture; the usual answer is to
//: turn its pointer events off mid-drag, which is a second state to get wrong.
//: The board already knows where everything is, so this asks it.
//:
//: A node's own descendants are excluded because dropping a branch inside
//: itself is the ring `/move` refuses, and an offer the server will reject is
//: worse than no offer.
function wbMapDropTargetAt(d, clientX, clientY) {
  const container = document.getElementById("whiteboard-container");
  if (!container || !wbIsMap() || !WB_MAP_KINDS.has(d.kind)) return null;
  //: The one conversion every pointer read shares (`wbClientToBoard`): its
  //: origin is the per-gesture box, not a fresh measurement, since this runs
  //: on every frame of a branch drag after that frame wrote every moved
  //: edge's geometry, and it counts a scaled canvas as the hand-made sum did not.
  const [bx, by] = wbClientToBoard(clientX, clientY);
  const index = wbMapIndex();
  const forbidden = new Set(wbMapSubtree(index, d.id).map((o) => o.id));
  const hidden = wbMapConcealed(index);
  for (const node of index.nodes) {
    if (forbidden.has(node.id) || hidden.has(node.id)) continue;
    const size = wbMapNodeSize(node);
    if (bx >= node.x && bx <= node.x + size.w && by >= node.y && by <= node.y + size.h) {
      return node;
    }
  }
  return null;
}

//: **Reorder by dragging** (XMind, MindNode): a topic let go between two of
//: its siblings, in a layout that stacks them, takes that place, shown while
//: it is held by a line across the gap. The axis the siblings run along, per
//: layout; the rest (radial, Free, the column layouts) keep the drag a pin.
const WB_MAP_SLOT_AXIS = { "tree-right": "y", "tree-left": "y", "tree-both": "y", "logic-right": "y", "tree-down": "x", org: "x" };

//: The gap among its siblings the pointer is in, or null: off the siblings'
//: band, a trunk, or the place it already has.
function wbMapSiblingSlotAt(d, clientX, clientY) {
  if (!wbIsMap() || !WB_MAP_KINDS.has(d.kind)) return null;
  const index = wbMapIndex();
  const node = index.byId.get(d.id);
  const parent = node && index.byId.get(node.parent_id);
  const layout = node?._bl || wbMapLayout();
  const axis = WB_MAP_SLOT_AXIS[layout];
  if (!parent || !axis) return null;
  const [bx, by] = wbClientToBoard(clientX, clientY);
  const point = { x: bx, y: by };
  const box = (o) => ({ ...wbMapNodeSize(o), x: o.x, y: o.y });
  const hidden = wbMapConcealed(index);
  const pc = box(parent).x + box(parent).w / 2;
  const showing = wbMapSiblingsOf(index, node).filter((o) => !hidden.has(o.id));
  //: Both sides of a trunk are one list; the side the pointer is on is the one meant.
  const side = layout === "tree-both" ? showing.filter((o) => o.id === node.id || (o.x + box(o).w / 2 < pc) === (bx < pc)) : showing;
  const [along, size, cross, span] = axis === "y" ? ["y", "h", "x", "w"] : ["x", "w", "y", "h"];
  //: In the order they are drawn, which a laid-out branch shares with its keys.
  //: The dragged one counts from where it was picked up.
  const home = (o) => (o !== node ? o[along] : (along === "y" ? d._dragOriginY : d._dragOriginX) ?? o[along]);
  side.sort((p, q) => home(p) - home(q));
  const others = side.filter((o) => o.id !== node.id);
  if (!others.length) return null;
  const lo = Math.min(...others.map((o) => o[cross])), hi = Math.max(...others.map((o) => o[cross] + box(o)[span]));
  const first = others[0], last = others[others.length - 1];
  const reach = Math.max(...others.map((o) => box(o)[size]));
  if (point[cross] < lo - 24 || point[cross] > hi + 24) return null;
  if (point[along] < first[along] - reach || point[along] > last[along] + box(last)[size] + reach) return null;
  const at = others.filter((o) => o[along] + box(o)[size] / 2 < point[along]).length;
  const before = others[at - 1] || null, after = others[at] || null;
  const mine = side.indexOf(node);
  if ((side[mine - 1] || null) === before && (side[mine + 1] || null) === after) return null;
  const gap = before && after ? (before[along] + box(before)[size] + after[along]) / 2
    : before ? before[along] + box(before)[size] + 8 : after[along] - 8;
  const line = axis === "y" ? { x1: lo, y1: gap, x2: hi, y2: gap } : { x1: gap, y1: lo, x2: gap, y2: hi };
  return { parentId: parent.id, key: wbMapKeyBetween(before, after), line };
}

//: The line across the gap, in the overlay so it draws over the topics.
function wbMapShowSlotCue(slot) {
  let cue = document.getElementById("wb-map-slot-cue");
  if (!slot) {
    cue?.remove();
    return;
  }
  if (!cue) {
    cue = document.createElementNS("http://www.w3.org/2000/svg", "line");
    cue.id = "wb-map-slot-cue";
    cue.setAttribute("class", "wb-map-slot-cue");
    cue.setAttribute("pointer-events", "none");
    document.getElementById("wb-overlay-zoom-group")?.appendChild(cue);
  }
  for (const [k, v] of Object.entries(slot.line)) cue.setAttribute(k, String(v));
}

//: The drop: the topic takes the slot's key, loses a pin it had (it was
//: placed by the layout now), and the branch is laid out again, all one Undo
//: step from where the drag picked it up (`origins`).
async function wbMapDropAmongSiblings(d, slot, origins) {
  const index = wbMapIndex();
  const before = new Map(index.nodes.map((o) => [o.id, WB_KIND_INFO.object.payload(o)]));
  for (const [id, at] of origins) Object.assign(before.get(id) || {}, at);
  const { pinned: _pin, ...rest } = d.data || {};
  d.data = { ...rest, order: slot.key };
  await wbSaveObject(d);
  await wbMapTidy({ onlyBranch: wbMapTidyBranchScope(slot.parentId), quiet: true });
  renderWhiteboardNow();
  const entries = [];
  for (const obj of wbMapIndex().nodes) {
    const was = before.get(obj.id);
    if (was && (was.x !== obj.x || was.y !== obj.y || was.data !== obj.data)) entries.push({ action: "move", kind: "object", id: obj.id, before: was });
  }
  if (entries.length) wbPushUndo(entries.length === 1 ? entries[0] : { action: "batch", entries });
  wbAnnounce("Moved to that place among its siblings.");
}

//: The highlight, and the one place it is cleared. A class rather than an
//: inline style: the CSP rejects `style=` and a drop cue that silently did
//: nothing is the fourth shape CLAUDE.md §6 lists.
let wbMapDropTargetId = null;

function wbMapShowDropTarget(id) {
  if (wbMapDropTargetId === id) return;
  wbMapClearDropTarget();
  if (id == null) return;
  document.querySelector(`.wb-object[data-id="${id}"]`)?.classList.add("wb-map-drop-target");
  wbMapDropTargetId = id;
}

function wbMapClearDropTarget() {
  wbMapShowSlotCue(null);
  if (wbMapDropTargetId == null) return;
  document.querySelector(`.wb-object[data-id="${wbMapDropTargetId}"]`)
    ?.classList.remove("wb-map-drop-target");
  wbMapDropTargetId = null;
}

//: The drop. `alone` is Ctrl held: the topic moves by itself and its children
//: go up to its old parent first, so nothing is orphaned and nothing travels
//: that was not asked for.
//:
//: The node is unpinned on the way: it was dragged, so `wbMapPinOnDrag` would
//: otherwise fix it exactly where the pointer let go, which is the one place
//: it should not stay now that it belongs to a different parent.
//:
//: **Laid out as the new parent's child, branch and all, and one Undo**
//: (INBOX 410: "when I relink or newly link two mindmap nodes, they clump
//: together??"). Measured with `scratchpad/ui-sweeps/maprelink.js`: on a map
//: whose layout is Free the tidy below does nothing, so a dropped branch
//: stayed exactly where the pointer let go of it, on top of the topic it was
//: dropped on, and a joined one stayed wherever it had been; a descendant
//: pinned by an earlier drag kept its old place on every layout, so the branch
//: arrived without it; and none of it could be undone, because `/move` is the
//: only write of `parent_id` and the history had no entry that makes one.
//: `before` is the positions the gesture started from (a drag's own origin),
//: so Undo puts a dragged branch back where it was picked up rather than
//: where it was dropped.
async function wbMapTransplant(d, targetId, alone, { via = "drag", before = null } = {}) {
  const boardId = window.currentBoardId;
  const index = wbMapIndex();
  const target = index.byId.get(targetId);
  if (!boardId || !target) return false;
  if (d.parent_id === targetId && !alone) return false;
  const oldParent = index.byId.has(d.parent_id) ? d.parent_id : null;
  const movedChildren = alone ? [...(index.childrenOf.get(d.id) || [])] : [];
  //: Every topic's row as it stands, for the one history entry at the end:
  //: whatever the layout moves, the undo restores, and nothing else.
  const payload = WB_KIND_INFO.object.payload;
  const rows = new Map(index.nodes.map((node) => {
    const row = payload(node);
    const from = before?.get(node.id);
    return [node.id, from ? { ...row, x: from.x, y: from.y } : row];
  }));
  const move = (id, parentId) => apiJson(
    `/whiteboard/boards/${boardId}/nodes/${id}/move`,
    { method: "PUT", body: JSON.stringify({ parent_id: parentId }) }
  );
  try {
    for (const child of movedChildren) {
      Object.assign(child, await move(child.id, oldParent));
    }
    Object.assign(d, await move(d.id, targetId));
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "move that branch" }), true);
    return false;
  }
  if (d.data?.pinned) {
    d.data = { ...d.data, pinned: false };
    await wbSaveObject(d);
  }
  //: **A branch dropped on a folded topic opens it** (INBOX 537, the owner: "I
  //: moved the separated branch and it straight up disappeared"). Measured
  //: (`boardundo.js`): a loose branch dropped on a folded topic went under it
  //: and was hidden by the fold, which reads as the branch being lost.
  if (target.data?.collapsed) {
    target.data = { ...target.data, collapsed: false };
    await wbSaveObject(target);
  }
  const branch = wbMapSubtree(wbMapIndex(), d.id);
  const landed = new Map(branch.map((node) => [node.id, { x: node.x, y: node.y }]));
  if (wbMapLayout() === "free") {
    await wbMapPlaceAsChild(d, target, branch);
  } else {
    await wbMapTidyBranch(targetId);
    if (oldParent != null) await wbMapTidyBranch(oldParent);
    //: A tidy leaves a pinned topic where it is, which is right for a topic
    //: someone placed inside its own branch and wrong for one whose whole
    //: branch has just moved: it would stay behind. So a pinned descendant
    //: travels by exactly what its moved topic travelled, which keeps the
    //: place it was given relative to it.
    const start = landed.get(d.id);
    const dx = d.x - start.x, dy = d.y - start.y;
    const carry = new Map();
    for (const node of branch) {
      if (node === d || !node.data?.pinned) continue;
      const was = landed.get(node.id);
      if (node.x !== was.x || node.y !== was.y || (!dx && !dy)) continue;
      carry.set(wbMultiKey("object", node.id), { kind: "object", id: node.id, item: node, x: was.x + dx, y: was.y + dy });
    }
    if (carry.size) {
      wbApplyBulkMove(carry, 0, 0);
      await wbSaveBulkMove(carry);
    }
  }
  const history = [{ action: "reparent", kind: "object", id: d.id, parentId: oldParent }];
  for (const child of movedChildren) {
    history.push({ action: "reparent", kind: "object", id: child.id, parentId: d.id });
  }
  for (const node of wbMapIndex().nodes) {
    const row = rows.get(node.id);
    if (!row) continue;
    const pinChanged = (node === d || node === target) && row.data !== node.data;
    if (row.x !== node.x || row.y !== node.y || pinChanged) {
      history.push({ action: "move", kind: "object", id: node.id, before: row });
    }
  }
  wbPushUndo({ action: "batch", entries: history });
  renderWhiteboardNow();
  //: A line drawn between two topics and a branch dragged onto one are the
  //: same move and want different words: the first connected something, the
  //: second moved it.
  //: The outline's Tab says nothing: the row moving in is the answer.
  if (via !== "outline") toast(via === "link"
    ? `Connected to "${wbMapLabel(target)}" as a branch.`
    : alone
      ? `Moved this topic under "${wbMapLabel(target)}", its branches stayed.`
      : `Moved this branch under "${wbMapLabel(target)}".`);
  return true;
}

//: **Where a re-parented branch goes on a Free map** (INBOX 410). Free means
//: the tidy never runs, so this is the one placement a free map gets: the
//: branch is moved as a whole so its topic sits where a topic added under the
//: same parent would, beside the parent and under its last child, or level
//: with the parent when it is the first. The gaps are
//: the tidy's own (`wbMapGapDepth()`, `wbMapGapBreadth()`), so a free map
//: and a tidied one space a branch alike. A free map has no growing side, so
//: "beside" is the right, where the server puts a new child of a topic on a
//: free map too (`_next_position`). "Under its last child" is under that
//: child's whole branch, so the new arrival never lands on a grandchild.
async function wbMapPlaceAsChild(d, target, branch) {
  const index = wbMapIndex();
  const moving = new Set(branch.map((node) => node.id));
  const size = (node) => wbMapNodeSize(node);
  const targetSize = size(target);
  const siblings = (index.childrenOf.get(target.id) || []).filter((node) => !moving.has(node.id));
  let x = target.x + targetSize.w + wbMapGapDepth();
  let y = target.y + (targetSize.h - size(d).h) / 2;
  if (siblings.length) {
    x = Math.min(...siblings.map((node) => node.x));
    let bottom = -Infinity;
    for (const sibling of siblings) {
      for (const node of wbMapSubtree(index, sibling.id)) bottom = Math.max(bottom, node.y + size(node).h);
    }
    y = bottom + wbMapGapBreadth();
  }
  const dx = x - d.x, dy = y - d.y;
  if (!dx && !dy) return;
  const origin = new Map();
  for (const node of branch) {
    origin.set(wbMultiKey("object", node.id), { kind: "object", id: node.id, item: node, x: node.x + dx, y: node.y + dy });
  }
  wbApplyBulkMove(origin, 0, 0);
  await wbSaveBulkMove(origin);
}

//: **A link tool, on a map, joins the tree** (INBOX 180: "I cant properly
//: reconnect things that are disconnected" and "the connections between stuff
//: in the mindmap should be different from the ones in the whiteboard").
//:
//: On a board a link is a drawn connector, and that is the whole of what it
//: is. On a map the connections *are* the structure: a node hanging off
//: nothing is a loose root, the tidy skips it, the outline does not contain
//: it, and collapsing its would-be parent leaves it on screen. Drawing a
//: curve from one topic to it looked like a repair and was not one: it made a
//: cross-link, a decoration over a tree the node still was not part of, which
//: is exactly the "I tried the link tools and they didn't work" report.
//:
//: So a link drawn between two topics, where one of them has no parent, is
//: read as the obvious thing: attach the loose one to the other. Both ends
//: are tried, because a person draws the line in whichever direction they are
//: thinking in. Two nodes that are both already in the tree keep the old
//: behaviour, a cross-link, which is a real thing to want and is already
//: drawn dashed to say it is not the tree.
//:
//: Returns true when it took the gesture, false to let the cross-link happen.
async function wbMapJoinByLink(source, target) {
  const plan = wbMapJoinPlan(source, target);
  if (!plan) return false;
  //: `wbMapTransplant` is the one mover: it moves the branch, unpins the
  //: node, tidies both ends and says what it did. A second copy of that here
  //: is how the two would drift apart.
  return wbMapTransplant(plan.child, plan.parent.id, false, { via: "link" });
}

//: **What a connect drag between two topics will make**, decided without
//: making it: `{parent, child}` when the release joins one to the tree under
//: the other, `null` when it will be a cross-link (or nothing on a map). One
//: function for the drop and for the cue in flight (`wbMapLinkCue`), so the
//: cue cannot promise one kind and the release make the other.
function wbMapJoinPlan(source, target) {
  if (!wbIsMap() || !source || !target) return null;
  if (!WB_MAP_KINDS.has(source.kind) || !WB_MAP_KINDS.has(target.kind)) return null;
  const index = wbMapIndex();
  //: **The map's own first root is in the tree, not loose.** It is the one
  //: node that legitimately has no parent (`wbMapStats` counts every *other*
  //: parentless node as a loose root), so reading "no parent" as "loose"
  //: would have let a line drawn from the root to a branch hang the whole map
  //: under one of its own children.
  const mainRoot = index.roots[0] || null;
  const inTree = (node) => index.byId.has(node.parent_id) || node.id === mainRoot?.id;
  //: A node cannot be adopted by its own descendant: the server's `/move`
  //: refuses the ring, and an offer it will reject is worse than no offer.
  const subtreeOf = (node) => new Set(wbMapSubtree(index, node.id).map((o) => o.id));
  let parent = null;
  let child = null;
  if (!inTree(target) && !subtreeOf(target).has(source.id)) {
    parent = source;
    child = target;
  } else if (!inTree(source) && !subtreeOf(source).has(target.id)) {
    parent = target;
    child = source;
  }
  if (!parent || !child) return null;
  return { parent, child };
}

//: **Which of the two connections a drag is about to make, while it is in
//: flight** (MINDMAP_PLAN §13c's remainder: "nothing says which kind a drag
//: is about to make while it is in flight, only after it lands"). The topic
//: under the pointer wears the answer: the accent ring the branch drag
//: already uses for "lands under this" when the release will join the tree,
//: a dashed muted ring when it will be a cross-link; the preview line is
//: dashed for a cross-link; and the announcer says it in words, once per
//: change. Transient, so decision 5 (nothing added to the resting canvas)
//: holds. Returns the kind, or null when the pointer is not on a topic.
let wbMapLinkCueState = null;

function wbMapLinkCue(source, target) {
  const onTopics = wbIsMap() && source && target
    && WB_MAP_KINDS.has(source.kind) && WB_MAP_KINDS.has(target.kind);
  if (!onTopics) {
    wbMapClearLinkCue();
    return null;
  }
  const plan = wbMapJoinPlan(source, target);
  const kind = plan ? "branch" : "cross-link";
  if (wbMapLinkCueState?.id === target.id && wbMapLinkCueState.kind === kind) return kind;
  wbMapClearLinkCue();
  const el = document.querySelector(`.wb-object[data-id="${target.id}"]`);
  el?.classList.add(plan ? "wb-map-link-cue-branch" : "wb-map-link-cue-cross");
  wbMapLinkCueState = { id: target.id, kind };
  const name = (node) => `"${(wbMapLabel(node) || "Untitled").slice(0, 40)}"`;
  wbAnnounce(plan
    ? `Release to put ${name(plan.child)} under ${name(plan.parent)}.`
    : `Release to cross-link ${name(source)} and ${name(target)}.`);
  return kind;
}

function wbMapClearLinkCue() {
  if (!wbMapLinkCueState) return;
  document.querySelector(`.wb-object[data-id="${wbMapLinkCueState.id}"]`)
    ?.classList.remove("wb-map-link-cue-branch", "wb-map-link-cue-cross");
  wbMapLinkCueState = null;
}

//: Open the library item a reference node stands for. One place, because
//: "double-click opens it" is the whole reason a reference node is different
//: from a topic with the same words in it.
function wbMapOpenReference(d) {
  const refId = d.data?.ref_id;
  if (!refId) return;
  //: `flashEntry` is the app's one door to a note: it switches to Notes,
  //: puts the "browse" sub-tab up, clears the filters that would hide the
  //: target, and scrolls to the card. This named `openEntryEditor`, which no
  //: file defines, and the `typeof` guard meant the failure was silent: a
  //: double-click on a note node fell through to the "open it from the
  //: Library" toast, which is the message for the kinds that have no door.
  if (d.kind === "note" && typeof flashEntry === "function") {
    flashEntry(refId);
    return;
  }
  if (d.kind === "document" && typeof openDocument === "function") {
    openDocument(refId);
    return;
  }
  //: A file opens in the viewer every attachment opens in (an image zoomable,
  //: a document readable); a bookmark opens its address in a new tab, held to
  //: the schemes a link on a page may have (B38: "I cant ... even go to the
  //: thing attached"; both used to send the person away to the Library).
  if (d.kind === "file") {
    openLightbox([{ filename: wbMapLabel(d), getUrl: () => mediaSrc(`/files/${refId}`) }], 0);
    return;
  }
  if (d.kind === "link") {
    apiJson("/bookmarks?limit=1000", { silent: true })
      .then((rows) => {
        const href = String((rows || []).find((row) => row.id === refId)?.url || "").trim();
        if (!WB_MAP_LINK_SCHEMES.test(href)) {
          toast("That bookmark is not a web address.", "info");
          return;
        }
        window.open(href, "_blank", "noopener,noreferrer");
      })
      .catch(() => toast("That bookmark could not be opened.", "info"));
    return;
  }
  toast(`This node points at a ${d.kind}, which has nothing to open here.`, "info");
}

//: A node's drawn size. The DOM first, because a map node is `height: auto`
//: (its text decides how tall it is, so nothing can clip) and the stored
//: `height` column is therefore only ever an approximation of it. Falls back
//: to the stored value, then to the creation defaults, for a node that is not
//: in the DOM at all, collapsed away, or being laid out before first paint.
//:
//: **Measured once per node between renders, not once per edge per frame**
//: (MINDMAP_PLAN.md §13a). Every edge redraw asks this for both of its ends,
//: and a drag redraws every edge of every topic it is carrying, so the two
//: lines below used to run a document-wide attribute query and a layout read
//: a few thousand times inside a single frame. A CPU profile of one 500-topic
//: drag put `querySelector` and this function's own `offsetWidth`/
//: `offsetHeight` reads at the top of the list by a wide margin; nothing else
//: on the drag path came close, and the maths around them was noise.
//:
//: A map node's *size* cannot change without something that also clears this:
//: a render (which rebuilds the element), the size grip (which deletes its
//: own node's entry as it drags), or the end of any gesture. Its *position*
//: changes constantly during a drag and is not cached here, because position
//: is read from the datum, not from the DOM. Only a real measurement is
//: cached: the fallback below is what a node that has not been laid out yet
//: returns, and freezing that would keep the wrong number after first paint.
let wbMapNodeSizeCache = null;

function wbMapNodeSize(d) {
  //: A structured branch's whole block stands in for its root while the map
  //: around it is laid out (`wbMapStructuredPositions`).
  if (d._block) return d._block;
  const size = wbMapNodeSize.measured(d);
  const narrow = wbMapNodeSize.narrow(d);
  return narrow && size.w > narrow ? { w: narrow, h: size.h } : size;
}

//: **A radial map's leaves are drawn narrower** (L373): a leaf is the widest
//: thing on the outer ring, and the ring's arc is spent on box widths, so a
//: 31-topic map of 6 branches of 4 laid out 1927 x 1791 and fitted at 31%.
//: Only an unsized leaf below the centre (`_leaf` is set by `wbMapIndex`);
//: the render writes the same width (`renderWbObjects`), so the layout and the
//: drawn box agree. 0 means the topic keeps its own width.
wbMapNodeSize.narrow = (d) =>
  d._leaf && d.parent_id != null && !d.data?.sized && !d.data?.collapsed && wbMapLayout() === "radial" ? 120 : 0;

wbMapNodeSize.measured = (d) => {
  //: A branch with its own structure, standing in for its whole box while
  //: the map around it is laid out (`wbMapStructuredPositions`).
  if (d._block) return d._block;
  const cached = wbMapNodeSizeCache?.get(d.id);
  if (cached) return cached;
  const el = document.querySelector(`.wb-object[data-id="${d.id}"]`);
  if (el && el.offsetHeight) {
    const size = { w: el.offsetWidth, h: el.offsetHeight };
    if (!wbMapNodeSizeCache) wbMapNodeSizeCache = new Map();
    wbMapNodeSizeCache.set(d.id, size);
    return size;
  }
  return { w: d.width || WB_MAP_NODE_W, h: d.height || WB_MAP_NODE_H };
};

function wbClearMapNodeSizeCache() {
  wbMapNodeSizeCache = null;
}

//: **Every topic's element and box in one pass, for the gesture that is about
//: to want all of them** (MINDMAP_PLAN.md §13a). Picking up a topic with a
//: branch under it needs, on its first frame, the element of every topic it
//: is carrying and the box of both ends of every edge between them: one
//: `querySelector` each is five hundred separate walks of the document, and
//: the first layout read after each of them is a fresh flush. One
//: `querySelectorAll` and one batch of reads is the same information for one
//: walk and one flush, which is what turns the pick-up from a stall into a
//: frame.
//:
//: First element wins, matching what `wbMapNodeSize`'s own `querySelector`
//: would have returned had two layers ever carried the same id. Only real
//: measurements are kept, for the reason `wbMapNodeSize` gives.
//:
//: `linkEndsOnly` measures just the objects a connector ends on, through the item index with no walk
//: of the page: a board's connectors need their ends' boxes and nothing else (W30).
function wbIndexMapNodeElements(linkEndsOnly = false) {
  const byId = new Map();
  if (!wbMapNodeSizeCache) wbMapNodeSizeCache = new Map();
  if (linkEndsOnly) {
    const ends = new Set();
    for (const sketch of wbState.sketches || []) {
      if (typeof sketch.data !== "string" || !sketch.data.includes("link-")) continue;
      try {
        const parsed = JSON.parse(sketch.data);
        if (parsed.sourceKind === "object") ends.add(Number(parsed.sourceId));
        if (parsed.targetKind === "object") ends.add(Number(parsed.targetId));
      } catch { /* not a link */ }
    }
    for (const id of ends) {
      const el = wbItemElement("object", id);
      if (!el || wbMapNodeSizeCache.has(id) || !el.offsetHeight) continue;
      wbMapNodeSizeCache.set(id, { w: el.offsetWidth, h: el.offsetHeight });
    }
    return byId;
  }
  for (const el of document.querySelectorAll(".wb-object[data-id]")) {
    const id = Number(el.dataset.id);
    if (byId.has(id)) continue;
    byId.set(id, el);
    if (!wbMapNodeSizeCache.has(id) && el.offsetHeight) {
      wbMapNodeSizeCache.set(id, { w: el.offsetWidth, h: el.offsetHeight });
    }
  }
  return byId;
}

//: One node's measurement dropped, for the gesture that is changing that one
//: node's box while it runs (the size grip). Clearing the whole cache there
//: would put the board-wide re-measure back into every frame of a resize.
function wbForgetMapNodeSize(id) {
  wbMapNodeSizeCache?.delete(id);
}

// Every drag ends in one of these, whichever element it started on, and the
// same two events already clear the alignment guides' own box cache.
window.addEventListener("pointerup", wbClearMapNodeSizeCache, true);
window.addEventListener("pointercancel", wbClearMapNodeSizeCache, true);

//: Where an edge leaves its parent and where it meets its child, by layout, 
//: right/left for a map that grows sideways, bottom/top for one that grows
//: down. `radial` and `free` have no fixed direction, so the axis is chosen
//: per edge from whichever delta is larger, which is what makes a radial map's
//: edges leave a node on the side the child is actually on.
//: A topic dragged beside its parent in a map that grows down: a line out of
//: the parent's bottom into the child's top would double back (the owner,
//: 2026-10-26: "refuses to connect to the side"), so it joins side to side.
//: Only when the two are about level; a level of a tree is always further apart.
function wbMapBesideParent(parent, p, child, c) {
  const gapX = Math.max(child.x - (parent.x + p.w), parent.x - (child.x + c.w));
  const gapY = Math.max(child.y - (parent.y + p.h), parent.y - (child.y + c.h));
  return gapX > 0 && gapY < Math.min(p.h, c.h) / 2;
}

// whiteboard-map-edges.js: whiteboard-map-edges.js: map line geometry, ribbons, edge paths and their paint. (moved out, L286).
//: One edge's geometry written onto the elements it already has.
//:
//: **A custom property, not a `stroke` attribute**, and the difference is the
//: whole branch-colour feature. `.wb-map-edge` declares `stroke` in
//: 07-whiteboard-misc.css, and a presentation attribute is a declaration at
//: the bottom of the cascade, below every author rule however unspecific: so
//: the attribute was dead markup and every edge on every map drew in the
//: accent. Measured on a five-edge map: three distinct `stroke` attributes
//: from the branch palette, one computed colour, `rgb(70, 100, 240)`, which
//: is `--accent`. `tests/test_svg_paint_attributes.py` is the lint that found
//: it, and `el.style` sits above the stylesheet where the attribute sat
//: below. Removed as well as set, which a rebuilt element never had to do:
//: a branch that loses its colour has to lose it on the line too.
//: **A line's label follows the pointer, in board units.** The first
//: version rode d3-drag's `dx`, which is measured in the edge layer's SVG
//: space; that layer is scaled by the board's CSS zoom, which Chromium's
//: `getScreenCTM` does not see, so at any zoom but 1x the label ran ahead of
//: or behind the hand (owner: "it goes a bit off my mouse"). It also stopped
//: only the mouse event, after the canvas had already taken the pointerdown
//: and started a selection box. This takes the pointer itself: the screen
//: delta divided by the zoom, captured so a fast drag cannot lose it, and a
//: stopped pointerdown so nothing behind the label reacts. One undo step,
//: through `wbMapSetNodeStyle`, on release.
function wbWireEdgeLabelDrag(text, wrap) {
  text.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    const childId = Number(wrap.querySelector(".wb-map-edge")?.dataset.child);
    const node = wbMapIndex().byId.get(childId);
    if (!node) return;
    event.stopPropagation();
    event.preventDefault();
    const container = document.getElementById("whiteboard-container");
    const k = d3.zoomTransform(container).k || 1;
    const startX = event.clientX;
    const startY = event.clientY;
    const fromDx = Number(node.data?.edge_label_dx) || 0;
    const fromDy = Number(node.data?.edge_label_dy) || 0;
    const baseX = Number(text.getAttribute("x")) - fromDx;
    const baseY = Number(text.getAttribute("y")) - fromDy;
    let dx = fromDx;
    let dy = fromDy;
    text.setPointerCapture(event.pointerId);
    text.classList.add("is-dragging");
    const move = (e) => {
      dx = fromDx + (e.clientX - startX) / k;
      dy = fromDy + (e.clientY - startY) / k;
      text.setAttribute("x", String(baseX + dx));
      text.setAttribute("y", String(baseY + dy));
    };
    const done = async () => {
      text.removeEventListener("pointermove", move);
      text.removeEventListener("pointerup", done);
      text.removeEventListener("pointercancel", done);
      text.classList.remove("is-dragging");
      if (Math.round(dx) === fromDx && Math.round(dy) === fromDy) return;
      await wbMapSetNodeStyle(node, { edge_label_dx: Math.round(dx), edge_label_dy: Math.round(dy) });
      wbScheduleRender();
    };
    text.addEventListener("pointermove", move);
    text.addEventListener("pointerup", done);
    text.addEventListener("pointercancel", done);
  });
}

function wbMapEdgeApply(wrap, geom) {
  //: By class, not by position: the group's order is the hit test's (the
  //: invisible twin has to sit above the visible line), so reaching for a
  //: child by index here would tie this to that order for no reason.
  const path = wrap.querySelector("path.wb-map-edge");
  path.setAttribute("class", geom.className);
  path.setAttribute("d", geom.d);
  if (geom.colour) path.style.setProperty("--wb-map-edge-colour", geom.colour);
  else path.style.removeProperty("--wb-map-edge-colour");
  const hit = wrap.querySelector(".wb-map-edge-hit");
  hit.setAttribute("d", geom.line);
  const handle = wrap.querySelector(".wb-map-edge-handle");
  handle.setAttribute("cx", String(geom.grip.x));
  handle.setAttribute("cy", String(geom.grip.y));
  wbMapPlaceEdgeEnds(path, geom.ends);
  for (const grip of path._wbEnds || []) {
    if (geom.colour) grip.style.setProperty("--wb-map-edge-colour", geom.colour);
    else grip.style.removeProperty("--wb-map-edge-colour");
  }
  if (geom.colour) handle.style.setProperty("--wb-map-edge-colour", geom.colour);
  else handle.style.removeProperty("--wb-map-edge-colour");
  let text = wrap.querySelector(".wb-map-edge-label");
  if (!geom.label) {
    text?.remove();
    return;
  }
  if (!text) {
    text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("class", "wb-map-edge-label");
    //: The two ends, which is how `wbMapEdgeContext` finds it again.
    text.dataset.parent = path.dataset.parent;
    text.dataset.child = path.dataset.child;
    //: Centred on the line's own midpoint (INBOX 818), where it was 0.4em
    //: above it; the card-coloured halo is what lets it read on the line.
    text.setAttribute("dominant-baseline", "central");
    // bounding-box creates a solid hit area matching the text's box, preventing mis-clicks
    text.style.pointerEvents = "bounding-box";
    text.style.cursor = "move";
    text.addEventListener("dblclick", (e) => {
      e.stopPropagation();
      const childId = Number(wrap.querySelector(".wb-map-edge").dataset.child);
      if (childId) wbMapLabelEdge(childId);
    });

    wbWireEdgeLabelDrag(text, wrap);

    wrap.appendChild(text);
  }
  text.setAttribute("x", String(geom.lx));
  text.setAttribute("y", String(geom.ly));
  text.textContent = geom.label;
  const [size, bold, ink, chip] = geom.look.split("|");
  text.style.fontSize = size ? `${size}px` : "";
  text.style.fontWeight = bold ? "700" : "";
  text.style.fill = ink;
  text.classList.toggle("wb-map-edge-label-chip", Boolean(chip));
}

//: Where the mid-line `+` sits: a short step along the line from the handle,
//: towards the child, so a line's two controls are side by side on it rather
//: than one on top of the other (see `WB_MAP_EDGE_CONTROL_GAP`).
//:
//: Along the line and not merely along the chord: the step is taken down the
//: curve's own tangent at its middle, the elbow's own crossing leg, or the
//: kinked straight line's second half, so the `+` stays on the line it
//: inserts into whatever shape that line is and however far it has been bent.
//: On a line too short to hold both, the step shrinks rather than running the
//: `+` off the end.
function wbMapEdgePlusPoint(parent, child, layout) {
  const a = wbMapEdgeAnchors(parent, child, layout);
  const style = wbMapEdgeStyle(child);
  const middle = wbMapEdgeHandlePoint(parent, child, layout);
  let dx;
  let dy;
  let room = Math.hypot(a.x2 - a.x1, a.y2 - a.y1);
  if (style === "elbow") {
    // The leg the turn sits on, which is the one that crosses the edge's axis.
    dx = a.horizontal ? 0 : a.x2 - a.x1;
    dy = a.horizontal ? a.y2 - a.y1 : 0;
    if (a.pinned) {
      //: The leg the handle is on, read off the corners themselves.
      const pts = wbMapElbowPoints(a, wbMapEdgeWaypoint(a, child));
      dx = pts[2].x - pts[1].x;
      dy = pts[2].y - pts[1].y;
    }
    room = Math.hypot(dx, dy);
  } else if (style === "straight") {
    const w = wbMapEdgeWaypoint(a, child);
    dx = a.x2 - w.x;
    dy = a.y2 - w.y;
  } else {
    const c = wbMapEdgeCubic(a, child);
    const tangent = wbMapCubicAt(0.5, c.p0, c.c0, c.c1, c.p1);
    dx = tangent.dx;
    dy = tangent.dy;
  }
  // Two siblings at the same height make a horizontal elbow with no crossing
  // leg at all: the line is straight, and the step goes along it instead.
  if (!dx && !dy) {
    dx = a.x2 - a.x1;
    dy = a.y2 - a.y1;
    room = Math.hypot(dx, dy);
  }
  const len = Math.hypot(dx, dy) || 1;
  const step = Math.min(WB_MAP_EDGE_CONTROL_GAP, room * 0.35);
  return { x: middle.x + (dx / len) * step, y: middle.y + (dy / len) * step };
}

//: **A `+` at the middle of every line, to put a topic between two others**
//: (MINDMAP_PLAN.md §12.1 item 5, Coggle's own mid-point add). The other half
//: of that item, the `+` at the far end of a branch, is the node's own
//: `.wb-map-add` and has been there since Phase 2.
//:
//: Drawn in `#wb-html-layer` rather than in the edge group, and that is the
//: whole reason this is a separate pass: the layer carries the same pan and
//: zoom the edges do, so a button placed at board coordinates lands on the
//: line and scales with it, *and* it can be a real `button.ghost.small
//: .icon-only` from the app's own ramp instead of a shape drawn in SVG that
//: would be a control nothing else in the app looks like.
//:
//: Invisible until the pointer is on it (CSS), which is what keeps a map of
//: two hundred lines from being a map of two hundred buttons.
function wbRenderMapEdgePluses(edges, layout, only = null) {
  const host = document.getElementById("wb-html-layer");
  if (!host) return;
  let layer = host.querySelector(".wb-map-plus-layer");
  if (!wbIsMap()) {
    layer?.remove();
    return;
  }
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "wb-map-plus-layer";
    host.appendChild(layer);
  }
  //: **Kept, keyed by their two ends, and moved rather than rebuilt**
  //: (FEAT-02's 100ms gate). Every render threw away a button per line and
  //: built it again with its icon and four listeners: 300 created and 300
  //: removed on every Tab at 301 topics, each a style recalculation, which
  //: the selection bar's read then paid for (traced: 33 to 60ms, 2,100
  //: elements). Now a button is built once per line, placed when its line's
  //: middle moved, and the layer reordered only where the tree's order and
  //: the layer's disagree (`mapstrip.js` pairs the first line with the first
  //: `+`).
  const cache = layer._wbPluses instanceof Map ? layer._wbPluses : (layer._wbPluses = new Map());
  //: Stale buttons out first, for `wbRenderMapEdges`'s reason.
  wbMapDropStale(cache, new Set(edges.map((edge) => edge.key)));
  edges.forEach(({ parent, child, key }, slot) => {
    let button = cache.get(key);
    if (!(only && button && !only.has(parent.id) && !only.has(child.id))) {
      const middle = wbMapEdgePlusPoint(parent, child, layout);
      if (!button) cache.set(key, (button = wbMapEdgePlusButton(parent.id, child.id)));
      button.style.left = `${middle.x - 12}px`;
      button.style.top = `${middle.y - 12}px`;
    }
    if (layer.childNodes[slot] !== button) layer.insertBefore(button, layer.childNodes[slot] || null);
  });
}

//: One mid-line `+`, built once for the line between two topics.
function wbMapEdgePlusButton(parentId, childId) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ghost small icon-only wb-map-edge-plus";
  // The two ends, so `wbSyncMapEdgeHandles` can stand this button aside
  // for the waypoint handle, which lives at the same point on the line.
  button.dataset.parent = String(parentId);
  button.dataset.child = String(childId);
  button.title = "Put a topic between these two";
  button.setAttribute("aria-label", "Put a topic between these two");
  // Placed by `wbRenderMapEdgePluses`: half the button's own 1.5rem off
  // the *line's* middle, not the anchors' (a bent line, §12.1 item 5's
  // third, no longer passes through the halfway point between its ends),
  // in board units, which is what this layer is measured in.
  const glyph = document.createElement("i");
  glyph.className = "ph ph-plus";
  glyph.setAttribute("aria-hidden", "true");
  button.appendChild(glyph);
  button.addEventListener("pointerdown", (event) => event.stopPropagation());
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    wbMapInsertBetween(parentId, childId);
  });
  //: **It sits exactly where you would right-click the line**, so it has
  //: to pass that gesture on. Found by the sweep the moment this landed:
  //: the link ring stopped opening at a line's middle, because an
  //: invisible button was in front of the hit stroke and a right-click on
  //: a button is not a click. Forwarding it means the whole line answers
  //: the same gesture, middle included.
  button.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    event.stopPropagation();
    wbOpenMapLinkRadial(childId, event.clientX, event.clientY);
  });
  //: And the hold, for the same reason: a finger has no second button, so
  //: the button that sits on the line's middle has to answer the line's
  //: own gesture there too. `wireLongPress` (navigation.js) is the app's one
  //: hold, and it swallows the click the lift makes, which this button's
  //: own click (insert a topic here) would otherwise run the moment the
  //: ring opened.
  wireLongPress(button, (event, point) => wbOpenMapLinkRadial(childId, point.x, point.y));
  return button;
}

//: Put a new topic between a parent and one of its children: the new topic
//: takes the parent, and the child takes the new topic.
//:
//: Two steps, and the second is a `/move` rather than a create-with-parent,
//: because the child already exists and `parent_id` is only writable through
//: the endpoint that runs the cycle check. The new topic opens for typing
//: like every other add on this map.
//:
//: **One Undo step that puts the child back** (INBOX 537: the create was in
//: history and the move was not, so Ctrl+Z deleted the new topic and left
//: the child's branch with no parent, cut off from the map). The batch
//: replays in order: the child goes back under its parent, then the new
//: topic goes, then every topic the tidy moved returns to where it was.
async function wbMapInsertBetween(parentId, childId) {
  const boardId = window.currentBoardId;
  if (!boardId) return;
  const payload = WB_KIND_INFO.object.payload;
  const rows = new Map(wbMapIndex().nodes.map((n) => [n.id, payload(n)]));
  const created = await wbMapCreateNode({ parentId });
  if (!created) return;
  //: `wbMapCreateNode` pushed its own create entry; this gesture is one step.
  const top = wbUndoStack[wbUndoStack.length - 1];
  if (top?.action === "create" && top.id === created.id) wbUndoStack.pop();
  const history = [];
  const child = (wbState.objects || []).find((o) => o.id === childId);
  //: **It takes its child's place** (the owner, 2026-10-10: "when I added a
  //: mindmap node in between, it changed the colour of the other nodes in the
  //: branch and the spacing is really close"): the child's spot, so the
  //: both-sides split keeps the branch on its side and the tidy opens the
  //: gap from where the branch was, and its slot among the siblings, so the
  //: branch does not jump to the end of the list.
  if (child) {
    created.x = child.x;
    created.y = child.y;
    created.data = { ...created.data, order: wbMapOrderKey(child) };
    await wbSaveObject(created);
  }
  if (child) {
    try {
      const moved = await apiJson(`/whiteboard/boards/${boardId}/nodes/${childId}/move`, {
        method: "PUT",
        body: JSON.stringify({ parent_id: created.id }),
      });
      Object.assign(child, moved);
      history.push({ action: "reparent", kind: "object", id: childId, parentId });
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "move that topic under the new one" }), true);
    }
  }
  history.push({ action: "create", kind: "object", id: created.id });
  selectWbItem("object", created.id);
  await wbMapTidyBranch(parentId);
  for (const node of wbMapIndex().nodes) {
    const row = rows.get(node.id);
    if (row && (row.x !== node.x || row.y !== node.y)) {
      history.push({ action: "move", kind: "object", id: node.id, before: row });
    }
  }
  wbPushUndo({ action: "batch", entries: history });
  renderWhiteboardNow();
  wbMapEditNode(created.id);
}

// --- editing a map ----------------------------------------------------------
//
// Obsidian Canvas Mindmap's set (§5 item 5), which is the de-facto standard:
// Tab is a child, Enter a sibling, Shift+Tab outdents, the arrows walk the
// tree, F2 renames and Delete takes the subtree. The point of copying it
// rather than inventing one is that these are the gestures that make a mind
// map fast; dragging boxes one at a time is a drawing tool with a tree drawn
// on it.

//: The selected object, if it is a map node on a map. Everything keyboard
//: below goes through this rather than reading `wbSelectedItem` directly, so
//: "am I editing a map right now" is decided in one place.
function wbSelectedMapNode() {
  if (!wbIsMap() || wbSelectedItem?.kind !== "object") return null;
  const obj = (wbState.objects || []).find((o) => o.id === wbSelectedItem.id);
  return obj && WB_MAP_KINDS.has(obj.kind) ? obj : null;
}

//: Add one node, letting the **server** place it (§9.3: "Omit `x`/`y` and the
//: server places it"). A client that invents coordinates gets them wrong, and
//: gets them wrong differently from the AI tools and the OPML import, which is
//: how one map ends up looking like three tools' opinions of a map.
//: What a topic is called before you have called it anything.
//:
//: **Not an empty string**, which is what the first version created and what
//: looking at the result showed the problem with: five nodes on screen, four
//: of them blank white boxes with no way to tell a node you had not named yet
//: from a rendering fault. `wbMindMapAddCard` above reached the same
//: conclusion for the concept map and calls its own "New branch"; the label is
//: selected on creation, so the first keystroke replaces it either way.
const WB_MAP_NEW_TOPIC = "New topic";

async function wbMapCreateNode({ parentId = null, kind = "topic", text = WB_MAP_NEW_TOPIC, refId = null } = {}) {
  const boardId = window.currentBoardId;
  if (!boardId) return null;
  const body = { kind, parent_id: parentId, text };
  if (refId != null) body.ref_id = refId;
  try {
    const created = await apiJson(`/whiteboard/boards/${boardId}/nodes`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    wbState.objects = wbState.objects || [];
    wbState.objects.push(created);
    wbPushUndo({ action: "create", kind: "object", id: created.id });
    return created;
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "add that node" }), true);
    return null;
  }
}

//: Add a child of `parentId`, select it, tidy its branch and open it for
//: typing. **A new branch is an empty thought, so it opens ready to be typed**
//:, the same rule (and the same wording) the concept map's own branch gesture
//: follows further up this file; a node that makes you go and find the way to
//: name it is the difference between a mind-mapping tool and a diagram editor.
//: **What is typed while a new topic is on its way is the topic's text**
//: (INBOX 445). Tab and Enter make the topic on the server before its editor
//: opens, 130ms at the median and 300ms at p95 on a sixty-topic map
//: (wbmapaudit.js), and every key typed in that window went to the canvas as
//: a shortcut: measured, "First branch" typed straight after Tab saved as "st
//: branch", the F having turned on focus mode on the way. The keys are held
//: here (`wbMapCatchTypeahead`, called first by the board's key handler, and
//: `wbOwnsChord`, which keeps the app's own shortcuts off them) and written
//: into the editor when it opens.
let wbMapTypeahead = null;

//: Two seconds at most: a create that failed somewhere this file did not
//: foresee must not leave every key on the board swallowed.
const WB_MAP_TYPEAHEAD_MS = 2000;

function wbMapTypeaheadLive() {
  if (wbMapTypeahead && performance.now() - wbMapTypeahead.at > WB_MAP_TYPEAHEAD_MS) wbMapTypeahead = null;
  return Boolean(wbMapTypeahead);
}

//: **Enter in that window is the Enter that ends the name** (measured
//: 2026-10-04: Tab, "First branch", Enter typed at speed saved two empty
//: topics, because the Enter reached the map's own Enter and added a sibling
//: before the first topic's editor had opened, and the sibling's create then
//: started a fresh, empty typeahead). It is held as `commit`, and the editor
//: closes on the typed text as soon as it opens. Keys after it are swallowed
//: rather than appended: they were typed after the name was finished, and a
//: shortcut fired from them would act on a topic that is not there yet.
//: Since 2026-10-10 Enter in the editor is a line break (the owner: "Pressing
//: enter when typing on a mindmap node makes a new node instead of a new
//: line"), so an Enter typed ahead is one too, and Escape is the key held
//: as `commit`, the editor's own way to end a name.
function wbMapCatchTypeahead(e) {
  if (!wbMapTypeaheadLive() || e.ctrlKey || e.metaKey || e.altKey) return false;
  if (e.key === "Escape") {
    e.preventDefault();
    wbMapTypeahead.commit = true;
    return true;
  }
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!wbMapTypeahead.commit) wbMapTypeahead.text += "\n";
    return true;
  }
  if (e.key.length !== 1) return false;
  e.preventDefault();
  if (!wbMapTypeahead.commit) wbMapTypeahead.text += e.key;
  return true;
}

//: **A new topic is on the canvas and open for typing before the server has
//: answered** (audit FEAT-02, 2026-10-05). Tab used to wait for the POST,
//: then tidy and render the whole map, then wait for the tidy's save, then
//: render the whole map again: 830 to 2,000ms from the key to an editable
//: topic at 300 topics, measured, and growing with the map. Now the topic is
//: made here as a provisional row with a negative id, laid out by the same
//: tidy (positions only, applied as transforms), drawn by one render, and
//: opened for typing; the POST, the order, the tidy's save and the Undo step
//: follow in the background (`wbMapAdoptProvisional`). A save that reaches
//: the topic first waits for its real id (`wbSaveObject`), and a child added
//: under it waits for the same thing here.
let wbMapProvisionalSeq = 0;

async function wbMapAddChild(parentId, { order = null } = {}) {
  const boardId = window.currentBoardId;
  if (!boardId) return null;
  wbMapTypeahead = { text: "", at: performance.now() };
  let parent = parentId != null ? (wbState.objects || []).find((o) => o.id === parentId) : null;
  if (parent?._creating) {
    if (!(await parent._creating)) {
      wbMapTypeahead = null;
      return null;
    }
    parentId = parent.id;
  }
  if (parentId != null && !parent) parent = (wbState.objects || []).find((o) => o.id === parentId) || null;
  const created = {
    id: -(++wbMapProvisionalSeq),
    board_id: boardId,
    kind: "topic",
    parent_id: parent ? parent.id : null,
    x: 0,
    y: 0,
    z: 1,
    //: The server's own default width; the height is the text's, measured by
    //: the render.
    width: WB_MAP_NODE_W,
    height: null,
    rotation: null,
    data: { content: WB_MAP_NEW_TOPIC, ...(order != null ? { order } : {}) },
    //: The first rename is part of making it: one Undo step, not two
    //: (audit FEAT-15). Cleared by the label's first commit.
    _fresh: true,
  };
  wbState.objects = wbState.objects || [];
  wbMapFreshPlace(created, parent);
  wbState.objects.push(created);
  // Expanding first: adding a child to a collapsed node would otherwise put
  // the new node straight into the hidden set, so the gesture would appear to
  // do nothing at all.
  const expand = Boolean(parent?.data?.collapsed);
  if (expand) parent.data = { ...parent.data, collapsed: false };
  //: The branch laid out without a render or a save of its own: the one
  //: render below draws it, and the save goes after the create.
  const origin = wbMapTidyBranchPlan(parentId, created);
  //: **The new places as data only** (FEAT-02's 100ms gate): the render
  //: right below writes every moved topic's transform and every line, after
  //: its measure, so writing them here as well was the same work twice and
  //: left the whole moved map dirty for the measure's first read. A plan that
  //: carries a drawn line (a cross-link) is applied in full, as before.
  if (origin && [...origin.values()].every((entry) => entry.kind !== "sketch")) {
    for (const entry of origin.values()) {
      entry.item.x = entry.x;
      entry.item.y = entry.y;
    }
    wbScheduleCull();
  } else if (origin) wbApplyBulkMove(origin, 0, 0);
  const undo = { action: "create", kind: "object", id: created.id };
  wbPushUndo(undo);
  wbAddGate.barDeferred = true;
  wbAddGate.renderHold = { moves: [], edges: false };
  try {
    renderWhiteboardNow();
    selectWbItem("object", created.id);
    wbMapEditNode(created.id, { now: true });
    wbMapRevealTopic(created);
  } finally {
    wbRenderRelease();
    wbSyncMapEdgeHandles();
    wbAddGate.barDeferred = false;
  }
  created._creating = wbMapAdoptProvisional(created, { expand: expand ? parent : null, origin, order });
  //: The editor is already open; what waits here is the caller, so a caller
  //: that uses the topic it gets back (a script, the recorded gesture's
  //: after-snapshot) gets it with its real id, or null when it was refused.
  return (await created._creating) ? created : null;
}

//: **Text pasted onto a map becomes a branch** (audit FEAT-09, 2026-10-05:
//: a nested list pasted onto a selected topic did nothing, 4 topics before
//: and after). XMind, MindNode and SimpleMind all take an indented list this
//: way. Under the selected topic, or as new trunks with none; one line per
//: topic, nested by indentation, read by the server's outline reader (the
//: Markdown import's), made in one transaction and recorded as one Undo
//: step. Ctrl+V reaches here only when nothing was copied on the board
//: itself (the board's key handler lets the browser's paste through then).
async function wbMapPasteText(text) {
  const boardId = window.currentBoardId;
  if (!boardId || !text.trim()) return 0;
  const node = wbSelectedMapNode();
  let made;
  try {
    made = await apiJson(`/whiteboard/boards/${boardId}/nodes/outline`, {
      method: "POST",
      body: JSON.stringify({ parent_id: node ? node.id : null, text: text.slice(0, 200000) }),
    });
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "paste that onto the map" }), true);
    return 0;
  }
  wbState.objects = [...(wbState.objects || []), ...made];
  if (node?.data?.collapsed) {
    node.data = { ...node.data, collapsed: false };
    await wbSaveObject(node);
  }
  renderWhiteboardNow();
  if (wbMapLayout() !== "free") await wbMapTidy({ onlyBranch: wbMapTidyBranchScope(node ? node.id : null), quiet: true });
  if (made[0]) selectWbItem("object", made[0].id);
  const n = made.length;
  wbAnnounce(`Pasted ${nounCount(n, "topic")}`);
  return n;
}

document.addEventListener("paste", (event) => {
  if (event.defaultPrevented || typeof wbIsMap !== "function" || !wbIsMap()) return;
  const canvas = document.getElementById("whiteboard-container");
  if (!canvas?.getClientRects().length) return;
  const target = event.target;
  if (target?.closest?.("input, textarea, select, [contenteditable='true'], [contenteditable='plaintext-only'], dialog, .modal-overlay")) return;
  const data = event.clipboardData;
  if (!data || [...(data.items || [])].some((item) => item.kind === "file")) return;
  const text = data.getData("text/plain") || "";
  if (!text.trim()) return;
  event.preventDefault();
  wbMapPasteWithChip(text);
});

// MAP-DOC-BEGIN
//: **A map written as a document** (audit brief M5, the first half: "Write
//: this map as a document"). The tree as the document's outline: one central
//: topic is the title, its branches are `##` headings and theirs `###`
//: (the document's own heading levels below its title), everything deeper is
//: a nested list, and a topic's note is the paragraph under it (decision 18:
//: a note is plain text, so it goes in as written). Several trunks keep the
//: map's name as the title and each trunk is a `##`. Pure, so node tests it
//: (tests/test_map_to_document.py).
function wbMapTreeMarkdown(roots, mapTitle) {
  const nodes = Array.isArray(roots) ? roots : [];
  const one = nodes.length === 1 ? nodes[0] : null;
  const title = ((one ? one.text : mapTitle) || "Untitled map").replace(/\s+/g, " ").trim();
  const out = [];
  const note = (n) => String(n?.style?.note || "").trim();
  if (one && note(one)) out.push(note(one), "");
  const walk = (list, depth) => {
    for (const n of list) {
      const text = String(n.text || "Untitled").replace(/\s+/g, " ").trim();
      const kids = n.children || [];
      if (depth < 2) {
        out.push(`${"#".repeat(depth + 2)} ${text}`, "");
        if (note(n)) out.push(note(n), "");
        walk(kids, depth + 1);
        if (depth === 1 && kids.length) out.push("");
      } else {
        const pad = "  ".repeat(depth - 2);
        out.push(`${pad}- ${text}`);
        for (const line of note(n) ? note(n).split("\n") : []) out.push(line.trim() ? `${pad}  ${line}` : "");
        walk(kids, depth + 1);
      }
    }
  };
  walk(one ? one.children || [] : nodes, 0);
  return { title, body: out.join("\n").replace(/\n{3,}/g, "\n\n").trim() };
}
// MAP-DOC-END

//: **One branch out of the map** (XMind's Copy as text, MindNode's export of
//: a selection): the topic and everything under it as the same Markdown
//: outline the whole map writes, the topic as its title. From the server's
//: tree, so the order and the notes are the ones the exports use.
async function wbMapCopyBranchOutline(id) {
  const boardId = window.currentBoardId;
  if (!boardId || id == null) return false;
  let tree;
  try {
    tree = await apiJson(`/whiteboard/boards/${boardId}/tree`);
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "read this map" }), true);
    return false;
  }
  const find = (list) => {
    for (const n of list || []) {
      if (n.id === id) return n;
      const hit = find(n.children);
      if (hit) return hit;
    }
    return null;
  };
  const node = find(tree.roots);
  if (!node) return false;
  const { title, body } = wbMapTreeMarkdown([node]);
  const copied = await copyToClipboard(body ? `# ${title}\n\n${body}\n` : `# ${title}\n`);
  if (copied) toast(`Copied “${title}” and its branch as an outline.`);
  return copied;
}

//: The export dialog for this branch alone: the branch is the selection, so
//: the picture formats take only it (the outline formats are the whole map's).
function wbMapExportBranch(id) {
  const index = wbMapIndex();
  const hidden = wbMapConcealed(index);
  const branch = wbMapSubtree(index, id).filter((o) => !hidden.has(o.id));
  if (!branch.length) return;
  clearWbSelection();
  for (const o of branch) wbMultiSelection.add(wbMultiKey("object", o.id));
  wbApplySelectionHighlight();
  wbUpdateSelectionBar();
  wbExportBoard({ branch: true });
}

//: The menu row and the palette row: written, saved as a new document that
//: opens with a card of the map at its head (the board embed, so the
//: document leads back to its map), and opened.
async function wbMapWriteDocument() {
  const boardId = window.currentBoardId;
  if (!boardId) return null;
  //: A map is written from its tree; a board from its frames (L-documents-4, `POST /boards/{id}/draft`).
  const isMap = wbIsMap();
  let tree;
  let draft;
  try {
    if (isMap) tree = await apiJson(`/whiteboard/boards/${boardId}/tree`);
    else draft = await apiJson(`/whiteboard/boards/${boardId}/draft`, { method: "POST" });
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: isMap ? "read this map" : "read this board" }), true);
    return null;
  }
  //: The index may predate a map made a moment ago; it is refreshed once.
  if (typeof mapBoardById === "function" && !mapBoardById(boardId) && typeof loadMapBoardIndex === "function") {
    await loadMapBoardIndex(true).catch(() => null);
  }
  const board = (typeof mapBoardById === "function" && mapBoardById(boardId)) || { id: boardId, type: isMap ? "map" : "board", title: "" };
  const { title, body } = isMap ? wbMapTreeMarkdown(tree.roots, board.title) : draft;
  let doc;
  try {
    doc = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title: title.slice(0, 200), content: `${boardEmbedMarkdown(board)}\n\n${body}\n` }),
    });
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "make that document" }), true);
    return null;
  }
  pushBinPairUndo(`Wrote “${title}” as a document`, `/documents/${doc.id}`, `/documents/${doc.id}/restore`, true, () => (typeof loadDocuments === "function" ? loadDocuments() : null));
  switchTab("documents");
  await openDocument(doc.id);
  toast(`Wrote “${title}” as a document.`);
  return doc;
}

//: **The open map's commands in the command palette** (audit FEAT-11,
//: 2026-10-05: the palette mentioned the board only as the AI's subject, so
//: on the most control-dense surface nothing could be found by typing its
//: name). Rows in the editor group's shape (`docPaletteCommands`): a group,
//: a label with its icon, the key when there is one, a `run`. Only while a
//: map is open on the canvas; the topic rows only with a topic selected.
//: Each `run` waits a task, for the reason `paletteLater` gives: the palette
//: runs a row on Enter's keydown.
function mapPaletteCommands() {
  const canvas = document.getElementById("library-view-whiteboard");
  //: Showing, not merely present: another tab hides the Library, not this.
  if (typeof wbIsMap !== "function" || !wbIsMap() || !canvas?.getClientRects().length) return [];
  const later = (fn) => () => wbMapCache.defer(fn);
  const rows = [];
  const node = wbSelectedMapNode();
  const row = (group, label, run, keys, about) => rows.push({ group, label, run: later(run), keys, about });
  if (node) {
    row("This topic", "ph:arrow-elbow-down-right Add a child topic", () => wbMapAddChild(node.id), "Tab");
    row("This topic", "ph:arrow-down Add a sibling topic", () => wbMapAddSibling(node.id), "Enter");
    //: The topic's grips by name (row 9): the library `+` and the corner.
    row("This topic", "ph:link-simple Add a child that points at a note, document, file or link", () => wbMapAddReference(node.id));
    //: The fill and the canvas colour by name (INBOX 431(b)): both wells were wired but only a right-click or the View menu led to them, and a search for fill, colour or background found neither.
    row("This topic", "ph:paint-bucket Topic fill colour", () => document.getElementById("wb-map-strip-color")?.click(), "", "Colours this topic's card; the branch colour is in the right-click menu. Also found by colour, color or background.");
    row("This topic", "ph:corners-in Resize this topic to the usual width", () => wbMapResetTopicSize(node.id));
    //: The line's mid `+` by name: a touch screen has no hover to find it.
    if (node.parent_id != null) row("This topic", "ph:arrow-elbow-left-up Put a topic between this and its parent", () => wbMapInsertBetween(node.parent_id, node.id));
    if (node.kind === "topic") row("This topic", "ph:pencil-simple Rename the topic", () => wbMapEditNode(node.id), "F2");
    row("This topic", "ph:caret-down Fold or unfold the branch", () => wbMapToggleCollapse(node.id), "C");
    row("This topic", "ph:crosshair Focus on this branch", () => wbMapSetFocus(node.id));
    row("This topic", "ph:flag Markers on this topic…", () => wbMapOpenMarkers(node.id));
    row("This topic", "ph:microphone Audio note: pick a recording…", () => wbMapLazy.pickAudio(node));
    row("This topic", "ph:image Picture from a link…", () => wbMapLazy.imageFromLink(node));
    row("This topic", "ph:copy-simple Copy this topic's shape", () => wbMapLazy.copyShape(node));
    row("This topic", "ph:clipboard Paste the copied shape onto this topic", () => wbMapLazy.pasteShape(node));
    row("This topic", "ph:stack-plus Add a template branch…", () => wbMapLazy.pickTemplate(node));
    row("This topic", "ph:file-md Save this branch as Markdown", () => wbMapLazy.saveBranch(node));
    row("This topic", "ph:flow-arrow Add a second central topic joined to this one…", () => wbMapLazy.secondRoot(node));
    if (node.data?.recording) {
      row("This topic", "ph:play Play the audio note", () => wbMapLazy.playAudio(node.id, document.querySelector(`.wb-object[data-id="${node.id}"] .wb-map-audio`) || document.getElementById("whiteboard-container")));
      row("This topic", "ph:microphone-slash Remove the audio note", () => wbMapLazy.removeAudio(node));
    }
    row("This topic", "ph:eyedropper Copy this topic's style", () => wbCopySelectedStyle(), "Ctrl+Alt+C");
    row("This topic", "ph:paint-bucket Paste style onto this topic", () => wbPasteCopiedStyle(), "Ctrl+Alt+V");
    row("This topic", "ph:stack Use this look for its level", () => wbMapUseLookForLevel(node.id));
    row("This topic", "ph:text-align-left Summarise this branch", () => wbMapSummariseBranch(node));
    if (!(node.parent_id == null && wbMapLevels(wbMapIndex()).get(node.id) === 0)) row("This topic", "ph:arrow-bend-right-down Move under…", () => wbMapMoveUnder(node.id), "M");
    row("This topic", "ph:copy Copy this branch as an outline", () => wbMapCopyBranchOutline(node.id));
    row("This topic", "ph:export Export this branch…", () => wbMapExportBranch(node.id));
    row("This topic", "ph:trash Delete the topic and its branch", () => wbMapDeleteSubtree(node.id), "Delete");
  }
  row("This map", "ph:plus-circle Add a top-level topic", () => wbMapAddChild(null));
  row("This map", "ph:paint-bucket Map background colour", () => document.getElementById("wb-bg-color-picker")?.click(), "", "The canvas colour behind the map, also in View. Also found by colour, color or fill.");
  row("This map", "ph:broom Tidy the map", () => wbMapTidy());
  row("This map", "ph:arrows-out-simple Open every folded branch", () => wbMapExpandAll());
  row("This map", "ph:arrows-in-line-vertical Fold every branch", () => wbMapFoldToLevel(1), "Alt+1");
  row("This map", "ph:list-dashes Show two levels", () => wbMapFoldToLevel(2), "Alt+2");
  {
    //: Only when they change something (INBOX 1774, the rule of 1773).
    const index = wbMapIndex();
    const folded = wbMapHidden(index);
    if (wbMapBuild.ring(index, folded, 1).ids.length) row("This map", "ph:plus-circle Show one more level", () => wbMapFoldToLevel({ by: 1 }), "Alt+=");
    if (wbMapBuild.ring(index, folded, -1).ids.length) row("This map", "ph:minus-circle Show one less level", () => wbMapFoldToLevel({ by: -1 }), "Alt+-");
  }
  if (wbMapFocusState) {
    row("This map", "ph:x-circle Show the whole map again", () => wbMapClearFocus());
  }
  row("This map", "ph:palette How this map looks", () => wbMapThemeDialog());
  const numbered = Boolean(window.wbMapState?.numbered);
  row("This map", numbered ? "ph:list-bullets Stop numbering the topics" : "ph:list-numbers Number the topics", () => wbMapSetNumbered(!numbered));
  row("This map", "ph:chart-bar What this map is made of", () => wbShowMapStats());
  row("This map", "ph:presentation Present branches", () => wbStartPresenting());
  row("This map", "ph:steps Build up branch by branch", () => wbMapBuild.start());
  row("This map", "ph:student Study the map", () => wbMapStartStudy());
  row("This map", "ph:list-numbers Study the map in map order", () => wbMapStartStudy({ inOrder: true }));
  row("This map", "ph:chart-bar-horizontal Gantt chart of the dated topics", () => wbMapLazy.openGantt());
  row("This map", wbMapLazy.timerOn() ? "ph:timer Stop the brainstorm timer" : "ph:timer Start a five minute brainstorm timer", () => (wbMapLazy.timerOn() ? wbMapLazy.stopTimer() : wbMapLazy.startTimer(5)));
  row("This map", "ph:funnel Filter by marker…", () => wbMapChooseMarkerFilter());
  if (wbMarkerUi.filters.size) row("This map", "ph:x-circle Stop filtering by marker", () => wbMapSetMarkerFilter(null));
  row("This map", wbOutlineShowing() ? "ph:list-dashes Hide the outline" : "ph:list-dashes Show the map as an outline", () => wbOutlineToggle());
  row("This map", "ph:frame-corners Zoom to fit the map", () => wbZoomToFit());
  for (const [value, name] of WB_MAP_LAYOUT_NAMES) {
    if (value !== wbMapLayout()) row("Map layout", `ph:tree-structure Layout: ${name}`, () => wbMapSetLayout(value));
  }
  row("This map", "ph:file-text Write this map as a document", () => wbMapWriteDocument());
  for (const [format, name] of [["markdown", "Markdown outline"], ["opml", "OPML"], ["freemind", "FreeMind (.mm)"], ["xmind", "XMind (.xmind)"], ["text", "plain text"]]) {
    row("Export the map", `ph:export Export as ${name}`, () => wbExportMapText(format));
  }
  return rows;
}

//: The resize grip's undo by name: the usual width again and the height its
//: words need, one Undo step.
function wbMapResetTopicSize(id) {
  const node = (wbState.objects || []).find((o) => o.id === id);
  if (!node) return;
  wbPushUndo({ action: "move", kind: "object", id: node.id, before: WB_KIND_INFO.object.payload(node) });
  node.width = WB_MAP_NODE_W;
  node.height = null;
  wbClearMapNodeSizeCache();
  wbSaveObject(node);
  renderWhiteboardNow();
  if (wbMapLayout() !== "free") wbMapTidy({ quiet: true });
}

//: Where a new topic starts, before any tidy: beside its parent and under
//: its last sibling's whole branch (`wbMapPlaceAsChild`'s rule and the
//: server's `_next_position`), or under everything for a new trunk. On a
//: Free map this is where it stays.
function wbMapFreshPlace(row, parent) {
  const index = wbMapIndex();
  const size = (node) => wbMapNodeSize(node);
  const below = (nodes) => {
    let bottom = -Infinity;
    for (const top of nodes) {
      for (const node of wbMapSubtree(index, top.id)) bottom = Math.max(bottom, node.y + size(node).h);
    }
    return bottom;
  };
  //: Its height before it has an element to measure: a sibling's, or any
  //: branch topic's, so the tidy centres it as it will be drawn rather than
  //: at the default box and 6px off once measured.
  const like = (parent && (index.childrenOf.get(parent.id) || [])[0]) || index.nodes.find((n) => n.parent_id != null && n !== row);
  if (like && !row.height) row.height = size(like).h;
  if (!parent) {
    row.x = index.roots.length ? Math.min(...index.roots.map((r) => r.x)) : 0;
    row.y = index.roots.length ? below(index.roots) + wbMapGapDepth() : 0;
    return;
  }
  let siblings = index.childrenOf.get(parent.id) || [];
  const mid = (node) => node.x + size(node).w / 2;
  //: **The central topic's children go to the side with fewer** (bug sweep
  //: 2026-10-12: 7 of 8 stacked on one side), right on a tie; the new one
  //: goes under that side's last branch. Other topics' children are not
  //: moved (below: they grow away from the trunk).
  if (parent.parent_id == null) {
    const lefts = siblings.filter((n) => n !== row && mid(n) < mid(parent));
    const rights = siblings.filter((n) => n !== row && mid(n) >= mid(parent));
    const toLeft = lefts.length < rights.length;
    siblings = toLeft ? lefts : rights;
    const width = row.width || WB_MAP_NODE_W;
    if (toLeft) row.x = (lefts.length ? Math.max(...lefts.map((n) => n.x + size(n).w)) : parent.x - wbMapGapDepth()) - width;
    else row.x = rights.length ? Math.min(...rights.map((n) => n.x)) : parent.x + size(parent).w + wbMapGapDepth();
    row.y = siblings.length ? below(siblings) + wbMapGapBreadth() : parent.y;
    return;
  }
  //: **A branch grows away from its trunk** (the owner, 2026-10-11: a child
  //: added under a left-hand topic landed on its right, back toward the
  //: trunk, and on a Free map that is where it stayed). The side is the one
  //: the parent is drawn on, read from its centre against its trunk's.
  let trunk = parent;
  for (let hops = 0; trunk.parent_id != null && index.byId.get(trunk.parent_id) && hops < 200; hops++) trunk = index.byId.get(trunk.parent_id);
  const leftward = trunk !== parent && mid(parent) < mid(trunk);
  const width = row.width || WB_MAP_NODE_W;
  if (leftward) {
    row.x = (siblings.length ? Math.max(...siblings.map((n) => n.x + size(n).w)) : parent.x - wbMapGapDepth()) - width;
  } else {
    row.x = siblings.length ? Math.min(...siblings.map((n) => n.x)) : parent.x + size(parent).w + wbMapGapDepth();
  }
  row.y = siblings.length ? below(siblings) + wbMapGapBreadth() : parent.y;
}

//: The provisional topic made real: POST it where the tidy put it, swap its
//: id for the server's everywhere it is held (the row, its element, the
//: selection, the Undo stacks), then write what the POST could not carry
//: (its place among its siblings, the text typed so far) and the tidy's
//: moves. Resolves true once it has its id, false when the server refused
//: it, in which case the topic is taken back off the canvas.
async function wbMapAdoptProvisional(row, { expand = null, origin = null, order = null } = {}) {
  const tempId = row.id;
  let made;
  try {
    made = await apiJson(`/whiteboard/boards/${row.board_id}/nodes`, {
      method: "POST",
      body: JSON.stringify({ kind: "topic", parent_id: row.parent_id, text: WB_MAP_NEW_TOPIC, x: row.x, y: row.y }),
    });
  } catch (err) {
    delete row._creating;
    wbState.objects = (wbState.objects || []).filter((o) => o !== row);
    const step = wbUndoStack.find((e) => e.action === "create" && e.id === tempId);
    if (step) wbDropUndoEntry(step);
    toast(err.message || voiceLine("failed", { what: "add that node" }), true);
    wbScheduleRender();
    return false;
  }
  row.id = made.id;
  const el = document.querySelector(`.wb-object[data-id="${tempId}"]`);
  if (el) el.dataset.id = String(made.id);
  if (wbSelectedItem?.kind === "object" && wbSelectedItem.id === tempId) wbSelectedItem.id = made.id;
  const size = wbMapNodeSizeCache?.get(tempId);
  if (size) wbMapNodeSizeCache.set(made.id, size);
  wbRemapUndoIds(new Map([[tempId, made.id]]));
  delete row._creating;
  //: What the server knows that this row does not (its timestamps), without
  //: taking back what has happened here since: the place the tidy gave it
  //: and whatever has been typed.
  for (const key of Object.keys(made)) {
    if (!["x", "y", "data", "id", "width", "height"].includes(key)) row[key] = made[key];
  }
  if (!row.width) row.width = made.width;
  if (!row.height) row.height = made.height;
  const typed = row.data?.content !== WB_MAP_NEW_TOPIC;
  if (order != null || typed) wbSaveObject(row);
  if (expand) wbSaveObject(expand);
  if (origin?.size) wbSaveBulkMove(origin);
  //: The lines into and out of it are keyed by the old id: they, their
  //: mid-line `+` and its waypoint handle are drawn again under the new. Not
  //: a whole render (MINDMAP_PLAN 15, row 4: one render per act, not two);
  //: the topic itself took its new id on its element above.
  wbRenderMapEdges({ only: new Set([made.id]) });
  return true;
}

//: **A new trunk where the person pointed** (MINDMAP_PLAN §13, the owner:
//: the map's tools "dont show themselves how id expect"). Double-clicking
//: empty canvas is how a new topic is made in Coggle, XMind and every
//: whiteboard in this app's own reference list, and on a map it did nothing
//: at all: measured, 3 topics before and 3 after. The rail's "Add a
//: top-level topic" was the only route, and it puts the new trunk wherever
//: the layout decides.
//:
//: Pinned, because the position is a decision the person made with the
//: pointer: that is the same bargain `wbMapPinOnDrag` strikes for a dragged
//: node, and without it the next tidy would move the new trunk away from the
//: spot that was just chosen.
async function wbMapAddRootAt(x, y) {
  const created = await wbMapCreateNode({ parentId: null });
  if (!created) return null;
  created.x = Math.round(x - (created.width || WB_MAP_NODE_W) / 2);
  created.y = Math.round(y - (created.height || WB_MAP_NODE_H) / 2);
  created.data = { ...created.data, pinned: true };
  await wbSaveObject(created);
  selectWbItem("object", created.id);
  renderWhiteboardNow();
  wbMapEditNode(created.id);
  return created;
}

//: Add a child that **points at something the library already holds**
//: (MINDMAP_PLAN.md §5 item 11).
//:
//: The label is *not* sent. `POST /boards/{id}/nodes` takes the kind and the
//: id and resolves the title itself, and `GET /tree` re-resolves it on every
//: load (§9.2): so renaming the note renames the node, which is the whole
//: reason a reference node is different from a topic with the same words in
//: it. `text` is left empty deliberately: a copy of the title stored here
//: would be the value that goes stale, and `wbMapLabel` prefers the resolved
//: one anyway.
//:
//: `wbRefreshMapState` is re-run before the render because the resolved label
//: lives in `wbMapState.labels`, which only that call fills, without it the
//: new node draws with no text at all until the next board load, which is
//: exactly the "renders as a blank box" failure §10.2 already fixed once for
//: topics.
async function wbMapAddReference(parentId) {
  if (typeof pickLibraryItemDialog !== "function") return null;
  const chosen = await pickLibraryItemDialog("Point a new node at…", { noUploads: true });
  if (!chosen) return null;
  const created = await wbMapCreateNode({
    parentId,
    kind: chosen.kind,
    text: "",
    refId: chosen.id,
  });
  if (!created) return null;
  const parent = (wbState.objects || []).find((o) => o.id === parentId);
  if (parent?.data?.collapsed) {
    parent.data = { ...parent.data, collapsed: false };
    await wbSaveObject(parent);
  }
  await wbRefreshMapState();
  selectWbItem("object", created.id);
  await wbMapTidyBranch(parentId);
  renderWhiteboardNow();
  toast(`Added “${chosen.label}” to the map.`);
  return created;
}

//: Enter: a sibling, which is a child of *this* node's parent. A root has no
//: parent to be a sibling under, so Enter there adds another root, which is
//: the only reading of "a sibling of the root" that means anything.
//: **Right after the topic it was pressed on** (Shift+Enter: right before),
//: which is what XMind, MindNode and Coggle do and what this comment always
//: said Enter did; with siblings sorted by id it landed at the end of the
//: branch instead, measured on a middle topic (INBOX 445).
async function wbMapAddSibling(id, { above = false } = {}) {
  const index = wbMapIndex();
  const node = index.byId.get(id);
  if (!node) return null;
  // A dangling `parent_id` counts as no parent, exactly as `wbMapIndex` and
  // `_build_tree` already treat it: so a node under a stale pointer gets a
  // sibling at the top level rather than one hung off a parent that is not
  // on this board.
  const parentId = node.parent_id != null && index.byId.has(node.parent_id)
    ? node.parent_id
    : null;
  //: **The centre's Enter adds a main branch** (MINDMAP_PLAN.md decision
  //: 47; XMind and Coggle): a second centre is never what was meant. A
  //: floating topic (a root drawn at level 2) keeps adding one beside it.
  if (parentId === null && wbMapLevels(index).get(id) === 0) return wbMapAddChild(id);
  const siblings = wbMapSiblingsOf(index, node);
  const at = siblings.findIndex((s) => s.id === id);
  const neighbour = siblings[above ? at - 1 : at + 1];
  // The last place needs no key: a new id already sorts there.
  const order = !above && !neighbour
    ? null
    : above ? wbMapKeyBetween(neighbour, node) : wbMapKeyBetween(node, neighbour);
  return wbMapAddChild(parentId, { order });
}

//: Ctrl+D on a topic: the same text and look, right after it among its
//: siblings, one undo step (the create), the copy selected. Its children are
//: not copied: a duplicate branch is Copy and Paste's job, and a key that
//: quietly copied forty topics would be a surprise.
async function wbMapDuplicateTopic(node) {
  const index = wbMapIndex();
  const parentId = node.parent_id != null && index.byId.has(node.parent_id) ? node.parent_id : null;
  const created = await wbMapCreateNode({
    parentId, kind: node.kind, text: node.data?.text ?? "", refId: node.data?.ref_id ?? null,
  });
  if (!created) return null;
  const siblings = wbMapSiblingsOf(index, node);
  const neighbour = siblings[siblings.findIndex((s) => s.id === node.id) + 1];
  //: Its look comes along; whether it is folded and where it sorts do not.
  const look = { ...(node.data || {}) };
  delete look.collapsed;
  delete look.order;
  created.data = { ...look, ...created.data, text: node.data?.text ?? "" };
  if (neighbour) created.data.order = wbMapKeyBetween(node, neighbour);
  await wbSaveObject(created);
  selectWbItem("object", created.id);
  await wbMapTidyBranch(parentId);
  renderWhiteboardNow();
  return created;
}

//: Shift+Tab: outdent: this node becomes a sibling of its own parent.
//:
//: Through `/move`, never `PUT /objects/{id}`, because the move endpoint is
//: the only one that runs the cycle check, §9.3 says so in as many words, and
//: `PUT` deliberately does not touch `parent_id` so the check cannot be
//: bypassed by using the wrong endpoint.
async function wbMapOutdent(id) {
  const boardId = window.currentBoardId;
  const index = wbMapIndex();
  const node = index.byId.get(id);
  if (!boardId || !node) return;
  const parent = node.parent_id != null ? index.byId.get(node.parent_id) : null;
  if (!parent) {
    toast("This is already a top-level topic.");
    return;
  }
  //: Every topic's row as it stands, so the one history entry can put back
  //: whatever the tidy moves along with the parent (the shape
  //: `wbMapTransplant` records for a drag).
  const rows = new Map(index.nodes.map((n) => [n.id, WB_KIND_INFO.object.payload(n)]));
  try {
    const moved = await apiJson(`/whiteboard/boards/${boardId}/nodes/${id}/move`, {
      method: "PUT",
      body: JSON.stringify({ parent_id: parent.parent_id ?? null }),
    });
    Object.assign(node, moved);
    await wbMapTidyBranch(moved.parent_id ?? null);
    //: **One Undo step** (INBOX 445, second audit: Shift+Tab was the one
    //: structural key with no history, so Ctrl+Z took back whatever came
    //: before it).
    const history = [{ action: "reparent", kind: "object", id, parentId: parent.id }];
    for (const now of wbMapIndex().nodes) {
      const row = rows.get(now.id);
      if (row && (row.x !== now.x || row.y !== now.y)) {
        history.push({ action: "move", kind: "object", id: now.id, before: row });
      }
    }
    wbPushUndo(history.length === 1 ? history[0] : { action: "batch", entries: history });
    renderWhiteboardNow();
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "move that node" }), true);
  }
}

//: **Move under…** (audit 1028 U4, WCAG 2.5.7): a branch has a way to a new
//: parent that is not a drag. A searchable list of every topic it may go under
//: (not itself or anything in its own branch, not the parent it already has),
//: then the same `wbMapTransplant` a drop uses, so the cycle check and the one
//: Undo step are the drag's own. Keys: M; the topic menu, palette and sheet.
function wbMapMoveUnder(id) {
  const index = wbMapIndex();
  const node = index.byId.get(id);
  if (!node) return;
  const own = new Set(wbMapSubtree(index, id).map((o) => o.id));
  const options = index.nodes.filter((n) => !own.has(n.id) && n.id !== node.parent_id);
  if (!options.length) {
    toast("There is nowhere else to put this topic.", "info");
    return;
  }
  const shell = pickerDialog({
    title: "Move under…",
    about: `Pick the topic that "${wbMapLabel(node) || "this topic"}" and its branch go under.`,
    placeholder: "Search topics…",
  });
  const paint = () => {
    const term = shell.search.value.trim().toLowerCase();
    const rows = options.filter((n) => !term || (wbMapLabel(n) || "").toLowerCase().includes(term)).slice(0, 80);
    if (!rows.length) {
      const none = document.createElement("li");
      none.className = "muted entry-pick-about";
      none.textContent = "No topic matches.";
      shell.list.replaceChildren(none);
      return;
    }
    shell.list.replaceChildren(...rows.map((n) => {
      const li = document.createElement("li");
      const button = richPickerRow({ tag: "button", role: null, icon: "ph:tree-structure", label: wbMapLabel(n) || "Untitled topic" });
      button.addEventListener("click", () => shell.close(n.id));
      li.appendChild(button);
      return li;
    }));
  };
  shell.search.addEventListener("input", paint);
  paint();
  new Promise((resolve) => shell.open(resolve)).then((targetId) => {
    if (targetId != null) wbMapTransplant(node, targetId, false, { via: "menu" });
  });
}

//: **Ctrl+Enter: a parent topic** (XMind's Insert parent topic, which the map
//: lacked): a new topic takes this one's place among its siblings and this
//: one, with its branch, goes under it. The centre has no place to give up.
//: One Undo step: the move, whatever the tidy shifted, and the create.
async function wbMapInsertParent(id) {
  const boardId = window.currentBoardId;
  const index = wbMapIndex();
  const node = index.byId.get(id);
  if (!boardId || !node) return null;
  const parentId = node.parent_id != null && index.byId.has(node.parent_id) ? node.parent_id : null;
  if (parentId === null && wbMapLevels(index).get(id) === 0) {
    toast("The centre has no parent: add a topic beside it instead.");
    return null;
  }
  const rows = new Map(index.nodes.map((n) => [n.id, WB_KIND_INFO.object.payload(n)]));
  const created = await wbMapCreateNode({ parentId });
  if (!created) return null;
  //: Folded into the batch below, so one Ctrl+Z takes both back.
  if (wbUndoStack[wbUndoStack.length - 1]?.action === "create") wbUndoStack.pop();
  created.data = { ...created.data, order: wbMapOrderKey(node) };
  await wbSaveObject(created);
  try {
    const moved = await apiJson(`/whiteboard/boards/${boardId}/nodes/${id}/move`, {
      method: "PUT",
      body: JSON.stringify({ parent_id: created.id }),
    });
    Object.assign(node, moved);
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "move that topic" }), true);
  }
  await wbMapTidyBranch(parentId);
  //: Undo runs these in order: the topic goes back before its new parent goes.
  const history = [{ action: "reparent", kind: "object", id, parentId }];
  for (const now of wbMapIndex().nodes) {
    const row = rows.get(now.id);
    if (row && (row.x !== now.x || row.y !== now.y)) history.push({ action: "move", kind: "object", id: now.id, before: row });
  }
  history.push({ action: "create", kind: "object", id: created.id });
  wbPushUndo({ action: "batch", entries: history });
  selectWbItem("object", created.id);
  renderWhiteboardNow();
  wbMapEditNode(created.id);
  return created;
}

//: The arrows, in tree terms rather than screen terms: up/down are the
//: siblings either side, left is the parent and right is the first child.
//:
//: Deliberately *not* "whatever box is nearest in that direction on screen".
//: A tree already knows what is above and below a node, and a spatial search
//: gives a different answer the moment two branches overlap, which is
//: precisely when you most need the keys to be predictable.
function wbMapNavigate(id, key) {
  const index = wbMapIndex();
  const node = index.byId.get(id);
  if (!node) return false;
  const hidden = wbMapConcealed(index);
  const siblings = node.parent_id != null && index.byId.has(node.parent_id)
    ? index.childrenOf.get(node.parent_id) || []
    : index.roots;
  const at = siblings.findIndex((s) => s.id === id);
  let target = null;
  if (key === "ArrowUp") target = siblings[at - 1];
  else if (key === "ArrowDown") target = siblings[at + 1];
  else if (key === "ArrowLeft") target = index.byId.get(node.parent_id);
  else if (key === "ArrowRight" && !node.data?.collapsed) {
    target = (index.childrenOf.get(id) || [])[0];
  }
  if (!target || hidden.has(target.id)) return false;
  selectWbItem("object", target.id);
  //: Said aloud as well as drawn (INBOX 445): which topic, and where it sits.
  const kids = (index.childrenOf.get(target.id) || []).length;
  const fold = target.data?.collapsed ? `, folded, ${kids} under it` : kids ? `, ${kids} under it` : "";
  wbAnnounce(`${wbItemSpokenName("object", target)}${fold}`);
  wbApplySelectionHighlight();
  wbUpdateSelectionBar();
  // Bring it on screen, but **only when it is actually off screen**.
  // Navigating into a node past the edge of the viewport reads exactly like
  // the key having done nothing, so the scroll has to happen; recentring on
  // every arrow instead makes the whole map lurch under you while you are
  // simply walking a branch you can already see, which is worse than either.
  wbMapRevealTopic(target);
  return true;
}

//: Does a client rectangle reach outside the one it should sit in.
function wbRectEscapes(node, view) {
  return node.left < view.left || node.right > view.right || node.top < view.top || node.bottom > view.bottom;
}

//: **Bring a topic into view, only when it is out of it** (the arrow keys'
//: rule above, and a new topic's: dogfood 2026-10-25 item 12, where Tab put a
//: child at x~1265 past the window's edge and the view stayed). Measured
//: against the canvas the board's own chrome leaves free, not the whole
//: container, so a topic under the top bar or the dock counts as hidden.
function wbMapRevealTopic(item) {
  const el = document.querySelector(`.wb-object[data-id="${item.id}"]`);
  const container = document.getElementById("whiteboard-container");
  if (!el || !container) return false;
  const free = typeof wbVisibleCanvasRect === "function" ? wbVisibleCanvasRect() : container.getBoundingClientRect();
  //: **Inside the slide's own margin counts as at the edge** (audit 1028 U24:
  //: the newest topic stood 5px from the canvas edge, "in view" to a plain
  //: containment test, so the view never moved and it read as cut off).
  const m = 24;
  const inset = { left: free.left + m, top: free.top + m, right: free.right - m, bottom: free.bottom - m };
  if (!wbRectEscapes(el.getBoundingClientRect(), inset)) return false;
  const box = wbItemBBox("object", item);
  if (!box) return false;
  //: With its parent when the two fit side by side (dog2 item 12): centring
  //: the child alone slid the root under the left rail at 700, so the topic
  //: you branched from left the screen as its child arrived.
  const parentItem = item.parent_id != null ? (wbState.objects || []).find((o) => o.id === item.parent_id) : null;
  const pBox = parentItem ? wbItemBBox("object", parentItem) : null;
  const k = d3.zoomTransform(container).k || 1;
  const area = wbFreeArea(container);
  const both = pBox && {
    minX: Math.min(box.minX, pBox.minX), minY: Math.min(box.minY, pBox.minY),
    maxX: Math.max(box.maxX, pBox.maxX), maxY: Math.max(box.maxY, pBox.maxY),
  };
  const fits = both && (both.maxX - both.minX) * k <= area.right - area.left - 32 && (both.maxY - both.minY) * k <= area.bottom - area.top - 32;
  const want = fits ? both : box;
  //: **The least move that brings it in, not a recentre** (mapdog-1026: Tab
  //: three levels deep centred the new topic and the root was left 16px from
  //: the window's edge, a 627px pan). Each axis slides only as far as the
  //: topic (with its parent) needs, to a 24px margin inside the free area, so
  //: what was on screen mostly stays where it was. A view too small to read
  //: still eases up to a legible zoom, which is `wbCenterOn`'s job.
  if (k < 0.55) {
    wbCenterOn(want, { animate: true });
    return true;
  }
  const t = d3.zoomTransform(container);
  const slide = (lo, hi, a0, a1) => {
    let d = 0;
    if (hi > a1 - m) d = a1 - m - hi;
    if (lo + d < a0 + m) d = a0 + m - lo;
    return d;
  };
  const dx = slide(t.x + k * want.minX, t.x + k * want.maxX, area.left, area.right);
  const dy = slide(t.y + k * want.minY, t.y + k * want.maxY, area.top, area.bottom);
  if (!dx && !dy) return false;
  d3.select(container).transition().duration(300).call(wbZoom.transform, d3.zoomIdentity.translate(t.x + dx, t.y + dy).scale(t.k));
  return true;
}

//: F2 / double-click: rename in place, through the same two functions a text
//: box uses. A reference node has no text of its own: its label is the note's,
//: and editing it here would either lie or silently rename the note.
function wbMapEditNode(id, { now = false } = {}) {
  //: A topic the outline's Enter made is typed in the outline (decision 33).
  if (wbOutlineState.adding) {
    wbMapTypeahead = null;
    wbOutlineTakeNewTopic(id);
    return;
  }
  const node = (wbState.objects || []).find((o) => o.id === id);
  if (!node || node.kind !== "topic") wbMapTypeahead = null;
  if (!node) return;
  if (node.kind !== "topic") {
    wbMapEditCaption(node);
    return;
  }
  // The render that just ran replaced this element, so it is looked up fresh
  // rather than kept from before, the same trap `wbCreateTextBox` documents.
  //: `now` when the caller has just drawn it synchronously (the add path,
  //: FEAT-02's 100ms gate): waiting a frame was a frame of the gate spent on
  //: nothing, and the frame's own style pass is then the editor's.
  const open = () => {
    const typed = wbMapTypeahead?.text || "";
    const commit = Boolean(wbMapTypeahead?.commit);
    wbMapTypeahead = null;
    const el = document.querySelector(`.wb-object[data-id="${id}"] .wb-map-text`);
    if (!el) return;
    wbBeginTextEdit(el);
    // Select the whole label so the first keystroke replaces it: a new node
    // arrives empty, and a renamed one is almost always being replaced rather
    // than edited. Keys typed before the editor opened replace it instead,
    // with the caret after them.
    if (typed) el.textContent = typed;
    const range = document.createRange();
    range.selectNodeContents(el);
    if (typed) range.collapse(false);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    //: The Enter typed ahead (`wbMapCatchTypeahead`): the blur is the same
    //: commit the editor's own Enter makes.
    if (commit) el.blur();
  };
  if (now) open();
  else wbMapCache.defer(open, 1);
}

//: **A reference node's own words** (B38). Its name is the item's, so a
//: rename here is a caption on the node: the item is untouched, the tree
//: still resolves the item's name, and typing the item's own name back (or
//: the caption cleared by the Reset row) returns the node to following it.
//: Escape answers "" like an empty field, so an empty answer changes nothing.
async function wbMapEditCaption(node) {
  const resolved = window.wbMapState?.labels?.get(node.id) || "";
  const current = node.data?.caption || resolved;
  const answer = String((await promptDialog("What should this node say?", current, { confirmLabel: "Rename the node" })) ?? "").trim();
  if (!answer || answer === current) return;
  await wbMapSetNodeStyle(node, { caption: answer === resolved ? null : answer.slice(0, 120) });
  renderWhiteboardNow();
}

//: **A map always keeps one topic** (MINDMAP_PLAN.md §12.0, decided after the
//: owner asked "should the user even be able to delete the primary core
//: node??").
//:
//: Not a taste call: every way of adding a node hangs off a node that is
//: already on the map (Tab on the selection, the hover +, the node's own
//: right-click menu), so the delete that empties a map is the delete that
//: removes the way to undo itself. The empty-state panel is the net under
//: this; the refusal is the rule.
//:
//: Refusing without an alternative would just be a wall, so the refusal
//: carries the action someone emptying a map actually wants: clear it and
//: start again from one blank topic.
function wbMapDeleteEmptiesMap(id) {
  if (!wbIsMap()) return false;
  const index = wbMapIndex();
  if (!index.byId.has(id)) return false;
  return index.nodes.length - wbMapSubtree(index, id).length <= 0;
}

function wbMapRefuseLastTopic() {
  toastAction(
    "A map keeps at least one topic, so this one stays.",
    "Clear the map",
    wbMapClearToOneTopic
  );
}

//: The explicit version of what deleting the last node would have done by
//: accident: take everything away, then leave one blank topic open for
//: typing, which is the state a new map starts in.
//:
//: Deleting the roots is enough to delete the map: `DELETE
//: /whiteboard/objects/{id}` takes a node's whole subtree with it (§9.1), so
//: one request per root removes every descendant too.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapClearToOneTopic(...args) {
  return wbRecordGesture(wbMapClearToOneTopicNow, args);
}

async function wbMapClearToOneTopicNow() {
  if (!wbIsMap()) return;
  const roots = wbMapIndex().roots;
  for (const root of roots) {
    try {
      const res = await apiJson(`/whiteboard/objects/${root.id}`, { method: "DELETE" });
      const gone = new Set((Array.isArray(res?.deleted) ? res.deleted : []).map((row) => row.id));
      gone.add(root.id);
      wbState.objects = (wbState.objects || []).filter((o) => !gone.has(o.id));
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "clear the map" }), true);
      return;
    }
  }
  clearWbSelection();
  await wbMapAddChild(null);
}

//: Delete: the subtree, with a real Undo rather than a confirm dialog.
//:
//: `DELETE /whiteboard/objects/{id}` returns the whole deleted subtree, rows
//: and positions included, precisely so this can put it back (§9.1). A confirm
//: dialog asks you to predict what you are about to lose; an undo shows you.
//: The re-create walks the returned list in order, it comes back parents
//: first: and maps each old id to its new one, so the tree comes back with
//: the shape it had rather than as a heap of roots.
async function wbMapDeleteSubtree(id) {
  const boardId = window.currentBoardId;
  const node = (wbState.objects || []).find((o) => o.id === id);
  if (!boardId || !node) return;
  if (wbMapDeleteEmptiesMap(id)) {
    wbMapRefuseLastTopic();
    return;
  }
  let deleted = [];
  //: The cross-links that went with the branch (the server drops them with
  //: their topics and now hands them back), kept on the entry so Undo draws
  //: them again between the restored topics (INBOX 445, second audit).
  let links = [];
  try {
    const res = await apiJson(`/whiteboard/objects/${id}`, { method: "DELETE" });
    deleted = Array.isArray(res.deleted) ? res.deleted : [];
    links = Array.isArray(res.links) ? res.links : [];
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "delete that" }), true);
    return;
  }
  const gone = new Set(deleted.map((row) => row.id));
  const goneLinks = new Set(links.map((link) => link.id));
  wbState.objects = (wbState.objects || []).filter((o) => !gone.has(o.id));
  wbState.sketches = (wbState.sketches || []).filter((k) => !goneLinks.has(k.id));
  clearWbSelection();
  wbScheduleRender();
  //: **On the board's own undo stack, so Ctrl+Z brings it back** (INBOX 445).
  //: The only way back used to be the toast's button: measured, Delete then
  //: Ctrl+Z restored nothing and took back whatever had been done *before*
  //: the delete instead. The toast's Undo is now the same entry, taken off
  //: the stack wherever it sits, so the two can never restore it twice.
  const entry = { action: "subtree", kind: "object", rows: deleted, links };
  const count = deleted.length;
  //: Inside a recorded gesture the gesture pushes the one step for the whole
  //: act; the toast's Undo is then the board's own.
  if (wbRecordDepth > 0) {
    toastAction(`Deleted ${nounCount(count, "node")}.`, "Undo", () => wbUndo());
    return;
  }
  wbPushUndo(entry);
  toastAction(
    `Deleted ${nounCount(count, "node")}.`,
    "Undo",
    async () => {
      const at = wbUndoStack.lastIndexOf(entry);
      if (at === -1) return; // already taken back with Ctrl+Z
      if (at === wbUndoStack.length - 1) {
        await wbUndo();
        return;
      }
      wbUndoStack.splice(at, 1);
      wbUpdateUndoRedoButtons();
      await wbMapRestoreRows(deleted, links);
      await wbRefreshMapState();
      renderWhiteboardNow();
    }
  );
}

//: Put a deleted subtree back, parents first, and return the new ids of its
//: top rows (the ones whose parent was not deleted with them).
//:
//: **Two writes per topic, so it comes back as it was.** `POST .../nodes`
//: is the only route that sets `parent_id` (it runs the cycle check) and it
//: takes the text and the colour alone, so a restored topic used to come back
//: plain: its shape, fill, icon, picture, fold, size and place among its
//: siblings gone. The `PUT` after it writes the rest of the row as it was.
//:
//: **Its cross-links come back too, between the restored topics**: each end
//: that was inside the branch is translated to the new id, an end outside it
//: keeps its own (it still exists). And **every older history entry that
//: named a restored topic is rewritten** (`wbRemapUndoIds`), because the new
//: topics have new ids and the stacks would otherwise point at nothing.
async function wbMapRestoreRows(rows, links = []) {
  const boardId = window.currentBoardId;
  const remap = new Map();
  const tops = [];
  for (const row of rows) {
    // **A parent that was not itself deleted keeps its own id.** The first
    // version fell back to `null` whenever `remap` had no entry, which is
    // true for exactly one row, the top of the deleted subtree, whose
    // parent is still sitting on the board. So the branch came back as a
    // *root* instead of reattaching where it was taken from. Only a parent
    // inside `rows` needs translating, because only those have new ids.
    const parent = row.parent_id == null
      ? null
      : remap.get(row.parent_id) ?? row.parent_id;
    const body = {
      kind: row.kind,
      parent_id: parent,
      text: row.data?.content || "",
      x: row.x,
      y: row.y,
    };
    if (row.data?.ref_id != null) body.ref_id = row.data.ref_id;
    if (row.data?.color) body.color = row.data.color;
    try {
      const made = await apiJson(`/whiteboard/boards/${boardId}/nodes`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      const full = await apiJson(`/whiteboard/objects/${made.id}`, {
        method: "PUT",
        body: JSON.stringify({
          kind: made.kind,
          board_id: made.board_id,
          data: { ...made.data, ...(row.data || {}) },
          x: row.x,
          y: row.y,
          z: row.z ?? made.z,
          width: row.width ?? made.width,
          height: row.height ?? made.height,
          rotation: row.rotation ?? null,
          group_id: row.group_id ?? null,
        }),
      });
      remap.set(row.id, made.id);
      if (!remap.has(row.parent_id) || row.parent_id == null) tops.push(made.id);
      wbState.objects.push({ ...made, ...full, parent_id: made.parent_id });
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "restore that node" }), true);
      break;
    }
  }
  const linkRemap = new Map();
  for (const link of links) {
    let data;
    try {
      data = JSON.parse(link.data);
    } catch {
      continue;
    }
    if (!data || typeof data !== "object") continue;
    const ends = [["sourceId", "sourceKind"], ["targetId", "targetKind"]];
    let whole = true;
    for (const [idKey, kindKey] of ends) {
      if ((data[kindKey] || "node") !== "object") continue;
      if (remap.has(data[idKey])) data[idKey] = remap.get(data[idKey]);
      // An end that is neither restored nor still on the board (the restore
      // stopped part way, or the far topic was deleted since) would be a line
      // to nowhere, which the server cleans up everywhere else.
      else if (!(wbState.objects || []).some((o) => o.id === data[idKey])) whole = false;
    }
    if (!whole) continue;
    try {
      const made = await apiJson("/whiteboard/sketches", {
        method: "POST",
        body: JSON.stringify({
          data: JSON.stringify(data),
          board_id: link.board_id ?? boardId,
          x: link.x ?? 0,
          y: link.y ?? 0,
          z: link.z ?? 0,
          group_id: link.group_id ?? null,
        }),
      });
      linkRemap.set(link.id, made.id);
      wbState.sketches = wbState.sketches || [];
      wbState.sketches.push(made);
    } catch (err) {
      toast(err.message || voiceLine("failed", { what: "restore a link" }), true);
    }
  }
  wbRemapUndoIds(remap, linkRemap);
  return tops;
}


//: The chevron: fold a branch away, or bring it back. `collapsed` is per-node
//: view state in the object's own JSON blob (§9.1), so it survives a reload
//: and the tree endpoint hands it back, a fold you made yesterday is still
//: folded today, which is the only version of this that is worth having.
async function wbMapToggleCollapse(id) {
  const node = (wbState.objects || []).find((o) => o.id === id);
  if (!node) return;
  node.data = { ...node.data, collapsed: !node.data?.collapsed };
  wbScheduleRender();
  await wbSaveObject(node);
}

// --- tidy: Reingold–Tilford with variable node sizes (§5 item 6) ------------
//
// Implemented here rather than pulled in, because the app is offline-first and
// there is no CDN to pull from, and because `graph.js` already hand-rolls its
// own layout, so this is a sibling of existing code rather than a new
// dependency. The reference is Buchheim, Jünger and Leipert's linear-time form
// of Reingold–Tilford, with d3-flextree's extension: the distance between two
// nodes is half of each one's own size plus a gap, instead of a constant.
// Variable sizes are not a nicety here, a map node is as tall as its text.
//
// The breadth axis (siblings) is exact, per node. The depth axis is one offset
// per level, taken from the widest node on that level: that is what `d3.tree`
// itself does, and a per-node depth would let two nodes on the same level sit
// at different distances from the root, which reads as a broken tree rather
// than a tidy one.

//: One tidy pass. `roots` are wrapper objects `{obj, children}`; everything
//: else on a wrapper is the algorithm's own bookkeeping.
function wbTidyFirstWalk(v, breadthOf, gap) {
  if (!v.children.length) {
    v.prelim = v.number > 0 && v.parent
      ? v.parent.children[v.number - 1].prelim + wbTidyDistance(v, v.parent.children[v.number - 1], breadthOf, gap)
      : 0;
    return;
  }
  let defaultAncestor = v.children[0];
  for (const w of v.children) {
    wbTidyFirstWalk(w, breadthOf, gap);
    defaultAncestor = wbTidyApportion(w, defaultAncestor, breadthOf, gap);
  }
  wbTidyExecuteShifts(v);
  const midpoint = (v.children[0].prelim + v.children[v.children.length - 1].prelim) / 2;
  const left = v.number > 0 && v.parent ? v.parent.children[v.number - 1] : null;
  if (left) {
    v.prelim = left.prelim + wbTidyDistance(v, left, breadthOf, gap);
    v.mod = v.prelim - midpoint;
  } else {
    v.prelim = midpoint;
  }
}

//: How far apart two nodes on the same level must sit: half of each one's own
//: breadth plus the gap. The constant this replaces is the whole difference
//: between a tidy tree of identical boxes and one of real, differently-sized
//: nodes: with a constant, a tall node overlaps its neighbours and a short
//: one leaves a hole.
function wbTidyDistance(a, b, breadthOf, gap) {
  return (breadthOf(a) + breadthOf(b)) / 2 + gap;
}

function wbTidyNextLeft(v) {
  return v.children.length ? v.children[0] : v.thread;
}

function wbTidyNextRight(v) {
  return v.children.length ? v.children[v.children.length - 1] : v.thread;
}

function wbTidyMoveSubtree(wm, wp, shift) {
  const subtrees = wp.number - wm.number;
  if (!subtrees) return;
  wp.change -= shift / subtrees;
  wp.shift += shift;
  wm.change += shift / subtrees;
  wp.prelim += shift;
  wp.mod += shift;
}

function wbTidyExecuteShifts(v) {
  let shift = 0;
  let change = 0;
  for (let i = v.children.length - 1; i >= 0; i -= 1) {
    const w = v.children[i];
    w.prelim += shift;
    w.mod += shift;
    change += w.change;
    shift += w.shift + change;
  }
}

function wbTidyAncestor(vim, v, defaultAncestor) {
  return vim.ancestor && vim.ancestor.parent === v.parent ? vim.ancestor : defaultAncestor;
}

//: The part that makes the tree *tidy*: walk the right contour of everything
//: to the left and the left contour of this subtree in step, and push this
//: subtree right by however much they overlap. The threads (`nextLeft` /
//: `nextRight` falling back to `.thread`) are what keep it linear-time instead
//: of re-walking whole subtrees.
function wbTidyApportion(v, defaultAncestor, breadthOf, gap) {
  const left = v.number > 0 && v.parent ? v.parent.children[v.number - 1] : null;
  if (!left) return defaultAncestor;
  let vip = v;
  let vop = v;
  let vim = left;
  let vom = vip.parent.children[0];
  let sip = vip.mod;
  let sop = vop.mod;
  let sim = vim.mod;
  let som = vom.mod;
  while (wbTidyNextRight(vim) && wbTidyNextLeft(vip)) {
    vim = wbTidyNextRight(vim);
    vip = wbTidyNextLeft(vip);
    vom = wbTidyNextLeft(vom);
    vop = wbTidyNextRight(vop);
    vop.ancestor = v;
    const shift = vim.prelim + sim - (vip.prelim + sip) + wbTidyDistance(vim, vip, breadthOf, gap);
    if (shift > 0) {
      wbTidyMoveSubtree(wbTidyAncestor(vim, v, defaultAncestor), v, shift);
      sip += shift;
      sop += shift;
    }
    sim += vim.mod;
    sip += vip.mod;
    som += vom.mod;
    sop += vop.mod;
  }
  if (wbTidyNextRight(vim) && !wbTidyNextRight(vop)) {
    vop.thread = wbTidyNextRight(vim);
    vop.mod += sim - sop;
  }
  if (wbTidyNextLeft(vip) && !wbTidyNextLeft(vom)) {
    vom.thread = wbTidyNextLeft(vip);
    vom.mod += sip - som;
    return v;
  }
  return defaultAncestor;
}

//: **The structures XMind has beyond the tree** (MINDMAP_PLAN 15, row 6):
//: a timeline, a fishbone and a tree table. Each lays a main branch out as a
//: column, the topic then its whole branch one row each, indented by depth,
//: and differs only in where the columns go: along an axis through the
//: centre (timeline, branches below and above in turn), off a spine that
//: runs left from the head (fishbone, pairs above and below), or side by
//: side under the centre (tree table). A new topic moves its neighbours'
//: columns, so these tidy the whole map on an add (`wbMapTidyBranchScope`).
const WB_MAP_COLUMN_LAYOUTS = new Set(["timeline", "fishbone", "tree-table"]);
//: The line a layout draws when neither the topic nor the map's look sets
//: one: right angles for the logic chart and the table, straight ribs for
//: the fishbone.
const WB_MAP_LAYOUT_EDGE = Object.freeze({ "logic-right": "elbow", "tree-table": "elbow", fishbone: "straight" });
const WB_MAP_INDENT = 24;
//: Every layout by its picker's words, in the picker's order (index.html's
//: `#wb-map-layout`, `tests/test_map_layouts.py` holds the two together).
const WB_MAP_LAYOUT_NAMES = Object.freeze([
  ["tree-right", "Tree, to the right"], ["tree-left", "Tree, to the left"], ["tree-both", "Tree, both sides"],
  ["tree-down", "Tree, downward"], ["radial", "Radial"], ["logic-right", "Logic chart"], ["timeline", "Timeline"],
  ["fishbone", "Fishbone"], ["tree-table", "Tree table"], ["free", "Free"],
]);

function wbMapEdgeStyle(child) {
  return wbMapThemedData(child).edge_style || WB_MAP_LAYOUT_EDGE[child._bl || wbMapLayout()] || "curve";
}

function wbMapColumnPositions(index, layout) {
  const positions = new Map();
  const size = (o) => wbMapNodeSize(o);
  const gapB = wbMapGapBreadth();
  const gapD = wbMapGapDepth();
  const kidsOf = (o) => (o.data?.collapsed ? [] : index.childrenOf.get(o.id) || []);
  //: A branch as rows: each descendant of `top` with its depth under it.
  const rowsUnder = (top) => {
    const out = [];
    const walk = (o, depth) => {
      for (const kid of kidsOf(o)) {
        out.push({ o: kid, depth });
        walk(kid, depth + 1);
      }
    };
    walk(top, 0);
    return out;
  };
  const extent = (rows) => {
    let w = 0;
    let h = 0;
    for (const r of rows) {
      const s = size(r.o);
      w = Math.max(w, r.depth * WB_MAP_INDENT + s.w);
      h += s.h + gapB;
    }
    return { w, h: rows.length ? h - gapB : 0 };
  };
  //: Rows from `y` down, or up from `y` (each row's bottom at the cursor),
  //: nearest first either way, so a branch reads away from its topic.
  const stack = (rows, x, y, up) => {
    let cursor = y;
    for (const r of rows) {
      const s = size(r.o);
      if (up) {
        cursor -= s.h;
        positions.set(r.o.id, { x: x + r.depth * WB_MAP_INDENT, y: cursor });
        cursor -= gapB;
      } else {
        positions.set(r.o.id, { x: x + r.depth * WB_MAP_INDENT, y: cursor });
        cursor += s.h + gapB;
      }
    }
  };
  const [root, ...others] = index.roots;
  const rs = size(root);
  const kids = kidsOf(root);
  positions.set(root.id, { x: 0, y: 0 });
  let bottom = rs.h;
  if (layout === "timeline") {
    const axis = rs.h / 2;
    let x = rs.w + gapD;
    kids.forEach((kid, i) => {
      const ks = size(kid);
      const rows = rowsUnder(kid);
      const ext = extent(rows);
      positions.set(kid.id, { x, y: axis - ks.h / 2 });
      if (i % 2 === 0) stack(rows, x, axis + ks.h / 2 + gapB, false);
      else stack(rows, x, axis - ks.h / 2 - gapB, true);
      bottom = Math.max(bottom, axis + ks.h / 2 + gapB + ext.h);
      x += Math.max(ks.w, ext.w) + gapD;
    });
  } else if (layout === "tree-table") {
    const top = rs.h + gapD;
    let x = 0;
    for (const kid of kids) {
      const ks = size(kid);
      const rows = rowsUnder(kid).map((r) => ({ o: r.o, depth: r.depth + 1 }));
      const ext = extent(rows);
      positions.set(kid.id, { x, y: top });
      stack(rows, x, top + ks.h + gapB, false);
      bottom = Math.max(bottom, top + ks.h + gapB + ext.h);
      x += Math.max(ks.w, ext.w) + gapB;
    }
    //: The centre over the middle of its columns.
    positions.set(root.id, { x: Math.max(0, (x - gapB - rs.w) / 2), y: 0 });
  } else {
    //: Fishbone: the head on the right, pairs of main branches above and
    //: below a spine at its middle, each pair one slot further left, the
    //: main topic farthest from the spine and its causes between.
    const spine = rs.h / 2;
    let right = -gapD;
    for (let i = 0; i < kids.length; i += 2) {
      const pair = kids.slice(i, i + 2).map((kid) => {
        //: Indented one step, as a tree table's rows are, so the line to a
        //: second cause drops beside the first instead of through it (L-mindmap-12).
        const rows = rowsUnder(kid).map((r) => ({ o: r.o, depth: r.depth + 1 }));
        return { kid, rows, ext: extent(rows), ks: size(kid) };
      });
      const w = Math.max(...pair.map((b) => Math.max(b.ks.w, b.ext.w)));
      const x = right - w;
      pair.forEach((b, side) => {
        const tall = b.ks.h + (b.rows.length ? gapB + b.ext.h : 0);
        if (side === 0) {
          const y = spine - gapD - tall;
          positions.set(b.kid.id, { x, y });
          stack(b.rows, x, y + b.ks.h + gapB, false);
        } else {
          stack(b.rows, x, spine + gapD, false);
          positions.set(b.kid.id, { x, y: spine + gapD + tall - b.ks.h });
          bottom = Math.max(bottom, spine + gapD + tall);
        }
      });
      right = x - gapD;
    }
  }
  //: Any other root, with its branch, in a column under everything.
  let y = bottom + gapD;
  for (const other of others) {
    positions.set(other.id, { x: 0, y });
    const rows = rowsUnder(other).map((r) => ({ o: r.o, depth: r.depth + 1 }));
    stack(rows, 0, y + size(other).h + gapB, false);
    y += size(other).h + gapB + extent(rows).h + gapD;
  }
  //: The first root keeps its place, as in `wbMapTidyPositions`.
  const anchor = positions.get(root.id);
  const dx = root.x - anchor.x;
  const dy = root.y - anchor.y;
  for (const pos of positions.values()) {
    pos.x += dx;
    pos.y += dy;
  }
  return positions;
}

//: The tidy positions for every map node, as `Map(id -> {x, y})`.
//:
//: Pure: it reads sizes and the tree and returns coordinates, touching neither
//: the DOM nor the network. That is what lets `wbMapTidy` below run the whole
//: layout, then paint once and save once, §8's "auto-layout must run off the
//: paint path", which is a real constraint here because the whiteboard already
//: had a lag bug of exactly that shape (task #71).
function wbMapTidyPositions(index, layout) {
  if (!index.roots.length) return new Map();
  const tops = index.nodes.filter((o) => o.data?.branch_layout && !o.data?.collapsed && index.childrenOf.get(o.id)?.length);
  if (tops.length) return wbMapStructuredPositions(index, layout, tops);
  return layout === "free" ? new Map() : wbMapLayoutPositions(index, layout);
}

//: **A branch with its own structure is laid out first, then stands in the
//: map as one box** (XMind's per-branch structure). Innermost first: each
//: such branch is laid out alone as its own layout, its box measured, and in
//: the layout round it the topic is a folded stand-in that big
//: (`_block`, read by `wbMapNodeSize`), so nothing outside can overlap it.
//: Then every stand-in is opened back out at the place it was given. On a
//: Free map only the structured branches move, round their own topic.
function wbMapStructuredPositions(index, layout, tops) {
  const depth = (o) => {
    let d = 0;
    for (let at = o; at?.parent_id != null && d < 500; at = index.byId.get(at.parent_id)) d += 1;
    return d;
  };
  const order = tops.map((o) => [o, depth(o)]).sort((a, b) => b[1] - a[1]).map(([o]) => o);
  const proxies = new Map();
  const blocks = new Map();
  const swap = (o) => proxies.get(o.id) || o;
  const expand = (positions) => {
    for (const [id, block] of blocks) {
      const at = positions.get(id);
      if (!at || !proxies.has(id)) continue;
      //: A fishbone's head is on its right; one whose parent is to its left
      //: is turned round, so the line in meets the head, not the tail.
      const pid = proxies.get(id).parent_id;
      const parent = positions.get(pid) || index.byId.get(pid);
      const turn = block.fish && parent && parent.x < at.x;
      for (const [inner, r] of block.rel) {
        const x = turn ? block.w - r.x - wbMapNodeSize(index.byId.get(inner)).w : r.x;
        positions.set(inner, { x: at.x + x, y: at.y + r.y });
      }
    }
    return positions;
  };
  for (const top of order) {
    //: The top without its own mark, or the layouts that call back into
    //: `wbMapTidyPositions` (both sides, the logic chart) would find it again.
    const root = { ...top, data: { ...top.data, branch_layout: null } };
    const members = wbMapSubtree(index, top.id).map((o) => (o.id === top.id ? root : swap(o)));
    const sub = {
      nodes: members,
      byId: new Map(members.map((o) => [o.id, o])),
      childrenOf: new Map(members.map((o) => [o.id, (index.childrenOf.get(o.id) || []).map(swap)])),
      roots: [root],
    };
    const positions = expand(wbMapLayoutPositions(sub, top.data.branch_layout));
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const [id, pos] of positions) {
      const s = wbMapNodeSize(index.byId.get(id));
      minX = Math.min(minX, pos.x);
      minY = Math.min(minY, pos.y);
      maxX = Math.max(maxX, pos.x + s.w);
      maxY = Math.max(maxY, pos.y + s.h);
    }
    const rel = new Map([...positions].map(([id, pos]) => [id, { x: pos.x - minX, y: pos.y - minY }]));
    blocks.set(top.id, { rel, w: maxX - minX, fish: top.data.branch_layout === "fishbone" });
    proxies.set(top.id, { ...top, data: { ...top.data, collapsed: true }, _block: { w: maxX - minX, h: maxY - minY } });
  }
  if (layout === "free") {
    //: Each outermost structured branch round its own topic, where it is.
    const out = new Map();
    for (const top of order) {
      if (top._bl) continue;
      const own = blocks.get(top.id).rel.get(top.id);
      out.set(top.id, { x: top.x - own.x, y: top.y - own.y });
    }
    return expand(out);
  }
  const outer = {
    nodes: index.nodes.map(swap),
    childrenOf: new Map([...index.childrenOf].map(([id, list]) => [id, list.map(swap)])),
    roots: index.roots.map(swap),
  };
  outer.byId = new Map(outer.nodes.map((o) => [o.id, o]));
  return expand(wbMapLayoutPositions(outer, layout));
}

function wbMapLayoutPositions(index, layout) {
  //: XMind's logic chart is the sideways tree with right-angled lines
  //: (`WB_MAP_LAYOUT_EDGE`); the places are the same.
  if (layout === "logic-right") return wbMapTidyPositions(index, "tree-right");
  if (WB_MAP_COLUMN_LAYOUTS.has(layout)) return wbMapColumnPositions(index, layout);
  //: **Both sides, Coggle's signature** (MINDMAP_PLAN §12.0's own list of
  //: eight layouts, §13.4: "tree-left and both-sides are missing, and
  //: both-sides is Coggle's signature"). It is not a third algorithm: it is
  //: this one twice, with the trunk's children split between the two runs and
  //: the left run mirrored, which is exactly what a both-sides map *is*. Both
  //: runs anchor on the same trunk (the shift at the bottom of this function
  //: keeps `roots[0]` where it already was), so the two halves meet on it
  //: without any arithmetic here.
  //:
  //: **By weight, in order, greedily**: each branch goes to whichever side is
  //: currently lighter, counting the whole subtree rather than the branch
  //: itself. Alternating was the first version and it is wrong on any map
  //: that is not already balanced: measured on a 40-topic map whose four
  //: branches held 1, 1, 1 and 36 topics, alternating put 37 on one side and
  //: 2 on the other, because it counts branches and a person sees topics.
  //: Greedy by weight gives the best split that keeps the branches in the
  //: order they were written, which is the property a person notices second.
  if (layout === "tree-both") {
    const trunk = index.roots[0];
    const kids = index.childrenOf.get(trunk.id) || [];
    if (kids.length < 2) return wbMapTidyPositions(index, "tree-right");
    const rightKids = [];
    const leftKids = [];
    let rightWeight = 0;
    let leftWeight = 0;
    //: **A branch stays on its side** (the owner, 2026-10-10: "New mind map
    //: nodes don't take into account direction of flow for that branch").
    //: Measured: one topic added under a left branch re-ran the greedy split
    //: and sent two other branches across the trunk (A R, B L, C L, D R to
    //: A R, B L, C R, D L). Once the map is already split, each branch that
    //: has a place keeps the side it is drawn on; only a new one (`_fresh`,
    //: or not yet given an id) is dealt to the lighter side. A map not yet
    //: split (just switched to this layout) is dealt from scratch.
    const trunkMid = trunk.x + wbMapNodeSize(trunk).w / 2;
    const placed = (kid) => !kid._fresh && kid.id > 0 && Number.isFinite(kid.x);
    const sideOf = (kid) => (kid.x + wbMapNodeSize(kid).w / 2 < trunkMid ? "left" : "right");
    const drawn = kids.filter(placed).map(sideOf);
    const split = drawn.includes("left") && drawn.includes("right");
    //: The placed branches are weighed before a new one is dealt (bug sweep
    //: 2026-10-12: a new topic sorts first among its siblings, so it was
    //: dealt against empty sides and went right every time, 7 of 8).
    if (split) {
      for (const kid of kids) {
        if (!placed(kid)) continue;
        const weight = wbMapSubtree(index, kid.id).length;
        if (sideOf(kid) === "left") leftWeight += weight;
        else rightWeight += weight;
      }
    }
    for (const kid of kids) {
      const weight = wbMapSubtree(index, kid.id).length;
      if (split && placed(kid)) {
        (sideOf(kid) === "left" ? leftKids : rightKids).push(kid);
        continue;
      }
      if (rightWeight <= leftWeight) {
        rightKids.push(kid);
        rightWeight += weight;
      } else {
        leftKids.push(kid);
        leftWeight += weight;
      }
    }
    //: One side taking everything is not a both-sides map: with a single
    //: branch, or with one branch heavier than every other put together, the
    //: honest answer is the sideways tree it would have been anyway.
    if (!rightKids.length || !leftKids.length) return wbMapTidyPositions(index, "tree-right");
    const side = (keep, onlyTrunk) => ({
      ...index,
      roots: onlyTrunk ? [trunk] : index.roots,
      childrenOf: new Map([...index.childrenOf, [trunk.id, keep]]),
    });
    //: The right run keeps every other root as well, so a map with a second
    //: trunk lays that one out once; the left run is the first trunk's own
    //: branches and nothing else.
    const right = wbMapTidyPositions(side(rightKids, false), "tree-right");
    const left = wbMapTidyPositions(side(leftKids, true), "tree-left");
    const both = new Map(right);
    for (const [id, pos] of left) if (id !== trunk.id) both.set(id, pos);
    return both;
  }
  const vertical = layout === "tree-down" || layout === "radial";
  //: A map that grows to the left is the sideways tree with the depth axis
  //: negated, and the node's own width taken off it because `x` is a left
  //: edge: without that, each level would start where the last one ended and
  //: the boxes would overlap by their own widths.
  const leftward = layout === "tree-left";
  // Breadth is the axis siblings spread along: heights for a map that grows
  // sideways, widths for one that grows downward. Radial spreads siblings
  // around a ring, so its breadth is a width too, arc length, before it is
  // turned into an angle.
  const sizes = new Map(index.nodes.map((o) => [o.id, wbMapNodeSize(o)]));
  //: **Radial measures breadth in angle, not in pixels**, and that is not a
  //: refinement: it is what makes the layout correct near the middle. The
  //: breadth axis becomes the angle, so a fixed pixel gap buys a *wide* angle
  //: at the first ring and a narrow one at the fifth: laid out in pixels, the
  //: nodes closest to the root overlap each other while the outer rings sit in
  //: empty space. Measured before this existed: two overlapping boxes out of
  //: five on the first radial layout. Dividing each node's width by its own
  //: ring number asks for the angle that width actually needs at that radius,
  //: which is d3's own `separation(a, b) / a.depth` in another form. The gap
  //: is folded in here for the same reason, so the distance function keeps
  //: working in one unit.
  const radial = layout === "radial";
  //: How much of a ring a topic takes: its width, or for a structured branch standing in as one
  //: box (`_block`) its longer side, because a tall block taken for its width overlapped its neighbour.
  const wbMapRadialSpan = (obj, size) => {
    const s = size || { w: WB_MAP_NODE_W, h: WB_MAP_NODE_H };
    return obj?._block ? Math.max(s.w, s.h) : s.w;
  };
  const breadthOf = (w) => {
    if (!w.obj) return 0; // the virtual root below has no size of its own
    const s = sizes.get(w.obj.id) || { w: WB_MAP_NODE_W, h: WB_MAP_NODE_H };
    if (radial) return (wbMapRadialSpan(w.obj, s) + wbMapGapBreadth()) / Math.max(1, w.depth);
    return vertical ? s.w : s.h;
  };
  const gap = radial ? 0 : wbMapGapBreadth();

  // One virtual root over the real ones, so a map with two top-level topics
  // is laid out as one tree rather than two overlapping ones. It is dropped
  // before any coordinate is written.
  const wrap = (obj, parent, number, depth) => {
    const node = {
      obj, parent, number, depth, children: [],
      prelim: 0, mod: 0, shift: 0, change: 0, thread: null, ancestor: null,
    };
    node.ancestor = node;
    const kids = obj ? index.childrenOf.get(obj.id) || [] : index.roots;
    // A collapsed branch is not laid out: its children are not on screen, and
    // reserving room for them would leave a hole where the fold is.
    if (!obj || !obj.data?.collapsed) {
      kids.forEach((child, i) => node.children.push(wrap(child, node, i, depth + 1)));
    }
    return node;
  };
  //: **Radial with several top-level topics puts them on the first ring**
  //: (boardfix-1108): they were all depth 0, so radius 0, and sat on one
  //: another (measured: four roots, 6 overlapping pairs of 10 boxes). The
  //: virtual root takes the centre instead; one root still stands on it.
  const virtual = wrap(null, null, 0, radial && index.roots.length > 1 ? 0 : -1);

  wbTidyFirstWalk(virtual, breadthOf, gap);

  // Depth offsets: one per level, from the widest (or tallest) node on it.
  const perDepth = [];
  const collect = (w) => {
    if (w.obj) {
      const s = sizes.get(w.obj.id) || { w: WB_MAP_NODE_W, h: WB_MAP_NODE_H };
      perDepth[w.depth] = Math.max(perDepth[w.depth] || 0, vertical ? s.h : s.w);
    }
    w.children.forEach(collect);
  };
  collect(virtual);
  const ring = Math.max(...perDepth.filter(Number.isFinite), WB_MAP_NODE_W) + wbMapGapDepth();
  const offsets = [0];
  for (let d = 1; d < perDepth.length; d += 1) {
    // Radial does not use these: its radius per ring is worked out below,
    // from the span the first walk actually produced.
    offsets[d] = offsets[d - 1] + (perDepth[d - 1] || 0) + wbMapGapDepth();
  }

  const flat = [];
  const second = (w, m) => {
    if (w.obj) flat.push({ obj: w.obj, breadth: w.prelim + m, depth: w.depth });
    for (const child of w.children) second(child, m + w.mod);
  };
  second(virtual, 0);
  if (!flat.length) return new Map();

  const positions = new Map();
  if (layout === "radial") {
    // x as angle, y as radius, the same call `d3.tree().size([2π, 1])` makes
    // and the same reading of it: the breadth axis, normalised, *is* the angle.
    // The span is padded so the first and last branch do not meet back at the
    // top: by the *smallest* node extent in the layout, which is one node's
    // worth of angle at the outermost ring. Padding by a raw pixel constant
    // was wrong for the same reason the breadths above are divided by depth:
    // it is not a quantity in this unit at all.
    const extentOf = (f) =>
      (wbMapRadialSpan(f.obj, sizes.get(f.obj.id)) + wbMapGapBreadth()) / Math.max(1, f.depth);
    const min = Math.min(...flat.map((f) => f.breadth));
    const max = Math.max(...flat.map((f) => f.breadth));
    const span = max - min + Math.min(...flat.map(extentOf)) || 1;
    //: **The rings grow when the circle runs out of room**, and without this
    //: a radial map overlaps itself as soon as it has more nodes than one
    //: turn can hold. The breadth axis is normalised onto 2π, so the factor
    //: from a breadth unit to an angle is `2π / span`, while the arc a node
    //: needs at depth `d` is its own breadth divided by the ring spacing (the
    //: breadths above are already divided by depth for exactly this reason).
    //: The two agree only while `span <= 2π * ring`; past that the normalise
    //: silently compresses every node into less arc than it occupies. So the
    //: spacing is whichever is larger, which spreads a big map over wider
    //: rings instead of stacking it on top of itself, and is a no-op on any
    //: map small enough that the base spacing was already sufficient.
    //: Measured (WHITEBOARD_PLAN Phase 4, `wbphase4.js`): 30 nodes in radial
    //: gave 6 overlapping pairs, the worst 38x28 board units, and 0 after.
    //: Arc length is the centres' distance, but boxes meet at their corners, so a
    //: wide block beside a narrow topic can still touch (a structured branch
    //: standing in as one box, measured 6 units). The rings widen by a tenth
    //: until no two boxes overlap, at most twelve times; a no-op on a clear map.
    let ringRadius = Math.max(ring, span / (2 * Math.PI));
    for (let tries = 0; tries < 12; tries += 1) {
      positions.clear();
      for (const f of flat) {
        const size = sizes.get(f.obj.id) || { w: WB_MAP_NODE_W, h: WB_MAP_NODE_H };
        const angle = ((f.breadth - min) / span) * 2 * Math.PI - Math.PI / 2;
        const radius = f.depth * ringRadius;
        // Centres, then back to the top-left corner an object's `x`/`y` mean.
        positions.set(f.obj.id, {
          x: radius * Math.cos(angle) - size.w / 2,
          y: radius * Math.sin(angle) - size.h / 2,
        });
      }
      const boxes = flat.map((f) => ({ ...positions.get(f.obj.id), ...(sizes.get(f.obj.id) || { w: WB_MAP_NODE_W, h: WB_MAP_NODE_H }) }));
      const touching = boxes.some((a, i) => boxes.slice(i + 1).some((c) =>
        Math.min(a.x + a.w, c.x + c.w) - Math.max(a.x, c.x) > 1 && Math.min(a.y + a.h, c.y + c.h) - Math.max(a.y, c.y) > 1));
      if (!touching) break;
      ringRadius *= 1.1;
    }
  } else {
    for (const f of flat) {
      const size = sizes.get(f.obj.id) || { w: WB_MAP_NODE_W, h: WB_MAP_NODE_H };
      const along = offsets[f.depth] || 0;
      positions.set(f.obj.id, vertical
        ? { x: f.breadth - size.w / 2, y: along }
        : { x: leftward ? -along - size.w : along, y: f.breadth - size.h / 2 });
    }
  }

  // Shift the whole layout so the first root keeps the position it already
  // had. "Tidy this map" means tidy it, not "recentre my board", the same
  // choice, for the same reason, `wbArrangeMindMap` makes further up.
  const anchor = positions.get(index.roots[0].id);
  if (anchor) {
    const dx = index.roots[0].x - anchor.x;
    const dy = index.roots[0].y - anchor.y;
    for (const pos of positions.values()) {
      pos.x += dx;
      pos.y += dy;
    }
  }
  return positions;
}

//: Lay the map out and save it: compute everything, paint once, then write.
//:
//: The three phases are the point. `wbMapTidyPositions` touches nothing;
//: `wbApplyBulkMove` moves every element in one pass; `wbSaveBulkMove` is the
//: only part that goes near the network, and it runs after the paint. That is
//: §8's "auto-layout must run off the paint path", and it reuses the two
//: functions a multi-item drag already uses rather than writing a third way to
//: move a set of things.
async function wbMapTidy({ onlyBranch = null, quiet = false } = {}) {
  if (!wbIsMap()) return 0;
  const layout = wbMapLayout();
  if (!wbMapLaysOut()) {
    if (!quiet) toast("This map's layout is Free, pick a layout to tidy it.");
    return 0;
  }
  const origin = wbMapTidyOrigin(onlyBranch, layout);
  if (!origin.size) return 0;
  // Zero delta, because each entry already carries its own target, the
  // bulk-move helper adds `dx`/`dy` to the origin it was given, so handing it
  // the destinations and no delta is how one shared helper does a per-node
  // layout as well as a rigid drag.
  wbApplyBulkMove(origin, 0, 0);
  renderWhiteboardNow();
  //: **A tidy that pushed the map off the canvas frames it again.** Recorded
  //: by the seventh run and left as a decision rather than a bug: measured at
  //: 390x844 after a tidy, the trunk's own box sat at x=-95 and
  //: `elementFromPoint` at its centre returned the shell behind the canvas, so
  //: the one node a person would reach for was not on screen. §12.0 says
  //: auto-arrange is a command and not a constant, which is why this does not
  //: frame on every tidy: it frames only a *whole-map* tidy, and only when
  //: something has actually gone past an edge. A branch tidy is the silent
  //: half of pressing Tab and must never move the view while someone is
  //: typing, and a tidy whose result already fits is a view nobody asked to
  //: have changed.
  if (onlyBranch == null && wbMapSpillsOffCanvas()) wbFrameSpilledMap();
  await wbSaveBulkMove(origin);
  return origin.size;
}

//: The moves a tidy would make, as a bulk-move origin, touching nothing
//: (`wbMapTidy` applies, paints and saves them; the optimistic add applies
//: them and leaves the paint to its one render).
function wbMapTidyOrigin(onlyBranch, layout = wbMapLayout()) {
  const index = wbMapIndex();
  const positions = wbMapTidyPositions(index, layout);
  const origin = new Map();
  if (!positions.size) return origin;

  // Which nodes this run is allowed to move. A branch tidy (after adding a
  // child) touches only that branch, so the rest of the map does not jump
  // under you while you are typing into a new node.
  const scope = onlyBranch != null
    ? new Set(wbMapSubtree(index, onlyBranch).map((o) => o.id))
    : null;

  for (const [id, pos] of positions) {
    const obj = index.byId.get(id);
    if (!obj) continue;
    if (scope && !scope.has(id)) continue;
    // **A dragged node is pinned, and a pinned node keeps its place.** That is
    // Coggle's bargain: tidy is on demand, and anything you positioned by hand
    // is a decision, not a thing to be undone by the next tidy. Its children
    // still take their tidy positions, the fold is in the branch, not the
    // whole map.
    if (obj.data?.pinned) continue;
    //: **A branch under a pinned topic is tidied where that topic sits** (the
    //: owner, 2026-10-11: a child added under a dragged topic took the
    //: layout's own column, 1,400px away, with its line across the map). Its
    //: tidy place is shifted by how far the nearest pinned ancestor was
    //: dragged from its own, so the branch keeps its shape beside it.
    let ancestor = obj.parent_id != null ? index.byId.get(obj.parent_id) : null;
    for (let hops = 0; ancestor && !ancestor.data?.pinned && hops < 200; hops++) {
      ancestor = ancestor.parent_id != null ? index.byId.get(ancestor.parent_id) : null;
    }
    const home = ancestor ? positions.get(ancestor.id) : null;
    const to = home ? { x: pos.x + (ancestor.x - home.x), y: pos.y + (ancestor.y - home.y) } : pos;
    if (Math.abs(obj.x - to.x) < 0.5 && Math.abs(obj.y - to.y) < 0.5) continue;
    origin.set(wbMultiKey("object", id), { kind: "object", id, item: obj, x: to.x, y: to.y });
  }
  return origin;
}

//: **A map that arrived from a file or a proposal is laid out once, as it
//: opens** (audit FEAT-05, 2026-10-05). The server places an import as a
//: ladder, one row per topic, which is readable but is not the layout the
//: map names; the first Tab then tidied one branch against a ladder and the
//: branches overlapped. One whole-map tidy at open, no undo entry (a tidy
//: never records one), then the view is framed again.
async function wbMapTidyFresh() {
  if (!wbIsMap() || wbMapLayout() === "free") return;
  //: Run as plain rather than as a recorded gesture (`wbRecordGesture`): the
  //: map arrived this way, and an Undo that un-tidied it would be a step
  //: nobody took.
  wbRecordDepth += 1;
  try {
    await wbMapTidy({ quiet: true });
  } finally {
    wbRecordDepth -= 1;
  }
  wbFrameMapOnOpen();
}

//: A whole-map tidy that spilled fits the map, as it always did; only a narrow
//: canvas (`wbMapFrameScales`) takes the phone frame, where a fit reads at 4px.
//: On desktop `wbFrameMapOnOpen` would jump a large map to its root at 1:1
//: instead of showing all of it.
function wbFrameSpilledMap() {
  const container = document.getElementById("whiteboard-container");
  if (container && wbMapFrameScales(container).open < 1) wbFrameMapOnOpen();
  else wbZoomToFit({ animate: false });
}

//: Is any part of the map outside the canvas right now? Read off the rendered
//: boxes rather than off the stored coordinates, because what matters is what
//: is on screen at the zoom in force, which is the thing the report was about.
function wbMapSpillsOffCanvas() {
  const container = document.getElementById("whiteboard-container");
  if (!container) return false;
  const box = container.getBoundingClientRect();
  let spilled = false;
  for (const el of document.querySelectorAll("#wb-html-layer .wb-object")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (r.left < box.left || r.top < box.top || r.right > box.right || r.bottom > box.bottom) {
      spilled = true;
      break;
    }
  }
  return spilled;
}

//: Re-tidy one branch after a node was added to it, when the layout asks for
//: it. Silent by design: this runs as part of Tab, and a toast per keystroke
//: while building a map out is noise, not feedback.
async function wbMapTidyBranch(parentId) {
  if (!wbIsMap() || !wbMapLaysOut()) return;
  await wbMapTidy({ onlyBranch: wbMapTidyBranchScope(parentId), quiet: true });
}

// Whole-map when a root gained a child: a new top-level branch changes where
// every other branch has to sit, so tidying only the new one would leave it
// sitting on top of its neighbour.
function wbMapTidyBranchScope(parentId) {
  if (WB_MAP_COLUMN_LAYOUTS.has(wbMapLayout())) return null;
  const index = wbMapIndex();
  //: A structured branch that grows moves whatever sits beside its box.
  if (index.nodes.some((o) => o.data?.branch_layout)) return null;
  const parent = parentId != null ? index.byId.get(parentId) : null;
  return parent && parent.parent_id != null ? parent.parent_id : null;
}

//: The add's tidy (`wbMapAddChild`): the branch's moves, with the new topic
//: placed directly (it has no element yet for a move to carry), or null on a
//: Free map, where a new topic stays where it was put.
function wbMapTidyBranchPlan(parentId, fresh) {
  if (!wbIsMap() || !wbMapLaysOut()) return null;
  const layout = wbMapLayout();
  const origin = wbMapTidyOrigin(wbMapTidyBranchScope(parentId), layout);
  const own = origin.get(wbMultiKey("object", fresh.id));
  if (own) {
    fresh.x = own.x;
    fresh.y = own.y;
    origin.delete(wbMultiKey("object", fresh.id));
  }
  //: Every moved topic's element from one walk of the layer, not one
  //: document-wide query each (93ms of a Tab at 301 topics, profiled).
  if (origin.size) {
    const byId = new Map();
    for (const el of document.querySelectorAll("#wb-html-layer .wb-object[data-id]")) byId.set(el.dataset.id, el);
    for (const entry of origin.values()) entry.el = byId.get(String(entry.id)) || null;
  }
  return origin;
}

//: The board top bar's map controls: a "Map" chip that says what this board
//: is, the layout picker, and Tidy. All three are hidden on an ordinary
//: whiteboard rather than disabled, a control that can never apply here is
//: not a control you want to read past on every other board.
//:
//: The chip is `.library-chip`, which is the app's own filter-chip recipe
//: (DESIGN.md, "the interactive filter chip"), not a badge invented for the
//: canvas.
//: The whiteboard tools a map has no use for, by the tool name the dock
//: button carries. Freehand, the highlighter, the eraser and the fill paint on
//: a surface a map does not have; the six shapes, the sticky, the free text
//: box and the image place things a tree cannot hold, since everything on a
//: map is a node with a parent. Kept as a set rather than read off the hidden
//: sections, because this also has to answer "was the tool that is *currently*
//: selected one of these" after a board-to-map switch.
const WB_BOARD_ONLY_TOOLS = new Set([
  "draw", "highlighter", "eraser", "bucket",
  "line", "arrow", "rect", "circle", "triangle", "diamond",
  "sticky", "text", "frame",
]);

//: Which dock sections a map shows (MINDMAP_PLAN.md §12.0).
//:
//: The owner: "even though it is built off the whiteboard, it isnt the white
//: board and they needs to stay relatively separate with the mindmap having
//: controls specific to it, but the mindmap can keep important and usable
//: parts of the whiteboard." So this is a split, not a second dock: the
//: sections that only make sense on a board are marked in the markup, the
//: map's own sections are marked the other way, and the shared three (move,
//: connect, edit) carry no marker at all and are never touched here.
//: **The rail says which of the map's two connections its Connect tools
//: make** (MINDMAP_PLAN §13c). §13.3 measured the exact place the owner's
//: "there are two types of connections" is *felt*: the Connect section's two
//: buttons are the only things on screen with the word Connect on them, and
//: both make a **cross-link**. Nothing on the rail makes a branch, because a
//: branch is Tab, Enter, the ring or the node's own `+`. The words are the
//: cheapest possible fix and the one the plan asked for: on a map the tools
//: say cross-link and the section says what the other kind is and where it
//: comes from. On a board there is only one kind of link, so the board's own
//: words are left exactly as they were.
const WB_CONNECT_WORDS = {
  map: {
    section: ["Cross-link", "Join two branches without changing the tree. A branch itself is Tab, or the topic's own +"],
    "link-straight": ["Cross-link (C)", "Cross-link (C): drag from one topic to another. It is drawn in this map's own line style, dashed, and joins two branches without changing the tree"],
    "link-curved": ["Cross-link (C)", "Cross-link (C): drag from one topic to another"],
  },
  board: {
    section: ["Connect", "Join two things together"],
    "link-straight": ["Straight link (C)", "Straight link (C): drag from one card to another"],
    "link-curved": ["Curved link (Shift+C)", "Curved link (Shift+C): drag from one card to another"],
  },
};

//: **On a map, one connection tool that looks like the map's own lines**
//: (INBOX 392, the owner: "the connections in the bottom bar are different
//: from the ones the mind map nodes use"). A board offers a straight and a
//: curved link because a board has no line style of its own; a map does
//: (Straight, Curve or Elbow, `edge_style`), and offering two generic shapes
//: beside it said a cross-link was a different kind of drawing. So a map
//: shows one tool, drawn in the map's style and dashed (a cross-link's own
//: mark, §13c), and what it draws follows the same style.
//: **A cross-link on a map is drawn by the map, not by the board** (owner,
//: with a screenshot: "these links I drew using the cross-link tools are
//: different from the ones between the other mind map nodes ... I want them
//: to be the same"). Measured on that map: the branches were tapered ribbons
//: in their branch's colour leaving each topic's facing side, and the
//: cross-link was a 3px straight cyan line from the bottom anchor of one
//: topic, because a link is a board sketch and was drawn with the pen's
//: colour and the board's link geometry. So between two topics this returns
//: the branch drawing itself: `wbMapEdgePathD` and `wbMapRibbonD` between
//: the two topics' facing sides, in the map's line style, weight and taper,
//: coloured like the source topic's branch. A stand-in child carries only
//: the map's style, so the target's own tree edge (its bend, its slide) is
//: not borrowed. `null` off a map, for any end that is not a topic, and for
//: a link someone has bent by hand, which keeps the board's own bent curve.
//: Built once per render pass (the microtask reset), since a render asks
//: for every link and the index and colours are a walk of the whole map.
let wbMapCrossLinkMemo = null;
function wbMapCrossLinkLook(parsed) {
  if (!wbIsMap() || !parsed?.type?.startsWith("link-")) return null;
  const source = wbLinkItem(parsed.sourceKind || "node", parsed.sourceId);
  const target = wbLinkItem(parsed.targetKind || "node", parsed.targetId);
  if (!source || !target || !WB_MAP_KINDS.has(source.kind) || !WB_MAP_KINDS.has(target.kind)) return null;
  if (!wbMapCrossLinkMemo) {
    const index = wbMapIndex();
    wbMapCrossLinkMemo = { index, colors: wbMapNodeColors(index), layout: wbMapLayout(), looks: new Map() };
    queueMicrotask(() => { wbMapCrossLinkMemo = null; });
  }
  const { index, colors, layout } = wbMapCrossLinkMemo;
  //: **Found once per link per pass** (W30 D26). One render asked for the same link's look three times
  //: (the path, the hand-drawn check, the label), 300 links at 4x CPU were about 640 ms of it. Keyed on
  //: everything the drawing reads from its two ends, so a node moved between two asks in one task is
  //: never answered with the old line; a branch laid out as a block (`_bl`) is not kept at all.
  const sz = (item) => (item._block ? null : wbMapNodeSize(item));
  const sourceBox = sz(source);
  const targetBox = sz(target);
  const kept = !source._bl && !target._bl && target._blTop == null && !source._block && !target._block;
  const stamp = kept
    ? `${parsed.type}|${source.id}|${target.id}|${source.x},${source.y},${source.parent_id}|${target.x},${target.y},${target.parent_id}|${sourceBox.w}x${sourceBox.h}|${targetBox.w}x${targetBox.h}|${parsed.bend ? `${parsed.bend.x},${parsed.bend.y}` : ""}|${JSON.stringify(parsed.sourceAnchor || 0)}${JSON.stringify(parsed.targetAnchor || 0)}`
    : "";
  const held = stamp ? wbMapCrossLinkMemo.looks.get(stamp) : undefined;
  if (held !== undefined) return held;
  const found = wbMapCrossLinkLook.built(parsed, source, target, index, colors, layout);
  if (stamp) wbMapCrossLinkMemo.looks.set(stamp, found);
  return found;
}

wbMapCrossLinkLook.built = function (parsed, source, target, index, colors, layout) {
  //: A leaf has no colour of its own (null in the map): it wears its
  //: branch's, so the nearest coloured ancestor is the one its line has.
  //: A root has none at all, so a link from one takes the target's branch,
  //: and failing both, the accent an uncoloured map line already draws in.
  const branchColour = (from) => {
    for (let at = from, hops = 0; at && hops < 64; hops++) {
      const own = colors.get(at.id);
      if (own) return own;
      at = at.parent_id != null ? index.byId.get(at.parent_id) : null;
    }
    return "";
  };
  const colour = branchColour(source) || branchColour(target) || currentAccentHex();
  //: Bent by hand: the board's own bent curve, still in the branch's colour
  //: and weight, since a bend is the one shape the map's lines cannot hold.
  if (parsed.bend && (parsed.bend.x || parsed.bend.y)) {
    const ends = wbResolveLinkEndpoints(parsed);
    if (!ends) return null;
    const line = wbLinkPathD("link-curved", ends.source, ends.target, null, 3, parsed.bend);
    return { line, d: line, ribbon: false, colour, width: 3 };
  }
  const style = wbMapTheme().edge_style || "curve";
  //: An end dropped on one of a topic's side ports keeps that side (K31):
  //: a board anchor is two fractions of the box, and a port on an edge's
  //: middle names the side the map's own pinned ends use.
  const sideOf = (f) => (!f ? null : f.y <= 0 ? "top" : f.y >= 1 ? "bottom" : f.x <= 0 ? "left" : f.x >= 1 ? "right" : null);
  const ghost = {
    ...target,
    data: { edge_style: style, edge_from: sideOf(parsed.sourceAnchor), edge_to: sideOf(parsed.targetAnchor) },
  };
  const line = wbMapEdgePathD(source, ghost, layout);
  const ribbon = wbMapEdgeIsRibbon(ghost);
  return {
    line,
    d: ribbon ? wbMapRibbonD(source, ghost, layout) : line,
    ribbon,
    colour,
    width: 3 * wbMapEdgeWeight(ghost),
  };
};

//: Where a drawn line starts and ends, read off its own path: the first
//: `M x y` and the last pair of numbers, which is the end point in every
//: command the map's lines use (L, C, and the elbow's run of Ls). The link's
//: handles sit here, so on a map they are on the line that is drawn rather
//: than on the board's anchor the link was first dropped on.
function wbPathEnds(d) {
  const nums = String(d).match(/-?\d*\.?\d+(?:e-?\d+)?/gi)?.map(Number) || [];
  if (nums.length < 4) return null;
  return {
    source: { x: nums[0], y: nums[1] },
    target: { x: nums[nums.length - 2], y: nums[nums.length - 1] },
  };
}

function wbMapCrossLinkType() {
  const style = window.wbMapState?.theme?.edge_style || "curve";
  return style === "straight" ? "link-straight" : "link-curved";
}

const WB_MAP_LINK_GLYPH = {
  curve: "M4 20 C4 11 20 13 20 4",
  straight: "M4 20 L20 4",
  elbow: "M4 20 L12 20 L12 4 L20 4",
};

function wbSyncMapLinkGlyph(button, isMap) {
  const svg = button?.querySelector("svg");
  if (!svg) return;
  let glyph = svg.querySelector("path.wb-map-link-glyph");
  for (const child of svg.children) {
    if (child !== glyph) child.classList.toggle("hidden", isMap);
  }
  if (!isMap) {
    glyph?.remove();
    return;
  }
  if (!glyph) {
    glyph = document.createElementNS("http://www.w3.org/2000/svg", "path");
    glyph.setAttribute("class", "wb-map-link-glyph");
    glyph.setAttribute("stroke-dasharray", "3 3");
    svg.appendChild(glyph);
  }
  glyph.setAttribute("d", WB_MAP_LINK_GLYPH[window.wbMapState?.theme?.edge_style] || WB_MAP_LINK_GLYPH.curve);
}

function wbSyncConnectWords(isMap) {
  const words = WB_CONNECT_WORDS[isMap ? "map" : "board"];
  //: Found by its role in the rail, not by its label: the label is what this
  //: function rewrites, so a lookup by `aria-label="Connect"` found nothing
  //: once a map had renamed it, and a board opened after a map kept the map's
  //: words.
  const section = document.querySelector("#wb-tool-group [data-tool=\"link-straight\"]")?.closest(".wb-tool-section");
  if (section) {
    const label = section.querySelector(".wb-tool-section-label");
    if (label) {
      label.textContent = words.section[0];
      label.title = words.section[1];
    }
    //: The group's own accessible name as well as the word in it: the label
    //: is `1x1` on screen (the rail's sections are named for a screen reader,
    //: not drawn), so the `aria-label` is what a screen reader actually says
    //: here and leaving it as "Connect" would keep the old vocabulary in the
    //: one place it is read aloud.
    section.setAttribute("aria-label", words.section[0]);
  }
  for (const tool of ["link-straight", "link-curved"]) {
    const button = document.querySelector(`#wb-tool-group [data-tool="${tool}"]`);
    if (!button) continue;
    button.setAttribute("aria-label", words[tool][0]);
    button.title = words[tool][1];
  }
  const straight = document.querySelector('#wb-tool-group [data-tool="link-straight"]');
  const curved = document.querySelector('#wb-tool-group [data-tool="link-curved"]');
  if (curved) curved.hidden = isMap;
  wbSyncMapLinkGlyph(straight, isMap);
}

// whiteboard-map-strip.js: whiteboard-map-strip.js: the map's topic strip, its sync with the selected node  (moved out, L286).
//: A guard, not a convenience. `enhanceSelect` mirrors the real `<select>`
//: into its own opener on the `change` event only, so a value written here
//: without dispatching one leaves the visible control reading the previous
//: node's value. Dispatching it lands in this file's own change handlers,
//: which would then save the value straight back onto the node: this flag is
//: what tells them the change came from the sync rather than from a person.
let wbMapStripSyncing = false;

//: The node the open ring belongs to. Read at click time by every slot, so a
//: ring still showing across a render acts on the node it was opened for rather
//: than on whatever is selected now.
let wbMapRadialFor = null;

function wbOpenMapRadial(node) {
  const ring = document.getElementById("wb-map-radial");
  const container = document.getElementById("whiteboard-container");
  const host = document.getElementById("library-view-whiteboard");
  if (!ring || !container || !host || !node) return false;
  const box = wbItemBBox("object", node);
  if (!box) return false;
  // The node's centre in the view's own coordinates, through the live zoom
  // transform: the same route `wbUpdateSelectionBar` takes, because a ring
  // placed from the pointer instead would sit off-centre on every node whose
  // edge you happened to right-click.
  const t = d3.zoomTransform(container);
  const rect = container.getBoundingClientRect();
  const hostRect = host.getBoundingClientRect();
  const cx = rect.left - hostRect.left + t.applyX((box.minX + box.maxX) / 2);
  const cy = rect.top - hostRect.top + t.applyY((box.minY + box.maxY) / 2);
  wbMapRadialFor = node.id;
  //: The node's box on screen, not on the board: the slots are a fixed size in
  //: px whatever the zoom, so what the ring has to clear is what the node
  //: measures at the zoom in force.
  const shift = wbPlaceMapRadial(ring, host, cx, cy, {
    w: (box.maxX - box.minX) * t.k,
    h: (box.maxY - box.minY) * t.k,
  });
  //: **The topic goes with its ring.** A ring slid in from an edge is a ring
  //: whose hole no longer holds its topic, and the hole is the point of a pie
  //: (measured on a map's first topic, under the top bar: slid 118px down,
  //: the topic was behind the Add child sector). So the board pans by the
  //: same amount, once, and the topic is in the middle of the hole wherever
  //: it was on screen. Not animated: the ring is already drawn at the end
  //: position, and a board easing towards it would be a topic sliding
  //: through its own ring.
  if (shift && (shift.dx || shift.dy)) {
    d3.select(container).call(wbZoom.translateBy, shift.dx / t.k, shift.dy / t.k);
  }
  wbSyncMapRadialAlt(false);
  const collapse = document.getElementById("wb-radial-collapse");
  if (collapse) {
    const folded = Boolean(node.data?.collapsed);
    const label = folded ? "Open this branch again (C)" : "Fold this branch away (C)";
    collapse.title = label;
    collapse.setAttribute("aria-label", label);
    const name = collapse.querySelector(".wb-map-radial-name");
    if (name) name.textContent = folded ? "Unfold" : "Fold";
    //: A leaf has nothing to fold. Disabled rather than gone: a ring whose
    //: slots move about with the node under them is a ring nobody can learn.
    collapse.disabled = (wbMapIndex().childrenOf.get(node.id) || []).length === 0;
    const glyph = collapse.querySelector("i");
    if (glyph) glyph.className = `ph ph-caret-circle-${folded ? "right" : "down"}`;
  }
  wbMarkMapRadialNode(node.id);
  wbUpdateSelectionBar();
  return true;
}

//: The node an open ring acts on, or null. Every slot goes through this so a
//: ring whose node has since been deleted closes instead of throwing.
function wbMapRadialNode() {
  if (wbMapRadialFor == null) return null;
  const node = (wbState.objects || []).find((o) => o.id === wbMapRadialFor);
  if (!node || !WB_MAP_KINDS.has(node.kind)) {
    wbCloseMapRadial();
    return null;
  }
  return node;
}

//: Copy a branch: this topic and everything under it, as a sibling of itself.
//:
//: Built from the node endpoint rather than from the board's copy/paste,
//: which works on a flat selection and would paste ten unrelated boxes where
//: a branch was. Parents before children (`wbMapSubtree` returns them in that
//: order), so every child's new parent already exists by the time it is
//: created: an old id maps to a new one exactly once.
async function wbMapCopyBranch(id) {
  const index = wbMapIndex();
  const source = index.byId.get(id);
  if (!source) return;
  const subtree = wbMapSubtree(index, id);
  if (subtree.length > WB_MAP_COPY_MAX) {
    toast(`That branch has ${nounCount(subtree.length, "topic")}: copying stops at ${WB_MAP_COPY_MAX}.`, "info");
    return;
  }
  const mapped = new Map();
  for (const node of subtree) {
    const parentId = node.id === id
      ? (index.byId.has(node.parent_id) ? node.parent_id : null)
      : mapped.get(node.parent_id);
    // A child whose parent failed to copy has nowhere to go: stop rather than
    // scattering the rest of the branch at the top level.
    if (node.id !== id && parentId == null) break;
    const created = await wbMapCreateNode({
      parentId: parentId ?? null,
      kind: node.kind,
      text: wbMapLabel(node),
      refId: node.data?.ref_id ?? null,
    });
    if (!created) break;
    // The copy looks like the original: the styling lives in `data` and the
    // create endpoint only takes a label, so it is written straight after.
    const style = {};
    for (const key of [...WB_MAP_STYLE_KEYS, ...WB_MAP_CONTENT_KEYS]) {
      if (node.data?.[key] != null) style[key] = node.data[key];
    }
    if (Object.keys(style).length) {
      created.data = { ...created.data, ...style };
      await wbSaveObject(created);
    }
    mapped.set(node.id, created.id);
  }
  await wbMapTidy({ quiet: true });
  renderWhiteboardNow();
  const rootCopy = mapped.get(id);
  if (rootCopy) selectWbItem("object", rootCopy);
  toast(`Copied ${nounCount(mapped.size, "topic")}.`);
}

//: A branch big enough that copying it is a mistake rather than an intention.
//: One POST per node (there is no bulk create), so a thousand-node branch
//: would be a thousand requests: the same shape `wbSaveBulkMove` already
//: pays for, and the reason a cap is kinder than a progress bar here.
const WB_MAP_COPY_MAX = 120;

//: Everything the strip and the radial can set on a node, in one list, so a
//: copy carries what the original wore and "reset to the branch" clears
//: exactly the same set. A key added to one and not the other is how a copy
//: quietly loses its colour.
//:
//: The line's own four (`edge_style`, `edge_dashed`, `edge_width`,
//: `edge_arrow`) belong here for the same reason its label always did: they
//: are written from the strip and the link ring onto the node, so a branch
//: copied without them comes out drawn differently from the one it was copied
//: from. The first two were missing until item 177 added the other two, which
//: is what made the gap worth closing rather than recording again: half a
//: line's look travelling with a copy is worse than none of it.
const WB_MAP_STYLE_KEYS = [
  "color", "bold", "italic", "font_size", "align", "icon", "link", "edge_label",
  "edge_label_dx", "edge_label_dy", "edge_label_size", "edge_label_bold", "edge_label_color", "edge_label_chip",
  "shape", "core", "spine", "fill", "effect", "edge_style", "edge_dashed", "edge_width", "edge_arrow",
  //: The waypoint on the line (§12.1 item 5's third) belongs with the other
  //: four for the same reason: it is written from the line itself onto the
  //: node, and a branch copied without it comes out drawn differently from the
  //: one it was copied from.
  "edge_bend", "edge_slide", "edge_from", "edge_to",
];

//: What a copy carries that "back to the branch" must **not** drop: a picture
//: in a topic (§12.1 item 2's fourth) is content, not a look. Reset's whole
//: promise is that it is the safe way out of a topic you have over-decorated,
//: and a reset that also threw away the picture somebody uploaded would make
//: it the one control on this map you cannot press to find out what it does.
//: Two lists rather than one flag, because the two questions are different
//: ones and a boolean beside each key would be read as neither.
//: A task (decision 15) is content for the same reason: "reset this topic's
//: look" must not untick or un-task anything.
//: And a note (decision 18): a reset is about looks, never about words.
//: And a boundary and a summary (decisions 19, 20): what the map says.
const WB_MAP_CONTENT_KEYS = [
  "image", "task", "note", "boundary", "boundary_label", "boundary_set", "summary", "summary_span",
  "priority", "progress", "flag", "markers", "due", "due_time", "start", "recording", "branch_layout", "callout", "labels", "stamps", "stamped",
];

//: **Reaction stamps and votes** (Miro; MINDMAP_PLAN 14.4): six Phosphor
//: glyphs, not emoji, for decision 34's reason (an emoji is drawn
//: differently by every system), each with its count.
const WB_MAP_STAMPS = Object.freeze([
  ["up", "thumbs-up", "Vote"], ["heart", "heart", "Love it"], ["star", "star", "Star"],
  ["check", "check-circle", "Agree"], ["question", "question", "Question"], ["fire", "fire", "Hot"],
]);

//: **A stamp is a toggle per person** (INBOX 1493, "no wqay tp remove a stamp
//: vote"): a press adds yours, a second press takes yours back; `stamped` names
//: the stamps that are yours, each one counted in `stamps` too. A count from
//: before the toggle has no owner, so it comes down with the chip's menu:
//: Remove one ("one") or Clear all ("all"). Pure: returns the patch and the
//: words for the live region, or null when there is nothing to do.
function wbMapStampPatch(data, name, how) {
  const known = WB_MAP_STAMPS.find(([n]) => n === name);
  if (!known) return null;
  const stamps = { ...(data?.stamps || {}) };
  let mine = (Array.isArray(data?.stamped) ? data.stamped : []).filter((n) => stamps[n] > 0 && n !== name);
  const owned = Array.isArray(data?.stamped) && data.stamped.includes(name);
  const count = stamps[name] || 0;
  let said;
  if (how === "toggle" && owned) {
    stamps[name] = count - 1;
    said = `${known[2]}: yours taken back.`;
  } else if (how === "toggle") {
    if (count >= 999) return null;
    stamps[name] = count + 1;
    mine.push(name);
    said = `${known[2]}: yours added.`;
  } else if (!count) {
    return null;
  } else if (how === "one") {
    stamps[name] = count - 1;
    if (owned && stamps[name] > 0) mine.push(name);
    said = `${known[2]}: one removed.`;
  } else {
    delete stamps[name];
    said = `${known[2]}: cleared.`;
  }
  if (!(stamps[name] > 0)) delete stamps[name];
  return { stamps: Object.keys(stamps).length ? stamps : null, stamped: mine.length ? mine : null, said };
}

//: One press, one Undo step.
async function wbMapStampSet(node, name, how) {
  const patch = node ? wbMapStampPatch(node.data, name, how) : null;
  if (patch) await wbMapSetExtra(node, { stamps: patch.stamps, stamped: patch.stamped }, patch.said);
}

//: A topic's callout (canvasdepth2), read off its own data: content. The
//: card wraps (`data-extras`) only while it carries one, so every other topic
//: keeps the one row it has always been.
function wbMapPaintExtras(node, data) {
  const callout = node.querySelector(".wb-map-callout");
  const words = typeof data.callout === "string" ? data.callout.trim() : "";
  if (callout) {
    callout.hidden = !words;
    if (callout.textContent !== words) callout.textContent = words;
    callout.title = words ? "Callout: double-click to change it" : "";
  }
  const tags = node.querySelector(".wb-map-tags");
  const labels = Array.isArray(data.labels) ? data.labels.filter((l) => typeof l === "string" && l.trim()) : [];
  const stamps = WB_MAP_STAMPS.filter(([name]) => data.stamps?.[name] > 0);
  if (tags) {
    tags.hidden = !labels.length && !stamps.length;
    const mine = Array.isArray(data.stamped) ? data.stamped : [];
    const key = `${labels.join("\u0000")}|${stamps.map(([name]) => `${name}${data.stamps[name]}${mine.includes(name) ? "m" : ""}`).join(",")}`;
    if (tags.dataset.key !== key) {
      tags.dataset.key = key;
      tags.replaceChildren(...labels.map((label) => {
        const chip = document.createElement("span");
        chip.className = "wb-map-tag";
        chip.textContent = label;
        return chip;
      }), ...stamps.map(([name, glyph, said]) => {
        const yours = mine.includes(name);
        const wrap = document.createElement("span");
        wrap.className = "wb-map-stamp-wrap";
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "wb-map-stamp";
        chip.dataset.stamp = name;
        chip.setAttribute("aria-pressed", String(yours));
        chip.title = `${said}: ${yours ? "press to take yours back" : "press to add yours"}`;
        chip.setAttribute("aria-label", `${said}, ${data.stamps[name]}${yours ? ", yours included" : ""}. ${yours ? "Press to take yours back." : "Press to add yours."}`);
        const icon = document.createElement("i");
        icon.className = `ph ph-${glyph}`;
        icon.setAttribute("aria-hidden", "true");
        chip.append(icon, String(data.stamps[name]));
        const live = () => wbMapLiveDatum({ id: Number(node.dataset.id) });
        wrap.append(chip, kebabMenu([
          { label: "Remove one", title: "Takes one off the count", run: () => wbMapStampSet(live(), name, "one") },
          { label: "Clear all", title: "Every count of this stamp; Ctrl+Z brings them back", danger: true, run: () => wbMapStampSet(live(), name, "all") },
        ], `${said} stamp options`));
        return wrap;
      }));
    }
    tags.title = labels.length ? "Labels: double-click to change them" : "";
  }
  if (words || labels.length || stamps.length) node.dataset.extras = "";
  else delete node.dataset.extras;
}

//: Labels as one comma-separated answer; an empty answer from a topic that
//: has some keeps them (Escape is never destructive), removing is its row.
async function wbMapEditLabels(node) {
  if (!node) return;
  const current = Array.isArray(node.data?.labels) ? node.data.labels : [];
  const answer = String((await promptDialog("Labels for this topic, separated by commas (up to eight).", current.join(", "),
    { confirmLabel: current.length ? "Change the labels" : "Add the labels" })) ?? "");
  const next = [...new Set(answer.split(",").map((l) => l.trim().slice(0, 30)).filter(Boolean))].slice(0, 8);
  if (!next.length || next.join(",") === current.join(",")) return;
  await wbMapSetExtra(node, { labels: next }, current.length ? "Labels changed." : "Labels added.");
}

//: Add, change or (with an empty answer from a filled one) keep a callout;
//: removing is its own menu row, `wbMapEditLink`'s rule for Escape.
async function wbMapEditCallout(node) {
  if (!node) return;
  const current = String(node.data?.callout || "");
  const next = String((await promptDialog("What should the callout over this topic say?", current,
    { confirmLabel: current ? "Change the callout" : "Add the callout" })) ?? "").trim().slice(0, 200);
  if (!next || next === current) return;
  await wbMapSetExtra(node, { callout: next }, current ? "Callout changed." : "Callout added.");
}

//: A callout, labels or stamps changed: the field and the tidy that makes
//: room for the taller card are one Undo step.
async function wbMapSetExtra(node, patch, said) {
  await wbRecordGesture(async () => {
    await wbMapSetNodeStyle(node, patch);
    renderWhiteboardNow();
    if (wbMapLaysOut()) await wbMapTidy({ quiet: true });
  });
  renderWhiteboardNow();
  if (said) wbAnnounce(said);
}

//: Remove this topic and keep its branch: the children move up to its parent
//: first, then the node goes. Through `/move`, which is the only endpoint
//: that runs the cycle check (`wbMapOutdent`'s own comment), and children
//: first so a failure leaves the branch attached to something rather than
//: orphaned under a node that no longer exists.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapRemoveKeepingBranch(...args) {
  return wbRecordGesture(wbMapRemoveKeepingBranchNow, args);
}

async function wbMapRemoveKeepingBranchNow(id) {
  const boardId = window.currentBoardId;
  const index = wbMapIndex();
  const node = index.byId.get(id);
  if (!boardId || !node) return;
  const children = index.childrenOf.get(id) || [];
  // The last-topic rule, at this door too: removing the only topic on the map
  // empties it, and §12.0 says a map is never empty.
  if (!children.length && wbMapDeleteEmptiesMap(id)) {
    wbMapRefuseLastTopic();
    return;
  }
  const parentId = index.byId.has(node.parent_id) ? node.parent_id : null;
  try {
    //: The whole branch in one request when there is more than one child: the
    //: half-moved branch a failure used to leave behind is the reason
    //: `move-many` exists. One child is still one `/move`, which says what it
    //: did in its own event rather than as a batch of one.
    if (children.length > 1) {
      const moved = await apiJson(`/whiteboard/boards/${boardId}/nodes/move-many`, {
        method: "PUT",
        body: JSON.stringify({
          moves: children.map((child) => ({ id: child.id, reparent: true, parent_id: parentId })),
        }),
      });
      for (const after of moved || []) Object.assign(index.byId.get(after.id) || {}, after);
    } else {
      for (const child of children) {
        const after = await apiJson(`/whiteboard/boards/${boardId}/nodes/${child.id}/move`, {
          method: "PUT",
          body: JSON.stringify({ parent_id: parentId }),
        });
        Object.assign(child, after);
      }
    }
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "move that branch up" }), true);
    return;
  }
  await wbMapDeleteSubtree(id);
  await wbMapTidyBranch(parentId);
}

//: Sever (§12.1 item 9): cut a topic free of its parent so it becomes a trunk
//: of its own, branch and all. `parent_id: null` is a move the endpoint
//: already supports; floating topics are allowed by §12.0 ("multiple roots
//: are allowed"), so this needs no new rule, only a way to ask for it.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapSever(...args) {
  return wbRecordGesture(wbMapSeverNow, args);
}

async function wbMapSeverNow(id) {
  const boardId = window.currentBoardId;
  const index = wbMapIndex();
  const node = index.byId.get(id);
  if (!boardId || !node) return;
  if (node.parent_id == null || !index.byId.has(node.parent_id)) {
    toast("This topic is already a trunk of its own.");
    return;
  }
  const oldParent = node.parent_id;
  try {
    const moved = await apiJson(`/whiteboard/boards/${boardId}/nodes/${id}/move`, {
      method: "PUT",
      body: JSON.stringify({ parent_id: null }),
    });
    Object.assign(node, moved);
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "cut that topic free" }), true);
    return;
  }
  // A severed topic keeps the colour it had as part of the branch it left,
  // which would be a lie about where it belongs: it is its own trunk now, so
  // it starts the palette again like every other trunk's children do.
  if (node.data?.color) await wbMapSetNodeStyle(node, { color: null });
  await wbMapTidyBranch(oldParent);
  renderWhiteboardNow();
  toastAction("Cut free as its own trunk.", "Put it back", () => wbUndo());
}

//: What the line into a topic says. Stored on the child, which is the end of
//: a tree edge that has exactly one of them (see the schema's own comment),
//: and drawn by `wbRenderMapEdges`.
async function wbMapLabelEdge(id) {
  const index = wbMapIndex();
  const node = index.byId.get(id);
  if (!node) return;
  if (!index.byId.has(node.parent_id)) {
    toast("A trunk has no line into it to label.");
    return;
  }
  const current = node.data?.edge_label || "";
  const answer = await promptDialog(
    "What does the line into this topic say?",
    current,
    { confirmLabel: current ? "Change the label" : "Add the label" }
  );
  //: **An empty answer changes nothing.** `promptDialog` resolves `""` for
  //: Escape, Cancel and an empty field alike, so "empty removes it" would
  //: make Escape destructive. Removing is its own row in the node menu
  //: ("Take the label off the line"), the way Unlink is for a link.
  const text = String(answer ?? "").trim();
  if (!text) return;
  await wbMapSetNodeStyle(node, { edge_label: text.slice(0, 80) });
  renderWhiteboardNow();
}

//: "Back to the branch" (§12.0: "'Reset to branch' on any node"). Drops every
//: key the strip and the radial can set, in one list rather than one button
//: per property, which is what makes it usable as the way out of a node you
//: have over-decorated.
async function wbMapResetToBranch(id) {
  const node = (wbState.objects || []).find((o) => o.id === id);
  if (!node) return;
  const patch = {};
  for (const key of WB_MAP_STYLE_KEYS) patch[key] = null;
  await wbMapSetNodeStyle(node, patch);
  renderWhiteboardNow();
  //: What it goes back to depends on whether the map says anything (§13e):
  //: on a themed map a reset topic follows the map, and a toast that said
  //: "the branch's own look" over a topic that just took the map's would be
  //: describing the wrong thing.
  //: Every topic has a level now (§14), so what it goes back to is that.
  toast(Object.keys(wbMapTheme()).length
    ? "Back to following this map and its level."
    : "Back to its level's look and its branch's colour.");
}

//: **What Copy style carries from a topic** (MINDMAP_PLAN.md decision 42):
//: how it is drawn, never what it is. Not the icon, the core mark, the link,
//: the line's label or its waypoint: a pasted look that renamed a topic's
//: icon or bent its line would be pasting content.
const WB_MAP_PASTE_STYLE_KEYS = [
  "color", "bold", "italic", "font_size", "align", "shape", "spine", "fill", "effect",
  "edge_style", "edge_dashed", "edge_width", "edge_arrow",
];

//: A topic's look as a patch: every key, `null` where it says nothing, so a
//: paste makes the target look the same rather than adding to what it had.
function wbMapTopicStyle(node) {
  const style = {};
  for (const key of WB_MAP_PASTE_STYLE_KEYS) {
    const value = node?.data?.[key];
    style[key] = value === undefined || value === "" ? null : value;
  }
  return style;
}

//: **"Use this look for its level"** (decision 41, Illustrator's Redefine
//: graphic style). The topic's own level fields go into its level's look and
//: off the topic, so it and every topic at that level that was never told
//: otherwise draw alike. One gesture (`WB_RECORDED`), so one Undo step.
async function wbMapUseLookForLevel(id) {
  const node = (wbState.objects || []).find((o) => o.id === id);
  const level = wbMapLevelOf(node);
  if (!node || level === undefined) return;
  const levels = JSON.parse(JSON.stringify(wbMapTheme().levels || {}));
  const look = { ...(levels[String(level)] || {}) };
  const patch = {};
  for (const field of WB_MAP_LEVEL_FIELDS) {
    let value = node.data?.[field];
    if (value === undefined || value === null || value === "") continue;
    //: A topic's fill words are not a level's: its tint is `self`, and a
    //: branch fill is a cascade, which is the branch's and not a level's.
    if (field === "fill") {
      if (value === "branch") continue;
      if (value === "self") value = "tint";
    }
    //: Size 0 is the pin for "the app's own size", which a level says by
    //: saying nothing.
    if (field === "font_size" && !value) {
      delete look.font_size;
    } else {
      look[field] = value;
    }
    patch[field] = null;
  }
  if (!Object.keys(patch).length) {
    toast("This topic has no look of its own to give its level.");
    return;
  }
  levels[String(level)] = look;
  await wbMapSetTheme({ levels });
  await wbMapSetNodeStyle(node, patch);
  renderWhiteboardNow();
  toast(`Every one of ${WB_MAP_LEVEL_NAMES[level]} that was never given its own look now looks like this.`);
}

//: --- the link radial (MINDMAP_PLAN.md §12.1 item 4) -------------------------
//:
//: The same ring, on the line rather than on the topic. Every slot writes to
//: the **child**, because a tree edge has no row of its own: it is
//: `parent_id`, and the child is the end of it with exactly one incoming line.
//:
//: **Coggle's plain left-click on a line opens the colour wheel alone, and
//: that is deliberately not copied.** A left-click on this canvas is how you
//: clear a selection, and a tree edge is a 2px line inside a 16px target: a
//: near-miss would open a colour picker you did not ask for, on a branch you
//: were only trying to click past. The ring is the same gesture as the node's
//: (right-click, or hold on a touch screen), which is one gesture to learn
//: rather than two, and the colour well is a slot inside it.
let wbMapLinkRadialFor = null;
//: **The same ring, on the map's other kind of connection** (MINDMAP_PLAN
//: §13c). A map has two: the branch, which is the child's own `parent_id` and
//: is therefore stored on the child, and the cross-link, which is a link
//: sketch naming both ends. §13.2 measured what that cost a person: a
//: right-click on a branch opened this ring, a right-click on a cross-link
//: opened the *board's* flat menu and its context bar, so the same gesture on
//: two lines that sit beside each other gave two different surfaces with two
//: different vocabularies. One ring, told which kind it is on, is the fix
//: §13's decision 2 asked for: "the data keeps two kinds of connection; the
//: controls stop having two."
let wbMapLinkRadialCross = null;

function wbCloseMapLinkRadial() {
  const ring = document.getElementById("wb-map-link-radial");
  if (!ring || ring.classList.contains("hidden")) return;
  if (ring.contains(document.activeElement)) document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
  ring.classList.add("hidden");
  wbMapLinkRadialFor = null;
  wbMapLinkRadialCross = null;
}

//: A cross-link, read from a sketch row: its parsed data plus both topics,
//: or null for a sketch that is not one (an ordinary board connector, a link
//: to a card, a line whose ends are gone). One reader, because every slot
//: below and the renderer's own dashed class all have to agree about what
//: counts as a cross-link.
function wbMapCrossLinkInfo(sketchId) {
  if (!wbIsMap()) return null;
  const sketch = (wbState.sketches || []).find((x) => x.id === sketchId);
  if (!sketch) return null;
  let data = null;
  try {
    data = JSON.parse(sketch.data);
  } catch {
    return null;
  }
  if (!data || !String(data.type || "").startsWith("link-")) return null;
  const index = wbMapIndex();
  const source = index.byId.get(data.sourceId);
  const target = index.byId.get(data.targetId);
  if (!source || !target) return null;
  return { sketch, data, source, target, index };
}

//: A waypoint handle shown or hidden, with the line's `<g>` that shows its ends.
function wbMapEdgeShown(handle, on) {
  handle.classList.toggle("is-shown", on);
  handle.parentNode.classList.toggle("is-shown", on);
}

//: **Which lines show their waypoint handle without being pointed at.**
//:
//: Two routes, and the second is not a luxury. Hover (the `<g>` wrapper, in
//: the stylesheet) is the one that always works, because it needs nothing
//: selected and so never has the map strip over it. This one is the other
//: half: the lines of the topic you have selected show their handles while it
//: is selected, which is the route a keyboard selection reaches and the one
//: that says the control exists at all. A cheap attribute toggle over elements
//: the render already built, so it can run on every selection change rather
//: than forcing a re-render.
//: **Only the handles that change are touched** (FEAT-02's 100ms gate): this
//: walked every handle on the map twice per add and toggled each one (12ms
//: at 301 topics). The handles shown are the selected topic's own lines, so
//: the ones to show are found by their ends, and the ones to hide are the
//: ones showing now.
function wbSyncMapEdgeHandles() {
  const group = document.querySelector("#wb-zoom-group .wb-map-edges");
  if (!group) return;
  const selected = wbIsMap() && wbMultiSelection.size <= 1 ? wbSelectedMapNode() : null;
  const id = selected ? String(selected.id) : null;
  const want = new Set();
  const cache = group._wbMapEdges;
  if (id && cache instanceof Map) {
    for (const [key, held] of cache) {
      const cut = key.indexOf(":");
      if (key.slice(0, cut) !== id && key.slice(cut + 1) !== id) continue;
      const handle = held.wrap.querySelector(".wb-map-edge-handle");
      if (handle) want.add(handle);
    }
  }
  //: The line's own `<g>` carries the class too: the two end grips are shown by
  //: it, where a `:has()` on the handle made every class write on the board
  //: re-match two hundred lines (OPEN 813).
  for (const handle of group.querySelectorAll(".wb-map-edge-handle.is-shown")) {
    if (!want.has(handle)) wbMapEdgeShown(handle, false);
  }
  for (const handle of want) if (!handle.classList.contains("is-shown")) wbMapEdgeShown(handle, true);
  //: **The selected topic's lines are drawn last** (K31): SVG takes the
  //: pointer in paint order, and a sibling line sharing a leg (an elbow's
  //: trunk, a stack of topics under one another) lay over this line's end
  //: grips, so they could be seen and not pressed. Moved only when not
  //: already at the end; the next render puts the tree order back first.
  const wraps = new Set([...want].map((handle) => handle.parentNode).filter(Boolean));
  let at = group.lastElementChild;
  let last = 0;
  while (at && wraps.has(at)) {
    last += 1;
    at = at.previousElementSibling;
  }
  if (last < wraps.size) for (const wrap of wraps) group.appendChild(wrap);
  //: **The selected topic's own lines lend their middle to its grips**
  //: (MINDMAP_PLAN 15, row 3): their mid-line `+` sat under the add row and
  //: the waypoint handle (`deepen72a.js`, 4 overlaps at 1440, 8 at 390), so a
  //: press there was a guess between three controls. Hover still finds it
  //: on every other line.
  const layer = document.querySelector("#wb-html-layer .wb-map-plus-layer");
  if (!layer) return;
  const aside = new Set(id ? layer.querySelectorAll(`.wb-map-edge-plus[data-parent="${id}"], .wb-map-edge-plus[data-child="${id}"]`) : []);
  for (const plus of layer.querySelectorAll(".wb-map-edge-plus.is-aside")) {
    if (!aside.has(plus)) plus.classList.remove("is-aside");
  }
  for (const plus of aside) plus.classList.add("is-aside");
}

// whiteboard-map-waypoints.js: whiteboard-map-waypoints.js: map line waypoints, cross-link handles and their me (moved out, L286).
//: Turn a cross-link around. The row's two ends swap, which is the whole of
//: it: a cross-link is not stored on either topic, so nothing in the tree
//: moves and nothing has to be tidied. The anchors swap with them, or a line
//: turned around would leave from the edge its far end used to arrive at.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapReverseCrossLink(...args) {
  return wbRecordGesture(wbMapReverseCrossLinkNow, args);
}

async function wbMapReverseCrossLinkNow(sketchId) {
  const info = wbMapCrossLinkInfo(sketchId);
  if (!info) return;
  const data = {
    ...info.data,
    sourceId: info.data.targetId,
    targetId: info.data.sourceId,
    sourceKind: info.data.targetKind,
    targetKind: info.data.sourceKind,
    sourceAnchor: info.data.targetAnchor,
    targetAnchor: info.data.sourceAnchor,
  };
  const sketch = info.sketch;
  try {
    //: The whole row, not the one field: `PUT /sketches/{id}` takes a
    //: `WhiteboardSketchBase`, so a body of `{data}` alone is a 422 rather
    //: than a partial update.
    const saved = await apiJson(`/whiteboard/sketches/${sketchId}`, {
      method: "PUT",
      body: JSON.stringify({
        data: JSON.stringify(data), board_id: sketch.board_id,
        x: sketch.x, y: sketch.y, z: sketch.z, group_id: sketch.group_id ?? null,
      }),
    });
    Object.assign(info.sketch, saved);
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "turn that cross-link around" }), true);
    return;
  }
  renderWhiteboardNow();
  toast("Turned the cross-link around.");
}

//: **A cross-link promoted to a branch** (§13c). The one action that teaches
//: the difference between the map's two kinds of connection by undoing a
//: choice the gesture made for you: `wbMapJoinByLink` decides between the two
//: from whether the far end is already in the tree, which is invisible, so
//: this is the way back for the case it guessed wrong. The far end moves
//: under the near one, its own branch comes with it, and the cross-link row
//: goes: keeping it would draw a dashed line over the branch it just became.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapCrossLinkToBranch(...args) {
  return wbRecordGesture(wbMapCrossLinkToBranchNow, args);
}

async function wbMapCrossLinkToBranchNow(sketchId) {
  const info = wbMapCrossLinkInfo(sketchId);
  if (!info) return;
  const { source, target, index } = info;
  const descendants = new Set(wbMapSubtree(index, target.id).map((o) => o.id));
  if (descendants.has(source.id)) {
    toast(`"${wbMapLabel(source)}" is already under "${wbMapLabel(target)}": turn the cross-link around first.`, "info");
    return;
  }
  if (!(await wbMapTransplant(target, source.id, false, { via: "link" }))) return;
  try {
    await apiJson(`/whiteboard/sketches/${sketchId}`, { method: "DELETE" });
    wbState.sketches = (wbState.sketches || []).filter((x) => x.id !== sketchId);
  } catch (err) {
    toast(err.message || "The branch was made, but the cross-link is still there.", true);
  }
  await wbRefreshMapState();
  renderWhiteboardNow();
}

//: Cut a cross-link: the row goes and neither topic is touched, which is the
//: difference between this and cutting a branch (that one re-parents).
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapCutCrossLink(...args) {
  return wbRecordGesture(wbMapCutCrossLinkNow, args);
}

async function wbMapCutCrossLinkNow(sketchId) {
  const info = wbMapCrossLinkInfo(sketchId);
  if (!info) return;
  try {
    await apiJson(`/whiteboard/sketches/${sketchId}`, { method: "DELETE" });
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "cut that cross-link" }), true);
    return;
  }
  wbState.sketches = (wbState.sketches || []).filter((x) => x.id !== sketchId);
  await wbRefreshMapState();
  renderWhiteboardNow();
  toast("Cut the cross-link. Both topics kept their branches.");
}

//: Turn a line around: the topic below becomes the one above.
//:
//: Two moves, in this order, and the order is the whole of it. Moving the
//: parent under the child while the child is still under the parent is
//: exactly the ring `/move`'s cycle check refuses, so the child is lifted to
//: the parent's own parent first: after that neither is a descendant of the
//: other and the second move is an ordinary re-parent.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapReverseEdge(...args) {
  return wbRecordGesture(wbMapReverseEdgeNow, args);
}

async function wbMapReverseEdgeNow(childId) {
  const boardId = window.currentBoardId;
  const index = wbMapIndex();
  const child = index.byId.get(childId);
  const parent = child ? index.byId.get(child.parent_id) : null;
  if (!boardId || !child || !parent) return;
  const grandparent = index.byId.has(parent.parent_id) ? parent.parent_id : null;
  const move = (id, parentId) => apiJson(
    `/whiteboard/boards/${boardId}/nodes/${id}/move`,
    { method: "PUT", body: JSON.stringify({ parent_id: parentId }) }
  );
  try {
    Object.assign(child, await move(child.id, grandparent));
    Object.assign(parent, await move(parent.id, child.id));
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "turn that line around" }), true);
    return;
  }
  await wbMapTidy({ quiet: true });
  renderWhiteboardNow();
  toast("Turned the line around.");
}

function wbSyncMapChrome() {
  wbApplyMapFont();
  //: A note open on the board being left goes with it (decision 18).
  if (wbMapNoteState && !document.querySelector(`.wb-object[data-id="${wbMapNoteState.id}"]`)) wbMapCloseNote();
  //: The map's line style can change here, and the cross-link tool draws it.
  if (wbIsMap()) wbSyncConnectWords(true);
  const isMap = wbIsMap();
  wbSyncToolSurfaces(isMap);
  wbSyncMapToolState();
  // A map that grows downward puts the branch spine on the node's top edge and
  // its chevron underneath: decided once here as a class on the view rather
  // than per node, since it is a property of the layout, not of any one node.
  document.getElementById("library-view-whiteboard")
    ?.classList.toggle("wb-map-down", isMap && wbMapLayout() === "tree-down");
  //: The switch says what it will do, not what the board is: a button whose
  //: label is the current state reads as a toggle that is already on, and this
  //: one changes the board rather than reporting it.
  const kind = document.getElementById("wb-board-kind-label");
  if (kind) kind.textContent = isMap ? "Turn into a whiteboard" : "Turn into a mind map";
  //: **The board menus a map has no use for** (MINDMAP_PLAN §12.5, INBOX 200:
  //: "what controls and tools are available and where"). The dock already
  //: hides thirteen board-only tools on a map (`wbSyncToolSurfaces`); the top
  //: bar was still offering the same things again as menus. Insert places a
  //: sticky, a text box, a shape or a bare note card, none of which a tree can
  //: hold (everything on a map is a node with a parent, which is what the map
  //: strip's own "Add from the library" makes). Arrange aligns, distributes
  //: and re-orders by hand, which is the layout's job on a map. Measured on a
  //: map of twelve topics before this: 60 controls reachable from the top bar,
  //: 21 of them board-only.
  //:
  //: Hidden, not disabled, for the reason the chip and the layout picker
  //: already are: a whole menu that can never apply here is not something to
  //: read past on every map.
  //:
  //: **Kept in the markup, and found through its button** (MINDMAP_PLAN
  //: decision 16). The two menus are not dead: the one top bar serves both
  //: kinds, and a board needs all 20 of their controls. And the wrap is
  //: found from the toggle, never from the menu, because an open menu that
  //: `escapeAndCapMenu` has moved to <body> is no longer inside its wrap:
  //: measured at 1280x520, Insert open on a board and a map opened without a
  //: click elsewhere (a view address, a keyboard path) left both toggles
  //: drawn on the map. The menu is closed and put home first, so the next
  //: board opens it from where it was built.
  for (const id of ["wb-insert-menu", "wb-arrange-menu"]) {
    const menu = document.getElementById(id);
    const toggle = document.querySelector(`.wb-topbar [aria-controls="${id}"]`);
    const wrap = toggle?.closest(".wb-board-menu-wrap");
    if (wrap) wrap.hidden = isMap;
    if (isMap && menu) {
      menu.classList.add("hidden");
      toggle?.setAttribute("aria-expanded", "false");
      restoreEscapedMenu(menu);
      menu.style.maxHeight = "";
    }
  }
  const chip = document.getElementById("wb-map-chip");
  const picker = document.getElementById("wb-map-layout");
  const tidy = document.getElementById("wb-map-tidy");
  if (chip) chip.hidden = !isMap;
  if (tidy) tidy.hidden = !isMap;
  if (picker) {
    picker.hidden = !isMap;
    picker.value = wbMapLayout();
  }
  wbSyncMapLinkStyle(isMap);
  //: Phase 5's own chrome. All of it is a *view* of the map, so it is synced
  //: from the same place the layout picker is rather than from wherever each
  //: happened to be changed: the failure this avoids is a control that reports
  //: a state the canvas disagrees with.
  const perspective = document.getElementById("wb-map-perspective");
  if (perspective) {
    perspective.value = wbMapPerspective();
    const row = perspective.closest(".wb-menu-row");
    if (row) row.hidden = !isMap;
  }
  const statsRow = document.getElementById("wb-map-stats-item");
  if (statsRow) statsRow.hidden = !isMap;
  const expandRow = document.getElementById("wb-map-expand-all");
  if (expandRow) expandRow.hidden = !isMap;
  const foldRow = document.getElementById("wb-map-fold-all");
  if (foldRow) foldRow.hidden = !isMap;
  const themeRow = document.getElementById("wb-map-theme-item");
  if (themeRow) themeRow.hidden = !isMap;
  //: The numbering switch (decision 17) says what the map does now.
  const numbered = document.getElementById("wb-map-numbered");
  if (numbered) {
    numbered.checked = Boolean(isMap && window.wbMapState?.numbered);
    const row = numbered.closest(".wb-menu-row");
    if (row) row.hidden = !isMap;
  }
  const dim = document.getElementById("wb-map-dim");
  if (dim) {
    dim.checked = Boolean(isMap && wbMapDim.on);
    const row = dim.closest(".wb-menu-row");
    if (row) row.hidden = !isMap;
  }
  //: The group itself as well as its rows: on a board it held nothing but
  //: its own heading, a group of zero rows drawn between two that have some.
  const mapSection = document.getElementById("wb-view-map-section");
  if (mapSection) mapSection.hidden = !isMap;
  if (!isMap && wbMapFocusState) wbMapFocusState = null;
  wbSyncMapViews();
}

//: Change the layout, then lay the map out in it. Changing a layout without
//: applying it would leave the picker saying "tree-down" over a map still
//: arranged sideways, which is a control that reports a state the screen
//: disagrees with: the shape of bug this app has been bitten by repeatedly.
//: One Undo step on the board's history (INBOX 898): the rows and the map's
//: settings are compared before and after, whatever the act wrote.
function wbMapSetLayout(...args) {
  return wbRecordGesture(wbMapSetLayoutNow, args);
}

//: **The map's line style, beside its layout** (K31). The theme's own
//: `edge_style`, which the theme dialog's Branch line, Shape already wrote:
//: the owner, in Free, could not find it. Shown as what the lines draw,
//: so a logic chart's elbow (`WB_MAP_LAYOUT_EDGE`) reads as Elbow; picking
//: that default stores nothing. One Undo step (`wbMapSetTheme`).
function wbSyncMapLinkStyle(isMap = wbIsMap()) {
  const select = document.getElementById("wb-map-link-style");
  if (!select) return;
  select.hidden = !isMap;
  if (isMap) select.value = wbMapTheme().edge_style || WB_MAP_LAYOUT_EDGE[wbMapLayout()] || "curve";
}

function wbMapSetLinkStyle(value) {
  const fallback = WB_MAP_LAYOUT_EDGE[wbMapLayout()] || "curve";
  return wbMapSetTheme({ edge_style: value === fallback ? null : value });
}

//: `quiet`: the caller has just said which layout it wants (a template), so
//: "Laid out 7 nodes" would only cover the map it drew (blind test 1031, 390px).
async function wbMapSetLayoutNow(layout, { quiet = false } = {}) {
  const boardId = window.currentBoardId;
  if (!boardId || !wbIsMap()) return;
  try {
    await apiJson(`/whiteboard/boards/${boardId}`, {
      method: "PUT",
      body: JSON.stringify({ layout }),
    });
    window.wbMapState = { ...window.wbMapState, layout };
    wbSyncMapChrome();
    const moved = await wbMapTidy({ quiet: true });
    renderWhiteboardNow();
    if (quiet) return;
    toast(layout === "free"
      ? "Layout set to Free, nodes stay where you put them."
      : `Laid out ${nounCount(moved, "node")}.`);
  } catch (err) {
    toast(err.message || voiceLine("failed", { what: "change the layout" }), true);
  }
}

//: A branch's own structure, by the words its menu uses (XMind's list).
const WB_MAP_BRANCH_STRUCTURES = Object.freeze([
  ["logic-right", "Logic chart"], ["tree-down", "Org chart"], ["tree-table", "Tree table"], ["timeline", "Timeline"],
  ["fishbone", "Fishbone"], ["tree-both", "Map, both sides"], ["tree-right", "Tree, to the right"],
  ["tree-left", "Tree, to the left"], ["radial", "Radial"],
]);

//: Give a branch its own structure, or `null` to follow the map again: the
//: field and the tidy it causes are one Undo step.
async function wbMapSetBranchLayout(node, value) {
  if (!node) return;
  await wbRecordGesture(async () => {
    await wbMapSetNodeStyle(node, { branch_layout: value });
    await wbMapTidy({ quiet: true });
  });
  renderWhiteboardNow();
  const name = WB_MAP_BRANCH_STRUCTURES.find(([v]) => v === value)?.[1];
  wbAnnounce(name ? `This branch is laid out as ${name.toLowerCase()}.` : "This branch follows the map's layout again.");
}

//: **Dragging a node pins it.** The other half of the tidy bargain above: a
//: position you chose by hand is a decision, and the next Tidy has to leave it
//: alone or the gesture is pointless. Called from the object drag's own end
//: handler, and only for a real move on a map, a click that happened to
//: register as a zero-length drag must not silently pin anything.
async function wbMapPinOnDrag(d) {
  if (!wbIsMap() || !WB_MAP_KINDS.has(d.kind) || d.data?.pinned) return;
  d.data = { ...d.data, pinned: true };
  await wbSaveObject(d);
  wbScheduleRender();
}

//: --- Boundaries and summaries (MINDMAP_PLAN.md decisions 19 and 20) --------
//:
//: Both are drawn from where the topics are, on every render and every drag
//: frame (the selection bar's frame), so they grow, fold and move with the
//: branch and there is nothing stored about where they sit. A boundary goes
//: under the lines, a summary's brace and words over them; both in the
//: branch's colour, so the branch colour well is their colour control.

const WB_MAP_BOUNDARY_PAD = 12;
const WB_MAP_BRACE_GAP = 10;
const WB_MAP_BRACE_W = 14;

//: The box round a topic and every topic under it that is showing.
function wbMapBranchBox(index, hidden, id) {
  let box = null;
  for (const node of wbMapSubtree(index, id)) {
    if (hidden.has(node.id)) continue;
    const size = wbMapNodeSize(node);
    const r = { minX: node.x, minY: node.y, maxX: node.x + size.w, maxY: node.y + size.h };
    box = box
      ? { minX: Math.min(box.minX, r.minX), minY: Math.min(box.minY, r.minY), maxX: Math.max(box.maxX, r.maxX), maxY: Math.max(box.maxY, r.maxY) }
      : r;
  }
  return box;
}

//: The siblings a summary on `node` covers: it and the ones after it.
function wbMapSummaryRun(index, node) {
  const span = Math.max(1, Math.round(Number(node.data?.summary_span) || 1));
  const siblings = wbMapSiblingsOf(index, node);
  const at = siblings.findIndex((s) => s.id === node.id);
  return at < 0 ? [node] : siblings.slice(at, at + span);
}

//: A cloud: the box's four sides as runs of outward bumps, drawn clockwise
//: so every arc's sweep puts its bulge outside.
function wbMapCloudD(x, y, w, h) {
  const bump = 26;
  const nx = Math.max(2, Math.round(w / bump));
  const ny = Math.max(2, Math.round(h / bump));
  const sx = w / nx;
  const sy = h / ny;
  const across = `a${sx / 2} ${Math.min(sx / 2, 9)} 0 0 1`;
  const down = `a${Math.min(sy / 2, 9)} ${sy / 2} 0 0 1`;
  let d = `M${x} ${y}`;
  for (let i = 0; i < nx; i += 1) d += ` ${across} ${sx} 0`;
  for (let i = 0; i < ny; i += 1) d += ` ${down} 0 ${sy}`;
  for (let i = 0; i < nx; i += 1) d += ` ${across} ${-sx} 0`;
  for (let i = 0; i < ny; i += 1) d += ` ${down} 0 ${-sy}`;
  return `${d} Z`;
}

//: A brace along one side of `box`, its tip pointing away from the parent.
//: Worked out along the side (`a`) and outwards from it (`o`), then turned
//: onto the side, so all four sides are one drawing.
function wbMapBraceGeometry(side, box) {
  const horizontal = side === "left" || side === "right";
  const a1 = horizontal ? box.minY : box.minX;
  const a2 = horizontal ? box.maxY : box.maxX;
  const am = (a1 + a2) / 2;
  const base = side === "right" ? box.maxX + WB_MAP_BRACE_GAP
    : side === "left" ? box.minX - WB_MAP_BRACE_GAP
    : side === "bottom" ? box.maxY + WB_MAP_BRACE_GAP
    : box.minY - WB_MAP_BRACE_GAP;
  const sign = side === "right" || side === "bottom" ? 1 : -1;
  const at = (a, o) => (horizontal ? `${base + sign * o} ${a}` : `${a} ${base + sign * o}`);
  const r = Math.min(10, (a2 - a1) / 4);
  const h = WB_MAP_BRACE_W / 2;
  const d = [
    `M${at(a1, 0)}`, `Q${at(a1, h)} ${at(a1 + r, h)}`, `L${at(am - r, h)}`,
    `Q${at(am, h)} ${at(am, WB_MAP_BRACE_W)}`, `Q${at(am, h)} ${at(am + r, h)}`,
    `L${at(a2 - r, h)}`, `Q${at(a2, h)} ${at(a2, 0)}`,
  ].join(" ");
  const out = WB_MAP_BRACE_W + 8;
  const tip = horizontal ? { x: base + sign * out, y: am } : { x: am, y: base + sign * (out + (sign > 0 ? 8 : 0)) };
  const anchor = side === "right" ? "start" : side === "left" ? "end" : "middle";
  return { d, tip, anchor };
}

function wbMapStructureGroup(zoomGroup, cls, before) {
  let group = zoomGroup.querySelector(`:scope > .${cls}`);
  if (!group) {
    group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", cls);
    group.setAttribute("aria-hidden", "true");
    zoomGroup.insertBefore(group, before);
  }
  return group;
}

function wbMapStructureText(cls, x, y, anchor, words, colour) {
  const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
  text.setAttribute("class", cls);
  text.setAttribute("x", String(x));
  text.setAttribute("y", String(y));
  text.setAttribute("text-anchor", anchor);
  text.setAttribute("dominant-baseline", "middle");
  text.textContent = words;
  if (colour) text.style.setProperty("--wb-boundary", colour);
  return text;
}

function wbRenderMapStructure() {
  const zoomGroup = document.getElementById("wb-zoom-group");
  if (!zoomGroup) return;
  const marked = wbIsMap() && (wbState.objects || []).some((o) => o.data?.boundary || o.data?.summary);
  if (!marked) {
    zoomGroup.querySelector(":scope > .wb-map-boundaries")?.remove();
    zoomGroup.querySelector(":scope > .wb-map-summaries")?.remove();
    return;
  }
  const NS = "http://www.w3.org/2000/svg";
  const boundaries = wbMapStructureGroup(zoomGroup, "wb-map-boundaries", zoomGroup.firstChild);
  const edges = zoomGroup.querySelector(":scope > .wb-map-edges");
  const summaries = wbMapStructureGroup(zoomGroup, "wb-map-summaries", edges ? edges.nextSibling : boundaries.nextSibling);
  //: Under the lines, always: a render can put the edge group first again.
  if (zoomGroup.firstChild !== boundaries) zoomGroup.insertBefore(boundaries, zoomGroup.firstChild);
  const index = wbMapIndex();
  const hidden = wbMapConcealed(index);
  const colors = wbMapNodeColors(index);
  const tint = (id) => colors.get(id) || "var(--accent)";
  const shapes = [];
  const marks = [];
  for (const node of index.nodes) {
    if (hidden.has(node.id)) continue;
    const style = node.data?.boundary;
    if (style) {
      //: A lasso'd set (`boundary_set`) is the union of those topics; else the branch.
      const box = Array.isArray(node.data?.boundary_set) ? wbMapLazy.setBox(index, hidden, node.data.boundary_set) : wbMapBranchBox(index, hidden, node.id);
      if (box) {
        const x = box.minX - WB_MAP_BOUNDARY_PAD;
        const y = box.minY - WB_MAP_BOUNDARY_PAD;
        const w = box.maxX - box.minX + WB_MAP_BOUNDARY_PAD * 2;
        const h = box.maxY - box.minY + WB_MAP_BOUNDARY_PAD * 2;
        const path = document.createElementNS(NS, "path");
        path.setAttribute("class", `wb-map-boundary wb-map-boundary-${style}`);
        path.setAttribute("data-topic", String(node.id));
        path.setAttribute("d", style === "cloud" ? wbMapCloudD(x, y, w, h)
          : `M${x + 16} ${y} H${x + w - 16} Q${x + w} ${y} ${x + w} ${y + 16} V${y + h - 16} Q${x + w} ${y + h} ${x + w - 16} ${y + h} H${x + 16} Q${x} ${y + h} ${x} ${y + h - 16} V${y + 16} Q${x} ${y} ${x + 16} ${y} Z`);
        path.style.setProperty("--wb-boundary", tint(node.id));
        shapes.push(path);
        const label = String(node.data?.boundary_label || "").trim();
        if (label) shapes.push(wbMapStructureText("wb-map-boundary-label", x + 6, y - (style === "cloud" ? 16 : 10), "start", label, null));
      }
    }
    const words = String(node.data?.summary || "").trim();
    const parent = node.parent_id != null ? index.byId.get(node.parent_id) : null;
    if (words && parent) {
      const run = wbMapSummaryRun(index, node).filter((s) => !hidden.has(s.id));
      let box = null;
      let own = null;
      for (const topic of run) {
        const b = wbMapBranchBox(index, hidden, topic.id);
        const size = wbMapNodeSize(topic);
        const o = { minX: topic.x, minY: topic.y, maxX: topic.x + size.w, maxY: topic.y + size.h };
        box = !b ? box : box ? { minX: Math.min(box.minX, b.minX), minY: Math.min(box.minY, b.minY), maxX: Math.max(box.maxX, b.maxX), maxY: Math.max(box.maxY, b.maxY) } : b;
        own = own ? { minX: Math.min(own.minX, o.minX), minY: Math.min(own.minY, o.minY), maxX: Math.max(own.maxX, o.maxX), maxY: Math.max(own.maxY, o.maxY) } : o;
      }
      if (box && own) {
        const ps = wbMapNodeSize(parent);
        const dx = (own.minX + own.maxX) / 2 - (parent.x + ps.w / 2);
        const dy = (own.minY + own.maxY) / 2 - (parent.y + ps.h / 2);
        const side = Math.abs(dx) >= Math.abs(dy) ? (dx >= 0 ? "right" : "left") : dy >= 0 ? "bottom" : "top";
        const geom = wbMapBraceGeometry(side, box);
        const brace = document.createElementNS(NS, "path");
        brace.setAttribute("class", "wb-map-summary-brace");
        brace.setAttribute("data-topic", String(node.id));
        brace.setAttribute("d", geom.d);
        brace.style.setProperty("--wb-boundary", tint(node.id));
        marks.push(brace, wbMapStructureText("wb-map-summary-label", geom.tip.x, geom.tip.y, geom.anchor, words, null));
      }
    }
  }
  boundaries.replaceChildren(...shapes);
  summaries.replaceChildren(...marks);
}

//: Sets a boundary's or a summary's fields through the topic's one undo step.
async function wbMapSetStructure(node, patch, said = "") {
  await wbMapSetNodeStyle(node, patch);
  renderWhiteboardNow();
  if (said) wbAnnounce(said);
}

//: A boundary's label or a summary's words, asked for in the app's prompt.
//: An empty answer changes nothing (Escape is never destructive; removing is
//: its own row, `wbMapEditLink`'s rule).
async function wbMapAskStructureWords(node, field, question, confirmLabel, extra = {}) {
  const current = String(node.data?.[field] || "");
  const next = String((await promptDialog(question, current, { confirmLabel })) ?? "").trim().slice(0, 80);
  if (!next || (next === current && Object.keys(extra).every((k) => node.data?.[k] === extra[k]))) return false;
  await wbMapSetStructure(node, { [field]: next, ...extra });
  return true;
}

//: A summary over the given topics: the run from the first of them to the
//: last, in sibling order, kept on the first. Siblings only.
async function wbMapSummarise(nodes) {
  const index = wbMapIndex();
  const first = nodes[0];
  if (!first || first.parent_id == null) return;
  const siblings = wbMapSiblingsOf(index, first);
  const places = nodes.map((n) => siblings.findIndex((s) => s.id === n.id));
  if (places.some((at) => at < 0)) {
    toast("A summary covers topics side by side under one parent.", "info");
    return;
  }
  const from = Math.min(...places);
  const to = Math.max(...places);
  const head = siblings[from];
  const made = await wbMapAskStructureWords(head, "summary", "What do these topics come to? A few words beside them.",
    head.data?.summary ? "Change the summary" : "Add the summary", { summary_span: to - from + 1 });
  if (made) wbAnnounce("Summary added.");
}

//: **A map presents by branch** (decision 21): the whole map first, then each
//: trunk's branches in sibling order, each fitted with what of it is showing
//: (a folded branch is its topic). A trunk with nothing under it is a step of
//: its own. The board's bar, keys and Escape (`wbStartPresenting`).
function wbMapPresentSteps() {
  const index = wbMapIndex();
  if (!index.nodes.length) return [];
  const pad = 24;
  const branch = (id) => () => {
    const now = wbMapIndex();
    if (!now.byId.has(id)) return null;
    const b = wbMapBranchBox(now, wbMapConcealed(now), id);
    return b ? { x: b.minX - pad, y: b.minY - pad, w: b.maxX - b.minX + pad * 2, h: b.maxY - b.minY + pad * 2 } : null;
  };
  const named = (id) => () => wbMapLabel(wbMapIndex().byId.get(id) || {}) || "Topic";
  const steps = [{
    title: () => (index.roots.length === 1 ? named(index.roots[0].id)() : "The whole map"),
    box: () => {
      const b = wbContentBounds();
      return b && Number.isFinite(b.minX) ? { x: b.minX - pad, y: b.minY - pad, w: b.maxX - b.minX + pad * 2, h: b.maxY - b.minY + pad * 2 } : null;
    },
  }];
  const hidden = wbMapConcealed(index);
  for (const root of index.roots) {
    if (hidden.has(root.id)) continue;
    const kids = (index.childrenOf.get(root.id) || []).filter((k) => !hidden.has(k.id));
    for (const node of kids.length ? kids : index.roots.length > 1 ? [root] : []) {
      steps.push({ title: named(node.id), box: branch(node.id) });
    }
  }
  return steps;
}

// --- Build up branch by branch (INBOX 1774, MINDMAP_PLAN 2026-11-11) -------
//
//: **Presenting a map from the centre out**, a branch and a level at a time:
//: the central topic(s) alone, then for each branch in the order Present
//: branches walks, the branch topic, then its next level, to its last visible
//: level, then the whole map. A folded branch stays out, so folding first
//: trims the talk. What step i shows is everything revealed in steps 0 to i,
//: worked out from the map, so Home, End, a typed page and the page picker
//: all land right, and Previous hides exactly one step's part. Hidden is a
//: view like Study's (decision 36): nothing is folded, saved or put on the
//: Undo list, so the map is as it was after Escape and a shared map works.
//: Outer to inner is the same steps backwards (End, then Previous).
//: `plan`, `hiddenAt`, `ring`, `depths` and `levels` are pure, so the whole
//: object is the marked region, run in node by
//: `tests/test_map_build_up_1774.py` (the other methods read the board only
//: when called). `run` is the plan being presented.
// WB-MAP-BUILD-BEGIN
const wbMapBuild = {
  on: false,
  hidden: new Set(),
  steps: [],
  run: [],
  //: `folded` is what `wbMapHidden` answers: topics under a folded one.
  plan(index, folded) {
    const out = [];
    const seen = new Set();
    const roots = index.roots.filter((r) => !folded.has(r.id));
    for (const r of roots) seen.add(r.id);
    out.push({ kind: "centre", id: null, root: null, level: 0, reveal: roots.map((r) => r.id) });
    for (const root of roots) {
      for (const branch of index.childrenOf.get(root.id) || []) {
        if (folded.has(branch.id) || seen.has(branch.id)) continue;
        let ring = [branch];
        for (let level = 1; ring.length; level += 1) {
          ring = ring.filter((n) => !seen.has(n.id));
          if (!ring.length) break;
          for (const n of ring) seen.add(n.id);
          out.push({ kind: "branch", id: branch.id, root: root.id, level, reveal: ring.map((n) => n.id) });
          ring = ring.flatMap((n) => (index.childrenOf.get(n.id) || []).filter((k) => !folded.has(k.id)));
        }
      }
    }
    //: Anything the walk did not reach still ends on a whole map.
    const left = index.nodes.filter((n) => !folded.has(n.id) && !seen.has(n.id)).map((n) => n.id);
    out.push({ kind: "whole", id: null, root: null, level: 0, reveal: left });
    return out;
  },
  //: Everything shown at step `at` is the union of steps 0 to `at`; this is
  //: what is not.
  hiddenAt(plan, at) {
    const hidden = new Set(plan.flatMap((s) => s.reveal));
    for (const s of plan.slice(0, at + 1)) for (const id of s.reveal) hidden.delete(id);
    return hidden;
  },
  //: The ring one more or one less level changes: every visible folded
  //: topic at the shallowest depth (`fold` false), or every visible open
  //: topic with a branch at the deepest (`fold` true). A trunk is depth 1.
  ring(index, folded, dir) {
    const depth = wbMapBuild.depths(index);
    const want = dir < 0;
    let best = null;
    let ids = [];
    for (const node of index.nodes) {
      if (folded.has(node.id) || !(index.childrenOf.get(node.id) || []).length) continue;
      if (Boolean(node.data?.collapsed) === want) continue;
      const d = depth.get(node.id);
      if (d === undefined) continue;
      if (best === null || (want ? d > best : d < best)) {
        best = d;
        ids = [];
      }
      if (d === best) ids.push(node.id);
    }
    return { ids, fold: want };
  },
  depths(index) {
    const depth = new Map();
    const queue = index.roots.map((r) => [r, 1]);
    while (queue.length) {
      const [node, d] = queue.shift();
      if (depth.has(node.id)) continue;
      depth.set(node.id, d);
      for (const kid of index.childrenOf.get(node.id) || []) queue.push([kid, d + 1]);
    }
    return depth;
  },
  //: How many levels are showing now.
  levels(index, folded) {
    let most = 0;
    for (const [id, d] of wbMapBuild.depths(index)) if (!folded.has(id)) most = Math.max(most, d);
    return most;
  },
  //: The box a step fits: the trunk's topic plus what of the branch is showing.
  box(at) {
    const step = wbMapBuild.run[at];
    const now = wbMapIndex();
    const pad = 24;
    let ids;
    if (step.kind === "branch") {
      const shown = new Set(wbMapBuild.run.slice(0, at + 1).flatMap((s) => s.reveal));
      ids = [step.root, ...wbMapSubtree(now, step.id).map((n) => n.id).filter((id) => shown.has(id))];
    } else if (step.kind === "centre") {
      ids = step.reveal;
    } else {
      const b = wbContentBounds();
      return b && Number.isFinite(b.minX) ? { x: b.minX - pad, y: b.minY - pad, w: b.maxX - b.minX + pad * 2, h: b.maxY - b.minY + pad * 2 } : null;
    }
    let box = null;
    for (const id of ids) {
      const node = now.byId.get(id);
      if (!node) continue;
      const size = wbMapNodeSize(node);
      const r = { minX: node.x, minY: node.y, maxX: node.x + size.w, maxY: node.y + size.h };
      box = box ? { minX: Math.min(box.minX, r.minX), minY: Math.min(box.minY, r.minY), maxX: Math.max(box.maxX, r.maxX), maxY: Math.max(box.maxY, r.maxY) } : r;
    }
    return box ? { x: box.minX - pad, y: box.minY - pad, w: box.maxX - box.minX + pad * 2, h: box.maxY - box.minY + pad * 2 } : null;
  },
  title(at) {
    const step = wbMapBuild.run[at];
    const name = (id) => wbMapLabel(wbMapIndex().byId.get(id) || {}) || "Topic";
    if (step.kind === "centre") {
      const roots = wbMapIndex().roots;
      return roots.length === 1 ? name(roots[0].id) : "The central topics";
    }
    if (step.kind === "whole") return "The whole map";
    return step.level === 1 ? name(step.id) : `${name(step.id)}, level ${step.level}`;
  },
  start() {
    //: One presentation at a time: a second start would take the camera it already holds.
    if (wbPresent) return;
    const index = wbMapIndex();
    const plan = wbMapBuild.plan(index, wbMapHidden(index));
    if (!plan.some((s) => s.kind === "branch")) {
      toast("Nothing to build up yet: add a branch first.");
      return;
    }
    wbMapBuild.run = plan;
    wbMapBuild.steps = plan.map((s, i) => ({
      title: () => wbMapBuild.title(i),
      box: () => wbMapBuild.box(i),
      reveal: s.reveal,
      enter: () => wbMapBuild.enter(i),
    }));
    wbMapBuild.on = true;
    wbMapBuild.hidden = wbMapBuild.hiddenAt(plan, 0);
    renderWhiteboardNow();
    wbStartPresenting();
    //: The shell could not open (no board to present on): put the map back whole.
    if (!wbPresent) wbMapBuild.end();
  },
  //: The shell calls this as step `at` is shown: set what is hidden from the
  //: step alone, so any jump lands right, and ring what just appeared.
  enter(at) {
    if (!wbMapBuild.on || !wbMapBuild.run[at]) return;
    wbMapBuild.hidden = wbMapBuild.hiddenAt(wbMapBuild.run, at);
    renderWhiteboardNow();
    wbMapBuild.unring();
    if (wbMapBuild.run[at].kind === "whole") return;
    const stage = document.getElementById("whiteboard-container");
    for (const id of wbMapBuild.run[at].reveal) {
      stage?.querySelector(`.wb-object[data-id="${id}"]`)?.classList.add("flash-target", "flash");
    }
  },
  unring() {
    for (const el of document.querySelectorAll(".wb-object.flash-target")) el.classList.remove("flash-target", "flash");
  },
  //: Called by `wbStopPresenting`: the map draws whole again.
  end() {
    if (!wbMapBuild.on) return;
    wbMapBuild.on = false;
    wbMapBuild.hidden = new Set();
    wbMapBuild.steps = [];
    wbMapBuild.run = [];
    wbMapBuild.unring();
    renderWhiteboardNow();
  },
};
// WB-MAP-BUILD-END

// --- Study the map (MINDMAP_PLAN §12.3 item 5, decision 36) ----------------
//
//: **Presenting, with each branch's topics hidden until recalled.** The
//: questions are the trunks' branches that have topics under them, in the
//: order Present branches walks; each step shows the branch topic alone,
//: "Show" (or Enter) draws what is under it, and "Knew it" or "Not yet"
//: marks it and moves on. Hidden is a view, like focus: nothing is folded
//: or written. The marks are kept per map on this device (`wbStudy:<id>`),
//: and a branch missed last time says so in its step.
//: `revealed` holds the note questions whose answer has been shown.
const wbStudy = {
  on: false, hidden: new Set(), revealed: new Set(), steps: [], marks: {}, boardId: null,
  key() {
    return `wbStudy:${wbStudy.boardId}`;
  },
  //: Through the one door to saved settings (prefs.js), which already
  //: survives blocked storage and an unreadable value.
  load() {
    return prefs.json(wbStudy.key(), {}) || {};
  },
  save() {
    try {
      prefs.set(wbStudy.key(), JSON.stringify(wbStudy.marks));
    } catch {
      // storage blocked (a private window): the run still works, unremembered
    }
  },
};

// WB-MAP-STUDY-BEGIN
//: The questions: each trunk's children with a branch under them, in sibling
//: order (`childrenOf` is already sorted), and every topic under each one.
//: Pure, so `tests/test_map_study.py` runs it in node. With `marks` (the
//: map's record on this device) the order is spaced (decision 36): a branch
//: missed last time first, then those due for review (a streak of knowing it
//: waits 0, 1, 3, 7, 14 then 30 days, most overdue first), then any never
//: asked, in the map's order, then those not due yet, soonest first.
function wbMapStudyQuestions(index, marks = null, now = 0) {
  const out = [];
  const under = (id) => {
    const all = [];
    const stack = [...(index.childrenOf.get(id) || [])];
    const seen = new Set();
    while (stack.length) {
      const node = stack.pop();
      if (seen.has(node.id)) continue;
      seen.add(node.id);
      all.push(node.id);
      stack.push(...(index.childrenOf.get(node.id) || []));
    }
    return all;
  };
  for (const root of index.roots) {
    for (const branch of index.childrenOf.get(root.id) || []) {
      const hides = under(branch.id);
      if (hides.length) out.push({ id: branch.id, hides });
    }
  }
  //: **The note behind a topic as the answer** (the plan's open half of item
  //: 5): a topic with a note that is not already a branch question asks for
  //: its note, which "Show" reads out. Appended in map order after the
  //: branches, so the walk through the boxes does not jump back and forth.
  //: A topic under a branch question is out: it is hidden until that branch
  //: is shown, so it has no box to walk to.
  const asked = new Set(out.flatMap((q) => [q.id, ...q.hides]));
  const seen = new Set();
  const walk = (node) => {
    if (seen.has(node.id)) return;
    seen.add(node.id);
    const answer = String(node.data?.note || "").trim();
    if (answer && !asked.has(node.id)) out.push({ id: node.id, hides: [], answer });
    for (const child of index.childrenOf.get(node.id) || []) walk(child);
  };
  for (const root of index.roots) walk(root);
  if (!marks || !Object.keys(marks).length) return out;
  const rank = (q) => {
    const m = marks[q.id];
    if (!m) return [2, 0];
    if (m.last === "missed") return [0, m.at || 0];
    const over = now - (m.at || 0) - [0, 1, 3, 7, 14, 30][Math.min(m.streak || 1, 5)] * 86400000;
    return over >= 0 ? [1, -over] : [3, -over];
  };
  const keyed = out.map((q, i) => ({ q, i, r: rank(q) }));
  keyed.sort((a, b) => a.r[0] - b.r[0] || a.r[1] - b.r[1] || a.i - b.i);
  return keyed.map((k) => k.q);
}

//: What "Recalled 3 of 5" counts, and the line a step carries from last time.
function wbMapStudyTally(questions, marks) {
  const knew = questions.filter((q) => marks[q.id]?.last === "knew").length;
  const missed = new Set(questions.filter((q) => marks[q.id]?.last === "missed").map((q) => q.id));
  return { knew, of: questions.length, missed };
}
// WB-MAP-STUDY-END

//: The steps the presenting shell walks: one per question, fitted to what
//: is showing of the branch (the question alone, then the answer).
function wbMapStudySteps() {
  const pad = 24;
  return wbStudy.steps.map((q) => ({
    id: q.id,
    title: () => {
      const label = wbMapLabel(wbMapIndex().byId.get(q.id) || {}) || "Topic";
      const shown = wbMapStudyShown(q);
      const was = wbStudy.marks[q.id]?.last === "missed" ? " (not yet, last time)" : "";
      if (q.answer) return shown ? `${label}: ${q.answer.replace(/\s+/g, " ")}` : `What is the note on “${label}”?${was}`;
      return shown ? label : `What is under “${label}”?${was}`;
    },
    box: () => {
      const now = wbMapIndex();
      if (!now.byId.has(q.id)) return null;
      const b = wbMapBranchBox(now, wbMapConcealed(now), q.id);
      return b ? { x: b.minX - pad, y: b.minY - pad, w: b.maxX - b.minX + pad * 2, h: b.maxY - b.minY + pad * 2 } : null;
    },
  }));
}

//: Whether a question's answer is on screen: its branch drawn, or its note read.
function wbMapStudyShown(q) {
  return q.answer ? wbStudy.revealed.has(q.id) : !q.hides.some((id) => wbStudy.hidden.has(id));
}

//: `inOrder` asks in the map's order instead of the spaced one.
function wbMapStartStudy({ inOrder = false } = {}) {
  const marks = wbStudy.load();
  const questions = wbMapStudyQuestions(wbMapIndex(), inOrder ? null : marks, Date.now());
  if (!questions.length) {
    toast("Nothing to recall yet: a branch with topics under it, or a topic with a note, is a question.");
    return;
  }
  wbStudy.on = true;
  wbStudy.boardId = window.currentBoardId;
  wbStudy.steps = questions;
  wbStudy.hidden = new Set(questions.flatMap((q) => q.hides));
  wbStudy.revealed = new Set();
  wbStudy.marks = marks;
  renderWhiteboardNow();
  wbStartPresenting();
  wbMapStudySyncBar();
  //: After the shell's own focus on Next (a frame on), so Enter shows.
  wbMapCache.defer(() => document.getElementById("wb-study-show")?.focus({ preventScroll: true }), 2);
}

//: Show, then the two marks: the bar's study buttons follow the step.
function wbMapStudySyncBar() {
  const step = wbStudy.on && wbPresent ? wbStudy.steps[wbPresent.at] : null;
  const shown = step ? wbMapStudyShown(step) : false;
  document.getElementById("wb-study-show")?.classList.toggle("hidden", !step || shown);
  document.getElementById("wb-study-knew")?.classList.toggle("hidden", !step || !shown);
  document.getElementById("wb-study-missed")?.classList.toggle("hidden", !step || !shown);
}

function wbMapStudyShow() {
  const step = wbPresent && wbStudy.steps[wbPresent.at];
  if (!step) return;
  for (const id of step.hides) wbStudy.hidden.delete(id);
  if (step.answer) wbStudy.revealed.add(step.id);
  renderWhiteboardNow();
  wbPresentShow(wbPresent.at);
  wbMapStudySyncBar();
  document.getElementById("wb-study-knew")?.focus({ preventScroll: true });
}

function wbMapStudyMark(knew) {
  const step = wbPresent && wbStudy.steps[wbPresent.at];
  if (!step) return;
  const was = wbStudy.marks[step.id] || { knew: 0, missed: 0 };
  //: `streak` (times in a row it was known) and `at` (when) place it in the spaced order.
  wbStudy.marks[step.id] = { ...was, [knew ? "knew" : "missed"]: (was[knew ? "knew" : "missed"] || 0) + 1, last: knew ? "knew" : "missed", streak: knew ? (was.last === "knew" ? was.streak || 1 : 0) + 1 : 0, at: Date.now() };
  wbStudy.save();
  if (wbPresent.at < wbStudy.steps.length - 1) {
    wbPresentShow(wbPresent.at + 1);
    wbMapStudySyncBar();
    document.getElementById("wb-study-show")?.focus({ preventScroll: true });
    return;
  }
  const tally = wbMapStudyTally(wbStudy.steps, wbStudy.marks);
  wbStopPresenting();
  toast(`Recalled ${tally.knew} of ${tally.of} branches.`);
}

//: Called by `wbStopPresenting`: the map draws whole again.
function wbMapEndStudy() {
  if (!wbStudy.on) return;
  wbStudy.on = false;
  wbStudy.hidden = new Set();
  wbStudy.revealed = new Set();
  wbMapStudySyncBar();
  renderWhiteboardNow();
}

// --- The outline (MINDMAP_PLAN §12.2 item 8, the audit's M3) ---------------
//
//: **The map as an indented list, edited in place and kept in step both
//: ways** (decision 33). A panel beside the canvas (the board sidebar's
//: place and shell, `.whiteboard-sidebar`), one text field per topic in the
//: tree's own order (`wbMapIndex`, siblings by `wbMapBySiblingOrder`), so
//: the outline, the exports and the canvas agree. The keys are an outliner's
//: (Workflowy, XMind's outliner): Enter adds a topic after this one, Tab
//: makes it a child of the one above, Shift+Tab moves it out a level,
//: Backspace on an empty topic removes it, the arrows move between rows, and
//: Escape hands the keys back to the canvas. Every change goes through the
//: canvas's own functions (the add, `wbMapTransplant`, `wbMapOutdent`, the
//: rename's save), so Undo, the tidy and the server are the canvas's. Typing
//: draws the topic's label on the canvas as it goes, without a render; the
//: name is saved when the row is left.
//: Set while the outline's Enter makes a topic, so the add path opens the
//: outline's row for typing instead of the canvas editor (`wbMapEditNode`).
const wbOutlineState = { adding: false };

//: The outline is the sidebar's Outline tab (WHITEBOARD_PLAN decision 26), so
//: it is open while that tab is the one showing.
function wbOutlineShowing() {
  const panel = document.getElementById("wb-sidebar-panel");
  return Boolean(panel && !panel.classList.contains("hidden") && wbSideState().tab === "outline" && wbIsMap());
}

//: View's Outline switch says whether the tab is showing.
function wbOutlineSwitchShows() {
  const sw = document.getElementById("wb-panel-outline");
  if (sw) sw.checked = wbOutlineShowing();
}

function wbOutlineToggle(on = !wbOutlineShowing()) {
  if (on && wbIsMap()) wbOpenSidebar("outline", { focus: false });
  else if (!on && wbOutlineShowing()) wbCloseSidebar();
  wbOutlineSwitchShows();
}

//: A map opening, or the board switching to one that is not: the sidebar
//: keeps its own tab (`wbSyncSidebarKind`); the rows and the switch follow.
function wbOutlineAfterSurface() {
  wbOutlineSwitchShows();
  wbOutlineSync(true);
}

//: The selected topic's row, or the first, takes the keys.
function wbOutlineFocusSelected() {
  const tree = document.getElementById("wb-outline-tree");
  const row = tree?.querySelector('.wb-outline-row[aria-selected="true"]') || tree?.querySelector(".wb-outline-row");
  if (row?._node) wbOutlineFocus(row._node);
}

function wbOutlineRowsNow() {
  const index = wbMapIndex();
  const rows = [];
  const walk = (node, depth) => {
    rows.push({ node, depth });
    for (const child of index.childrenOf.get(node.id) || []) walk(child, depth + 1);
  };
  for (const root of index.roots) walk(root, 1);
  return rows;
}

function wbOutlineRowEl(node, depth) {
  const row = document.createElement("div");
  row.className = "wb-outline-row";
  row.setAttribute("role", "treeitem");
  row.setAttribute("aria-level", String(depth));
  row.style.setProperty("--outline-depth", String(depth - 1));
  row._node = node;
  const field = document.createElement("input");
  field.type = "text";
  field.className = "wb-outline-text";
  field.value = wbMapLabel(node);
  field.setAttribute("aria-label", `Topic, level ${depth}`);
  field.spellcheck = true;
  //: **A row reads until it is asked to be edited** (INBOX 792, the owner: "i
  //: dont think i should be typing in these outline options in the sidebar
  //: unless i like double click on them or press an edit button"). A read-only
  //: field still takes focus and the arrow keys, so the list walks like a
  //: tree; a double click, F2, Enter or the pencil on the row opens it
  //: (`wbOutlineEdit`), Enter saves and Escape puts the old name back.
  field.readOnly = true;
  row.appendChild(field);
  //: A reference's name is the note or file behind it, not the map's to edit.
  if (node.kind !== "topic") {
    field.title = "This topic's name comes from the item it points at. Press F2 on the map to give it a caption.";
  } else {
    const pencil = document.createElement("button");
    pencil.type = "button";
    pencil.className = "ghost small icon-only wb-outline-edit";
    pencil.tabIndex = -1;
    pencil.title = "Rename this topic (F2)";
    pencil.setAttribute("aria-label", "Rename this topic");
    setLabel(pencil, "ph:pencil-simple");
    row.appendChild(pencil);
  }
  //: The topic's markers and due day, then its labels, as cells under its
  //: words (decision 34): the canvas's own painting, so the two agree.
  const cells = document.createElement("div");
  cells.className = "wb-outline-cells";
  const marks = document.createElement("span");
  marks.className = "wb-map-markers wb-outline-marks";
  const tags = document.createElement("span");
  tags.className = "wb-outline-tags";
  cells.append(marks, tags);
  row.appendChild(cells);
  wbMarkerUi.match.cells(row);
  return row;
}

//: Brings a row's cells up to date; each repaints only when its content changed.
function wbOutlineEditing(row) {
  return Boolean(row?.classList.contains("is-editing"));
}

//: Opens a row's field for typing; `select` takes the whole name so the first
//: key replaces it, as a new topic's "New topic" is.
function wbOutlineEdit(row, { select = false } = {}) {
  const field = row?.firstChild;
  if (!field || row._node.kind !== "topic") return;
  row.classList.add("is-editing");
  field.readOnly = false;
  field.focus({ preventScroll: true });
  if (select) field.select();
  else field.setSelectionRange(field.value.length, field.value.length);
}

//: Back to reading. `cancel` puts the saved name back first, on the canvas too.
function wbOutlineStopEdit(row, { cancel = false } = {}) {
  const field = row?.firstChild;
  if (!field) return;
  if (cancel) {
    field.value = wbMapLabel(row._node);
    wbOutlineMirror(row._node, field.value);
  }
  field.readOnly = true;
  row.classList.remove("is-editing");
}

//: Called after every render of the board (`wbScheduleRender`,
//: `renderWhiteboardNow`): rows rebuilt only when the tree's shape changed,
//: otherwise only the names and the selection mark are brought up to date,
//: and never the field being typed in.
function wbOutlineSync(force = false) {
  if (!wbOutlineShowing()) return;
  const tree = document.getElementById("wb-outline-tree");
  if (!tree) return;
  const rows = wbOutlineRowsNow();
  const shape = rows.map((r) => `${r.node.id}:${r.depth}`).join(",");
  const focused = tree.contains(document.activeElement) ? document.activeElement : null;
  const selected = wbSelectedItem?.kind === "object" ? wbSelectedItem.id : null;
  if (force || shape !== tree.dataset.shape) {
    //: The field being typed in survives a rebuild whole: its text (not yet
    //: saved) and its selection, so a new topic adopting its real id while
    //: "New topic" is selected does not leave the next key typed before it.
    const focusNode = focused?.closest(".wb-outline-row")?._node || null;
    const wasEditing = wbOutlineEditing(focused?.closest(".wb-outline-row"));
    const typing = focused
      ? { value: focused.value, start: focused.selectionStart, end: focused.selectionEnd }
      : null;
    tree.replaceChildren(...rows.map((r) => wbOutlineRowEl(r.node, r.depth)));
    tree.dataset.shape = shape;
    if (focusNode) {
      wbOutlineFocus(focusNode);
      const row = wbOutlineRowOf(focusNode);
      const field = row?.firstChild;
      if (field && field === document.activeElement) {
        if (wasEditing) wbOutlineEdit(row);
        field.value = typing.value;
        field.setSelectionRange(typing.start, typing.end);
      }
    }
  }
  const now = tree.contains(document.activeElement) ? document.activeElement : null;
  let at = 0;
  for (const row of tree.children) {
    const field = row.firstChild;
    const label = wbMapLabel(row._node);
    if (!(field === now && wbOutlineEditing(row)) && field.value !== label) field.value = label;
    row.setAttribute("aria-selected", String(row._node.id === selected));
    wbMarkerUi.match.cells(row, rows[at++].node);
  }
}

function wbOutlineRowOf(node) {
  const tree = document.getElementById("wb-outline-tree");
  if (!tree) return null;
  for (const row of tree.children) if (row._node === node || row._node.id === node.id) return row;
  return null;
}

function wbOutlineFocus(node, { caret = null, select = false } = {}) {
  const field = wbOutlineRowOf(node)?.firstChild;
  if (!field) return;
  field.focus({ preventScroll: true });
  field.scrollIntoView({ block: "nearest" });
  if (select) wbOutlineEdit(wbOutlineRowOf(node), { select: true });
  else {
    const at = caret == null ? field.value.length : Math.min(caret, field.value.length);
    field.setSelectionRange(at, at);
  }
}

//: The name on the canvas as it is typed, without a render: the label's own
//: inline drawing, the one a rename on the canvas ends with.
function wbOutlineMirror(node, text) {
  const el = document.querySelector(`.wb-object[data-id="${node.id}"] .wb-map-text`);
  if (el && el !== document.activeElement) wbMapInlineText(el, text);
}

//: The rename's save, as the canvas makes it: one Undo step for a real
//: change, folded into the add while the topic is still new (FEAT-15).
async function wbOutlineCommit(node, field) {
  if (node.kind !== "topic") return;
  const live = (wbState.objects || []).find((o) => o === node || o.id === node.id);
  if (!live) return;
  const edited = field.value.trim() || WB_MAP_NEW_TOPIC;
  if (live.data.content === edited) return;
  if (live._creating) await live._creating;
  wbHistoryFor();
  const top = wbUndoStack[wbUndoStack.length - 1];
  const madeIt = (e) => e?.action === "create" && e.kind === "object" && e.id === live.id;
  if (!(live._fresh && (madeIt(top) || (top?.action === "batch" && top.entries.some(madeIt))))) {
    wbPushUndo({ action: "move", kind: "object", id: live.id, before: WB_KIND_INFO.object.payload(live) });
  }
  delete live._fresh;
  live.data = { ...live.data, content: edited };
  await wbSaveObject(live);
  wbScheduleRender();
}

async function wbOutlineIndent(node, field) {
  await wbOutlineCommit(node, field);
  if (node._creating && !(await node._creating)) return;
  const index = wbMapIndex();
  const siblings = wbMapSiblingsOf(index, node);
  const above = siblings[siblings.findIndex((s) => s.id === node.id) - 1];
  if (!above) {
    wbAnnounce("This topic is already the first in its branch.");
    return;
  }
  const kids = index.childrenOf.get(above.id) || [];
  const order = wbMapKeyBetween(kids[kids.length - 1] || null, null);
  if (order != null) {
    node.data = { ...node.data, order };
    await wbSaveObject(node);
  }
  await wbMapTransplant(node, above.id, false, { via: "outline" });
  wbOutlineSync(true);
  wbOutlineFocus(node, { caret: field.selectionStart });
}

async function wbOutlineOutdent(node, field) {
  await wbOutlineCommit(node, field);
  if (node._creating && !(await node._creating)) return;
  const index = wbMapIndex();
  const parent = node.parent_id != null ? index.byId.get(node.parent_id) : null;
  if (!parent) {
    wbAnnounce("This is already a top-level topic.");
    return;
  }
  //: Right after its old parent, where an outliner puts it, rather than
  //: wherever its old key happens to sort among its new siblings.
  const aunts = wbMapSiblingsOf(index, parent);
  const next = aunts[aunts.findIndex((s) => s.id === parent.id) + 1] || null;
  node.data = { ...node.data, order: wbMapKeyBetween(parent, next) };
  await wbSaveObject(node);
  await wbMapOutdent(node.id);
  wbOutlineSync(true);
  wbOutlineFocus(node, { caret: field.selectionStart });
}

async function wbOutlineAddAfter(node, field) {
  await wbOutlineCommit(node, field);
  wbOutlineState.adding = true;
  try {
    await wbMapAddSibling(node.id);
  } finally {
    wbOutlineState.adding = false;
  }
}

//: The add path's hand-over (`wbMapEditNode`): the new row, selected so the
//: first key replaces "New topic", as the canvas editor does.
function wbOutlineTakeNewTopic(id) {
  wbOutlineSync(true);
  const node = (wbState.objects || []).find((o) => o.id === id);
  if (node) wbOutlineFocus(node, { select: true });
}

async function wbOutlineRemoveEmpty(node) {
  const index = wbMapIndex();
  if ((index.childrenOf.get(node.id) || []).length || index.nodes.length <= 1) return false;
  const rows = wbOutlineRowsNow();
  const at = rows.findIndex((r) => r.node.id === node.id);
  const before = rows[at - 1]?.node || rows[at + 1]?.node || null;
  if (node._creating) await node._creating;
  await wbMapDeleteSubtree(node.id);
  wbOutlineSync(true);
  if (before) {
    selectWbItem("object", before.id);
    wbOutlineFocus(before);
  }
  return true;
}

function wbOutlineStep(field, by) {
  const rows = [...document.getElementById("wb-outline-tree").children];
  const at = rows.indexOf(field.closest(".wb-outline-row"));
  const to = rows[at + by];
  if (to) wbOutlineFocus(to._node);
}

//: The outline panel is part of the board canvas, built when a board first opens (row 21).
onSurface("board", () => {
  document.getElementById("wb-outline-tree")?.addEventListener("input", (event) => {
    const row = event.target.closest(".wb-outline-row");
    if (row && row._node.kind === "topic" && wbOutlineEditing(row)) wbOutlineMirror(row._node, event.target.value);
  });

  document.getElementById("wb-outline-tree")?.addEventListener("dblclick", (event) => {
    const row = event.target.closest(".wb-outline-row");
    if (row && event.target.matches(".wb-outline-text")) wbOutlineEdit(row);
  });

  document.getElementById("wb-outline-tree")?.addEventListener("click", (event) => {
    const pencil = event.target.closest(".wb-outline-edit");
    if (pencil) wbOutlineEdit(pencil.closest(".wb-outline-row"), { select: true });
  });

  document.getElementById("wb-outline-tree")?.addEventListener("focusin", (event) => {
    const row = event.target.closest(".wb-outline-row");
    if (!row || row._node.id < 0) return;
    if (wbSelectedItem?.kind !== "object" || wbSelectedItem.id !== row._node.id) selectWbItem("object", row._node.id);
    for (const other of row.parentElement.children) other.setAttribute("aria-selected", String(other === row));
  });

  document.getElementById("wb-outline-tree")?.addEventListener("focusout", (event) => {
    const row = event.target.closest(".wb-outline-row");
    if (!row || !event.target.matches(".wb-outline-text")) return;
    if (wbOutlineEditing(row)) wbOutlineStopEdit(row);
    wbOutlineCommit(row._node, event.target);
  });

  document.getElementById("wb-outline-tree")?.addEventListener("keydown", (event) => {
    const field = event.target;
    const row = field.closest?.(".wb-outline-row");
    if (!row || event.ctrlKey || event.metaKey || event.altKey) return;
    if (!field.matches(".wb-outline-text")) return;
    const node = row._node;
    const editing = wbOutlineEditing(row);
    const done = () => {
      event.preventDefault();
      event.stopPropagation();
    };
    if (event.key === "F2" && !editing) {
      done();
      wbOutlineEdit(row);
    } else if (event.key === "Enter" && event.shiftKey) {
      done();
      wbOutlineAddAfter(node, field);
    } else if (event.key === "Enter") {
      done();
      if (editing) {
        wbOutlineStopEdit(row);
        wbOutlineCommit(node, field);
      } else wbOutlineEdit(row);
    } else if (event.key === "Tab") {
      done();
      if (event.shiftKey) wbOutlineOutdent(node, field);
      else wbOutlineIndent(node, field);
    } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      done();
      wbOutlineStep(field, event.key === "ArrowUp" ? -1 : 1);
    } else if (event.key === "Backspace" && editing && field.value === "" && node.kind === "topic") {
      done();
      wbOutlineRemoveEmpty(node);
    } else if (event.key === "Escape") {
      done();
      if (editing) {
        wbOutlineStopEdit(row, { cancel: true });
        return;
      }
      document.getElementById("whiteboard-container")?.focus({ preventScroll: true });
    }
  });

  document.getElementById("wb-panel-outline")?.addEventListener("change", (event) => wbOutlineToggle(event.target.checked));
});

// --- Markers (MINDMAP_PLAN §12.2 item 4, the audit's M4) --------------------
//
//: **A topic's markers** (decision 34): a priority 1 to 5, how far along it
//: is, a flag, and up to six icons, drawn in a row before the label
//: (`wbMapPaintMarkers`), set in one popover from the topic's menu
//: (`wbMapOpenMarkers`), and used to dim every topic that does not carry one
//: (`wbMapSetMarkerFilter`). The icons are a fixed set from the vendored
//: Phosphor font, never emoji: an emoji is drawn by the operating system,
//: differently on each, and not at all in an SVG or PNG export.
const WB_MAP_MARKER_ICONS = [
  ["star", "Star"], ["heart", "Heart"], ["lightbulb", "Idea"], ["question", "Question"],
  ["warning", "Warning"], ["check-circle", "Yes"], ["x-circle", "No"], ["thumbs-up", "For"],
  ["thumbs-down", "Against"], ["lightning", "Urgent"], ["target", "Goal"], ["clock", "Waiting"],
];
const WB_MAP_MARKER_ICON_NAMES = new Map(WB_MAP_MARKER_ICONS);
const WB_MAP_MARKERS_MAX = 6;

function wbMapMarkerParts(data) {
  const priority = Number.isInteger(data?.priority) && data.priority >= 1 && data.priority <= 5 ? data.priority : null;
  const progress = Number.isInteger(data?.progress) && data.progress >= 0 && data.progress <= 100 ? data.progress : null;
  const flag = data?.flag === true;
  const icons = Array.isArray(data?.markers)
    ? data.markers.filter((name) => typeof name === "string" && /^[a-z0-9-]{1,40}$/.test(name)).slice(0, WB_MAP_MARKERS_MAX)
    : [];
  //: A due day (decision 37), checked as the server checks it.
  const due = typeof data?.due === "string" && /^\d{4}-\d{2}-\d{2}$/.test(data.due) ? data.due : null;
  //: A start day (the Gantt view), the same shape; a bar needs both.
  const start = typeof data?.start === "string" && /^\d{4}-\d{2}-\d{2}$/.test(data.start) ? data.start : null;
  //: The time on the due day (L371), only beside a due day.
  const dueTime = due && typeof data?.due_time === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(data.due_time) ? data.due_time : null;
  return { priority, progress, flag, icons, due, dueTime, start };
}

//: "12 Oct", and whether that day has gone (local midnight to midnight).
//: With a `start` too, "5 Oct to 12 Oct"; a `start` alone (no due day), "from 5 Oct".
//: With a `time` ("09:30") the due day reads "20 Nov, 9:30 am" and is gone only once that time has.
function wbMapDueWords(due, start = null, time = null) {
  const now = new Date();
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const say = (text) => {
    const [y, m, d] = text.split("-").map(Number);
    const day = new Date(y, m - 1, d);
    return { day, words: day.toLocaleDateString(undefined, { day: "numeric", month: "short", ...(y !== today.getFullYear() ? { year: "numeric" } : {}) }) };
  };
  const end = say(due || start);
  const from = due && start ? say(start).words : null;
  const words = from ? `${from} to ${end.words}` : due ? end.words : `from ${end.words}`;
  if (!time || !due || from) return { words, past: Boolean(due) && end.day < today };
  const [h, m] = time.split(":").map(Number);
  const at = new Date(end.day);
  at.setHours(h, m);
  return { words: `${words}, ${at.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`, past: at < now };
}

//: What the row says to a screen reader and in its tooltip, in the order it
//: is drawn.
function wbMapMarkerWords(parts) {
  const words = [];
  if (parts.priority) words.push(`priority ${parts.priority}`);
  if (parts.progress != null) words.push(parts.progress === 100 ? "done" : parts.progress === 0 ? "not started" : `${parts.progress}% done`);
  if (parts.flag) words.push("flagged");
  if (parts.due) {
    const due = wbMapDueWords(parts.due, null, parts.dueTime);
    words.push(due.past ? `was due ${due.words}` : `due ${due.words}`);
  }
  if (parts.start) words.push(`starts ${wbMapDueWords(parts.start).words}`);
  for (const icon of parts.icons) words.push((WB_MAP_MARKER_ICON_NAMES.get(icon) || icon).toLowerCase());
  const text = words.join(", ");
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}

//: The row before the label. Rebuilt only when what it shows changed, so a
//: render of an unchanged map writes nothing here.
function wbMapPaintMarkers(host, data) {
  const parts = wbMapMarkerParts(data);
  const key = `${parts.priority}|${parts.progress}|${parts.flag}|${parts.icons.join(",")}|${parts.due}|${parts.dueTime}|${parts.start}`;
  if (host.dataset.key === key) return;
  host.dataset.key = key;
  host.replaceChildren();
  const words = wbMapMarkerWords(parts);
  host.hidden = !words;
  if (!words) {
    host.removeAttribute("role");
    host.removeAttribute("aria-label");
    host.removeAttribute("title");
    return;
  }
  host.setAttribute("role", "img");
  host.setAttribute("aria-label", words);
  host.title = words;
  if (parts.priority) {
    const badge = document.createElement("span");
    badge.className = "wb-map-mark wb-map-mark-priority";
    badge.dataset.priority = String(parts.priority);
    badge.textContent = String(parts.priority);
    host.appendChild(badge);
  }
  if (parts.progress != null) {
    const pie = document.createElement("span");
    pie.className = "wb-map-mark wb-map-mark-progress";
    pie.style.setProperty("--progress", `${parts.progress}%`);
    host.appendChild(pie);
  }
  const glyph = (name, extra = "") => {
    const i = document.createElement("i");
    i.className = `ph ph-${name} wb-map-mark${extra}`;
    host.appendChild(i);
  };
  if (parts.flag) glyph("flag", " wb-map-mark-flag");
  if (parts.due || parts.start) {
    const when = wbMapDueWords(parts.due, parts.start, parts.dueTime);
    const chip = document.createElement("span");
    chip.className = `wb-map-mark wb-map-mark-due${when.past ? " is-past" : ""}`;
    chip.textContent = when.words;
    host.appendChild(chip);
  }
  for (const icon of parts.icons) glyph(icon);
}

// whiteboard-map-marks.js: whiteboard-map-marks.js: map markers, dim and filter views, build-from-document  (moved out, L286).
//: Whether a topic is one of the person's notes rather than
//: words typed on the map: the only kind Expand from my notes reads.
function wbMapIsNoteTopic(node) {
  return Boolean(node && node.kind === "note" && node.data?.ref_id);
}

//: **Expand from my notes** (MINDMAP_PLAN 12.3 item 2). For a topic that is a
//: note: its own headings and the notes it links to, from the server's
//: `/expand`, which needs no model. The same picker and the same add as
//: Branches from my notes, so one Undo step takes the ticked ones back.
async function wbMapExpandFromNote(node) {
  const boardId = window.currentBoardId;
  if (!node || !boardId) return;
  wbAnnounce("Reading the note behind this topic.");
  let got = null;
  try {
    got = await apiJson(`/whiteboard/boards/${boardId}/nodes/${node.id}/expand`, { method: "POST" });
  } catch (err) {
    toast(err.message || "This topic could not be expanded.", true);
    return;
  }
  const rows = (got?.suggestions || []).map((s, i) => ({ id: i, ...s }));
  if (!rows.length) {
    toast("Everything in this note, its headings and the notes it links to, is already on the map.");
    return;
  }
  const chosen = await wbMapBranchPicker(rows, {
    title: "Expand from your note",
    about: `Under "${got.topic}", from the note's headings and the notes it links to.`,
    node,
    meta: (row) => [row.kind === "link" ? "A note it links to" : `A heading in "${row.note_title}"`],
  });
  await wbMapAddChosenBranches(node, boardId, chosen);
}

//: **Ghost topics** (MINDMAP_PLAN, the features audit's Phase G): the
//: suggestions both branch doors offer, drawn faded under the topic they
//: would hang from. Tab takes the one in focus (it firms up), Enter adds the
//: taken ones (the one in focus when none is taken), Escape drops them all;
//: a click takes or lets go. Resolves with the taken rows as `{text, note_id}`,
//: or null when dropped, so `wbMapAddChosenBranches` is still the one add and
//: one Undo step takes them back. A layer on `document.body`, fixed at the
//: topic's screen box, so the canvas never clips it; it closes when the board
//: is moved, zoomed or clicked, since it would no longer sit under its topic.
function wbMapBranchPicker(rows, { title, about, meta, node }) {
  return new Promise((resolve) => {
    document.querySelector(".wb-ghosts")?.remove();
    const anchor = wbMapNodeScreenBox(node);
    const layer = document.createElement("div");
    layer.className = "wb-ghosts";
    layer.setAttribute("role", "group");
    layer.style.zIndex = "22";
    layer.setAttribute("aria-label", title);
    const taken = new Set();
    const buttons = rows.map((row) => {
      const ghost = document.createElement("button");
      ghost.type = "button";
      ghost.className = "wb-ghost";
      ghost.setAttribute("aria-pressed", "false");
      const text = document.createElement("span");
      text.className = "wb-ghost-text";
      text.textContent = row.text;
      const from = document.createElement("span");
      from.className = "wb-ghost-from";
      from.textContent = (meta?.(row) || []).join(" ");
      ghost.append(text, from);
      ghost.addEventListener("click", () => toggle(ghost, row));
      layer.append(ghost);
      return ghost;
    });
    const toggle = (ghost, row, on = !taken.has(row.id)) => {
      if (on) taken.add(row.id);
      else taken.delete(row.id);
      ghost.classList.toggle("is-taken", on);
      ghost.setAttribute("aria-pressed", String(on));
    };
    const finish = (chosen) => {
      window.removeEventListener("pointerdown", outside, true);
      window.removeEventListener("wheel", away, true);
      window.removeEventListener("resize", away);
      layer.remove();
      document.getElementById("whiteboard-container")?.focus?.();
      resolve(chosen);
    };
    const away = () => finish(null);
    const outside = (event) => {
      if (!layer.contains(event.target)) finish(null);
    };
    layer.addEventListener("keydown", (event) => {
      const at = buttons.indexOf(document.activeElement);
      if (at < 0) return;
      //: Taken here, not passed on: the map's own Enter adds a sibling topic
      //: and Tab a child, and the layer is gone by the time they would run.
      if (["Escape", "Tab", "Enter", "ArrowDown", "ArrowUp"].includes(event.key)) event.stopPropagation();
      if (event.key === "Escape") {
        event.preventDefault();
        wbAnnounce("Suggestions dropped.");
        finish(null);
      } else if (event.key === "Tab") {
        //: Tab takes, Shift+Tab lets go: the walk is the arrows'.
        event.preventDefault();
        toggle(buttons[at], rows[at], !event.shiftKey);
        buttons[Math.min(at + (event.shiftKey ? 0 : 1), buttons.length - 1)].focus();
      } else if (event.key === "Enter") {
        event.preventDefault();
        const chosen = (taken.size ? rows.filter((r) => taken.has(r.id)) : [rows[at]]).map((r) => ({ text: r.text, note_id: r.note_id }));
        finish(chosen);
      } else if ({ ArrowDown: 1, ArrowUp: -1 }[event.key]) {
        event.preventDefault();
        buttons[(at + { ArrowDown: 1, ArrowUp: -1 }[event.key] + buttons.length) % buttons.length].focus();
      }
    });
    document.body.append(layer);
    const room = layer.getBoundingClientRect();
    const left = anchor ? Math.min(Math.max(anchor.left, 8), window.innerWidth - room.width - 8) : 8;
    const top = anchor ? Math.min(anchor.bottom + 8, window.innerHeight - room.height - 8) : 8;
    layer.style.left = `${Math.max(left, 8)}px`;
    layer.style.top = `${Math.max(top, 8)}px`;
    window.addEventListener("pointerdown", outside, true);
    window.addEventListener("wheel", away, { capture: true, passive: true });
    window.addEventListener("resize", away);
    buttons[0]?.focus();
    wbAnnounce(`${rows.length} suggested branch${rows.length === 1 ? "" : "es"}. ${about} Tab takes one, Enter adds, Escape drops them.`);
  });
}

async function wbMapAddChosenBranches(node, boardId, chosen) {
  if (!chosen?.length || window.currentBoardId !== boardId) return;
  let made = [];
  await wbRecordGesture(async () => {
    try {
      made = await apiJson(`/whiteboard/boards/${boardId}/nodes/${node.id}/branches`, {
        method: "POST",
        body: JSON.stringify({ items: chosen }),
      });
    } catch (err) {
      toast(err.message || "The branches could not be added.", true);
      return;
    }
    wbState.objects = [...(wbState.objects || []), ...made];
    if (node.data?.collapsed) {
      node.data = { ...node.data, collapsed: false };
      await wbSaveObject(node);
    }
    renderWhiteboardNow();
    if (wbMapLayout() !== "free") await wbMapTidy({ onlyBranch: wbMapTidyBranchScope(node.id), quiet: true });
  });
  if (!made.length) return;
  selectWbItem("object", made[0].id);
  wbAnnounce(`Added ${made.length} branch${made.length === 1 ? "" : "es"} from your notes. Ctrl+Z takes them back.`);
}
