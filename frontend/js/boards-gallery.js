// boards-gallery.js: the Boards & maps sub-tab's gallery, out of whiteboard.js so it
// paints without waiting for the 2.3 MB of board code to be fetched and run (INBOX 1772).
// Loads with the `library` files (app.js `LAZY_MODULES`) and on its own as
// `boardsGallery` the first time the sub-tab is reached or pressed (library.js).
// Everything it calls in the board code is a stand-in (lazy-entries.js `boards`) that
// fetches the bundle first, and only runs from a click on a card or its menu.

//: Sorting for the Whiteboards sub-tab, the fifth and last list to get it
//: ("the library subtabs are missing sorting and filtering options").
//:
//: `BoardOut` (routes_whiteboard.py) carries no timestamps at all, so there is
//: no honest "newest first" here: a board's `id` is the only thing that
//: orders by age, and it does, because a board *is* an Entry and entry ids
//: rise with creation. Named "Newest first" rather than "Highest id" because
//: that is what it means to the person reading it.
//:
//: The default board (`id === null`) is pinned first under every sort. It is
//: the one board that always exists and cannot be renamed or deleted, the
//: gallery already treats it as a fixed landmark (no tick, no ⋯ menu), and a
//: sort that shuffled it into the middle of the list would take that away.
const BOARD_SORTS = {
  newest: (a, b) => (b.id || 0) - (a.id || 0),
  oldest: (a, b) => (a.id || 0) - (b.id || 0),
  az: (a, b) => String(a.title || "").localeCompare(String(b.title || ""), undefined, { sensitivity: "base" }),
  za: (a, b) => String(b.title || "").localeCompare(String(a.title || ""), undefined, { sensitivity: "base" }),
  fullest: (a, b) => boardItemCount(b) - boardItemCount(a),
  //: Looked up when it runs: library.js, which defines `libraryCustomCmp`, is the last file of the bundle.
  custom: (a, b) => libraryCustomCmp("boards", (board) => `${board.type === "map" ? "map" : "board"}:${board.id}`)(a, b),
};

const BOARD_SORT_KEY = "library-boards-sort";

function boardItemCount(board) {
  return (board.node_count || 0) + (board.sketch_count || 0) + (board.object_count || 0);
}

function boardSort() {
  const stored = prefs.get(BOARD_SORT_KEY, null);
  return BOARD_SORTS[stored] ? stored : "newest";
}

//: On `window` because `syncLibraryBoardsTicks` (library.js) rebuilds this
//: same list to line the *n*th checkbox up with the *n*th card. Its own
//: comment says it must apply "the exact same filter"; a sort is now part of
//: that, and a second copy of this function would tick the wrong boards the
//: first time the two drifted.
window.wbVisibleBoards = function wbVisibleBoards(boards, needle) {
  const listed = boards.filter(libraryListsBoard);
  const shown = needle
    ? listed.filter((b) => String(b.title || "").toLowerCase().includes(needle))
    : listed;
  shown.sort(BOARD_SORTS[boardSort()]);
  const fixed = shown.filter((b) => b.id === null);
  return fixed.length ? [...fixed, ...shown.filter((b) => b.id !== null)] : shown;
};

onDomReady(() => {
  const select = $("library-boards-sort");
  if (!select) return;
  select.value = boardSort();
  select.addEventListener("change", () => {
    prefs.set(BOARD_SORT_KEY, select.value);
    redrawLibraryBoardsGallery();
  });
});

window.renderLibraryBoardsGallery = renderLibraryBoardsGallery;
window.redrawLibraryBoardsGallery = redrawLibraryBoardsGallery;

