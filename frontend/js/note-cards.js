// note-cards.js: map chips and previews, the board index, entryItem (the note
// card). Moved out of app.js on 2026-09-26 as one contiguous range (INBOX 426
// cc, docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- one map chip and one map preview, used everywhere ----------------------
//
//: MINDMAP_PLAN.md §5 item 12, and the sentence in it that is the whole
//: reason this exists: *"One `mapChip()` and one `mapPreview()`, used by all
//: of them: the app's recurring failure is the same object drawn five
//: ways."*
//:
//: It had already happened twice before this was written. The Library's board
//: card (`renderLibraryBoardsGallery`, whiteboard.js) drew the minimap with
//: edges, labels, a sketch squiggle and an edge-aware label side; the
//: dashboard's boards widget (`dashBoardThumb`, dashboard.js) drew the *same*
//: `preview_items` at a different scale with **no edges at all**, so the one
//: fact that distinguishes a map from a board was missing from one of the two
//: places a map appears. Neither was wrong on its own; they were two opinions
//: of one picture.
//:
//: Lives in app.js because five files draw these, whiteboard.js, dashboard.js,
//: the timeline and the note renderer here, and the chat transcript, and
//: app.js is the one loaded before all of them (see index.html's script
//: order).

//: Take, discard or restore a suggested tag: tag-suggest.js's
//: `answerSuggestedTags` (lazy: the boot gzip ratchet), fetched on the press.
function answerTags(entry, body) {
  ensureModule("tagSuggest").then(() => answerSuggestedTags(entry, body));
}

//: A miniature of what is on a board (map-preview.js draws it: lazy, for the boot
//: gzip ratchet). The svg comes back empty at once, so every caller can class and
//: place it, and the drawing lands in it when the file is in (a microtask later
//: once it is). An empty board draws the empty state there, not nothing.
function mapPreview(board, { size = "card" } = {}) {
  //: The stored thumbnail (board-raster.js, lazy) when this board has a current one.
  if (board?.thumb_v && window.mapRaster) return mapRaster(board, size);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", `board-minimap board-minimap-${size}`);
  svg.setAttribute("aria-hidden", "true");
  ensureModule("mapPreview").then((ok) => ok && mapPreviewDraw(svg, board, size));
  return svg;
}

//: How many things are on a board, as the sentence a person reads. On a map
//: the objects *are* the nodes, so calling them "images", which every surface
//: did before maps existed, is simply the wrong noun for the only thing on
//: the board.
function mapCountLabel(board) {
  const isMap = board?.type === "map";
  const nodes = board?.node_count || 0;
  //: **Links, not "sketches"** (audit 2026-10-05, UX-06): a concept map of
  //: three cards and two lines read "3 cards · 2 sketches", the storage's
  //: word for what a person drew as connections. `link_count` is how many of
  //: the sketches are connectors; the rest are drawings.
  const links = board?.link_count || 0;
  const sketches = Math.max(0, (board?.sketch_count || 0) - links);
  const objects = board?.object_count || 0;
  const parts = [];
  if (nodes) parts.push(nounCount(nodes, "card"));
  if (links) parts.push(nounCount(links, "link"));
  if (sketches) parts.push(nounCount(sketches, "drawing"));
  if (objects) {
    //: **"items", not "images", on a board.** `object_count` is
    //: `count(WhiteboardObject)` with no filter on `kind`
    //: (`routes_whiteboard.py`, the `/whiteboard/boards` listing), and a
    //: board's objects are text, images, notes, documents, files and links.
    //: A board seeded with five text boxes read "5 images" in the dashboard
    //: widget and in the Library, which is the same class of wrong noun §5
    //: item 12 fixed for a map's nodes and missed here.
    parts.push(isMap
      ? nounCount(objects, "topic")
      : nounCount(objects, "item"));
  }
  return parts.length ? parts.join(" · ") : isMap ? "Empty map" : "Empty board";
}

