// dash-boards.js: the dashboard's Boards & maps widget. Moved out of
// dashboard.js on 2026-10-05 (the boot-script gzip budget, 86 bytes from its
// cap) when the widget gained its large map (INBOX 553(d)); loaded on the
// widget's first draw (`ensureModule("dashBoards")`, app.js), and calls only
// into files that are always there (note-cards.js, dashboard.js).

//: **The busiest map, drawn large, at its own shape** (INBOX 553(d), the
//: owner's decision: the widget is "dynamic depending on map size and
//: scale"). The rows' 40px thumbnails letterbox every board into the same
//: square, so a map was a smudge. The first board gets the widget's width and
//: a height that follows it: its natural height at that width (the width over
//: the map's own aspect), at least `min` so a long thin map is still a
//: picture, at most `small` when the map has only a few topics (so three
//: boxes are drawn at a readable size, not blown up to fill a card), and at
//: most `max` otherwise, past which the whole map is fitted inside (the
//: preview's `meet`), so a tall map gets a taller card up to a limit and is
//: then shown whole.
const DASH_MAP_FEATURE = Object.freeze({ min: 96, small: 168, max: 320, smallItems: 6 });

function dashMapFeatureHeight(width, aspect, items) {
  const shape = Number(aspect) > 0 ? Number(aspect) : 1;
  const natural = Number(width) / shape;
  const cap = Number(items) <= DASH_MAP_FEATURE.smallItems ? DASH_MAP_FEATURE.small : DASH_MAP_FEATURE.max;
  return Math.round(Math.max(DASH_MAP_FEATURE.min, Math.min(cap, natural)));
}

//: The large picture, one button (the board embed's recipe, DESIGN.md: the
//: whole card is the press), sized now and again whenever the widget's width
//: changes (Wide and Narrow, a window resize).
function dashMapFeature(board) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "dash-board-feature";
  const kind = board.type === "map" ? "map" : "board";
  //: No aria-label: the name is the visible caption (title and count, WCAG 2.5.3);
  //: the tooltip says what a press does.
  button.title = `Open the ${kind} ${board.title}`;
  const svg = mapPreview(board, { size: "card" });
  svg.classList.add("dash-board-feature-map");
  button.appendChild(svg);
  //: Its name and what is on it, in the rows' own type, under the picture.
  const caption = document.createElement("span");
  caption.className = "dash-board-feature-caption";
  const name = document.createElement("span");
  name.className = "dash-list-title";
  name.textContent = board.title;
  const meta = document.createElement("span");
  meta.className = "dash-list-preview";
  meta.textContent = mapCountLabel(board);
  caption.append(name, meta);
  button.appendChild(caption);
  button.addEventListener("click", () => openWhiteboardBoard(board.id));
  const items = Array.isArray(board.preview_items) ? board.preview_items.length : 0;
  //: INBOX 1415: the width is the observer entry's, not a layout read.
  new ResizeObserver(([{ contentRect }]) => {
    if (contentRect.width > 0) svg.style.height = `${dashMapFeatureHeight(contentRect.width, board.preview_aspect, items)}px`;
  }).observe(button);
  return button;
}

async function dashRenderBoards(body) {
  // Every board, not the first page: the widget ranks them by how much is on
  // them, and the busiest board is not necessarily on page one. That is the
  // same walk `loadMapBoardIndex` (note-cards.js) makes for the note list's map
  // chips, with the same page size, and at boot the two ran within a tick of
  // each other: two walks of every board before the first tab had finished
  // drawing (WORLD_CLASS_PLAN A2). Sharing it means the widget can read
  // counts up to the index's eight seconds old, which is the age at which a
  // board's node count changes the order of a five-row list and nothing more.
  await loadMapBoardIndex().catch(() => null);
  const boards = mapBoardRows().filter(libraryListsBoard);
  const usable = boards.filter((b) => (b.node_count + b.sketch_count + (b.object_count || 0)) > 0);
  if (!usable.length) {
    //: An empty board is left out of the ranking, so a notebook with only
    //: empty boards used to be told to draw one (INBOX 446 (5), seen with a
    //: board called "Launch plan" sitting in the Library).
    dashEmpty(
      body,
      boards.length
        ? "Nothing on your boards yet. Add a card or a sketch to one and it shows up here."
        : "Draw a board or build a mind map and it will show up here.",
      boards.length
        ? { label: "ph:squares-four Open boards", run: "tab", tab: "library", sub: "library-view-whiteboard" }
        : { label: "ph:plus New board", run: "new-board", tab: "library", sub: "library-view-whiteboard" },
    );
    return;
  }
  // Busiest first. `GET /whiteboard/boards` has no updated_at to sort on, and
  // "the board with the most on it" is a better answer than "whichever row
  // the database returned first", which is what an unsorted list would be.
  const ranked = [...usable]
    .sort(
      (a, b) =>
        b.node_count + b.sketch_count + (b.object_count || 0) -
        (a.node_count + a.sketch_count + (a.object_count || 0)),
    )
    .slice(0, 5);
  //: The first, large and at its own shape (INBOX 553(d)); the rest as rows.
  body.appendChild(dashMapFeature(ranked[0]));
  const ul = document.createElement("ul");
  ul.className = "dash-list";
  for (const board of ranked.slice(1)) {
    dashActionRow(ul, {
      title: board.title,
      // `mapCountLabel` (note-cards.js) rather than three lines here. The three lines
      // it replaces called a map's objects "images", which is the wrong noun
      // for the only thing on a map, the Library card had already been fixed
      // and this copy had not, which is precisely what §5 item 12 is about.
      meta: mapCountLabel(board),
      hint: board.type === "map" ? "Open this map" : "Open this board",
      thumb: dashBoardThumb(board),
      // `openWhiteboardBoard` handles the tab and sub-tab switch itself.
      onOpen: () => openWhiteboardBoard(board.id),
      // **A map says it is one, in the row.** The row's title is a bare
      // string, so before this a map and a whiteboard were the same row with
      // different words in it. `mapChip` is the app's one map chip, so this
      // reads identically to a map in a note, on the timeline and in the chat.
      chip: board.type === "map" ? mapChip(board, { count: false, interactive: false }) : null,
    });
  }
  body.appendChild(ul);
}

/**
 * The same miniature the Library's board cards draw, at widget-row size.
 *
 * **One renderer, not two.** This used to be its own 20-line copy that drew
 * `preview_items` and nothing else, no `preview_edges`, so a map in the
 * dashboard previewed as a scatter of dots while the identical map in the
 * Library previewed as a tree. Structure is the entire difference between a
 * map and a board, so the one place it was missing was the one place it
 * mattered. `mapPreview` (note-cards.js) is now the only place this picture exists;
 * MINDMAP_PLAN.md §5 item 12 asked for exactly that.
 */
function dashBoardThumb(board) {
  // Never null now: an empty board draws the designed empty state rather than
  // leaving the row without its left rail (see mapPreview). The guard stays
  // for a caller that hands this a board object it does not have yet.
  const svg = mapPreview(board, { size: "row" });
  if (!svg) return null;
  // The row's own thumbnail classes, on top of the shared `.board-minimap`
  // ones: sizing belongs to the row, the drawing belongs to the map.
  svg.classList.add("dash-list-thumb", "dash-board-thumb");
  return svg;
}