//: **The sub-tab's press** (library.js): show the landing and draw the cards. With the board code in, that is
//: `wbShowBoardsLanding` (it also leaves a board that is open); without it, the cards alone, drawn here, and then
//: the board code is asked for in idle time, once they are up, so it never sits ahead of the first paint and a
//: card or New board finds it in (INBOX 1772). A property of the function, not a new name in the shared scope.
renderLibraryBoardsGallery.show = async function showBoardsGallery() {
  //: A board opened by code presses this sub-tab itself (`openWhiteboardBoard`), and this runs once the gallery file
  //: has loaded, which can be after the canvas is up: the landing then hid the map the import had just opened.
  const opening = window.openWhiteboardBoard?.at;
  if (opening && performance.now() - opening < 5000 && !$("wb-canvas-view")?.classList.contains("hidden")) return;
  if (window.initWhiteboard) return wbShowBoardsLanding();
  await renderLibraryBoardsGallery();
  const load = () => ensureModule("boards");
  window.requestIdleCallback ? requestIdleCallback(load, { timeout: 3000 }) : setTimeout(load, 300);
};

//: Maps / Boards / All (MINDMAP_PLAN.md §5 item 10). Which one is showing.
//: In `localStorage` for the same reason the view mode and the sort already
//: are: a filter you have to set again on every visit is one you stop using.
const BOARD_FILTER_KEY = "library-boards-filter";
const BOARD_FILTERS = [
  { key: "all", label: "All", icon: "ph:squares-four", type: null },
  { key: "map", label: "Maps", icon: "ph:tree-structure", type: "map" },
  { key: "board", label: "Boards", icon: "ph:pencil-simple-line", type: "board" },
];

function boardTypeFilter() {
  const stored = prefs.get(BOARD_FILTER_KEY, null);
  return BOARD_FILTERS.some((f) => f.key === stored) ? stored : "all";
}

//: The Maps / Boards / All narrowing, in one place for the same reason
//: `wbVisibleBoards` is: `syncLibraryBoardsTicks` (library.js) rebuilds the
//: list the gallery drew to line each tick up with its card, and without this
//: it counted every board while the grid showed one kind, so the lengths
//: never matched and no tick was attached while Maps or Boards was on.
window.wbBoardsOfTypeFilter = function wbBoardsOfTypeFilter(boards) {
  const wanted = BOARD_FILTERS.find((f) => f.key === boardTypeFilter())?.type ?? null;
  return wanted ? boards.filter((b) => (b.type || "board") === wanted) : boards;
};

//: The chip row itself. `.library-chip`, the app's own filter-chip recipe,
//: with the count on the chip, the Everything sub-tab's rule and for the same
//: reason: a filter you have to press to discover is empty wastes a click
//: every time, and with three of them that is the whole row.
function renderBoardTypeFilter(counts) {
  const box = $("library-boards-filter");
  if (!box) return;
  const active = boardTypeFilter();
  box.replaceChildren();
  for (const filter of BOARD_FILTERS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `library-chip${filter.key === active ? " active" : ""}`;
    button.dataset.boardFilter = filter.key;
    button.setAttribute("aria-pressed", String(filter.key === active));
    const icon = document.createElement("span");
    setLabel(icon, filter.icon);
    icon.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = filter.label;
    button.append(icon, label);
    if (counts) {
      const badge = document.createElement("span");
      badge.className = "library-chip-count";
      badge.textContent = String(counts[filter.key] ?? 0);
      button.appendChild(badge);
    }
    button.addEventListener("click", () => {
      prefs.set(BOARD_FILTER_KEY, filter.key);
      redrawLibraryBoardsGallery();
    });
    box.appendChild(button);
  }
}

//: **The last list drawn, and its text** (INBOX 496: "it takes a while to load
//: the boards and maps library subtab"). A visit redraws only if the server's
//: answer differs from what is already drawn; the search box, sort, chip and
//: view switch redraw from it without a request (each keystroke was a fetch).
let libraryBoardsLast = null;
let libraryBoardsLastText = "";

//: A redraw that needs no new data. Falls back to a full render the first time.
function redrawLibraryBoardsGallery() {
  if (libraryBoardsLast) drawLibraryBoardsGallery(libraryBoardsLast);
  else renderLibraryBoardsGallery();
}