//: **A map as a chip**: its icon, its title and how many nodes it holds, and
//: pressing it opens the map. The one control every surface uses to refer to a
//: map in passing: a note body, the timeline, a dashboard row, the chat
//: transcript.
//:
//: A `<button>`, not a link: opening a map is a tab switch plus a board load
//: (`openWhiteboardBoard` does both), not a navigation this app has a URL for.
//: `.map-chip` sits on `.chip`, the app's own recipe, so it inherits the chip
//: height, radius and hover state rather than inventing a fourth pill shape.
//:
//: `board` may be as little as `{id, title}`, the chat transcript has an id
//: and a label and nothing else. The count line is simply omitted then, rather
//: than the chip refusing to draw or claiming "0 nodes".
//:
//: **`interactive: false` draws the same chip as a `<span>` with no handler**,
//: for the one context where the thing around it is already the control: the
//: dashboard's board rows are `role="button"` list items, and a `<button>`
//: inside one is a nested interactive control, two tab stops that do the same
//: thing, which is worse for a keyboard user than no chip at all. The chip is
//: identical to look at either way; only the element and the listener differ.
function mapChip(board, { onOpen = null, count = true, interactive = true } = {}) {
  const chip = document.createElement(interactive ? "button" : "span");
  if (interactive) chip.type = "button";
  chip.className = "chip map-chip";
  const isMap = board?.type !== "board";
  const title = board?.title || "Untitled map";
  setLabel(chip, `${isMap ? "ph:tree-structure" : "ph:squares-four"} ${title}`);
  const known = board && (board.object_count != null || board.node_count != null);
  if (count && known) {
    const meta = document.createElement("span");
    meta.className = "map-chip-count";
    meta.textContent = mapCountLabel(board);
    chip.appendChild(meta);
  }
  chip.title = known
    ? `${title}: ${mapCountLabel(board)}${interactive ? ". Press to open it." : ""}`
    : interactive
      ? `Open “${title}”`
      : title;
  if (interactive) {
    chip.addEventListener("click", (event) => {
      event.stopPropagation();
      if (onOpen) onOpen(board);
      else openWhiteboardBoard(board?.id ?? null);
    });
  }
  return chip;
}

//: Every board the notebook has, by id, for the surfaces that are handed an
//: *entry* id and have to find out whether it is a board.
//:
//: One shared cache rather than a fetch per surface: the timeline paints a
//: hundred dots and the note list paints a chip per wiki link, and neither can
//: afford a request each. `apiJson`'s own `cacheMs` does the de-duplication: 
//: this only holds the id→row index built from it, which is the part that
//: would otherwise be rebuilt per dot.
let mapBoardIndexCache = null;
//: When that cache was last filled. It used to be `apiJson`'s own `cacheMs`
//: doing this, and that stopped working when `GET /whiteboard/boards` became
//: paged: `apiPagedList` walks pages through `api`, which has no read cache,
//: and one first page is not an index of every board anyway. So the eight
//: seconds moved here, onto the thing it was really protecting, which is the
//: index rather than the response.
let mapBoardIndexAt = 0;
const MAP_BOARD_INDEX_MS = 8000;
//: The walk in flight, if there is one. The eight seconds above only help a
//: caller that arrives after an earlier one has *finished*, and at boot they
//: do not arrive like that: the note list and the agent panel both ask within
//: the same tick, both find an empty cache, and both walk every page of
//: `/whiteboard/boards` (WORLD_CLASS_PLAN A2, measured as the same request
//: twice). A second caller joins the first walk instead.
let mapBoardIndexWalk = null;

//: `force` skips the eight seconds. One caller passes it: a note's board
//: object that could not find its board (`boardEmbedElement`). Eight seconds
//: is the right answer for a chip that is merely decorating a row, and the
//: wrong one for a card that is about to tell somebody their board has been
//: deleted: a board made a moment ago is missing from an index built before
//: it existed, and nothing else ever rebuilds that index (every other caller
//: returns early while it is set). A walk already in flight is still joined
//: rather than doubled.
function loadMapBoardIndex(force = false) {
  if (!force && mapBoardIndexCache && Date.now() - mapBoardIndexAt < MAP_BOARD_INDEX_MS) {
    return Promise.resolve(mapBoardIndexCache);
  }
  if (mapBoardIndexWalk) return mapBoardIndexWalk;
  mapBoardIndexWalk = apiPagedList("/whiteboard/boards", 200, { silent: true })
    .catch(() => null)
    .then((rows) => {
      //: The walk failed. The stale index is better than none, and an empty
      //: Map keeps `mapBoardById` and friends synchronous for their callers.
      //: Deliberately not cached as an answer: `mapBoardIndexAt` is untouched,
      //: so the next caller tries again rather than waiting out the eight
      //: seconds on a failure.
      if (!rows) return mapBoardIndexCache || new Map();
      mapBoardIndexAt = Date.now();
      mapBoardIndexCache = new Map(rows.filter((b) => b.id != null).map((b) => [b.id, b]));
      return mapBoardIndexCache;
    })
    .finally(() => {
      mapBoardIndexWalk = null;
    });
  return mapBoardIndexWalk;
}

