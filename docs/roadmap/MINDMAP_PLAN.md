# Mindmaps: a dev plan

> Companions: [ROADMAP.md](../ROADMAP.md) · [HANDOVER.md](HANDOVER.md) ·
> [UI_MODERNISATION_PLAN.md](UI_MODERNISATION_PLAN.md) ·
> [AGENT_SKILLS_REFORM.md](AGENT_SKILLS_REFORM.md) · [PLAN.md](PLAN.md) ·
> [../ARCHITECTURE.md](../ARCHITECTURE.md) · [../DESIGN.md](../DESIGN.md)
>
> **Note for Fable: this plan is a first pass and is meant to be extended and
> refined, not executed verbatim.** Everything in §2 is grounded in the code as
> it stands; §5 onward is design intent that should be pressure-tested against
> the running app before any of it is built.

## 1. The instruction, verbatim

> I have a vision. I want to extend the whiteboard and make a mindmap feature
> like kaggle. any and all text boxes and things that are in the map stay
> bundled within the map and basically the mindmap as a whole becomes its own
> entity that can be attached to notes and is its own object and has its own
> library subtab or is a part of the boards and maps subtab. do deep research
> and figure out all the features and functions kaggle.it has as well as other
> mindmapping websites and programs and create a detailed dev plan to make it a
> reality. mindmaps should be readable by the ai, exportable as images and
> pdfs, built off the whiteboard, have lots of utility, have the ability to
> link and reference notes and documents and files etc. the mindmap as a whole
> can be an item that can be attached to, linked to, referenced in notes and
> documents. this features needs to be properly integrated with everything,
> with rendered previews and chips if attached to notes and/or the chat as well
> as if they appear in the dashboard widgets and/or the timeline and/or graph
> etc.

**The naming question is settled.** Asked directly, the user confirmed
"kaggle" was a typo for **Coggle (coggle.it)**: and said all of the tools
named here are good references, so the feature set below draws on **Coggle**
(immediacy, branch colours, loops and joins, image nodes, PNG/PDF/text/OPML
export, `.mm` import), **Kumu** (attributes, perspectives, focus mode, signed
edges), **XMind** (output quality, structure templates) and **Obsidian Canvas
Mindmap** (the keyboard set). They also named **Lucidchart** as a reference,
"but that's more for the whiteboard", its smart connectors, containers,
alignment tools and shape libraries map onto PLAN.md W1–W5, not this plan.

**The scope call in §4 is made: option B** (confirmed by the user in the same
exchange). Everything from §5 on assumes it.

## 2. What already exists (checked in the code, not assumed)

This is the single most important section: a large part of this feature is
already built, and CLAUDE.md's first rule exists because three sessions have
rebuilt existing work here.

- **A board is already an `Entry`.** `WhiteboardNode.board_id`,
  `WhiteboardSketch.board_id` and `WhiteboardObject.board_id` are all
  `ForeignKey("entries.id")` (`src/tessellate/core/database.py` ~930-1010). A
  board *is* a note row. So "the mindmap as a whole is its own object that can
  be attached to, linked to and referenced" is **already true at the data
  layer**: it inherits linking, tags, categories, the graph, the timeline and
  full-text search for free. The work is surfacing that, not adding it.
- **Nodes, sketches and objects are all board-scoped and workspace-scoped**
  (`WorkspaceMixin`), with `x/y/z`, optional `width/height/rotation`, and a
  `group_id`, so grouping and z-order exist.
- **`WhiteboardObject` uses one table with a `kind` discriminator**, which is
  the extension point for new node kinds (a mindmap topic, an embedded file
  card) without a migration per kind.
- **Boards have a preview renderer** (`_board_preview`, `_preview_items` in
  `routes_whiteboard.py`) and a Library "Boards & maps" sub-tab that lists and
  manages them, plus duplicate.