async function renderLibraryBoardsGallery() {
  const grid = $("library-boards-grid");
  if (!grid) return;
  // Always the unfiltered list, then narrowed here. `?type=` exists and works
  // (§9.3), but the chips carry counts, and counts for the two kinds you are
  // *not* looking at cannot come from a request that excluded them, asking
  // three times to draw one row would be three round trips for one small
  // array. The server-side filter earns its place for a caller that wants only
  // maps and no counts; this one wants both.
  // And to the end, for the same reason `refreshBoardList` reads it that way:
  // the chips below count what came back, so a first page would make the
  // counts a count of the first page.
  //: The grid keeps its last cards while hidden, so a revisit shows them at
  //: once; skeletons only when there is nothing yet.
  const had = libraryBoardsLast;
  if (!had) showSkeletons(grid, 4);
  //: The list the sub-tab press already asked for (library.js), used once and
  //: only while young: one that waited out a slow bundle is asked for again.
  const early = window.libraryBoardsPrefetch;
  window.libraryBoardsPrefetch = null;
  const listed = await (early && Date.now() - early.at < 5000
    ? early.list
    : apiPagedList("/whiteboard/boards", 200, { silent: true }).catch(() => null));
  if (!had) clearSkeletons(grid);
  //: The board made a moment ago is part of what is drawn (see below).
  const text = listed ? JSON.stringify(listed) + (window.wbLastCreatedBoard?.id ?? "") : "";
  if (had && listed && text === libraryBoardsLastText) return;
  libraryBoardsLast = listed;
  libraryBoardsLastText = text;
  drawLibraryBoardsGallery(listed);
}