//: The board behind an entry id, or null, synchronous, because the callers
//: are inside a render loop. Returns null until `loadMapBoardIndex` has run
//: once, which is a surface that has not asked for boards yet rather than an
//: error: it degrades to the plain note rendering it had before.
function mapBoardById(id) {
  return mapBoardIndexCache?.get(id) || null;
}

//: The board whose title is `needle` (already lower-cased), or null.
//:
//: One matcher for the `[[wiki]]` resolver and the editor's `@` picker, so
//: the link the picker inserts and the link the renderer resolves cannot
//: drift apart. A board's own row carries `title` with the `# ` already
//: stripped; the raw `# My map` form is matched too, because that is what
//: the picker inserted before it learned better and those links are in real
//: notes now.
function mapBoardTitled(needle) {
  if (!needle || !mapBoardIndexCache) return null;
  for (const board of mapBoardIndexCache.values()) {
    const title = String(board.title || "").trim().toLowerCase();
    if (!title) continue;
    if (title === needle || `# ${title}` === needle) return board;
  }
  return null;
}

//: Every board the notebook has, newest-looking order preserved from
//: `/whiteboard/boards`, the editor's `@`/`[[` picker's own source. Empty
//: until `loadMapBoardIndex` has run once, which is the same "a surface that
//: has not asked for boards yet" degradation `mapBoardById` documents.
function mapBoardRows() {
  return mapBoardIndexCache ? [...mapBoardIndexCache.values()] : [];
}

//: **Which boards the Library counts** (INBOX 464 (15)): `/whiteboard/boards`
//: always returns the default scratch board (`id: null`), and `/library`
//: lists boards that are notes, which it is not, so Everything said "Boards 1"
//: where Boards & maps said "All 2". The default board is listed when
//: something is on it (its content is reachable only there) and not when it
//: is empty. Every Library view of boards, its counts and the dashboard's
//: widget go through this one predicate.
function libraryListsBoard(board) {
  if (board.id !== null && board.id !== undefined) return true;
  return (board.node_count || 0) + (board.sketch_count || 0) + (board.object_count || 0) > 0;
}

//: ---------------------------------------------------------------------------
//: **Shared by surfaces that are not loaded yet** (WORLD_CLASS_PLAN A1). Five
//: files now arrive on first use rather than at boot (`ensureModule` below),
//: and a `const` in one of them is a *lexical* global: a bare read of it from
//: here throws ReferenceError until that file has run, which no `typeof`
//: guard and no `window.` stub can paper over. Everything in this block was
//: read by app.js's own boot path (the note list) or by `editor.js`, both of
//: which run with no tab open at all, so each one moved here, to the file
//: that is always present, rather than pinning its whole module to boot.
//:
//: None of it is graph, library or document logic: the clamp is the note
//: list's, the size formatter is read by four files, and the page sizes are
//: the paging contract the backend publishes. They were in those files only
//: because that is where the app.js split happened to leave them.

// How much of a linked note's text a link chip shows. Long enough to know
// which note it is, short enough that four of them are a row rather than a
// paragraph: a chip is a signpost, and a signpost with a sentence on it is
// not a signpost. The full text is the chip's tooltip.
//: Raised from 28 (the owner, 2026-09-21: "note text gets cut off at like
//: 2/3 through the note width, I think it should have a bit more width"). A
//: character count rather than a width is what made it look arbitrary: the
//: chip was cut at the same word whether it sat in a 400px column or across
//: a 1900px card, so on a wide card it stopped two thirds of the way along a
//: row that had room to spare. The chips wrap, so a longer label costs a row
//: at worst, never an overflow.
const LINK_CHIP_CHARS = 48;

// How much of a note the list shows before clamping it: a note list is an
// index you scan, so the preview only needs enough to recognise the note.
// Raised again (INBOX 473, "increase the amount of lines or characters"): the
// clamp is `--note-preview-lines` (4, 3 compact, 5 spacious; the CSS holds
// it), and a note of more than three text lines is a candidate for it. The
// settle pass below takes "Show more" back off any note that fits.
const LONG_NOTE_CHARS = 280;
const LONG_NOTE_LINES = 3;
// Which notes the user has opened out, for this session. Not persisted: it is
// a reading position, not a preference.
const expandedNotes = new Set();