- **A Concept Map feature exists** (task #7, "Build the authored mindmap"),
  reachable from the Graph tab's toolbar. Its learnability is a known open item
  (task #103). **Read what it does before designing a second one**, the
  likeliest right answer is that "mindmap" and "concept map" become one feature,
  not two.
- **The graph already renders note-to-note structure** (`frontend/js/graph.js`),
  and the Library already has a Boards & maps sub-tab (the user's own preferred
  home for this).

**So the honest framing of this work is: promote the board from "a canvas that
happens to be an entry" to "a first-class map object with mindmap semantics,
surfaced everywhere the app already surfaces notes."**

## 3. Research: what the field actually offers

Sources at the end. Grouped by what it would mean here.

### 3.1 Structure and layout
- **Reingold–Tilford "tidy" tree**, improved to linear time by Buchheim et al.,
  is the standard mind-map layout; `d3-hierarchy`'s `tree()` implements it, and
  treating `x` as angle and `y` as radius gives the classic radial map from the
  same call. `d3-flextree` extends it to variable-sized nodes, which matters
  here because a node may be a note card, not a word.
- **Obsidian Canvas Mindmap** is the closest model for keyboard-first editing:
  Tab adds a child, Enter adds a sibling, arrow keys navigate, a node's whole
  subtree can be selected and moved, and edges can be coloured for grouping.
  This is the interaction set to copy, it is what makes a mindmap fast rather
  than a drawing.
- **XMind** is the benchmark for *output* quality and offline work; **Coggle**
  for immediacy (no ceremony, real-time concurrent edits); **MindMeister** for
  idea→task workflows; **Whimsical** for mixing maps with flowcharts and docs.

### 3.2 Semantics beyond a tree
- **Kumu** is the one worth studying hardest for this app: elements and
  connections carry **tags and attributes**, and "perspectives" turn that data
  into decorations: colour, size, filter. It adds **social-network metrics**
  (betweenness, closeness, eigenvector centrality), **automated community
  detection**, and a **focus mode** that starts from one element and unfolds the
  network step by step. It supports **systems maps and causal loop diagrams**
  (signed, directional edges), not just trees.
- That maps onto Tessellate directly: a map's nodes are often *real notes*, which
  already have tags and categories, so "perspectives" is a filter over data the
  app already holds: and the graph tab already computes some of these metrics.

### 3.3 Integration patterns
- **Excalidraw-in-Obsidian** is the reference for "a drawing is a first-class
  linked document": backlinks work, links survive a rename, and drawings appear
  in the graph view. That is precisely the integration bar the user is setting.
- Obsidian's own warning is worth heeding: with Canvas you end up with **two
  levels of linking** (through the canvas and through the notes), which
  confuses people. **Decide once, here: a map-to-note link is a real link and
  shows in the graph; a node's position on a canvas is not a link.**

## 4. Scope decision (make this call first)

Three options, with a recommendation.

| | Option | Consequence |
| --- | --- | --- |
| A | Mindmap as a **mode of the whiteboard**, same board, a toggle that turns on tree semantics, auto-layout and keyboard editing | Least new code, no second data model, one Library home. Risk: modes are a learnability tax. |
| B | Mindmap as a **new board `type`** on the existing board entry (`board.type = "map" \| "board"`) | One data model, two behaviours, two filters in the Library. Clean. **Recommended.** |
| C | A **separate entity** with its own tables and sub-tab | Duplicates linking, preview, export, permissions and the Library plumbing that boards already have. Not recommended. |

**Decision: B: confirmed by the user.** A board is already an entry; add a
`type` and a `layout` to it. Everything in §5 and §6 assumes B.

### What Coggle specifically does that the phases below must keep

Recorded because Coggle is the reference the user actually meant:

- **Zero ceremony.** A new map is one click and one central node; a child is
  the `+` on hover or `Tab`; there is no "mode" to enter. Phase 2 item 5 is
  the keyboard half of this; the `+` affordance on the hovered node is the
  pointer half and belongs in the same item.
- **Branch colour carries down the branch**, every descendant inherits the
  first-level colour unless overridden. Phase 2 item 8's "inherit-from-parent
  by default" is exactly this; the default palette is one colour per
  first-level branch, assigned in order.
- **Loops and joins**: a second parent link between branches, drawn as a
  curve distinct from the tree edges. Phase 2 item 9.
- **Text is markdown-ish** (bold, italics, links, code) and a node may be an
  image. Node kinds in Phase 1 item 3 cover the image; the text renderer is
  the whiteboard's existing markdown pass.
- **Export**: PNG, PDF, plain-text outline, `.mm` (FreeMind) and OPML;
  **import** `.mm` and OPML. Phase 4 items 16–17 add `.mm` to their list.
- **Auto-arrange** on demand rather than always: the user can drag a branch
  and it stays; "tidy" re-lays it out. Phase 2 item 6 becomes a command, with
  free placement kept per branch (a `pinned` flag on a node).
- **Presentation/print**: a map fits to page for PDF. Covered by Phase 4.

## 5. The feature set, in build order

### Phase 1: the map object (foundation)
1. **`type` and `layout` on the board entry.** `type: "board" | "map"`;
   `layout: "free" | "tree-right" | "tree-down" | "radial"`. Stored on the
   board's own `Entry` (a JSON settings column or a dedicated table,
   `WhiteboardObject`'s `kind` discriminator is the precedent for not adding a
   table per idea).
2. **A parent edge for nodes.** Mindmaps are trees; the whiteboard's links are
   a general graph. Add `parent_id` to whatever carries a map node, and keep the
   existing free links for cross-branch connections (which every serious
   mindmapper supports and calls a "relationship" or "cross-link").
3. **Node kinds**, on the existing discriminator: `topic` (text), `note` (a real
   `Entry`, this is `WhiteboardNode` today), `document`, `file`, `image`,
   `link`. A node that *is* a note keeps its identity: editing it edits the note.
4. **Containment is real.** "any and all text boxes and things that are in the
   map stay bundled within the map", enforce it: deleting a map deletes its
   `topic` nodes (they exist only there) and *unlinks* its `note`/`document`/
   `file` nodes (those live in the library and must survive). Write the test
   first; this is the rule most likely to be got wrong.

### Phase 2: editing that feels like a mindmap
5. **Keyboard-first**: Tab = child, Enter = sibling, Shift+Tab = outdent,
   arrows = navigate, F2/double-click = rename, Delete = subtree with confirm.
   Copy Obsidian Canvas Mindmap's set; it is the de-facto standard.
6. **Auto-layout** via Reingold–Tilford with variable node sizes (d3-flextree's
   algorithm, implemented locally: **no CDN, the app is offline-first**;
   `frontend/js/graph.js` already hand-rolls layout, so this is a sibling of
   existing code, not a new dependency).
7. **Collapse/expand a branch**, with a count badge on the collapsed node.
8. **Styling that carries meaning, not decoration**: per-node colour, shape and
   icon; per-edge colour and thickness; inherit-from-parent by default.
9. **Cross-links** (non-tree edges) rendered distinctly, dashed, per the
   systems-map convention: and optionally **signed/directional** for causal
   loop diagrams (Kumu's model).

### Phase 3: the map as a citizen of the app
10. **Library**: maps live in **Boards & maps** with a Maps filter chip (the
    user's stated preference), with the existing board preview upgraded to
    render map structure.
11. **Attachable and referenceable**: a map can be attached to a note, a
    document and a chat message, exactly as a file can today
    (`routes_chat.py`'s `file_ids` is the pattern to copy), and referenced
    inline with the existing `@` picker.
12. **Rendered previews and chips** everywhere the user listed: note bodies,
    the chat transcript, dashboard widgets, the timeline and the graph. One
    `mapChip()` and one `mapPreview()`, used by all of them, the app's
    recurring failure is the same object drawn five ways.
13. **Graph integration**: a map is a node in the graph; its note-nodes are
    edges from the map to those notes. This is the "decide once" call from
    §3.3: a map's *membership* is a link, a node's *position* is not.

### Phase 4: AI and export
14. **The AI can read a map.** A `read_mindmap` tool returning an indented
    outline (title, then the tree, with each node's kind and any note id), which
    is the form a small model handles best. Plus `create_mindmap`,
    `add_map_node`, `link_map_nodes`, gated behind the tool toggles, and
    written to the *contract* shape the skills reform (Phase A of
    [AGENT_SKILLS_REFORM.md](AGENT_SKILLS_REFORM.md)) defines, so they are
    usable by a 4B model.
15. **AI generation**: "make a map of these notes", the agent proposes a tree,
    the user accepts or edits it. Every mainstream tool now has this; the
    differentiator here is that the nodes are *the user's real notes*, not
    invented text.
16. **Export**: PNG and SVG from the existing canvas render, and PDF via the
    same path the app already uses for "Print or save as PDF" in the documents
    kebab. Also **Markdown outline**, **OPML** and **FreeMind `.mm`**, the
    interchange formats every mindmapper (Coggle included) reads: cheap, and
    it makes the feature not a lock-in.
17. **Import**: OPML, FreeMind `.mm` and indented Markdown, so an existing map
    can come in.

### Phase 5: utility
18. **Focus mode** (Kumu): start at one node, reveal the network step by step.
19. **Filter/perspective**: colour or hide by tag, category, age, or "has a
    note behind it", reusing the notebook's own metadata, which is the thing
    a general mindmapper cannot do.
20. **Map metrics** where they are honest: node count, depth, orphan branches,
    and, for cross-linked maps, the centrality measures the graph tab already
    computes.
21. **Templates**: a few starting shapes (brainstorm, decision tree, project
    breakdown, cause-and-effect), because an empty canvas is the main reason
    mindmap features go unused.

## 6. Files this will touch

- `src/tessellate/core/database.py`, board `type`/`layout`, node `parent_id`,
  new `kind` values. One Alembic migration.
- `src/tessellate/api/routes_whiteboard.py`, map CRUD, layout endpoint, node
  tree endpoints, export; extend `_board_preview` for map structure.
- `src/tessellate/ai/tools*.py`, the four map tools, contract-shaped.
- `frontend/js/whiteboard.js` (and `frontend/js/graph.js` for layout precedent): the
  map mode, keyboard editing, auto-layout, collapse.
- `frontend/js/library.js`, the Maps filter and the upgraded preview.
- `frontend/js/app.js`, `mapChip()`/`mapPreview()`, the `@` picker source, chat
  attachment, dashboard widget, timeline row.
- `docs/DESIGN.md`, the node/edge visual language, once, so it is not
  reinvented per surface.

## 7. Acceptance

- A map created from three notes shows those notes as nodes; editing a node
  edits the note; deleting the map leaves the notes intact and deletes only its
  own topics (test first).
- The same map appears as a chip in a note, in a chat message, in the graph, in
  a dashboard widget and on the timeline, all drawn by one renderer.
- `read_mindmap` returns an outline a 4B model can act on, verified against a
  real local model (the standing caveat in CLAUDE.md applies).
- Export produces PNG, SVG, PDF, Markdown and OPML; OPML round-trips through
  import.
- Keyboard: Tab/Enter/arrows build a twenty-node map without touching the mouse.

## 8. Risks

- **Two linking levels** (§3.3): decide the rule before building, or the graph
  fills with noise.
- **A second concept-map feature.** Check task #7 and #103 first; merging is
  almost certainly right.
- **Layout performance** on a large map, the whiteboard already had "shapes
  and links lag behind notes when panning" (task #71); auto-layout must run off
  the paint path.
- **Scope.** Phases 1-3 are the user's actual request; 4-5 are where a
  mindmap becomes worth having. Ship 1-3 completely before starting 4.

## Sources

- [Kumu](https://kumu.io/) · [Kumu: network mapping](https://kumu.io/markets/network-mapping)
- [Best Mind Mapping Software for 2026, ClickHelp](https://clickhelp.com/clickhelp-technical-writing-blog/best-mind-mapping-software/)
- [The 12 Best Mind Mapping Tools and Apps, Storyflow](https://storyflow.so/blog/best-mind-mapping-tools-2025)
- [Canvas Mindmap: Obsidian plugin](https://community.obsidian.md/plugins/canvas-mindmap)
- [Mind mapping with Excalidraw in Obsidian](https://www.zsolt.blog/2021/09/mind-mapping-with-excalidraw-in-obsidian.html)
- [Spatial canvases and your notes](https://tfthacker.substack.com/p/spatial-canvases-and-your-notes)
- [d3-hierarchy `tree()`, Reingold–Tilford](https://d3js.org/d3-hierarchy/tree) · [d3-flextree](https://github.com/Klortho/d3-flextree)
- [Radial tree component: Observable](https://observablehq.com/@d3/radial-tree-component)

## 9. Built: Phase 1 (backend)

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", MINDMAP_PLAN.md) on 2026-09-09: a plan holds open work only.

## 10. Built: Phase 2 (frontend)

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", MINDMAP_PLAN.md) on 2026-09-09: a plan holds open work only.

## 11. Built: the previews, Phase 4 and Phase 5

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", MINDMAP_PLAN.md) on 2026-09-09: a plan holds open work only.

## 12. The map as its own tool (INBOX 93, the owner's ask, 2026-09-09)

The owner: "the mindmap needs more specialised and targeted controls, yes
it is built off the whiteboard but it isn't the whiteboard ... it doesn't
need to stop at Coggle, it can straight up copy, merge and make better
many mindmap software." This section is the complete spec: every bug and
missing feature the owner named, every feature worth taking from Coggle,
XMind, MindMeister, MindNode, Freeplane, Miro and Whimsical, and the
things a notebook-native map can do that none of them can. Two sessions,
Opus, one worktree, each phase gated by `scratchpad/ui-sweeps/mindmap.js`
extended with the numbers named.

### 12.0 Decisions made (do not remake)

- **A whole-map tidy frames the map again, and only when it has to**
  (decided 2026-09-13, the option the seventh run left open). Auto-arrange
  is a command and not a constant, so nothing frames on its own; but a
  command that leaves the trunk off the canvas has not finished. Measured
  at 390x844 before this: after a tidy the root's box sat at x=-95 and
  `elementFromPoint` at its centre returned the shell behind the canvas.
  So a tidy with `onlyBranch` null calls `wbZoomToFit` when, and only when,
  some node's rendered box is outside the container. A branch tidy is the
  silent half of pressing Tab and never moves the view, and a tidy whose
  result already fits leaves the view alone. Gated by
  `scratchpad/ui-sweeps/maptidy.js`, 5 checks at 1440x900 and at 390x844.

- A map is a board of `type: "map"`; it keeps the whiteboard's storage,
  undo, export and previews, and gets its **own toolbar, its own context
  menus and its own keys**. The whiteboard's tool rail is hidden on a map;
  nothing of the whiteboard's chrome shows unless it applies to a map.
- **A map is never empty and never stuck.** Deleting the last node leaves
  a root placeholder ("Untitled map, type to start"); the toolbar always
  has "Add topic", "Add sub-topic", "Add sibling" enabled for the
  selection; a collapsed branch shows a count badge that reopens it on
  click and on Space.
- Every node action is reachable three ways: the node's edit strip, the
  right-click radial, and a key. The keys are the industry's: Tab child,
  Enter sibling, Shift+Enter above, Delete removes the node and re-parents
  its children, Shift+Delete removes the branch, F2 edits, Space toggles
  collapse, arrows walk the tree, Ctrl+D duplicate, Ctrl+Shift+arrows
  move within siblings, Alt held turns adds into removes (Coggle).
- Styling is per node and per link and is stored in `data` (shape, fill,
  border, text size, weight, alignment, icon, image, link style, link
  label position), with **inheritance down the branch** and "Reset to
  branch" on any node; the theme picks defaults, never overrides a
  choice.
- Layouts: tree right, tree left, both sides (Coggle), org chart down,
  logic chart, fishbone, timeline (XMind), radial (MindNode); a branch
  can override the map's layout; auto-arrange is a command, not a
  constant, so a hand-placed node stays put until asked.
- Everything the map shows is in the tree endpoint and the FreeMind and
  OPML exports round-trip; a feature that cannot round-trip is not built.
  (Audit 2026-10-05 found FreeMind dropped a one-root map's centre; fixed
  the same day, decision 22.)
- **The last topic cannot be deleted; clearing the map is offered
  instead** (the owner asked directly: "should the user even be able to
  delete the primary core node??"). A map with no nodes is a dead end by
  construction: every add gesture hangs off a node that is already there,
  so removing the last one removes the way to make the next one. Refusing
  the delete is a smaller surprise than silently recreating a root under
  the same name, and "clear the map" says what it does, so the refusal
  carries that action: it takes the whole map away and leaves one blank
  topic ready to type into. Enforced at both delete paths (the map's own
  subtree delete, and the generic object delete the Delete tool, the
  context menu and the selection bar use), because a rule enforced at one
  of two doors is not a rule.
- **Multiple roots are allowed** ("should the user be able to make
  multiple main core nodes??"). Yes: real maps have several trunks, and
  nothing in the code has ever assumed one, `wbMapIndex` returns a list of
  roots, the tidy pass lays out a forest, and Enter on a root already adds
  another root. So this is a decision to keep and to surface, not to build:
  "Add topic" in the map dock adds a top-level topic whatever is selected,
  which is the only visible way to make the second trunk.
- **There is no "sub core" node type** ("sub core nodes??"). A node with
  children *is* the sub core: it already draws larger than its leaves
  through the branch colour and the depth it sits at, and its subtree
  already collapses, tidies, transplants and exports as a unit. A third
  tier would be a concept the data model does not have (`parent_id` and
  `kind`, nothing else), and every export format this plan commits to
  round-tripping (FreeMind, OPML, Markdown outline) has no way to carry
  it, so it would be a decoration that vanishes on the first export.

- **Space keeps the pan; `C` folds a branch; Space works on the fold
  control itself** (left open by the previous run, decided here). Held space
  is this canvas's pan gesture from every tool (`wbZoomFilter`) and a map
  node is selected nearly all the time once someone is editing, so binding
  Space to collapse would take the pan away exactly when it is most used and
  would make a map pan differently from a board, which is the opposite of
  "the mindmap can keep important and usable parts of the whiteboard". So
  the key on the canvas is `C` (bare, beside Tab, Enter, F and the arrows;
  `c` is not a tool key), and §12.1 item 7's "reopens on click and on Space"
  is met where it actually reads as a button: with the keyboard focus on a
  node's chevron or on the dock's Collapse button, the Space handler stands
  aside and the browser's own activation folds the branch.
- **A node carries its colour on its own card, so a trunk can set one.** The
  previous run disabled the picker on a root because "a colour paints only
  the line coming into a node and a root has no incoming line". That is true
  of the edge and false of the card: `wbPaintMapNode` writes `--wb-branch` on
  every node and `.wb-map-node` already draws it as the 4px spine down the
  leading edge, so a root's colour was drawn all along and only the control
  refused to set it. It does not cascade: the roots' children are the
  first-level topics and start the palette over by design, which is Coggle's
  rule, so a trunk's colour marks the trunk and every branch under it keeps
  its own. The picker's title says which of the two it is doing.

- **A picture in a topic is one of this notebook's own uploads, through
  `/media/upload`, and nothing else** (§12.1 item 2's fourth, decided 2026-09-21
  while building it). The plan said the item "needs the board's upload path",
  and it turned out there is exactly one to need: a board image, a picture
  pasted onto a board and a note's own attachment all already POST to
  `/media/upload`, which is what runs the captioning, the text extraction and
  what the Library's orphan sweep counts. So no route was added; the node
  stores the url that path hands back, in `data.image`, held to the same
  `MEDIA_URL_RE` allowlist an image *object*'s url is, by a validator on the
  field rather than at the endpoint, because the two XML imports write into
  `data` through the same model and a `_image` attribute in a file somebody
  was sent is exactly the door an off-origin url would come through.
- **Taking the picture out of a topic leaves the upload alone.** The file is in
  the Library and a topic is one of the places it can appear, not its home; a
  delete of the bytes from a menu whose every other entry is about this node
  would be a delete nobody asked for. For the same reason `image` is *not* in
  the list "back to the branch" clears (`WB_MAP_STYLE_KEYS`): reset's whole
  promise is that it is the safe way out of an over-decorated topic, so it
  drops looks and never content. It is in the list a *copy* carries, because a
  copied branch that lost its pictures would be the other half of that mistake.
- **A bend on a line is two fractions of that line's own length, not two board
  coordinates** (§12.1 item 5's third, decided 2026-09-21 while building it).
  The plan named the cost correctly: a tree edge has no row, so it is two
  `data` fields on the child, `edge_bend` (across the line) and `edge_slide`
  (along it from the halfway mark). They are fractions in the frame the line
  defines because the frame is rebuilt from the anchors on every read: a pair
  of coordinates would be right until either end moved, which on a map that
  tidies itself is one gesture later, and the same pair would mean a different
  shape after an export and an import at another size.
- **The waypoint composes with all three line shapes, each in the way that
  shape can**: the curve passes through it (its two control points move 4/3 as
  far, which is what puts the handle *on* the curve at t = 0.5 rather than near
  it), the straight line kinks at it, and the elbow moves its turn to it,
  clamped between the anchors so a right angle cannot double back. The tapered
  ribbon the default curve is drawn as reads the same four points, so the
  control is not one that does nothing on most of a map.
- **A line's two controls sit side by side on it, and the handle is revealed by
  pointing at the line as well as by selecting a topic.** Both of these are
  answers to something measured rather than reasoned: the mid-line `+` was at
  the same point as the handle and, being HTML above the SVG and invisible but
  still taking the pointer, swallowed the drag outright, so it now steps 26
  units along the line; and the map strip opens 44px above the selected topic
  and is several hundred pixels wide, so for a child laid out a little below
  its parent it lands exactly on the middle of the line into it
  (`elementFromPoint` at the handle's centre returned the strip). Hover needs
  nothing selected, so it needs no strip.
- **A topic's place among its siblings is a key, `data.order`, defaulting to
  its id** (taken 2026-10-03, INBOX 445, building the Ctrl+Shift+arrows this
  section names). A key rather than a rank, so a move writes two rows and an
  insert one; the id default keeps every existing map in creation order; the
  server sorts by the same key (`_sibling_key`), so the tree, the exports and
  the agent's outline agree with the canvas, and the order round-trips as
  outline order. Branch colours stay with the branch (the palette walks by
  id), so moving a branch up does not repaint the map.
- **Delete on a topic is one entry on the board's undo stack** (taken
  2026-10-03): the toast's Undo and Ctrl+Z are the same entry, and the
  restore writes the whole row back, not only the text and colour.

### 12.1 Phase 6a, the controls

Closed 2026-10-05 (op5): moved whole to HISTORY.md ("Moved from the plans,
2026-10-05 (MINDMAP_PLAN §12.1 closed, op5)").

### 12.2 Phase 6b, structure and richness (1 session)

1. **Boundaries** and 2. **Summaries**: built (decisions 19 and 20;
   HISTORY.md, "Moved from the plans, 2026-10-05 (boundaries and
   summaries)"). A boundary round a lasso'd set that is not one branch is
   not built.
3. **Relationships**: built (§13c, the cross-link; HISTORY.md, op5's
   §12.1 record).
4. **Markers and task info**: priority 1 to 5, progress 0 to 100, flags,
   due date (a reminder can be created from it), a checkbox; filter the
   map by marker; the outline view shows them as columns. The checkbox and
   the count up the branch are built (decision 15; HISTORY.md, "Moved from
   the plans, 2026-10-04"); priority, progress, the flag, icon markers and
   the filter are built (decision 34; HISTORY.md, "Moved from the plans,
   2026-10-05 (markers)"); due dates with a reminder are built (decision
   37; HISTORY.md, "Moved from the plans, 2026-10-05 (due dates, op5)");
   tags on a topic are open.
5. **Notes on nodes**: a node that is a notebook note shows the note's
   own text here, editable both ways. The text note behind a topic is
   built (decision 18; HISTORY.md, "Moved from the plans, 2026-10-04").
6. **Comments** (MindMeister): a thread per node, count marker. Built for
   topics and board items alike (WHITEBOARD_PLAN decision 17; HISTORY.md,
   "Moved from the plans, 2026-10-04 (comments)").
7. **Multiple roots, floating topics, eight palettes**: built (HISTORY.md,
   "Moved from the plans, 2026-10-05 (MINDMAP_PLAN §12.2 items 7 and 10, op5)").
8. **Outline view**: built (decision 33; HISTORY.md, "Moved from the plans,
   2026-10-05 (the map's outline)"). Its markers as columns wait on item 4.
9. **Presentation mode**: built (decision 21; HISTORY.md, "Moved from the
   plans, 2026-10-05 (a map presented by branch)").
10. **Export and import**: built (the same HISTORY.md record).
Gate: mindmap3.js extended with one check per feature; the 201-node map
keeps 60 fps pan (measured with the frame probe); round-trip of every
export that claims it.

### 12.3 Phase 6c, what only a notebook can do (½ session)

1. **Nodes are notes**: any node can become a note (and stays linked); a
   note dragged from the Library becomes a node with its card; the map
   node and the note title edit each other.
2. **Grow with the AI**: on any node, "Suggest branches" proposes five
   children from the notebook (grounded, with the source note on each),
   "Expand from my notes" fills a branch from search results,
   "Summarise this branch" writes the parent's note. (Suggest branches is in:
   WHITEBOARD_PLAN decision 36, HISTORY "wb-phase2"; drawn as ghosts under the topic, fixes7-1018. Summarise this branch is built, HISTORY.md, "Moved
   from the plans, 2026-10-05 (op3-1005)". Expand from my notes is built,
   HISTORY.md, "Moved from the plans, 2026-10-18 (mindmap-1018)".)
3. **From a question**: "Make a map of..." in chat proposes a map
   (exists, Phase 4) and now opens it in the map editor with the
   proposal as floating topics to accept or discard. (Chat's Make a mind map
   of an answer or a whole chat is built, 2026-10-18 fixes7: no model, the
   text's headings and lists; the floating-topics proposal is still open.)
4. ~~**Graph sync**~~ **Built** (HISTORY.md, "Moved from the plans, 2026-10-05
   (docs hygiene before 0.4.0: MINDMAP_PLAN)"): a map is a node in the graph
   with an edge of kind `map` to each note on it (`_add_map_edges`,
   `routes_graph.py`; `tests/test_mindmap.py`), and the graph's "Mind map"
   selection action makes one.
5. **Study mode**: built (decision 36; HISTORY.md, "Moved from the plans,
   2026-10-05 (study the map, op5)"). The note behind a topic as the answer
   is built (HISTORY.md, "Moved from the plans, 2026-10-18 (mindmap-1018)").
Gate: each AI action grounded (its sources listed) and faked in tests;
the study mode measured on a 40-node map.

### 12.4 Not built until asked

Real-time collaboration, cloud sync, voice-to-map, AI image generation
in nodes.

### 12.5 One place per action (INBOX 200 and 201, the owner, 2026-09-13 night)

The owner reopened this section's ring: "especially with the mindmap, it
needs a lot of ux and usability improvement, like the way the controls are
available, what controls and tools are available and where, and how the item
radials are used is confusing and doesnt feel clean", and "I want more and
better ways to differentiate core idea nodes in the mindmap".

The audit that this is written from is in
[`archive/agent-remaining/mindmap.md`](archive/agent-remaining/mindmap.md), measured by
`scratchpad/ui-sweeps/mapaudit.js` on a map of twelve topics: **112 controls
across six surfaces**, add-a-child reachable from five places, a fold from
four, a colour from four, six actions reachable only from a ring nobody finds
by accident, and a node context menu that was **dead code on a map** (the
right-click opens the ring and returns before the menu is built).

#### Decisions made, 2026-09-13 night (do not remake)

*Revised 2026-10-05* (WHITEBOARD_PLAN decisions 19 and 26, the features
audit 9.5): the sidebar and the Format panel are new surfaces, off the canvas.
The ring keeps the topic; the strip's three doors move into the Format panel's
tabs when the panel reaches maps, so one place per action is kept.

- **One place per action, and three surfaces with one job each.** The **ring**
  is what you do to *this topic from here*; the **strip** is how the topic and
  its line *look*; the **dock** is what you do to the *map*. An action that
  was on two of them loses one. Gated by `scratchpad/ui-sweeps/mapplaces.js`,
  which maps every control id to the edit it writes and fails on a repeat.
- **The ring is six slots, each with its word drawn**: add child, add beside,
  fold, delete, connect, more. Not eight icon-only discs, which is a memory
  test; not a ring that grows with the feature list, which is how it got to
  eight. A slot is a 7rem pill placed with `left`/`top` from the radius (the
  press cue owns `translate`, `tests/test_ui_recipes.py`), so the six sit at
  60 degrees on one circle over the opaque band from `ab70d9b`.
- **The ring and the strip are never open at once.** They answer two questions
  about one topic and were both placed from its box, which produced a strip
  shoved 136px clear of the ring or drawn across it (INBOX 114). The ring
  takes the node while it is open; the strip comes back when it closes.
- **What left the ring went to the topic's own menu, not away**: tidy this
  branch, copy this branch, add from the library, cut free of its parent, and
  where the topic points. The menu now carries every action a topic has, the
  ring's six included, and it is reachable from the ring's **More** slot and
  from the ContextMenu key (Shift+F10), because a right-click on a map node
  belongs to the ring.
- **Every ring slot is also a key**: Tab, Enter, C, Delete, Shift+C (connect,
  which is the board's own connector chord) and Shift+F10. The ring's caption
  says the first four at rest, so the ring reads as a shortcut rather than as
  the only way in. Proved without a pointer: `mapplaces.js` builds a five-node
  tree from the keyboard.
- **The line ring keeps only what is not a look**: reverse, label, cut. Its
  dash and its colour wrote the same two fields the strip's own controls do
  (`edge_dashed`, `color`), and its three line shapes are a look, so they are
  one picker in the strip now.
- **A map does not show the board's Insert and Arrange menus.** The dock
  already hides thirteen board-only tools on a map; the top bar was offering
  the same things again. Insert places a sticky, a text box, a shape or a bare
  note card, none of which a tree can hold; Arrange aligns and re-orders by
  hand, which is the layout's job. Measured: 60 controls in a map's top bar
  before, 40 after.
- **A core idea is told apart three ways at once**: the ellipse, a filled
  ground in the branch colour with contrasting text, and one step larger type,
  with a star before the label. One toggle in the strip sets all of them
  (INBOX 201: "more and better ways to differentiate core idea nodes"). A
  border alone was the old answer and it is the one a map full of coloured
  branches cannot carry.
- **The empty map says how to start.** One line under the templates card, gone
  on the first topic added and never shown again.

## 13. The map, read against its six complaints: measured 2026-09-21, phases open

The owner, INBOX 305: "the mindmap needs A LOT of improving. Tools and
utilities are really awkward to use and dont show themselves how id expect,
there are two types of connections, it is really confusing to access and use
features and utilities, they are hard to find and figure out how to use, they
are unintuitive, the ui needs improving, the mindmap is slow, the
customisation features are lacking severely and it just feels really unclean
and unprofessional."

That is six complaints, and this section is a read rather than a redesign:
the complaint is broad, and a redesign built on a guess is this project's
most expensive recurring mistake. Every number below was taken in a real
Chromium against the branch head on 2026-09-21, at 1440x900 in light unless
another width is named. **Nothing here is carried over from a previous
session**; where a previous session's figure is quoted it is labelled prior
and was re-taken.

**What the map surface is for, decided here so the phases cannot drift.**
This is a notebook's thinking surface, not a diagram editor. The person using
it is laying out what they already know or are working out, and the map's
whole claim is that the structure in their head is on the screen with as
little ceremony as possible. So "professional" here means a map they would be
content to put in front of somebody, and "improved" means fewer decisions per
topic, not more controls: nothing in the phases below adds a control to the
canvas that a thinker did not ask for, and an affordance that belongs to one
topic is sized like one topic.

### 13.1 Is it slow? The one claim measured before anything was designed

`scratchpad/ui-sweeps/mapperf.js`, registered in `scripts/gate.sh`'s sweep
list. Maps of 50, 200 and 500 topics built through `/whiteboard/boards/import`
(a route a person has, from the Board menu) so the figures are the cost of
*having* the nodes rather than of adding them. Frame deltas come from a rAF
loop running in the page across a real `page.mouse` gesture, so a blocked main
thread shows up as one long frame, which is what it is.

| Topics | Open to painted | `wbMapIndex` | `wbMapTidyPositions` | `renderWhiteboard` | Pan, median / worst | Drag, median / worst |
| --- | --- | --- | --- | --- | --- | --- |
| 50 | 371.5ms | 0.0ms | 2.9ms | 60.5ms | 16.7 / 33.3ms | 16.7 / 66.6ms |
| 200 | 906.4ms | 0.1ms | 16.7ms | 281.4ms | 16.7 / 50.1ms | 16.7 / 416.5ms |
| 500 | 3608.8ms | 0.1ms | 76.8ms | 1282.4ms | 16.7 / 133.4ms | 16.7 / 1583.3ms |

**Re-measured on the same probe after 13a** (2026-09-21, same machine, same
Chromium, one run each; the 500 row's before figures in this second table are
that run's own baseline, taken minutes earlier, not the numbers above):

| Topics | Open to painted | `wbMapTidyPositions` | `renderWhiteboard` | Pan, median / worst | Drag, median / worst |
| --- | --- | --- | --- | --- | --- |
| 50 | 371.5 to **314.2ms** | 2.9 to **0.1ms** | 60.5 to **23.3ms** | 16.7 / 16.8ms | 83.3 to **16.8ms** |
| 200 | 906.4 to **714.2ms** | 16.7 to **0.3ms** | 281.4 to **123.2ms** | 16.7 / 50.1ms | 416.6 to **33.3ms** |
| 500 | 3443.3 to **2049.1ms** | 76.3 to **0.6ms** | 1279.2 to **543.0ms** | 16.7 / 133.4ms | 1650.0 to **66.8ms** |

**Re-measured a third time, after 13a-open** (2026-09-21, same machine, same
Chromium, the probe's own five new numbers). The before column is that run's
own baseline, taken from the merge head on a second server minutes earlier,
not the tables above; `renderWhiteboard` is now measured after a change,
because a differential render timed against nothing measures the skip:

| Topics | Open to painted | Render, one topic moved | Render, every topic | Render, nothing changed |
| --- | --- | --- | --- | --- |
| 50 | 314.0 to **393.1ms** | 22.6 to **7.9ms** | 27.7 to **16.6ms** | 23.7 to **10.5ms** |
| 200 | 757.0 to **537.2ms** | 122.6 to **19.8ms** | 138.5 to **53.5ms** | 112.2 to **19.4ms** |
| 500 | 2022.3 to **965.6ms** | 534.7 to **47.8ms** | 540.2 to **149.1ms** | 509.4 to **45.3ms** |

And the gesture the same run takes, before and after, at 500 topics: pan
16.7ms median and 133.4 to 150.0ms worst, drag 16.7ms median and 66.6 to
66.7ms worst, and one branch drag over 300 link sketches **1,000.0 to
116.7ms** worst (66.7ms without the links, both before and after).

The 50-topic open is slower after the pass than its own baseline was: at that
size the open is not the render at all (7.9ms of it), it is the tab switch,
the fetch and the fit, and the spread between two runs of it is bigger than
anything this pass changed.

**Zoom, measured for the first time** (nothing in this repository had ever
taken it, and 13.1 reading 1 predicted it): six ctrl-wheel steps out and six
back in, at 500 topics, **16.7ms median and 166.7ms worst**, against 16.7 and
133.4ms on the same head before this pass, which is one frame of this
machine's spread either way.

**And it is not script, measured rather than reasoned.** The same gesture with
`handleWbZoom`, `wbApplyZoomTransform`, `wbSyncGridToTransform`,
`wbRenderNavigator`, `wbUpdateSelectionBar` and `renderWhiteboard` each wrapped
in a timer: **2.6ms of script across a 2,239ms gesture**, while 14 of its 34
frames ran over 33ms and the worst was 166.7ms. A zoom changes the scale of one
promoted layer holding every topic on the board, the browser re-rasters it, and
no amount of making the render cheaper touches a frame that runs no render. The prediction is confirmed: a zoom
changes the scale of one promoted layer holding every topic, the browser
re-rasters it, and no amount of making the render cheaper touches it, because
no script runs on those frames. That is 13a-view. **Corrected 2026-09-23 by
a trace:** the worst frames were not rasterising but a restyle of every
element on the board on the press and the release (an inherited `:active`
cursor on the container, and a Settings rule that made any class change
restyle a whole subtree); the record is 13a-view's in HISTORY.md.

**One edge of the zoom control, found while measuring it.** d3-zoom multiplies
a wheel delta by ten when ctrl is held, because that is how a browser reports
a trackpad pinch. A trackpad sends a few units a notch and gets a smooth
1.1x; a mouse wheel sends 120 and gets **5.3x a notch**, so two notches take a
map from 1x to the 4x ceiling or to the 0.1x floor. Nobody has reported it and
it is not this pass's work, but it is the likeliest reading of a zoom that
"jumps" on a machine with a real mouse.

**The claim is true, and it is one thing.** Four readings settled it, and 13a
found that the third and fourth name two different bugs, not one:

1. ~~**Panning is not slow at any size.**~~ **Withdrawn, 2026-09-21.** The
   median frame is 16.7ms at 50, at 200 and at 500 *in most runs*, and the
   reading above treated one run as the answer. The owner, after this section
   was written: "the mindmap is still insanely laggy to pan around, move
   objects, and zoom." Re-measured with
   `scratchpad/ui-sweeps/mapmidpan.js`, panning a 500-topic map is
   **bimodal on the same machine**: five runs of the identical gesture gave
   16.7, 16.7, 116.7, 133.3 and 150.0ms per frame, and the slow runs are not
   explained by the tool or the button (the Hand tool with the left button
   measured both fast and slow, as did the middle button from Select). Under
   the CPU profiler the whole 30-move gesture spends **under 10ms in script**:
   the time is the browser re-rasterising, and the three panned layers already
   carry `will-change: transform`, so what is being re-rasterised is one
   promoted layer holding every topic on the board. That is the render pass,
   13a-open, reached from a second direction. **What is settled** is that the
   pan *path* is not the bug: the middle button reaches the same d3-zoom
   behaviour through `wbZoomFilter` as the Hand tool, and the two measure the
   same in the same run, which `mapmidpan.js` now asserts as a comparison
   rather than against a budget that a fast run would always meet.
2. **The layout maths is not slow either.** 76.8ms to lay out 500 topics is
   a command a person pressed, and `wbMapIndex`, which every map action calls
   first, is free at 0.1ms. Neither is worth optimising.
3. **`renderWhiteboard` is the whole of the *opening***, and it grows faster
   than the node count: 8.1× the nodes buys 21× the render. 1,282ms is a full
   second of frozen tab per pass. **Corrected by 13a**: it is not what the
   drag pays. A CPU profile of the probe's own 500-topic gesture put
   `renderWhiteboard` at a twentieth of the drag's cost and
   `document.querySelector` plus `offsetWidth` at the top of the list, so the
   two halves of this section had two separate causes and reading 3 was
   carrying the blame for both.
4. **It lands on the user at the worst possible moment.** A second run of the
   probe recorded where in the gesture the worst frame falls: `dragWorstAt`
   **0.03**, three per cent into the drag. The 1.6-second stall at 500 topics
   is not the drop, it is the **pick-up**: the map freezes the instant a
   finger goes down on a topic, before it has moved. (`panWorstAt` 0.91, near
   the end, which is the settle after the pan.) A second 500-node run
   reproduced it: 1,616.5ms worst drag frame, 1,179.5ms render. **This
   reading was the one that mattered, and it was exactly right.** What the
   first frame of a drag does is capture the branch under the topic and move
   it once, and every part of that was written per member: a board scan to
   find each one, a rebuilt map index and three document-wide attribute
   queries per edge to find its lines, an element lookup per member per
   frame, and a `querySelector` plus a layout read for both ends of every
   edge. None of it was a render.

So: the map is slow to open and slow to touch, and both are the same bug.
Nothing else measured here is worth a phase until that one is fixed. **What
is not known is the owner's own map size**, and it changes which phase
matters: at 50 topics the stall is 67ms and nobody would write that sentence,
at 500 it is 1.6 seconds. (The question is moot: 13a is built.)

### 13.2 The two kinds of connection

`scratchpad/ui-sweeps/maptwokinds.js`, 10/10. One map, one tree edge and one
free link between two topics that are both already in the tree, then the
running app asked what each offers. They are drawn by the same renderer and
look nearly alike, which is exactly why the difference had to be read off the
controls rather than looked at.

| | **Tree edge** (`parent_id`) | **Free link** (a link sketch) |
| --- | --- | --- |
| What it is | Not a row. It *is* the child's `parent_id`, so everything about it is stored on the child | Its own `whiteboard_sketches` row, `type: "link-straight"` or `"link-curved"`, naming both ends |
| Made by | Tab, Enter, the ring's Add child / Add beside, the node's own `+`, dragging a loose topic onto another | The rail's **Connect** section: Straight link (C), Curved link (Shift+C); and the ring's **Connect** slot, which picks the same rail tool |
| Right-click opens | The **link ring**, 3 slots: Reverse, Label, Cut | Nothing of the map's. The ring stays hidden (measured: `linkRingVisibleForFreeLink` false) |
| Its look is set from | The **topic strip**, 5 of whose 14 controls are the line's: thickness, dash, arrowhead, shape, and the topic colour it inherits | The **board's own context bar**, `wbContextKindOf` returns `"link"`: ink, caps, stroke. A different surface, with different words, for the same idea |
| Can be re-shaped | Yes: `edge_bend` / `edge_slide`, a waypoint dragged on the line (added this session) | No waypoint. The board's link has its own anchors and caps instead |
| Label | Yes, `edge_label` on the child, from the ring | Yes, `label` in the sketch's data, but no map control writes it |
| Survives Markdown / OPML / FreeMind export | **Yes**, all three: it is the indent | **No**, none of the three. `export_board` builds from `_build_tree(_map_objects(...))`, which walks objects and `parent_id` only. The tree endpoint does return `cross_links`; no exporter reads it |
| Counted in the map's own stats | Yes, as the tree | Yes, separately, as "Cross-links" |

**And one gesture produces either, decided by something invisible.**
`wbMapJoinByLink` reads the drop: if the target is not already in the tree,
the drag becomes a **re-parent** and a tree edge; if both ends are in the
tree, the same drag leaves a **free link**. Nothing on screen says which is
about to happen, and the two outcomes differ in whether the result exports.

**The judgement, with the cost of each direction.** The split is *justified in
the data* and *not justified in the controls*. A tree is a tree and a
cross-reference is a graph edge; XMind and Coggle both keep the distinction,
and collapsing `parent_id` into rows would be a migration of every map for no
gain a user can see. What is not justified is that the two have separate
control surfaces, separate vocabularies and different export fates:

- **Absorb the free link into the map's own grammar** (the direction this
  plan should take). The free link keeps being a sketch row; what changes is
  that on a map it gets the link ring rather than the board's context bar, its
  own word for what it is, and a line in the exports. Cost: an exporter change
  in all three formats (FreeMind has `<arrowlink>`, OPML has no natural place
  and needs a decision), plus the ring learning a second subject. Nothing
  migrates.
- **Absorb the tree edge into rows.** Cost: a migration of every map, the loss
  of the one property that makes the tree cheap to read, and every one of the
  seventeen `data` fields that currently ride on the child needing a new home.
  Refused.

### 13.3 What the surface offers, and by how many doors

Re-measured with `scratchpad/ui-sweeps/mapaudit.js` on the same twelve-topic
map the ninth run used, plus a route-split pass. **§12.5 has landed since that
audit, and most of its numbers are stale:**

| Surface | Prior (ninth run) | Now | |
| --- | --- | --- | --- |
| Top bar, on screen | 13 | **9** | 3 of the 9 are menu openers |
| Top bar, inside its menus | 47 | **60** | across five menus |
| Tool rail | 16 in 6 sections | **13 in 5** | Move 3, Map 3, Layout 7, Connect 2, Edit 3 |
| Topic strip | 13, box 810x38 | **14, box 959x38** | |
| Node ring | 8 slots, **no label drawn** | **6 slots, each a labelled pill**, 112x28 | the memory test is gone |
| Link ring | 8 slots | **3**: Reverse, Label, Cut | the five that were looks moved to the strip |
| The node's own row | 7 | 7 | |
| Context menu | 8 items, **none reachable on a map node** | **15 items, reachable** through the ring's More | |

So the ninth run's worst finding is fixed and the duplicate list is much
shorter. What the re-measurement found instead:

- **Two menus are built into a map's top bar with no opener on screen.** The
  Insert menu's **8 items** (sticky, text box, image, note card, rectangle,
  circle, arrow, connector) and the Arrange menu are both in the DOM and
  neither opener is among the 9 controls actually on screen. They are not
  reachable and not removed.
- **The rail's most connection-looking control makes the other kind.** The
  Connect section's two buttons, "Straight link (C)" and "Curved link
  (Shift+C)", are the only things on screen with the word Connect on them, and
  both make a **free link**. Nothing on the rail makes a tree edge; the tree
  is Tab, Enter, the ring and the node's `+`. This is where "there are two
  types of connections" is *felt*, as opposed to where it is stored.
- **Still one door only:** everything on the link ring (reverse, label, cut)
  needs a right-click on a line, which nothing on screen advertises; "Add a
  top-level topic", the only route to a second trunk, is the rail's Map
  section alone; "Open every folded branch" and the perspective legend are
  inside the View menu alone.

### 13.4 What can be customised, against what a map tool offers

Read off `MAP_STYLE_FIELDS` and the layout picker, then confirmed on screen.

**A topic, today (11):** colour, bold, italic, text size, alignment, icon,
shape (pill / rect / ellipse), core-idea flag, the spine down its leading
edge, a picture, a link out. **Its line (6):** label, shape (curve / elbow /
straight), dash, thickness, arrowhead, and a dragged waypoint. That is a
serious per-node set and it is not where the complaint is.

**The map as a whole is where it is thin.** Four layouts exist: tree sideways,
tree downward, radial, free. §12.0's own decision list promised eight, naming
"tree right, tree left, both sides (Coggle), org chart down, logic chart,
fishbone, timeline (XMind), radial". **Tree-left and both-sides are missing,
and both-sides is Coggle's signature.** Beyond layout, a map has no theme of
its own (no font choice, no branch palette a person picks, no line-style
default), no per-branch layout override, and no way to set a default for new
topics: every one of the eleven fields above is set one topic at a time, and
"Reset to branch" is the only bulk operation of any kind.

So "customisation is lacking severely" is right about the *map* and wrong
about the *topic*, and a phase that adds more per-node fields answers the
wrong half.

### 13.5 Clean and professional: the same measurements section 17 took

Gutters, rhythm, type scale, and whether the surface uses the app's tokens or
its own values. The token scales were resolved by giving a probe element each
value as a width, because `--space-N` is `calc(0.25rem * var(--density))` and
reading the property text hands back the calc, never a length.

| What | Reading |
| --- | --- |
| Topic card | 200x44 stored; padding 8px / 9.6px, gap 6.4px, radius 8.4px |
| Topic type | 13.6px, line height 18.36px, so 1.35 |
| Ring slot | 112x28, type 13.6px, radius 999px |
| Rail | 624x36, gap 4px, sitting 11.4px above the canvas floor, centred |
| Top bar | 1392x46, padding 4px / 6.4px, radius 14px |
| Rhythm, zoomed to fit | leaf-to-leaf gap 59.6px, depth-to-depth gap 56.7px at both levels read |
| Topic strip | **959.4 x 38**, opening 43.7px above the topic |

**The tokens are not the problem, and that is worth saying plainly**, because
it is the opposite of what section 17 found for the live view. Every padding
and gap read on the map's chrome is on `--space-1..9` (`offScale` empty). The
type is on the scale too: 13.6px is `--text-md`, the workhorse; the rail's
section labels are 11.2px, `--text-xs`. The radii are derived from the user's
own `--radius` of 14px: 8.4px is `--radius-md`, 999px is `--radius-pill`. A
sweep of the stylesheet will not find the problem.

**One number is the problem, and it holds at every width measured.** The topic
strip is 959.4px wide to describe a topic that is 95px wide on screen: **10.1
times the width of its own subject, and 67% of the window at 1440.** It does
not adapt:

| Width | Strip | Fraction of the window |
| --- | --- | --- |
| 1440 | 959.4 x 38 | 0.67 |
| 1024 | **959.4 x 38** (unchanged) | **0.94** |
| 390 | 348.4 x **150** (wrapped to four rows) | 0.89 |

At 1024 a bar of fourteen controls takes 94% of the window every time a topic
is selected; at 390 it becomes a 150px block, 18% of the screen height,
floating 44px above the topic it belongs to. That is the measurable half of
"unclean and unprofessional": the surface is built from the right tokens and
then assembled at the wrong scale. It is also why §12.1's own remaining list
already records the strip covering the handle of the line into the selected
topic: a control that wide has nowhere to go.

### Decisions made

1. **The render is the bug, and it is fixed before anything is designed.**
   No phase below 13a is worth starting, because every one of them would be
   judged through a one-second stall.
2. **The data keeps two kinds of connection; the controls stop having two.**
   `parent_id` stays. What changes is that a map's free link is spoken about
   in the map's own words, gets the map's own ring, and appears in the
   exports.
3. **The strip is sized like its subject.** A control surface for one topic
   does not take two thirds of the window, and it adapts below 1440 rather
   than keeping one width until the phone band wraps it.
4. **Customisation grows at the map level, not at the topic level.** The
   eleven per-topic fields are enough; the missing layouts and the absence of
   any map-wide default are the gap.
5. **Nothing is added to the canvas.** Per standing order 11, any new
   affordance comes from DESIGN.md's recipe index or arrives with its own
   recipe and lint in the same commit.
   *Revised 2026-10-05* (WHITEBOARD_PLAN decision 26, the features audit
   9.5): the board's left sidebar (Library: saved branches and map templates;
   Outline) and the Format panel sit off the canvas, beside it, so this
   decision holds; neither draws on the map.
6. **A cross-link has no colour of its own** (taken 2026-09-21, building
   13c). It is drawn in `--muted`, dashed, whatever the rail's ink well held
   when it was drawn. The alternative was to keep the stored colour and give
   the ring a colour well, which would have let a person paint a cross-link in
   a branch's colour: two kinds of line that can be given each other's look
   are two kinds nobody can tell apart, which is the report this section
   exists for. The colour stays on the row, so an ordinary board still draws
   it and a map turned back into a board gets it back.
   **Revised by the owner 2026-09-23**: "these links I drew using the
   cross-link tools are different from the ones between the other mind map
   nodes ... I want them to be the same". A cross-link between two topics is
   now drawn by the map (`wbMapCrossLinkLook`): the branch's shape, facing
   anchors, weight and taper, in the source branch's colour (the target's
   for a root, the accent failing both). Still no colour of its own, and the
   pen's colour still stays on the row for an ordinary board.
7. **The ring's middle slot promotes a cross-link to a branch** (taken
   2026-09-21, building 13c). The gesture that makes one or the other decides
   from whether the far end is already in the tree, which nothing on screen
   can say in advance without describing the tree; the honest answer is a way
   back afterwards, in the surface that already names both kinds.
8. **A map's theme holds the ten fields that describe how a map draws
   topics, and none of the ones that say which topic this is** (taken
   2026-09-21, building 13e). The question was asked once of each of
   §13.4's eleven: text size, alignment, bold, italic, the box, the bar on
   its edge, and the branch line's shape, thickness, dash and arrowhead are
   how *this map* draws; an icon, the core mark, a picture, a link out, a
   line's label and a line's waypoint are which *this topic* is. A map-wide
   default for the second set would not be a theme: "every topic is a core
   idea with the same picture" is a bug with a settings row in front of it.
   `color` is left out for a third reason, and it is the only one of the
   eleven that is: it is not one value but a rule, seeding a whole subtree,
   and the map-level answer to it is a branch palette, which is drawn twice
   (the canvas from d3, the Library thumbnail from `MAP_BRANCH_PALETTE` on
   the server) and would have to teach the preview cache about itself before
   anybody could pick one. That is its own row below, not a corner of this
   one.
9. **The theme is resolved when a topic is painted, never written onto the
   topics** (taken 2026-09-21, building 13e). A topic's own value always
   wins, and an explicit `false` is a value: so a topic that was decorated by
   hand cannot be changed by a map-wide setting, which is the single property
   that makes the setting safe to press. It also makes theming a 500-topic
   map one request rather than 500, and makes it reversible, since nothing
   was overwritten to reverse. The alternative, stamping the theme onto every
   topic at the moment it is chosen, was refused for both halves of that: it
   is the change that cannot be undone and the one that silently overwrites.
   The cost is that a topic cannot be pulled back to the *app's* own default
   for a field the map themes, only to another named value or to the map's.
   What that cost is **not** allowed to be is a control that visibly does
   nothing: every one of the strip's selects stores the app's default as no
   value at all, so its blank row is named after that default ("Rounded",
   "Line", "M"), and on a themed map choosing it means "follow the map" while
   the row still says "Rounded". So the blank row is relabelled to "As the
   map draws (pill)" while the map themes that field and put back the moment
   it stops, and the three toggles that stored "off" as nothing at all are
   three-state against the theme, which is the rule `edge_arrow` had been
   following alone. The remaining gap is recorded below rather than solved,
   because it needs a stored name for each app default and the case is narrow.
   (Built 2026-10-04 with exactly that stored name per field; see 13e.)
10. **The theme lives in one row of the View menu's Map section, and nothing
   is added to the canvas** (taken 2026-09-21, building 13e). Decision 5
   above, and §13b had just taken the topic strip from fourteen controls to
   five: a theme that arrived as a sixth control on the canvas would undo
   half of the section it belongs to. The row is the menu bar's own recipe,
   beside "Open every folded branch" and "What this map is made of", and it
   opens the recipe index's `.card.modal-card` through `wbInfoDialog`, whose
   body is that index's own two rows, a plain `<select>` for a dropdown of
   values and a `label.setting-check` for an on/off. Measured after:
   top bar 10, rail 0 and strip 0 on a map with nothing selected, unchanged.
   Every control saves as it is changed, the way the View menu's own
   background and grid already do, so there is no OK: a dialog of looks with
   an OK asks what you are agreeing to when what you want is to watch the map
   change behind it.
11. **"Reset to branch" and the map-wide reset are one idea at two scopes,
   not two ideas** (taken 2026-09-21, building 13e). The ring's reset drops
   one topic's own look so that it goes back to following what it inherits;
   with a theme, what a topic inherits is the map, so the same sentence said
   about every topic is the bulk operation §13.4 measured missing. Same list
   of fields (`MAP_CLEARABLE_FIELDS` on the server is `WB_MAP_STYLE_KEYS` in
   the client), same rule about a picture, one endpoint and one transaction
   for the reason `move-many` is one. Two buttons that meant nearly the same
   thing would be two things to learn and one of them would be wrong.
12. **Markdown carries no cross-links, and that is a decision rather than
   the work not being done** (taken 2026-09-21, building 13d). §13.2's table
   asked for a line in the exports and 13d's row said OPML and Markdown
   needed the decision made before the code. FreeMind has `<arrowlink>`, so
   it gets it natively. OPML is strictly a tree with no element for an edge
   that is not containment, so it gets the private-attribute treatment
   `_kind` and `_ref` already have: an `_id` per outline and `_links` on the
   one the link starts at, ignored by every other reader and read back by
   this one. Markdown gets nothing, for the reason `_export_markdown`'s own
   docstring already gives about style: that file's whole promise is an
   outline anybody can paste into anything. A "Cross-links" section after
   the outline would also be read straight back in by
   `_parse_markdown_outline`, which reads indentation and nothing else, so
   one map's two links would return as two topics. Two of three formats is
   the honest answer, and `maptwokinds.js` asserts both halves.
13. **Delete removes the whole branch** (taken 2026-10-03, order 3). The code
   and the server already did, and now that it is one undo step (the
   topics and their cross-links, `wbMapRestoreRows`) there is nothing to
   soften; §12.0's "re-parents children" line is superseded.
14. **Tab adds a topic only when the map was engaged** (taken 2026-10-03).
   Tab on a selected topic added a child from anywhere, so a keyboard user
   could not Tab past the map without Escape first, and the Tab that carried
   focus in added a topic nobody asked for. `wbMapKeysArmed` (whiteboard.js)
   is set by a pointer press on the canvas, by selecting a topic and by any
   map key, and cleared when focus lands on a control outside the canvas.
   Not armed, or focus on another control: Tab is Tab (and so is Shift+Tab).
   The alternative, Tab always walking the topics like a board's items, was
   refused because it takes away the one key every mind map builds with.
   Escape then Tab still leaves from an armed map.
15. **A topic can be a task, and §12.2 item 4 starts there** (taken
   2026-10-04, the competitor pass: MindNode and XMind both put a box on a
   topic and count the done ones up the branch, and a map of a plan is what
   a notebook's maps are for). `data.task` is `open` or `done`, one field so
   "done but not a task" cannot be stored; content, not a look, so the theme
   never sets it and neither reset clears it. Made from the topic's menu
   ("Make this a task", "Stop being a task"), ticked by its box on the topic
   (a real checkbox button, so no new control on the strip, the ring or the
   dock: decision 5 and §12.5's three surfaces stand), counted as quiet text
   after every ancestor's label ("1/2", the success ink at "2/2"). Markdown
   carries it as `- [ ]` / `- [x]`, the one thing a node wears that Markdown
   has a word for (decision 12's reasoning about that file holds: every
   reader draws those as boxes), and reads it back; OPML and FreeMind carry
   `_task`. No key: Space is the hand tool's hold. Priority, progress
   percentages, flags and due dates (the rest of item 4) stay open.
16. **The board's Insert and Arrange menus stay in the markup** (taken
   2026-10-04, §13f's remainder). Read as dead markup on a map; measured, it
   is the board's own: one top bar serves both kinds and a board uses all 20
   of those controls, so removing it from a map means building it per kind,
   a working thing made riskier for no change anybody sees (`hidden` already
   keeps it out of the tab order and the accessibility tree). What was wrong
   was the lookup: the wrap was found from the menu, and an open menu
   escaped to `<body>` is outside its wrap, so a map opened with one open
   drew both toggles. Found from the button now, and the open menu is closed
   and put home (`maptopbar.js`).
17. **Numbering is the map's, by outline place, and off until asked** (taken
   2026-10-04, §12.2 item 7). One switch in the View menu's Map group (the
   menu's own switch row), stored as `numbered` beside `type`, `layout` and
   `theme` in the board's settings and not in the theme: the theme is what a
   topic follows when it says nothing, and a number is not something one
   topic can decline. A root is the map's subject and has none; its children
   are 1, 2, 3 and theirs 1.1, 1.2, counted in sibling order (the canvas's
   `wbMapBySiblingOrder` and the server's `_sibling_key` are one order), and
   drawn as quiet text before the label, never inside it, so a rename never
   edits a number. No trailing dot: `- 2. Write` is an ordered list inside a
   bullet to every Markdown reader. Markdown writes the number after a
   task's box and reads it back only when every topic's number is its own
   place, all or nothing, so "2024 plan" stays a name; OPML carries
   `_number`. FreeMind does not carry it (the setting is a view; its private
   attributes are the topics' own).
18. **A note behind a topic is plain text, a topic's own, and opens in the
   help popover's shell** (taken 2026-10-04, §12.2 item 5's first half).
   `data.note`, up to 10,000 characters, content like `task` (no theme sets
   it, no reset clears it, a copy keeps it). A topic that has one wears a
   note mark (`.wb-map-note`, the link marker's recipe in the label's ink);
   the mark, or the topic menu's "Add a note…" / "Open the note…", opens
   `.help-popover.wb-map-note-peek` anchored to it: one text box, saved when
   it closes (Escape, a press elsewhere, Ctrl+Enter), an emptied note is no
   note, one undo step. Not a new surface and nothing new on the strip, the
   ring or the dock (decision 5, §12.5). Not on a note node: it already has
   the notebook's note behind it, and showing that note's text here,
   editable both ways, is item 5's second half, still open. Markdown writes
   the note as an indented paragraph under its bullet (a reader draws a
   paragraph inside the item; a line that would read as a bullet or a
   heading is escaped with a backslash), and the import reads any text
   indented under a bullet as that topic's note, which is also what a
   paragraph under a hand-written bullet means. OPML carries `_note`, the
   spelling OmniOutliner and Workflowy write; FreeMind a private `_note`,
   because its own `<richcontent TYPE="NOTE">` is HTML this file does not
   read.
19. **A boundary is a branch's, drawn round the topics it holds** (taken
   2026-10-04, §12.2 item 1, under standing order 3; XMind's shape).
   `data.boundary` on the topic whose branch it encloses (`rounded`, `dashed`
   or `cloud`) and `data.boundary_label` (up to 80 characters). Drawn by the
   map's own render pass as one SVG shape under the lines
   (`.wb-map-boundaries`): the box of that topic and of every topic under it
   that is showing, padded by 12, so it grows, folds and moves with them,
   redrawn on every drag frame. Its colour is the branch's (a tint inside, the
   colour on the edge), so the branch colour well is its colour control and
   there is no second one. The label sits above its top edge in the line
   label's recipe. Made, restyled, labelled and removed from the topic menu's
   Branch group. A lasso'd set that is not one branch is not in this decision
   (a run of siblings is what a summary is for). Content, not a look: no theme
   sets it and Reset branch styling keeps it. The image exports draw it as
   drawn; OPML and FreeMind carry `_boundary` and `_boundary_label`; Markdown
   does not (a list has no word for a region).
20. **A summary is words beside a run of siblings, not a topic** (taken
   2026-10-04, §12.2 item 2). `data.summary` (up to 80 characters) and
   `data.summary_span` (1 to 100) on the first topic of the run: the run is
   that topic and the siblings after it in sibling order, `summary_span` in
   all, clipped to the siblings there are, so it survives a reorder and an
   export by place rather than by id. A brace on the run's outer side (away
   from the parent, found from where the run lies, so every layout gets one)
   spans the run's showing branches, and the words sit beyond its tip in the
   line label's recipe one size up. Not a topic: a topic outside the tree is a
   root to every walk of the tree (Tidy, the exports, numbering, the outline)
   and none of the formats this map writes has a word for one. Made from the
   topic menu (one topic) or from the menu of a multi-selection of siblings
   (the run from the first of them to the last); changed and removed from the
   first topic's menu. A root takes none. Content, exported as boundaries are
   (`_summary`, `_summary_span`).
21. **A map presents by branch** (taken 2026-10-05, §12.2 item 9, under
   standing order 3; MindMeister's shape on the board's machinery,
   WHITEBOARD_PLAN decision 16). View, Present branches: the board's full
   screen, bar, keys and Escape, with the steps a map has instead of frames:
   the whole map first, then each trunk's branches in sibling order, each
   fitted with what of it is showing (a folded branch is its topic); a trunk
   with nothing under it is a step of its own when the map has more than
   one. One level deep: a branch's own branches are not steps, which keeps a
   two-hundred-topic map a talk of a dozen steps. No key edits the map while
   it runs.
22. **A FreeMind file's single root node is the central topic** (taken
   2026-10-05, audit FEAT-01, features.md 9.5: the owner's newer words win).
   This reverses the older code decision pinned by
   `test_freemind_imports_with_its_root_as_the_maps_name`, which read the
   root as the map's name and dropped it, so every `.mm` from Freeplane or
   XMind arrived as loose trunks and a map made here lost its centre on the
   way back. The map is named after the root unless `<map _title>` names it;
   the trunk the export invents over a multi-root map carries `_wrapper` and
   is taken off again. OPML, FreeMind and Markdown each round-trip a
   101-topic map made here, every topic, edge, the centre and the name
   (`test_a_101_topic_map_made_here_round_trips_losslessly`).
23. **A map made from text starts in tree-right and is tidied once as it
   opens** (taken 2026-10-05, audit FEAT-05). The import and the accepted AI
   proposal took the board default, Free, while every other map door starts
   in tree-right (`DEFAULT_MAP_LAYOUT`); `wbMapTidyFresh` lays it out once,
   with no undo entry, when the import or proposal opens.
24. **A new topic is drawn and open for typing before the server answers**
   (taken 2026-10-05, audit FEAT-02). Tab and Enter make a provisional row
   (negative id), lay the branch out by the tidy's positions applied as
   transforms, render once, open the editor, and adopt the server's id in
   the background (`wbMapAdoptProvisional`): the row, its element, the
   selection and both Undo stacks take the real id; a save that reaches the
   row first waits for it (`wbSaveObject`); a save's answer no longer takes
   back a position or a text changed while it was out. A render repaints
   what changed and moves what only moved (the paint key has no x or y).
   Three stylesheet rules whose `:has()` sat before a classless compound
   made every DOM insertion restyle the whole page; they are rewritten and
   `tests/test_has_invalidation.py` holds the line. Second pass, the same
   day (HISTORY, "Moved from the plans, 2026-10-05 (the add path, second
   pass)"): the editor opens in the add's own task, before the moved
   topics' transforms and the lines are written (`wbRenderHold`), the
   measure reads only what was repainted, the mid-line `+` buttons and the
   edge handles are kept rather than rebuilt, the selection bar is placed
   two frames on, and a `:has()` keyed on `.ph` (every icon) is rewritten
   with a ratchet against its kind. The render of one add is 21 to 63ms at
   301 topics against 118 to 421 before; the 100ms key-to-editable gate is
   still not met on this sandbox under a load of 7 to 10 (medians 177 to
   276ms against 265 to 351 for the base scripts on the same runs), and is
   to be measured on a quiet machine.
25. **The open map's commands are palette rows** (taken 2026-10-05, audit
   FEAT-11): add, rename, fold, focus, delete, tidy, open every branch,
   look, numbering, statistics, present, zoom to fit, the six layouts and
   the three text exports, in groups "This topic", "This map", "Map
   layout" and "Export the map", only while a map is on screen. The
   board's own commands are the board's (WHITEBOARD_PLAN, section 8's one
   command table).
26. **A new topic and its first name are one Undo step** (taken 2026-10-05,
   audit FEAT-15), as in XMind: the rename is folded while the add is still
   the last step.
27. **A committed name hands the keys back to the canvas and is said aloud**
   (taken 2026-10-05, audit FEAT-16), unless the press that ended it went to
   another field.
28. **No front-and-back Order on a laid-out map** (taken 2026-10-05, audit
   FEAT-17): a tidied tree never overlaps; a Free map keeps the group.
29. **Text pasted onto a map is a branch** (taken 2026-10-05, audit FEAT-09):
   one topic per line, nested by indentation, a numbered or heading line
   read as a topic, under the selected topic (or as trunks), made by
   `POST /boards/{id}/nodes/outline` in one transaction and recorded as one
   Undo step. Ctrl+V on a map with nothing copied on the board lets the
   browser's paste through to it; an in-app copy still pastes as before.
30. **The dashboard draws a map at its own shape** (taken 2026-10-05, INBOX
   553(d), the owner's decision): the Boards & maps widget's busiest board
   at the widget's width and its natural height, at least 96px, at most
   168px for six topics or fewer and 320px otherwise, then fitted whole;
   the rest as rows. DESIGN.md's recipe row names the numbers.
31. **A map writes itself as a document, one way first** (taken 2026-10-05,
   the audit's brief M5, first half): the board menu's Write as a document
   and the palette row make a new document titled after the central topic
   (or the map, with several trunks), branches as `##`, theirs as `###`,
   deeper topics as nested lists, notes as paragraphs, and the map's card
   (`boardEmbedMarkdown`) at its head as the way back. The other direction
   is decision 35.
32. **A concept map's topics are notes that stay on their map** (taken
   2026-10-05, audit UX-06). A note made by a map gesture (a new concept
   map's root, a card Tab or Enter adds) carries `map_topic`; Notes (All,
   the categories, Favourites, Untagged) and Recently added leave it out,
   and a search in Notes, Ctrl+K and Ask still find it. Old maps' topics
   are marked by the upgrade (a short note placed on a board within ten
   seconds of being written). The board picker counts a map's topics and a
   board's items (not the links between them) and is kept current from the
   board on screen; the Library and dashboard say "links" and "drawings",
   never "sketches". After Enter names a card, a letter renames it (the
   focus is not moved to the canvas, where Tab walks items).
33. **A map's outline is a panel of fields in the tree's order** (taken
   2026-10-05, §12.2 item 8, the audit's M3). View, Outline (and the
   palette's row) opens it in the board sidebar's place (`#wb-map-outline`,
   the `.whiteboard-sidebar` shell, one of the two at a time), on maps only,
   remembered per device. One text field per topic, indented by depth; the
   keys are an outliner's: Enter adds a topic after this one and types it in
   the outline (not on the canvas), Tab makes it the last child of the topic
   above, Shift+Tab puts it right after its old parent, Backspace on an
   empty topic with no branch removes it, the arrows walk the rows, Escape
   hands the keys to the canvas. Every change goes through the canvas's own
   functions (the add, `wbMapTransplant`, `wbMapOutdent`, the rename's save
   and its FEAT-15 fold), so Undo and the tidy are the canvas's. Typing
   draws the label on the canvas as it goes, without a render; the name is
   saved when the row is left. The outline follows every render, rebuilt only
   when the tree's shape changed, never taking the field being typed in.
34. **A topic's markers are content, from one icon set** (taken 2026-10-05,
   §12.2 item 4, the audit's M4). `data.priority` (1 to 5), `data.progress`
   (0 to 100; the menu offers None, 0, 25, 50, 75 and Done), `data.flag` and
   `data.markers` (up to six names from `WB_MAP_MARKER_ICONS`, twelve glyphs
   of the vendored Phosphor font; never emoji, which each system draws its
   own way and an export does not draw at all). Drawn in one row before the
   label, set in one popover from the topic's menu (Content, Markers) and
   the palette, each press one Undo step. Content, not a look: a look reset
   and a branch copy keep them; OPML and FreeMind carry them as private
   `_priority`, `_progress`, `_flag` and `_markers` (a comma list), Markdown
   not at all (decision 12's rule). View, Filter by marker lists the markers
   in use with their counts and dims (never hides) every topic without the
   chosen one, for this visit, with a bar in the focus bar's shell to end
   it. Not built: due dates, tags, several filters at once, markers as the
   outline's columns.
35. **A document maps its own headings, one way** (taken 2026-10-05, the
   audit's M5 second half). The document's menu, Map the headings (and the
   palette's row) makes a new map through the Markdown import, so it opens
   in tree-right and tidied (decision 23). The headings are read by
   `wbMapHeadingsOutline` (node-tested): a heading inside a fenced code
   block is code; one top-level heading, first, is the central topic,
   otherwise the document's title is and every top-level heading a branch;
   a skipped level hangs one level down, never two. The way back is a
   document topic under the centre pointing at the document (it opens it, as
   any document topic does), so it travels with the map into every export
   that keeps references. A twin kept in step both ways is the audit's idea,
   not built.
36. **Studying a map is presenting with each branch hidden until recalled**
   (taken 2026-10-05, §12.3 item 5, under standing order 3; op5). The board
   menu's Study the map (maps only; the View menu is at its 450px ceiling)
   and the palette's row start the presenting shell (decision 21's bar,
   keys and Escape). The questions are the trunks' branches that have
   topics under them, in Present branches' order; everything under each is
   hidden as a view, like focus (`wbMapConcealed`), never folded or
   written. Show (or Enter) draws the answer; Knew it or Not yet marks it
   and moves on; the end says how many were recalled. The marks are kept
   per map on this device (`wbStudy:<id>` in local storage: a study record
   is the person's, not the map's), and a branch missed last time says so
   in its step. Not built: a note behind the topic as the answer (the
   plan's "the note's own text"), a spaced order.
37. **A topic's due date is a day, a marker, and a reminder only when asked**
   (taken 2026-10-05, §12.2 item 4, under standing order 3; op5).
   `data.due` is a calendar day (`YYYY-MM-DD`, no time: a topic is due on a
   day wherever the map is opened), content like decision 34's markers (a
   look reset keeps it; OPML and FreeMind carry `_due`; Markdown does not).
   Set in the Markers popover's Due row (the browser's date field, Clear),
   drawn in the marker row as words ("14 Mar") in the ink, a day gone in the
   error ink and read "was due"; View, Filter by marker lists "With a due
   date". Remind me makes an ordinary reminder at 9:00 that day; a day gone
   makes none and says why. No reminder is made by setting a date. Tags on a
   topic stay open.

### Phases, each with the gate it is finished against

- ~~**13a. The render pass.** Make `renderWhiteboard` proportional to what
  changed rather than to what exists: the drag path must not rebuild every
  node to pick one up.~~ **The drag half is built, 2026-09-21**, and the
  record is in HISTORY.md ("Moved from the plans, 2026-09-21", "From
  MINDMAP_PLAN section 13a: the drag pick-up"). Worst drag frame on
  `mapperf.js`: 83.3 to **16.8ms** at 50, 416.6 to **33.3ms** at 200, 1,650.0
  to **66.8ms** at 500, under the 100ms the gate asked for, with the pan
  medians still 16.7ms at all three sizes and nothing worse at 50 than at 500.
  `tests/test_map_drag_cost.py` holds the nine shapes the profile found.
  **What is left of 13a is the open, and it is now its own row**: the drag
  pass carried `renderWhiteboard` from 1,279.2 to 543.0ms and open-to-painted
  from 3,443.3 to 2,049.1ms at 500 topics, because the render and the layout
  read the same topic boxes this pass stopped re-measuring, but the gate's
  other two figures (render under 200ms, open under 1s) are not met and will
  not be met by caching: `renderWhiteboard` is still a full d3 data-join over
  every node on the board, and making it proportional to what changed is a
  separate piece of work.
- (Audit 2026-10-05: 13a-open's figures hold for a move; the add path was
  never gated and cost two whole renders, see decision 24.)
- ~~**13a-open. The render pass proper.**~~ **Built 2026-09-21**, and the
  record is in HISTORY.md ("Moved from the plans, 2026-09-21", "From
  MINDMAP_PLAN.md section 13a-open: the render pass"). Both gate figures are
  met at 500 topics: `renderWhiteboard` 534.7 to **47.8ms** after one topic
  moves and **149.1ms** with every topic changed at once, against the 200ms
  asked for, and open-to-painted 2,022.3 to **965.6ms** against the 1s asked
  for.
  The drag and pan figures are no worse. **What the row also predicted is not
  built and is now 13a-view below**: drawing only what is on screen. The open
  turned out not to need it.
- ~~**13a-view. Draw the topics that are on screen.**~~ **Built 2026-09-23**,
  and the record is in HISTORY.md ("Moved from the plans, 2026-09-23", "From
  MINDMAP_PLAN.md section 13a-view"). The worst pan frame at 500 topics
  **166.6 to 16.8ms** and the zoom 33.3 (gate 50): it was a whole-board
  restyle on press and release, not rasterising. Off-screen items are culled,
  and a dragged branch's lines no longer trail it by a frame (77 of 81 frames
  up to 12px behind, now 0, `mapedgelag.js`).

- **13g. The middle-button pan on the owner's own machine.** He reports, with
  13.1's own gesture: "the whiteboard and mindmap goes haywire and moves to
  the left when I try to move around by pushing down my mouse scroll wheel
  and moving the mouse to the edges of the screen, no matter which
  direction." **Not reproduced here**, and the two things that would explain
  it were each tested: `mapmidpan.js` drives a real middle-button drag in all
  four directions at 50 and 500 topics and the board goes the way the hand
  goes every time, and a pan whose release never arrives (window blurred
  mid-gesture) leaves the board still rather than following the pointer.
  What cannot be tested here is the remaining explanation and the likeliest
  one: **Chromium's middle-button autoscroll is a windowed-browser
  behaviour**, a headless run has none, so the `mousedown` guard that exists
  for it (INBOX 183, reasoned and never observed) is not exercised by any
  gate in this repository. Gate: this needs the owner, not a sweep. What to
  ask him for is which platform and whether the four-way autoscroll cursor
  appears when he presses the wheel; if it does, the guard is not reaching
  the event on his machine and the next thing to read is whether
  `#library-view-whiteboard` is really an ancestor of what he pressed on.
- ~~**13b. The strip is sized like a topic.**~~ **Built 2026-09-21**, and the
  record is in HISTORY.md ("Moved from the plans, 2026-09-21", "From
  MINDMAP_PLAN.md section 13b: the topic strip is sized like a topic"). The
  fourteen controls are behind three named doors, Text, Shape and Branch line,
  each the board menu bar's own recipe; the strip is **314 x 38** at 1440,
  1024 and 820 (0.22, 0.31 and 0.38 of the window, against a gate of a half)
  and 314 x 54 at 390, against 959.4 x 38 and 348.4 x 150 before. `mapstrip.js`
  39/39, `mapnarrow.js` 3/3, and `mapline.js`, `mapcore.js` (removed 2026-10-12, recoverable from git history) and `mapspine.js`
  untouched at 13/13, 16/16 and 9/9. ~~**What is left of 13b**: whether the
  strip still covers the handle of the line into its own topic~~ **measured
  and fixed 2026-10-04**, recorded in HISTORY.md ("Moved from the plans,
  2026-10-04 (the map's palette, font and the app's own default)"): 4 of 48
  handles covered at 1440, 0 of 192 at 1440, 1024, 820 and 390
  (`mapstripcover.js`).
- ~~**13c. One vocabulary for two connections.**~~ **Built 2026-09-21**, and
  the record is in HISTORY.md ("Moved from the plans, 2026-09-21", "From
  MINDMAP_PLAN.md section 13c: one vocabulary for two connections"). Both
  kinds get the same ring, which names the kind it is on; the board's context
  bar never appears for a cross-link on a map; the rail says cross-link on a
  map and link on a board; a cross-link draws in the map's own ink, dashed,
  whatever the pen held, and is told it is one before it is first drawn rather
  than at the next reload. `maptwokinds.js` 10 checks to 16, **16/16**, six of
  which fail on the base branch. ~~A right-click on a selected cross-link's
  bend grip did nothing~~: **built 2026-09-26**, the grips (bend and both
  ends) hand the press to the link's own hit stroke
  (`wbForwardGripContextMenu`), so the grip opens the same ring as the line;
  `maptwokinds.js` 18/18, the new check failing on base. The in-flight cue
  (which kind a connect drag will make, before it lands) is built
  2026-10-04 (HISTORY.md, "Moved from the plans, 2026-10-04").
- ~~**13d. A free link survives an export.**~~ **Built 2026-09-21**, and the
  record is in HISTORY.md ("Moved from the plans, 2026-09-21", "From
  MINDMAP_PLAN.md section 13d: a cross-link survives an export"). FreeMind
  carries it in its own `<arrowlink DESTINATION>` under the node the link
  starts at, with an `ID` on every node; OPML carries it in a private `_id`
  and `_links`, the bargain `_kind` and `_ref` already struck there; Markdown
  carries it in neither, by decision 12. Both XML formats round-trip
  (`test_a_cross_link_round_trips_through_freemind`, `..._through_opml`), a
  link whose far end is not in the file is dropped rather than left dangling,
  and a map with no cross-links exports byte-for-byte the file it did.
  `maptwokinds.js` 16 checks to 17, **17/17**, with the export check inverted
  as the gate asked.
- **13e. The map's own customisation.** ~~Tree-left and both-sides, the two
  §12.0 promised and Coggle is known for~~ **built 2026-09-21**, recorded in
  HISTORY.md ("Moved from the plans, 2026-09-21", "From MINDMAP_PLAN.md
  section 13e: the two layouts the plan promised"): both in the picker, in
  `BOARD_LAYOUTS` and in the tidy, 0 overlapping pairs at 12 and 200 topics
  in all five layouts, 5/6 and 93/106 either side of the trunk, `maptidy.js`
  5/5 at 1440 and 390, `maplayouts.js` new at 19/19 (5 failing on base).
  ~~**What is left of 13e is the other half: a map-level default for new
  topics.**~~ **Built 2026-09-21**, and the record is in HISTORY.md ("Moved
  from the plans, 2026-09-21", "From MINDMAP_PLAN.md section 13e: the map's
  own look"). A map now has a theme of ten of the eleven fields, resolved
  when a topic is painted so that a topic which was never told otherwise
  follows it and one that was keeps exactly what it was given; and "bring
  every topic back to the map" is the map-scope of the ring's own reset.
  `maptheme.js`, new, 24/24 in light at 1440, in dark at 1440 and at 390,
  against a base branch on which it stops at its second check
  (`wbMapTheme is not defined`). One request themes 25 topics; one request
  clears them. ~~**What is left of 13e**: the branch palette, the font and
  decision 9's narrow case~~ **built 2026-10-04**, recorded in HISTORY.md
  ("Moved from the plans, 2026-10-04 (the map's palette, font and the app's
  own default)"): one palette list on the server read by canvas and
  thumbnail, a map font, and a pin per themed select; `mappalette.js` (removed 2026-10-12, recoverable from git history) 13/13
  in light, dark and 390. 13e is closed.
- ~~**13f. The doors that are built and shut.**~~ **Withdrawn 2026-09-21, and
  a different thing built in its place**, recorded in HISTORY.md ("Moved from
  the plans, 2026-09-21", "the two gestures a blank map did not answer").
  Re-measured: `wbSyncMapChrome` sets `hidden` on the Insert and Arrange wraps
  on a map, and that takes the menu inside the wrap with it, so their 8 and 10
  controls are neither drawn nor exposed to a screen reader. Dead markup on a
  map, not a shut door. What the counting *did* find is that a map's canvas
  answered neither of the two gestures anybody tries on a blank part of it: a
  right-click opened nothing and a double-click added nothing. Both now do,
  and `mapdoors.js` (7/7, 3/7 on base, in the gate's sweep list) holds them
  plus the door count and the naming rule. The Insert and Arrange markup
  stays (decision 16; HISTORY.md, "Moved from the plans, 2026-10-04").

### Not verified, and to be taken first by whoever opens this

- ~~**The owner's own map size is unknown**~~ Moot: 13a is built and met its
  gate at 500 topics (HISTORY.md, "Moved from the plans, 2026-10-05 (docs
  hygiene before 0.4.0: MINDMAP_PLAN)").
- **Dark and 820 wide are read, and what they found is fixed** (HISTORY.md, "Moved from the plans, 2026-10-18 (left-1018)").
- The timings are one machine, one Chromium, one run each except the 500-node
  row, which was run twice (1,583.3ms and 1,616.5ms worst drag frame). They
  are a shape, not a benchmark.
- **The strip is measured at 1440, 1024, 820 and 390.** `boot()` defaults to
  1440 but takes `opts.viewport`, so other widths were reached by passing it;
  820 is read in the bullets above.
- The free link was created through `/whiteboard/sketches` with the fields the
  connect drag writes, not by driving the drag itself. The row is the same
  shape; the drag's own hit-testing is not exercised.
- **Nothing here reproduces the owner's phrase "awkward to use".** The counts
  say where the controls are, not what it feels like to reach for one. 13b and
  13c are the two that can be judged by measurement; whether they are what he
  meant is a question, not a finding.

## Placed from INBOX, 2026-09-09

24 built; moved to HISTORY.md ("Moved from the plans, 2026-10-04 (the map's
palette, font and the app's own default)", "the placed items of 2026-09-09").

## Placed from INBOX, 2026-09-09 (the owner's evening batch)

The All list's kind test and the dock's wrap are built; moved to the same
HISTORY.md record.
The dashboard widget's tall-map sliver is built (decision 30, `d873a3f`);
moved to HISTORY.md with §12.1 (op5).

## Placed from INBOX, 2026-09-13

177 (part): every item built; moved whole to HISTORY.md ("Moved from the
plans, 2026-10-05 (placed blocks found built, op5)").

## Placed from INBOX, 2026-09-21

305. **The owner, 2026-09-21, verbatim:** "the mindmap needs A LOT of
    improving. Tools and utilities are really awkward to use and dont show
    themselves how id expect, there are two types of connections, it is
    really confusing to access and use features and utilities, they are hard
    to find and figure out how to use, they are unintuitive, the ui needs
    improving, the mindmap is slow, the customisation features are lacking
    severely and it just feels really unclean and unprofessional."
    Plan-sized, and it names a structural problem rather than a list of bugs:
    "there are two types of connections" is the tree edge derived from
    `parent_id` sitting beside the free link, which this session added
    waypoints to tonight. Belongs in MINDMAP_PLAN as a measured read plus
    gated phases, in the shape DOCUMENTS_PLAN section 17 uses. "Slow" is the
    one claim that must be measured before anything is designed.
    **Placed 2026-09-21 into MINDMAP_PLAN section 13**, which carries the
    measured read, the decisions and the gated phases.

## Placed from INBOX, 2026-10-03 (445 (2) audit, found not fixed)

Built; moved whole to HISTORY.md ("Moved from the plans, 2026-10-03", "From MINDMAP_PLAN.md: the second audit's open items"). Its two decisions are 13 and 14 above.

## Placed from INBOX, 2026-10-05

431. **The owner, 2026-09-27 after the reset, verbatim.** "I think notes
     appear in the command palate search / Also is there a way to customise
     the colour the fill of mind map nodes?? Also for the mindmap export to
     customise the colour of the background / Or just to be able to customise
     the mind map background colour in general / Also can there be some more
     animations and states of the companions?? Like lying down and sleeping or
     doing other things like reading, sitting on a beanbag, pulling out a
     chair and sitting on it, face palming, other gestures and props etc. But
     focus on the smooth transitions and movement adjustment transitions and
     other similar organic movement as that is the current worst thing. Maybe
     also giving like the hair, tails, nebular streams some flow and swaying
     or smth to make the atlas characters really attractive, well designed,
     well animated and more. The female atlas main body could potentially
     have a bit more of a femine chest but don't overdo it just really
     subtle. Round out polish and finish the whole companion and avatar
     feature. Polish the testing tool html pages for them as well. Then make
     sure it is all optimised and cheap to run and everything is togglable in
     settings. And continue. Polish the app, devibecode it. Fix bugs. Fix
     ui/ux learnability, utility, accessibility, usability and information
     architecture"
     Placed: ~~(a) palette notes (verify: notes should appear; if not, bug)
     and (b) mind map node fill, canvas and export background colour: one
     Sonnet agent~~ **done 2026-09-27**: both already existed and worked
     (verified live in Chromium against a real palette search and a real
     mind map), no feature code changed; regression tests added
     (`tests/test_palette_contract.py`, `tests/test_export_paint.py`).
     Left, from the same report: (b)'s discoverability (the owner asked
     without knowing they exist, so the controls need better labels/help,
     placed below as its own item) and companion motion. (c) companion
     motion first (transitions, glide, secondary motion on hair, tails and
     nebula), then new states and props, the subtle feminine chest, the
     test pages, per-feature toggles, cost: the two Opus agents on atlas.js
     and avatars.js; (d) the devibecode programme, WORLD_CLASS_PLAN 22.4,
     after.
     Addenda the same afternoon, verbatim where quoted, all placed with the
     two companion agents: the top-bar peek; locomotion by distance (walk,
     hop or fly near, portal far: "It is a companion, not a fake soulless
     construct"); a smoother bust; a slight body tilt left or right; the
     sleepy face in both looks, "z" emotes and a night cap; close-range
     pointer following; hover and click reactions that ease in and decay
     ("more natural and gradual, unless it is startled"); boredom
     wandering; lying down to sleep and masculine and feminine body
     language; rotating per-persona thinking words beside the typing dots
     (the Sonnet agent, lists written by the orchestrator).
     (e) Categories: "there needs to be a better, easier and more accessible
     and learnable way to edit categories like with merging them, splitting
     them, moving notes between them etc. accessible from the notes tab, and
     settings. maybe an access menu or panel cna be used from the your notes
     subtab and/or sidebar??" Exists today: rename (onto an existing name it
     merges) and delete, from the sidebar menu (`renameCategory`,
     routes_categories.py PUT/DELETE). Missing: an explicit merge, a split,
     moving notes between categories, and one place to do all of it.
     Recommendation, taken: one "Manage categories" panel (the sheet recipe),
     opened from the sidebar head, each category's menu and Settings; a
     row per category with count, rename, merge into, split (pick notes or
     let the AI propose), delete with a destination; notes dragged or
     multi-selected across; every action undoable. Next free Opus slot.
     The owner, straight after: "I should say manually edit. the user needs
     to be able to easily do anything the ai can do". So the panel is part
     of a parity rule: every write tool the agent has (WRITE_TOOLS and
     tools/categories.py: create, rename, merge and delete category; create,
     edit, tag, pin, link, unlink, delete and restore note; reminders; rename
     and delete tag; documents; whiteboard cards and links; mind map nodes)
     gets an audited, discoverable manual path, each gap fixed, and a lint
     that fails when a new write tool has no named UI entry point.
     **Built 2026-09-27** (e): the Manage categories panel and routes
     (create, merge, split, proposed split, move, delete into), and the
     parity lint, `tests/test_manual_parity.py`, naming the manual path of
     every write tool. Left: the proposed split groups by tags; an AI
     proposal would need the model.
     (f) The owner, with a screenshot of the Documents AI assistant dialog:
     "I actually reallly like the design of the document editor's ai
     assistant popup panel. especially with the design of the close,
     history,a nd tooltip buttons. idm the edit/write/remove pill either.
     the suggest an edit button is fine to." Placed: DESIGN.md's recipe
     index now names it the reference dialog head; every modal and popup
     head is brought to it, with a ratchet lint (the Sonnet agent, after
     the thinking words).
     (g) The owner: "remake and retake the screenshots for the readme file,
     update the atlas section with a short intro, title, headline and short
     description and accompanying image with an expression or mood. take the
     screenshots in dark mode but maybe have a dark/light comparison image.
     make the graph really visually pleasing and impressive with a mix of
     connected and non connected, some clusters some webs, some connections
     ahve reasons and others dont etc. make sure all main features are
     properly shown. and polish and update the rest of the the readme as
     well." Placed: after the Atlas and companion passes land (so the shots
     show the finished art), the first agent to free takes it: a seeded
     showcase data dir (clusters, webs, loose notes, reasoned and plain
     links), dark shots of every main feature, one dark/light split, the
     Atlas section rewritten, README polished; test_readme_freshness green.
     **Addendum, the owner, 2026-09-28 (Windows, granite4.1:3b), verbatim.**
     "No gap below the 'use nomic-embed-text' button. Colour contrast issues
     on the plan and web polls when active on the chat interface. Depending
     on what the companion is perched on or anchored to at a given time it
     might have different z-indexes so like if it is perched on like a chat
     message bubble or a library card, when it scrolls with them it should
     probably go behind the top bar like the thing it is perched on not in
     front of it. If say it is stitting on or perched on an element like the
     top bar, then it would be in front yk?? It's still really confusing to
     use the built in embedding model because half the time I can't tell if
     it is working or how well... also the fit drag mini fit map on the
     whiteboard and mindmap is reallllly glitchy and laggy. The Popup agent
     has been unable to answer multiple prompts as well and it's really
     worrying. The whole process of filing, creating, editing, refining,
     managing, tagging, recategorising notes and more anywhere, especially in
     the main sections needs to be wayyy more fast, intuitive, guided,
     assisted, automated, easy manually, and smooth to use." And: "there have
     obviously been a lot of bugs that have been missed if something as big
     as filing a note was very broken so I'm worried."
     Same day, also open: the graph's default layout "looks messy and is
     distributed wierdly"; the slash menu's Link card and Web link render the
     same on a line of their own (a lone link is a card, CHAT_PLAN decision
     12; recommendation: Web link on an empty line inserts inline syntax the
     card rule skips, owner to confirm); a toggle in the note edit form's
     preview reportedly exits preview (not reproduced in Chromium, capture's
     half fixed in 31d5460).
     Done the same day (commits 3d493ac to 2b721bd): capture preview and
     gutter, spinner under reduced motion, one-tab picker strip, unread-dot
     gap, popup agent "(no answer)" reasons and waiting line, Ask waiting
     line, 499 for abandoned requests, greeting name once, one nudge on an
     empty agent round, built-in engine applies on selection, Chat and agent
     read the app's help for how-to questions, popup user mark, companion
     hide sweep, web reader on site-builder pages.
     **2026-10-03 (INBOX 432, PR 162):** (1) to (7) all done; (5) the
     companion goes under the bar its perch scrolls under
     (`tests/test_companion_stacking.py`, `companionstack.js`: 62px over the
     bar to 0, 103px at Large to 0).
     Placed, in this order: (1) **a real-model pass before more features**:
     `scratchpad/llama-dev.sh serve` with a 3B model, then the popup agent's
     two failing prompts, filing a new note, and `pytest -m evals`, because
     every failure reported today passed a fake-transport suite; (2) the
     note flow as one brief (WORLD_CLASS_PLAN, notes dossier): filing,
     re-filing, tagging and editing measured end to end in the running app
     with the model; (3) built-in engine status in words (ready, indexing N
     of M, last query semantic or keyword); (4) minimap drag performance
     (whiteboard and mind map, measured frame times); (5) companion stacking
     by perch; (6) graph default forces; (7) the two small visual ones
     (button gap, Plan/Web pill contrast) with contrast.js.

## The features audit's Phase G, what is left (placed 2026-10-05, op3-1005)

From `scratchpad/audit1005/features.md` section 10 and Phase G, open since
FEAT-13's first part (HISTORY.md, "Step 6"). Built so far: Branches from my
notes (decision 36 in WHITEBOARD_PLAN) and Summarise this branch (HISTORY.md,
"Moved from the plans, 2026-10-05 (op3-1005)"). Open, each with the fake
transport for its tests and the no-model fallback measured in a sweep:

- ~~**Ghost topics on the canvas**~~ built 2026-10-18 (HISTORY.md, "Moved from the plans, 2026-10-18 (fixes7-1018)").
- ~~**Expand from my notes**~~ built 2026-10-18 (HISTORY.md, "Moved from the
  plans, 2026-10-18 (mindmap-1018)").
- **The affinity sort** (a board, WHITEBOARD_PLAN's territory): thirty
  stickies grouped into named frames by theme, each placement shown with the
  notes that back it, accepted per frame, one Undo step.
- **The claim check** (DOCUMENTS_PLAN's territory): a document's sentences
  checked against the notebook, each marked supported, contradicted or not
  found, with the note.


## 14. Core nodes, levels and the icon library (INBOX 641, 642; mc1, 2026-10-05)

The owner, 2026-10-05: "I'm still not happy on the mindmap with how the core
nodes work and can be customised as well as with the icons in them", and "an
emoji and icon widget library which can be dragged and placed in the
whiteboard and mindmap and which are also available in text editors and
formatting toolbars". Read against Coggle, XMind, Miro, Illustrator and
Photoshop.

### 14.1 Measured before anything was designed

Moved to HISTORY.md ("Moved from the plans, 2026-10-05 (MINDMAP_PLAN §14, mc1)"), with the build record: the centre, a branch and a leaf drew identically (13.6px, 400, 31px).

### 14.2 What the five apps do, and what is taken

| App | What it does | Taken as |
| --- | --- | --- |
| XMind | A theme styles Central topic, Main topic and Subtopic separately; floating topics have their own | Levels (decision 38) and the hierarchy presets (decision 39) |
| Coggle | The centre is a large bold card; branches are thick tapered lines; deeper topics are text on the line | The Outline preset; main branches thick by default |
| Illustrator | Graphic styles: a named look, linked, "Redefine graphic style" updates every object wearing it; Symbols dragged from a panel; the eyedropper copies appearance | Level styles are linked looks; "Use this look for its level" is Redefine (decision 41); stickers (decision 44) |
| Photoshop | Copy and Paste layer style; the Glyphs panel: search, recent, insert into text | Copy and paste a topic's style (decision 42); the picker's search and Recent row (decision 43) |
| Miro | Copy style and Paste style (Ctrl+Alt+C, V); an icon and emoji panel dragged onto the board; reactions | Paste style reaches topics; drag from the picker onto the canvas |

Not taken now, kept open under INBOX 641: Illustrator's linked symbol
instances (edit one, every placed copy follows), Photoshop's layer effects
(shadow, glow, stroke per topic), Miro's reaction stamps and voting, and the
whiteboard half of 641's research (beyond stickers).

### 14.3 Decisions made (do not remake)

38. **A topic draws as its level unless told otherwise** (taken 2026-10-05,
    mc1). Three levels: 0 is the centre (a root with topics under it, or the
    only topic on the map), 1 the main branches (its children), 2 every
    topic deeper, and a free root with nothing under it (a floating topic,
    XMind's own fourth style, drawn as a sub-topic). The level is worked out
    in the render's one walk of the tree (`wbMapLevels`) and painted as
    `data-level`, never stored on a topic: dragging a branch to another
    parent changes its look with its place, which is what a level means.
39. **The hierarchy is a named preset on the theme, resolved at paint**
    (decision 9's rule, extended). `theme.hierarchy` names one of four:
    Classic (the default, stored as no value: centre 22px bold on a pill
    filled in the accent, main branches 17px bold with a tinted card and a
    thick line), Outline (Coggle: the centre as Classic, everything else
    plain text on its line), Boxed (XMind: a filled box per level) and Flat
    (every topic as before this section, for a person who wants that). Every
    map made before this draws Classic, since the owner asked for a
    hierarchy by default; Flat is one choice away and one Undo back.
40. **A level's own look overrides its preset, and a topic's own look
    overrides both** (taken 2026-10-05). `theme.levels` holds up to seven
    fields per level (text size, bold, italic, box shape, edge bar, fill,
    line thickness), sent and stored whole, so Undo puts the whole set back.
    The order a field is read in: the topic's own value, its level's,
    its preset's, the map-wide theme's, the app's. The map-wide theme stays
    what it was (decision 8's ten fields), now underneath the levels: setting
    every topic's size map-wide no longer flattens the centre.
41. **"Use this look for its level" is Illustrator's Redefine** (taken
    2026-10-05). On a topic's menu: the topic's own looks (the level fields)
    are written into its level's style and dropped from the topic, one
    request for the theme and one per changed topic, one Undo step, so every
    topic at that level that was never told otherwise follows. "Reset to
    branch" stays the way back for one topic.
42. **Copy style and Paste style reach topics** (taken 2026-10-05). Ctrl+Alt+C
    on a topic copies its look (`WB_MAP_STYLE_KEYS` less `link`, the line's
    label and its waypoint: what a topic *is* never travels); Ctrl+Alt+V
    pastes onto every selected topic, one Undo step. A topic's style pasted
    on a shape, or a shape's on a topic, is refused out loud as before.
43. **One icon and emoji picker, one lazy module** (taken 2026-10-05).
    `icon-picker.js` and its stylesheet, fetched on first use by
    `pickIconOrEmoji` (editor.js: app.js is at its gzip ratchet), never a
    second grid: a `.help-popover.icon-picker`
    placed by `placeHelpPopover`, a search field, Emoji and Icons as a `.seg`,
    a Recent row first (this device, twenty), category heads, and one
    `role="listbox"` grid of `role="option"` tiles (arrows move, Enter
    picks, Escape closes and gives focus back). Icons are the vendored
    Phosphor names read off its own stylesheet (no list to keep in step);
    emoji are a curated set of about 470 in nine groups with their
    Unicode names, written as escapes like `DOC_EMOJI_SOURCE`. Nothing is
    fetched. Every tile is draggable, carrying its glyph as text (so a drop
    into any text box inserts it) and as `application/x-memorymap-icon`.
44. **A dropped icon is a sticker; dropped on a topic it is that topic's
    icon** (taken 2026-10-05). On a board or a map's empty canvas: an emoji
    becomes a text object with `sticker: true` (no card, the glyph sized to
    its box, resized as any object is); a Phosphor icon is the Library's own
    vector icon (`wbLibIconEntry`, placed through `/place`, so it recolours
    and exports as a shape). Dropped on a topic, either sets `data.icon`.
    Each is one Undo step. The board's Insert menu opens the picker for a
    person without a mouse; a picked tile is placed at the middle of the view.
45. **A topic's icon is one slot: a Phosphor name or one emoji** (taken
    2026-10-05). `data.icon` keeps its name and widens its rule: either the
    Phosphor pattern it had or a single emoji (at most 16 code points, no
    ASCII, no markup); the paint pass tells them apart by that pattern. The
    exports carry it as `_icon` already. Decision 34 stands: markers stay
    Phosphor only, because a marker is read across a map and an emoji is
    drawn differently by every system.
46. **In text, an emoji is a character and an icon is `:ph-name:`** (taken
    2026-10-05). The note and document formatting toolbars, the document's
    Insert menu and the "/" menu open the picker; an emoji goes in as itself
    (it survives any export), an icon as the token `:ph-name:`, which the
    reading view draws as the glyph (`renderInlineMarkdown`, outside code)
    and every other reader sees as the words.
47. **The Centre's Enter adds a main branch** (taken 2026-10-05; XMind and
    Coggle). On the level-0 topic, Enter and Shift+Enter add a child, since a
    second centre is never what was meant; a floating topic's Enter keeps
    adding a free topic beside it.
48. **A map's left-drag on empty canvas is the board's** (the owner,
    2026-10-19, INBOX 1332): pans by default, Shift-drag draws the
    selection box, and the one "Left-drag on empty canvas" preference
    swaps them for maps and boards together (WHITEBOARD_PLAN decision 41).
    **Reversed** (the owner, 2026-10-19: "we need to revert the left click pan as it clashes with and negates the drag selection tools"): a left-drag with Select draws the selection box again; Pan, Space, the middle and right buttons and the trackpad pan; the preference is removed.

### 14.4 What is open

Phases 14a to 14e are built (HISTORY.md, "Moved from the plans, 2026-10-05
(MINDMAP_PLAN §14, mc1)"). Open, from INBOX 641 and §14.2's "not taken now":

- **Linked stickers** (Illustrator's symbols): edit one placed icon or emoji
  and every copy follows. Needs a `library_ref` that is followed, which
  decision 25 of WHITEBOARD_PLAN keeps as "kept, never followed".
- ~~Topic effects~~ built 2026-10-10: HISTORY.md ("Moved from the plans, 2026-10-10 (boardmap-1010)"); not yet in the PNG or SVG picture.
- Reaction stamps and voting: on a topic, built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"); on a board card, open.
- **The whiteboard half of 641's research**, beyond stickers.
- The exported picture draws each topic's shape since 2026-10-10 (boardmap-1010); a
  topic's effect and a Phosphor icon still do not reach PNG or SVG (an emoji icon does, as text).
- The document editor's `:shortcode:` completion keeps its own 248-entry table
  (`DOC_EMOJI_SOURCE`); fold it into `ICON_EMOJI_SOURCE` when the completion
  can wait on the picker's script.

## Placed from the owner's list, 2026-10-10

Every entry built 2026-10-10 (boardmap-1010). Moved to HISTORY.md ("Moved from the plans, 2026-10-10 (boardmap-1010)").

## 15. Deepened 2026-10-10 (Brief 72a, decision 71)

Measured with `scratchpad/ui-sweeps/deepen72a.js` (fresh data dir, no model,
three runs on a shared four-core machine, ranges across runs) and
`boardundo.js`. Sections 13 and 14 hold the map's own phases; these rows are
the trust contract's (WORLD_CLASS_PLAN 28).

**What renders today**

| Measure | 1440 | 390 (touch) |
| --- | --- | --- |
| Controls in `#library-view-whiteboard`, a five-topic map, one topic selected | 44 (top bar 9) | 24 (top bar 6) |
| Clicks from the dashboard to a new map | 5 (Library, Boards & maps, New, Map, Create) and a name typed; the palette 1, but it says "New concept map" where the Library's picker and the toast say "mind map" | the same |
| Time from Create to the first topic painted | 314 to 1,092 ms | 724 to 2,148 ms |
| Add a child, 20 in a row | 102 to 208 ms each | 424 ms each |
| Undo | add a child, Undo, Redo: both exact; `boardundo.js` 43/43 covers fold, layout, theme, detach, copy branch, expand all | not driven |
| Overflow | 0 past the viewport, 0 clipped; 4 overlaps: on the selected topic an icon-only grip sits over "Add a child to" | 8 overlaps (the grips and "Put a topic between these two"); 4 grips past the edge on the pannable canvas (not a defect) |
| No model | 0 AI controls on the map; the map palette has 33 commands | the same |

**The professional bar.** XMind: a map from the keyboard alone (Tab,
Enter, arrows), structures beyond the tree (logic chart, org chart,
fishbone, timeline, tree table), an outline view that edits the same map,
Zen mode, pitch mode, and every topic act one undo step.

**The rows, by impact**

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | **Built 2026-10-10 (Brief 78; HISTORY "MINDMAP Brief 78")**: New, Mind map makes "Untitled map N" with its root in edit (`wbNewUntitledBoard("map")`) | `map78.js`: clicks 5 to 3 as deepen72a counts (6 to 4 with the menu's opening) | 2, 13 |
| 2 | fix | **Built 2026-10-10 (Brief 78; HISTORY "MINDMAP Brief 78")**: "mind map" everywhere a person reads, `tests/test_terms.py` from DESIGN.md's glossary | "concept map" 14 to 0 | 10 |
| 3 | fix | **Built 2026-10-10 (Brief 78; HISTORY "MINDMAP Brief 78")**: the selected topic's lines stand their `+` aside, hidden grips leave the page, no invisible `+` on touch, the strip clears the add row | `map78.js`: overlaps 6 to 0 at 1440, 11 to 0 at 390; 0 unnamed | 7, 8, 9 |
| 4 | optimisation | **Built 2026-10-10 (Brief 78; HISTORY "MINDMAP Brief 78")**: one render per add (the adopt re-keys its lines), the accent read once per accent | style passes over 300 elements per add 8 to 4 (CDP, 390); press to editable 24 to 27 ms at 1440, 140 to 159 at 390 (not under 50 there; see the remaining file); Create to first topic 155 to 214 ms warm at 390 | 13 |
| 5 | fix | **Built 2026-10-10 (Brief 78; HISTORY "MINDMAP Brief 78")**: the More sheet lists the map palette's rows (`wbSyncMoreMapRows`) | `map78.js`: 6 of 33 to 40 of 40 at 390 | 8, 2 |
| 6 | expansion | **Built 2026-10-10 (Brief 78; HISTORY "MINDMAP Brief 78")**: logic chart, timeline, fishbone, tree table (`wbMapColumnPositions`, `WB_MAP_LAYOUT_NAMES`) | `maplayouts.js`: each 0 overlaps at 12 and 200, stored, lined; 38/39 (the fail is the base's) | 6 |
| 7 | expansion | Linked stickers, reaction stamps and voting (14.4) | 14.4's rows | 6 |
| 8 | fix | **Built 2026-10-10 (Brief 78; HISTORY "MINDMAP Brief 78")**: `wbExportTopicEffect`, `wbExportTopicGlyph` | `map78-export.js` + pngpixel: shadow 242 against 255, glow 251,231,231 against 255, the icon's ink in its slot | 11 |
| 9 | optimisation | **Built 2026-10-10 (Brief 78; HISTORY "MINDMAP Brief 78")**: `#wb-help-about` names each; WB_COMMANDS and the map palette gain the missing rows | `map78.js`: no popover 9 to 0, no palette row 5 to 0 | 6 |

**Briefs.** 36 (14.4), 78 (rows 1 to 6, 8, 9).

### Vendored capabilities to use, 2026-10-10 (Brief 75)

The owner: "make sure all the vendored repositories are made full use of. I want maximum utility." Ranked by the utility to the surface; `scratchpad/vendor_use.py` prints the counts ("available N, called M") and `tests/test_vendor_utilisation.py` ratchets them, so a row that lands raises its floor in the same commit. Each is a lead from a lower-bound count: grep the call site before building (CLAUDE.md section 1).

- **VC12, Harper on node labels** (S, rank 12). The mind map's labels are prose that no checker reads; the worker already exists and takes any string. Measure: a label with a seeded agreement error is flagged and its suggestion applies as one undo step; no lint call on a drag.

## Placed from Brief 60, 2026-10-10 (the measured census)

- Measured nearly clean (WORLD_CLASS 26.5): the showcase map at rest 0 long tasks, 0 gaps over 20 ms; a drag of one node 4 gaps over 20 ms of 605 frames and one 50 ms long task (`frames.js`). A map of hundreds of nodes is not measured.

## Placed from INBOX, 2026-10-10 (the owner on feature depth)

- INBOX 797, the owner 2026-10-10 23:02Z: "Also I feel like the mindmap and whiteboard are still missing a lot of features and options and stuff that draw.io and other things like the craft repos have :(" Owner: an Opus brief (canvasdepth), next Opus slot: re-audit the mind map against draw.io, designcraft and the other craft references in ANALYSIS.md ("Whiteboard, against draw.io and designcraft", "Mind map, against designcraft's canvas"), plus tldraw, Excalidraw, XMind and MindNode; rank every gap by how often a person meets it; build the top ones measured (connection points, the shape library at scale, named layers with visibility, swimlanes, more Mermaid kinds, and for maps: themes, branch styles, relationship lines, boundaries, summaries, outline import and export, presentation mode), each a commit with a test.

### canvasdepth, ranked by how often a person meets the gap (2026-10-10)

From ANALYSIS.md "Mind map, against designcraft's canvas", re-read against
XMind and MindNode. The brief's list (themes, branch styles, relationship
lines, boundaries, summaries, outline in and out, presentation, Tab, Enter
and F2) is built; what is open:

1. Built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"): a structure per branch.
2. Built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"): callouts on a topic.
3. Built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"): labels under a topic.
4. Built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"): `.xmind` export.
5. Built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"): reaction stamps and votes (14.4). Stickers were built as decision 44; linked stickers stay open in 14.4.

## Placed from INBOX, 2026-10-11 (the topic's tools)

Owner: the mapfix agent (Sonnet).

- **The owner, 2026-10-11, verbatim.** "also when I change stuff in the
  tools for a mindmap node, I cant actually see what the difference is
  until I click off it 😅" (screenshot: a topic's Shape popover, rows Core
  idea, Box, Edge bar, Fill, Effect; selected options drawn three ways
  (accent fill, a bordered box, a grey fill) and the resets in two
  colours). Placed: the Sonnet mapfix agent: a change paints the topic
  at once while it stays selected, the popover never covers the topic it
  edits, and one selected look and one reset look in the popover.
- INBOX 816, the owner 2026-10-11, verbatim: "should thes ebuttons be that big??" (screenshot: a zoomed-out dark map; the selected topic "test" is about 60 px wide and its + and link buttons are each about 50 px squares under it, larger than the topic). Read: no. The topic's action buttons are drawn at a fixed screen size while the map is zoomed out. Target: they scale with the topic and are clamped between 20 and 28 px, sit beside the topic without covering a neighbour, and below 50% zoom only the + shows.
- INBOX 817, the owner 2026-10-11, verbatim: "also that popup edit bar for when I try editing text doesn follow the selected text with scroll or zoom, and the panels and buttons kinda get in the way of me trying to edit the text in them" (screenshots: editing "Goal": the format bar, bold through comment, stays where it opened while the map pans, and in the second it sits across the topic; the + and link buttons and the fold toggle overlap the text box). Target: the format bar is anchored to the selection and re-placed on pan, zoom and scroll (one rAF per frame), above the topic, or below when there is no room, never over the text being edited; while a topic's text is edited its + and link buttons, fold toggle and resize grip are hidden.
- INBOX 818, the owner 2026-10-11, verbatim: "labels on mind map links dont move with the links". Target: a link's label is placed on the link's path (the midpoint of the drawn curve, `getPointAtLength`) and re-placed in the same frame as the link on a topic drag, a layout change, a fold and a pan or zoom; measured: label centre within 2 px of the path midpoint after a 200 px topic drag.
- INBOX 819, the owner 2026-10-11, verbatim: "also i dont think there is a way to label links on a whiteboard. also can link labels be customisable??" (screenshot: a selected board connector, its ends and midpoint handles, no label control). Read: a board connector takes a label today only by Enter on the selected link (`wbLinkTakesLabel`, decision 13), with nothing on screen saying so. Target: (1) the selected connector's context bar has "Label" (the tag icon), and a double-click on the line starts one at the click; (2) a label's look in the same bar: size, bold, text colour, a background chip on or off, and position along the line (start, middle, end, or dragged, kept as `t`); mind map link labels share the same controls and recipe; help moves with it (the Guide's board-connectors topic).
  Decided 2026-10-11 (mapfix found the clash): a double-click on a line stays "add a bend", as the owner asked earlier; a label starts from the visible Label button (built 2026-10-11, mapfix) or Enter, and a double-click on the label itself edits it. Open: (2), the label look controls, owner: the cards agent with 825.

## Placed from INBOX, 2026-10-19 (INBOX 1308: the gap audit)

Read from the code against XMind, MindManager and Miro mind maps. Sizes S, M, L; the first row is built in surfaces-1019.

1. Sort a topic's branches A to Z or Z to A, numbers as numbers (XMind "Sort") - S, built.
2. Import a .xmind file (the map already reads OPML, FreeMind and Markdown) - M.
3. A Gantt view of the topics that have dates (XMind) - L.
4. Audio notes on a topic, recorded and kept with the board - M.
5. A brainstorm timer on the map bar (XMind "Brainstorming") - S.
6. Copy the shape of a branch (layout and look together) to another branch - S.
7. Topic templates for one topic (a pros and cons topic from the topic's menu) - S.
8. Topic image from a link, fetched and kept - M.
9. Export a branch only, as PNG, PDF or Markdown - S.
10. Rainbow branches as a theme option for every branch, not only first level - S.
11. A legend for markers and colours, drawn on the map - M.
12. A second root on one map, joined by a labelled link (floating topics exist; named roots do not) - M.
13. Search inside topics' notes from the map's find bar - S.
14. Fisheye and focus dimming of everything but the selected branch - S.
15. Real-time presenter pointer in the present mode - L.

## Placed from INBOX, 2026-10-19 (edge sides; next PR)

1342. **The owner, 2026-10-19, verbatim.** "also the mindmap links will always connect only to the top or bottom of nodes, never the sides, should they?"
     Measured by code reading: `wbMapEdgeAnchors` (whiteboard-map.js:3224) uses the sides for tree-right, tree-left, tree-both and logic-right, and top and bottom for tree-down and org. For radial and free it picks the axis per edge, but compares the boxes' top-left corners (`child.x - parent.x`), not their centres, so a wide parent or a narrow child tips edges to the top or bottom. Recommendation: compare centre to centre, and weight the comparison by the boxes' aspect (a child level with the parent's side leaves from the side); reproduce on the owner's layout first.