function drawLibraryBoardsGallery(listed) {
  const grid = $("library-boards-grid");
  const empty = $("library-boards-empty");
  const noMatch = $("library-boards-no-match");
  if (!grid) return;
  const boards = listed && listed.filter(libraryListsBoard);
  if (!boards) {
    grid.replaceChildren();
    if (empty) surfaceFailed(empty, "your boards", renderLibraryBoardsGallery);
    noMatch?.classList.add("hidden");
    return;
  }
  surfaceRecovered(empty);
  nounCount.dock("library-boards", boards.length, "board or map", "boards and maps");
  // See `createNewBoard`'s own comment: a board with nothing on it yet
  // doesn't come back from the server at all.
  const created = window.wbLastCreatedBoard;
  if (created && !boards.some((b) => b.id === created.id)) {
    boards.push({ ...created, node_count: 0, sketch_count: 0, object_count: 0 });
  }
  // Counted before the filter, so each chip says how many it *would* show.
  const counts = { all: boards.length, map: 0, board: 0 };
  for (const b of boards) counts[b.type === "map" ? "map" : "board"] += 1;
  renderBoardTypeFilter(counts);
  //: The picker's static "Default board" row is not a board while the gallery
  //: counts none: count and list say the same thing (audit 1018, item 11).
  if (!boards.length && window.currentBoardId == null) {
    for (const opt of $("wb-board-select")?.querySelectorAll('option[value=""]') || []) opt.remove();
  }
  window.wbBoardsAll = boards;
  const inScope = window.wbBoardsOfTypeFilter(boards);
  const needle = ($("library-boards-search")?.value || "").trim().toLowerCase();
  const shown = window.wbVisibleBoards(inScope, needle);
  //: `.library-list` is the Library's own rows mode (00-tokens-shell.css) and
  //: a board card is already a `.library-card`, so this is the whole change:
  //: the same class the All sub-tab toggles, driven by the same preference.
  const rowsMode = prefs.get("libraryView", null) === "list";
  grid.classList.toggle("library-list", rowsMode);
  grid.replaceChildren();
  if (!shown.length) {
    const isFilteredEmpty = Boolean(needle) && boards.length > 0;
    empty?.classList.toggle("hidden", isFilteredEmpty);
    noMatch?.classList.toggle("hidden", !isFilteredEmpty);
    if (noMatch && isFilteredEmpty) {
      noMatch.textContent = `No boards match “${needle}”.`;
    }
    return;
  }
  empty?.classList.add("hidden");
  noMatch?.classList.add("hidden");
  for (const board of shown) {
    // An `<article>`, the same shape libraryCard() and the Documents
    // subtab's doc-list-item use: a plain <button> can't also host the
    // kebab menu's own <button>, and reported live: "can't rename or delete
    // a board from the Whiteboards subtab", the exact gap that shape
    // already closed for documents. Not a button by role either (INBOX
    // 433): the title opens it, stretched over the card (`cardOpener`).
    const card = document.createElement("article");
    card.className = "library-card library-board-card";
    card.wbBoard = board; // the tick's board (`syncLibraryBoardsTicks`)
    //: What a drag, a copy and the tray read the card as (obj-ref.js).
    Object.assign(card.dataset, { obj: `${board.type === "map" ? "map" : "board"}:${board.id}`, objTitle: board.title });
    const open = () => openWhiteboardBoard(board.id);
    card.addEventListener("click", open);

    const top = document.createElement("div");
    top.className = "library-card-top";
    const icon = document.createElement("span");
    icon.className = "library-card-icon";
    // A map and a board share this sub-tab, so the icon is the one thing on
    // the card that says which of the two you are looking at before you read
    // the title: the same icon the top bar's Map chip and the New mind map
    // action use, so the three agree.
    const isMapCard = board.type === "map";
    setLabel(icon, isMapCard ? "ph:tree-structure" : "ph:squares-four");
    icon.setAttribute("aria-hidden", "true");
    top.appendChild(icon);

    const title = document.createElement("strong");
    title.className = "library-card-title";
    title.textContent = board.title;
    cardOpener(title, open, `${board.title}, ${isMapCard ? "map" : "board"}`);

    const meta = document.createElement("span");
    meta.className = "muted library-card-meta";
    // One sentence about how much is on a board, shared with every other
    // surface that says it, `mapCountLabel` in note-cards.js. It used to be nine
    // lines here and four in the dashboard's own widget, which is how the two
    // came to disagree about what to call a map's objects.
    const count = document.createElement("span");
    count.textContent = mapCountLabel(board);
    meta.appendChild(count);
    //: **When it last changed**, which every other Library card says and this
    //: one did not (pass2.md, Remaining 2: `/whiteboard/boards` sent no time).
    //: Drawn exactly as the Library's own card foot draws it
    //: (`.library-card-when` in library.js: relative, the full time on hover),
    //: so a board and a document side by side in the Library read the same
    //: way. `updated_at` is the later of the note's edit and the last thing
    //: drawn on the board (`list_boards`).
    if (board.updated_at) {
      const when = document.createElement("span");
      when.className = "library-card-when";
      when.textContent = relativeTime(board.updated_at);
      when.title = `Changed ${whenText(parseServerTime(board.updated_at) || new Date(board.updated_at))}`;
      meta.appendChild(when);
    }

    // **A thumbnail of the board itself**, rather than the same icon on every
    // card. Asked for directly: the Boards & maps sub-tab is "boring and
    // should probably have previews".
    //
    // `mapPreview` (note-cards.js) is now the only place this picture is drawn.
    // MINDMAP_PLAN.md §5 item 12 asked for exactly one preview renderer, and
    // the reason was already visible here: this card drew the tree edges, the
    // labels and the sketch squiggles, while the dashboard's boards widget
    // drew the same `preview_items` with none of them, so the one fact that
    // tells a map from a board was missing from one of the two places a map
    // shows up. An empty board still draws nothing and keeps its "Empty
    // board" line, which says more than a blank rectangle would.
    //: Every board gets one, including an empty one: `mapPreview` draws the
    //: designed empty state itself now. This used to be a three-way branch,
    //: with a hand-made dashed `<span>` for rows mode only, because the rows
    //: whose board had a preview pushed their title 34px right of the rows
    //: whose board did not (measured: 107px, 155px and 189px on three
    //: consecutive rows). One picture per board, one left edge.
    const minimap = mapPreview(board, { size: "card" });
    card.append(top, title, minimap, meta);

    // The default (id === null) scratch board isn't a note and can't be
    // renamed or deleted the way a real board (a plain Entry: see
    // create_board in routes_whiteboard.py) can.
    if (board.id !== null) {
      //: One rename path for Rename and Suggest a name: undoable, and the gallery redrawn.
      const renameBoardWithUndo = async (next) => {
        const named = (title) => apiJson(`/whiteboard/boards/${board.id}`, {
          method: "PUT",
          body: JSON.stringify({ title }),
        }).then(() => renderLibraryBoardsGallery());
        try {
          await named(next);
          pushUndo(`Renamed "${board.title}"`, () => named(board.title), () => named(next));
        } catch (e) {
          toast(e.message, true);
        }
      };
      const menu = kebabMenu(
        [
          //: The shared "act on this" row (INBOX 393): a board or a map can
          //: be taken to the chat that answers about it, like a note.
          makeMenuItem("ph:chat-circle Ask Atlas about this", "Start a chat about this board or map", () =>
            askAtlasAboutThing(board.type === "map" ? "map" : "board", board.title)
          ),
          //: A board is an `Entry`, so its reminder is an `entry_id` one; the
          //: row in Reminders opens the board (WORLD_CLASS_PLAN 1.3, row 15).
          makeMenuItem("ph:alarm Remind me", "Set a reminder about this board or map", () =>
            remindAbout({ title: board.title, entryId: board.id })
          ),
          makeMenuItem("ph:pencil-simple Rename", "Rename this board", async () => {
            const next = await promptDialog("Rename this board", board.title);
            if (next) await renameBoardWithUndo(next);
          }),
          //: L348: the model names it from what is on it, else its first words do; renamed through Rename's undoable path.
          makeMenuItem("ph:sparkle Suggest a name", "A name from what is on this board", async () => {
            const got = await apiJson(`/whiteboard/boards/${board.id}/suggest-title`, { method: "POST" }).catch((e) => toast(e.message, true));
            if (got?.title && got.title !== board.title) await renameBoardWithUndo(got.title);
          }),
          //: L280: named from what is on it, as a document is (INBOX 904
          //: B17); renamed through Rename's undoable PUT.
          makeMenuItem("ph:sparkle Suggest a name", "A name from what the board or map says", async () => {
            const named = (title) => apiJson(`/whiteboard/boards/${board.id}`, {
              method: "PUT",
              body: JSON.stringify({ title }),
            }).then(() => renderLibraryBoardsGallery());
            try {
              const got = await apiJson(`/whiteboard/boards/${board.id}/suggest-title`, { method: "POST" });
              if (!got?.title || got.title === board.title) return;
              await named(got.title);
              pushUndo(`Renamed "${board.title}"`, () => named(board.title), () => named(got.title));
            } catch (e) {
              toast(e.message, true);
            }
          }),
          // ROADMAP.md item 8: creating, listing and renaming a map all
          // worked; duplicating did not exist, and it is the one that makes a
          // map reusable: a laid-out map is a template for the next one.
          // The copy is deep server-side (its cards are new notes), so
          // editing it cannot rewrite the original's.
          makeMenuItem("ph:copy Duplicate", "Make a copy of this board", async () => {
            try {
              const copy = await apiJson(`/whiteboard/boards/${board.id}/duplicate`, {
                method: "POST",
              });
              renderLibraryBoardsGallery();
              pushUndo(`Copied "${board.title}"`, () => wbBinBoard(copy.id, false), () => wbBinBoard(copy.id, true));
              toast(`Copied to “${copy.title}”`);
            } catch (e) {
              toast(e.message, true);
            }
          }),
          //: The same action the open board's own menu carries (INBOX 309),
          //: here because the gallery is where boards are browsed and the
          //: one you want in a note is usually one you are looking at in a
          //: list rather than one you have opened.
          makeMenuItem("ph:note-pencil Add to a note", "Put this board in a note as an object", async () => {
            await addBoardToNote(board);
          }),
          appLinkMenuItem(board.type === "map" ? "map" : "board", board.id),
          makeMenuItem("ph:trash Delete", "Delete this board", () => wbDeleteBoard(board.id, board.title)),
        //: Six rows is past the ceiling (DESIGN.md): what you do to it, its
        //: address, and the row that ends it.
        ].map((item) => ({ ...item, group: /Copy app link/.test(item.label) ? "copy" : /Delete/.test(item.label) ? "end" : "act" })),
        `Actions for "${board.title}"`
      );
      menu.classList.add("library-card-menu");
      menu.addEventListener("click", (event) => event.stopPropagation());
      card.appendChild(menu);
    }

    grid.appendChild(card);
  }
}