//: **"Show more" is offered for text that is clipped, measured** (INBOX 678,
//: the owner: "this note has show more but it doesnt have any text cut off").
//: The character count in `entryItem` decides which notes *might* be too
//: tall; only a measurement can say, because that depends on the width. The
//: clamp goes on optimistically and this takes it back off wherever the note
//: fits. It was one `requestAnimationFrame` after the card was built, plus a
//: settle pass on the threaded render only: a card built while its sub-tab
//: was hidden (every size 0) or appended in a later chunk (not yet in the
//: document) kept its "Show more", and a search or sort never settled at
//: all. A ResizeObserver answers when the text first has a size, whenever
//: that is (shown, scrolled into a `content-visibility` window, a chunk
//: landing) and again when the width changes, and a removed card leaves it.
const noteClampFit = new ResizeObserver((seen) => {
  //: Every read first, then the writes: an unclip between two cards' reads made each next read a forced layout.
  const fits = [];
  for (const { target } of seen) {
    if (!target.isConnected) noteClampFit.unobserve(target);
    else if (target.clientHeight && target.classList.contains("entry-clamped") && target.scrollHeight <= target.clientHeight + 2) fits.push(target);
  }
  for (const target of fits) target.unclip();
});




//: The page size each of those lists is asked for, matching the server's own
//: default (routes_documents.DOCUMENTS_PAGE_SIZE and routes_files
//: .MEDIA_PAGE_SIZE): one request for any realistic notebook, more only when
//: there genuinely is more.
const DOCUMENTS_PAGE_SIZE = 200;
const MEDIA_PAGE_SIZE = 200;

//: **The star that says a note is a favourite, in both states.**
//:
//: Reported with a screenshot: the active one rendered as an **empty circle**
//:, no glyph at all. The cause is worth stating because it is a whole class
//: of bug, not one icon: the off state asked for `ph:star` and the on state
//: for `ph:star-slash`, and **`star-slash` is not in this app's vendored
//: Phosphor subset.** A missing glyph in an icon font is not an error, the
//: character simply has nothing to draw, so it fails silently, looks like a
//: styling problem, and nothing in the suite could see it. One icon name out
//: of 176 was wrong and there was no way to know. `tests/test_icon_names.py`
//: now checks every one against the font.
//:
//: The fix is also the better design. A slashed star means "remove", which is
//: a *verb* on a control whose job is to show *state*; every app the user has
//: ever used shows a favourite as a star that has changed colour. So both
//: states draw `ph:star` and the difference is `is-favourite`, plus
//: `aria-pressed`, which is what makes the state readable without the colour.
//: A meeting note (INBOX 644): typed Meeting, or tagged `meeting` as every
//: meeting is (`entry/meetings.py`'s `is_meeting`, the same two tests).
function noteIsMeeting(entry) {
  return entry.tags.includes("meeting") || /^meeting$/i.test(entry.properties?.type?.[0] || "");
}

// One entry card, shared by the browse list, chat results, and the bin.
// "2 hours ago" style, with the exact date kept for the hover tooltip
// (Wave J). Anything older than a week just shows the date.

// The row menu's "Move to bin", as one function, because the phone's swipe
// (`initRowSwipe`) is the same action from a different gesture and must not
// carry a second copy of it. Instant + one-click Undo, soft delete
// underneath (Wave J). Also on the global undo stack (status bar / Ctrl+Z),
// so it survives past the toast's own timeout.
//: Move to bin keeps keyboard focus (W8): the neighbour is taken before the delete and focused only if focus was lost.
async function binNoteWithUndo(entry) {
  const list = document.getElementById("entry-list");
  const rows = list ? entryListItems(list) : [];
  const at = rows.findIndex((row) => row.dataset.id === String(entry.id));
  const heirId = (rows[at + 1] || rows[at - 1])?.dataset.id;
  await api(`/entries/${entry.id}`, { method: "DELETE" });
  await refreshEntries([entry.id]);
  const held = document.activeElement;
  if (at >= 0 && (!held || held === document.body || !held.isConnected)) {
    const heir = heirId && list.querySelector(`:scope > li[data-id="${heirId}"]`);
    (heir || document.getElementById("capture-bar-input"))?.focus();
  }
  const restoreIt = async () => {
    await api(`/entries/${entry.id}/restore`, { method: "POST" });
    await refreshEntries([entry.id]);
  };
  const binIt = async () => {
    await api(`/entries/${entry.id}`, { method: "DELETE" });
    await refreshEntries([entry.id]);
  };
  const action = pushUndo("Moved a note to the bin", restoreIt, binIt);
  window.nameMarkBuddyReact?.("binned");
  toastAction("Moved to the bin.", "Undo", async () => {
    settleUndoFromToast(action);
    await restoreIt();
    toast("Note restored.");
  }, { also: GO_TO_BIN });
}

