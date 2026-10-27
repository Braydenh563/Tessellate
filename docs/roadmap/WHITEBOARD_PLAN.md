# The whiteboard: controls that belong together, tools that behave

**Status: written by Fable by direct instruction ("the whiteboard panels
and tools need a better modern redesign still, this is horrendous"; "the
whiteboard control elements dont have that joined and cohesive feel"),
from the owner's screenshots and the code. Executed after
DOCUMENTS_PLAN.md and before MINDMAP_PLAN Phases 4 to 5, which build on
the same canvas.**

Back to [../ROADMAP.md](../ROADMAP.md).

## 1. What exists (checked in the code)

`frontend/js/whiteboard.js` (9,767 lines) draws an infinite dotted canvas with
object kinds `note`, `document`, `file`, `image`, `sketch`, `text`, `square`,
`circle`, `arrow`, `topic`/`node`/`radial` (mind maps) and `object`. Chrome:
a top bar on the Phase 8 grammar (Boards, board picker, rename, add, Map
toggle, layout select, Tidy, search, minimap, Insert/Edit/Arrange/View/Board
menus, Library, fullscreen); a bottom tool strip of 16 round buttons in
five groups (select, pan, lasso; pen, marker, eraser, fill; line with a
caret; sticky, text, image; straight and curved connectors; delete, undo,
redo); a zoom strip bottom right; a floating selection bar (duplicate,
style pipette, fill, send back, bring front, export, delete); a
properties panel on the right (copy style, guide colours, colour, width,
start cap, end cap, stroke style, and the arrange block: group, ungroup,
align, space, extract notes); the export popover; the new-board dialog.

## 2. Why it disappoints (from the screenshots, each checked in the code)

1. **Five surfaces, five recipes.** The top bar is the dock grammar; the
   tool strip is 16 separate circles on a pill; the selection bar is a
   third shape; the properties panel is a fourth (a scrolling column of
   label/control pairs with no sections); the arrange block is a fifth,
   and its buttons draw an icon on top of their label ("Ungroup" with the
   scissors through it) because the icon-only recipe and the labelled
   recipe are both applied. Nothing says "this is one tool".
2. **The tool strip does not say what a tool does or which is active
   beyond one filled circle**, has no labels, no shortcuts shown, and the
   line tool's caret opens a menu that is the only sub-tool picker in the
   strip. The colour of the ink you are about to draw is not visible
   anywhere on the strip.
3. **The export popover** opens as a 1,300px list (five sections of three)
   under the selection bar and runs off the screen (screenshot). The
   choices are a matrix (scope: selection / screen / board; format: image
   library / PNG / SVG / PDF / outline) rendered as a list.
4. **Properties lie or hide.** A drawn line reports Start cap Arrow and
   End cap Arrow when only the end has one (the default for the line tool
   is written into both selects); the arrange block offers Space and
   Group but no align-centre, no distribute-gaps, no same-size.
5. **Selection handles differ by kind** (notes show a thin rectangle with
   outside handles; shapes show handles on the corner with a rotate stem)
   so the same drag reads as two different objects.
6. **The highlighter draws opaque** and the quick-sketch highlighter
   "needs reworking" (owner): no multiply blend, no width, no straightness.
7. **A new mind map's root sits under the top bar; dragged map nodes leave
   their edges behind** (a regression from the marquee fix; owner's
   screenshot). Tidy never measured past five nodes.
8. **No keyboard model.** V, H, P, T, R, O, L, Delete, Ctrl+D, Ctrl+G,
   arrows nudge: the strip has none of it and the help does not say.

## 3. The target, in one paragraph

One canvas with three chrome pieces that share one recipe: the top bar
(the dock grammar, unchanged), a **tool rail** (one panel, tools as ghost
buttons with an active state, each with a tooltip naming its key, one
ink swatch that shows the pen colour and opens the colour picker, sub-tools
as a small flyout on long-press or the caret), and a **context bar** that
replaces both the floating selection bar and the properties panel: it
appears above the selection, shows only what applies to the selected
kinds (colour, stroke, caps for lines; fill and corner for shapes; font
for text; align/distribute/group when two or more), and opens a compact
popover for the long tail. Export is a dialog with two rows of segments
(scope, format) and one primary button. Handles are one recipe for every
kind. Every tool has a key and every key is in the tooltip and the help.

## 4. Decisions made (do not re-decide)

1. **Tool rail, not circles.** `.wb-rail` is a panel (card surface, glass
   edge) holding `.wb-tool` ghost buttons at `--control-h-lg`; the active
   tool is `accent-soft` with `aria-pressed`; groups are separated by a
   hairline; the ink swatch is the last group. Bottom-centre on desktop,
   bottom full-width on phone (Phase 9 already moved it).
2. **One context bar** (`.wb-context`) replaces `.wb-selection-bar` and
   `#wb-properties-panel`. Built from a table of kind → controls, so a new
   kind gets its controls by adding a row, not a panel. The long tail
   (guide colours, copy style, extract notes) lives in a "..." popover on
   the bar.
3. **Arrange is a segment group in the context bar**: align (left,
   centre, right, top, middle, bottom), distribute (horizontal, vertical),
   same size (width, height), group/ungroup, order (front, back). All
   eleven exist as functions or are ten lines each; the block in the
   screenshot is missing five of them.
4. **Export is a dialog** (`.modal` recipe): scope segment (selection,
   screen, board), format segment (PNG, SVG, PDF, Markdown outline, OPML,
   Save to image library), one primary "Export". The popover goes.
5. **Caps default per tool**: line tool = none/none, arrow tool = none /
   arrow, connector = none/none; the properties read the object, never
   the tool default (bug 4).
6. **One handle recipe** for every kind: eight handles, rotate stem on
   top, the bounding box at `--accent` 1px; a note's inner card no longer
   draws its own outline.
7. **Highlighter** = marker with `mix-blend-mode: multiply` at 40%
   opacity, width 12 to 24, Shift for straight; the quick-sketch pad uses
   the same tool code, not a copy.
   Two halves of this were left open when Phase 3 was built and are decided
   here, 2026-09-20, with the measurements that decided them:
   - **One table, two renderers. The pad stays a canvas.** The board draws
     SVG paths and the pad draws into a `<canvas>`; they are two rendering
     models and turning the pad into an SVG surface would be a rewrite of a
     working thing to make one tool's numbers agree. What is shared is the
     *definition*, not the code: `HIGHLIGHTER_STYLE` in `app.js` (alpha,
     width multiplier, the 12 to 24 clamp, cap, join, and the blend per
     backdrop) with `highlighterWidth()` and `highlighterBlend()` beside it,
     read by the pad's `sketchMove`/`sketchEnd` and by whiteboard.js's
     live-draw, mouseup and render paths. It lives in `app.js` because
     `whiteboard.js` is lazily loaded (`app.js`'s module map) and can read
     `app.js`, never the other way round. A tenth field of a highlighter
     added to one renderer and not the other is the bug this ends; the
     numbers before it were 0.4 with multiply on the board against 0.35
     with no blend and no clamp on the pad.
   - **The blend follows the backdrop, not the theme name.** Multiply is
     worth 20 luminance units a pass on a light board and 3 on a dark one
     (measured 252.9 / 229.6 / 211.5 light, 26.4 / 23.6 / 22.0 dark), so
     multiply on a dark board is a blend that does nothing while turning
     the ink to mud. The rule is `multiply` over a light backdrop and
     `screen` over a dark one, chosen by the resolved mode and re-applied
     when the mode changes, because the blend is an inline style (the
     export clones these nodes into a standalone SVG, where a stylesheet
     does not follow them). The pad passes "light" always and that is not a
     fudge: its strokes go into their own transparent canvas stacked over
     the paper canvas, so the backdrop a canvas blend sees is the other
     strokes and never the paper.
8. **Keys** (also in tooltips and help): V select, H pan, L lasso, P pen,
   M marker, E eraser, N sticky, T text, I image, C connector, A arrow,
   R rectangle, O ellipse, Delete, Ctrl+D duplicate, Ctrl+G group,
   Ctrl+Shift+G ungroup, arrows nudge 1px (Shift 10px), + / - / 0 zoom,
   F fit selection, Escape deselect. Same as the graph where they overlap.
   Two letters this list did not settle, decided while building Phase 1 and
   followed from here (the interrupt rule's point 4: a decision is recorded
   in the plan it affects):
   - **The board has two connectors and this list names one letter.** C is
     the straight link, Shift+C the curved one. The shifted form of the same
     letter rather than a second letter, so the pair reads as one idea; the
     built rail kept K for lasso and L for line, which is why L is not the
     lasso here.
   - **N was already the board overview** (bare, since the overview was
     built) and this list gives it to the sticky note. The sticky takes N and
     the overview moves to Shift+N, which is the same shifted-pair shape, and
     the top bar's button and the board help say so.
9. **Mind map root placement**: new root centred in the visible canvas,
   below the top bar's inset; edges are re-drawn from the node model on
   every drag frame (the marquee fix must not have detached them; add the
   sweep check that a dragged node's edge endpoint moves with it).
10. **The canvas is a Tab stop, and Tab on it walks the items** (taken
   2026-10-03, INBOX 445). It was kept out of the tab order while Tab on it
   did nothing; with nothing else reaching a shape without a pointer, Tab and
   Shift+Tab select the next item in reading order and `#wb-announcer` names
   it. Past the last item Tab leaves the canvas, so it is never a trap. A
   map keeps its own Tab (add a topic).
11. **The tool bar shows only what the held tool reads** (taken 2026-10-03,
   INBOX 445): `WB_TOOL_SETTINGS` maps a tool to its settings; a tool with
   none (a link, the eraser, the sticky, the text box, the bucket) shows no
   bar, and nothing that acts on a selection shows with nothing selected.
12. **A closed shape holds text** (taken 2026-10-04, the competitor pass:
   tldraw, Excalidraw, Miro and FigJam all do it, and a flowchart is the
   first thing anyone draws with the four shape tools). The text is `label`
   in the shape's own data blob, drawn as an SVG `<text>` inside the shape's
   group, so it moves, resizes, turns, exports and undoes with the shape
   rather than being a text box parked on top. Double-click the shape or
   press Enter with it selected; Enter or Escape ends, Shift+Enter breaks the
   line; the right-click menu says "Add text". Centred in the shape's label
   area (the inscribed band of an ellipse, the middle half of a diamond, the
   lower half of a triangle), wrapped to it, re-wrapped on a resize. Ink is
   the theme's text colour, or black or white on a fill of half opacity or
   more (`wbCoreInkFor`, the core topic's rule). No size, font or alignment
   controls: the bar keeps its seven, and those three are not what a first
   flowchart misses. Lines, arrows and pen strokes take no text; a label on
   a connector is decision 13.
13. **A connector holds a label** (taken 2026-10-04, the same pass: Miro,
   FigJam and Excalidraw all label a connector, and "yes" and "no" on the two
   arrows out of a diamond are what decision 12's flowchart needs next).
   `label` in the link's own data, one line of at most 80 characters (the
   map edge label's limit), drawn at the middle of the shaft, on the curve
   when the line is bent, in the map's edge-label recipe (ink haloed in the
   card colour) one size up. **The double-click keeps the bend** (asked for
   directly, earlier, and a gesture people already use here): the label is
   Enter on the selected connector and "Add a label" on its right-click menu.
   A cross-link on a map is the map's and keeps its ring; this is the
   board's links. Shares decision 12's one editor (`wbOpenSketchLabelEditor`).
14. **A frame is a titled region that carries what is in it** (taken
   2026-10-04: no decision existed for the open "board frames" row, and the
   recommendation was taken under standing order 3). tldraw's and
   Excalidraw's shape: an edge and a title, no fill, so shapes on the
   drawing layer show through; F, the rail's Add section and the Insert
   menu; click drops one (480x320, fitted to the screen), a drag draws it.
   An object of kind `frame`, its title in `content`, stacked below
   everything. Its inside lets the pointer through (a press inside selects
   or draws as on bare board); the title takes the pointer. Dragging the
   title carries whatever lies wholly inside, decided when the drag starts;
   Ctrl moves the frame alone (the map topic's rule). Double-click the title
   to rename. Delete leaves what it held. Rotation added 2026-10-19 (INBOX 1327,
   the owner asked): the box turns, what lay inside stays put. A click on a
   tinted panel's body or a plain frame's edge selects it. No style or order
   controls. Not on maps. Nesting, clipping and a frame as an export or
   presentation unit are not in this decision.
15. **A locked item lets the pointer through** (taken 2026-10-04, the open
   "lock" row, recommendation taken under standing order 3). Excalidraw's
   shape rather than tldraw's selectable-but-frozen one: a locked item
   cannot be selected, dragged, resized, erased or typed into, and Select
   all, a marquee, the lasso, a group's click and a frame's drag pass it
   by, so no gesture needs a guard of its own. Lock: the item's right-click
   menu and Ctrl+Shift+L. Unlock: the board's right-click menu ("Unlock 3
   locked items"; a right-click on the item goes through to it) and
   Ctrl+Shift+L with nothing selected. One undo step per lock or unlock. A
   card's flag is a column (`whiteboard_nodes.locked`, migration
   `e5a1c8f3b7d2`); a sketch's and an object's are in their data. Not on
   maps. No lock mark is drawn.
16. **Presentation steps through the frames** (taken 2026-10-04, the open
   "presentation mode" row, under standing order 3; tldraw's and Miro's
   shape, now that decision 14 gives a board its slides). View, Present
   frames: full screen, every control hidden but one bar at the foot
   (Previous, "2 of 5: title", Next, End), the frames in reading order
   (rows from the top, left to right), each fitted with its title above the
   bar's strip. Arrows, Space, Page Up and Down, Home and End walk; Escape
   ends and restores the camera and the window. A view: no key or press
   edits the board while it runs. No frames: a toast says to add one. Not
   on maps (MINDMAP_PLAN 12.2 item 9 is the map's own, by branch). Speaker
   notes, transitions and a presenter view are not in this decision.
17. **A comment thread lives in the item it is about** (taken 2026-10-04, the
   open "comments" row and MINDMAP_PLAN §12.2 item 6, under standing order 3;
   MindMeister's and Miro's shape: a thread per item, a count on it).
   `comments`, a list of `{id, text, at}` (at most 100, each at most 2,000
   characters of plain text), in a sketch's or an object's own data and in a
   card's own `comments` column (migration on `e5a1c8f3b7d2`). Not a table
   keyed across the three tables: in the item's own data a thread moves,
   copies, undoes and is deleted with its item and needs no cascade. A
   commented item wears a count mark at its top-right corner
   (`.wb-comment-mark`, a speech bubble and the number, at screen size like a
   grip), one layer for every kind so a shape has one too, and outside the
   item, so a locked item's thread still opens. The mark, the item's
   right-click menu ("Comment…", "Comments (3)…") and a map topic's Topic
   group open the thread in the help popover's shell (MINDMAP_PLAN decision
   18's): the comments oldest first with their time, a delete on each, one box
   at the foot; Enter posts, Shift+Enter breaks the line, Escape closes. Each
   post and each delete is one undo step. A notebook has one author, so no
   names or mentions. **Amended 2026-10-10** (the owner: "there's no way to
   edit a comment", comments "need a lot of improvement", "attach bookmarks,
   web links and more in comments"): a comment may carry `edited`,
   `resolved` and `reply_to` (each left out when it says nothing); a row has
   Reply, Edit, Resolve and Delete; resolved threads fold away and the mark
   counts what is open; the box has Attach and the "/" and "[[" menu, and the
   words are drawn by the app's markdown (link cards, note chips). A
   connector takes no thread (its label is what a line says). Not in any
   export: a thread is talk about the board, not the board.
18. **A frame is an export scope; frames nest by what they hold; nothing is
   clipped** (taken 2026-10-05, decision 14's three open edges, under standing
   order 3). "Export this frame…" on a frame's right-click menu selects the
   frame and everything wholly inside it, locked items too, and opens the
   export dialog on Selection, so every format the dialog has applies. A
   frame wholly inside another is one of the things it holds: dragging the
   outer one carries the inner one and what is in it, which decision 14's rule
   already does, so nesting needs no rule of its own. An item that overhangs a
   frame belongs to no frame and is drawn whole: clipping would hide what a
   person put there with no way to see it but moving it.

17. **Which history Ctrl+Z walks** (taken 2026-10-05, the owner: "the undo
   and redo across the application needs to cover EVERYTHING" and "shouldnt
   there also be local undos and redos ... for specific documents,
   whiteboards, mindmaps"). An open board or map: its own stacks
   (`wbHistoryFor`, one pair per board id, 100 steps, kept for the session
   while you visit others). An open document: its own CodeMirror history,
   kept per document id for the session (`docResetDocument`, restored only
   over the same text, purged on lock). Everywhere else, including the
   boards list: the app's stack (`pushUndo`, 50 steps). Inside a text field:
   the field's own. The status bar's pair says which ("on this board", "in
   this document", or the app step's name) and is repainted on a tab, board
   or document change. **Amended 2026-10-05 (INBOX 553(b), the owner):
   kept across a reload**, the last 100 steps of each board and map and the
   last 100 of each document's history, in IndexedDB on this device
   (`undo-store.js`, keys `board:<id>` and `doc:<id>`), written a moment
   after each change and read back when the board or document is first
   opened in a session. IndexedDB rather than the server: a step is an
   instruction against what this device last saw, so it is not carried to
   another device, and it needs no schema or network. A document's history
   comes back only over the very text it was taken against; the lock
   empties the store. The server's event log stays the long memory
   (History sheet, Recent activity).
18. **A board gesture's Undo is read off what it changed** (taken
   2026-10-05). `wbRecordGesture` snapshots every row and the map's settings,
   runs, and pushes the difference as one batch (lost rows back, a map's
   topics as one branch parents first; reparents, via the root when several
   moved so no step makes a ring; made rows removed, links first, children
   first; changed rows written back whole), replacing what the gesture pushed
   itself. New gestures go in `WB_RECORDED`; a gesture that knows something
   the snapshot cannot (a drag's start, `wbMapTransplant`) keeps its own.

### Decisions made, 2026-10-05: the draw.io pass (INBOX 557, 558)

**Status 2026-10-05 (docs hygiene before 0.4.0): decisions 19 to 36 are all
built** (the record is HISTORY.md, "Moved from the plans, 2026-10-05 (docs
hygiene before 0.4.0: WHITEBOARD_PLAN)"), with two named leftovers: named
layers (decision 27, BACKLOG 29c) and ghost topics on the canvas (decision
36). The decisions stay as written; none is remade.

Taken from the features audit's section 9.5 recommendations
(`scratchpad/audit1005/features.md`), under standing order 3. Where one
revises an earlier decision the owner's newer words ("take everything from
draw.io", "redesign the controls ... to maximise usability, utility,
accessibility, and learnability") are why.

19. **Decision 2, revised: the context bar stays the quick bar; its "..."
    opens a docked Format panel.** At most seven controls per kind on the bar
    (decision 11). The long tail goes to a Format panel on the right (Style,
    Text, Arrange tabs; Ctrl+Shift+P, which the board takes while it is on
    screen as it takes Ctrl+Shift+G), hidden by default, never a second
    floating popover.
20. **Decision 12, revised: a shape's text takes size, font and alignment in
    the Format panel's Text tab only.** The bar keeps its seven.
21. **Decision 13, revised: one label per connector, and it slides.** `label_t`
    (0 to 1 along the line, 0.5 the middle) in the link's data; a drag on the
    label moves it along. Several labels stay out.
22. **Decision 14, revised: frames are the pages.** The sidebar lists the
    board's frames as its pages (reorder is the presentation order); no second
    concept of a page.
23. **One command table** (`WB_COMMANDS`, whiteboard-commands.js). The Edit
    and Arrange menus' rows name a command (`data-wb-cmd`) and say its words
    and key (lint: `tests/test_wb_commands.py`); the right-click menu, the
    command palette's "This board" group and the shortcut sheet's whiteboard
    section are built from it. `]` and `[` are one step (past the next item
    that overlaps, ties broken by paint order, the fewest rows written);
    Ctrl+] and Ctrl+[ are the front and the back (FEAT-07). A shape's z is its
    paint order. No Order on a map (FEAT-17).
24. **A plain wheel zooms about the pointer, on a board and a map alike**
    (taken 2026-10-18, the owner, INBOX 1301 D7: "mouse scroll on the
    whiteboard and mindmap still doesnt zoom"). Reverses the old plain-wheel
    pan. Ctrl+wheel and a pinch zoom too; Shift+wheel pans sideways; panning
    is a drag, Space+drag or the middle button. The page never scrolls.
24. **A board's look lives on the board** (FEAT-06): `background {color,
    image}` in the board's settings beside type and layout, migrated once from
    the old per-browser keys on open; media cleanup counts the image. Grid and
    snap stay per device.
25. **The object library is independent copies** (section 8.4): a placed item
    becomes ordinary rows that remember `library_ref {id, version}` and never
    follow later edits. Built-in sets are static JSON shipped with the app,
    drawn fresh (no draw.io stencils; Apache-2.0 features, not code); "Yours"
    holds six kinds (a selection, a custom shape, a style or palette, a
    preset, a branch, a whole board as a template). **BACKLOG 4b is answered
    here:** a template is a library item of kind `template`, not a mark on
    the board.
26. **One left sidebar** (MINDMAP §12.5 and decision 5 revised, below): tabs
    Library, Notes (the note library moved in from the right), Layers, and on
    a map Outline; collapsible to a 44px rail, remembered per device; on a
    phone it is the edge sheet.
27. **Layers, phase 1**: the board as a tree in paint order, each row with
    show/hide (a `hidden` flag), lock (decision 15's flag) and rename; a drag
    restacks (writes z). A hidden item is drawn nowhere, exported nowhere,
    skipped by search and the Tab walk. Named layers stay phase 2 (BACKLOG
    29c).
28. **A locked item shows a faded lock on hover** (INBOX 557a), found by a
    board-level hit test since the item takes no pointer (decision 15); a
    press on it hints once, "Locked. Right-click to unlock".
29. **The AI edits boards with confirmation** (FEAT-12): move, edit, restyle
    and delete tools, each one event and one undo step, through the same
    confirm the other destructive agent tools use.

### Decisions made, 2026-10-05: draw.io phase 2 (wb-phase2)

30. **Every connector style takes bends** (decision 13's single `bend`
    retired for new edits). `points` (board units) is the one list: an elbow
    routes through it, a straight line runs through each in turn, a curved
    line is one Catmull-Rom curve through all of them leaving along its
    shapes' edge normals. The same grips on every style (filled bend, hollow
    ring to add); a double-click on the line adds a bend there; changing the
    line shape keeps the bends. An old link's `bend` is drawn as before and
    read as one waypoint, written as `points` on its first edit. A map's
    cross-link keeps its own bend handle.
31. **Line jumps are per connector** (`jumps`: arc, gap or sharp; none by
    default, as draw.io), set in the Format panel's Style tab. A connector
    hops on its straight runs over every line painted under it, so of two
    crossing lines only the upper one hops; the hitbox and the label keep
    the plain line.
32. **A Mermaid subgraph is a frame** (decision 22: frames are the pages). A
    node belongs to the first subgraph that names it; a subgraph is laid out
    as one block inside its parent's rows, so its frame holds its members
    and nothing else; an edge naming a subgraph joins its frame. The export
    writes every frame that holds a joined item as a `subgraph` of its title
    (the innermost frame; nested frames go out flat).
33. **A board's history is its items' event log, read three ways**
    (`routes_board_history.py`): moments (runs of at most two minutes,
    newest first, paged), the board at any event (each item folded to it;
    an item with no log was there from the start, one whose log begins with
    an edit was there as that edit's `before` says), and a restore of the
    board or the named items in one transaction, each row with its own event,
    links and a topic's parent re-pointed at remade rows. A library
    placement records each item's `created` beside its one board event
    (decision 25's "one event" kept for the board). A compacted moment is
    listed and not shown (410). The client draws the past with the board's
    own render in the presenting mode (`.wb-presenting`) with its own bar, refuses
    writes while it is shown, and records a restore as one Undo step.
34. **Drawn shapes are guide targets, and a row's spacing continues**
    (`wbGuideBoxes`, `wbSpacingSeries`): a sketch with a `shape` or a closed
    path is lined up with like a card (a freehand stroke and a connector are
    not); with no neighbour on the far side, the gap to the nearest item
    snaps to the gap that item keeps to the next one out. Alt still bypasses
    every guide; align and distribute stay the Arrange menu's (they existed).
35. **Connection points are on the outline** (`wbPortsForPath`): a card, a
    text box and a rectangle keep the eight; a drawn polygon has its corners
    and side middles, a curve its eight compass points; each is a fraction
    of the box, and a stored anchor is read from its fraction, so links made
    before keep their ends. With Select, pointing at an item that is not
    selected, locked or on a map shows them, and a drag from one makes an
    elbow connector with an arrow (as clone-and-connect does), to the item
    let go on or to a free end; a press that does not travel selects. A
    connector whose two ends one drag carried has its waypoints carried too,
    in the same Undo step.
36. **Branches from my notes is grounded by construction** (FEAT-13,
    `routes_map_suggest.py`): the search engine finds the notes (not private,
    not a board, not already on the map), the model only names a topic for
    one of them by number, and a line naming no listed note is dropped; with
    no model, or prose, the notes' titles are the suggestions and the dialog
    says so. Previewed in the picker dialog (the Attach picker's rows, all
    ticked), never written until Add, which makes the ticked ones under the
    topic in one transaction with "From your note ..." as each one's note,
    one Undo step. Ghosts drawn on the canvas wait for boot CSS room (the
    cap is full); the picker is the recipe the app already has.
37. **Stickers come from the one icon and emoji picker** (taken 2026-10-05,
    INBOX 642, mc1): MINDMAP_PLAN decisions 43 and 44 hold for a board as
    for a map. An emoji dropped or picked is a text object with `sticker:
    true`; a Phosphor icon is the Library's own vector icon. The Insert
    menu's "Emoji and icons" opens the picker. INBOX 641's research for the
    board beyond stickers (Illustrator's linked symbols, Photoshop's layer
    effects, Miro's reactions) is open there.
38. **No default board; a new one needs no name** (taken 2026-10-10, the
    owner: "also si there meant to be a default board??", and INBOX 739's
    "auto naming ... so the user isnt forced to name a new object"). A fresh
    install's Boards & maps tab is its empty state with New board and New
    mind map, each opening the template gallery on its kind. The server's
    scratch board (`id: null`, "Default board") is offered by the picker, as
    by the gallery, only when something is on it (`libraryListsBoard`). The
    gallery's name field may stay empty: Create makes "Untitled board N" or
    "Untitled map N", the next number after the highest there is, shown as
    the field's placeholder (`wbUntitledNames`).
39. **The board's top bar is one row on a phone** (taken 2026-10-11, row
    1637, WORLD_CLASS_PLAN's "`#wb-topbar` is 104px at 390"). Below 600 the
    bar is the back arrow (its word kept for a screen reader), the picker,
    Insert, Edit, View and More. The Board menu leaves: every row of it is a
    `WB_COMMANDS` row, so More lists it once its toggle is gone, and it is
    the menu used least often (once per board, not once per edit). The
    Library button leaves too (Insert's Shapes, icons and frames; View's
    Library switch), with the two dividers. Measured with `wbbar.js`: 348x104
    in two rows to 348x54 in one, six controls, all 44px tall; at 320 it
    still wraps to two rows rather than crushing the picker. This revises
    UI_MODERNISATION_PLAN's "Insert, Edit, View and Board stay" for the phone
    only; above 600 the bar is unchanged.
40. **The audit's polish bundle, row by row** (taken 2026-10-11, row 1600,
    BACKLOG "Smaller polish items"). Built: Alt while resizing keeps the
    centre where it was and grows both sides (`wbResizeBox` for cards,
    `wbSketchResizeTransform` for drawn shapes; Shift still keeps the
    ratio; `tests/test_wb_resize_from_centre.py`). Not built, each with its
    reason: flip is already the Format panel's Flip for drawn shapes
    (`wbFmtFlip`), and a mirrored note, image or frame has no reading that
    helps; whole-object opacity is already the context bar's for shapes,
    lines, arrows, links, text and images, and a frame stays opaque because
    it is the container the eye groups by; a status bar is not built
    because zoom, tool and selection already read from the zoom dock, the
    pressed tool and the context bar, and section 3 wants less chrome, not a
    fourth strip. The contextual quick bar is `.wb-context` (built).
41. **A left-drag on empty canvas pans; Shift-drag selects** (the owner,
    2026-10-19, INBOX 1332; supersedes the "a plain left-drag only pans
    with Pan" rule in `wbZoomFilter` and the marquee being the plain
    drag). One preference, "Left-drag on empty canvas" in the View menu,
    Pan (default) or Select, shared by boards and maps so they teach one
    hand (MINDMAP_PLAN decision 48); Shift flips whichever it is. Items
    keep their own drag; right, middle and Space drags still pan; the Pan
    and Lasso tools are untouched; touch already pans bare canvas.
    **Reversed** (the owner, 2026-10-19: "we need to revert the left click pan as it clashes with and negates the drag selection tools"): a left-drag with Select draws the selection box again; Pan, Space, the middle and right buttons and the trackpad pan; the preference is removed.
42. **Turning a frame turns what lies wholly inside it** (the owner, 2026-10-19: "if I rotate a frame, should it also rotate all the elements in that frame??"; yes). Contents are captured at grip-down by `wbFrameContents`, each turns about the frame's centre by the frame's delta (centre rotated, own rotation gains the delta), links follow their ends, Ctrl turns the frame alone, one Undo step; built as `wbFrameTurnOrigin`.
43. **Each stroke stacks** (the owner, 2026-10-27; supersedes the one-layer order: drawings painted as one SVG layer under every card, BACKLOG's "one real architectural limit" and the three bands of wbz-1026). Drawings (pen, highlighter, shapes, lines, connectors) and cards are one band of `wbStackOrder`, ordered by z; frames stay under everything (decision 14). So Bring forward, Send back, to front and to back move a stroke past cards and a card past strokes, a mixed selection included, and a new stroke takes `wbStackNewZ` on top of both. Render: SVG children take no z-index, so `wbSketchBands` splits the stack into runs of strokes with no card between; the run under every HTML item stays in the base layer (`#wb-zoom-group`), each other run is one `svg.wb-sketch-band` in the card layer with the z-index of its first stroke's stack rank (`wbPlaceSketchBands`, moving only groups out of place). At most one band per card plus one, never one root per stroke; a pan moves the composited card layer and re-bands nothing. The stroke being drawn paints in the overlay layer, over the cards, where it lands. A map keeps every line in the base layer. Export, the hit test, the Layers tab and undo read the same order unchanged (z is the only number written). Migration `c4e8a1f6b2d9`: on each board the drawings move under its lowest non-frame card, their order kept, so an old board looks as it did; saved stencils the same, the built-in stencils when read (`drawings_under_cards`). Measured: `scratchpad/wbz/` (session scratchpad) `perf.js` and `pairs.js`, numbers in CHANGELOG.
44. **Drawn shapes are selected, the tool returns to Select** (the owner, 2026-10-27: auto-select drawn shapes; the pen keeps its tool). After a rectangle, ellipse, diamond, line, arrow or any other shape tool commits, the new shape is the selection and the tool is Select; the pen and highlighter keep their tool so strokes continue. One undo step removes the shape.

## Built, 2026-09-09: one surface per panel, and the Arrange section

Moved to HISTORY.md ("Moved from the plans, 2026-09-09", WHITEBOARD_PLAN.md) on 2026-09-09: a plan holds open work only.

## Undo coverage, audited 2026-10-05 (INBOX 537)

Every mutating action on a board or a map, and whether Undo puts all of it
back (server side effects included). "Recorded" means `WB_RECORDED`
(decision 18). Measured with `scratchpad/ui-sweeps/boardundo.js` (43/43),
`mapinsertundo.js` (8/8), `wbmapundo.js`, `maprelink.js`.

| Action | Undo before | Now |
| --- | --- | --- |
| Delete a topic (Delete key, tool, menu, X) | one row back, loose; its branch lost | the branch, under its parent |
| Undo of a create whose topic gained a branch since | branch deleted for good | branch kept, Redo brings both |
| Delete a card, box or shape | item back, its links lost | item and links, ends re-pointed |
| Delete a selection | one step per item; parallel deletes popped the wrong entry | one step, in order |
| Clear board | one step per item; 404 on cascaded links stopped it | one step |
| Image object deleted | file unlinked, Undo drew a broken picture | file kept (media cleanup reclaims) |
| Fold, Expand all, Tidy, layout, numbering, theme, reset every topic's style | none | recorded |
| Add child, sibling, root, reference, duplicate, copy branch, template | the create only (unfold and tidy left) | recorded |
| Detach, remove keeping branch, turn a line around, cross-link reverse, to branch, cut | none | recorded |
| Insert between, outdent, move among siblings | own entries | recorded |
| Group, ungroup, paste style, bucket fill, fit to text, arrange cards | none | recorded |
| Card text edit (the note's words) | none | `note` step |
| Branch card on a board (makes a note) | none | recorded, the note to the bin and back |
| Drop a branch on a topic | own entry | own entry; a folded target opens (the "disappeared" report) |
| Rename a topic left open across an Undo | wrote onto another topic | the live row by id; an open edit is committed first |
| Delete a board (board menu, gallery, bulk) | "cannot be undone" (it was the bin) | bin, toast Undo and app Undo |
| Rename or duplicate a board (gallery) | none | app Undo |
| Move, resize, rotate, nudge, align, z-order, lock, frame title, properties panel, link handles | own entries | unchanged |

A board's undo now survives a reload (the amendment to decision 2: IndexedDB,
`undo-store.js`). Open: an agent's or another tab's change to the open board
is not on its stack (the History sheet has it).

### The app's stack (outside boards and documents)

| Action | Undo |
| --- | --- |
| Note bin, archive, edit, attach, link, unlink, tags, categories (move, rename, merge, delete, split, colour), reminders delete, skills batch | already had one |
| Category delete from the keyboard | added |
| Merge duplicate notes | added (words, tags, the binned notes back) |
| Generate or remove a note's title | added |
| A link's kind or properties | added |
| Clear completed reminders; delete an overdue or done reminder | added (`POST /reminders` `restore`; the past-date rule refused them) |
| Empty the bin, purge a note | none by design: confirmed, permanent |
| Detach a bookmark from a note being edited, delete a note type, relation type (its links typed again), conversation, or a space that was empty or whose contents moved | added (undo-1005: each DELETE answers with what it removed; `restore` on the create, `POST /spaces/restore`, `POST /conversations/restore`) |
| Delete a space with everything in it | none by design: confirmed, its files leave the disk |
| Entity merge | added (INBOX 553(a): `merge_with_undo`, `POST /merges/{undo_id}/undo`, Undo in the merge's toast) |

## 5. Phases

### Phase 1: the rail and the keys: BUILT, 2026-09-12
Moved to HISTORY.md ("Moved from the plans, 2026-09-12", WHITEBOARD_PLAN
Phase 1): a plan holds open work only. The gate lives on in
`scratchpad/ui-sweeps/whiteboard.js` (13 checks, green at 1440x900 light
and dark and at 390x844).

### Phase 2: the context bar: BUILT, 2026-09-12
Moved to HISTORY.md ("Moved from the plans, 2026-09-12", WHITEBOARD_PLAN
Phase 2): a plan holds open work only. Its gate lives on in
`scratchpad/ui-sweeps/whiteboard.js` (24 checks, green at 1440x900 light
and dark and at 390x844).

### Phase 3: export dialog, handles, highlighter: BUILT, 2026-09-12
Moved to HISTORY.md ("Moved from the plans, 2026-09-12", WHITEBOARD_PLAN
Phase 3): a plan holds open work only. Its gate lives on in
`scratchpad/ui-sweeps/whiteboard3.js` (12 checks, green at 1440x900 light
and dark and at 390x844). The two parts of decision 7 that were open are
decided and built, 2026-09-20 (the decision's own two sub-points above):
one `HIGHLIGHTER_STYLE` table read by both renderers, and a blend chosen by
the backdrop. Their gate is `scratchpad/ui-sweeps/sketchparity.js`,
9 checks, green at 1440x900 in both modes.

### Phase 4: mind map regressions and Tidy: BUILT, 2026-09-12
Moved to HISTORY.md ("Moved from the plans, 2026-09-12", WHITEBOARD_PLAN
Phase 4): a plan holds open work only. Its gate lives on in
`scratchpad/ui-sweeps/wbphase4.js` (19 checks). Root placement and the
per-frame edge follow were already built and are now measured (0px endpoint
gap over 29 edges, mid-drag, for a leaf, a whole branch and a marquee pair);
Tidy with thirty nodes leaves no overlaps in any layout, which took one fix:
a radial map past about twenty nodes compressed its rings into less arc than
its nodes occupied.

## 6. Consistency rules

Tokens only; the rail and the context bar are the same `.panel` surface
the docks use; buttons are the six recipes of WORLD_CLASS_PLAN §1.2; menus
are the one menu recipe; dialogs the modal recipe; keys in KEYMAP.

## 7. Not verified until built

Touch: the rail's long-press flyout on a tablet; pen pressure for the
marker. What is not measured anywhere in this section is a real finger on a
real tablet.

**The context bar at phone width is decided, 2026-09-20: it pins.** Both
placements were built and measured at 390x844 with five kinds high and low
on the board, ten selections each way
(`scratchpad/ui-sweeps/wbcontextphone.js`, 5/5 at 390x844 and at 1440x900).

| | floating | pinned |
| --- | --- | --- |
| covers the item it edits | 0 of 10 | 2 of 10 (an image entirely, 8640px2; a line, 3519px2) |
| sits on the tool rail | 2 of 10 (7759px2, 1122px2) | 0 of 10 |
| leaves the canvas | 1 of 10 | 0 of 10 |
| distinct tops | 10, spanning 452px | 1 |

The earlier reading (Phase 2, 2026-09-12) measured the bar clear of the
selection and inside the canvas and called that the case for floating; what
it had not measured was the bar against the rest of the chrome. At this width
the bar is a band, 348px of a 364px canvas for four of the five kinds and
269px for an image, 6.6% to 25.3% of the board. A band over the item can be
panned out from under; a band over the rail takes the drawing tools away.
Pinning's cost is the two selections under it, which is recorded in the sweep
rather than hidden. Desktop keeps the floating bar, measured at 1440x900 in
the same run: 0.7% to 2.6% of the canvas, nothing covered.

Found and fixed with it: the bar's `top` was never clamped to the canvas the
way its `left` was, so a selection low on the board put it from 843px to
1183px down an 844px window. It is clamped on both axes now.

## 8. Research: tldraw, Excalidraw, Miro, FigJam, and what it changes here

Written from working knowledge of the products, not a live teardown;
confirm in the product before building the phase where it matters.

- **tldraw** (MIT-licensed core, the strongest reference for a web
  canvas): one vertical or bottom tool rail of ghost buttons with a
  single active state; a *style panel* that shows only the properties
  the selection can take (colour, fill, dash, size, font, align) and
  collapses to an icon when nothing is selected; selection handles are
  identical for every shape; arrows bind to shapes and re-route; keys
  V H D X R O A L T N F E, with the key shown in each tooltip. Implication:
  decisions 1, 2, 6 and 8 are tldraw's shape almost exactly, which is a
  good sign, and tldraw's style panel confirms that "only what applies"
  is the right rule for the context bar.
- **Excalidraw** puts the property panel at the left as a stacked card
  and the tool rail at the top; its export dialog is exactly a scope
  toggle (selection / whole) plus format buttons with a preview.
  Implication: decision 4's dialog should include a live preview
  thumbnail; it costs one `toBlob` and prevents the "which scope did I
  pick" mistake.
- **Miro** and **FigJam** show a *contextual toolbar* floating above the
  selection for the common properties and put the long tail in a side
  panel. Implication: the "..." popover in decision 2 is the same split;
  keep the bar to at most seven controls and measure it.
- **Highlighter**: FigJam and Apple Freeform draw highlighter strokes
  with multiply blending and a fixed wide nib, straight with Shift.
  Implication: decision 7 is the norm.
- **Mind map tools** (XMind, Coggle): the root is created centred and
  selected in edit mode; child nodes are created on Tab at the parent's
  side and the layout re-flows; edges are part of the node model, not
  separate objects. Implication: decision 9, and MINDMAP_PLAN Phases 4 to
  5 should treat edges as derived from the tree, never as objects that
  can detach.

## Placed from INBOX, 2026-09-09

The owner's reports this plan owns, moved whole from INBOX.md with their numbers (never reused). Each becomes a phase row when its phase is written; until then this list is the phase.

### ~~Found while measuring the board bar at 820 (2026-09-20, not the owner)~~

~~**The board's top bar runs past its own right edge below 600, by 75px at 320
and 5px at 390**, and carries thirteen controls at 1440 against the dock
grammar's ceiling of seven.~~ **Both done, 2026-09-21**, measured before and
after at five widths with `scratchpad/ui-sweeps/wbtopbar.js` (now in
`scripts/gate.sh`'s sweep list), which also gates the menus' keyboard and ARIA.
The Built block is in [HISTORY.md](HISTORY.md), "Moved from the plans,
2026-09-21".

12. **Whiteboard: export-selection popover opens a full-height list in the
    wrong place; arrow drawn shows both caps as Arrow in properties;
    missing align-centre and distribute-gaps; the arrange panel's buttons
    are unreadable (icons overlapping text).** Owner: WHITEBOARD_PLAN.md.
    **The caps part only is fixed** (my scope was "12 only the caps part"):
    `wbDetectArrowStyle`'s own regex scan included the shaft's leading `M`
    (matched separately, one line above, specifically to exclude it) in
    its search for head markers, so a shaft with zero start caps still
    measured a false zero-distance hit on its own start point and reported
    "both". Slicing the shaft's own match off the string before scanning
    fixed it; verified live (`startcap: "none"`, was `"arrow"`).
    **The rest is closed, 2026-09-20, by Phases 2 and 3 rather than by
    repairs**, and measured rather than assumed
    (`scratchpad/ui-sweeps/wbinbox12.js`, 6/6 at 1440x900 and at 390x844).
    The popover the report is about is not built any more: the export is a
    dialog (decision 4), `.wb-export-menu` builds nothing, and the dialog
    opens inside the window at both widths (480x393 at 480,254 in 1440x900;
    342x417 at 24,214 in 390x844). Align centres and even gaps are both on
    the context bar, which carries all twelve arrange controls for a
    selection of two plus the two z-order ones. And the panel whose buttons
    drew their icons through their labels is gone with the properties drawer:
    every arrange control is icon-only with its name in the tooltip, measured
    at 0px2 of icon-over-text across 24 buttons on the bar and in the top
    bar's Arrange menu together.
25, 43 and 47: built. Moved whole to HISTORY.md ("Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WHITEBOARD_PLAN)").

### Performance on small laptops, measured 2026-09-08 23:30 UTC (Chromium, 1366x768, no GPU)

Numbers from `scratchpad/weight.js`: first load 6.7 MB over 71 requests
(uncompressed; the gzip layer is scoped to non-streaming API replies and
does not cover static files); unlock to ready 4.0s; idle traffic 4
requests a minute (was 14 in the audit); DOM 5,870 elements; JS heap 16 MB;
four blurred surfaces covering 32% of the viewport at rest; frame p95
16.7ms scrolling Notes. Script weight: app.js 1.6 MB, whiteboard.js 469 KB,
library.js 348 KB, documents.js 280 KB, graph.js 177 KB, all loaded at boot,
plus d3 and p5 vendored; 124 `backdrop-filter` rules across the CSS.

48, 52, 56, 64 and 65: built. Moved whole to HISTORY.md ("Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WHITEBOARD_PLAN)").

278. **Mid-work drop, 2026-09-20, verbatim (the owner), two screenshots.**
    "the rotate line and circle dont sit at the top center of a group
    selection in the whiteboard and instead sit off to the top left or
    right, or below the top border". Seen: a group of two boxes and a bar
    inside a circle, the rotate stem and knob at about a third of the box's
    width from the left and the knob inside the box's top edge; a group of a
    note card, an image card and a line, the stem rising from the top edge
    at x of one member's own centre rather than the group box's, and a
    second stem from a member card below. Owner: WHITEBOARD_PLAN (the group
    selection box, `wbBulkGroupBox` and the group's rotate handle in
    whiteboard.js). Recommendation: the group's rotate stem is drawn from
    the group box's own top-centre in board units after the box is fitted
    to every member's rotated bounds, and a member's own handles are hidden
    while it is part of a group selection; measured with a probe placing the
    knob at (box.x + box.w / 2, box.y - stem) at 0.5x, 1x and 2x, in
    `scratchpad/ui-sweeps/wbgroupguides.js`. **Fixed, 2026-09-20**, and the
    cause was one line narrower than the recipe guessed: the group's grip was
    already drawn from the group box's own top centre in board units (measured
    (340, 672) against a wanted (340, 672) at every zoom), but it never set a
    `transform-origin`. `.wb-sketch-rotate-handle` and
    `.wb-rotate-handle-stem` carry `scale(var(--wb-inv-zoom))` so a grip stays
    one size to the hand, and that rule keeps `transform-box` at its
    `view-box` default *because the drawing code sets the origin in board
    coordinates*, which `wbDrawSketchHandles` does for a single shape and the
    group path did not. The scale therefore resolved about the SVG view box's
    origin and multiplied the grip's own coordinates by `1 / k`: on screen the
    knob sat 170px right of the box's centre and below its top edge at 0.5x,
    340px left of it at 2x, and exactly right at 1x, which is the report's
    "top left or right, or below the top border" and why it looks intermittent.
    The anchor is set in `layoutGroupChrome`, so it follows a resize drag
    (measured mid-drag: box top 638, knob 612, the box's own top centre).
    The recipe's second half was also real and is done: a three-item group drew
    **four** rotate knobs, two stems and sixteen member resize handles, and now
    draws one knob, one stem and none; a member keeps its outline, so the
    earlier report this has to keep answering ("the shapes and lines arent
    selected visually and individually") still is. A card or a line selected on
    its own keeps all eight handles and its grip, measured.
    `scratchpad/ui-sweeps/wbgroupguides.js` carries the checks (0.5x, 1x, 2x,
    plus mid-resize), and `tests/test_ui_recipes.py` holds the ratchet: every
    grip scaled by `--wb-inv-zoom` sets its own anchor.

## Placed from INBOX, 2026-09-09 (the owner's evening batch)

Built; moved whole to HISTORY.md ("Moved from the plans, 2026-10-05 (placed
blocks found built, op5)").

## Placed from INBOX, 2026-09-21

258. **Recommendation, not a change, 2026-09-19 (the session).** The
    reverted outside commit added right-drag to pan the board, filtered so
    a right-click still reaches a node's context menu
    (`wbZoomFilter`: `event.button === 2` on a target that is not
    `.node-card, .sketch-group, .wb-object`). It is a good gesture and
    every canvas app has it, but nobody asked for it and a new gesture on
    the surface that carries the app's only context menu is a decision, not
    a patch. Not built here on purpose (standing order 8: a new need is an
    entry, not an ad-hoc build).
    Recommendation: take it, guarded as above, plus `contextmenu` suppressed
    on the canvas only while such a drag actually moved (so a right *click*
    on empty canvas keeps whatever it does today), and measured against
    `scratchpad/ui-sweeps/wbpan.js`. The other two ideas from that commit,
    a rotated group outline and alignment guides for a group drag, are built
    (861e740, 5273bae).
    **Tried 2026-09-19 and taken back out, with what was learned.** The pan
    itself is four lines in `wbZoomFilter` (`event.button === 2` when
    `event.target` is not inside `.node-card, .sketch-group, .wb-object,
    .wb-map-edge-hit, [contenteditable]`, and the mousemove half gated on a
    flag the mousedown set) and measured clean: a right-drag moved the board
    150px, a right-click with no drag left the transform untouched.
    The half that matters could not be measured. Three things were found
    and are worth having written down:
    - The `contextmenu` that ends a right-drag over this board is dispatched
      at the `<section>` *around* it, not at anything inside it, so a
      listener scoped to `#whiteboard-container` never sees it and
      `event.target.closest("#library-view-whiteboard")` is null on it.
    - It is dispatched **before** `pointerup`, not after, so clearing the
      "this drag moved" flag on the release is safe and clearing it on a
      `setTimeout(0)` from the release is not.
    - With all of that accounted for, two runs of identical code disagreed
      about whether the menu was dispatched at all. Non-deterministic here,
      and the difference between "the gesture is polished" and "the gesture
      leaves a menu open on your board" is exactly that dispatch.
    So: not shipped. `scratchpad/ui-sweeps/wbrightpan.js` is the acceptance
    test, written first and failing, with the three facts above in its
    header. Whoever builds it makes that file pass on a board with a card on
    it, which is also the case this run could not cover.
    **Built and taken back out a second time, 2026-09-20, and this run found
    why. Two of the three facts above are wrong.** Measured with every event
    logged in the capture phase across a full right-drag:

        pointerdown@wb-svg-layer
        mousedown@wb-svg-layer
        contextmenu@wb-svg-layer      <- on the press
        pointerup@wb-svg-layer
        mouseup@wb-svg-layer
        auxclick@wb-svg-layer

    `contextmenu` arrives **on the press, before the drag has moved a pixel**,
    and at `#wb-svg-layer`, not at the `<section>`. So at the only moment the
    decision can be made, nothing can know whether the gesture will become a
    drag: "suppress the menu only when the drag moved" is not implementable,
    which is why both attempts left a menu open. The non-determinism recorded
    above did not reproduce: six runs across two attempts agreed every time,
    so it should not be planned around.
    The pan half measured clean again (0 to 150px, three runs identical), and
    a probe bug was fixed while there: the card's position was read at setup,
    before checks 1 and 2 pan the board, so check 3 pressed empty canvas and
    reported a 120px pan "on a card" that never touched one.
    **Recommendation, for the owner, because it is a decision and not a
    patch.** One shape works: suppress the native menu on the canvas outright
    and open the app's own pointer menu (`openMenuAtPoint`, which exists) in
    its place. A right-click then gives board actions instead of Chrome's
    menu, and a right-drag gives a clean pan. What goes in that menu is the
    open question, and assertion 2 of the acceptance test ("a right-click
    still opens whatever it opened before") changes with it.

276. The sketch pad's bar at 820 on Large text with Spacious: decided and
    closed 2026-10-05 (op5); moved to HISTORY.md ("Moved from the plans,
    2026-10-05 (276, op5)").

## Placed from INBOX, 2026-09-23

- **The small conventions every canvas user takes for granted.** The owner,
  verbatim: "I cant do things on the whiteboard and mindmap like double clcike
  the rotate point above the top centre of an object and reset it to its
  default rotate. the whiteboard and mindmap are still missing a lot of those
  small features that we as user's use all the time and take for granted but
  very much notice when they arent there." Then: "same with the documents and
  other app features." One pass per surface, whiteboard and map first (with
  the map UX remainder), then documents, notes, chat and the Library: list
  what a Figma, Miro, tldraw, Google Docs or VS Code user expects
  (double-click a handle to reset it, Alt-drag to duplicate, Shift to
  constrain, arrow-key nudge, Escape to cancel a gesture, Ctrl+D, Ctrl+A in
  scope, triple-click a paragraph, and so on), measure which are missing in
  the running app, build them. Decision, taken: the missing ones are built
  without asking; a convention the app breaks on purpose keeps its reason
  written next to it.
  **The whiteboard and map half is built**: the checklist, with before and
  after for each convention, is `archive/agent-remaining/mapux2.md` (agent M,
  `canvasconventions.js` 54/54). Its one row left, Escape during a marquee or
  lasso, was measured 2026-09-23 and was wrong: it took the rectangle away
  and then cleared the selection as well, and the release's click cleared
  it again. Escape now takes back the drag and nothing else, and the rest of
  the drag selects nothing (`wbmarqueeescape.js`, new, 8/8, 4/8 before).
  With a board menu open, Escape closes the menu and keeps the selection
  (INBOX 396). **Open:** the same pass on documents, notes, chat and the
  Library.

## Placed from INBOX, 2026-09-25

419. **The owner, 2026-09-24, verbatim.** "in the whiteboard, the arrange
    dropdown menu appears above the top bar, cutting off the contents" (only
    the Order rows showed) and "clicking the meatball button on the popup
    tools menu when selected on a text box or sticky note on the whiteboard
    doesnt show any dropdown menu, or it flickers for a seck somewhere to the
    right then disappears". **Not reproduced** in headless Chromium, on the
    head after `ccd1b48`: Arrange opens under its button at 1440x900,
    1184x760, 1366x600, 1280x480, 1024x768, 947x608, 820x700, 700x900, in
    full screen, with touch, at 125% scale with real scrollbars, dark
    (`wbmenuroom.js` 36/36); the context bar's ⋯ opens beside the bar and
    stays for a sticky and a text box, selected or being edited, by click
    or tap, after a render, a state fetch, a resize, and with the pointer
    wandering over the canvas and onto the menu. Every placement path read
    (`placeEscapedMenu`, `wbKeepMenuBesideBar`) can only put Arrange above
    its button when the window has less room below than above, which the top
    bar never has. Both reports come from the desktop window (WebView2); the
    next step needs the owner: the window size, whether the top bar was
    dragged, and a screen recording of the ⋯ case. Recommendation: ask.
    **Tried again 2026-09-26, with real scrollbars and a Windows laptop's
    scale** (`SCROLLBARS=1`, `deviceScaleFactor` 1.25), and still not
    reproduced. `wbmenuroom.js` now takes `DSF`: 87/87 at 1440x900,
    1184x760, 1366x600, 1280x480 and 1024x768, and 36/36 at 1536x864 and
    1536x800 (a 1920x1080 screen at 125%). The flicker is a thing over time,
    which no probe had read, so `wbmoreflicker.js` (new) samples the ⋯ menu
    every 40ms for 1.6s after a real click, for a sticky and a text box,
    each selected and each being edited, with the pointer resting and then
    moving toward the menu: open, on top, inside the window and within 1px
    of where it opened in every sample, 48/48 at 1440x900, 1184x760 and
    1280x640 and 32/32 at the two 1536 sizes. The recommendation stands.

## Placed from INBOX, 2026-09-27

411. **The owner, 2026-09-24, verbatim, with the board export dialog and
    two lightbox screenshots.** "is there a way to better design all
    instances of these menu bar elements in popups and the like?? I think
    there's a better way to visualise them?? also I exported a mindmap
    selection as an image to the library, the mindmap nodes turned white??
    also the description that was auto generated said it was typed by hand
    in the lightbox when it was autogenerated, and the image clashes with
    the side left and right arrow buttons on the lightbox" Placed: choice
    controls, orchestrator (the radio form joins the flat looks' neutral
    selection; more than four choices in a dialog become option tiles,
    first on the board export); the export colours, the caption's source
    and the lightbox arrows, the map agent.

## Placed from INBOX, 2026-10-05

The features audit (scratchpad/audit1005/features.md) holds the draw.io
catalogue, the library spec and the phased briefs these become.

557 and 558: built (decisions 19 to 36 below; the object library, the Layers tab, the draw.io pass). Moved whole to HISTORY.md ("Moved from the plans, 2026-10-05 (docs hygiene before 0.4.0: WHITEBOARD_PLAN)"). Open from them: named layers (BACKLOG 29c) and ghost topics.

## Placed from INBOX, 2026-10-05 (OPEN.md triage)

- **`contrast.js` never visits a board or a map** (documents was added
  2026-10-04). Brief: add `whiteboard` and `mindmap` to its `TABS` with a seeded
  board (cards, stickies, a frame, shapes) and a seeded map, run at 1440 and
  390 in both themes, fix what it finds one surface per commit. Expect
  pre-existing findings; a session of its own. Opus, M.

## Placed from INBOX, 2026-10-05 (boardmap-1005)

Held by the boardmap-1005 agent; the built halves are in HISTORY.md
("Moved from the plans, 2026-10-05 (boardmap-1005)"). Open:

- INBOX 596, the rest: built (the side column, the phone overlap and the
  sidebar's skeletons; HISTORY.md, "Moved from the plans, 2026-10-05
  (op3-1005)").
- INBOX 608, the lists: built (`DRAG_EDGE` in `frontend/js/selection.js`; the
  browser's own autoscroll covers the last 20px, this the next 36;
  `ui-sweeps/s2-1005.js` MODE=listedge).

## Placed from INBOX, 2026-10-07 (next PR)

Built (code and tests read 2026-10-18, whiteboard-1018); moved whole to HISTORY.md ("Moved from the plans, 2026-10-18 (whiteboard-1018, built Placed blocks)").

## Placed from the owner's list, 2026-10-10

Every entry built 2026-10-10 (boardmap-1010). Moved to HISTORY.md ("Moved from the plans, 2026-10-10 (boardmap-1010)"); decision 17 amended and decision 38 taken above.

## The draw.io programme, 2026-10-10

The owner, 2026-10-10: "deep analyse and catalog everything in draw.io as
well, use, replicate, take and implement it and then build on it and make it
the best editor the world has ever seen." This section is the catalogue
(SESSION_BRIEFS Brief 44, part 1); part 2 builds from it. draw.io is
Apache-2.0, so code and shape data may come in with the notice kept
(`frontend/board-library/drawio/NOTICE.txt`); the ANALYSIS.md licence line
(this project is AGPL-3.0) is unchanged.

**What was read.** The fork `Braydenh563/drawio` (upstream `jgraph/drawio`),
shallow-cloned on 2026-10-10: `src/main/webapp/js/grapheditor/` (Format.js
9,297 lines, Actions.js 2,375, Menus.js 1,995, Sidebar.js 6,487, Graph.js
36,791, EditorUi.js 9,107, Shapes.js 11,182, Dialogs.js 5,452),
`js/diagramly/` (Menus.js 6,398, EditorUi.js 35,275, Dialogs.js 22,983,
Pages.js 2,834, App.js 9,482, 66 `sidebar/Sidebar-*.js` files of 51,432
lines in all), `js/stencils.min.js` (204 libraries, 9,090 shapes),
`templates/` (156 template files in 15 categories) and the stencil
`LICENSE`. Upstream no longer ships `stencils/*.xml`: the libraries are a
base64 delta-coded op stream in `stencils.min.js` (decoded by
`mxStencilRegistry.loadStencil`), which the converter reads directly.
Line numbers below are the fork's, 2026-10-10.

**How to read the tables.** "Has it" is what the grep or the code showed in
this worktree (file or element id named); nothing here was driven in a
browser, so "yes" means the control and its handler exist, not that it
renders well (CLAUDE.md section 1). Cost: S under half a session, M about
one, L several. Canvas model used in the "How MemoryMap would" column: three
item kinds (`node` cards, `object` text, image, frame and topic rows,
`sketch` rows whose `data` JSON holds `d`, `shape`, `color`, `width`, `dash`,
`fill`, `fillOpacity`, `alpha`, `shadow`, `label_*`, `points`,
`sourceAnchor`/`targetAnchor`, or `type: "link-*"` with `route`, `jumps`,
caps), one SVG surface (`#wb-zoom-group`), every edit through `wbFmtApply`
(one undo step), every action a row of `WB_COMMANDS`
(`whiteboard-commands.js`), every library entry a `memorymap-library-set`
item.

**Corrections to the 2026-10-10 parity matrix** (ANALYSIS.md), found while
checking each row (CLAUDE.md "already exists" rule):
- Connection points exist. `WB_FIXED_ANCHORS`, `wbPortFractions`,
  `wbPortsForPath`, `wbAnchorPositions` (whiteboard.js 2321 to 2510) give
  every item eight fixed ports (a polygon's corners and side middles, a
  curve's eight compass points), stored as fractions in
  `sourceAnchor`/`targetAnchor`; the matrix said "no". What is missing is a
  port list that comes from the shape, which the converter now supplies.
- Templates: 17 board templates and 15 mind map templates ship in
  `frontend/board-library/templates.json` and `maps.json` (INBOX 715), not
  "one".
- Find exists (`wbBoardSearchRun`, Ctrl+F) but searches cards and objects
  only, not shape or connector labels, and has no replace.
- The blue connection arrows exist as clone grips (`wb-clone-grips`,
  `wbCloneConnect`, Alt+Shift+Arrow), draw.io's hover arrows.
- Same width and same height exist (`same-width`, `same-height`); draw.io
  has no such command.
- (Odysseus, fourth read 2026-10-10) 

### 1. Format panel, Style tab

draw.io: `StyleFormatPanel.init` (Format.js 6359) builds collapsible
sections Fill, Line, Line jumps, Opacity, Effects, then Edit and Style
operations. Tessellate: `wb-format` (index.html, `whiteboard-format.js`) with
the same three tabs (Style, Text, Arrange); fields per kind in
`WB_FMT_FIELDS`.

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Fill colour, on or off | yes (`wb-fmt-fill-on`, `wb-fmt-fill`) | `addFill` (Format.js 6861), `createCellColorOption` `fillColor` | done | none |
| Gradient: second colour plus direction (north, east, south, west, radial) | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `addFill`: `gradientColor`, `gradientDirection` (Format.js 6925) | `data.gradient {to, dir}`, drawn as an SVG `linearGradient` or `radialGradient` in the board's `<defs>`; export clones defs so SVG and PNG keep it | M |
| Fill style: hatch, cross-hatch, dots, dashed, zigzag line, solid | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `Editor.fillStyles` (Editor.js 250), `fillStyle` select in `addFill` (Format.js 7009) | `data.fillStyle` picks one of six SVG `<pattern>` fills clipped to the shape | M |
| Swatches and preset colours (24 presets, 40 defaults, custom row) | partly: saved palettes (`save-palette`), no swatch grid in the picker | `ColorDialog.presetColors`, `defaultColors` (Dialogs.js 1805, 1815), `getCustomColors` (Format.js 7119) | one swatch popover behind every colour input, seeded with draw.io's 24 and 40, plus the board's saved palettes | S |
| Line colour | yes (`wb-fmt-stroke`) | `addStroke` (Format.js 7193) `strokeColor` | done | none |
| Line width | yes (`wb-fmt-width`) | `strokeWidth`, up to 999 | done | none |
| Line pattern: solid, dashed, dotted | yes (`wb-fmt-dash`) | `solid`, `dashed`, `dotted` actions (Actions.js 1586 to 1630) | done | none |
| Custom dash pattern ("8 4") | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `addDashPattern` (Format.js 7165), `dashPattern` | `data.dashPattern` string overrides `dash`; one text field, validated to numbers | S |
| Line style for polylines: sharp, rounded, curved | no | `sharp`, `rounded`, `curved` actions (Actions.js 1631 to 1700) | `data.round` radius applied by the path builder at M/L corners (quad rounded into cubics) | M |
| Corner rounding of a rectangle | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `rounded=1` with `arcSize`; `toggleRounded` (Actions.js 1661) | `data.round` read by the rectangle path builder; the stencil `roundrect` op already uses it | S |
| Opacity | yes (`wb-fmt-alpha`) | `createRelativeOption` `opacity` (Format.js 6385) | done | none |
| Shadow | yes (`wb-fmt-shadow`) | `addEffects` (Format.js 7939) `shadow` | done | none |
| Glass | no | `glass` effect (Format.js 7939) | drop: a skeuomorphic gloss the board's look does not use | none |
| Sketch (hand-drawn) | no | `sketch` effect (Format.js 8004), rough.js | drop (matrix verdict, unchanged) | none |
| Flow animation on a connector | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `flowAnimation` effect (Format.js 7939) | `data.flow` adds a CSS class that animates `stroke-dashoffset`; export writes it static | S |
| Edit style (raw string) | no | `editStyle` (Actions.js 1717), Ctrl+E | see section 3: the board's equivalent is "Edit data", a JSON view of `data` | M |
| Copy style, paste style | yes (`copy-style`, `paste-style`, `wb-fmt-copy-style`) | `copyStyle`, `pasteStyle` (Menus.js 1028, 1049) | done | none |
| Set as default style, default for new connectors | no | `setAsDefaultStyle` (Actions.js 1749), `setAsDefaultForNewConnections` (1763), Ctrl+Shift+D | `board.defaults {shape, link, text}` in the board's settings row, read by the tools when they create an item; Ctrl+Shift+D writes it from the selection | M |
| Named styles | yes (`save-style`, `wb-fmt-save-style`, library kind `style`) | style presets in the sidebar and `DiagramStylePanel.addGraphStyles` (Format.js 8383) | done for items; the whole-board presets are the next row | none |
| Board-wide style presets (twelve colour schemes applied to every shape) | no | `DiagramStylePanel` (Format.js 8252 to 8858) | a "Board style" row in the Format panel's no-selection state, writing fill, stroke and text colour across the board in one undo step | M |
| Edit image, replace image, crop | no (`icon-picker.js` crop is the avatar picker) | `editImage`, `image...`, `crop...` (Actions.js 884, 1998, 2112) | canvas crop to a new media row; ANALYSIS row "Crop, rotate, flip" | M |
| SVG image styles and CSS variables | no | `addSvgStyles`, `addSvgVars` (Format.js 6442, 6594) | drop: draw.io-specific theming of embedded SVG | none |

### 2. Format panel, Text tab, and the Arrange tab

draw.io: `TextFormatPanel` (Format.js 4439) and `ArrangePanel` (2002).
Tessellate: the Text and Arrange tabs of `wb-format`; text controls per kind
are `size`, `ink`, `bold`, `italic`, `align`.

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Font family | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `fontFamily` menu (Menus.js 137), `STYLE_FONTFAMILY` | `label_font` from a short list of the app's loaded faces plus system stacks | S |
| Font size | yes (`wb-fmt-size`) | `fontSize` menu (Menus.js 227) | done | none |
| Bold, italic | yes | `fontStyle` bits, Ctrl+B, Ctrl+I | done | none |
| Underline, strikethrough | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `fontStyle` bits 4 and 8, Ctrl+U | `label_underline`, `label_strike`, drawn as `text-decoration` on the SVG text | S |
| Subscript, superscript | no | `subscript`, `superscript` (Actions.js 1911, 1918) | needs rich text inside shapes; text boxes already hold markdown | M |
| Horizontal align (left, centre, right) | yes (`wb-fmt-align`) | `STYLE_ALIGN` | done | none |
| Vertical align (top, middle, bottom) | yes, 2026-10-10 (HISTORY) | `STYLE_VERTICAL_ALIGN` | `label_valign`; the SVG label block is positioned by it; Brief 36 carries it | S |
| Font colour | yes (`wb-fmt-ink`) | `fontColor...` (Actions.js 1525) | done | none |
| Label background and border colour | no | `labelBackgroundColor`, `labelBorderColor` (Format.js, Text tab) | `label_bg`, `label_border`: a rounded rect behind the label, which a connector label needs to stay readable over crossing lines | S |
| Text opacity | no | `textOpacity` | `label_alpha` | S |
| Text shadow | no | `textShadow` | drop | none |
| Label position (inside, outside: above, below, left, right of the shape) | no | `labelPosition`, `verticalLabelPosition` | `label_pos` enum; the icon and swimlane use it | M |
| Text direction, vertical text | no (Brief 36 names vertical text) | `textDirection`, `horizontal=0` (`vertical` action, Actions.js 1584) | `label_dir` (rtl, vertical-rl) applied as SVG `writing-mode` | S |
| Word wrap, label width, padding | partly (shapes wrap inside `label_area`) | `whiteSpace=wrap`, `labelWidth`, `labelPadding` | `label_width`, `label_pad` on top of `label_area` | S |
| Spacing: top, right, bottom, left, global | no | `spacing`, `spacingTop..Left` | `label_pad {t,r,b,l}` shares the row above | S |
| Line height | no | `lineheight` in the text panel | `label_lh` | S |
| Auto-size to text, fit text to shape | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `autosize` action (Actions.js 1001), `autosizeText`, `fitTextToShape` | one command `autosize` in `WB_COMMANDS`: measure the label with `getBBox`, resize the shape's box; grows only | S |
| Formatted (HTML) text, lists, indent, links, horizontal rule | partly: text boxes are markdown with a slash menu; shapes plain | `formattedText` (Actions.js 1086), `html=1`, list and indent buttons | shapes keep plain text; markdown stays for text boxes; the Format panel shows the markdown toolbar for them | none |
| Clear formatting | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `removeFormat` (Actions.js 1564) | one command: drop all `label_*` | S |
| Increase and decrease font size | yes, 2026-10-18 (whiteboard-1018; HISTORY, palette rows) | Ctrl+Shift+Plus, Ctrl+Shift+Minus (Actions.js 1956, 1960) | two `WB_COMMANDS` rows, 1pt steps | S |
| Layer order: front, back, forward, backward | yes (four `order-*` commands) | `toFront`, `toBack`, `bringForward`, `sendBackward` (Actions.js 569 to 585) | done | none |
| Group, ungroup, lock | yes (`group`, `ungroup`, `lock`) | `group`, `ungroup`, `lockUnlock` (Actions.js 644, 665, 521) | done | none |
| Remove from group | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `removeFromGroup` (Actions.js 705) | one command: clear `group_id` on the selected member, keeping the group | S |
| Copy size, paste size, swap | copy and paste size yes, 2026-10-18 (whiteboard-1018; HISTORY); swap no | `copySize`, `pasteSize`, `swap` (Actions.js 223, 238, 213) | `same-width`, `same-height` cover the multi-select case; copy size is two commands that remember w and h | S |
| X, Y, width, height | yes (`wb-fmt-x/y/w/h`) | `addGeometry` (Format.js 3082) | done; resize from the centre is the one gap (matrix) | S |
| Constrain proportions | no | `constrainProportions` checkbox (Format.js 3082) | `data.aspect` lock; shift-drag already keeps it | S |
| Rotation angle, flip horizontal and vertical | yes (`wb-fmt-angle`, `wb-fmt-flip-h/v`) | `addAngle` (Format.js 2913), `addFlip` (2612) | done | none |
| Turn 90 degrees | yes, 2026-10-18 (whiteboard-1018; HISTORY), no Ctrl+R (the browser's reload) | `turn` action (Ctrl+R) | a command that adds 90 to `rotation` | S |
| Align (six), distribute (two) | yes (eight commands) | `addAlign` (Format.js 2575), `addDistribute` (2856) | done | none |
| Snap to grid after align | partly (`wb-snap-toggle`) | `snapToGrid` in the align block | none worth building | none |
| Group padding | no | `addGroupPadding` (Format.js 3663) | frame padding row (`tint` and `hint` exist on frames) | S |
| Table: rows, columns, merge, stripes | no | `addTable` (Format.js 2162), section 12 below | section 12 | M |
| Arrow shape geometry (width of a block arrow connector) | no | `addArrowGeometry` (Format.js 3972) | needs the `flexArrow` connector shape, section 4 | M |
| Connector direction: reverse, loop side | reverse yes, 2026-10-18 (whiteboard-1018; HISTORY); loop side no | `addEdgeTurn` (Format.js 2811), `addLoopDirection` (2650) | a `reverse` command swaps ends and caps; self-loops are not drawn today | S |
| Edit data, copy and paste data, edit tooltip, note, link, open link | no (links on items exist) | `editData` (Actions.js 742), `editTooltip` (748), `editNote` (786), `editLink` (812) | section 3 | M |

### 3. Edit style, Edit data, placeholders, tooltips

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Edit style as text | no | `editStyle` (Actions.js 1717): a dialog with the `key=value;` string | an "Edit data" dialog showing the item's `data` JSON, parsed and validated on Apply, one undo step; the same field is how AI sees it | M |
| Edit data: custom properties | yes, 2026-10-11 (canvasdepth2; HISTORY) | `EditDataDialog` (Dialogs.js 3707): key and value rows, id, placeholders toggle | `data.props {key: value}` shown as a two-column editor; search and the AI tools read it | M |
| Placeholders `%name%` in labels | yes, 2026-10-18 (whiteboard-1018 and fixes7-1018; HISTORY), `%date%` and `%page%` included | `Graph.replacePlaceholders` (Graph.js 14099), `updatePlaceholders` (13534) | the label renderer replaces `%key%` from `data.props`, `%date%`, `%page%`; export bakes the values | M |
| Tooltip | yes, 2026-10-18 (whiteboard-1018; HISTORY), shapes and connectors; a native SVG title, not a popover | `getTooltipForCell` (Graph.js 17291), `editTooltip` | `data.tip` rendered as a hover popover on the SVG item; a link row already exists for notes | S |
| Note on a shape | no (comments exist, `comment` command) | `editNote` (Actions.js 786) | covered by board comments | none |
| Link on a shape (URL or page) | yes (object links, WHITEBOARD_PLAN decision) | `getLinkForCell` (Graph.js 15330), `editLink`, `openLink`, `link=`; `data:page/id,` links to pages | done for objects; add sketches and a "frame" target | S |
| Edit geometry as numbers | yes (`wb-fmt-x/y/w/h`) | `editGeometry` (Menus.js 962) | done | none |
| Edit polygon points, edit connection points | no | `editPolygon` (Menus.js 991), `editConnectionPoints` (1011) | section 5 (the ports editor); polygon editing is a later "edit points" tool on a path | M |
| Edit shape (custom stencil XML) | no | `editShape` (Menus.js 768), `EditShapeDialog` | drop; the library's "Save as a shape" (`save-shape`) covers it | none |

### 4. Connectors: edge styles, waypoints, jumps, arrowheads, labels

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Straight, curved, elbow routes | yes (three: `wb-fmt-route`, `line-curved/straight/elbow`) | `edgeStyle` menu (Menus.js 59): straight, orthogonal, curved, entity relation, elbow horizontal and vertical, isometric horizontal and vertical, sequence | done | none |
| Orthogonal routing that avoids other shapes | partly: elbow detours around its own two end boxes only (`wbElbowRoute`, `wbElbowDetour`) | mxEdgeStyle plus libavoid (`LibavoidRouting.js`, `libavoidRouting=1`), loaded when the extensions bundle is | an obstacle grid over item boxes (A* on a coarse grid, then simplify to corners); `route: "elbow"` keeps its shape, the router becomes the default behind it | L |
| Entity relation, isometric and sequence routes | no | `entityRelationEdgeStyle`, `isometricEdgeStyle`, `addSequenceEdgeStyleItem` (Menus.js 59 to 105) | `route: "er"` (an S-shape with fixed stubs), `"iso"` (30 degree legs); sequence is a UML rule, drop | S |
| Waypoints: add, move, remove, clear | yes (`waypoint` in `whiteboard-map.js`; `points` in the link data); "Clear the connector's bends" command 2026-10-18 (whiteboard-1018; HISTORY), the numeric list not | `addWaypoint`, `removeWaypoint`, `clearWaypoints` (Actions.js 1782, 1830, 1871), `addEdgeWaypoints` list (Format.js 4278) | done; add a "Clear waypoints" command and the numeric list in the Arrange tab | S |
| Line jumps (arc, gap, sharp) with size | yes, size 2026-10-18 (whiteboard-1018; HISTORY) | `addLineJumps` (Format.js 7835), `jumpStyle`, `jumpSize` | add `jump_size` | S |
| Arrowheads: about 40 (classic, block, open, oval, diamond, thin variants, async, box, half circle, dash, cross, circle plus, ER set, double block), filled or hollow, with size | partly: 11 stroked kinds (`WB_CAP_KINDS`: arrow, circle, square, multiline, six ER); no filled heads, no size | `Format.processMenuIcon` list (Format.js 140 to 175), `startArrow`, `endArrow`, `startFill`, `endFill`, `startSize`, `endSize` | caps become `{kind, fill, size}`; add block, diamond, oval filled and hollow, open, dash, cross, half circle; draw as closed subpaths like `wbCapPath` | M |
| Connector shapes: line, link (double), flex arrow, simple arrow, tapered arrow, filled edge, pipe, wire | no | `edgeShape` menu (Menus.js 107); `Shapes.js` `link`, `flexArrow`, `taperedArrow`, `filledEdge`, `pipe`, `wire` | `link-*` gains `shape` (line, double, block arrow, pipe) drawn as a closed outline around the centre line | L |
| Edge labels: text, position along the line, background | yes (`wb-fmt-label-t`, `wblinklabel.js`) | `edge value`, label offset in `mxGeometry`; background `labelBackgroundColor` | done; add `label_bg` (section 2) and a perpendicular offset | S |
| Multiple labels on one edge | no | child cells of the edge with relative geometry | a second label field `label2_*` is enough; more is drop | S |
| Perimeter spacing (gap between line end and shape) | yes, 2026-10-18 (whiteboard-1018; HISTORY), as `gapStart` and `gapEnd` | `sourcePerimeterSpacing`, `targetPerimeterSpacing`, `perimeterSpacing` (Format.js `addStroke`) | `gap_start`, `gap_end` subtracted along the end tangent | S |
| Source and target connect to a shape, an edge, or float | partly: links join cards and shapes; a free end floats | `mxConnectionHandler`, `Graph.connectVertex` (Graph.js 14940) | done for items; edge-to-edge is drop | none |
| Hover connection arrows to create a connected shape | yes (`wb-clone-grips`, `wbCloneConnect`) | `HoverIcons` (Graph.js 17581), `connectVertex` | done; add a shape picker after a drag from a grip to empty space (section 17) | S |
| Reverse direction, self-loop side | reverse yes, 2026-10-18 (whiteboard-1018; HISTORY); self-loop no | `addEdgeTurn`, `addLoopDirection` (Format.js 2811, 2650) | `reverse` command; self-loop as a drawn arc | S |
| Rounded and curved polylines | rounded: yes, 2026-10-18 (an elbow connector; whiteboard-1018, HISTORY); curved: no | `rounded`, `curved` styles | `data.round` on link polylines | M |
| Edge shadow and opacity | yes | `shadow`, `opacity` | done | none |

### 5. Connection points and constraints

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Fixed ports on a shape (eight, or polygon corners and side middles) | yes (`wbPortFractions`, `wbPortsForPath`, whiteboard.js 2321 to 2510) | `getAllConnectionConstraints` (Graph.js 23647): the `points` style, else the shape's `getConstraints`, else the stencil's `constraints` | done; `data.ports` (section "Decisions") supplies a shape's own list first | S |
| Ports from a stencil (names, perimeter flag) | no (converter writes them; the board does not read them) | `mxStencil` `<connections><constraint x y perimeter name>` | `wbPortFractions` returns `parsed.ports` when present; names become port tooltips; `perimeter` ports snap to the outline | S |
| Custom ports with an offset (`points=[[x,y,perimeter,dx,dy]]`) | no | `points` style (Graph.js 23651 comment) | `data.ports` entries take optional `dx`, `dy` in pixels | S |
| Add and delete a port by clicking | no | `addConnectionPoint` (Actions.js 1814), `getConnectionConstraintForPoint` (Graph.js 23719), `clearAnchors` (Actions.js 1841), `editConnectionPoints` | a "Ports" mode on a selected shape: click the outline to add, click a port to delete; writes `data.ports` | M |
| Fixed versus floating end | yes (omit `sourceAnchor` for floating) | `exitX`, `exitY`, `entryX`, `entryY`, `exitPerimeter` | done | none |
| Show ports while dragging a connector end | yes (`wb-port-preview`, whiteboard.js 13437) | `mxConstraintHandler` (blue crosses) | done | none |
| Connection arrows and points as View toggles | no | `connectionArrows`, `connectionPoints` actions (Actions.js 1389, 1396) | two View toggles (hide grips, hide ports) | S |
| Snap to connection (orthogonal ends) | no | `snapToConnection` and `snapToPoint` (Graph.js 22012, 23241) | with the obstacle router, snap the end so the last leg is square | M |
| Port constraint on a table row (east-west only) | no | `portConstraint=eastwest` (Graph.js 18454) | with tables | S |

### 6. Layers and pages

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Named layers: add, rename, duplicate, delete | no: `wb-layers-tree` lists items grouped by kind (`wbRenderLayers`, whiteboard-library.js 1474) | `LayersWindow` (Dialogs.js 4593): `addLayer`, `rename`, `duplicate`, `delete`, an `mxCell` child of the root per layer | `board.layers [{id, name, visible, locked}]` in the board settings row; items carry `layer` in `data` (sketch, object) or a card column; the tree gains a Layers group above the item groups | M |
| Show and hide a layer | no | eye toggle per layer, `show`, `hide` | filtered out in render and in hit-testing (`wbItemHidden` already exists for search) | S |
| Lock a layer | partly: per-item `lock` (`wbIsLocked`) | `lock`, `unlock` | `wbIsLocked` also reads the layer's flag | S |
| Current layer (new items land in it) | yes, 2026-10-11 (canvasdepth2; HISTORY) | `currentLayer` radio | `wbState.layer`, read by every `create` path | S |
| Move selection to a layer, select all in a layer | no | `moveSelectionTo`, `selectObjectsInLayer` (LayersWindow) | two commands in `WB_COMMANDS` | S |
| Layer order | no (z is per item) | `toFront`, `toBack` on the layer | layer z base added to item z | S |
| Pages (tabs) in one file: insert, duplicate, rename, delete, move, sort | by decision (WHITEBOARD_PLAN decision 22: frames are the pages; boards are separate rows) | `Pages.js` (2,834 lines), `insertPage`, `removePage`, `renamePage`, `duplicatePage`, `sortPages` (diagramly/Menus.js 264 to 292) | done by decision; a "Pages" side tab already lists frames (`wb-side-tab-pages`) | none |
| Links between pages | no | `data:page/id,` link target (Graph.js `getLinkForCell`) | a link target of "frame" scrolls and zooms to it (the present mode already knows frames) | S |
| Page view and paper size (A4, Letter, custom, landscape) | no | `pageView`, `PageSetupDialog` (Dialogs.js), `pageScale`; Format panel "Paper size" (Format.js 9231) | frame presets: A4, A3, Letter, slide 16:9, each a `frames.json` entry; export frame already exists | S |
| Page background colour and image | yes (board background, `wb1005-bg.js`) | `DiagramFormatPanel.addView` (Format.js 8906) | done | none |
| Units (points, inches, mm, cm, m) | no | `units` menu (diagramly/Menus.js 370) | drop: the board has no print scale | none |

### 7. Shape libraries and the stencil format

Library state in Tessellate: five built-in sets (`frontend/board-library/`,
`index.json`): templates 17, maps 15, general 19, flowchart 13, arrows 8,
frames 2, icons 1,530 (Phosphor), plus the user's own rows
(`routes_board_library.py`: kinds element, style, palette, preset, shape,
template; favourites, tags, search by name, tag and set at
whiteboard-library.js 400). draw.io: `Sidebar.prototype.addStencilPalette`
(Sidebar.js 6365) loads a stencil file; palettes are listed in
`Sidebar.prototype.updateEntries` (diagramly/sidebar/Sidebar.js).

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Stencil libraries at scale | no: four primitives plus the sets above | 204 libraries, 9,090 shapes in `stencils.min.js`, loaded per palette by `mxStencilRegistry.loadStencil` | the converter (`scratchpad/stencils/convert_stencils.py`) makes one `memorymap-library-set` per library; five ship in `frontend/board-library/drawio/` (basic 30, flowchart 36, arrows 34, bpmn 39, networks 57 shapes; 0.37 MB), all 204 convert (24.5 MB, so the rest stay offline and load on request) | S to ship, M for the loader |
| JS-drawn shape classes (cylinder, cube, callout, step, hexagon, UML actor and lifeline, folder, note, tape, document, process...) | no | `Shapes.js`: 99 `mxCellRenderer.registerShape` classes (for example `cylinder3` at Shapes.js, `umlActor`, `callout`) drawn by `redrawPath` | a `wbShapePath(kind, w, h)` table of 40 of them that returns M/L/C/Z, with the shape name stored in `data.shape` so the path regenerates on resize (stencils scale; these keep corner radii) | M |
| More-shapes dialog (tick libraries on and off) | no | `shapes` action, `moreShapes` dialog (diagramly/Menus.js 2924) | a "Shape libraries" dialog on the Library tab: one row per set, count, on or off; written to a user preference | S |
| Library import: `mxlibrary` XML and JSON | partly: `wb-lib-import` takes `.json` (the app's own set format) | `<mxlibrary>[{"xml": "<mxGraphModel>...", "w": 80, "h": 40, "title": "x"}]</mxlibrary>`, `LibraryDialog`, `DesktopLibrary`, `RemoteLibrary` | an `mxlibrary` reader that feeds each entry through the `.drawio` cell importer (section 14) | M |
| Library export | partly | `StorageLibrary`, "Export" in the library menu | exists in the app's JSON; add `.xml` mxlibrary out only with the cell exporter | S |
| Scratchpad (a user shelf, drag in to save) | yes: the Library tab's "Save to the library" (`save-selection`, Ctrl+Shift+S) and the favourites | `scratchpad` action (diagramly/Menus.js 3164), `addToScratchpad` (3718) | done | none |
| Library search by name and tag | yes (name, tags, set) | tag index `Sidebar.taglist`, `searchEntries` (Sidebar.js 1634): compound-token split, soundex and translated tag fallback, strict AND then OR | add stemming for the 9,090 names; tags come from the converter (words of the name plus the library) | S |
| Custom shape editor (draw a stencil from XML) | partly (`save-shape` from a drawing) | `EditShapeDialog`, `createShape` (diagramly/Menus.js 2938) | done in effect | none |
| Preview thumbnails | yes (`wbThumbSvg`) | `Sidebar.createThumb`, per-set PNGs (`images/sidebar-*.png`) | done | none |
| Drag a library item into a connector to insert it in the line | no | `Sidebar.dropAndConnect` (Sidebar.js 4321), edge drop target | drop onto a link splits it at the item's ports | M |
| Replace a shape keeping its connections | no | drag a sidebar shape onto a selected one with Alt, `swap` | one command "Replace with library item" keeping `sourceAnchor` and `targetAnchor` fractions | S |

**The stencil XML format** (what the converter reads; `mxStencil.drawNode`,
mxgraph `shape/mxStencil.js`). A `<shape name w h aspect strokewidth>` (w and
h default to 100) holds `<connections>`, `<background>` and `<foreground>`,
each a stream of ops over one canvas state:

| Op | Meaning | Converter output |
| --- | --- | --- |
| `path` with `move`, `line`, `quad`, `curve`, `arc`, `close` | replaces the current geometry | one `d` string of M, L, C, Z (a quad becomes a cubic; an arc becomes quarter-turn cubics) |
| `rect`, `roundrect` (`arcsize`), `ellipse` | replaces the current geometry | a closed M/L/C/Z path (kappa 0.5523) |
| `fill`, `stroke`, `fillstroke` | paints the geometry with the current state | one sketch row; a `fill` and a `stroke` of the same path merge into one row |
| `fillcolor`, `strokecolor` (a literal, or a style key with a `default`) | state | `fill`, `color`; a style key takes its `default`, counted |
| `strokewidth`, `alpha`, `fillalpha`, `strokealpha`, `dashed`, `dashpattern` | state | `width` (times the board's 2), `alpha`, `fillOpacity`, `opacity`, `dash` |
| `save`, `restore` | state stack | kept |
| `text` (`str`, `x`, `y`, `align`, `valign`) | a label region | `stencil.text` |
| `include-shape` | draws another stencil in a box | inlined with the box transform |
| `image`, `linejoin`, `linecap`, `miterlimit`, `fontstyle`, `fontfamily`, `fontsize`, `fontcolor` | unsupported or no counterpart | dropped and counted |
| `connections/constraint` (`x`, `y`, `perimeter`, `name`) | a connection point | `stencil.ports`, and `data.ports` on the first row |

Converter run, 2026-10-10 (`convert_stencils.py`, 5 libraries): 196 shapes in,
196 out, none skipped. Whole upstream: 204 libraries, 9,090 shapes in, 9,090
out, 28,084 ports, 766,379 path segments, 24.5 MB; dropped properties
counted, not hidden: style-keyed colour with a default used 5,066, bare
`<rect/>` of zero area 2,378, linejoin 1,220, linecap 549, miterlimit 372,
fontstyle 367, fontfamily 287, fontsize 218, fontcolor 196. The brief named
a UML library: upstream has none as a stencil (UML is drawn by `Shapes.js`
classes: `umlActor`, `umlLifeline`, `umlFrame`, `umlState`, and the 66
`Sidebar-*.js` palettes), so the converted set is basic, flowchart, arrows,
BPMN and networks, and UML is the JS-class row above.

**Five rendered and measured** (`scratchpad/stencils/render_compare.js`;
Chromium canvas 200 by 200; left half the converted JSON, right half the
stencil's own ops interpreted straight onto a canvas with separate arc
maths, because draw.io's own PNG of a shape cannot be made offline; fills
solid and strokes one device pixel so only geometry is compared; PNGs in
`scratchpad/stencils/out/`):

| Shape | Bounding box (px), JSON and ops | Fill coverage of the box, JSON and ops | Segments, JSON and ops | Ink overlap |
| --- | --- | --- | --- | --- |
| flowchart Decision | 10,10 to 189,189, same | 0.5056 and 0.5056 | 5 and 5 | 1.0000 |
| basic Heart | 15,22 to 184,181, same | 0.6103 and 0.6103 | 8 and 8 | 1.0000 |
| arrows Circular Arrow | 10,35 to 189,164, same | 0.4377 and 0.4372 | 10 and 8 (arcs split) | 0.9993 |
| bpmn Gateway XOR (data) | 10,10 to 189,189, same | 0.4998 and 0.4998 | 9 and 9 | 1.0000 |
| networks Router | 10,73 to 190,126, same | 0.9621 and 0.9614 | 177 and 104 (arcs, round rects) | 1.0000 |

Not measured: that the board draws them (they are not in `index.json`, so
no set loads them yet; `frontend/board-library/*.json` is globbed
non-recursively by `routes_board_library.py`, which is why they sit one
folder down), stroke width fidelity (draw.io's `strokewidth` is in shape
units; the converter writes 2 board pixels per unit), and the Atlassian
restriction in upstream's `stencils/LICENSE` (Tessellate is not an Atlassian
product; the NOTICE says so).

### 8. Templates

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Template gallery with categories, search, preview | yes: the New board dialog (`whiteboard-templates.js`, INBOX 715): 17 board templates, 15 map templates | `templates/index.xml` plus 15 category folders, 156 `.xml` files each with a `.png`; `NewDialog` (diagramly/Dialogs.js) | done; add categories as tags | S |
| Insert a template into the current board | no | `insertTemplate` action (diagramly/Menus.js 257) | `import` of a library template entry at the viewport centre (the library already places items) | S |
| draw.io's templates (basic 10, business 15, charts 6, engineering 3, flowcharts 9, layout 4, maps 5, network 13, other 12, software 12, tables 4, uml 8, venn 8, wireframes 5) | no | `templates/*/*.xml` are `mxfile` with a deflate-compressed `mxGraphModel` | convert 40 through the cell importer (section 14); licence is CC BY 4.0 (`templates/LICENSE`), so each carries "Template by JGraph, CC BY 4.0" in its library note | M, after the importer |
| Save a board as a template | yes (`save-template`) | `File > Save as template` | done | none |

### 9. Find and replace

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Find text, next and previous, highlight, count | yes for cards and objects (`wbBoardSearchRun`, whiteboard.js 2210; `wb-search-*`; Ctrl+F) | `FindWindow` (diagramly/Dialogs.js 9512), `findReplace` action (Ctrl+F) | done; extend to shape and connector labels (`label`) and `data.props` | S |
| Replace and replace all | no | `FindWindow` with `withReplace`: replace field, Replace, Replace all | a second field and two buttons on `wb-search-bar`; one undo step per Replace all through `wbRecordGesture` | S |
| Regular expression, all pages, case | regex and whole word yes, 2026-10-18 (whiteboard-1018; HISTORY); "all frames" open: find already spans every frame of the board, so the row needs a decision (a "this frame only" scope?) | `regularExpression` and `allPages` checkboxes (Dialogs.js 9512 onward); matches in label text and, with regex, in metadata | regex toggle and "all frames" (not boards); case-insensitive by default | S |
| Find in custom data | yes, 2026-10-18 (whiteboard-1018; HISTORY) | `testMeta` over the cell's attributes | with `data.props` | S |
| Tags on shapes, filter by tag | no | `tags` action (Ctrl+K, diagramly/Menus.js 1299), `tags` style attribute | `data.tags` with a tag filter that dims the rest; the Library already has tags | M |

### 10. Outline, navigation and view

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Outline window (a minimap) | yes (`wb-navigator`, Shift+N) | `outline` action (Actions.js 2187), Ctrl+Shift+O, `mxOutline` | done | none |
| Fit window, fit page width, fit page, two pages, custom zoom, zoom list | partly (fit everything Shift+1, 100 percent, in and out) | `viewZoom` menu (Menus.js 444): 25 to 400 percent list, `fitWindow`, `fitPage`, `fitTwoPages`, `fitPageWidth`, `customZoom` (Ctrl+0) | a zoom list in the zoom strip's menu; fit selection (F) exists per the decisions | S |
| Home, enter and exit group, expand and collapse | partly (`group` exists; no enter or collapse) | `home`, `enterGroup`, `exitGroup`, `collapse`, `expand` (Actions.js 562 to 566) | enter group dims everything else; collapse folds a frame to its title bar | M |
| Ruler | no (matrix says drop) | `ruler` action, `mxRuler.js` (690 lines) | drop; guides and smart guides cover it | none |
| Grid size and colour, guides, page view, connection arrows, tooltips toggles | partly (grid style: none, lines, dots, iso; snap) | `grid`, `guides`, `tooltips`, `connectionArrows`, `connectionPoints`, `pageView`, `animations`, `zoomWheel` (Actions.js 1313 to 1403) | add grid size (matrix row) and the two port toggles | S |
| Fullscreen | yes | `fullscreen` (diagramly/Menus.js 399) | done | none |
| Mouse wheel: zoom or scroll | not checked | `zoomWheel` | not checked | none |
| Presentation mode | yes (`present`) | `presentationMode` (diagramly/Menus.js 3954) | done | none |
| Light, dark and automatic appearance, adaptive colours | yes (the app's themes; the board's ink follows) | `adaptiveColors`, `light-dark()` colours (Format.js `defaultStripeColor`) | done | none |
| Full-screen shape picker (a quick palette at the cursor) | no | `showShapePicker`, `toggleShapes` Ctrl+Shift+K | section 15 | M |

### 11. Keyboard shortcuts

draw.io's list is `EditorUi.js` 8543 to 8612 plus `diagramly/EditorUi.js`
19743 to 19755. Tessellate's is `WB_COMMANDS` (whiteboard-commands.js) and
decision 8 above. "Differs" means the same action sits on another key; a
clash is listed so the choice is made once.

| draw.io | Action | Tessellate | Note |
| --- | --- | --- | --- |
| Ctrl+Z, Ctrl+Shift+Z or Ctrl+Y | undo, redo | Ctrl+Z, Ctrl+Y | add Ctrl+Shift+Z |
| Ctrl+X, C, V | cut, copy, paste | same | paste here and paste size: none |
| Delete, Backspace | delete | Del | Backspace: add on the board only |
| Ctrl+Delete | delete with connections | none | S |
| Shift+Delete | delete labels only | none | S |
| Ctrl+D | duplicate | Ctrl+D | same |
| Ctrl+A | select all | same | |
| Ctrl+Shift+I | select vertices | none, 2026-10-18: a command without the key (whiteboard-1018) | one command, "Select all shapes" |
| Ctrl+Shift+E | select edges | none, 2026-10-18: a command without the key (whiteboard-1018) | one command, "Select all connectors" |
| Ctrl+Shift+A | select none | none | Esc deselects |
| Ctrl+G, Ctrl+Shift+U | group, ungroup | Ctrl+G, Ctrl+Shift+G | differs on ungroup; keep ours, accept both |
| Ctrl+L | lock | Ctrl+Shift+L | differs (ours is the lint-held key) |
| Ctrl+Shift+F, Ctrl+Shift+B | to front, to back | Ctrl+], Ctrl+[ | keep ours; accept both |
| Ctrl+B, Ctrl+I, Ctrl+U | bold, italic, underline | bold and italic only on text | underline with section 2 |
| Ctrl+E | edit style | none | with "Edit data" (Ctrl+M) |
| Ctrl+M | edit data | none | section 3 |
| Ctrl+Shift+M | edit geometry | the Format panel (Ctrl+Shift+P) | |
| Ctrl+Shift+P | format panel | same | |
| Ctrl+Shift+L | layers panel | lock (clash) | the layers panel opens from the side tab and keeps no key |
| Ctrl+Shift+O | outline | Shift+N | differs |
| Ctrl+Shift+D | set as default style | none | section 1 |
| Ctrl+Shift+R | clear default style | none | S |
| Ctrl+R | turn 90 degrees | none, 2026-10-18: a command without the key (whiteboard-1018) | S |
| Ctrl+Shift+Y | autosize | none, 2026-10-18: a command without the key (whiteboard-1018) | S |
| Ctrl+Shift+G | grid on and off | ungroup (clash) | grid stays on the View menu |
| Ctrl+F | find and replace | find only | section 9 |
| Ctrl+K | tags | none | |
| Ctrl+Shift+K | toggle shape sidebar | none | |
| Ctrl+Shift+H | fit window | Shift+1 | differs |
| Ctrl+J, Ctrl+Shift+J | fit page, fit two pages | none | with page frames |
| Ctrl+0 | custom zoom | 100 percent | differs |
| Ctrl+plus, Ctrl+minus | zoom in, out | Ctrl+=, Ctrl+- | same |
| Home, Shift+Home | reset view, home | none | S |
| Ctrl+Home, Ctrl+End | collapse, expand | none | with collapse |
| Ctrl+Shift+Home, Ctrl+Shift+End | exit group, enter group | none | with enter group |
| Ctrl+Shift+Plus, Ctrl+Shift+Minus, Ctrl+{ , Ctrl+} | font size up, down | none | section 2 |
| Ctrl+., Ctrl+, | superscript, subscript | none | |
| Enter, F2 | start editing the selection | Enter | add F2 |
| Arrow keys, Shift+arrow, Ctrl+arrow | move 1 px, move by the grid size, resize (`nudge`, EditorUi.js 8249) | arrows 1 px, Shift 10 px | add Ctrl+arrow resize |
| Alt+Shift+arrow | clone and connect (`connectVertex`) | Alt+Shift+Arrow | same |
| Alt+Shift+R, L, T, N | clear waypoints, edit link, edit tooltip, edit note (`altShiftActions`, EditorUi.js 8129) | none | with sections 3 and 4 |
| Alt+Shift+F, V, B, E | copy size, paste size, copy data, paste data | none; copy and paste size are commands without the key, 2026-10-18 (whiteboard-1018) | S each |
| Alt+Shift+A, O, Q | connection arrows, connection points, edit connection points | none | with section 5 |
| Ctrl+Alt+Shift+F, B | bring forward, send backward | ] and [ | differs |
| Ctrl+Alt+X, Ctrl+Alt+Shift+X | copy as image, as SVG | none | section 14 |
| / | focus the sidebar search (`geOmniSearch`) | Ctrl+F finds on the board | the Library search could take / |
| Tab, Shift+Tab | next and previous cell | map topics only | S: cycle through items in z order on a board |
| Ctrl+Shift+6 | adaptive colours | none | drop |
| A, S, D, F, L, R, C, X (draw.io's one-letter inserts) | text, note, rectangle, ellipse, link, rhombus, connector, freehand | N sticky, T text, R rect, O circle, D diamond, C connector, L line, A arrow, P pen | clash by design: ours stay (decision 8) |
| Ctrl+S, Ctrl+Shift+S, Ctrl+P | save, save as, print | autosave; Ctrl+Shift+S is save to the library | print: export PDF |
| Esc | cancel, deselect | same | |

### 12. Selection, grouping, containers, swimlanes, tables

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Rubber-band, lasso, shift-add, select all of a kind | yes (select, lasso K; Ctrl+A); select all shapes and select all connectors, 2026-10-18 (whiteboard-1018; HISTORY) | `mxRubberband`, `selectVertices`, `selectEdges` (Actions.js 517, 518) | two commands | S |
| Groups with nesting | partly: `group_id` (18 hits in whiteboard.js); nested depth not checked | `group`, `ungroup`, `removeFromGroup` (Actions.js 644 to 705); `Graph.updateGroupBounds` (Graph.js 16483) | check the depth, add remove from group | S |
| Containers (a shape that holds children, drop target highlight, children move with it, auto-resize) | partly: frames hold items (`frames.json`); no drop highlight, no resize with children | `container=1`, `isContainer` (Graph.js 11233), `getDropTarget` (26334), `dropTarget`, `recursiveResize`, `collapsible`, `foldCells` (15610) | frames gain "fit to children", a drop highlight, and collapse; the frame-as-container rule is an existing decision | M |
| Swimlanes and pools (header strip, lanes in a stack) | no (matrix: partly) | `swimlane;startSize=...`, `childLayout=stackLayout`, `horizontalStack`, `resizeParent`, `resizeLast` | a "Lane" frame preset (frames.json already has "Timeline lane") with a header strip and a stack layout in `wbFrameLayout`: new lane appended in line, children keep their offsets | M |
| Child layouts (stack, tree, flow, rack) | no | `childLayout` styles (Graph.js, 68 hits), `mxStackLayout`, `rackLayout` | the stack layout on lanes only; others are the Layout menu (section 16) | M |
| Tables: rows, columns, cell merge, stripes, header | rows, columns and a header, 2026-10-11 (canvasdepth2; HISTORY); open: merge, stripes, a line dragged to size one row or column, Markdown paste | `Graph.createTable` (Graph.js 18553), `insertTableRow` (29524), `insertTableColumn` (29349), `setTableRowHeight` (19762), `tableLine`, `tableRow` shapes, Arrange panel `addTable` (Format.js 2162) | a `table` item: a grid frame with row and column sizes, cells as text objects, resize by dragging a line; Markdown paste converts into one | L |
| Lock, hide and "locked" cursor | yes | `lockUnlock` (Actions.js 521), `locked=1` | done | none |
| Z-order within a container | yes (z per item) | child order | done | none |

### 13. Images, math, links and tooltips

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Insert an image (file, URL, drag, paste), embedded data URI | yes (`insert-image`, I; media rows) | `image...` (Actions.js 1998), `shape=image;image=data:...` | done | none |
| Image as a shape fill (`image` style on any shape) | no | `STYLE_IMAGE`, `shape=image` | drop; an image is its own item | none |
| Crop, replace, border | no | `crop` (Actions.js 2112), `editImage` | section 1 | M |
| Math typesetting (LaTeX in labels) | no | `mathematicalTypesetting` action (diagramly/Menus.js 840), `Editor.initMath` (diagramly/Editor.js 4701) loads MathJax | KaTeX is MIT and offline-friendly; a `$...$` span in text objects and shape labels rendered to SVG `foreignObject`; Tessellate's markdown has no math today, so it would come with notes | L |
| Hyperlinks on shapes, to a URL, a page, or a note | yes for objects; links to a note are the app's own | `editLink`, `link=` | add to sketches; targets: note, frame, URL | S |
| Tooltips | no | `editTooltip`, `getTooltipForCell`, `tooltips` toggle | section 3 | S |
| Embedded notes | no (comments) | `editNote` | comments cover it | none |
| Edit data and placeholders | no | section 3 | section 3 | M |

### 14. Export and import formats

| Format | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| PNG with scale and transparent | yes (`wbExportPng`, `WB_EXPORT_FORMATS`) | `ExportDialog` (grapheditor/Dialogs.js 3582) zoom, width, height, dpi, transparent, grid, border width; "include a copy of my diagram" embeds the XML in the PNG | add border width, DPI; embedding the board JSON in a PNG `tEXt` chunk makes the PNG re-importable | S |
| JPG, WebP, GIF | JPG and WebP yes, 2026-10-18 (whiteboard-1018; HISTORY); GIF open | `exportJpg`, `exportWebp`, `exportAnimatedGif` (diagramly/Menus.js 1170 to 1181) | JPG and WebP are one canvas call each | S |
| SVG (re-editable, with the model embedded) | yes (`wbExportSvg`; `<metadata>` carries the board, `wbBoardSvgMetadata`) | `exportSvg` (diagramly/Menus.js 1101) with `content=` attribute | done | none |
| PDF | yes (`wbExportPdf`) | `exportPdf` (692), server side | done (print path) | none |
| HTML, embedded viewer, iframe, link | no | `exportHtml` (669), `embed` menu (4208) | an HTML export is the SVG in a page; embedding is out of scope | S |
| XML, JSON, URL | no | `exportXml` (536), `exportJson` (605), `exportUrl` (581) | the `.drawio` export below | M |
| `.drawio` import and export (mxfile with `diagram`, `mxGraphModel`, `mxCell`, `mxGeometry`, `UserObject`) | no (`mxfile` appears nowhere in `frontend/`) | `Editor.getGraphXml` (grapheditor/Editor.js 1563), `setGraphXml` (1508), compressed or plain `diagram` text, `mxCodec` | a pure parse in `whiteboard-interchange.js`: cells to items (vertex style `shape`, `fillColor`, `strokeColor`, `rounded`, `ellipse`, `rhombus`, `text`, `swimlane`, `image` to sketch, text, frame, image rows; edge `source` and `target` to link rows with `sourceAnchor` from `exitX`/`entryX`), pages to frames, `UserObject` label and link to `data.props`; the reverse writes plain `mxfile`; the Style mapping is the "Decisions" table | L |
| VSDX import and export, Gliffy, Lucidchart, draw.io CSV import | no | `vsdx/importer.js` (15,344 lines), `exportVsdx` (1431), `importFrom` (3410), `csv` action | drop VSDX and Lucid; the CSV importer is S to M and gives the AI a way to draw org charts | M |
| Mermaid in and out; PlantUML | yes for Mermaid flowcharts (`whiteboard-interchange.js`); no PlantUML | `mermaid`, `plantUml` actions (insertAdvanced menu) | keep the Mermaid subset; PlantUML needs a server, drop | none |
| Outline, Markdown, OPML, FreeMind, plain text | yes (for maps and outline) | no | Tessellate's own | none |
| Export selection, visible area, whole board, one frame | yes | `selection only`, `crop`, page range | done | none |
| Copy as image, copy as SVG | copy as image yes, 2026-10-18 (whiteboard-1018; HISTORY); copy as SVG yes, 2026-10-18 (fixes7-1018; HISTORY) | `copyAsImage`, `copyAsSvg` (diagramly/Menus.js 1186, 1194) | two commands that write to the clipboard | S |

### 15. Insert menu, shape picker and the sidebar search

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Insert menu: text, note, rectangle, ellipse, rhombus, line, polygon, freehand, image, link, template, table | yes except polygon, table (Insert menu, `insert-*` commands) | diagramly/Menus.js 4516 to 4574 | add "Polygon" (click points, double-click to close) writing a closed `d`; table with section 12 | S |
| Shape picker at the cursor (a search box that inserts the match) | no | `showShapePicker` (diagramly/Menus.js 4507), `ShapePicker` | the command palette already searches commands; add a "Shape..." mode that searches the library and places the match at the last pointer position | M |
| Quick create from a hover arrow with a shape picker | no (the grip copies the source) | `HoverIcons` plus the picker on a drag to empty space | on a grip drag to empty space, open the picker; Enter takes the source's copy | S |
| Sidebar search: tags, soundex, translations, "mxgraph.x.y" names | name, tag and set substring | `searchEntries` (Sidebar.js 1634), `addSearchPalette` (1878), `splitCompoundToken`, `Editor.soundex` | add word-start matching and ranking; synonyms come with the converter's tags | S |
| Text to diagram (Mermaid, PlantUML, "from text", "generate") | partly: Mermaid import; the AI's `generate_diagram` (HISTORY section 61) | `fromText`, `generate` (diagramly/Menus.js 1393) AI action | done by the assistant, which already places a diagram | none |
| Freehand | yes (pen, highlighter) | `insertFreehand`, `mxFreehand.js` | done | none |

### 16. Layouts

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Tidy a board | yes (Tidy in the top bar, `whiteboard-map.js`) | `runLayout` (diagramly/Menus.js 1666), `runLastLayout` | done | none |
| Mind map layouts (radial, tree, left, right) | yes (layout select, MINDMAP_PLAN) | n/a | done | none |
| Flow (horizontal, vertical), tree (vertical, horizontal, radial), organic, circle, org chart | no on boards | `insertLayout` menu, `mxHierarchicalLayout`, `mxCompactTreeLayout`, `mxRadialTreeLayout`, `mxFastOrganicLayout`, `mxCircleLayout`, ELK (`ElkLayout.js`, `layout: 'elkLayered'`, `elkTree`, `elkOrganic`) | the layered layout (Sugiyama in 150 lines) and the existing map tree layout over a selection of shapes joined by links; circle is ten lines; organic is a force pass | L |
| Parallel edges spacing | no | `mxParallelEdgeLayout` ("parallels", diagramly/Menus.js 1935) | offset links that share both ends | S |
| Vertical or horizontal flip of a layout | no | `direction` menu (Menus.js 337) | a command per axis on a selection | S |

### 17. The Format panel with nothing selected, and diagram options

| Feature | Tessellate has it | How draw.io does it | How Tessellate would | Cost |
| --- | --- | --- | --- | --- |
| Background colour or image | yes | `DiagramFormatPanel.addView` (Format.js 8906) | done | none |
| Grid: size, colour, on or off | partly (style, snap) | `addGridOption` (Format.js 9103) | grid size | S |
| Options: connection arrows, connection points, guides, tooltips, page view, shadow default, "Edit data" of the diagram | partly | `addOptions` (Format.js 9016) | the toggles in section 10 | S |
| Paper size, orientation | no | `addPaperSize` (Format.js 9231) | section 6 | S |
| Diagram style presets | no | `DiagramStylePanel` | section 1 | M |

### 18. Out of scope, with the reason

| Feature | Where in draw.io | Reason |
| --- | --- | --- |
| Cloud storage: Google Drive, OneDrive, Dropbox, GitHub, GitLab, Trello | `DriveClient.js`, `OneDriveClient.js`, `DropboxClient.js`, `GitHubClient.js`, `GitLabClient.js`, `TrelloClient.js` | the product is offline and local-first (CLAUDE.md) |
| Real-time collaboration, shared cursors, "present to everyone" | `P2PCollab.js`, `DrawioFileSync.js`, `shareCursor`, `presentToEveryone` | one user, one machine; no network service |
| Comments with notifications, share dialog, revision history on a server | `DrawioComment.js`, `share`, `revisionHistory` | the board has comments and its own history (`whiteboard-history.js`) |
| Plugins and `configuration` JSON | `plugins`, `ConfigEditor.js` | no third-party code in the app |
| Confluence, Jira, Notion, Microsoft Office, Atlassian embeds | `Sidebar-Atlassian*.js`, `microsoftOffice`, `embedNotion` | the stencil licence's Atlassian clause and no use for them offline |
| Desktop updater, language packs, telemetry | `check4Updates`, `language` | the app has its own |
| Visio, Lucidchart, Gliffy, Miro import | `vsdx/`, `miro/`, `graphml/`, `emf/` | large readers for formats nobody here has asked for; revisit on request |

### Build first

Ten phases for Brief 44 part 2 (Opus), in this order. Every phase is gated
by `bash scratchpad/ui-sweeps/wbregress.sh` (and `wbports.js`,
`wbrotatelinks.js` where ports or links move), the matrix rows it names in
ANALYSIS.md "Parity matrix, 2026-10-10", and a measurement written in the
commit. Help moves with each control (standing order 13).

1. **Ports from the shape.** `wbPortFractions` returns `parsed.ports` when
   present; port names as tooltips; the Library inserts the converted rows
   with `data.ports`. Gate: `wbports.js` plus a node test that a Decision
   shape's four ports are its tips. Matrix rows: connection points, library
   at scale.
2. **Stencil libraries load.** Ship the five converted sets in the
   Library: a "Shape libraries" dialog, search over names and tags, the five
   listed in `index.json`, the NOTICE shown in Help. Gate: the library test
   (`test_board_library.py`) with a new count, `wb1005-lib.js`.
3. **Format panel Text tab to draw.io's.** Vertical align, underline,
   strike, font family, label background, spacing, auto-size (the owner's
   open bug is vertical centring). Gate: `wb1005-format.js`, a
   `getBoundingClientRect` offset after a resize.
4. **Format panel Style tab to draw.io's.** Gradient, fill styles, custom
   dash pattern, corner rounding, swatches, default style, flow animation.
   Gate: SVG export keeps every one (`wb1005-export.js`).
5. **Connectors: arrowheads and routes.** Filled and sized heads, the full
   draw.io set, jump size, perimeter gap, entity and isometric routes,
   reverse, clear waypoints. Gate: `wbrotatelinks.js`, both ends rendered
   during drag (the owner's "edge arrows" bug).
6. **The obstacle-avoiding elbow router.** Grid A* over item boxes, one
   `route: "elbow"` behind the existing shape. Gate: `wb1005-elbow.js` plus a
   timing on a 200-item board (budget 16 ms per drag frame).
7. **Edit data, placeholders, tooltips, tags.** `data.props`, an Edit data
   dialog and Ctrl+M, `%key%` in labels, a tooltip, tag filter; the AI tools
   read `props`. Gate: search finds a property; the assistant's board read
   includes it.
8. **Find and replace.** Labels, connector text and props, regex, all
   frames, one undo step. Gate: `wbkeywalk.js` plus a replace-all test over
   a 100-item board.
9. **Layers, containers, swimlanes.** Named layers with visibility and
   lock, frames as containers (drop highlight, fit to children, collapse),
   a Lane preset with a stack layout. Gate: `wb1005-layers.js`,
   `wbframes.js`.
10. **`.drawio` import and export, then the templates.** The mxfile
    parser and writer, `mxlibrary` through the same path, 40 of draw.io's
    templates with CC BY 4.0 attribution, JPG, WebP, copy as image, PNG
    with the board embedded. Gate: a round trip of five draw.io templates
    (shape count, link count, label text equal) and `wb1005-interchange.js`.

After the ten: tables (L), math (L), layered and organic layouts (L), the
JS-drawn shape classes, the shape picker, and the shortcut gaps in section 11.

### Decisions, 2026-10-10

1. **The shape JSON the converter emits is the library's own set format
   with one added field.** A `memorymap-library-set` (`format`, `version`,
   `key` `drawio-<library>`, `name`, `source {project, library, licence,
   notice}`, `items`). Each item is the existing element
   (`key`, `kind: "element"`, `name`, `tags`, `payload {box {w, h}, items,
   links}`) so `routes_board_library.py` and the panel load it unchanged.
   Each stencil paint becomes one `sketch` row: `data.d` (only M, L, C, Z,
   because `wbPathBBox` and `wbPathPolyline` do not understand Q, S or an
   arc's flags), `shape: "custom"`, `color`, `width`, optional `dash`,
   `fill`, `fillOpacity`, `opacity`, `alpha`, `noStroke`; rows of one shape
   share `group: "g"`. The one addition is `stencil {source, aspect,
   strokewidth, ports, text, segments}` on the item, which the panel
   ignores today and the format panel and the ports read later. Aspect
   `fixed` is kept for the constrain-proportions default. Default fill
   under an outline is the flowchart set's 12 percent tint; an explicit
   colour is solid.
2. **Stencil constraints become ports.** A constraint (`x`, `y` fractions of
   the stencil's w and h, `perimeter`, `name`) is kept whole in
   `stencil.ports` and rebased onto the first row's own box as
   `data.ports [{x, y, name}]`, because `wbPortFractions` reads fractions of
   the row's bounding box (the control-point hull `wbPathBBox` measures),
   not of the stencil. `wbPortFractions` returns `parsed.ports` before
   `wbPortsForPath`; when a shape has none, the corner, midpoint and compass
   ports already there stay. A port stored on a link is still a fraction
   (`sourceAnchor`), so a resize carries it and nothing migrates. The
   `points` style's offsets (`dx`, `dy`, the fifth and sixth numbers) become
   optional `dx`, `dy` pixels on the port, not built until a shape needs
   them. `perimeter: 1` marks a port that slides to the outline; the value
   is kept now and used when the ports editor lands.
3. **Styles map to the format panel's own keys, not to a style string.** The
   board never stores a `key=value;` style (Edit data shows JSON). The
   import and export mapping, one row per draw.io key:

   | draw.io style key | Board `data` key | Note |
   | --- | --- | --- |
   | `strokeColor` | `color` | `none` sets `noStroke` |
   | `fillColor`, `gradientColor`, `gradientDirection` | `fill`, `gradient.to`, `gradient.dir` | `none` clears `fill` |
   | `opacity`, `fillOpacity`, `strokeOpacity`, `textOpacity` | `alpha`, `fillOpacity`, `opacity`, `label_alpha` | percent to 0..1 |
   | `strokeWidth` | `width` | draw.io 1 = board 2 (the converter's rule) |
   | `dashed`, `dashPattern` | `dash`, `dashPattern` | `dashed=1` is `dashed`; a pattern whose first length is 1 or less is `dotted` |
   | `shadow` | `shadow` | |
   | `rounded`, `arcSize` | `round` | |
   | `edgeStyle`, `curved`, `elbow` | `route` | `orthogonalEdgeStyle` is `elbow`, `curved=1` is `curved`, none is `straight`, `entityRelationEdgeStyle` is `er` |
   | `jumpStyle`, `jumpSize` | `jumps`, `jump_size` | |
   | `startArrow`, `endArrow`, `startFill`, `endFill`, `startSize`, `endSize` | caps `{kind, fill, size}` | `classic` and `block` are `arrow` filled, `open` is `arrow`, `oval` is `circle`, `ERone` is `er-one-only`, `ERmandOne` is `er-one`, `ERmany` is `er-many`, `ERoneToMany` is `er-one-many`, `ERzeroToOne` is `er-zero-one`, `ERzeroToMany` is `er-zero-many` |
   | `fontSize`, `fontColor`, `fontStyle` (1 bold, 2 italic, 4 underline, 8 strike) | `label_size`, `label_color`, `label_bold`, `label_italic`, `label_underline`, `label_strike` | text objects use `font_size`, `color`, `bold`, `italic` |
   | `align`, `verticalAlign` | `label_align`, `label_valign` | |
   | `labelBackgroundColor`, `labelBorderColor`, `spacing*`, `labelPosition` | `label_bg`, `label_border`, `label_pad`, `label_pos` | |
   | `rotation`, `flipH`, `flipV` | `rotation`, flip | |
   | `swimlane`, `container`, `startSize` | a frame with a header | |
   | `link`, `tooltip`, `tags`, user attributes | `link`, `tip`, `tags`, `props` | |
   | `sketch`, `glass`, `comic`, `cssVars`, `clipSvg` | none | dropped on import, counted in the import's report |

   A key with no row is kept in `data.drawio` verbatim so a re-export
   writes it back; nothing is lost in a round trip.
4. **Libraries ship in `frontend/board-library/drawio/`, not the top
   folder.** The glob in `routes_board_library.py` is non-recursive, so a
   set is loaded only when the "Shape libraries" dialog (phase 2) turns it
   on; counts in `index.json` do not move until then. The five shipped
   sets are 0.37 MB; the other 199 libraries (24.1 MB) stay out of the
   bundle and the converter regenerates any of them on request.
5. **The licence trail travels with the data.** `NOTICE.txt` and the Apache
   `LICENSE` sit beside the JSON; the Atlassian clause is stated and
   observed (Tessellate is not an Atlassian product); templates are CC BY
   4.0 and each converted template names its source in its library note.
   No THIRD_PARTY.md exists in this tree, so the entry is the NOTICE plus
   `archive/agent-remaining/drawio-1010.md`.
6. **Parity rows are corrected here, not in ANALYSIS.md.** The five
   corrections at the top of this section replace the matrix's wrong rows
   (connection points, templates, find, hover arrows, same size) until the
   next matrix pass.

## Deepened 2026-10-10 (Brief 72a, decision 71)

Measured with `scratchpad/ui-sweeps/deepen72a.js` (fresh data dir, no model,
three runs on a shared four-core machine, ranges across runs) and
`boardundo.js`. The draw.io programme above is the feature catalogue; these
rows are the trust contract's (WORLD_CLASS_PLAN 28) for the same surface.

**What renders today**

| Measure | 1440 | 390 (touch) |
| --- | --- | --- |
| Controls in `#library-view-whiteboard`, an empty board open | 40 (top bar 11) | 11 (top bar 7) |
| Clicks from the dashboard | open a board 3 (Library, Boards & maps, the card); a new board 4 (Library, Boards & maps, New, Create, and a name typed); the palette 1 ("New whiteboard board", "Board overview", "Find a card on this board") | the same |
| Time to the board (an empty board, bundle loaded) | 86 to 118 ms | 260 to 576 ms |
| Undo | `boardundo.js` 43/43 on this head; an agent's or another tab's change is not on the stack (the 2026-10-05 audit) | not driven |
| Overflow | 0 past the viewport, 0 clipped, 0 overlaps, no page scroll (the rail's seven section labels are visually hidden by design, 1 px) | the same |
| No model | 0 AI controls on the board; every board act is local | the same |

**The professional bar.** draw.io: every act from the keyboard and a menu,
any diagram from a template in two clicks, a named page history, the same
editor on a phone. Excalidraw and tldraw for the feel of a stroke and a
pinch.

**The rows, by impact**

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | **Built 2026-10-10 (Brief 77; HISTORY "WHITEBOARD Brief 77, rows 1 to 4")**: the top bar's More kebab below 820 (`wbInitMoreMenu`) | `wbphonecmds.js`: 40 of 81 to 81 of 81 at 390 (320 and 700 too); 0 top-bar targets under 44 px | 8, 2 |
| 2 | fix | **Built 2026-10-10 (Brief 77; HISTORY "WHITEBOARD Brief 77, rows 1 to 4")**: New, Whiteboard makes "Untitled board N", renamed in place (`wbNewUntitledBoard`, `renameCurrentBoard`) | `wbnewboard77.js`: clicks 4 and a typed name to 3; 690 to 873 ms from New to a drawable canvas | 2, 13 |
| 3 | fix | **Built 2026-10-10 (Brief 77; HISTORY "WHITEBOARD Brief 77, rows 1 to 4")**: `wbTakeChangeFromElsewhere` (whiteboard-history.js), from the chat stream's board tools and a BroadcastChannel | `boardundo.js` 43/43 to 45/45 (an agent row and an another-tab row) | 1 |
| 4 | redesign | **Built 2026-10-10 (Brief 77; HISTORY "WHITEBOARD Brief 77, rows 1 to 4")**: Board, Snapshots… (`wbOpenSnapshots`, `/whiteboard/history/snapshots`), each with the Library card's picture | `wbsnap77.js`: restore then Ctrl+Z object-equal, PASS | 1, 3 |
| 5 | expansion | The draw.io programme's ten phases (Brief 44 part 2), each gated by its own sweep | the matrix rows it names | 6, 11 |
| 6 | optimisation | 500 objects open in 2,551 ms first (25.2): paint the visible tiles first, then the rest | first paint under 1 s at 500 objects (25g, Brief 53) | 13 |
| 7 | fix | A failed save says what and why and retries; the board is never left half written | an offline save toast with an action; `test_never_lose.py` board row | 3, 4 |
| 8 | optimisation | Every rail and top-bar control has a `data-help-for` popover and a palette row | 0 missing | 6 |
| 9 | expansion | A board AI act (summarise a board, a board from a note) is one chat tool; the board keeps Tidy and the layouts as the no-model path | 0 dead controls with no model | 12 |

**Briefs.** 36 (the owner's fifteen items), 44 (row 5), 51 (row 7), 53
(row 6), 77 (rows 1 to 4, 8, 9).

### Vendored capabilities to use, 2026-10-10 (Brief 75)

The owner: "make sure all the vendored repositories are made full use of. I want maximum utility." Ranked by the utility to the surface; `scratchpad/vendor_use.py` prints the counts ("available N, called M") and `tests/test_vendor_utilisation.py` ratchets them, so a row that lands raises its floor in the same commit. Each is a lead from a lower-bound count: grep the call site before building (CLAUDE.md section 1).

- **VC10, the converted draw.io sets in the library picker** (M, rank 10). Five sets, 196 shapes (`drawio-arrows` 34, `-basic` 30, `-bpmn` 39, `-flowchart` 36, `-networks` 57) sit in `frontend/board-library/drawio/` and the library lists 7 of 12 sets; this is Phase 2 of "The draw.io programme" above, recorded here so the utilisation ratchet has its row. Measure: `scratchpad/vendor_use.py` reads "stencils called 12 of 12" and each shape drops onto the board with its ports.
- **VC16, a p5 generative element as parameters, not code** (L, rank 16). p5 is loaded for one surface (the dashboard art) and 21 of its 299 functions are called; the bundle is 1 MB raw. A board element that runs the person's sketch source is refused by the CSP (no `eval`, no `new Function`), so the kind would be presets with a seed and a few sliders. Measure: the same seed gives the same pixels twice (`pngpixel.py`), p5 loads only when a sketch element is on the board, and the cost against the 239 KB gzipped fetch is stated before it is built.

## Placed from Brief 60, 2026-10-10 (the measured census)

- Measured clean (WORLD_CLASS 26.5): the showcase board at rest has 0 long tasks and 0 gaps over 20 ms in 3 s; a drag of one object has 1 gap over 20 ms of 253 frames (`frames.js`, companion off). The 18 `requestAnimationFrame` sites and 15 `pointermove` handlers in `whiteboard.js` are the largest counts in the app, held per file by `tests/test_frontend_wake_sources.py`. Not measured: a board of 500 objects, or the companion on.

## Placed from INBOX, 2026-10-10 (the owner on feature depth)

- INBOX 797, the owner 2026-10-10 23:02Z: "Also I feel like the mindmap and whiteboard are still missing a lot of features and options and stuff that draw.io and other things like the craft repos have :(" Owner: an Opus brief (canvasdepth), next Opus slot: re-audit the whiteboard against draw.io, designcraft and the other craft references in ANALYSIS.md ("Whiteboard, against draw.io and designcraft", "Mind map, against designcraft's canvas"), plus tldraw, Excalidraw, XMind and MindNode; rank every gap by how often a person meets it; build the top ones measured (connection points, the shape library at scale, named layers with visibility, swimlanes, more Mermaid kinds, and for maps: themes, branch styles, relationship lines, boundaries, summaries, outline import and export, presentation mode), each a commit with a test.

### canvasdepth, ranked by how often a person meets the gap (2026-10-10)

From ANALYSIS.md "Whiteboard, against draw.io and designcraft", re-read from
the code. Each row is built as one commit with a test and a Playwright
measure at 1440 and 390, or left here.

1. Built 2026-10-10 (HISTORY "Moved from the plans, 2026-10-10 (canvasdepth)"): the draw.io sets in the Library with their own ports.
2. Built 2026-10-10 (HISTORY "Moved from the plans, 2026-10-10 (canvasdepth)"): Mermaid state, class and sequence in.
3. Built 2026-10-10 (same HISTORY block): `.drawio` import, first page; every page, each in a frame, built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"). Open: `.drawio` export, rotation, images.
4. Built 2026-10-10 (same HISTORY block): swimlanes in the Frames set.
5. Built 2026-10-10 (same HISTORY block): named layers with show, hide and lock. The current layer built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"). Open from section 6: layer order.
6. Built 2026-10-10 (same HISTORY block): find reads labels and text boxes; Ctrl+H replaces. Open from section 9: regex, whole word, notes' own text.
7. Built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"): the hand-drawn look, a board option and an item style.
8. Built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"): tables (section 12). Open from section 12: a column's own width, merged cells.
9. Built 2026-10-10 (same HISTORY block): a laser pointer while presenting.
10. Edit data built 2026-10-11 (HISTORY "Moved from the plans, 2026-10-11 (canvasdepth2)"). Open from section 3: `%name%` placeholders in labels, find reading the values.

## Placed from INBOX, 2026-10-11 (one export panel for the whole app)

INBOX 815, the owner: "I want to be able to preview any and all exports and
to be able to adjust them in a panel before I export anything, for
documents, boards, maps and notes etc." What exists: the board's export
dialog (WHITEBOARD_PLAN Phase 3, built), with no live preview; documents
export straight to .docx, .html and .pdf (`documents.js` ~10459 to 11040);
notes and chats export from Settings and menus with no step between;
`exportGraphPng` likewise.

Decisions, taken (standing order 3):

1. **One export panel, one recipe.** Every Export opens the same panel: a
   live preview on the left, options on the right, and one primary "Export"
   with the file name. Surfaces: a note or a selection of notes, a document,
   a board or frame or selection, a mind map, the graph, a chat, the Timeline
   view. Settings' whole-notebook exports keep their rows, and each gains
   "Preview".
2. **The preview is the file.** It renders from the same function that
   writes the file: the PDF's pages, the PNG at its scale, the HTML in a
   sandboxed frame, the Markdown as text and rendered. It updates within 300
   ms of an option change; a large export previews its first pages and says
   so.
3. **The options per format.**
   - All formats: the format and file name.
   - PDF: page size, orientation, margins, light or print theme, a
     header or footer, and the date.
   - Images: scale, a transparent or page background, padding, and the area
     (all, selection, frame, the view).
   - Text formats: what to include (tags, dates, links, attachments,
     comments) and the heading level.
   The last choices per surface are remembered.
4. **Nothing is lost silently.** The panel lists what the format cannot
   carry (an ink stroke in Markdown, a video in a PDF) before export.

Gates: the panel at 1440 and 390 inside the viewport. The preview and the
written file match for each surface and format: the PNG pixel-diffs under
1%, the PDF has the same page count, the text is byte-equal. Help moves
with it (standing order 13). Owner: the exports agent (Opus), queued after
the graph agent.

## Placed from INBOX, 2026-10-11 (fit a frame to its contents)

Built (INBOX 821 to 825, code read 2026-10-18); moved whole to HISTORY.md ("Moved from the plans, 2026-10-18 (whiteboard-1018, built Placed blocks)").

## Placed from INBOX, 2026-10-11 (ends, edge arrows, guides while drawing; canvasdepth3)

- INBOX 826, the owner 2026-10-11, verbatim (screenshots: a selected note card with no edge arrows; the Start and End menus): "I still feel like the whiteboard, mindmap,a nd text editor are missing a lot of features that other applications have. what happened to those edge triangle arrows?? can there be more arrow options on the links and lines?? can there be a custom memorymapai unique arrow design as well??" and "also dragging out shapes and boxes on the whiteboard doesnt have the alignment lines and assist"

Measured from the code: the edge arrows (`wbCloneSource`, whiteboard.js) show for a shape or a text box only; a note card (`kind === "node"`) and every mind map return null, so the card in the screenshot had none and nothing said why. The ends are 9 plain and 6 entity-relationship (index.html, `wb-cap-*`). Guides run on move and resize, not while a new shape is dragged out.

Decisions made:
- E1. A note card gets the edge arrows. Its arrow makes a new empty note card joined by a link (copying a note's text would duplicate a note); a shape or text box still copies. The arrow's title says which.
- E2. Ends added: outlined triangle, concave (stealth) arrow, dot, cross, half arrow, double arrow; and an end size (small, medium, large) beside each end menu. Every end draws the same in export. (wbs-1011: the dot is the filled circle already in the list; the sizes are 0.7, 1 and 1.45 of the head, medium stored as no field.)
- E3. One signature end, "MemoryMap": an open chevron with the brand mark's node dot at its tip, drawn from the mark's own geometry; it sits first under a "MemoryMap" group, and the default end stays Open arrow. (wbs-1011, C3: candidate A taken, the dot at the tip and the chevron a stroke behind it; it alone reads as two parts at 1x and 2x.)
- E4. Dragging out a new shape, text box or frame shows the move guides, snaps the moving corner to them, and shows the size ("120 x 80") beside the cursor, as Figma and draw.io do; Alt draws without snapping, as a move does.
- E5. The feature-depth gap is re-audited for the board, the map and the document editor together (tldraw, Excalidraw, draw.io, Miro, XMind, MindNode, Notion, Google Docs, Word), ranked by how often a person meets each gap, and the top five per surface built, one commit and test each; the rest stay here as rows.

Rows (owner: canvasdepth3, Opus, next free slot after transparency):
- C1 to C4: built (wbs-1011, 8e02b2bde and 8236fec29); HISTORY.md, "Moved from the plans, 2026-10-11 (canvasdepth3 C1 to C4)".
- C5. Decision E5: the audit table here, then its top five per surface; it lists the small taken-for-granted things too (Brief 87's list).

## Placed from INBOX, 2026-10-11 (board and map previews)

- INBOX 829, the owner 2026-10-11, verbatim (a board card's preview: grey blocks and squiggles): "board map previews need a lot of work, redesigning and maybe even reimagining."

Decisions made:
- P1. A preview is the board itself, drawn small: the real colours, shapes, connectors and the first words of each card, rendered off-screen to an image when the board changes (debounced, cached by revision), never a schematic of grey blocks.
- P2. A map's preview is its real tree: the central topic's title legible, branches in their colours, two levels deep.
- P3. The card shows the preview cropped to the content's bounds, the title, items and last edited; an empty board shows an empty-state line, not a blank frame.

Rows (owner: canvasdepth3, after C5): P1 to P3, each a commit with a test and a measured render time on the budget fixture's 500-object board.

## Placed from INBOX, 2026-10-19 (INBOX 1307, 1308: elements, templates, the W/H link; the gap audit)

Owner: "stuff like that, dont stop there, find what is missing on the whiteboard, mindmap and documents editor and add them." Built in surfaces-1019: the W/H link in Arrange, multi-part library elements placing as one group, 19 wireframe / 23 UML / 14 ERD / 16 flowchart elements, four templates (login, dashboard, mobile, sequence), Select similar, swimlanes. Gap list, read from the code against draw.io, Excalidraw and Miro (the first rows are done; sizes S, M, L):

1. Select similar (same kind, fill, line colour) - S, built.
2. Swimlane stencils, horizontal and vertical - S, built.
3. Align to a key object (draw.io: the shape the others line up to stays put) - M.
4. A shape's own web link, opened from the shape (draw.io "Edit link") - M; BACKLOG has a row.
5. A per-shape "keep proportions" property, so dragging a corner keeps the ratio without Shift (the W/H link is the numeric half) - S.
6. Quick sticky chain: Tab on a sticky makes the next one beside it (Miro) - S, built as Ctrl+Enter (Tab indents a sticky's lines here).
7. Dimension and measure lines with a live length - M.
8. Text that shrinks to fit its shape (draw.io "autosize" is grow only) - M.
9. BPMN set: task, event, gateway, data object - M.
10. C4 and architecture set: person, system, container, boundary - S, built (8 elements, `c4.json`).
11. Cloud and network icon sets, drawn here (no draw.io files) - M.
12. Org chart: a tree layout command for a board's boxes and connectors - M.
13. Crop a picture to a shape (circle, rounded) - M.
14. Voting dots and a timer for workshops (Miro) - M.
15. Text along a path - L.

## Placed from INBOX, 2026-10-19 (wb1327)

- INBOX 1332. **The owner, 2026-10-19, verbatim.** "im wondering if instead I should change the right click pan on the whiteboard and mind map to left click to make it more intuitive??" then "shouldnt it be kept consistent tho for learnabilioty?"
     Then: "maybe it csn be togglable bu=y the user??" A Settings choice, "Left-drag on empty canvas: Pan / Select", default Pan, one setting for both surfaces.
     Decision (taken): left-drag on empty canvas pans on both the whiteboard and the mind map; box select moves to Shift+drag; right, middle and Space drags keep panning. Owner: whiteboard agent wb1327, item 5.

## Placed from INBOX, 2026-10-19 (per-board view, Format on a map; next PR)

1340. **The owner, 2026-10-19, verbatim.** "when I go between the mind map and whiteboard, should the board recenter on the main content?" **Built in memory for the session (not saved with the board), 2026-10-19:** `wbBoardViews`, `wbRestoreOrFrameBoard`; a map too big to fit opens at its content corner (`wbMapOpenTarget`); sweep `scratchpad/ui-sweeps/mapopenframe.js`. Saving the view with the board is still open.
     Measured by code reading: a map refits on every open (`wbFrameMapOnOpen`, whiteboard.js:2516, `wbZoomToFit`); a board is not reframed and keeps whatever the shared camera (`wbZoom`, :170) last was, which may be the map's; no view is saved per board. For the next PR. Recommendation: each board and map remembers its own view (pan and zoom, saved with the board); returning restores it; fit to content only on first open, or when nothing would be on screen.


## Gap audit against draw.io, 2026-10-25 (wb2)

The owner, 2026-10-25: "upgrade the whiteboard and mindmap; add the features draw.io and others have that the app doesn't". Read from the code (`WB_COMMANDS`, `WB_FMT_ROWS`, the Library panel) against draw.io's Arrange, Edit, View and Format menus; "exists" names where. The five marked "build" are the ones taken for a student's diagrams, in this order.

Exists (no work): connector waypoints and elbow routing (`route`, Bend a line); line jumps at crossings (`jumps`); align, distribute, same size, align to a key object; equal spacing guides; z-order (forward, back, front, back of all); lock; duplicate (Ctrl+D) and copy-and-join arrows; copy, paste and reset style; connector labels; frames and swimlane stencils; layers; shape and icon search in the Library (`wb-lib-search`); grid snap toggle; export or copy the selection; flip; select similar; keep proportions; Edit data; find and replace; Mermaid and draw.io import.

Missing (items 1 to 5, zoom to the selection, tidy as a tree, change the shape, a shape's link and text that shrinks to fit, are built: HISTORY.md, "Moved from the plans, 2026-10-25 (wb2)"):
6. Dimension lines with a live length (10-19 item 7). M.
7. Crop a picture to a circle or rounded box (10-19 item 13). M.
8. BPMN element set (10-19 item 9). M.
9. Pages inside one board (draw.io's page tabs); boards and frames stand in. L, not planned.
10. Rulers and units. M, not planned for a student's board.

## Placed from INBOX, 2026-10-26

1352. **The owner, 2026-10-26, verbatim** (screenshot: PaintZ, a dark two-row icon toolbar with file, undo and redo on the left; select, lasso, eraser, picker, pencil, fill, spray, brush, text, line, curve, polygon, rectangle, rounded rectangle and ellipse tools; a line-width dropdown; outline, fill and both toggles; a two-row palette with a large current-colour swatch; fullscreen, info, settings and help on the right; a status bar with canvas size, cursor position and a zoom slider). "hey btw Ive just looked up simple paint web apps asn some of them have A LOT more refined functionality and ui and look soooo much more professional than tessellate. can you use them to update the whiteboard AND quick sketch in both UI/UX as well as functionality, features, quality, utility, how each feature works etc?? look at these repos: https://paintz.app/ (https://github.com/ZMYaro/paintz.git - I also just forked this repo), https://github.com/uthsobcb/ongkon.git, also small things for when the user tries to draw a shape like does it draw from the corner or middle and are all the format object properties that should be there present? do they funtion as they should? are the controls formatted properly?? the whiteboard, mindmap and quicksketch all need a ui improved UX usability and learnability redesign and upgrade"
    Placed: agent `paint-1026` (Opus, design judgement): audit PaintZ and Ongkon against the board, the map and Quick sketch (tools, shape drawing origin and modifiers, format properties and whether each works, control layout, status bar, palette), a measured gap table in `archive/agent-remaining/paint-1026.md`, then build the top gaps by impact with sweeps. Licence: ideas only unless the source licence allows AGPL inclusion (ANALYSIS.md).

1354. **The owner, 2026-10-26, verbatim** (the board half of CHAT_PLAN 1353). "the whiteboards, mindmap and quicksketch needs a lot better modern and professional ui and ux and design of controls and they need refinement, often I find the actual interaction with objects themselves like rotating them, resizing, moving them, editing them, using the popup tool bars is very finikey and sometimes those popup toolbars stretch nearly the whole width fo the screen. the usage of tools, functionality, learnability, thinsg like active and non active like group changes to ungroup when objects are grouped instead of showing both buttons, can groups be stacked? so if I have 7 items and group 5 but then highlight the grouped 5 and the other two can It group them all again and then if I ungroup them the 5 will also remain grouped?? its all the small features and functions and refinements like these that make or break the functionality and reliabilkity of an application, causing the user to not want to use it as it is unreliable."
    Placed: added to agent `paint-1026`'s brief: handle hit areas and drag feel (rotate, resize, move, edit), popup toolbar width cap, Group/Ungroup as one state-aware control, nested groups (group of groups; ungrouping the outer keeps the inner).

1355. **The owner, 2026-10-26, verbatim** (follows 1354). "its not just that, its resizing, view, does control +/- zoom in ongenerally or center on a selected or object or group selection?? what about linking, copy and pasting and cutting with multiple objects, using templates, more templates of the mindmapa nd whiteboard, more elements, more things I can do in the formatting panel and tools, a lot of functionality and utility and features are still missing"
    Measured 2026-10-26: Ctrl+= and Ctrl+- scale by 1.2 and 0.8 about the view's centre (`whiteboard.js` keydown, `wbZoom.scaleBy`), never about the selection; Shift+1 fits the board, Shift+2 (wb2) the selection. Placed: agent `wb3-1026` (Sonnet): zoom about the selection when one exists, multi-object copy, cut and paste (links between copied items kept, offset paste, paste in place), linking, templates (more board and map templates, a picker with previews), more elements (shape library), and the formatting panel's missing properties, measured against draw.io and PaintZ. `paint-1026` keeps interaction, toolbars, groups and Quick sketch.

1356. Board paste options and Paste special: built (`wbpaste-1026`); moved to HISTORY.md, "Moved from the plans, 2026-10-26 (wbpaste-1026)".

## Placed from INBOX, 2026-10-26b

1358. **The owner, 2026-10-26, verbatim.** "also keep improving all the main features like the whitebaord, mindmap and document editor, there are still A LOT of issues with them which keep being missed. as well as missing features or features that dont work properly, both of which I keep easily encountering."
     Placed: after the current three agents, one dogfood-and-fix agent per surface (whiteboard, mind map, document editor): a blind-tester pass on everyday tasks first (find what is missed, not what is listed), each finding fixed as a class, then the surface's open inventory rows (.claude/inputs/open-inventory-1026.md) by impact. Missing features are measured against the competitor reads in ANALYSIS.md and WORLD_CLASS_PLAN.

## Placed from INBOX, 2026-10-27

1403. **The owner, 2026-10-27, verbatim** (screenshots, dark: a sticky with "test note" selected and the inline bar B, I, S, highlight, code, link, list over it; a connector's context bar "Line, Curved, Label, duplicate, delete, ⋯" with its ⋯ menu open, whose top holds Start: None, End: Filled triangle, Medium, Solid as pills wrapping onto three ragged rows, Solid alone and indented after a stray divider). "I wan tot be able to change more things liek the text sise, font and other things like I can change on adobe indesign. and I want to be able to highlight specific text and change only that. also the top of this menu is poorly formatted and structured"
     Placed: (1) the inline bar on selected text gains size, font, colour and highlight colour that apply to the selected run only (stored as runs, survives save, export and undo), with the Format panel's object-wide text controls (size, font, align, line height, letter spacing) reachable from it; (2) the ⋯ menu's top is one labelled grid (Start, End, Weight, Dash), aligned, no orphan row or stray divider, measured at 1280 and 390 wide; fix the class across every context bar's ⋯ menu. One Sonnet agent when a slot frees.

1404. Drag a connector label by its words: built (`wb-1027`); moved to HISTORY.md, "Moved from the plans, 2026-10-27 (wb-1027)".