//: **New's arrow** (INBOX 1520): the main press makes a blank board, and this
//: menu holds the other starts. A map is made at once and named "Untitled map
//: N" (MINDMAP_PLAN 15 row 1); From a template is the dialog, whose Mind map
//: tab holds the map templates. The rows keep the ids the old menu's rows had,
//: so the Library's and the Dashboard's New board and New mind map reach them.
//: Built here, with the cards, so the arrow is there when they are; each row waits
//: for the board code (`ensureModule` is instant once it has run) before it acts.
function wbNewMenuMount() {
  const slot = $("wb-boards-new-slot");
  if (!slot || slot.firstChild) return;
  const afterBoards = (act) => () => ensureModule("boards").then(act);
  const wrap = kebabMenu([
    { label: "ph:note-pencil Whiteboard", title: "An empty canvas you arrange by hand", run: afterBoards(() => wbNewUntitledBoard()) },
    { label: "ph:tree-structure Mind map", title: "Topics branching from one central idea", run: afterBoards(() => wbNewUntitledBoard("map")) },
    { label: "ph:squares-four From a template", title: "Kanban, planning and decision boards, and map shapes", run: afterBoards(() => createNewBoard("board", { reveal: true })) },
  ], "Other ways to start a board");
  const opener = wrap.querySelector(":scope > button");
  const menu = wrap.querySelector(":scope > .action-menu");
  const rows = menu.querySelectorAll(".menu-item");
  rows[1].id = "wb-boards-new-map";
  rows[2].id = "wb-boards-new-template";
  opener.id = "wb-boards-new-more";
  opener.classList.remove("icon-only", "ghost");
  opener.classList.add("split-button-caret");
  setLabel(opener, "ph:caret-down");
  opener.title = "More ways to start: a mind map or a template";
  slot.replaceChildren(wrap);
}