let notesSpanMemo = { list: null, many: false };

//: **A note's details line is one line** (INBOX 455 (1), the owner: "note
//: metadata wraps now and needs a better redesign"). Measured at 1100 before:
//: six of ten seeded cards wrapped, and the time sat on a line of its own on
//: some and beside the facts on others. The line is `nowrap`; what does not
//: fit folds, from the end, into one "+N" chip: suggestions first, then tags.
//: The other facts ellipsise if it is still too long (08-consistency.css).
//: Every line on a resize is reset in one pass, read in one layout and folded
//: in a third, so a list of a hundred cards costs two layouts, not a hundred.
const noteMetaFit = new ResizeObserver((seen) => fitNoteMetas(seen.map((s) => s.target)));
//: The icon font landing changes a chip's width but not the line's.
document.fonts?.addEventListener("loadingdone", () => fitNoteMetas([...document.querySelectorAll(".note-meta")]));

function fitNoteMetas(metas) {
  const drawn = [];
  for (const meta of metas) {
    const more = meta.querySelector(":scope > .note-meta-more");
    if (!meta.isConnected) noteMetaFit.unobserve(meta);
    else if (!more) continue;
    //: A card a window off screen is not laid out (`content-visibility`,
    //: 07-whiteboard-misc.css), and measuring it lays it out alone: 60 of
    //: them cost 90ms. It is fitted when it is drawn.
    else if (!meta.checkVisibility({ contentVisibilityAuto: true })) {
      const row = meta.closest("li");
      if (row && !row.metaWait) {
        row.metaWait = 1;
        row.addEventListener("contentvisibilityautostatechange", (event) => event.skipped || fitNoteMetas([meta]));
      }
    } else drawn.push({ meta, more, folds: [...meta.querySelectorAll(":scope > [data-tag]")] });
  }
  //: Most lines fit as drawn: nothing folded, nothing cut, nothing over.
  //: Those are left alone (one shared read), and only the rest are refitted.
  const cut = (meta) => [...meta.querySelectorAll(":scope > .chip > .ph-text")].some((t) => t.scrollWidth > t.clientWidth);
  const lines = drawn.filter(({ meta }) => meta.scrollWidth > meta.clientWidth
    || meta.querySelector(":scope > [data-tag][hidden], :scope > .is-icon") || cut(meta));
  for (const { meta, more, folds } of lines) {
    for (const el of folds) el.hidden = false;
    for (const el of meta.querySelectorAll(":scope > .is-icon")) el.classList.remove("is-icon");
    more.hidden = !folds.length;
    more.firstChild.textContent = `+${folds.length}`;
    meta.classList.add("is-measuring");
  }
  const right = (el) => el.getBoundingClientRect().right;
  //: A first child has no left neighbour (a phone resize, seen in the perch
  //: sweep): measure from its parent's left edge instead.
  const before = (el) => (el.previousElementSibling ? right(el.previousElementSibling) : el.parentElement.getBoundingClientRect().left);
  for (const line of lines) {
    let over = line.meta.scrollWidth - line.meta.clientWidth;
    line.fold = [];
    line.icons = [];
    for (let i = line.folds.length - 1; i >= 0 && over > 0; i--) {
      const el = line.folds[i];
      over -= right(el) - before(el);
      line.fold.push(el);
    }
    //: With every tag gone the "+N" stands alone, a group's gap from the
    //: score rather than a tag's from the tag before it.
    const first = line.meta.querySelector(":scope > .hashtag");
    if (first && line.fold.includes(first)) {
      const gap = (el) => el.getBoundingClientRect().left - before(el);
      over += gap(first) - gap(line.more);
    }
    //: Still too long (a phone, with its ⋯ on the line): the facts after
    //: the tags keep their icon and lose their words, the words on the
    //: title, from the end; the low-score warning goes last.
    //: Ask's match reason folds last too (INBOX 728): an icon-only "70%
    //: similar" beside a worded one read as two different facts.
    const isLast = (text) => text.parentElement.matches(".review, .result-reason-chip");
    const words = [...line.meta.querySelectorAll(":scope > .chip:not(.category, .filing-sure, [data-tag]) > .ph-text")]
      .reverse().sort((x, y) => isLast(x) - isLast(y));
    for (const text of words) {
      if (over <= 0) break;
      over -= right(text) - before(text);
      line.icons.push(text.parentElement);
    }
  }
  for (const { meta, more, fold, icons } of lines) {
    for (const el of fold) el.hidden = true;
    for (const el of icons) {
      el.classList.add("is-icon");
      el.title ||= el.textContent;
      //: Its words are hidden now, so the title alone named it.
      if (el.getAttribute("role") === "button") el.setAttribute("aria-label", el.title);
    }
    more.hidden = !fold.length;
    more.firstChild.textContent = `+${fold.length}`;
    more.setAttribute("aria-label", nounCount(fold.length, "more tag", "more tags"));
    more.title = fold.map((el) => `#${el.dataset.tag}`).reverse().join(" ");
    meta.classList.remove("is-measuring");
  }
}

//: A document is a node of its own (`document:<id>`, routes_graph.py) that the
//: map draws only while its Documents switch is on, so asking for one turns
//: that switch on first, the way the map's own Show switches would.
//: The graph's own half is `graphShowNote` (graph.js, 2026-10-10: the boot
//: script budget); the tab switch loads it first.
async function showNoteInGraph(id, options = {}) {
  await switchTab("graph");
  return graphShowNote(id, options);
}

//: One door into the chat for any object: a note, a document, a board, a
//: file. Named, so the agent's own tools find it.
function askAtlasAboutThing(kind, name) {
  const label = String(name || "").trim().slice(0, 80) || `this ${kind}`;
  switchTab("chat");
  const input = $("chat-input");
  if (!input) return;
  input.value = `Tell me about my ${kind} "${label}" and what it connects to.`;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.focus();
}

//: UX-10: only the Notes list's stop card lends its controls to Tab (27
//: notes were 281 stops); tests/test_entry_list_keys_in_fields.py.
const ENTRY_CARD_CONTROLS = 'button, a[href], summary, input[type="checkbox"], [tabindex="0"]';
function entryCardControls(li, on) {
  if (li.querySelector("textarea, .cm-editor")) on = true;
  for (const el of li.querySelectorAll(ENTRY_CARD_CONTROLS)) {
    if (on && el.dataset.rovingOff !== undefined) {
      if (el.dataset.rovingOff) el.setAttribute("tabindex", el.dataset.rovingOff);
      else el.removeAttribute("tabindex");
      delete el.dataset.rovingOff;
    } else if (!on && el.dataset.rovingOff === undefined && el.tabIndex >= 0) {
      el.dataset.rovingOff = el.getAttribute("tabindex") || "";
      el.tabIndex = -1;
    }
  }
}
function entryListFocusStop(event) {
  const li = event.target.closest("li");
  const items = entryListItems(event.currentTarget);
  if (li && li.tabIndex !== 0 && items.includes(li)) entryListSetStop(items, li);
}
function entryListSetStop(items, stop) {
  for (const li of items) {
    li.tabIndex = li === stop ? 0 : -1;
    entryCardControls(li, li === stop);
  }
}

// The `.unlink` "×" spans (detach/remove/dismiss) predate chip()'s own
// keyboard support and never got it retrofitted, mouse-only, same gap
// chip() already closed once this session for the "Go to note" chip.
// Dispatches a real click rather than duplicating each call site's own
// handler, so this stays a one-line addition wherever a `.unlink` span
// already has its click listener attached.
function makeUnlinkAccessible(span) {
  span.setAttribute("role", "button");
  //: A title alone never shows on touch; callers set it first.
  if (span.title) span.setAttribute("aria-label", span.title);
  span.setAttribute("tabindex", "0");
  span.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      span.click();
    }
  });
}

//: A deduced link reason's confidence as a word, not a percentage (ledger
//: 943): a percentage claimed a precision the guess does not have. Used
//: by the card's link chips and the graph's line tooltip and peek.
function deducedStrength(confidence) {
  if (confidence >= 0.75) return "a strong guess";
  if (confidence >= 0.5) return "a fair guess";
  return "a loose guess";
}