//: The gallery's own two controls: its search box and the Reload button beside "+ New board".
onDomReady(() => {
  wbNewMenuMount();
  //: The landing's other buttons are wired by the board code (whiteboard.js), which is fetched after the
  //: cards are up. A press before it has run fetches it, then presses again.
  $("wb-boards-landing")?.addEventListener("click", (event) => {
    if (window.initWhiteboard) return;
    const button = event.target.closest?.("#wb-boards-new, #library-boards-new-map, #wb-boards-generate, #wb-boards-import");
    if (!button) return;
    event.stopPropagation();
    event.preventDefault();
    ensureModule("boards").then(() => button.click());
  }, true);
  //: A file dragged over the landing starts the board code loading, and one let go before it has run is
  //: held, then dropped again once it has (an unhandled drop would make the browser open the file).
  const landing = $("wb-boards-landing");
  const carriesFile = (e) => [...(e.dataTransfer?.items || [])].some((i) => i.kind === "file");
  landing?.addEventListener("dragover", (e) => {
    if (window.initWhiteboard || !carriesFile(e)) return;
    e.preventDefault();
    ensureModule("boards");
  }, true);
  landing?.addEventListener("drop", (e) => {
    const file = e.dataTransfer?.files?.[0];
    if (window.initWhiteboard || !file) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    ensureModule("boards").then(() => {
      const held = new DataTransfer();
      held.items.add(file);
      landing.dispatchEvent(new DragEvent("drop", { dataTransfer: held, bubbles: true, cancelable: true }));
    });
  }, true);
  $("library-boards-search")?.addEventListener("input", redrawLibraryBoardsGallery);
  // The Reload button beside "+ New board", now named after what it reloads.
  // It was `library-media-refresh`, a copy-paste leftover from the Media
  // sub-tab, and that name is why it sat unwired for so long: searching the id
  // found a listener that a reader assumed was this button's. Checked before
  // renaming rather than after: the id appears exactly once in index.html and
  // exactly once in the JS, here, and `library.js` does not mention it at all,
  // so the comment this replaces was itself out of date about the Media
  // sub-tab wiring it. `library-boards-refresh` matches the
  // `#library-boards-search` beside it.
  //
  // Its title and aria-label said only "Reload", which on a header holding
  // New board, Import outline and Help does not say reload what.
  $("library-boards-refresh")?.addEventListener("click", renderLibraryBoardsGallery);
});
